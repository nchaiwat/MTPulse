"""Outbound Mode C contract; all provider data is validated before local mutation."""

import hashlib
import json
import json as json_module
from datetime import UTC, datetime, timedelta

import httpx
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import utc
from app.models import (
    AuthSession,
    AuthUser,
    CiamAgentCommand,
    CiamAgentState,
    SystemSetting,
    TransactionLog,
)
from app.services import ciam
from app.services.telegram import set_setting

DEFAULTS = {"enabled": False, "app_code": "mtpulse"}
PREFIX = "ciam_agent_"


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


class Command(BaseModel):
    command_id: str = Field(min_length=1, max_length=200)
    action: str = Field(min_length=1, max_length=50)
    username: str = Field(min_length=1, max_length=200)
    reason: str = Field(default="", max_length=500)
    issued_at: datetime

    @field_validator("issued_at")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None:
            raise ValueError("Command requires timezone")
        return value.astimezone(UTC)

    @field_validator("username")
    @classmethod
    def normalize(cls, value):
        value = value.strip().lower()
        if not value or any(ord(c) < 32 for c in value):
            raise ValueError("Invalid account")
        return value


def audit(db, action, outcome, message, details, actor="system:ciam-agent"):
    if actor.startswith("user:"):
        user = db.get(AuthUser, actor[5:])
        if user:
            actor = "user:" + user.username
    context = db.info.get("audit_context", {})
    details = {
        **{
            k: context[k]
            for k in ("ip", "ip_source", "peer_ip", "request_method", "request_path")
            if k in context
        },
        **details,
    }
    db.add(
        TransactionLog(
            event_code="AGENT-" + action.upper(),
            category="ciam_agent",
            action=action,
            status=outcome,
            message=message,
            details=json.dumps(details, ensure_ascii=False),
            triggered_by=actor,
            records_count=1 if action == "command" else 0,
            duration_ms=0,
        )
    )


def config(db, secret=False):
    rows = {
        r.key: r.value
        for r in db.scalars(
            select(SystemSetting).where(
                SystemSetting.key.in_([PREFIX + k for k in [*DEFAULTS, "api_key"]])
            )
        )
    }
    cfg = {
        k: json.loads(rows[PREFIX + k]) if PREFIX + k in rows else v for k, v in DEFAULTS.items()
    }
    cfg["key_configured"] = bool(rows.get(PREFIX + "api_key"))
    if secret:
        cfg["api_key"] = (
            ciam.crypto().decrypt(rows[PREFIX + "api_key"].encode()).decode()
            if cfg["key_configured"]
            else ""
        )
    return cfg


def save_config(db, values, actor):
    if values.get("enabled"):
        current = ciam.config(db)
        if not current["ciam_client_id"].strip() or not (
            values.get("api_key") or config(db)["key_configured"]
        ):
            from fastapi import HTTPException

            raise HTTPException(422, "ต้องตั้ง CIAM Client ID และ Agent API Key ก่อนเปิด Agent")
    for key in DEFAULTS:
        if key in values:
            set_setting(db, PREFIX + key, json.dumps(values[key]), secret=False, actor=actor)
    if values.get("api_key"):
        set_setting(
            db,
            PREFIX + "api_key",
            ciam.crypto().encrypt(values["api_key"].encode()).decode(),
            secret=True,
            actor=actor,
        )
    audit(
        db,
        "settings",
        "success",
        "แก้ไขการตั้งค่า Outbound Agent",
        {"changed_fields": list(values)},
        actor,
    )
    db.commit()
    return config(db)


def state(db):
    row = db.get(CiamAgentState, 1)
    return json.loads(row.payload) if row else {}


def store_state(db, values):
    row = db.get(CiamAgentState, 1)
    if row is None:
        row = CiamAgentState(id=1)
        db.add(row)
    row.payload = json.dumps(values)


def status(db):
    cfg = config(db)
    saved = state(db)
    cfg.update({k: v for k, v in saved.items() if k not in ("scope", "inventory_digest")})
    cfg["pending_results"] = len(
        list(
            db.scalars(select(CiamAgentCommand.key).where(CiamAgentCommand.acknowledged.is_(False)))
        )
    )
    return cfg


def inventory(db):
    return [
        {
            "username": u.username,
            "full_name": u.full_name,
            "email": u.email,
            "department": None,
            "role": u.role,
            "is_active": u.active,
        }
        for u in db.scalars(select(AuthUser).order_by(AuthUser.username, AuthUser.id))
    ]


