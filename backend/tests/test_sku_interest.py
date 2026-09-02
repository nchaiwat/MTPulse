from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database import Base
from app.importers.twd import TwdExtract, TwdRow, summarize
from app.models import AuditEvent, ModernTrade, SkuInterest
from app.services import sku_interest
from app.services.sku_interest import decide_sku_interest, sync_sku_interests
from app.services.twd_import import _build_facts


def _row(sku: str) -> TwdRow:
    return TwdRow(
        branch_code="60016",
        branch_name="ภูเก็ต เฟสติวัล",
        category=None,
        subcategory=None,
        brand=None,
        sku=sku,
        barcode=None,
        description=f"สินค้า {sku}",
        product_type=None,
        source_amount=Decimal("107"),
        amount=Decimal("100"),
        sales_qty=Decimal("1"),
        stock_on_hand=Decimal("2"),
        stock_on_order=Decimal("0"),
        last_sold_date=None,
        last_receive_date=None,
    )


def _extract(*skus: str) -> TwdExtract:
    rows = tuple(_row(sku) for sku in skus)
    summary = summarize(rows)
    return TwdExtract(
        source_path="//server/share/TWD/2026-09-01/file.xls",
        source_filename="file.xls",
        checksum_sha256="a" * 64,
        data_date=date(2026, 9, 1),
        rows=rows,
        summary=summary,
        reported_summary=summary,
        reconciliation_errors=(),
    )


def _engine():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return engine


def test_initial_scan_marks_unknown_skus_ignored_baseline() -> None:
    with Session(_engine()) as session:
        session.add(ModernTrade(id=1, code="TWD", name="Thai Watsadu"))
        session.add(
            SkuInterest(
                modern_trade_id=1,
                source_sku="ACTIVE",
                source_description="สินค้า ACTIVE",
                status="active",
                first_seen_date=date(2026, 8, 1),
                last_seen_date=date(2026, 8, 1),
            )
        )
        session.commit()

        result = sync_sku_interests(
            session,
            1,
            _extract("ACTIVE", "BASELINE"),
            baseline=True,
        )
        session.commit()

        interests = {
            row.source_sku: row.status
            for row in session.scalars(select(SkuInterest))
        }
        assert result.stored_skus == frozenset({"ACTIVE"})
        assert result.new_ignored_skus == ("BASELINE",)
        assert interests == {"ACTIVE": "active", "BASELINE": "ignored"}


def test_import_stores_active_and_new_pending_but_skips_ignored() -> None:
    with Session(_engine()) as session:
        session.add(ModernTrade(id=1, code="TWD", name="Thai Watsadu"))
        session.add_all(
            [
                SkuInterest(
                    modern_trade_id=1,
                    source_sku="ACTIVE",
                    source_description="สินค้า ACTIVE",
                    status="active",
                    first_seen_date=date(2026, 8, 1),
                    last_seen_date=date(2026, 8, 1),
                ),
                SkuInterest(
                    modern_trade_id=1,
                    source_sku="IGNORED",
                    source_description="สินค้า IGNORED",
                    status="ignored",
                    first_seen_date=date(2026, 8, 1),
                    last_seen_date=date(2026, 8, 1),
                ),
            ]
        )
        session.commit()

        extract = _extract("ACTIVE", "IGNORED", "NEW")
        result = sync_sku_interests(session, 1, extract, baseline=False)
        facts = _build_facts(
            1,
            1,
            extract,
            stored_skus=result.stored_skus,
        )
        session.commit()

        stored_skus = {fact.source_sku for fact in facts}
        new_interest = session.scalar(
            select(SkuInterest).where(SkuInterest.source_sku == "NEW")
        )
        assert stored_skus == {"ACTIVE", "NEW"}
        assert new_interest is not None
        assert new_interest.status == "pending"


def test_ignore_is_reversible_without_deleting_history(monkeypatch) -> None:
    audit_id = iter((1, 2))
    monkeypatch.setattr(
        sku_interest,
        "AuditEvent",
        lambda **values: AuditEvent(id=next(audit_id), **values),
    )
    with Session(_engine()) as session:
        session.add(ModernTrade(id=1, code="TWD", name="Thai Watsadu"))
        session.add(
            SkuInterest(
                id=1,
                modern_trade_id=1,
                source_sku="NEW",
                source_description="สินค้า NEW",
                status="pending",
                first_seen_date=date(2026, 9, 1),
                last_seen_date=date(2026, 9, 1),
            )
        )
        session.commit()

        interest = session.get(SkuInterest, 1)
        assert interest is not None
        decide_sku_interest(session, interest, decision="ignore", actor="admin")
        assert session.get(SkuInterest, 1).status == "ignored"

        interest = session.get(SkuInterest, 1)
        assert interest is not None
        decide_sku_interest(session, interest, decision="accept", actor="admin")
        assert session.get(SkuInterest, 1).status == "active"
