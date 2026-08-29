from fastapi import HTTPException

from app.config import get_settings


def require_system_admin() -> str:
    """Temporary boundary until direct AD authentication is implemented."""
    if get_settings().auth_mode == "development":
        return "development-admin"
    raise HTTPException(
        status_code=503,
        detail="ยังไม่ได้เปิดใช้งาน AD Authentication สำหรับการตั้งค่าระบบ",
    )
