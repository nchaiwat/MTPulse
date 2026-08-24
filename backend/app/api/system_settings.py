import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import AuditEvent
from app.services.telegram import (
    GROUP_KEY,
    NOTIFY_MANUAL_KEY,
    SettingsCryptoError,
    send_telegram,
    set_bot_token,
    set_setting,
    setting_value,
    telegram_config,
)

router = APIRouter(prefix="/api/settings/system", tags=["system settings"])


class TelegramSettingsUpdate(BaseModel):
    bot_token: str | None = Field(default=None, max_length=300)
    group_id: str = Field(max_length=100)
    notify_manual_import: bool = True


@router.get("/telegram")
def get_telegram_settings(
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    return telegram_config(session)


@router.patch("/telegram")
def update_telegram_settings(
    update: TelegramSettingsUpdate,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    actor = "system-settings"
    try:
        if update.bot_token and update.bot_token.strip():
            set_bot_token(session, update.bot_token.strip(), actor)
    except SettingsCryptoError as exc:
        session.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    set_setting(session, GROUP_KEY, update.group_id.strip() or None, secret=False, actor=actor)
    set_setting(
        session,
        NOTIFY_MANUAL_KEY,
        "true" if update.notify_manual_import else "false",
        secret=False,
        actor=actor,
    )
    session.add(
        AuditEvent(
            entity_type="system_setting",
            entity_id="telegram",
            action="update",
            actor=actor,
            before_json=None,
            after_json=json.dumps(
                {
                    "group_id": update.group_id.strip(),
                    "notify_manual_import": update.notify_manual_import,
                    "bot_token_updated": bool(update.bot_token and update.bot_token.strip()),
                },
                ensure_ascii=False,
            ),
        )
    )
    session.commit()
    return telegram_config(session)


@router.post("/telegram/test")
def test_telegram_settings(
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    group_id = setting_value(session, GROUP_KEY) or "ยังไม่ได้ตั้งค่า"
    delivery = send_telegram(
        session,
        "MT Pulse — ทดสอบการแจ้งเตือน\nเชื่อมต่อ Telegram สำเร็จ",
        force=True,
    )
    session.add(
        AuditEvent(
            entity_type="system_setting",
            entity_id="telegram",
            action="test_notification",
            actor="system-settings",
            before_json=None,
            after_json=json.dumps(
                {"status": delivery.status, "message": delivery.message},
                ensure_ascii=False,
            ),
        )
    )
    session.commit()
    if delivery.status != "sent":
        raise HTTPException(
            status_code=502,
            detail=f"ใช้ Token ที่บันทึกไว้ → Group / Chat ID {group_id}: {delivery.message}",
        )
    return {
        "status": delivery.status,
        "message": f"ใช้ Token ที่บันทึกไว้ → Group / Chat ID {group_id}: {delivery.message}",
    }