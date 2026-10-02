# ruff: noqa: F811
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select
from test_ciam_auth import account, auth_client, sign_in  # noqa: F401

from app.models import AuthSession, CiamAgentCommand
from app.services import ciam_agent


def command(cid="one", action="DISABLE_USER", **kw):
    return {
        "command_id": cid,
        "action": action,
        "username": "tester",
        "issued_at": "2026-10-02T10:00:00Z",
        "reason": "Offboarding",
        **kw,
    }


def test_command_disable_enable_and_duplicate(auth_client):
    client, db = auth_client
    user = account(db, role="viewer")
    sign_in(client, db, user)
    result = ciam_agent.apply_command(db, "scope", command())
    assert result["status"] == "COMPLETED"
    db.refresh(user)
    assert not user.active and not list(db.scalars(select(AuthSession)))
    assert ciam_agent.apply_command(db, "scope", command()) == result
    with pytest.raises(ValueError):
        ciam_agent.apply_command(db, "scope", command(action="ENABLE_USER"))
    assert (
        ciam_agent.apply_command(
            db, "scope", command("two", "ENABLE_USER", issued_at="2026-10-02T10:01:00Z")
        )["status"]
        == "COMPLETED"
    )
    db.refresh(user)
    assert user.active
    assert (
        ciam_agent.apply_command(db, "scope", command("old", issued_at="2026-10-02T09:59:00Z"))[
            "status"
        ]
        == "FAILED"
    )


def test_emergency_account_protected(auth_client):
    _, db = auth_client
    account(db, issuer="urn:mtpulse:local")
    assert ciam_agent.apply_command(db, "scope", command())["status"] == "FAILED"


def test_agent_settings_admin_encrypted_and_do_not_revoke_session(auth_client):
    client, db = auth_client
    sign_in(client, db, account(db))
    result = client.put(
        "/api/settings/ciam-agent",
        json={"enabled": False, "app_code": "mtpulse", "api_key": "private-agent-key"},
    )
    assert result.status_code == 200
    assert "private-agent-key" not in result.text
    assert client.get("/api/auth/me").status_code == 200
    assert result.json()["key_configured"]


def test_cycle_resends_results_until_ack(auth_client, monkeypatch):
    _, db = auth_client
    account(db, role="viewer")
    from app.services import ciam

    ciam.save_config(db, {"ciam_client_id": "fixture-client"}, "test")
    ciam_agent.save_config(
        db, {"enabled": True, "app_code": "mtpulse", "api_key": "private-agent-key"}, "test"
    )
    calls = []

    def post(*a, **kw):
        calls.append(kw["json"])
        return {
            "status": "ACKNOWLEDGED",
            "app_code": "mtpulse",
            "next_heartbeat_seconds": 120,
            "pending_commands": [command()] if len(calls) == 1 else [],
        }

    monkeypatch.setattr(ciam_agent, "send_heartbeat", post)
    monkeypatch.setattr(ciam_agent, "api_healthy", lambda: True)
    now = datetime.now(UTC)
    ciam_agent.cycle(db, now)
    assert calls[0]["sync_type"] == "FULL_SYNC"
    row = db.scalar(select(CiamAgentCommand))
    assert not row.acknowledged

    def timeout(*a, **kw):
        raise httpx.ReadTimeout("must not leak private-agent-key")

    monkeypatch.setattr(ciam_agent, "send_heartbeat", timeout)
    ciam_agent.cycle(db, now + timedelta(seconds=121))
    db.refresh(row)
    assert not row.acknowledged
    monkeypatch.setattr(ciam_agent, "send_heartbeat", post)
    ciam_agent.cycle(db, now + timedelta(seconds=242))
    db.refresh(row)
    assert row.acknowledged
    assert calls[-1]["command_results"][0]["command_id"] == "one"
    assert "private-agent-key" not in json.dumps(ciam_agent.status(db))


@pytest.mark.parametrize("role", ["viewer", "operator"])
def test_agent_settings_denies_non_admin(auth_client, role):
    client, db = auth_client
    sign_in(client, db, account(db, role=role))
    assert client.get("/api/settings/ciam-agent").status_code == 403
    assert client.put("/api/settings/ciam-agent", json={}).status_code == 403
    assert client.post("/api/settings/ciam-agent/reveal").status_code == 403


