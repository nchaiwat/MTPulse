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
            binding_path = path.with_name("9da415c6d7e8_add_ad_binding.py")
            binding_spec = importlib.util.spec_from_file_location("ad_migration", binding_path)
            binding_migration = importlib.util.module_from_spec(binding_spec)
            binding_spec.loader.exec_module(binding_migration)
            binding_migration.upgrade()
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


def test_ad_emergency_requires_mode_and_binding(auth_client, monkeypatch):
    client, session = auth_client
    client.headers["Origin"] = ORIGIN
    monkeypatch.setattr(httpx.Client, "post", lambda *a, **k: pytest.fail("Gateway not expected"))
    assert (
        client.request(
            "POST", "/api/auth/ad/login", json={"username": "tester", "password": "test"}
        ).status_code
        == 503
    )
    ciam.save_config(
        session, {"ciam_break_glass_active": True, "ciam_ad_secret": "test-secret"}, "test"
    )
    assert (
        client.request(
            "POST", "/api/auth/ad/login", json={"username": "tester", "password": "test"}
        ).status_code
        == 401
    )


def test_ad_binding_reuses_role_outside_emergency_and_survives_mode_exit(auth_client, monkeypatch):
    client, session = auth_client
    admin = account(session)
    user = account(session, "operator")
    sign_in(client, session, admin)
    result = client.put(
        f"/api/settings/ciam-sso/users/{user.id}/ad-binding", json={"username": "  AD.Tester "}
    )
    assert result.status_code == 200
    assert result.json()["ad_username"] == "ad.tester"
    ciam.save_config(
        session, {"ciam_break_glass_active": False, "ciam_ad_secret": "test-secret"}, "test"
    )

    def gateway(_self, url, **kwargs):
        assert url == "http://192.168.12.11:3100/api/v2/login"
        payload = kwargs["json"]
        assert payload["app_id"] == "MTPULSE"
        assert payload["secret_key"] == "test-secret"
        assert payload["username"] == "ad.tester"
        assert payload["password"] == "ad-password"
        assert (
            abs((datetime.now(UTC) - datetime.fromisoformat(payload["timestamp"])).total_seconds())
            < 10
        )
        assert "headers" not in kwargs
        return httpx.Response(200, json={"status": "success", "data": {"username": "AD.Tester"}})

    monkeypatch.setattr(httpx.Client, "post", gateway)
    client.cookies.clear()
    response = client.request(
        "POST", "/api/auth/ad/login", json={"username": "AD.Tester", "password": "ad-password"}
    )
    assert response.status_code == 200
    assert response.json()["user"]["id"] == user.id
    assert response.json()["user"]["role"] == "operator"
    assert response.json()["provider"] == "ad"
    assert client.get("/api/auth/me").status_code == 200
    ciam.save_config(session, {"ciam_break_glass_active": False}, "test")
    assert client.get("/api/auth/me").status_code == 200
    logs = " ".join(x.after_json or "" for x in session.scalars(select(AuditEvent)))
    assert "ad-password" not in logs and "test-secret" not in logs


@pytest.mark.parametrize(
    "body,status",
    [
        ({"status": "error", "message": "password leak"}, 200),
        ({"status": "success", "data": {"username": "other"}}, 200),
        ({"status": "success"}, 200),
        ([], 200),
        ({"authenticated": True, "username": "tester"}, 200),
        ({"status": "success", "data": {"username": "tester"}}, 302),
        ({"message": "secret leak"}, 403),
        ({"message": "secret leak"}, 500),
        ({"message": "secret leak"}, 429),
    ],
)
def test_ad_rejects_untrusted_gateway_results(auth_client, monkeypatch, body, status):
    client, session = auth_client
    user = account(session, "viewer")
    user.ad_username = "tester"
    session.commit()
    ciam.save_config(
        session, {"ciam_break_glass_active": True, "ciam_ad_secret": "ad-secret"}, "test"
    )
    client.headers["Origin"] = ORIGIN
    monkeypatch.setattr(httpx.Client, "post", lambda *a, **k: httpx.Response(status, json=body))
    result = client.request(
        "POST", "/api/auth/ad/login", json={"username": "tester", "password": "password"}
    )
    assert result.status_code in (401, 429, 502)
    assert "leak" not in result.text
    assert session.scalar(select(AuthSession)) is None


