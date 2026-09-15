import json
from collections.abc import Iterator
from datetime import date
from io import BytesIO
from itertools import count

import openpyxl
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.dh_prices import router
from app.auth import require_data_operator
from app.database import Base, get_session
from app.models import AuditEvent, DhEffectivePrice, ModernTrade
from app.services.dh_price_master import (
    DhPricePreviewStaleError,
    confirm_dh_price_master,
    preview_dh_price_master,
)

HEADERS = ("SKU", "Price Ex VAT", "Effective From", "Effective To")
XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _workbook_bytes(rows: list[tuple[object, ...]]) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "DH Price Master"
    sheet.append(HEADERS)
    for row in rows:
        sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


@pytest.fixture
def database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    generated_ids = count(1)

    @event.listens_for(Session, "before_flush")
    def assign_sqlite_bigint_ids(
        session: Session,
        _flush_context: object,
        _instances: object,
    ) -> None:
        if session.bind is not engine:
            return
        for row in session.new:
            if isinstance(row, (DhEffectivePrice, AuditEvent)) and row.id is None:
                row.id = next(generated_ids)

    with Session(engine) as session:
        session.add(
            ModernTrade(id=1, code="DH", name="DoHome", vat_mode="exclude")
        )
        session.commit()
    try:
        yield engine
    finally:
        event.remove(Session, "before_flush", assign_sqlite_bigint_ids)
        engine.dispose()


def _client(database, *, allowed: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    def session_override() -> Iterator[Session]:
        with Session(database) as session:
            yield session

    def operator_override() -> str:
        if allowed:
            return "data-operator@test"
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์จัดการ DH Price Master")

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_data_operator] = operator_override
    return TestClient(app)


def test_dh_price_template_requires_operator_and_returns_xlsx(database) -> None:
    denied = _client(database, allowed=False).get("/api/dh-prices/template")
    assert denied.status_code == 403

    response = _client(database).get("/api/dh-prices/template")

    assert response.status_code == 200
    assert response.headers["content-type"] == XLSX_TYPE
    assert "DH_Price_Master_Template.xlsx" in response.headers["content-disposition"]
    workbook = openpyxl.load_workbook(BytesIO(response.content), data_only=True)
    assert tuple(cell.value for cell in workbook["DH Price Master"][1]) == HEADERS
    workbook.close()


def test_preview_confirm_and_paginated_list_are_one_audited_workflow(database) -> None:
    with Session(database) as session:
        session.add(
            DhEffectivePrice(
                id=100,
                modern_trade_id=1,
                source_sku="A",
                unit_price_ex_vat=100,
                effective_from=date(2025, 1, 1),
                effective_to=None,
                source_filename="old.xlsx",
                source_checksum_sha256="a" * 64,
                changed_by="original",
            )
        )
        session.add(
            DhEffectivePrice(
                id=103,
                modern_trade_id=1,
                source_sku="C",
                unit_price_ex_vat=300,
                effective_from=date(2025, 1, 1),
                effective_to=None,
                source_filename="old.xlsx",
                source_checksum_sha256="a" * 64,
                changed_by="original",
            )
        )
        session.commit()
    content = _workbook_bytes(
        [
            ("A", 110, date(2025, 1, 1), None),
            ("B", 200, date(2025, 1, 1), None),
            ("C", 300, date(2025, 1, 1), None),
        ]
    )
    client = _client(database)

    preview = client.post(
        "/api/dh-prices/preview",
        files={"file": ("prices.xlsx", content, XLSX_TYPE)},
    )

    assert preview.status_code == 200
    preview_body = preview.json()
    assert preview_body["inserted"] == 1
    assert preview_body["updated"] == 1
    assert preview_body["unchanged"] == 1
    assert preview_body["errors"] == []
    assert len(preview_body["preview_fingerprint"]) == 64

    confirmed = client.post(
        "/api/dh-prices/confirm",
        data={"preview_fingerprint": preview_body["preview_fingerprint"]},
        files={"file": ("prices.xlsx", content, XLSX_TYPE)},
    )

    assert confirmed.status_code == 200
    assert confirmed.json()["inserted"] == 1
    assert confirmed.json()["updated"] == 1
    with Session(database) as session:
        rows = session.scalars(
            select(DhEffectivePrice).order_by(DhEffectivePrice.source_sku)
        ).all()
        audits = session.scalars(
            select(AuditEvent).order_by(AuditEvent.entity_id)
        ).all()
        assert [(row.source_sku, int(row.unit_price_ex_vat)) for row in rows] == [
            ("A", 110),
            ("B", 200),
            ("C", 300),
        ]
        assert [row.action for row in audits] == [
            "update_dh_price",
            "create_dh_price",
        ]
        assert all(row.actor == "data-operator@test" for row in audits)
        update_before = json.loads(audits[0].before_json)
        assert update_before["source_filename"] == "old.xlsx"
        assert update_before["changed_by"] == "original"

    listed = client.get(
        "/api/dh-prices",
        params={
            "status": "current",
            "as_of": "2025-01-15",
            "page": 1,
            "page_size": 1,
            "q": "A",
        },
    )

    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["source_sku"] == "A"
    assert listed.json()["items"][0]["status"] == "current"


