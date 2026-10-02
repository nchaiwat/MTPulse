"""Emergency local administrator authentication; never stores AD credentials."""

import hashlib
import secrets
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import SESSION_COOKIE
from app.models import AuthSession, AuthUser
from app.services import ciam

ITERATIONS = 600_000


def hash_password(password: str) -> str:
    if not 12 <= len(password) <= 256:
        raise ValueError("รหัสผ่านต้องมีความยาว 12–256 ตัวอักษร")
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${key.hex()}"


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        # Similar work for unknown account/password to avoid user enumeration.
        hashlib.pbkdf2_hmac("sha256", password.encode(), b"missing-account", ITERATIONS)
        return False
    try:
        algorithm, iterations, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256" or int(iterations) != ITERATIONS:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS)
        return secrets.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False


def bootstrap(session: Session, username: str, password: str, *, reset=False) -> AuthUser:
    username = username.strip().lower()
    if not username or len(username) > 200:
        raise ValueError("ชื่อผู้ใช้ต้องยาว 1–200 ตัวอักษร")
    user = session.scalar(
        select(AuthUser).where(AuthUser.issuer == ciam.LOCAL_ISSUER, AuthUser.subject == username)
    )
    if user and not reset:
        raise ValueError("บัญชีนี้มีอยู่แล้ว ใช้ --reset-password เมื่อจำเป็น")
    encoded = hash_password(password)
    if user is None:
        user = AuthUser(
            id=str(uuid4()),
            issuer=ciam.LOCAL_ISSUER,
            subject=username,
            username=username,
            full_name=username,
            role="admin",
            active=True,
            created_at=datetime.now(UTC),
        )
        session.add(user)
        session.flush()
    user.password_hash = encoded
    user.role, user.active = "admin", True
    session.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    ciam.audit(session, "local_admin_bootstrap", "system:server-console", {"user_id": user.id})
    session.commit()
    return user


def login(session: Session, request: Request, response: Response, username: str, password: str):
    cfg = ciam.config(session)
    ciam.same_origin(request, cfg)
    username = username.strip().lower()
    ciam.throttle(session, "local-account:" + username, 10)
    ciam.throttle(session, "local-ip:" + (request.client.host if request.client else "unknown"), 40)
    user = session.scalar(
        select(AuthUser).where(AuthUser.issuer == ciam.LOCAL_ISSUER, AuthUser.subject == username)
    )
    valid = verify_password(password, user.password_hash if user else None)
    if not valid or not user or not user.active or user.role != "admin":
        ciam.audit(session, "login_failed", "anonymous", {"provider": "local"})
        session.commit()
        raise HTTPException(401, "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
    return ciam.issue_session(
        session,
        response,
        user,
        "local",
        cfg["ciam_session_ttl_minutes"],
        request.cookies.get(SESSION_COOKIE, ""),
    )