def test_ad_bindings_unique_admin_only_and_never_local(auth_client):
    client, session = auth_client
    admin = account(session)
    user = account(session, "viewer")
    local = local_auth.bootstrap(session, "emergency", "test-long-password")
    sign_in(client, session, admin)
    path = "/api/settings/ciam-sso/users/"
    assert (
        client.put(path + user.id + "/ad-binding", json={"username": "Tester"}).status_code == 200
    )
    assert (
        client.put(path + admin.id + "/ad-binding", json={"username": "TESTER"}).status_code == 409
    )
    assert (
        client.put(path + local.id + "/ad-binding", json={"username": "local"}).status_code == 422
    )
    sign_in(client, session, user, "ad")
    ciam.save_config(session, {"ciam_break_glass_active": True}, "test")
    assert client.put(path + user.id + "/ad-binding", json={"username": ""}).status_code == 403
    sign_in(client, session, admin)
    assert client.put(path + user.id + "/ad-binding", json={"username": ""}).status_code == 200
    assert not session.scalars(select(AuthSession).where(AuthSession.provider == "ad")).all()


def test_ad_settings_encrypt_secret_and_keep_it_when_blank(auth_client):
    client, session = auth_client
    sign_in(client, session, account(session))
    cfg = client.get("/api/settings/ciam-sso").json()
    cfg["ciam_ad_secret"] = "private-ad-secret"
    saved = client.put("/api/settings/ciam-sso", json=cfg)
    assert saved.status_code == 200
    assert saved.json()["ad_secret_configured"] is True
    assert "private-ad-secret" not in saved.text
    assert "private-ad-secret" not in session.get(SystemSetting, "ciam_ad_secret").value
    cfg["ciam_ad_secret"] = ""
    assert client.put("/api/settings/ciam-sso", json=cfg).status_code == 200
    assert ciam.config(session, ad_secret=True)["ciam_ad_secret"] == "private-ad-secret"
    cfg["ciam_ad_gateway_url"] = "http://public.example.com/api/v2/login"
    assert client.put("/api/settings/ciam-sso", json=cfg).status_code == 422
    assert "private-ad-secret" not in client.get("/api/settings/ciam-sso").text


@pytest.mark.parametrize("change", ["disabled", "unbound", "mode", "secret"])
def test_ad_rechecks_identity_and_settings_after_gateway(auth_client, monkeypatch, change):
    client, session = auth_client
    user = account(session, "operator")
    user.ad_username = "tester"
    session.commit()
    ciam.save_config(session, {"ciam_break_glass_active": True, "ciam_ad_secret": "secret"}, "test")
    client.headers["Origin"] = ORIGIN

    def gateway(*args, **kwargs):
        if change == "disabled":
            user.active = False
            session.commit()
        elif change == "unbound":
            user.ad_username = None
            session.commit()
        elif change == "mode":
            ciam.save_config(session, {"ciam_break_glass_active": False}, "test")
        else:
            ciam.save_config(session, {"ciam_ad_secret": "rotated"}, "test")
        return httpx.Response(200, json={"status": "success", "data": {"username": "tester"}})

    monkeypatch.setattr(httpx.Client, "post", gateway)
    assert (
        client.request(
            "POST", "/api/auth/ad/login", json={"username": "tester", "password": "password"}
        ).status_code
        == 401
    )
    assert session.scalar(select(AuthSession)) is None


def test_ad_rejects_origin_and_ldap_filter_input(auth_client, monkeypatch):
    client, session = auth_client
    ciam.save_config(session, {"ciam_break_glass_active": True, "ciam_ad_secret": "secret"}, "test")
    monkeypatch.setattr(httpx.Client, "post", lambda *a, **k: pytest.fail("Gateway not expected"))
    payload = {"username": "*)(objectClass=*)", "password": "do-not-echo"}
    assert client.request("POST", "/api/auth/ad/login", json=payload).status_code == 403
    client.headers["Origin"] = ORIGIN
    response = client.request("POST", "/api/auth/ad/login", json=payload)
    assert response.status_code == 422
    assert "do-not-echo" not in response.text


def test_ad_timeout_is_redacted_and_rate_limited(auth_client, monkeypatch):
    client, session = auth_client
    user = account(session)
    user.ad_username = "tester"
    session.commit()
    ciam.save_config(session, {"ciam_break_glass_active": True, "ciam_ad_secret": "secret"}, "test")
    client.headers["Origin"] = ORIGIN

    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("secret-and-password")

    monkeypatch.setattr(httpx.Client, "post", timeout)
    for _ in range(10):
        response = client.request(
            "POST", "/api/auth/ad/login", json={"username": "tester", "password": "password"}
        )
        assert response.status_code == 502
        assert "secret-and-password" not in response.text
    assert (
        client.request(
            "POST", "/api/auth/ad/login", json={"username": "tester", "password": "password"}
        ).status_code
        == 429
    )


