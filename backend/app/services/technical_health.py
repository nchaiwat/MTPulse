from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.local_time import BANGKOK_TIMEZONE, bangkok_now
from app.models import AuditEvent
from app.services.telegram import send_telegram, set_setting, setting_value

DAILY_ENABLED_KEY = "technical_daily_enabled"
DAILY_TIME_KEY = "technical_daily_time"
CRITICAL_ENABLED_KEY = "technical_critical_enabled"
RECOVERY_ENABLED_KEY = "technical_recovery_enabled"
COOLDOWN_KEY = "technical_cooldown_minutes"
LAST_EVALUATED_KEY = "technical_last_evaluated_at"
LAST_DAILY_SENT_KEY = "technical_last_daily_sent_date"
LAST_DAILY_ATTEMPT_KEY = "technical_last_daily_attempt_at"
ALERT_STATE_KEY = "technical_alert_state"
WORKER_HEARTBEAT_KEY = "technical_worker_heartbeat_at"

THRESHOLD_KEYS = {
    "cpu": ("technical_cpu_warning", "technical_cpu_critical"),
    "memory": ("technical_memory_warning", "technical_memory_critical"),
    "disk": ("technical_disk_warning", "technical_disk_critical"),
    "connections": (
        "technical_connections_warning",
        "technical_connections_critical",
    ),
    "deadTuples": (
        "technical_dead_tuples_warning",
        "technical_dead_tuples_critical",
    ),
}

DEFAULT_THRESHOLDS = {
    "cpu": (80.0, 95.0),
    "memory": (80.0, 90.0),
    "disk": (80.0, 90.0),
    "connections": (80.0, 95.0),
    "deadTuples": (10.0, 20.0),
}


@dataclass(frozen=True)
class TechnicalNotificationConfig:
    daily_enabled: bool
    daily_time: time
    critical_enabled: bool
    recovery_enabled: bool
    cooldown_minutes: int
    thresholds: dict[str, tuple[float, float]]

    def as_dict(self) -> dict[str, object]:
        return {
            "dailyEnabled": self.daily_enabled,
            "dailyTime": self.daily_time.strftime("%H:%M"),
            "criticalEnabled": self.critical_enabled,
            "recoveryEnabled": self.recovery_enabled,
            "cooldownMinutes": self.cooldown_minutes,
            "thresholds": {
                code: {"warning": values[0], "critical": values[1]}
                for code, values in self.thresholds.items()
            },
        }


def _bool_value(session: Session, key: str, default: bool) -> bool:
    value = setting_value(session, key)
    if value is None:
        return default
    return value.lower() == "true"


def _float_value(session: Session, key: str, default: float) -> float:
    try:
        return float(setting_value(session, key) or default)
    except ValueError:
        return default


def _int_value(session: Session, key: str, default: int) -> int:
    try:
        return int(setting_value(session, key) or default)
    except ValueError:
        return default


def technical_notification_config(session: Session) -> TechnicalNotificationConfig:
    raw_time = setting_value(session, DAILY_TIME_KEY) or "07:00"
    try:
        daily_time = time.fromisoformat(raw_time)
    except ValueError:
        daily_time = time(7)
    thresholds = {
        code: (
            _float_value(session, keys[0], defaults[0]),
            _float_value(session, keys[1], defaults[1]),
        )
        for code, keys in THRESHOLD_KEYS.items()
        for defaults in (DEFAULT_THRESHOLDS[code],)
    }
    return TechnicalNotificationConfig(
        daily_enabled=_bool_value(session, DAILY_ENABLED_KEY, True),
        daily_time=daily_time,
        critical_enabled=_bool_value(session, CRITICAL_ENABLED_KEY, True),
        recovery_enabled=_bool_value(session, RECOVERY_ENABLED_KEY, True),
        cooldown_minutes=max(5, _int_value(session, COOLDOWN_KEY, 60)),
        thresholds=thresholds,
    )


def save_technical_notification_config(
    session: Session,
    config: TechnicalNotificationConfig,
    *,
    actor: str,
) -> None:
    values = {
        DAILY_ENABLED_KEY: str(config.daily_enabled).lower(),
        DAILY_TIME_KEY: config.daily_time.strftime("%H:%M"),
        CRITICAL_ENABLED_KEY: str(config.critical_enabled).lower(),
        RECOVERY_ENABLED_KEY: str(config.recovery_enabled).lower(),
        COOLDOWN_KEY: str(config.cooldown_minutes),
    }
    for code, thresholds in config.thresholds.items():
        keys = THRESHOLD_KEYS[code]
        values[keys[0]] = str(thresholds[0])
        values[keys[1]] = str(thresholds[1])
    for key, value in values.items():
        set_setting(session, key, value, secret=False, actor=actor)


