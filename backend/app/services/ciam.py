"""Mode B OIDC integration. Provider credentials never leave the backend."""

import base64
import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

import httpx
import jwt
from cryptography.fernet import Fernet
from fastapi import HTTPException, Request, Response
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth import SESSION_COOKIE, digest
from app.config import get_settings
from app.models import AuditEvent, AuthRateLimit, AuthSession, AuthUser, SsoAttempt, SystemSetting
from app.services.telegram import set_setting

BINDING_COOKIE = "__Host-mtpulse_sso"
LOCAL_ISSUER = "urn:mtpulse:local"
MANAGED_ISSUER = "urn:mtpulse:managed"
DEFAULTS = {
    "ciam_base_url": "https://ciam.windowasia.com",
    "ciam_client_id": "",
    "ciam_ad_gateway_url": "http://192.168.12.11:3100/api/v2/login",
    "ciam_ad_app_id": "MTPULSE",
    "ciam_redirect_uri": "https://wa-mtpulse.wa.net/auth/callback",
    "ciam_sso_enabled": False,
    "ciam_break_glass_active": False,
    "ciam_auto_provision_group": "viewer",
    "ciam_session_ttl_minutes": 480,
}


def crypto() -> Fernet:
    key = get_settings().settings_encryption_key
    if not key:
        raise HTTPException(503, "ยังไม่ได้ตั้ง Encryption Key บน Server")
    try:
        return Fernet(key.encode())
    except ValueError as exc:
        raise HTTPException(503, "Encryption Key บน Server ไม่ถูกต้อง") from exc