@pytest.mark.parametrize("kind,key", [("client", "ciam_client_secret"), ("ad", "ciam_ad_secret")])
def test_secret_reveal_requires_admin_csrf_and_redacts_audit(auth_client, kind, key):
    client, session = auth_client
    ciam.save_config(session, {key: "fixture-private-value"}, "test")
    path = f"/api/settings/ciam-sso/secrets/{kind}/reveal"
    assert client.post(path).status_code == 401
    sign_in(client, session, account(session, "operator"))
    assert client.post(path).status_code == 403
    sign_in(client, session, account(session))
    assert client.post(path, headers={"X-CSRF-Token": "bad"}).status_code == 403
    result = client.post(path)
    assert result.status_code == 200
    assert result.json() == {"value": "fixture-private-value"}
    assert result.headers["cache-control"] == "no-store"
    assert "fixture-private-value" not in client.get("/api/settings/ciam-sso").text
    events = list(session.scalars(select(AuditEvent).where(AuditEvent.action == "secret_revealed")))
    assert len(events) == 1
    assert "fixture-private-value" not in events[0].after_json
    assert key in events[0].after_json


def test_admin_creates_managed_account_and_controls_ad(auth_client):
    client, session = auth_client
    admin = account(session)
    sign_in(client, session, admin)
    payload = {
        "username": "Chaiwat.N",
        "full_name": "Chaiwat",
        "role": "operator",
        "active": True,
        "ad_enabled": True,
    }
    result = client.post("/api/settings/ciam-sso/users", json=payload)
    assert result.status_code == 201
    user = result.json()
    assert user["ad_username"] == "chaiwat.n" and user["role"] == "operator"
    assert (
        client.post(
            "/api/settings/ciam-sso/users", json={**payload, "username": "CHAIWAT.N"}
        ).status_code
        == 409
    )
    result = client.patch(
        "/api/settings/ciam-sso/users/" + user["id"],
        json={"role": "operator", "active": True, "ad_enabled": False},
    )
    assert result.status_code == 200 and result.json()["ad_username"] is None


def test_sso_links_managed_username_preserving_role(provider):
    client, session, query, overrides, _ = provider
    user = account(session, "operator", issuer="urn:mtpulse:managed")
    user.username = "Chaiwat.N"
    user.ad_username = "chaiwat.n"
    session.commit()
    overrides["preferred_username"] = "CHAIWAT.N"
    result = client.post(
        "/api/auth/sso/callback", json={"code": "code", "state": query["state"][0]}
    )
    assert result.status_code == 200
    assert result.json()["user"]["id"] == user.id
    assert result.json()["user"]["role"] == "operator"
    assert result.json()["user"]["ad_username"] == "chaiwat.n"


@pytest.mark.parametrize(
    "issuer,active",
    [
        ("urn:mtpulse:local", True),
        ("https://ciam.windowasia.com", True),
        ("urn:mtpulse:managed", False),
    ],
)
def test_sso_never_links_local_bound_or_disabled_account(provider, issuer, active):
    client, session, query, overrides, _ = provider
    user = account(session, "admin", issuer=issuer)
    user.username = "Chaiwat.N"
    user.active = active
    original_subject = user.subject
    session.commit()
    overrides["preferred_username"] = "chaiwat.n"
    result = client.post(
        "/api/auth/sso/callback", json={"code": "code", "state": query["state"][0]}
    )
    assert result.status_code == 403
    session.refresh(user)
    assert user.subject == original_subject and user.issuer == issuer
    assert user.active == active


def test_non_admin_cannot_create_users(auth_client):
    client, session = auth_client
    for role in ["viewer", "operator"]:
        sign_in(client, session, account(session, role))
        assert (
            client.post("/api/settings/ciam-sso/users", json={"username": "new-user"}).status_code
            == 403
        )


