from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx
import jwt
import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Response
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth import PUBLIC_PATHS, SESSION_COOKIE, digest
from app.config import get_settings
from app.database import Base, get_session
from app.main import app
from app.models import AuditEvent, AuthSession, AuthUser, SystemSetting
from app.services import ciam, local_auth


@pytest.fixture
def auth_client(monkeypatch):
    monkeypatch.setenv("MTPULSE_AUTH_MODE", "ciam")
    monkeypatch.setenv("MTPULSE_SETTINGS_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        app.dependency_overrides[get_session] = lambda: session
        try:
            with TestClient(app, base_url="https://wa-mtpulse.wa.net") as client:
                yield client, session
        finally:
            app.dependency_overrides.clear()
            get_settings.cache_clear()
    engine.dispose()


def test_ciam_mode_denies_anonymous_business_access(auth_client):
    client, _ = auth_client
    assert client.get("/api/performance").status_code == 401


ORIGIN = "https://wa-mtpulse.wa.net"


def account(session, role="admin", issuer="https://ciam.windowasia.com"):
    user = AuthUser(
        id=str(uuid4()),
        issuer=issuer,
        subject=str(uuid4()),
        username="tester",
        full_name="Test User",
        role=role,
        active=True,
        created_at=datetime.now(UTC),
    )
    session.add(user)
    session.commit()
    return user


def sign_in(client, session, user, provider="sso"):
    response = Response()
    login = ciam.issue_session(session, response, user, provider, 480)
    token = response.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1]
    client.cookies.set(SESSION_COOKIE, token)
    client.headers.update({"X-CSRF-Token": login["csrf_token"], "Origin": ORIGIN})
    return token


def test_all_business_routes_require_login(auth_client):
    client, _ = auth_client
    for route in app.routes:
        if not isinstance(route, APIRoute) or route.path in PUBLIC_PATHS:
            continue
        path = route.path
        import re

        path = re.sub(r"\{[^}]+\}", "1", path)
        for method in route.methods - {"HEAD", "OPTIONS"}:
            result = client.request(method, path)
            assert result.status_code == 401, (method, path, result.text)


@pytest.mark.parametrize("role", ["viewer", "operator"])
def test_roles_cannot_read_secrets_or_manage_users(auth_client, role):
    client, session = auth_client
    sign_in(client, session, account(session, role))
    for path in [
        "/api/settings/ciam-sso",
        "/api/settings/system/telegram/token",
        "/api/admin/fileshare-settings",
        "/api/monitoring",
    ]:
        assert client.get(path).status_code == 403
    assert (
        client.post(
            "/api/auth/sso/break-glass-toggle", json={"active": True, "reason": "outage"}
        ).status_code
        == 403
    )
    assert (
        client.post("/api/admin/imports/manual-batches", json={"file_count": 1}).status_code == 403
    )


def test_viewer_readonly_operator_can_reach_mapping(auth_client):
    client, session = auth_client
    sign_in(client, session, account(session, "viewer"))
    assert client.get("/api/performance").status_code == 404  # Authorized, no fixture MT.
    assert client.post("/api/item-mappings/import").status_code == 403
    assert client.patch("/api/performance/sku-flags/HH/1", json={}).status_code == 403
    sign_in(client, session, account(session, "operator"))
    assert client.post("/api/item-mappings/import").status_code == 422  # Missing file.
    assert client.get("/api/settings/modern-trades/HH/unmatched-visibility").status_code == 404


def test_csrf_expiry_deactivation_and_fixed_lifetime(auth_client):
    client, session = auth_client
    user = account(session)
    token = sign_in(client, session, user)
    login = session.get(AuthSession, digest(token))
    original = login.expires_at
    assert client.get("/api/auth/me").status_code == 200
    assert login.expires_at == original
    assert client.post("/api/auth/logout", headers={"X-CSRF-Token": "wrong"}).status_code == 403
    user.active = False
    session.commit()
    assert client.get("/api/auth/me").status_code == 401
    user.active = True
    login.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session.commit()
    assert client.get("/api/auth/me").status_code == 401


