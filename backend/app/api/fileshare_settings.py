import json
from datetime import datetime, time, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_system_admin
from app.config import get_settings
from app.database import get_session
from app.local_time import BANGKOK_TIMEZONE, bangkok_now
from app.models import AuditEvent, ImportRun, ModernTrade
from app.services.automatic_import import initial_scan_completed, run_payload
from app.services.fileshare import (
    BASE_UNC_KEY,
    DOMAIN_KEY,
    LAST_TEST_AT_KEY,
    LAST_TEST_RESULTS_KEY,
    LAST_TEST_STATUS_KEY,
    PASSWORD_KEY,
    USERNAME_KEY,
    FileShareSettingsError,
    compose_unc,
    normalize_base_unc,
    normalize_subfolder,
    password_value,
    record_test,
    set_password,
    set_setting,
    setting_value,
    test_paths,
)

router = APIRouter(
    prefix="/api/admin/fileshare-settings",
    tags=["fileshare settings"],
    dependencies=[Depends(require_system_admin)],
)


class SourceProfileUpdate(BaseModel):
    code: str = Field(max_length=20)
    subfolder: str = Field(max_length=255)
    enabled: bool = True
    schedule_enabled: bool = False
    schedule_time: time | None = None

    @model_validator(mode="after")
    def validate_schedule_time(self) -> "SourceProfileUpdate":
        if self.schedule_enabled and self.schedule_time is None:
            raise ValueError("กรุณาระบุเวลาเมื่อเปิด Schedule")
        return self


class FileShareSettingsUpdate(BaseModel):
    base_unc: str = Field(max_length=1000)
    domain: str = Field(default="", max_length=100)
    username: str = Field(max_length=200)
    password: str | None = Field(default=None, max_length=500)
    profiles: list[SourceProfileUpdate]


class FileShareTestRequest(FileShareSettingsUpdate):
    pass


def _modern_trades(session: Session) -> list[ModernTrade]:
    return list(session.scalars(select(ModernTrade).order_by(ModernTrade.code)))


def _saved_results(session: Session) -> list[dict[str, str]]:
    raw = setting_value(session, LAST_TEST_RESULTS_KEY)
    if not raw:
        return []
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return result if isinstance(result, list) else []


def _response(session: Session) -> dict:
    base_unc = setting_value(session, BASE_UNC_KEY) or ""
    modern_trades = _modern_trades(session)
    hp_owner = next((mt for mt in modern_trades if mt.code == "HP"), None)
    profiles = []
    for mt in modern_trades:
        profile_mt = hp_owner if mt.source_group_code == "HP_MH" and hp_owner else mt
        folder = profile_mt.source_subfolder or (
            profile_mt.code if profile_mt.code == "TWD" else ""
        )
        full_path = compose_unc(base_unc, folder) if base_unc and folder else ""
        last_run = session.scalar(
            select(ImportRun)
            .where(ImportRun.modern_trade_id == profile_mt.id)
            .order_by(ImportRun.requested_at.desc(), ImportRun.id.desc())
            .limit(1)
        )
        next_run_at = None
        if profile_mt.schedule_enabled and profile_mt.schedule_time:
            now = bangkok_now()
            candidate = datetime.combine(
                now.date(),
                profile_mt.schedule_time,
                tzinfo=BANGKOK_TIMEZONE,
            )
            if candidate <= now:
                candidate += timedelta(days=1)
            next_run_at = candidate.isoformat()
        profiles.append(
            {
                "code": mt.code,
                "name": mt.name,
                "subfolder": folder,
                "enabled": profile_mt.source_enabled,
                "fullPath": full_path,
                "scheduleEnabled": profile_mt.schedule_enabled,
                "scheduleTime": (
                    profile_mt.schedule_time.strftime("%H:%M")
                    if profile_mt.schedule_time
                    else None
                ),
                "sourceGroup": mt.source_group_code,
                "sharedProfileOwner": (
                    mt.source_group_code is None or mt.code == profile_mt.code
                ),
                "sharedWith": (
                    ["MH"] if mt.code == "HP" and mt.source_group_code == "HP_MH"
                    else ["HP"] if mt.code == "MH" and mt.source_group_code == "HP_MH"
                    else []
                ),
                "initialScanCompleted": initial_scan_completed(
                    session, profile_mt.id
                ),
                "lastRun": (
                    run_payload(last_run, profile_mt, session=session)
                    if last_run
                    else None
                ),
                "nextRunAt": next_run_at,
            }
        )
    return {
        "baseUnc": base_unc,
        "domain": setting_value(session, DOMAIN_KEY) or "",
        "username": setting_value(session, USERNAME_KEY) or "",
        "passwordConfigured": bool(setting_value(session, PASSWORD_KEY)),
        "passwordMasked": "••••••••" if setting_value(session, PASSWORD_KEY) else "",
        "lastTestAt": setting_value(session, LAST_TEST_AT_KEY),
        "lastTestStatus": setting_value(session, LAST_TEST_STATUS_KEY),
        "lastTestResults": _saved_results(session),
        "profiles": profiles,
    }