def test_ad_permission_disabled_revokes_existing_ad_session(auth_client):
    client, session = auth_client
    admin = account(session)
    user = account(session, "operator")
    user.ad_username = "tester"
    session.commit()
    token = sign_in(client, session, user, "ad")
    sign_in(client, session, admin)
    result = client.patch(
        "/api/settings/ciam-sso/users/" + user.id,
        json={"role": "operator", "active": True, "ad_enabled": False},
    )
    assert result.status_code == 200
    assert session.get(AuthSession, digest(token)) is None
    assert not session.get(AuthUser, user.id).ad_username


def test_transaction_log_records_failed_login_and_is_admin_only(auth_client):
    client, session = auth_client
    client.headers["Origin"] = ORIGIN
    result = client.post(
        "/api/auth/local/login", json={"username": "unknown", "password": "never-log-this"}
    )
    assert result.status_code == 401
    admin = account(session)
    sign_in(client, session, admin)
    result = client.get("/api/settings/transaction-logs", params={"status": "failed"})
    assert result.status_code == 200
    assert result.json()["total"] == 1
    row = result.json()["items"][0]
    assert row["status"] == "failed" and row["details"]["ip"]
    assert "never-log-this" not in result.text
    sign_in(client, session, account(session, "viewer"))
    assert client.get("/api/settings/transaction-logs").status_code == 403


def test_transaction_logs_sso_provision_and_success(provider):
    client, session, query, _, _ = provider
    state = query["state"][0]
    response = client.post("/api/auth/sso/callback", json={"code": "secret-code", "state": state})
    assert response.status_code == 200
    from app.models import TransactionLog

    logs = list(session.scalars(select(TransactionLog)))
    assert {"SSO-01", "SSO-03"} <= {x.event_code for x in logs}
    success = next(x for x in logs if x.event_code == "SSO-01")
    assert success.triggered_by.startswith("user:")
    assert "secret-code" not in success.details


def test_transaction_matrix_failed_signature_and_inactive(provider):
    from app.models import TransactionLog

    client, session, query, overrides, _ = provider
    overrides["nonce"] = "invalid"
    response = client.post(
        "/api/auth/sso/callback", json={"code": "do-not-log", "state": query["state"][0]}
    )
    assert response.status_code == 401
    log = session.scalar(select(TransactionLog).where(TransactionLog.event_code == "SSO-02"))
    assert log.status == "failed" and "token_validation" in log.details
    assert "do-not-log" not in log.details


def test_transaction_matrix_inactive_account(provider):
    from app.models import TransactionLog

    client, session, query, _, _ = provider
    user = account(session)
    user.subject = "employee-123"
    user.active = False
    session.commit()
    response = client.post(
        "/api/auth/sso/callback", json={"code": "code", "state": query["state"][0]}
    )
    assert response.status_code == 403
    log = session.scalar(select(TransactionLog).where(TransactionLog.event_code == "SSO-04"))
    assert log.status == "warning"
    assert log.triggered_by == "user:tester"


def test_transaction_matrix_config_breakglass_and_ad(auth_client, monkeypatch):
    import json

    from app.models import TransactionLog

    client, session = auth_client
    admin = account(session)
    sign_in(client, session, admin)
    ciam.save_config(session, {"ciam_ad_secret": "keep-secret-private"}, "user:" + admin.id)
    response = client.post(
        "/api/auth/sso/break-glass-toggle", json={"active": True, "reason": "Gateway maintenance"}
    )
    assert response.status_code == 200
    bg = session.scalar(select(TransactionLog).where(TransactionLog.event_code == "BG-01"))
    assert bg.status == "warning"
    assert json.loads(bg.details)["prev_state"] is False
    assert json.loads(bg.details)["ip"] == "testclient"
    user = account(session, "operator")
    user.ad_username = "ad.tester"
    session.commit()
    monkeypatch.setattr(
        httpx.Client,
        "post",
        lambda *a, **kw: httpx.Response(
            200, json={"status": "success", "data": {"username": "ad.tester"}}
        ),
    )
    response = client.request(
        "POST", "/api/auth/ad/login", json={"username": "ad.tester", "password": "private-password"}
    )
    assert response.status_code == 200
    log = session.scalar(select(TransactionLog).where(TransactionLog.event_code == "BG-02"))
    assert log.category == "security_break_glass"
    client.cookies.clear()
    sign_in(client, session, admin)
    response = client.get(
        "/api/settings/transaction-logs",
        params={"category": "system_setting", "page_size": 1, "triggered_by": "tester"},
    )
    assert response.status_code == 200 and response.json()["total"] >= 1
    assert len(response.json()["items"]) == 1
    assert response.headers["cache-control"] == "no-store"
    assert "keep-secret-private" not in response.text and "private-password" not in response.text
    cfg = session.scalar(select(TransactionLog).where(TransactionLog.event_code == "CFG-01"))
    assert "ciam_ad_secret" in json.loads(cfg.details)["changed_fields"]
    assert client.get("/api/settings/transaction-logs", params={"page": 0}).status_code == 422
    assert (
        client.get(
            "/api/settings/transaction-logs",
            params={"date_from": "2026-01-02T00:00:00Z", "date_to": "2026-01-01T00:00:00Z"},
        ).status_code
        == 422
    )
    legacy = client.get("/api/settings/transaction-logs", params={"legacy": True}).json()
    assert legacy["total"] > 0 and legacy["items"][0]["status"] is None
    assert legacy["items"][0]["details"] == {}