def config(session: Session, *, secret=False, ad_secret=False) -> dict:
    # DB per request: settings changes are immediate across API processes.
    rows = {
        r.key: r.value
        for r in session.scalars(
            select(SystemSetting).where(
                SystemSetting.key.in_([*DEFAULTS, "ciam_client_secret", "ciam_ad_secret"])
            )
        )
    }
    result = {
        k: json.loads(rows[k]) if k in rows and rows[k] is not None else v
        for k, v in DEFAULTS.items()
    }
    result["client_secret_configured"] = bool(rows.get("ciam_client_secret"))
    result["ad_secret_configured"] = bool(rows.get("ciam_ad_secret"))
    if ad_secret:
        try:
            result["ciam_ad_secret"] = (
                crypto().decrypt(rows["ciam_ad_secret"].encode()).decode()
                if rows.get("ciam_ad_secret")
                else ""
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(503, "ไม่สามารถอ่าน AD Gateway Secret ได้") from exc
    if secret:
        try:
            result["ciam_client_secret"] = (
                crypto().decrypt(rows["ciam_client_secret"].encode()).decode()
                if rows.get("ciam_client_secret")
                else ""
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(503, "ไม่สามารถอ่าน CIAM Secret ได้") from exc
    return result


def audit(session: Session, action: str, actor: str, details: dict | None = None):
    event = AuditEvent(
        entity_type="ciam_security",
        entity_id="ciam",
        action=action,
        actor=actor,
        after_json=json.dumps(details or {}, ensure_ascii=False),
    )
    # SQLite tests lack PostgreSQL bigint identity generation.
    if session.bind.dialect.name == "sqlite":
        event.id = (session.scalar(select(func.max(AuditEvent.id))) or 0) + 1
    session.add(event)
    from app.services.transaction_logs import record

    record(session, action, actor, details or {})
    session.flush()


def validate_url(value: str) -> str:
    parts = urlsplit(value)
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
        or parts.port not in (None, 443)
    ):
        raise ValueError("ต้องเป็น HTTPS URL ไม่มี credentials, query หรือ fragment")
    return value.rstrip("/")


def origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def same_origin(request: Request, cfg: dict):
    if request.headers.get("origin") != origin(cfg["ciam_redirect_uri"]):
        raise HTTPException(403, "Origin ไม่ตรงกับ URL ของระบบ")


def fingerprint(cfg: dict) -> str:
    return digest(json.dumps(cfg, sort_keys=True))


def discovery(cfg: dict) -> dict:
    try:
        base = validate_url(cfg["ciam_base_url"])
        with httpx.Client(timeout=10, follow_redirects=False) as client:
            response = client.get(base + "/.well-known/openid-configuration")
            response.raise_for_status()
            doc = response.json()
        if doc["issuer"] != base or "S256" not in doc.get("code_challenge_methods_supported", []):
            raise ValueError("Invalid issuer or PKCE support")
        for name in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
            endpoint = validate_url(doc[name])
            if origin(endpoint) != origin(base):
                raise ValueError("Cross-origin provider endpoint")
        return doc
    except (ValueError, KeyError, TypeError, httpx.HTTPError) as exc:
        raise HTTPException(502, "ตรวจสอบ CIAM discovery ไม่สำเร็จ") from exc


def jwks(doc: dict) -> dict:
    try:
        with httpx.Client(timeout=10, follow_redirects=False) as client:
            response = client.get(doc["jwks_uri"])
            response.raise_for_status()
            keys = response.json()
        if not keys.get("keys"):
            raise ValueError("No keys")
        return keys
    except (ValueError, TypeError, httpx.HTTPError) as exc:
        raise HTTPException(502, "อ่าน CIAM signing keys ไม่สำเร็จ") from exc


def throttle(session: Session, key: str, limit: int):
    now = datetime.now(UTC)
    bucket = int(now.timestamp()) // 300
    identifier = digest(f"{key}:{bucket}")
    if session.bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    stmt = insert(AuthRateLimit).values(
        key=identifier, attempts=1, expires_at=now + timedelta(minutes=10)
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[AuthRateLimit.key], set_={"attempts": AuthRateLimit.attempts + 1}
    )
    count = session.scalar(stmt.returning(AuthRateLimit.attempts))
    session.execute(
        delete(AuthRateLimit)
        .where(AuthRateLimit.expires_at < now)
        .execution_options(synchronize_session="fetch")
    )
    session.commit()
    if count > limit:
        raise HTTPException(429, "ลองเข้าสู่ระบบบ่อยเกินไป กรุณารอ 5 นาที")


def sso_active(cfg: dict):
    if not cfg["ciam_sso_enabled"] or cfg["ciam_break_glass_active"]:
        raise HTTPException(503, "SSO ปิดใช้งานชั่วคราว")
    if not cfg["ciam_client_id"] or not cfg["ciam_client_secret"]:
        raise HTTPException(503, "ยังตั้งค่า CIAM ไม่ครบ")


def authorize(session: Session, request: Request, response: Response) -> dict:
    cfg = config(session, secret=True)
    same_origin(request, cfg)
    sso_active(cfg)
    throttle(session, "sso:" + (request.client.host if request.client else "unknown"), 60)
    doc = discovery(cfg)
    state, binding, nonce, verifier = (secrets.token_urlsafe(48) for _ in range(4))
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    )
    session.execute(
        delete(SsoAttempt)
        .where(SsoAttempt.expires_at < datetime.now(UTC))
        .execution_options(synchronize_session="fetch")
    )
    session.add(
        SsoAttempt(
            state_hash=digest(state),
            binding_hash=digest(binding),
            verifier=crypto().encrypt(verifier.encode()).decode(),
            nonce=nonce,
            config_digest=fingerprint(cfg),
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
    )
    session.commit()
    response.set_cookie(
        BINDING_COOKIE, binding, max_age=300, secure=True, httponly=True, samesite="lax", path="/"
    )
    query = urlencode(
        {
            "response_type": "code",
            "client_id": cfg["ciam_client_id"],
            "redirect_uri": cfg["ciam_redirect_uri"],
            "scope": "openid profile email",
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "max_age": "0",
            "prompt": "login",
        }
    )
    return {"authorize_url": doc["authorization_endpoint"] + "?" + query}


def issue_session(
    session: Session,
    response: Response,
    user: AuthUser,
    provider: str,
    ttl: int,
    old_token: str = "",
) -> dict:
    token = secrets.token_urlsafe(48)
    now = datetime.now(UTC)
    if old_token:
        session.execute(delete(AuthSession).where(AuthSession.token_hash == digest(old_token)))
    session.execute(
        delete(AuthSession)
        .where(AuthSession.expires_at < now)
        .execution_options(synchronize_session="fetch")
    )
    session.add(
        AuthSession(
            token_hash=digest(token),
            user_id=user.id,
            provider=provider,
            created_at=now,
            expires_at=now + timedelta(minutes=ttl),
        )
    )
    user.last_login_at = now
    cfg = config(session)
    audit(
        session,
        "login_success",
        "user:" + user.id,
        {
            "provider": provider,
            "break_glass_active": cfg["ciam_break_glass_active"],
            **({"gateway": cfg["ciam_ad_gateway_url"]} if provider == "ad" else {}),
        },
    )
    session.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=ttl * 60,
        secure=True,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return {
        "user": user_info(user),
        "csrf_token": digest("csrf:" + token),
        "provider": provider,
        "expires_at": (now + timedelta(minutes=ttl)).isoformat(),
    }


def user_info(user: AuthUser) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "active": user.active,
        "local": user.issuer == LOCAL_ISSUER,
        "ad_username": user.ad_username,
        "ad_enabled": bool(user.ad_username),
        "ciam_linked": user.issuer not in (LOCAL_ISSUER, MANAGED_ISSUER),
    }


