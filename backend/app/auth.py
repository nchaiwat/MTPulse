"""Shared authorization for every application API, including direct API clients."""

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_session
from app.models import AuthSession, AuthUser

SESSION_COOKIE = "__Host-mtpulse_session"
PUBLIC_PATHS = {
    "/health",
    "/api/auth/sso/config",
    "/api/auth/sso/authorize-url",
    "/api/auth/sso/callback",
    "/api/auth/local/login",
    "/api/auth/ad/login",
}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def actor_from_session(session: Session, fallback: str) -> str:
    return session.info.get("auth_actor", fallback)


def role_for_path(path: str, method: str) -> str:
    # Unknown endpoints require Admin; newly added APIs cannot silently become public.
    if path.startswith("/api/assortment/"):
        if method in SAFE_METHODS:
            return "viewer"
        return "operator" if path.startswith("/api/assortment/plans") else "admin"
    if path.startswith("/api/auth/"):
        return "admin" if path.endswith("break-glass-toggle") else "viewer"
    if (
        method in SAFE_METHODS
        and path.endswith("/unmatched-visibility")
        and path.startswith(("/api/settings/twd/", "/api/settings/modern-trades/"))
    ):
        return "operator"
    if path.startswith(("/api/settings/", "/api/admin/")):
        return "admin"
    if path.startswith(
        (
            "/api/dashboards/",
            "/api/performance",
            "/api/sale-out",
            "/api/item-mappings/export",
            "/api/data-coverage/export",
        )
    ):
        return "viewer" if method in SAFE_METHODS else "operator"
    if path.startswith(("/api/imports/fileshare",)):
        return "admin"
    if path.startswith(("/api/imports", "/api/item-mappings", "/api/dh-prices")):
        return "operator"
    return "admin"


def authorize_request(request: Request, session: Annotated[Session, Depends(get_session)]):
    mode = get_settings().auth_mode
    if mode == "development" or request.url.path in PUBLIC_PATHS:
        return
    if mode != "ciam":
        raise HTTPException(503, "ยังไม่ได้เปิดใช้งานระบบยืนยันตัวตน")
    token = request.cookies.get(SESSION_COOKIE, "")
    if not token:
        raise HTTPException(401, "กรุณาเข้าสู่ระบบ")
    login = session.get(AuthSession, digest(token))
    if login is None or utc(login.expires_at) <= datetime.now(UTC):
        raise HTTPException(401, "Session หมดอายุ กรุณาเข้าสู่ระบบใหม่")
    user = session.get(AuthUser, login.user_id)
    if not user or not user.active or (login.provider == "ad" and not user.ad_username):
        raise HTTPException(401, "บัญชีถูกระงับ กรุณาติดต่อผู้ดูแลระบบ")
    rank = {"viewer": 0, "operator": 1, "admin": 2}
    if rank.get(user.role, -1) < rank[role_for_path(request.url.path, request.method)]:
        raise HTTPException(403, "คุณไม่มีสิทธิ์ใช้งานส่วนนี้")
    if request.method not in SAFE_METHODS:
        csrf = request.headers.get("X-CSRF-Token", "")
        if not secrets.compare_digest(csrf, digest("csrf:" + token)):
            raise HTTPException(403, "คำขอไม่ผ่านการตรวจสอบ CSRF กรุณาโหลดหน้าใหม่")
    request.state.auth_user = user
    request.state.auth_session = login
    session.info["auth_actor"] = "user:" + user.id


def require_system_admin(request: Request = None) -> str:
    if get_settings().auth_mode == "development":
        return "development-admin"
    if get_settings().auth_mode != "ciam":
        raise HTTPException(503, "ยังไม่ได้เปิดใช้งานระบบยืนยันตัวตน")
    user = getattr(getattr(request, "state", None), "auth_user", None)
    if not user or user.role != "admin":
        raise HTTPException(403, "ต้องใช้สิทธิ์ System Admin")
    return "user:" + user.id


def require_data_operator(request: Request = None) -> str:
    if get_settings().auth_mode == "development":
        return "development-data-operator"
    user = getattr(getattr(request, "state", None), "auth_user", None)
    if not user or user.role not in {"operator", "admin"}:
        raise HTTPException(403, "ต้องใช้สิทธิ์ Data Operator หรือ System Admin")
    return "user:" + user.id