def test_ad_gateway_test_checks_unknown_user_without_changing_session(auth_client, monkeypatch):
    from app.models import TransactionLog

    client, session = auth_client
    admin = account(session)
    sign_in(client, session, admin)
    ciam.save_config(session, {"ciam_ad_secret": "fixture-ad-secret"}, "test")
    before = list(session.scalars(select(AuthSession.token_hash)))

    def gateway(_client, url, **kwargs):
        assert url == "http://192.168.12.11:3100/api/v2/login"
        assert kwargs["json"]["username"] == "new.employee"
        assert kwargs["json"]["secret_key"] == "fixture-ad-secret"
        return httpx.Response(200, json={"status": "success", "data": {"username": "New.Employee"}})

    monkeypatch.setattr(httpx.Client, "post", gateway)
    result = client.request(
        "POST",
        "/api/settings/ciam-sso/test-ad-login",
        json={"username": "New.Employee", "password": "private-test-password"},
    )
    assert result.status_code == 200
    assert result.json()["gateway_status"] == "success"
    assert result.json()["mtpulse_status"] == "account_missing"
    assert "set-cookie" not in result.headers
    assert list(session.scalars(select(AuthSession.token_hash))) == before
    assert len(list(session.scalars(select(AuthUser)))) == 1
    assert client.get("/api/auth/me").json()["user"]["id"] == admin.id
    log = session.scalar(select(TransactionLog).where(TransactionLog.event_code == "CFG-03"))
    assert log and log.status == "success" and log.triggered_by == "user:tester"
    assert "private-test-password" not in log.details and "fixture-ad-secret" not in log.details
    assert "new.employee" in log.details


@pytest.mark.parametrize("role", ["viewer", "operator"])
def test_ad_gateway_test_requires_admin(auth_client, monkeypatch, role):
    client, session = auth_client
    sign_in(client, session, account(session, role))
    called = []
    monkeypatch.setattr(httpx.Client, "post", lambda *a, **k: called.append(True))
    response = client.request(
        "POST",
        "/api/settings/ciam-sso/test-ad-login",
        json={"username": "ad.user", "password": "test-password"},
    )
    assert response.status_code == 403 and called == []


@pytest.mark.parametrize(
    "case,expected",
    [
        ("bad_password", "rejected"),
        ("wrong_username", "rejected"),
        ("timeout", "timeout"),
        ("server_error", "unavailable"),
        ("rate_limit", "rate_limited"),
        ("invalid_json", "unavailable"),
    ],
)
def test_ad_gateway_test_failure_redacted_and_session_preserved(
    auth_client, monkeypatch, case, expected
):
    from app.models import TransactionLog

    client, session = auth_client
    admin = account(session)
    sign_in(client, session, admin)
    ciam.save_config(session, {"ciam_ad_secret": "secret-not-in-audit"}, "test")

    def gateway(*args, **kwargs):
        if case == "timeout":
            raise httpx.ReadTimeout("private-password and secret-not-in-audit")
        if case == "invalid_json":
            return httpx.Response(200, text="private-password and secret-not-in-audit")
        return httpx.Response(
            500
            if case == "server_error"
            else 429
            if case == "rate_limit"
            else 401
            if case == "bad_password"
            else 200,
            json={
                "status": "success",
                "data": {"username": "someone.else"},
                "message": "private-password",
            },
        )

    monkeypatch.setattr(httpx.Client, "post", gateway)
    result = client.request(
        "POST",
        "/api/settings/ciam-sso/test-ad-login",
        json={"username": "ad.user", "password": "private-password"},
    )
    assert result.status_code == 200
    assert result.json()["gateway_status"] == expected
    assert result.json()["mtpulse_status"] == "not_checked"
    assert "private-password" not in result.text
    assert "set-cookie" not in result.headers
    assert client.get("/api/auth/me").json()["user"]["id"] == admin.id
    log = session.scalar(select(TransactionLog).where(TransactionLog.event_code == "CFG-03"))
    assert log.status == "failed" and expected in log.details
    assert "private-password" not in log.details and "secret-not-in-audit" not in log.details