def test_local_login_logout_rate_limit_and_no_password_leak(auth_client):
    client, session = auth_client
    password = "a-strong-emergency-password"
    user = local_auth.bootstrap(session, "Emergency", password)
    assert password not in user.password_hash
    client.headers["Origin"] = ORIGIN
    result = client.post(
        "/api/auth/local/login", json={"username": "emergency", "password": password}
    )
    assert result.status_code == 200
    assert "HttpOnly" in result.headers["set-cookie"] and "Secure" in result.headers["set-cookie"]
    assert result.json()["user"]["role"] == "admin"
    assert password not in result.text
    client.headers["X-CSRF-Token"] = result.json()["csrf_token"]
    assert client.get("/api/auth/me").status_code == 200
    result = client.post("/api/auth/logout")
    assert result.json()["redirect_url"] == "/login"
    assert client.get("/api/auth/me").status_code == 401
    for _ in range(10):
        result = client.post(
            "/api/auth/local/login", json={"username": "emergency", "password": "bad"}
        )
    assert result.status_code == 429
    audits = list(session.scalars(select(AuditEvent)))
    assert any(a.action == "login_failed" for a in audits)
    assert all(password not in (a.after_json or "") for a in audits)


def test_settings_encrypt_secret_and_take_effect_immediately(auth_client):
    client, session = auth_client
    sign_in(client, session, account(session))
    local_auth.bootstrap(session, "emergency", "a-long-local-password")
    values = {
        **ciam.DEFAULTS,
        "ciam_client_id": "registered-client",
        "ciam_client_secret": "secret-value-never-return",
        "ciam_sso_enabled": True,
    }
    values.pop("ciam_break_glass_active")
    result = client.put("/api/settings/ciam-sso", json=values)
    assert result.status_code == 200, result.text
    assert "secret-value" not in result.text
    stored = session.get(SystemSetting, "ciam_client_secret")
    assert stored.is_secret and "secret-value" not in stored.value
    assert client.get("/api/auth/sso/config").json()["sso_enabled"] is True
    assert ciam.config(session, secret=True)["ciam_client_secret"] == values["ciam_client_secret"]
    values["ciam_client_secret"] = None
    assert client.put("/api/settings/ciam-sso", json=values).status_code == 200
    assert ciam.config(session, secret=True)["ciam_client_secret"] == "secret-value-never-return"
    assert all(
        "secret-value" not in (a.after_json or "") for a in session.scalars(select(AuditEvent))
    )
    assert (
        client.post(
            "/api/auth/sso/break-glass-toggle", json={"active": True, "reason": "CIAM outage"}
        ).status_code
        == 200
    )
    assert client.post("/api/auth/sso/authorize-url").status_code == 503


@pytest.fixture
def provider(auth_client, monkeypatch):
    client, session = auth_client
    cfg = {
        **ciam.DEFAULTS,
        "ciam_client_id": "test-client",
        "ciam_client_secret": "provider-secret",
        "ciam_sso_enabled": True,
    }
    ciam.save_config(session, cfg, "test")
    doc = {
        "issuer": cfg["ciam_base_url"],
        "authorization_endpoint": cfg["ciam_base_url"] + "/authorize",
        "token_endpoint": cfg["ciam_base_url"] + "/token",
        "jwks_uri": cfg["ciam_base_url"] + "/jwks",
    }
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    public.update({"kid": "test-key", "alg": "RS256", "use": "sig"})
    monkeypatch.setattr(ciam, "discovery", lambda _: doc)
    monkeypatch.setattr(ciam, "jwks", lambda _: {"keys": [public]})
    claims_overrides = {}
    calls = []

    class ProviderClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, data):
            calls.append(data)
            now = int(datetime.now(UTC).timestamp())
            claims = {
                "iss": cfg["ciam_base_url"],
                "aud": "test-client",
                "sub": "employee-123",
                "iat": now,
                "exp": now + 300,
                "nonce": query["nonce"][0],
                "preferred_username": "employee",
                "email": "employee@example.test",
            }
            claims.update(claims_overrides)
            token = jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-key"})
            return httpx.Response(200, json={"id_token": token}, request=httpx.Request("POST", url))

    client.headers["Origin"] = ORIGIN
    result = client.post("/api/auth/sso/authorize-url")
    assert result.status_code == 200, result.text
    query = parse_qs(urlsplit(result.json()["authorize_url"]).query)
    assert query["code_challenge_method"] == ["S256"]
    assert "verifier" not in result.text
    monkeypatch.setattr(ciam.httpx, "Client", ProviderClient)
    return client, session, query, claims_overrides, calls