def test_agent_settings_csrf_and_secret_audit(auth_client):
    client, db = auth_client
    sign_in(client, db, account(db))
    assert (
        client.put("/api/settings/ciam-agent", json={}, headers={"X-CSRF-Token": "bad"}).status_code
        == 403
    )
    client.put("/api/settings/ciam-agent", json={"api_key": "private-key"})
    revealed = client.post("/api/settings/ciam-agent/reveal")
    assert revealed.json()["value"] == "private-key"
    assert revealed.headers["cache-control"] == "no-store"
    from app.models import SystemSetting, TransactionLog

    assert all("private-key" not in (r.details or "") for r in db.scalars(select(TransactionLog)))
    row = db.scalar(select(SystemSetting).where(SystemSetting.key == "ciam_agent_api_key"))
    assert row.value != "private-key"


def test_enable_overrides_local_disable_without_restoring_sessions(auth_client):
    _, db = auth_client
    user = account(db, role="viewer")
    user.active = False
    db.commit()
    assert (
        ciam_agent.apply_command(db, "scope", command(action="ENABLE_USER"))["status"]
        == "COMPLETED"
    )
    db.refresh(user)
    assert user.active and not list(db.scalars(select(AuthSession)))


def test_last_admin_and_unknown_user_rejected(auth_client):
    _, db = auth_client
    account(db)
    assert ciam_agent.apply_command(db, "scope", command())["status"] == "FAILED"
    assert (
        ciam_agent.apply_command(db, "scope", command("missing", username="unknown"))["status"]
        == "FAILED"
    )


def test_restart_resumes_durable_inbox_before_next_heartbeat(auth_client, monkeypatch):
    _, db = auth_client
    user = account(db, role="viewer")
    from app.services import ciam

    ciam.save_config(db, {"ciam_client_id": "client"}, "test")
    ciam_agent.save_config(db, {"enabled": True, "api_key": "private"}, "test")
    scope = ciam_agent.digest(["https://ciam.windowasia.com", "client", "mtpulse"])
    content = ciam_agent.Command.model_validate(command()).model_dump(mode="json")
    db.add(
        CiamAgentCommand(
            key=ciam_agent.digest([scope, "one"]),
            scope=scope,
            command_id="one",
            fingerprint=ciam_agent.digest(content),
            username="tester",
            issued_at=datetime.now(UTC),
            payload=json.dumps(content),
            result=json.dumps({"status": "PENDING"}),
            acknowledged=False,
        )
    )
    ciam_agent.store_state(
        db, {"next_attempt": (datetime.now(UTC) + timedelta(minutes=2)).isoformat()}
    )
    db.commit()
    monkeypatch.setattr(ciam_agent, "send_heartbeat", lambda *a, **k: pytest.fail("not due"))
    ciam_agent.cycle(db)
    db.refresh(user)
    assert not user.active


@pytest.mark.parametrize(
    "response",
    [
        {"status": "ACKNOWLEDGED", "app_code": "other", "pending_commands": [command()]},
        {
            "status": "ACKNOWLEDGED",
            "app_code": "mtpulse",
            "pending_commands": [{"username": "tester"}],
        },
        {
            "status": "ACKNOWLEDGED",
            "app_code": "mtpulse",
            "pending_commands": [command(), command(action="ENABLE_USER")],
        },
    ],
)
def test_invalid_provider_response_never_mutates_accounts(auth_client, monkeypatch, response):
    _, db = auth_client
    user = account(db, role="viewer")
    from app.services import ciam

    ciam.save_config(db, {"ciam_client_id": "client"}, "test")
    ciam_agent.save_config(db, {"enabled": True, "api_key": "private"}, "test")
    monkeypatch.setattr(ciam_agent, "send_heartbeat", lambda *a, **kw: response)
    monkeypatch.setattr(ciam_agent, "api_healthy", lambda: True)
    ciam_agent.cycle(db, datetime(2026, 10, 2, 12, tzinfo=UTC))
    db.refresh(user)
    assert user.active
    assert not list(db.scalars(select(CiamAgentCommand)))
    assert ciam_agent.status(db)["last_error"]