@pytest.mark.parametrize(
    "active,binding,issuer,expected",
    [
        (True, "ad.user", ciam.MANAGED_ISSUER, "ready"),
        (False, "ad.user", ciam.MANAGED_ISSUER, "disabled"),
        (True, None, ciam.MANAGED_ISSUER, "ad_not_enabled"),
        (True, None, ciam.LOCAL_ISSUER, "local_account"),
    ],
)
def test_ad_gateway_test_reports_mtpulse_eligibility(
    auth_client, monkeypatch, active, binding, issuer, expected
):
    client, session = auth_client
    sign_in(client, session, account(session))
    ciam.save_config(session, {"ciam_ad_secret": "test-secret"}, "test")
    user = account(session, "operator", issuer)
    user.username, user.active, user.ad_username = "AD.User", active, binding
    session.commit()
    monkeypatch.setattr(
        httpx.Client,
        "post",
        lambda *a, **k: httpx.Response(
            200, json={"status": "success", "data": {"username": "ad.user"}}
        ),
    )
    response = client.request(
        "POST",
        "/api/settings/ciam-sso/test-ad-login",
        json={"username": "AD.User", "password": "password"},
    )
    assert response.status_code == 200
    assert response.json()["gateway_status"] == "success"
    assert response.json()["mtpulse_status"] == expected
    session.refresh(user)
    assert (user.active, user.ad_username, user.role) == (active, binding, "operator")


def test_ad_gateway_test_guards_and_rate_limit(auth_client, monkeypatch):
    # Keep all attempts in one 5-minute bucket, even when the suite crosses a boundary.
    fixed_now = datetime.now(UTC)

    class FixedClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now if tz else fixed_now.replace(tzinfo=None)

    monkeypatch.setattr(ciam, "datetime", FixedClock)
    client, session = auth_client
    sign_in(client, session, account(session))
    calls = []

    def gateway(*a, **k):
        calls.append(k)
        return httpx.Response(200, json={"status": "success", "data": {"username": "ad.user"}})

    monkeypatch.setattr(httpx.Client, "post", gateway)
    payload = {"username": "ad.user", "password": "password"}
    endpoint = "/api/settings/ciam-sso/test-ad-login"
    missing = client.request("POST", endpoint, json=payload)
    assert missing.json()["gateway_status"] == "not_configured"
    ciam.save_config(session, {"ciam_ad_secret": "test-secret"}, "test")
    assert (
        client.request("POST", endpoint, json=payload, headers={"X-CSRF-Token": ""}).status_code
        == 403
    )
    assert (
        client.request(
            "POST", endpoint, json=payload, headers={"Origin": "https://untrusted.test"}
        ).status_code
        == 403
    )
    invalid = client.request("POST", endpoint, json={"username": "*()", "password": "password"})
    assert invalid.json()["gateway_status"] == "invalid_username"
    assert calls == []
    for _ in range(9):
        assert client.request("POST", endpoint, json=payload).json()["gateway_status"] == "success"
    assert client.request("POST", endpoint, json=payload).json()["gateway_status"] == "rate_limited"
    assert len(calls) == 9


def test_ad_gateway_test_rejects_changed_saved_config(auth_client, monkeypatch):
    client, session = auth_client
    sign_in(client, session, account(session))
    ciam.save_config(session, {"ciam_ad_secret": "test-secret"}, "test")

    def gateway(*a, **k):
        ciam.save_config(session, {"ciam_ad_app_id": "CHANGED"}, "test")
        return httpx.Response(200, json={"status": "success", "data": {"username": "ad.user"}})

    monkeypatch.setattr(httpx.Client, "post", gateway)
    result = client.request(
        "POST",
        "/api/settings/ciam-sso/test-ad-login",
        json={"username": "ad.user", "password": "password"},
    )
    assert result.json()["gateway_status"] == "settings_changed"
    assert result.json()["mtpulse_status"] == "not_checked"
