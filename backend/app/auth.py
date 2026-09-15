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


def require_data_operator() -> str:
    """Temporary Data Operator-or-Admin boundary until AD auth is implemented."""
    if get_settings().auth_mode == "development":
        return "development-data-operator"
    raise HTTPException(
        status_code=503,
        detail="ยังไม่ได้เปิดใช้งาน AD Authentication สำหรับ Data Operator",
    )
