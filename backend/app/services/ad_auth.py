"""Admin-enabled MTPulse accounts authenticated by the LAN AD Gateway."""

import re
from datetime import UTC, datetime
from ipaddress import ip_address, ip_network
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import SESSION_COOKIE
from app.models import AuthUser
from app.services import ciam


def normalize_username(value: str) -> str:
    value = value.strip().lower()
    # Gateway v2 interpolates the username into an LDAP filter. Reject filter syntax.
    if (
        not value
        or len(value) > 200
        or any(c in value for c in "*()\\\x00")
        or re.search(r"\s", value)
    ):
        raise ValueError("ใช้ AD sAMAccountName โดยไม่มี domain หรืออักขระพิเศษของ LDAP")
    return value


def validate_gateway_url(value: str) -> str:
    parts = urlsplit(value)
    if (
        parts.scheme not in ("http", "https")
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
        or parts.path != "/api/v2/login"
        or parts.port == 0
    ):
        raise ValueError("ต้องเป็น URL ของ AD Gateway /api/v2/login")
    if parts.scheme == "http":
        address = ip_address(parts.hostname)
        if not any(
            address in ip_network(net) for net in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
        ):
            raise ValueError("HTTP อนุญาตเฉพาะ IP ภายใน LAN")
    return value


def verify_gateway(cfg: dict, username: str, password: str):
    with httpx.Client(timeout=10, follow_redirects=False, trust_env=False) as client:
        result = client.post(
            validate_gateway_url(cfg["ciam_ad_gateway_url"]),
            json={
                "app_id": cfg["ciam_ad_app_id"],
                "secret_key": cfg["ciam_ad_secret"],
                "username": username,
                "password": password,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
    if result.status_code == 429:
        raise HTTPException(429, "AD Gateway จำกัดจำนวนคำขอ กรุณาลองใหม่ภายหลัง")
    if result.status_code >= 500:
        raise HTTPException(502, "AD Gateway ไม่พร้อมใช้งาน")
    if result.status_code != 200:
        raise HTTPException(401, "ยืนยันตัวตน AD ไม่สำเร็จ")
    body = result.json()
    if (
        not isinstance(body, dict)
        or body.get("status") != "success"
        or not isinstance(body.get("data"), dict)
        or not isinstance(body["data"].get("username"), str)
        or normalize_username(body["data"]["username"]) != username
    ):
        raise HTTPException(401, "ผลยืนยันตัวตน AD ไม่ถูกต้อง")


def login(session: Session, request: Request, response: Response, username: str, password: str):
    cfg = ciam.config(session, ad_secret=True)
    ciam.same_origin(request, cfg)
    if not cfg["ciam_ad_secret"] or not cfg["ciam_ad_app_id"].strip():
        raise HTTPException(503, "ยังตั้งค่า AD Gateway ไม่ครบ")
    ciam.throttle(session, "ad-ip:" + (request.client.host if request.client else "unknown"), 40)
    try:
        username = normalize_username(username)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    ciam.throttle(session, "ad-account:" + username, 10)
    try:
        user = session.scalar(select(AuthUser).where(AuthUser.ad_username == username))
        if not user or not user.active or user.issuer == ciam.LOCAL_ISSUER:
            raise HTTPException(401, "ยืนยันตัวตน AD ไม่สำเร็จ หรือยังไม่ได้รับสิทธิ์เข้าใช้งาน")
        verify_gateway(cfg, username, password)
        # Discard the earlier transaction/snapshot after network I/O and lock the user.
        user_id = user.id
        session.rollback()
        ciam.lock_ad_settings(session)
        user = session.scalar(select(AuthUser).where(AuthUser.id == user_id).with_for_update())
        current = ciam.config(session, ad_secret=True)
        if ciam.fingerprint(current) != ciam.fingerprint(cfg):
            raise HTTPException(401, "การตั้งค่าเปลี่ยน กรุณาเข้าสู่ระบบใหม่")
        if not user or not user.active or user.ad_username != username:
            raise HTTPException(401, "สิทธิ์หรือบัญชีที่ผูกไว้เปลี่ยน กรุณาติดต่อผู้ดูแลระบบ")
        return ciam.issue_session(
            session,
            response,
            user,
            "ad",
            cfg["ciam_session_ttl_minutes"],
            request.cookies.get(SESSION_COOKIE, ""),
        )
    except (HTTPException, httpx.HTTPError, ValueError, TypeError) as exc:
        session.rollback()
        ciam.audit(
            session,
            "login_failed",
            "anonymous",
            {
                "provider": "ad",
                "error": type(exc).__name__,
                "http_status": exc.status_code if isinstance(exc, HTTPException) else 502,
            },
        )
        session.commit()
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(502, "ติดต่อหรืออ่านผล AD Gateway ไม่สำเร็จ") from exc


def test_credentials(
    session: Session, request: Request, username: str, password: str, actor: str
) -> dict:
    """Probe saved gateway credentials without issuing a session or mutating accounts."""
    cfg = ciam.config(session, ad_secret=True)
    ciam.same_origin(request, cfg)
    tested_username = None
    gateway_status = "unavailable"
    mtpulse_status = "not_checked"
    messages = {
        "success": "AD Gateway ยืนยันตัวตนสำเร็จ",
        "rejected": "AD Gateway ไม่ยืนยันตัวตน ตรวจสอบบัญชี รหัสผ่าน และสิทธิ์ที่ Gateway",
        "timeout": "AD Gateway ไม่ตอบกลับภายในเวลาที่กำหนด",
        "unavailable": "ติดต่อหรืออ่านผล AD Gateway ไม่สำเร็จ",
        "rate_limited": "ทดสอบถี่เกินไป กรุณารอสักครู่แล้วลองใหม่",
        "not_configured": "ยังตั้งค่า AD Gateway ไม่ครบ กรุณาบันทึกการตั้งค่าก่อน",
        "invalid_username": "ใช้ AD sAMAccountName โดยไม่มี domain หรืออักขระพิเศษของ LDAP",
        "settings_changed": "การตั้งค่าเปลี่ยนระหว่างทดสอบ กรุณาทดสอบใหม่",
    }
    try:
        try:
            tested_username = normalize_username(username)
        except ValueError:
            raise HTTPException(422) from None
        ciam.throttle(session, "ad-test-admin:" + actor, 10)
        ciam.throttle(
            session, "ad-ip:" + (request.client.host if request.client else "unknown"), 40
        )
        ciam.throttle(session, "ad-account:" + tested_username, 10)
        if not cfg["ciam_ad_secret"] or not cfg["ciam_ad_app_id"].strip():
            raise HTTPException(503)
        verify_gateway(cfg, tested_username, password)
        session.rollback()
        session.expire_all()
        if ciam.fingerprint(ciam.config(session, ad_secret=True)) != ciam.fingerprint(cfg):
            raise HTTPException(409)
        # Match the real login's binding first; a same-name account alone is not permission.
        user = session.scalar(select(AuthUser).where(AuthUser.ad_username == tested_username))
        if user is None:
            matches = list(
                session.scalars(
                    select(AuthUser).where(
                        func.lower(func.trim(AuthUser.username)) == tested_username
                    )
                )
            )
            if len(matches) > 1:
                mtpulse_status = "ambiguous"
            elif matches:
                user = matches[0]
            else:
                mtpulse_status = "account_missing"
        if user:
            if user.issuer == ciam.LOCAL_ISSUER:
                mtpulse_status = "local_account"
            elif not user.active:
                mtpulse_status = "disabled"
            elif user.ad_username != tested_username:
                mtpulse_status = "ad_not_enabled"
            else:
                mtpulse_status = "ready"
        gateway_status = "success"
    except HTTPException as exc:
        gateway_status = {
            401: "rejected",
            429: "rate_limited",
            503: "not_configured",
            409: "settings_changed",
            422: "invalid_username",
        }.get(exc.status_code, "unavailable")
    except httpx.TimeoutException:
        gateway_status = "timeout"
    except (httpx.HTTPError, ValueError, TypeError):
        gateway_status = "unavailable"
    session.rollback()
    ciam.audit(
        session,
        "ad_gateway_test",
        actor,
        {
            "tested_username": tested_username,
            "provider": "ad",
            "gateway_status": gateway_status,
            "mtpulse_status": mtpulse_status,
            "status": "success" if gateway_status == "success" else "failed",
        },
    )
    session.commit()
    return {
        "gateway_status": gateway_status,
        "mtpulse_status": mtpulse_status,
        "message": messages[gateway_status],
    }