def apply_command(db: Session, scope: str, raw: dict):
    cmd = Command.model_validate(raw)
    content = cmd.model_dump(mode="json")
    key, fingerprint = digest([scope, cmd.command_id]), digest(content)
    previous = db.get(CiamAgentCommand, key)
    if previous:
        if previous.fingerprint != fingerprint:
            raise ValueError("Conflicting command ID")
        if json.loads(previous.result)["status"] != "PENDING":
            return json.loads(previous.result)
    ciam.lock_user_registry(db)
    users = list(
        db.scalars(
            select(AuthUser)
            .order_by(AuthUser.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    )
    matches = [u for u in users if u.username.strip().lower() == cmd.username]
    user = matches[0] if len(matches) == 1 else None
    newer = list(
        db.scalars(
            select(CiamAgentCommand).where(
                CiamAgentCommand.scope == scope, CiamAgentCommand.username == cmd.username
            )
        )
    )
    error = None
    if cmd.action not in ("DISABLE_USER", "ENABLE_USER"):
        error = "Unsupported command"
    elif not user:
        error = "Account missing or ambiguous"
    elif user.issuer == ciam.LOCAL_ISSUER:
        error = "Emergency Local Admin is protected"
    elif any(
        utc(r.issued_at) >= cmd.issued_at and json.loads(r.result)["status"] == "COMPLETED"
        for r in newer
    ):
        error = "Stale or unordered command"
    elif (
        cmd.action == "DISABLE_USER"
        and user.role == "admin"
        and not any(u.id != user.id and u.active and u.role == "admin" for u in users)
    ):
        error = "Last active administrator is protected"
    before = user.active if user else None
    revoked = 0
    if not error:
        user.active = cmd.action == "ENABLE_USER"
        if not user.active:
            revoked = db.execute(delete(AuthSession).where(AuthSession.user_id == user.id)).rowcount
    result = {
        "command_id": cmd.command_id,
        "action": cmd.action,
        "username": cmd.username,
        "status": "FAILED" if error else "COMPLETED",
        "message": error or "Account status applied",
    }
    if previous:
        previous.result = json.dumps(result)
    else:
        db.add(
            CiamAgentCommand(
                key=key,
                scope=scope,
                command_id=cmd.command_id,
                fingerprint=fingerprint,
                username=cmd.username,
                issued_at=cmd.issued_at,
                payload=json.dumps(content),
                result=json.dumps(result),
                acknowledged=False,
            )
        )
    audit(
        db,
        "command",
        "failed" if error else "success",
        f"CIAM {cmd.action}: {cmd.username}",
        {
            **result,
            "before_active": before,
            "after_active": user.active if user else None,
            "sessions_revoked": revoked,
            "issued_at": cmd.issued_at.isoformat(),
            "reason": cmd.reason,
            "initiator": "ไม่ระบุผู้สั่งจาก CIAM",
        },
        "system:ciam",
    )
    db.commit()
    return result


def api_healthy():
    try:
        return (
            httpx.get("http://api:8000/health", timeout=3, follow_redirects=False).status_code
            == 200
        )
    except httpx.HTTPError:
        return False


def send_heartbeat(url, *, headers, json):
    # No redirects: do not forward an M2M credential to another destination.
    with httpx.Client(timeout=15, follow_redirects=False) as client:
        with client.stream("POST", url, headers=headers, json=json) as response:
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > 2_000_000:
                    raise ValueError("Oversized heartbeat response")
            return json_module.loads(body)


def cycle(db: Session, now=None):
    now = now or datetime.now(UTC)
    s = state(db)
    cfg = config(db, secret=True)
    if not cfg["enabled"]:
        return
    try:
        identity = ciam.config(db)
        base = ciam.validate_url(identity["ciam_base_url"]).rstrip("/")
        client_id = identity["ciam_client_id"]
        if not cfg["api_key"] or not client_id:
            raise ValueError("Agent credentials not configured")
        scope = digest([base, client_id, cfg["app_code"]])
        pending = list(
            db.scalars(
                select(CiamAgentCommand)
                .where(CiamAgentCommand.scope == scope, CiamAgentCommand.acknowledged.is_(False))
                .order_by(CiamAgentCommand.issued_at, CiamAgentCommand.command_id)
            )
        )
        for item in pending:
            if json.loads(item.result)["status"] == "PENDING":
                apply_command(db, scope, json.loads(item.payload))
        if s.get("next_attempt") and datetime.fromisoformat(s["next_attempt"]) > now:
            return
        snapshot = digest([cfg, base, client_id])
        rows = list(
            db.scalars(
                select(CiamAgentCommand)
                .where(CiamAgentCommand.scope == scope, CiamAgentCommand.acknowledged.is_(False))
                .limit(100)
            )
        )
        sent_keys = [r.key for r in rows]
        accounts = inventory(db)
        full = (
            s.get("scope") != scope
            or s.get("inventory_digest") != digest(accounts)
            or not s.get("last_full_sync")
            or now - datetime.fromisoformat(s["last_full_sync"]) >= timedelta(days=1)
        )
        payload = {
            "app_code": cfg["app_code"],
            "status": "HEALTHY" if api_healthy() else "DEGRADED",
            "app_version": "mtpulse-mode-c-v1",
            "sync_type": "FULL_SYNC" if full else "HEARTBEAT",
            "command_results": [json.loads(r.result) for r in rows],
        }
        if full:
            payload["accounts"] = accounts
        db.rollback()  # No stale user/config snapshot across network I/O.
        response = send_heartbeat(
            base + "/api/v1/agent/heartbeat",
            headers={
                "X-Spoke-Client-ID": client_id,
                "X-Spoke-API-Key": cfg["api_key"],
                "X-Request-Timestamp": str(int(now.timestamp())),
            },
            json=payload,
        )
        fresh = ciam.config(db)
        if snapshot != digest(
            [config(db, secret=True), fresh["ciam_base_url"].rstrip("/"), fresh["ciam_client_id"]]
        ):
            raise ValueError("Settings changed during heartbeat")
        if (
            not isinstance(response, dict)
            or response.get("status") != "ACKNOWLEDGED"
            or response.get("app_code") != cfg["app_code"]
        ):
            raise ValueError("Invalid acknowledgement")
        commands = response.get("pending_commands", [])
        if not isinstance(commands, list) or len(commands) > 100:
            raise ValueError("Invalid command batch")
        parsed = [Command.model_validate(c) for c in commands]
        if any(c.issued_at > now + timedelta(minutes=5) for c in parsed):
            raise ValueError("Future command timestamp")
        # Reject a conflicting batch before any mutation or acknowledgement.
        fingerprints = {}
        for cmd in parsed:
            fp = digest(cmd.model_dump(mode="json"))
            prior = db.get(CiamAgentCommand, digest([scope, cmd.command_id]))
            if (cmd.command_id in fingerprints and fingerprints[cmd.command_id] != fp) or (
                prior and prior.fingerprint != fp
            ):
                raise ValueError("Conflicting command ID")
            fingerprints[cmd.command_id] = fp
        for key in sent_keys:
            db.get(CiamAgentCommand, key).acknowledged = True
        for cmd in parsed:
            key = digest([scope, cmd.command_id])
            if db.get(CiamAgentCommand, key) is None:
                content = cmd.model_dump(mode="json")
                db.add(
                    CiamAgentCommand(
                        key=key,
                        scope=scope,
                        command_id=cmd.command_id,
                        fingerprint=digest(content),
                        username=cmd.username,
                        issued_at=cmd.issued_at,
                        payload=json.dumps(content),
                        result=json.dumps({"status": "PENDING"}),
                        acknowledged=False,
                    )
                )
                db.flush()
            else:
                db.get(CiamAgentCommand, key).acknowledged = False
        s.update(
            scope=scope,
            last_success=now.isoformat(),
            last_attempt=now.isoformat(),
            last_error=None,
            api_status=payload["status"],
            next_attempt=(now + timedelta(seconds=120)).isoformat(),
        )
        if full:
            s.update(last_full_sync=now.isoformat(), inventory_digest=digest(accounts))
        store_state(db, s)
        audit(
            db,
            "heartbeat",
            "success",
            "CIAM ตอบรับ Heartbeat",
            {"sync_type": payload["sync_type"], "accounts_count": len(accounts) if full else 0},
        )
        db.commit()
        for cmd in sorted(parsed, key=lambda c: (c.issued_at, c.command_id)):
            apply_command(db, scope, cmd.model_dump(mode="json"))
    except Exception as exc:
        db.rollback()
        # Never persist response bodies, exception messages or credentials.
        code = (
            "HTTP_" + str(exc.response.status_code)
            if isinstance(exc, httpx.HTTPStatusError)
            else type(exc).__name__
        )
        s.update(
            last_attempt=now.isoformat(),
            last_error=code,
            next_attempt=(now + timedelta(seconds=120)).isoformat(),
        )
        store_state(db, s)
        audit(
            db,
            "heartbeat",
            "failed",
            "Outbound Agent ติดต่อหรือประมวลผล CIAM ไม่สำเร็จ",
            {"error": code},
        )
        db.commit()
