from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

import smbclient
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.config import get_settings
from app.local_time import bangkok_now
from app.models import SystemSetting

BASE_UNC_KEY = "fileshare_base_unc"
DOMAIN_KEY = "fileshare_domain"
USERNAME_KEY = "fileshare_username"
PASSWORD_KEY = "fileshare_password"
LAST_TEST_AT_KEY = "fileshare_last_test_at"
LAST_TEST_STATUS_KEY = "fileshare_last_test_status"
LAST_TEST_RESULTS_KEY = "fileshare_last_test_results"


class FileShareSettingsError(ValueError):
    pass


@dataclass(frozen=True)
class PathTestResult:
    code: str
    name: str
    path: str
    status: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "name": self.name,
            "path": self.path,
            "status": self.status,
            "message": self.message,
        }


def _fernet() -> Fernet:
    key = get_settings().settings_encryption_key
    if not key:
        raise FileShareSettingsError("ยังไม่ได้ตั้งค่า Settings Encryption Key บน Server")
    try:
        return Fernet(key.encode())
    except ValueError as exc:
        raise FileShareSettingsError("Settings Encryption Key ไม่ถูกต้อง") from exc


def _row(session: Session, key: str) -> SystemSetting | None:
    return session.get(SystemSetting, key)


def setting_value(session: Session, key: str) -> str | None:
    row = _row(session, key)
    return row.value if row else None


def set_setting(
    session: Session,
    key: str,
    value: str | None,
    *,
    secret: bool,
    actor: str,
) -> None:
    row = _row(session, key)
    if row is None:
        session.add(SystemSetting(key=key, value=value, is_secret=secret, updated_by=actor))
        return
    row.value = value
    row.is_secret = secret
    row.updated_by = actor


def set_password(session: Session, password: str, actor: str) -> None:
    encrypted = _fernet().encrypt(password.encode()).decode()
    set_setting(session, PASSWORD_KEY, encrypted, secret=True, actor=actor)


def password_value(session: Session) -> str | None:
    encrypted = setting_value(session, PASSWORD_KEY)
    if not encrypted:
        return None
    try:
        return _fernet().decrypt(encrypted.encode()).decode()
    except InvalidToken as exc:
        raise FileShareSettingsError("ไม่สามารถถอดรหัส FileShare Password ได้") from exc


def normalize_base_unc(value: str) -> str:
    normalized = value.strip().replace("/", "\\").rstrip("\\")
    parts = [part for part in normalized.split("\\") if part]
    if not normalized.startswith("\\\\") or len(parts) < 2:
        raise FileShareSettingsError(
            "Base UNC ต้องอยู่ในรูปแบบ \\\\server\\share หรือ Path ภายใน Share"
        )
    if any(part in {".", ".."} for part in parts):
        raise FileShareSettingsError("Base UNC ห้ามมี . หรือ ..")
    return "\\\\" + "\\".join(parts)


def normalize_subfolder(value: str) -> str:
    normalized = value.strip().replace("/", "\\").strip("\\")
    parts = [part for part in normalized.split("\\") if part]
    if not parts or value.strip().startswith(("\\", "/")):
        raise FileShareSettingsError("Subfolder ต้องเป็น Path ภายใน Base UNC")
    if any(part in {".", ".."} for part in parts):
        raise FileShareSettingsError("Subfolder ห้ามมี . หรือ ..")
    return "\\".join(parts)


def compose_unc(base_unc: str, subfolder: str) -> str:
    return f"{normalize_base_unc(base_unc)}\\{normalize_subfolder(subfolder)}"


def effective_username(domain: str, username: str) -> str:
    clean_domain = domain.strip()
    clean_username = username.strip()
    if clean_domain and "\\" not in clean_username and "@" not in clean_username:
        return f"{clean_domain}\\{clean_username}"
    return clean_username


def _safe_error(exc: Exception) -> str:
    text = str(exc).lower()
    name = type(exc).__name__.lower()
    if "logon" in text or "auth" in text or "credential" in text:
        return "User หรือ Password ไม่ถูกต้อง"
    if "access_denied" in text or "permission" in text or "denied" in text:
        return "Account ไม่มีสิทธิ์เข้าถึง Path"
    if "not_found" in text or "no such" in text or "bad_network_name" in text:
        return "ไม่พบ Share หรือ Folder"
    if "timeout" in text or "timed out" in text:
        return "เชื่อมต่อ NAS เกินเวลาที่กำหนด"
    if "name" in name or "network" in text or "connection" in text:
        return "เชื่อมต่อ NAS ไม่สำเร็จ กรุณาตรวจสอบชื่อ Server และ Network"
    return "เข้าถึง FileShare ไม่สำเร็จ"


def _stat_path(path: str, username: str, password: str) -> None:
    smbclient.stat(
        path,
        username=username,
        password=password,
        port=445,
        connection_timeout=10,
    )


def test_paths(
    *,
    base_unc: str,
    domain: str,
    username: str,
    password: str,
    profiles: list[tuple[str, str, str]],
) -> list[PathTestResult]:
    clean_base = normalize_base_unc(base_unc)
    login = effective_username(domain, username)
    if not login or not password:
        raise FileShareSettingsError("กรุณากรอก User และ Password สำหรับ FileShare")

    results: list[PathTestResult] = []
    try:
        try:
            _stat_path(clean_base, login, password)
        except Exception as exc:
            message = _safe_error(exc)
            return [
                PathTestResult(code, name, compose_unc(clean_base, folder), "failed", message)
                for code, name, folder in profiles
            ]
        for code, name, folder in profiles:
            path = compose_unc(clean_base, folder)
            try:
                _stat_path(path, login, password)
                results.append(PathTestResult(code, name, path, "success", "เข้าถึง Path ได้"))
            except Exception as exc:
                results.append(PathTestResult(code, name, path, "failed", _safe_error(exc)))
    finally:
        smbclient.reset_connection_cache()
    return results


def record_test(
    session: Session,
    results: list[PathTestResult],
    *,
    actor: str,
    tested_at: datetime | None = None,
) -> str:
    status = (
        "success"
        if results and all(item.status == "success" for item in results)
        else "failed"
    )
    timestamp = tested_at or bangkok_now()
    set_setting(session, LAST_TEST_AT_KEY, timestamp.isoformat(), secret=False, actor=actor)
    set_setting(session, LAST_TEST_STATUS_KEY, status, secret=False, actor=actor)
    set_setting(
        session,
        LAST_TEST_RESULTS_KEY,
        json.dumps([item.as_dict() for item in results], ensure_ascii=False),
        secret=False,
        actor=actor,
    )
    return status