def _metric(
    code: str,
    label: str,
    value: float | None,
    thresholds: tuple[float, float],
    recommendation: str,
) -> dict[str, object]:
    warning, critical = thresholds
    status = (
        "unknown"
        if value is None
        else "critical"
        if value >= critical
        else "warning"
        if value >= warning
        else "healthy"
    )
    return {
        "code": code,
        "label": label,
        "value": round(value, 2) if value is not None else None,
        "unit": "%",
        "warningThreshold": warning,
        "criticalThreshold": critical,
        "status": status,
        "recommendation": recommendation,
    }


def evaluate_technical_metrics(
    metrics: dict[str, Any],
    config: TechnicalNotificationConfig,
) -> list[dict[str, object]]:
    host = metrics.get("host") or {}
    database = metrics.get("database") or {}
    max_connections = float(database.get("maxConnections") or 0)
    current_connections = float(database.get("currentConnections") or 0)
    connection_percent = (
        current_connections / max_connections * 100 if max_connections else None
    )
    return [
        _metric(
            "cpu",
            "CPU load",
            host.get("cpuPercent"),
            config.thresholds["cpu"],
            "ตรวจ Process ที่ใช้ CPU สูงหรือเพิ่ม CPU เมื่อเกิดอย่างต่อเนื่อง",
        ),
        _metric(
            "memory",
            "RAM",
            host.get("memoryUsedPercent"),
            config.thresholds["memory"],
            "ตรวจ Memory ของ Container/Process และเตรียมเพิ่ม RAM",
        ),
        _metric(
            "disk",
            "Disk",
            host.get("diskUsedPercent"),
            config.thresholds["disk"],
            "ตรวจ Log/Backup/Database growth และเตรียมเพิ่มพื้นที่ Disk",
        ),
        _metric(
            "connections",
            "PostgreSQL connections",
            connection_percent,
            config.thresholds["connections"],
            "ตรวจ Connection leak หรือปรับ Pool/Max connections",
        ),
        _metric(
            "deadTuples",
            "PostgreSQL dead tuples",
            database.get("deadTupleRatio"),
            config.thresholds["deadTuples"],
            "ตรวจ Autovacuum และตารางที่มีการแก้ไขจำนวนมาก",
        ),
    ]


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=BANGKOK_TIMEZONE)
    return parsed.astimezone(BANGKOK_TIMEZONE)


def _load_alert_state(session: Session) -> dict[str, dict[str, object]]:
    try:
        state = json.loads(setting_value(session, ALERT_STATE_KEY) or "{}")
    except json.JSONDecodeError:
        return {}
    return state if isinstance(state, dict) else {}


def _save_delivery_audit(
    session: Session,
    *,
    action: str,
    delivery_status: str,
    details: dict[str, object],
) -> None:
    session.add(
        AuditEvent(
            entity_type="technical_notification",
            entity_id=action,
            action=action,
            actor="system-health-scheduler",
            before_json=None,
            after_json=json.dumps(
                {"deliveryStatus": delivery_status, **details},
                ensure_ascii=False,
            ),
        )
    )


def _daily_details(
    metrics: dict[str, Any],
    evaluated: list[dict[str, object]],
) -> list[str]:
    status = "ปกติ"
    if any(item["status"] == "critical" for item in evaluated):
        status = "วิกฤต"
    elif any(item["status"] in {"warning", "unknown"} for item in evaluated):
        status = "เฝ้าระวัง"
    values = " · ".join(
        f"{item['label']} "
        + (f"{item['value']:.1f}%" if item["value"] is not None else "ไม่พร้อมใช้งาน")
        for item in evaluated
    )
    database = metrics.get("database") or {}
    latest_date = metrics.get("latestDataDate") or "ยังไม่มีข้อมูล"
    heartbeat = metrics.get("workerHeartbeatAt") or "กำลังทำงาน"
    return [
        f"สถานะรวม: {status}",
        values,
        (
            "Database: "
            f"{float(database.get('databaseSizeBytes') or 0) / 1024 / 1024:.1f} MB · "
            f"Connections {database.get('currentConnections', 0)}/"
            f"{database.get('maxConnections', 0)}"
        ),
        f"ข้อมูลล่าสุด: {latest_date}",
        f"Worker heartbeat: {heartbeat}",
    ]


