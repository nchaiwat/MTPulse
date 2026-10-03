import json
from datetime import UTC, datetime
from time import perf_counter
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import SESSION_COOKIE, digest, require_system_admin, utc
from app.config import get_settings
from app.database import get_session
from app.models import AuditEvent, AuthSession, AuthUser, TransactionLog
from app.services import ad_auth, ciam, local_auth
from app.services.audit_request import request_details

Db = Annotated[Session, Depends(get_session)]
Admin = Annotated[str, Depends(require_system_admin)]


def audit_context(request: Request, session: Db):
    provider = {
        "/api/auth/sso/callback": "sso",
        "/api/auth/local/login": "local",
        "/api/auth/ad/login": "ad",
    }.get(request.url.path)
    session.info["audit_context"] = {
        **request_details(request),
        "started": perf_counter(),
        "provider": provider,
    }
    session.info["login_failure_logged"] = False
    session.info.pop("inactive_username", None)
    try:
        yield
    except HTTPException as exc:
        if provider and not session.info.get("login_failure_logged"):
            session.rollback()
            ciam.audit(
                session,
                "login_failed",
                "anonymous",
                {
                    "provider": provider,
                    "error": "RequestRejected",
                    "http_status": exc.status_code,
                },
            )
            session.commit()
        raise
    finally:
        session.info.pop("audit_context", None)


router = APIRouter(tags=["Authentication"], dependencies=[Depends(audit_context)])


class CiamSettings(BaseModel):
    ciam_ad_gateway_url: str = Field(
        default="http://192.168.12.11:3100/api/v2/login", max_length=500
    )
    ciam_ad_app_id: str = Field(default="MTPULSE", min_length=1, max_length=200)
    ciam_ad_secret: str | None = Field(default=None, max_length=2000, repr=False)
    ciam_base_url: str = Field(max_length=300)
    ciam_client_id: str = Field(max_length=200)
    ciam_client_secret: str | None = Field(default=None, max_length=2000, repr=False)
    ciam_redirect_uri: str = Field(max_length=500)
    ciam_sso_enabled: bool
    ciam_auto_provision_group: Literal["viewer"] = "viewer"
    ciam_session_ttl_minutes: int = Field(default=480, ge=5, le=1440)

    @field_validator("ciam_ad_gateway_url")
    @classmethod
    def gateway_url(cls, value):
        return ad_auth.validate_gateway_url(value)

    @field_validator("ciam_base_url", "ciam_redirect_uri")
    @classmethod
    def https_only(cls, value):
        return ciam.validate_url(value)


class Callback(BaseModel):
    code: str = Field(min_length=1, max_length=4000)
    state: str = Field(min_length=16, max_length=200)


class BreakGlass(BaseModel):
    active: bool
    reason: str = Field(min_length=5, max_length=300)


class UserUpdate(BaseModel):
    ad_enabled: bool | None = None
    role: Literal["viewer", "operator", "admin"]
    active: bool


@router.get("/api/auth/sso/config")
def public_config(session: Db, response: Response):
    response.headers["Cache-Control"] = "no-store"
    if get_settings().auth_mode == "development":
        return {"mode": "development", "sso_enabled": False, "break_glass_active": False}
    cfg = ciam.config(session)
    return {
        "mode": "ciam",
        "sso_enabled": cfg["ciam_sso_enabled"],
        "break_glass_active": cfg["ciam_break_glass_active"],
        "ad_login_enabled": bool(cfg["ad_secret_configured"] and cfg["ciam_ad_app_id"].strip()),
        "portal_url": cfg["ciam_base_url"] + "/portal",
    }


@router.post("/api/auth/sso/authorize-url")
def authorize(request: Request, response: Response, session: Db):
    response.headers["Cache-Control"] = "no-store"
    return ciam.authorize(session, request, response)


@router.post("/api/auth/sso/callback")
def callback(payload: Callback, request: Request, response: Response, session: Db):
    response.headers["Cache-Control"] = "no-store"
    return ciam.callback(session, request, response, payload.code, payload.state)


