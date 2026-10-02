from datetime import UTC, date, datetime
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database import Base
from app.models import ImportRun, ModernTrade, SourceFile
from app.services import automatic_import, dh_automatic_import
from app.services.automatic_import import SourceCandidate


def _candidate(path: str, filename: str) -> SourceCandidate:
    return SourceCandidate(
        path=path,
        filename=filename,
        size_bytes=100,
        modified_at=datetime(2025, 1, 8, tzinfo=UTC),
    )


def test_list_dh_pairs_matches_sale_to_next_day_stock_in_same_folder() -> None:
    candidates = [
        _candidate(
            r"\\server\DH\2025-01-07\รายงานยอดขาย06-01-2025_06-01-2025.xlsx",
            "รายงานยอดขาย06-01-2025_06-01-2025.xlsx",
        ),
        _candidate(
            r"\\server\DH\2025-01-07\รายงานสต็อคAll07-01-2025_07-01-2025.xlsx",
            "รายงานสต็อคAll07-01-2025_07-01-2025.xlsx",
        ),
        _candidate(
            r"\\server\DH\2025-01-08\รายงานยอดขาย07-01-2025_07-01-2025.xlsx",
            "รายงานยอดขาย07-01-2025_07-01-2025.xlsx",
        ),
    ]

    pairs = dh_automatic_import.list_dh_pairs(candidates)

    assert len(pairs) == 2
    assert pairs[0].batch_date == date(2025, 1, 7)
    assert pairs[0].inventory is not None
    assert pairs[0].sales is not None
    assert pairs[1].batch_date == date(2025, 1, 8)
    assert pairs[1].inventory is None
    assert pairs[1].sales is not None


def test_automatic_dispatch_uses_dh_coordinator(monkeypatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    called: list[int] = []
    monkeypatch.setattr(
        dh_automatic_import,
        "process_dh_run",
        lambda _session, run_id: called.append(run_id),
    )
    with Session(engine) as session:
        session.add(
            ModernTrade(
                id=1,
                code="DH",
                name="DoHome",
                vat_mode="exclude",
                source_group_code="DH",
            )
        )
        session.add(
            ImportRun(
                id=1,
                modern_trade_id=1,
                trigger="manual",
                mode="import",
                status="running",
                requested_by="operator",
            )
        )
        session.commit()

        automatic_import.process_run(session, 1)

    assert called == [1]


def test_automatic_pair_import_passes_priced_fingerprint_and_tracks_sources(
    monkeypatch,
) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    inventory = _candidate(
        r"\\server\DH\2025-01-07\รายงานสต็อคAll07-01-2025_07-01-2025.xlsx",
        "รายงานสต็อคAll07-01-2025_07-01-2025.xlsx",
    )
    sales = _candidate(
        r"\\server\DH\2025-01-07\รายงานยอดขาย06-01-2025_06-01-2025.xlsx",
        "รายงานยอดขาย06-01-2025_06-01-2025.xlsx",
    )
    pair = dh_automatic_import.DhPairCandidate(
        key="2025-01-07",
        batch_date=date(2025, 1, 7),
        inventory=inventory,
        sales=sales,
    )
    extract = SimpleNamespace(
        inventory_checksum="a" * 64,
        sales_checksum="b" * 64,
        batch_date=date(2025, 1, 7),
    )
    priced = SimpleNamespace(business_fingerprint="c" * 64)
    imported = []
    monkeypatch.setattr(
        dh_automatic_import,
        "_download_pair",
        lambda *_args, **_kwargs: extract,
    )
    monkeypatch.setattr(
        dh_automatic_import,
        "price_dh_import_preview",
        lambda *_args: priced,
    )

    def import_pair(_session, payload, *, actor, expected_fingerprint):
        imported.append((payload, actor, expected_fingerprint))
        return SimpleNamespace(id=99)

    monkeypatch.setattr(dh_automatic_import, "import_dh_pair", import_pair)
    with Session(engine) as session:
        owner = ModernTrade(
            id=1,
            code="DH",
            name="DoHome",
            source_group_code="DH",
        )
        run = ImportRun(
            id=1,
            modern_trade_id=1,
            trigger="manual",
            mode="import",
            status="running",
            requested_by="operator",
        )
        session.add_all([owner, run])
        session.commit()

        outcome = dh_automatic_import._process_pair(
            session,
            run,
            owner,
            pair,
            username="user",
            password="secret",
        )
        sources = session.scalars(
            select(SourceFile).order_by(SourceFile.source_kind)
        ).all()

    assert outcome["status"] == "imported"
    assert imported == [(extract, "operator", "c" * 64)]
    assert [row.status for row in sources] == ["imported", "imported"]
    assert [row.imported_batch_id for row in sources] == [99, 99]
