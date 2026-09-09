import json
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import auth
from app.api.fileshare_settings import (
    FileShareSettingsUpdate,
    FileShareTestRequest,
    SourceProfileUpdate,
    get_fileshare_password,
    update_fileshare_settings,
)
from app.api.fileshare_settings import (
    test_fileshare_settings as _test_fileshare_connection,
)
from app.database import Base
from app.models import AuditEvent, ModernTrade
from app.services import fileshare


def test_unc_normalization_and_traversal_protection() -> None:
    base_unc = r"\\WA-NAS-IT03\FileShare-2\SaleOut_RPT"
    assert fileshare.normalize_base_unc(base_unc) == base_unc
    assert fileshare.normalize_subfolder("TWD") == "TWD"
    assert fileshare.compose_unc(base_unc, "TWD") == f"{base_unc}\\TWD"
    with pytest.raises(fileshare.FileShareSettingsError):
        fileshare.normalize_base_unc(r"C:\SaleOut_RPT")
    with pytest.raises(fileshare.FileShareSettingsError):
        fileshare.normalize_subfolder(r"..\TWD")


def test_password_is_encrypted_and_reveal_respects_environment(monkeypatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(
        fileshare,
        "get_settings",
        lambda: SimpleNamespace(settings_encryption_key=key),
    )
    with Session(engine) as session:
        fileshare.set_password(session, "NAS-SECRET", "test-admin")
        session.commit()
        stored = fileshare.setting_value(session, fileshare.PASSWORD_KEY)
        assert fileshare.password_value(session) == "NAS-SECRET"
        assert "NAS-SECRET" not in (stored or "")

        monkeypatch.setattr(
            "app.api.fileshare_settings.get_settings",
            lambda: SimpleNamespace(allow_secret_reveal=True),
        )
        assert get_fileshare_password(session) == {"password": "NAS-SECRET"}

        monkeypatch.setattr(
            "app.api.fileshare_settings.get_settings",
            lambda: SimpleNamespace(allow_secret_reveal=False),
        )
        with pytest.raises(HTTPException) as error:
            get_fileshare_password(session)
        assert error.value.status_code == 403


def test_save_keeps_existing_password_and_audit_never_contains_secret(monkeypatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(
        fileshare,
        "get_settings",
        lambda: SimpleNamespace(settings_encryption_key=key),
    )
    audit_model = AuditEvent
    monkeypatch.setattr(
        "app.api.fileshare_settings.AuditEvent",
        lambda **values: audit_model(id=1, **values),
    )
    with Session(engine) as session:
        session.add(
            ModernTrade(
                id=1,
                code="TWD",
                name="Thai Watsadu",
                source_subfolder="TWD",
                source_enabled=True,
            )
        )
        fileshare.set_password(session, "NAS-SECRET", "test-admin")
        session.commit()

        response = update_fileshare_settings(
            FileShareSettingsUpdate(
                base_unc=r"\\WA-NAS-IT03\FileShare-2\SaleOut_RPT",
                domain="IT-ADMIN",
                username="svc-mtpulse",
                password=None,
                profiles=[
                    SourceProfileUpdate(code="TWD", subfolder="TWD", enabled=True)
                ],
            ),
            session,
            "development-admin",
        )
        audit = session.scalar(
            select(AuditEvent).where(AuditEvent.entity_id == "fileshare")
        )

        assert response["baseUnc"] == r"\\WA-NAS-IT03\FileShare-2\SaleOut_RPT"
        assert response["passwordConfigured"] is True
        assert fileshare.password_value(session) == "NAS-SECRET"
        assert audit is not None
        audit_payload = f"{audit.before_json}{audit.after_json}"
        assert "NAS-SECRET" not in audit_payload
        assert json.loads(audit.after_json or "{}")["password_updated"] is False


def test_connection_test_is_read_only_and_resets_cache(monkeypatch) -> None:
    paths: list[str] = []
    resets: list[bool] = []
    monkeypatch.setattr(
        fileshare,
        "_stat_path",
        lambda path, username, password: paths.append(path),
    )
    monkeypatch.setattr(
        fileshare.smbclient,
        "reset_connection_cache",
        lambda: resets.append(True),
    )

    base_unc = r"\\WA-NAS-IT03\FileShare-2\SaleOut_RPT"
    results = fileshare.test_paths(
        base_unc=base_unc,
        domain="IT-ADMIN",
        username="svc-mtpulse",
        password="secret",
        profiles=[("TWD", "Thai Watsadu", "TWD")],
    )

    assert paths == [base_unc, f"{base_unc}\\TWD"]
    assert resets == [True]
    assert results[0].status == "success"


def test_dns_resolution_error_has_actionable_message() -> None:
    error = OSError("[Errno -2] Name or service not known")
    assert fileshare.safe_fileshare_error(error) == (
        "ไม่พบชื่อ Server จาก DNS กรุณาใช้ชื่อเต็ม เช่น server.domain"
    )


def test_development_auth_stub_and_ad_boundary(monkeypatch) -> None:
    monkeypatch.setattr(
        auth,
        "get_settings",
        lambda: SimpleNamespace(auth_mode="development"),
    )
    assert auth.require_system_admin() == "development-admin"

    monkeypatch.setattr(
        auth,
        "get_settings",
        lambda: SimpleNamespace(auth_mode="ad"),
    )
    with pytest.raises(HTTPException) as error:
        auth.require_system_admin()
    assert error.value.status_code == 503


def test_shared_hp_mh_connection_tests_the_physical_path_once(monkeypatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    captured: list[list[tuple[str, str, str]]] = []
    monkeypatch.setattr(
        "app.api.fileshare_settings.test_paths",
        lambda **values: captured.append(values["profiles"]) or [],
    )
    monkeypatch.setattr(
        "app.api.fileshare_settings.record_test",
        lambda session, results, actor: "success",
    )
    audit_model = AuditEvent
    monkeypatch.setattr(
        "app.api.fileshare_settings.AuditEvent",
        lambda **values: audit_model(id=1, **values),
    )
    with Session(engine) as session:
        session.add_all(
            [
                ModernTrade(
                    id=1,
                    code="HP",
                    name="HomePro",
                    source_group_code="HP_MH",
                ),
                ModernTrade(
                    id=2,
                    code="MH",
                    name="MegaHome",
                    source_group_code="HP_MH",
                ),
            ]
        )
        session.commit()
        request = FileShareTestRequest(
            base_unc=r"\\server\share",
            domain="WA",
            username="user",
            password="secret",
            profiles=[
                SourceProfileUpdate(code="HP", subfolder="HP_MH", enabled=True),
                SourceProfileUpdate(code="MH", subfolder="HP_MH", enabled=True),
            ],
        )

        response = _test_fileshare_connection(request, session, "admin")

    assert response["status"] == "success"
    assert captured == [[("HP", "HomePro", "HP_MH")]]