@router.get("/api/auth/me")
def me(request: Request, response: Response, session: Db):
    response.headers["Cache-Control"] = "no-store"
    if get_settings().auth_mode == "development":
        return {
            "user": {
                "id": "development",
                "username": "development-admin",
                "full_name": "Development Admin",
                "role": "admin",
                "active": True,
            },
            "provider": "development",
            "csrf_token": "",
            "expires_at": None,
        }
    user = request.state.auth_user
    return {
        "user": ciam.user_info(user),
        "provider": request.state.auth_session.provider,
        "csrf_token": digest("csrf:" + request.cookies[SESSION_COOKIE]),
        "expires_at": utc(request.state.auth_session.expires_at).isoformat(),
        "portal_url": ciam.config(session)["ciam_base_url"] + "/portal",
    }


@router.post("/api/auth/logout")
def logout(request: Request, response: Response, session: Db):
    token = request.cookies.get(SESSION_COOKIE, "")
    login = session.get(AuthSession, digest(token)) if token else None
    target = "/login"
    if login:
        if login.provider == "sso":
            target = ciam.config(session)["ciam_base_url"] + "/portal"
        ciam.audit(session, "logout", "user:" + login.user_id)
        session.delete(login)
        session.commit()
    response.delete_cookie(SESSION_COOKIE, secure=True, httponly=True, samesite="lax")
    return {"redirect_url": target}


@router.get("/api/settings/ciam-sso")
def get_config(session: Db, actor: Admin):
    return ciam.config(session)


@router.put("/api/settings/ciam-sso")
def put_config(payload: CiamSettings, session: Db, actor: Admin):
    if payload.ciam_sso_enabled:
        local_admin = session.scalar(
            select(AuthUser).where(
                AuthUser.issuer == ciam.LOCAL_ISSUER,
                AuthUser.active.is_(True),
                AuthUser.role == "admin",
                AuthUser.password_hash.is_not(None),
            )
        )
        if not local_admin:
            raise HTTPException(422, "ต้องสร้าง Local Admin ฉุกเฉินบน Server ก่อนเปิด SSO")
        old = ciam.config(session)
        if not payload.ciam_client_id.strip() or not (
            payload.ciam_client_secret or old["client_secret_configured"]
        ):
            raise HTTPException(422, "ต้องกำหนด Client ID และ Secret ก่อนเปิด SSO")
    return ciam.save_config(session, payload.model_dump(), actor)


@router.post("/api/settings/ciam-sso/test-connection")
def test_connection(session: Db, actor: Admin):
    cfg = ciam.config(session)
    try:
        doc = ciam.discovery(cfg)
        keys = ciam.jwks(doc)
        ciam.audit(session, "connection_test", actor, {"status": "success"})
        session.commit()
        return {
            "ok": True,
            "issuer": doc["issuer"],
            "signing_keys": len(keys["keys"]),
            "message": "Discovery/JWKS สำเร็จ ยังไม่ได้ทดสอบ Client Secret หรือ Login จริง",
        }
    except HTTPException:
        ciam.audit(session, "connection_test", actor, {"status": "failed"})
        session.commit()
        raise


@router.post("/api/auth/sso/break-glass-toggle")
def break_glass(payload: BreakGlass, session: Db, actor: Admin):
    previous = ciam.config(session)["ciam_break_glass_active"]
    result = ciam.save_config(session, {"ciam_break_glass_active": payload.active}, actor)
    ciam.audit(
        session,
        "break_glass_toggle",
        actor,
        {"active": payload.active, "reason": payload.reason, "prev_state": previous},
    )
    session.commit()
    return result


@router.get("/api/settings/ciam-sso/users")
def users(session: Db, actor: Admin):
    return [
        ciam.user_info(u) for u in session.scalars(select(AuthUser).order_by(AuthUser.username))
    ]