def test_signed_sso_provisions_viewer_single_use_and_logout(provider):
    client, session, query, _, calls = provider
    payload = {"code": "one-time-code", "state": query["state"][0]}
    result = client.post("/api/auth/sso/callback", json=payload)
    assert result.status_code == 200, result.text
    assert result.json()["user"]["role"] == "viewer"
    assert len(calls) == 1 and len(calls[0]["code_verifier"]) >= 64
    assert client.post("/api/auth/sso/callback", json=payload).status_code == 401
    assert len(calls) == 1
    client.headers["X-CSRF-Token"] = result.json()["csrf_token"]
    assert (
        client.post("/api/auth/logout").json()["redirect_url"]
        == "https://ciam.windowasia.com/portal"
    )
    assert client.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize(
    "bad_claims",
    [
        {"nonce": "wrong"},
        {"iss": "https://attacker.test"},
        {"aud": "other-app"},
        {"exp": 1},
        {"sub": ""},
        {"azp": "other-app"},
        {"aud": ["test-client", "other-app"]},
        {"iat": 9999999999},
    ],
)
def test_invalid_signed_claims_rejected(provider, bad_claims):
    client, session, query, overrides, _ = provider
    overrides.update(bad_claims)
    result = client.post(
        "/api/auth/sso/callback", json={"code": "code", "state": query["state"][0]}
    )
    assert result.status_code == 401
    assert session.scalar(select(AuthUser)) is None


def test_callback_browser_binding_and_settings_rotation(provider):
    client, session, query, _, calls = provider
    payload = {"code": "code", "state": query["state"][0]}
    cookies = dict(client.cookies)
    client.cookies.clear()
    assert client.post("/api/auth/sso/callback", json=payload).status_code == 401
    assert not calls
    client.cookies.update(cookies)
    ciam.save_config(session, {"ciam_client_id": "rotated"}, "test")
    assert client.post("/api/auth/sso/callback", json=payload).status_code == 401
    assert not calls


def test_role_change_revokes_sessions_and_admin_cannot_demote_self(auth_client):
    client, session = auth_client
    admin = account(session)
    viewer = account(session, "viewer")
    viewer_token = sign_in(client, session, viewer)
    sign_in(client, session, admin)
    result = client.patch(
        f"/api/settings/ciam-sso/users/{viewer.id}", json={"role": "operator", "active": True}
    )
    assert result.status_code == 200
    assert session.get(AuthSession, digest(viewer_token)) is None
    assert (
        client.patch(
            f"/api/settings/ciam-sso/users/{admin.id}", json={"role": "viewer", "active": True}
        ).status_code
        == 422
    )


def test_cross_origin_login_blocked(auth_client):
    client, _ = auth_client
    assert (
        client.post(
            "/api/auth/local/login",
            headers={"Origin": "https://evil.test"},
            json={"username": "admin", "password": "guess"},
        ).status_code
        == 403
    )


def test_auth_validation_does_not_echo_password(auth_client):
    client, _ = auth_client
    password = "super-secret-" * 50
    result = client.post("/api/auth/local/login", json={"username": "admin", "password": password})
    assert result.status_code == 422 and "super-secret" not in result.text


def test_password_rotation_revokes_other_sessions(auth_client):
    client, session = auth_client
    user = local_auth.bootstrap(session, "emergency", "old-strong-password")
    old_token = sign_in(client, session, user, "local")
    sign_in(client, session, user, "local")
    result = client.post(
        "/api/settings/ciam-sso/local-password",
        json={"current_password": "old-strong-password", "new_password": "new-strong-password"},
    )
    assert result.status_code == 200, result.text
    assert session.get(AuthSession, digest(old_token)) is None
    assert not local_auth.verify_password("old-strong-password", user.password_hash)
    assert local_auth.verify_password("new-strong-password", user.password_hash)