def process_technical_notifications(
    session: Session,
    *,
    now: datetime | None = None,
) -> int:
    current = (now or bangkok_now()).astimezone(BANGKOK_TIMEZONE)
    config = technical_notification_config(session)
    last_evaluated = _parse_datetime(setting_value(session, LAST_EVALUATED_KEY))
    if last_evaluated and current - last_evaluated < timedelta(minutes=5):
        return 0

    from app.services.monitoring import collect_monitoring_metrics

    metrics = collect_monitoring_metrics(session)
    evaluated = evaluate_technical_metrics(metrics, config)
    set_setting(
        session,
        LAST_EVALUATED_KEY,
        current.isoformat(),
        secret=False,
        actor="system-health-scheduler",
    )
    set_setting(
        session,
        WORKER_HEARTBEAT_KEY,
        current.isoformat(),
        secret=False,
        actor="system-health-scheduler",
    )
    metrics["workerHeartbeatAt"] = current.isoformat()
    deliveries = 0
    cooldown = timedelta(minutes=config.cooldown_minutes)

    scheduled_at = datetime.combine(
        current.date(),
        config.daily_time,
        tzinfo=BANGKOK_TIMEZONE,
    )
    last_daily_sent = setting_value(session, LAST_DAILY_SENT_KEY)
    last_daily_attempt = _parse_datetime(setting_value(session, LAST_DAILY_ATTEMPT_KEY))
    daily_due = (
        config.daily_enabled
        and current >= scheduled_at
        and last_daily_sent != current.date().isoformat()
        and (
            last_daily_attempt is None
            or current - last_daily_attempt >= cooldown
        )
    )
    if daily_due:
        delivery = send_telegram(
            session,
            "🩺 MT Pulse · Daily Technical Health",
            _daily_details(metrics, evaluated),
            force=True,
        )
        set_setting(
            session,
            LAST_DAILY_ATTEMPT_KEY,
            current.isoformat(),
            secret=False,
            actor="system-health-scheduler",
        )
        if delivery.status == "sent":
            set_setting(
                session,
                LAST_DAILY_SENT_KEY,
                current.date().isoformat(),
                secret=False,
                actor="system-health-scheduler",
            )
            deliveries += 1
        _save_delivery_audit(
            session,
            action="daily_health",
            delivery_status=delivery.status,
            details={"date": current.date().isoformat()},
        )

    state = _load_alert_state(session)
    critical_due: list[dict[str, object]] = []
    recovery_due: list[dict[str, object]] = []
    for item in evaluated:
        code = str(item["code"])
        item_state = state.get(code, {})
        was_active = bool(item_state.get("active"))
        last_attempt = _parse_datetime(str(item_state.get("lastAttemptAt") or ""))
        is_critical = item["status"] == "critical"
        if is_critical and config.critical_enabled:
            if not was_active or last_attempt is None or current - last_attempt >= cooldown:
                critical_due.append(item)
            item_state["active"] = True
        elif not is_critical and was_active and config.recovery_enabled:
            recovery_due.append(item)
        elif not is_critical:
            item_state["active"] = False
        state[code] = item_state

    if critical_due:
        delivery = send_telegram(
            session,
            "🚨 MT Pulse · Technical Critical",
            [
                f"{item['label']}: {item['value']:.1f}% "
                f"(Critical ≥ {item['criticalThreshold']:.1f}%) · "
                f"{item['recommendation']}"
                for item in critical_due
            ],
            force=True,
        )
        for item in critical_due:
            state[str(item["code"])]["lastAttemptAt"] = current.isoformat()
        if delivery.status == "sent":
            deliveries += 1
        _save_delivery_audit(
            session,
            action="critical_health",
            delivery_status=delivery.status,
            details={"metrics": [item["code"] for item in critical_due]},
        )

    if recovery_due:
        delivery = send_telegram(
            session,
            "✅ MT Pulse · Technical Recovery",
            [f"{item['label']}: กลับสู่ระดับปกติ/เฝ้าระวังแล้ว" for item in recovery_due],
            force=True,
        )
        if delivery.status == "sent":
            for item in recovery_due:
                state[str(item["code"])]["active"] = False
            deliveries += 1
        _save_delivery_audit(
            session,
            action="recovery_health",
            delivery_status=delivery.status,
            details={"metrics": [item["code"] for item in recovery_due]},
        )

    set_setting(
        session,
        ALERT_STATE_KEY,
        json.dumps(state),
        secret=False,
        actor="system-health-scheduler",
    )
    session.commit()
    return deliveries