@router.patch("/api/settings/ciam-sso/users/{user_id}")
def update_user(user_id: str, payload: UserUpdate, session: Db, actor: Admin):
    # Serialize administrator changes to preserve the last active admin.
    all_users = list(session.scalars(select(AuthUser).order_by(AuthUser.id).with_for_update()))
    user = next((u for u in all_users if u.id == user_id), None)
    if not user:
        raise HTTPException(404, "ไม่พบผู้ใช้")
    if user.issuer == ciam.LOCAL_ISSUER:
        raise HTTPException(422, "บัญชีฉุกเฉินต้องคงสิทธิ์ Admin; จัดการผ่านเครื่องมือบน Server")
    if actor == "user:" + user.id and (not payload.active or payload.role != "admin"):
        raise HTTPException(422, "ไม่สามารถลดสิทธิ์หรือปิดบัญชีตนเอง")
    if user.role == "admin" and (not payload.active or payload.role != "admin"):
        if not any(u.id != user.id and u.active and u.role == "admin" for u in all_users):
            raise HTTPException(422, "ต้องเหลือ System Admin ที่ใช้งานได้อย่างน้อยหนึ่งบัญชี")
    ad_enabled = bool(user.ad_username) if payload.ad_enabled is None else payload.ad_enabled
    if (
        user.role == payload.role
        and user.active == payload.active
        and ad_enabled == bool(user.ad_username)
    ):
        return ciam.user_info(user)
    before = ciam.user_info(user)
    if ad_enabled and not user.ad_username:
        try:
            user.ad_username = ad_auth.normalize_username(user.username)
            session.flush()
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(409, "AD username นี้ถูกใช้งานแล้ว") from exc
    elif not ad_enabled:
        user.ad_username = None
    user.role, user.active = payload.role, payload.active
    session.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    ciam.audit(session, "user_updated", actor, {"before": before, "after": ciam.user_info(user)})
    session.commit()
    return ciam.user_info(user)


class LocalLogin(BaseModel):
    username: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=256, repr=False)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=256, repr=False)
    new_password: str = Field(min_length=12, max_length=256, repr=False)


@router.post("/api/auth/local/login")
def local_login(payload: LocalLogin, request: Request, response: Response, session: Db):
    response.headers["Cache-Control"] = "no-store"
    return local_auth.login(session, request, response, payload.username, payload.password)


@router.post("/api/settings/ciam-sso/local-password")
def change_password(
    payload: PasswordChange, request: Request, response: Response, session: Db, actor: Admin
):
    user = getattr(request.state, "auth_user", None)
    if not user or user.issuer != ciam.LOCAL_ISSUER:
        raise HTTPException(403, "ใช้ได้เฉพาะบัญชี Local ของตนเอง")
    ciam.throttle(session, "local-password:" + user.id, 10)
    if not local_auth.verify_password(payload.current_password, user.password_hash):
        ciam.audit(session, "password_change_failed", actor)
        session.commit()
        raise HTTPException(403, "รหัสผ่านปัจจุบันไม่ถูกต้อง")
    user.password_hash = local_auth.hash_password(payload.new_password)
    session.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    ciam.audit(session, "password_changed", actor)
    return ciam.issue_session(
        session, response, user, "local", ciam.config(session)["ciam_session_ttl_minutes"]
    )


class AdBinding(BaseModel):
    username: str | None = Field(default=None, max_length=200)

    @field_validator("username")
    @classmethod
    def username_value(cls, value):
        return ad_auth.normalize_username(value) if value and value.strip() else None


@router.put("/api/settings/ciam-sso/users/{user_id}/ad-binding")
def bind_ad(user_id: str, payload: AdBinding, session: Db, actor: Admin):
    user = session.scalar(select(AuthUser).where(AuthUser.id == user_id).with_for_update())
    if not user:
        raise HTTPException(404, "ไม่พบผู้ใช้")
    if user.issuer == ciam.LOCAL_ISSUER:
        raise HTTPException(422, "บัญชี Local Admin ต้องแยกจาก AD")
    before = user.ad_username
    if before == payload.username:
        return ciam.user_info(user)
    user.ad_username = payload.username
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, "AD username นี้ผูกกับบัญชีอื่นแล้ว") from exc
    session.execute(
        delete(AuthSession).where(AuthSession.user_id == user.id, AuthSession.provider == "ad")
    )
    ciam.audit(
        session,
        "ad_binding_changed",
        actor,
        {"user_id": user.id, "before": before, "after": payload.username},
    )
    session.commit()
    return ciam.user_info(user)


@router.post("/api/auth/ad/login")
def ad_login(payload: LocalLogin, request: Request, response: Response, session: Db):
    response.headers["Cache-Control"] = "no-store"
    return ad_auth.login(session, request, response, payload.username, payload.password)