def callback(session: Session, request: Request, response: Response, code: str, state: str):
    cfg = config(session, secret=True)
    same_origin(request, cfg)
    stage = "state_validation"
    try:
        sso_active(cfg)
        now = datetime.now(UTC)
        # DELETE RETURNING consumes atomically across all API processes.
        attempt = session.execute(
            delete(SsoAttempt)
            .where(
                SsoAttempt.state_hash == digest(state),
                SsoAttempt.binding_hash == digest(request.cookies.get(BINDING_COOKIE, "")),
                SsoAttempt.expires_at > now,
                SsoAttempt.config_digest == fingerprint(cfg),
            )
            .returning(SsoAttempt.verifier, SsoAttempt.nonce)
        ).first()
        session.commit()
        if not attempt:
            raise HTTPException(401, "SSO session ไม่ถูกต้องหรือหมดอายุ กรุณาเริ่มใหม่")
        stage = "token_exchange"
        doc = discovery(cfg)
        verifier = crypto().decrypt(attempt.verifier.encode()).decode()
        with httpx.Client(timeout=10, follow_redirects=False) as client:
            result = client.post(
                doc["token_endpoint"],
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": cfg["ciam_client_id"],
                    "client_secret": cfg["ciam_client_secret"],
                    "redirect_uri": cfg["ciam_redirect_uri"],
                    "code_verifier": verifier,
                },
            )
            result.raise_for_status()
            token = result.json()["id_token"]
        stage = "token_validation"
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256" or not header.get("kid"):
            raise ValueError("Invalid signing algorithm")
        keys = [
            k
            for k in jwks(doc)["keys"]
            if k.get("kid") == header["kid"]
            and k.get("kty") == "RSA"
            and k.get("use", "sig") == "sig"
            and k.get("alg", "RS256") == "RS256"
        ]
        if len(keys) != 1:
            raise ValueError("Ambiguous signing key")
        claims = jwt.decode(
            token,
            jwt.PyJWK.from_dict(keys[0]).key,
            algorithms=["RS256"],
            audience=cfg["ciam_client_id"],
            issuer=cfg["ciam_base_url"],
            options={"require": ["iss", "sub", "aud", "exp", "iat", "nonce"]},
        )
        if not secrets.compare_digest(str(claims["nonce"]), attempt.nonce):
            raise ValueError("Invalid nonce")
        if (
            isinstance(claims["aud"], list)
            and len(claims["aud"]) > 1
            and claims.get("azp") != cfg["ciam_client_id"]
        ):
            raise ValueError("Invalid authorized party")
        if "azp" in claims and claims["azp"] != cfg["ciam_client_id"]:
            raise ValueError("Invalid authorized party")
        subject = claims["sub"]
        if not isinstance(subject, str) or not subject or len(subject) > 255:
            raise ValueError("Invalid subject")
        stage = "account_resolution"
        # Lock by issuer/subject during provisioning on PostgreSQL.
        if session.bind.dialect.name == "postgresql":
            from sqlalchemy import text

            lock = int(digest(cfg["ciam_base_url"] + subject)[:15], 16)
            session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock})
        lock_user_registry(session)
        user = session.scalar(
            select(AuthUser).where(
                AuthUser.issuer == cfg["ciam_base_url"], AuthUser.subject == subject
            )
        )
        if user is None:
            preferred = claims.get("preferred_username")
            if isinstance(preferred, str) and preferred.strip():
                matches = list(
                    session.scalars(
                        select(AuthUser)
                        .where(
                            func.lower(func.trim(AuthUser.username)) == preferred.strip().lower()
                        )
                        .with_for_update()
                    )
                )
                if matches:
                    if len(matches) != 1 or matches[0].issuer != MANAGED_ISSUER:
                        raise HTTPException(403, "ชื่อบัญชีนี้เชื่อมตัวตนอื่นแล้ว กรุณาติดต่อ Admin")
                    user = matches[0]
                    if not user.active:
                        session.info["inactive_username"] = user.username
                        raise HTTPException(403, "บัญชีถูกระงับ กรุณาติดต่อผู้ดูแลระบบ")
                    user.issuer, user.subject = cfg["ciam_base_url"], subject
                    audit(session, "ciam_account_linked", "user:" + user.id)
        if user is None:
            user = AuthUser(
                id=str(uuid4()),
                issuer=cfg["ciam_base_url"],
                subject=subject,
                username=str(claims.get("preferred_username") or subject)[:200],
                full_name=str(claims.get("name") or subject)[:300],
                email=str(claims.get("email") or "")[:300] or None,
                role="viewer",
                active=True,
                created_at=now,
            )
            session.add(user)
            session.flush()
            audit(session, "auto_provision", "user:" + user.id, {"role": "viewer"})
        if not user.active:
            session.info["inactive_username"] = user.username
            raise HTTPException(403, "บัญชีถูกระงับ กรุณาติดต่อผู้ดูแลระบบ")
        # Settings may have changed while waiting for the provider.
        session.expire_all()
        if fingerprint(config(session, secret=True)) != fingerprint(cfg):
            raise HTTPException(401, "การตั้งค่าเปลี่ยน กรุณาเริ่มเข้าสู่ระบบใหม่")
        response.delete_cookie(BINDING_COOKIE, secure=True, httponly=True, samesite="lax")
        return issue_session(
            session,
            response,
            user,
            "sso",
            cfg["ciam_session_ttl_minutes"],
            request.cookies.get(SESSION_COOKIE, ""),
        )
    except (HTTPException, httpx.HTTPError, ValueError, KeyError, TypeError, jwt.PyJWTError) as exc:
        session.rollback()
        inactive = session.info.pop("inactive_username", None)
        if inactive:
            audit(
                session,
                "account_deactivated",
                "user:" + user.id,
                {"username": inactive, "provider": "sso"},
            )
        audit(
            session,
            "login_failed",
            "anonymous",
            {
                "provider": "sso",
                "error": type(exc).__name__,
                "stage": stage,
                "http_status": exc.status_code if isinstance(exc, HTTPException) else 401,
            },
        )
        session.commit()
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(401, "ยืนยันตัวตนกับ CIAM ไม่สำเร็จ กรุณาเริ่มใหม่") from exc