def _validate_profiles(
    updates: list[SourceProfileUpdate],
    modern_trades: list[ModernTrade],
) -> dict[str, SourceProfileUpdate]:
    known = {mt.code: mt for mt in modern_trades}
    result: dict[str, SourceProfileUpdate] = {}
    for update in updates:
        code = update.code.strip().upper()
        if code not in known:
            raise HTTPException(status_code=400, detail=f"ไม่พบ Modern Trade {code}")
        if code in result:
            raise HTTPException(status_code=400, detail=f"Modern Trade {code} ซ้ำกัน")
        try:
            normalized = normalize_subfolder(update.subfolder)
        except FileShareSettingsError as exc:
            raise HTTPException(status_code=400, detail=f"{code}: {exc}") from exc
        result[code] = update.model_copy(update={"code": code, "subfolder": normalized})
    return result


@router.get("")
def get_fileshare_settings(
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    return _response(session)


@router.get("/password")
def get_fileshare_password(
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    if not get_settings().allow_secret_reveal:
        raise HTTPException(status_code=403, detail="ปิดการเปิดดู Password บน Environment นี้")
    try:
        password = password_value(session)
    except FileShareSettingsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not password:
        raise HTTPException(status_code=404, detail="ยังไม่มี FileShare Password ที่บันทึกไว้")
    return {"password": password}


@router.patch("")
def update_fileshare_settings(
    update: FileShareSettingsUpdate,
    session: Annotated[Session, Depends(get_session)],
    actor: Annotated[str, Depends(require_system_admin)],
) -> dict:
    try:
        base_unc = normalize_base_unc(update.base_unc)
    except FileShareSettingsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    modern_trades = _modern_trades(session)
    profiles = _validate_profiles(update.profiles, modern_trades)
    before = {
        "base_unc": setting_value(session, BASE_UNC_KEY),
        "domain": setting_value(session, DOMAIN_KEY),
        "username": setting_value(session, USERNAME_KEY),
        "password_configured": bool(setting_value(session, PASSWORD_KEY)),
        "profiles": {
            mt.code: {
                "subfolder": mt.source_subfolder,
                "enabled": mt.source_enabled,
                "schedule_enabled": mt.schedule_enabled,
                "schedule_time": (
                    mt.schedule_time.isoformat() if mt.schedule_time else None
                ),
            }
            for mt in modern_trades
        },
    }
    try:
        if update.password and update.password.strip():
            set_password(session, update.password, actor)
    except FileShareSettingsError as exc:
        session.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    set_setting(session, BASE_UNC_KEY, base_unc, secret=False, actor=actor)
    set_setting(session, DOMAIN_KEY, update.domain.strip() or None, secret=False, actor=actor)
    set_setting(session, USERNAME_KEY, update.username.strip() or None, secret=False, actor=actor)
    for mt in modern_trades:
        profile = profiles.get(mt.code)
        if mt.source_group_code == "HP_MH":
            profile = profiles.get("HP") or profiles.get("MH")
        if profile:
            mt.source_subfolder = profile.subfolder
            mt.source_enabled = profile.enabled
            mt.schedule_enabled = profile.schedule_enabled
            mt.schedule_time = profile.schedule_time
    after = {
        "base_unc": base_unc,
        "domain": update.domain.strip(),
        "username": update.username.strip(),
        "password_updated": bool(update.password and update.password.strip()),
        "profiles": {
            code: {
                "subfolder": profile.subfolder,
                "enabled": profile.enabled,
                "schedule_enabled": profile.schedule_enabled,
                "schedule_time": (
                    profile.schedule_time.isoformat()
                    if profile.schedule_time
                    else None
                ),
            }
            for code, profile in profiles.items()
        },
    }
    session.add(
        AuditEvent(
            entity_type="system_setting",
            entity_id="fileshare",
            action="update",
            actor=actor,
            before_json=json.dumps(before, ensure_ascii=False),
            after_json=json.dumps(after, ensure_ascii=False),
        )
    )
    session.commit()
    return _response(session)


@router.post("/test")
def test_fileshare_settings(
    request: FileShareTestRequest,
    session: Annotated[Session, Depends(get_session)],
    actor: Annotated[str, Depends(require_system_admin)],
) -> dict:
    modern_trades = _modern_trades(session)
    profiles = _validate_profiles(request.profiles, modern_trades)
    names = {mt.code: mt.name for mt in modern_trades}
    trades_by_code = {mt.code: mt for mt in modern_trades}
    enabled = [
        (code, names[code], profile.subfolder)
        for code, profile in profiles.items()
        if profile.enabled
        and not (
            trades_by_code[code].source_group_code == "HP_MH"
            and code != "HP"
        )
    ]
    if not enabled:
        raise HTTPException(status_code=400, detail="กรุณาเปิดใช้งานอย่างน้อย 1 Modern Trade")
    try:
        password = request.password.strip() if request.password else password_value(session)
        results = test_paths(
            base_unc=request.base_unc,
            domain=request.domain,
            username=request.username,
            password=password or "",
            profiles=enabled,
        )
    except FileShareSettingsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    status = record_test(session, results, actor=actor)
    session.add(
        AuditEvent(
            entity_type="system_setting",
            entity_id="fileshare",
            action="test_connection",
            actor=actor,
            before_json=None,
            after_json=json.dumps(
                {"status": status, "results": [item.as_dict() for item in results]},
                ensure_ascii=False,
            ),
        )
    )
    session.commit()
    return {
        "status": status,
        "message": (
            "เข้าถึง FileShare ได้"
            if status == "success"
            else "FileShare บาง Path ใช้งานไม่ได้"
        ),
        "results": [item.as_dict() for item in results],
    }
