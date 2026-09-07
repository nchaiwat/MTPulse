from datetime import datetime
from itertools import count

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api import system_settings
from app.database import Base
from app.local_time import BANGKOK_TIMEZONE
from app.models import AuditEvent, SystemSetting
from app.services import monitoring, technical_health
from app.services.technical_health import process_technical_notifications


def _metrics(cpu_percent: float = 20) -> dict:
    return {
        "host": {
            "cpuPercent": cpu_percent,
            "memoryUsedPercent": 30,
            "diskUsedPercent": 40,
        },
        "database": {
            "databaseSizeBytes": 100 * 1024 * 1024,
            "currentConnections": 4,
            "maxConnections": 100,
            "deadTupleRatio": 1,
        },
        "latestDataDate": "2026-09-04",
        "workerHeartbeatAt": "2026-09-05T07:00:00+07:00",
    }


def test_daily_critical_cooldown_and_recovery_are_persisted(monkeypatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    current_metrics = _metrics()
    deliveries: list[tuple[str, list[str]]] = []
    audit_ids = count(1)

    monkeypatch.setattr(
        monitoring,
        "collect_monitoring_metrics",
        lambda session: current_metrics,
    )
    monkeypatch.setattr(
        technical_health,
        "AuditEvent",
        lambda **values: AuditEvent(id=next(audit_ids), **values),
    )

    def capture_delivery(session, title, details, **kwargs):
        deliveries.append((title, list(details)))
        return type("Delivery", (), {"status": "sent", "message": "sent"})()

    monkeypatch.setattr(technical_health, "send_telegram", capture_delivery)

    def at(hour: int, minute: int) -> datetime:
        return datetime(2026, 9, 5, hour, minute, tzinfo=BANGKOK_TIMEZONE)

    with Session(engine) as session:
        assert process_technical_notifications(session, now=at(7, 0)) == 1
        assert process_technical_notifications(session, now=at(7, 2)) == 0

        current_metrics["host"]["cpuPercent"] = 99
        assert process_technical_notifications(session, now=at(7, 5)) == 1
        assert process_technical_notifications(session, now=at(7, 30)) == 0
        assert process_technical_notifications(session, now=at(8, 6)) == 1

        current_metrics["host"]["cpuPercent"] = 20
        assert process_technical_notifications(session, now=at(8, 11)) == 1

    assert [title for title, _ in deliveries] == [
        "🩺 MT Pulse · Daily Technical Health",
        "🚨 MT Pulse · Technical Critical",
        "🚨 MT Pulse · Technical Critical",
        "✅ MT Pulse · Technical Recovery",
    ]
    assert any("CPU load 20.0%" in detail for detail in deliveries[0][1])
    assert "CPU load" in deliveries[1][1][0]


def test_unavailable_metric_is_unknown_not_healthy() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        config = technical_health.technical_notification_config(session)

    evaluated = technical_health.evaluate_technical_metrics(
        {
            "host": {
                "cpuPercent": None,
                "memoryUsedPercent": 10,
                "diskUsedPercent": 10,
            },
            "database": {
                "currentConnections": 0,
                "maxConnections": 100,
                "deadTupleRatio": 0,
            },
        },
        config,
    )

    cpu = next(item for item in evaluated if item["code"] == "cpu")
    assert cpu["status"] == "unknown"


def test_manual_health_sends_fresh_report_without_changing_scheduler_state(
    monkeypatch,
) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    audit_ids = count(1)
    deliveries: list[str] = []
    monkeypatch.setattr(
        monitoring,
        "collect_monitoring_metrics",
        lambda session: _metrics(),
    )
    monkeypatch.setattr(
        technical_health,
        "AuditEvent",
        lambda **values: AuditEvent(id=next(audit_ids), **values),
    )
    monkeypatch.setattr(
        technical_health,
        "send_telegram",
        lambda session, title, details, **kwargs: (
            deliveries.append(title)
            or type("Delivery", (), {"status": "sent", "message": "sent"})()
        ),
    )
    protected = {
        technical_health.LAST_DAILY_SENT_KEY: "2026-09-07",
        technical_health.LAST_DAILY_ATTEMPT_KEY: "2026-09-07T07:00:00+07:00",
        technical_health.ALERT_STATE_KEY: '{"cpu":{"active":true}}',
    }
    with Session(engine) as session:
        session.add_all(
            [
                SystemSetting(
                    key=key,
                    value=value,
                    is_secret=False,
                    updated_by="test",
                )
                for key, value in protected.items()
            ]
        )
        session.commit()
        result = technical_health.send_manual_technical_health(
            session,
            actor="admin",
            now=datetime(2026, 9, 7, 9, 30, tzinfo=BANGKOK_TIMEZONE),
        )
        after = {
            key: session.get(SystemSetting, key).value
            for key in protected
        }
        audit = session.query(AuditEvent).one()

    assert result["status"] == "sent"
    assert result["overallStatus"] == "healthy"
    assert deliveries == ["🩺 MT Pulse · Technical Health (ตรวจทันที)"]
    assert after == protected
    assert audit.action == "manual_health"
    assert audit.actor == "admin"


def test_system_settings_persist_daily_time_and_thresholds(monkeypatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    audit_ids = count(1)
    monkeypatch.setattr(
        system_settings,
        "AuditEvent",
        lambda **values: AuditEvent(id=next(audit_ids), **values),
    )
    update = system_settings.TechnicalNotificationSettingsUpdate.model_validate(
        {
            "daily_enabled": True,
            "daily_time": "07:30",
            "critical_enabled": True,
            "recovery_enabled": True,
            "cooldown_minutes": 90,
            "thresholds": {
                "cpu": {"warning": 75, "critical": 92},
                "memory": {"warning": 76, "critical": 91},
                "disk": {"warning": 77, "critical": 90},
                "connections": {"warning": 78, "critical": 94},
                "deadTuples": {"warning": 8, "critical": 18},
            },
        }
    )

    with Session(engine) as session:
        response = system_settings.update_technical_notification_settings(
            update,
            session,
        )
        reloaded = system_settings.get_technical_notification_settings(session)

    assert response == reloaded
    assert reloaded["dailyTime"] == "07:30"
    assert reloaded["cooldownMinutes"] == 90
    assert reloaded["thresholds"]["cpu"] == {
        "warning": 75.0,
        "critical": 92.0,
    }


def test_system_settings_reject_warning_not_below_critical() -> None:
    with pytest.raises(ValidationError, match="Warning ต้องน้อยกว่า Critical"):
        system_settings.TechnicalThresholdUpdate(warning=90, critical=90)