def test_price_list_filters_current_upcoming_and_expired(database) -> None:
    with Session(database) as session:
        session.add_all(
            [
                DhEffectivePrice(
                    id=110,
                    modern_trade_id=1,
                    source_sku="CURRENT",
                    unit_price_ex_vat=100,
                    effective_from=date(2025, 1, 1),
                    effective_to=None,
                    source_filename="prices.xlsx",
                    source_checksum_sha256="a" * 64,
                    changed_by="operator",
                ),
                DhEffectivePrice(
                    id=111,
                    modern_trade_id=1,
                    source_sku="UPCOMING",
                    unit_price_ex_vat=100,
                    effective_from=date(2025, 2, 1),
                    effective_to=None,
                    source_filename="prices.xlsx",
                    source_checksum_sha256="a" * 64,
                    changed_by="operator",
                ),
                DhEffectivePrice(
                    id=112,
                    modern_trade_id=1,
                    source_sku="EXPIRED",
                    unit_price_ex_vat=100,
                    effective_from=date(2024, 1, 1),
                    effective_to=date(2024, 12, 31),
                    source_filename="prices.xlsx",
                    source_checksum_sha256="a" * 64,
                    changed_by="operator",
                ),
            ]
        )
        session.commit()
    client = _client(database)

    results = {
        status: client.get(
            "/api/dh-prices",
            params={"status": status, "as_of": "2025-01-15"},
        ).json()
        for status in ("current", "upcoming", "expired")
    }

    assert [item["source_sku"] for item in results["current"]["items"]] == [
        "CURRENT"
    ]
    assert [item["source_sku"] for item in results["upcoming"]["items"]] == [
        "UPCOMING"
    ]
    assert [item["source_sku"] for item in results["expired"]["items"]] == [
        "EXPIRED"
    ]


def test_confirm_rejects_stale_preview_without_mutation(database) -> None:
    content = _workbook_bytes([("A", 100, date(2025, 1, 1), None)])
    with Session(database) as session:
        preview = preview_dh_price_master(session, content)
        session.add(
            DhEffectivePrice(
                id=101,
                modern_trade_id=1,
                source_sku="OTHER",
                unit_price_ex_vat=50,
                effective_from=date(2025, 1, 1),
                effective_to=None,
                source_filename="other.xlsx",
                source_checksum_sha256="b" * 64,
                changed_by="other",
            )
        )
        session.commit()

        with pytest.raises(DhPricePreviewStaleError):
            confirm_dh_price_master(
                session,
                content,
                filename="prices.xlsx",
                actor="operator",
                expected_preview_fingerprint=preview.preview_fingerprint,
            )

        assert session.scalar(
            select(DhEffectivePrice).where(DhEffectivePrice.source_sku == "A")
        ) is None


def test_confirm_rolls_back_price_and_audit_when_commit_fails(
    database,
    monkeypatch,
) -> None:
    content = _workbook_bytes([("A", 100, date(2025, 1, 1), None)])
    with Session(database) as session:
        preview = preview_dh_price_master(session, content)

        def fail_commit() -> None:
            raise RuntimeError("database unavailable")

        monkeypatch.setattr(session, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="database unavailable"):
            confirm_dh_price_master(
                session,
                content,
                filename="prices.xlsx",
                actor="operator",
                expected_preview_fingerprint=preview.preview_fingerprint,
            )

        assert session.scalars(select(DhEffectivePrice)).all() == []
        assert session.scalars(select(AuditEvent)).all() == []


def test_confirm_rejects_wrong_extension_and_stale_api_preview(database) -> None:
    content = _workbook_bytes([("A", 100, date(2025, 1, 1), None)])
    client = _client(database)
    wrong_type = client.post(
        "/api/dh-prices/preview",
        files={"file": ("prices.csv", content, "text/csv")},
    )
    assert wrong_type.status_code == 400

    preview = client.post(
        "/api/dh-prices/preview",
        files={"file": ("prices.xlsx", content, XLSX_TYPE)},
    ).json()
    with Session(database) as session:
        session.add(
            DhEffectivePrice(
                id=102,
                modern_trade_id=1,
                source_sku="OTHER",
                unit_price_ex_vat=50,
                effective_from=date(2025, 1, 1),
                source_filename="other.xlsx",
                source_checksum_sha256="c" * 64,
                changed_by="other",
            )
        )
        session.commit()

    stale = client.post(
        "/api/dh-prices/confirm",
        data={"preview_fingerprint": preview["preview_fingerprint"]},
        files={"file": ("prices.xlsx", content, XLSX_TYPE)},
    )
    assert stale.status_code == 409