def test_disabled_local_user_and_wrong_password_have_same_error(auth_client):
    client, session = auth_client
    user = local_auth.bootstrap(session, "emergency", "strong-password-local")
    client.headers["Origin"] = ORIGIN
    wrong = client.post("/api/auth/local/login", json={"username": "emergency", "password": "bad"})
    user.active = False
    session.commit()
    disabled = client.post(
        "/api/auth/local/login", json={"username": "emergency", "password": "strong-password-local"}
    )
    assert wrong.status_code == disabled.status_code == 401
    assert wrong.json() == disabled.json()


def test_disabled_sso_callback_does_not_exchange_code(provider):
    client, session, query, _, calls = provider
    ciam.save_config(session, {"ciam_sso_enabled": False}, "test")
    result = client.post(
        "/api/auth/sso/callback", json={"code": "code", "state": query["state"][0]}
    )
    assert result.status_code == 503 and not calls


def test_expired_attempt_rejected_before_token_exchange(provider):
    from app.models import SsoAttempt

    client, session, query, _, calls = provider
    attempt = session.scalar(select(SsoAttempt))
    attempt.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    session.commit()
    result = client.post(
        "/api/auth/sso/callback", json={"code": "code", "state": query["state"][0]}
    )
    assert result.status_code == 401 and not calls


def test_sso_does_not_link_by_email_or_accept_inactive_identity(provider):
    client, session, query, _, _ = provider
    unrelated = account(session, "admin", issuer="https://other-provider.test")
    unrelated.email = "employee@example.test"
    session.commit()
    result = client.post(
        "/api/auth/sso/callback", json={"code": "code", "state": query["state"][0]}
    )
    assert result.status_code == 200
    assert result.json()["user"]["id"] != unrelated.id
    assert result.json()["user"]["role"] == "viewer"


def test_additive_auth_migration_matches_models():
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect

    from app.models import AuthRateLimit, SsoAttempt

    path = Path(__file__).parents[1] / "alembic/versions/8c9304b5c6d7_add_ciam_auth.py"
    spec = importlib.util.spec_from_file_location("ciam_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()
            inspector = inspect(connection)
            for model in [AuthUser, AuthSession, SsoAttempt, AuthRateLimit]:
                columns = {c["name"] for c in inspector.get_columns(model.__tablename__)}
                assert columns == set(model.__table__.columns.keys())
            migration.downgrade()
            assert inspect(connection).get_table_names() == []
    engine.dispose()


@pytest.mark.parametrize("bad_keys", ["wrong_key", "wrong_kid", "wrong_algorithm"])
def test_signature_and_key_confusion_rejected(provider, monkeypatch, bad_keys):
    client, session, query, _, _ = provider
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    public.update(
        {
            "kid": "other" if bad_keys == "wrong_kid" else "test-key",
            "alg": "HS256" if bad_keys == "wrong_algorithm" else "RS256",
        }
    )
    monkeypatch.setattr(ciam, "jwks", lambda _: {"keys": [public]})
    result = client.post(
        "/api/auth/sso/callback", json={"code": "code", "state": query["state"][0]}
    )
    assert result.status_code == 401
    assert session.scalar(select(AuthUser)) is None


@pytest.mark.parametrize("invalid", ["issuer", "endpoint", "pkce"])
def test_discovery_rejects_unsafe_metadata(auth_client, monkeypatch, invalid):
    from fastapi import HTTPException

    cfg = ciam.config(auth_client[1])
    base = cfg["ciam_base_url"]
    doc = {
        "issuer": base,
        "authorization_endpoint": base + "/authorize",
        "token_endpoint": base + "/token",
        "jwks_uri": base + "/keys",
        "code_challenge_methods_supported": ["S256"],
    }
    if invalid == "issuer":
        doc["issuer"] = "https://evil.test"
    if invalid == "endpoint":
        doc["token_endpoint"] = "https://evil.test/token"
    if invalid == "pkce":
        doc["code_challenge_methods_supported"] = ["plain"]

    class DiscoveryClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url):
            return httpx.Response(200, json=doc, request=httpx.Request("GET", url))

    monkeypatch.setattr(ciam.httpx, "Client", DiscoveryClient)
    with pytest.raises(HTTPException) as error:
        ciam.discovery(cfg)
    assert error.value.status_code == 502