@router.post("/api/settings/ciam-sso/secrets/{kind}/reveal")
def reveal_secret(kind: Literal["client", "ad"], response: Response, session: Db, actor: Admin):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    key = "ciam_client_secret" if kind == "client" else "ciam_ad_secret"
    cfg = ciam.config(session, secret=kind == "client", ad_secret=kind == "ad")
    ciam.audit(session, "secret_revealed", actor, {"key": key})
    session.commit()
    return {"value": cfg[key]}


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=200)
    full_name: str = Field(default="", max_length=300)
    role: Literal["viewer", "operator", "admin"] = "viewer"
    active: bool = True
    ad_enabled: bool = False

    @field_validator("username")
    @classmethod
    def valid_username(cls, value):
        ad_auth.normalize_username(value)
        return value.strip()


@router.post("/api/settings/ciam-sso/users", status_code=201)
def create_user(payload: UserCreate, session: Db, actor: Admin):
    ciam.lock_user_registry(session)
    normalized = payload.username.lower()
    duplicate = session.scalar(
        select(AuthUser).where(
            (func.lower(func.trim(AuthUser.username)) == normalized)
            | (AuthUser.ad_username == normalized)
        )
    )
    if duplicate:
        raise HTTPException(409, "ชื่อบัญชีนี้มีอยู่แล้ว")
    user = AuthUser(
        id=str(uuid4()),
        issuer=ciam.MANAGED_ISSUER,
        subject=str(uuid4()),
        username=payload.username,
        full_name=payload.full_name.strip() or payload.username,
        role=payload.role,
        active=payload.active,
        ad_username=normalized if payload.ad_enabled else None,
        created_at=datetime.now(UTC),
    )
    session.add(user)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, "ชื่อบัญชีนี้ถูกใช้งานแล้ว") from exc
    ciam.audit(session, "user_created", actor, ciam.user_info(user))
    session.commit()
    return ciam.user_info(user)


@router.get("/api/settings/transaction-logs")
def transaction_logs(
    session: Db,
    actor: Admin,
    response: Response,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    category: str | None = Query(default=None, max_length=50),
    status: Literal["success", "failed", "warning", "info"] | None = None,
    triggered_by: str | None = Query(default=None, max_length=220),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    legacy: bool = False,
):
    response.headers["Cache-Control"] = "no-store"
    if date_from and date_to and utc(date_from) > utc(date_to):
        raise HTTPException(422, "ช่วงวันที่ไม่ถูกต้อง")
    model = AuditEvent if legacy else TransactionLog
    query = select(model)
    timestamp = model.occurred_at if legacy else model.created_at
    if legacy:
        query = query.where(AuditEvent.entity_type == "ciam_security")
        if category or status:
            raise HTTPException(422, "ประวัติเดิมไม่มี Category/Status ที่ยืนยันได้")
    else:
        if category:
            query = query.where(TransactionLog.category == category)
        if status:
            query = query.where(TransactionLog.status == status)
    if triggered_by:
        column = model.actor if legacy else model.triggered_by
        query = query.where(column.icontains(triggered_by, autoescape=True))
    if date_from:
        query = query.where(timestamp >= utc(date_from))
    if date_to:
        query = query.where(timestamp <= utc(date_to))
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    rows = session.scalars(
        query.order_by(timestamp.desc(), model.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    if legacy:
        # Legacy details were not schema-allowlisted; expose only established metadata.
        items = [
            {
                "id": r.id,
                "event_code": "LEGACY",
                "category": None,
                "action": r.action,
                "status": None,
                "message": "ประวัติเดิม: " + r.action,
                "details": {},
                "triggered_by": r.actor,
                "created_at": r.occurred_at,
                "records_count": None,
                "duration_ms": None,
            }
            for r in rows
        ]
    else:
        items = [
            {
                **{
                    key: getattr(r, key)
                    for key in (
                        "id",
                        "event_code",
                        "category",
                        "action",
                        "status",
                        "message",
                        "triggered_by",
                        "created_at",
                        "records_count",
                        "duration_ms",
                    )
                },
                "details": json.loads(r.details or "{}"),
            }
            for r in rows
        ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/api/settings/ciam-sso/test-ad-login")
def test_ad_login(
    payload: LocalLogin, request: Request, response: Response, session: Db, actor: Admin
):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return ad_auth.test_credentials(session, request, payload.username, payload.password, actor)