def lock_ad_settings(session: Session):
    # Serialize configuration changes with AD session issuance across API processes.
    if session.bind.dialect.name == "postgresql":
        from sqlalchemy import text

        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": 782614032})


def save_config(session: Session, values: dict, actor: str):
    lock_ad_settings(session)
    before = config(session)
    for key, value in values.items():
        if key in ("ciam_client_secret", "ciam_ad_secret"):
            if value:
                set_setting(
                    session,
                    key,
                    crypto().encrypt(value.encode()).decode(),
                    secret=True,
                    actor=actor,
                )
        else:
            set_setting(session, key, json.dumps(value), secret=False, actor=actor)
    session.flush()
    session.execute(delete(SsoAttempt))
    after = config(session)
    if any(before[key] != after[key] for key in ("ciam_ad_gateway_url", "ciam_ad_app_id")) or bool(
        values.get("ciam_ad_secret")
    ):
        session.execute(delete(AuthSession).where(AuthSession.provider == "ad"))
    audit(
        session,
        "settings_changed",
        actor,
        {
            "before": before,
            "after": after,
            "secret_changed": bool(values.get("ciam_client_secret")),
            "ad_secret_changed": bool(values.get("ciam_ad_secret")),
        },
    )
    session.commit()
    return after


def lock_user_registry(session: Session):
    # Shared by manual creation and CIAM linking/provisioning, across API workers.
    if session.bind.dialect.name == "postgresql":
        from sqlalchemy import text

        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": 782614033})
