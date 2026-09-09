from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.local_time import bangkok_now
from app.models import ImportBatch, ModernTrade, MonitoringSnapshot
from app.services.technical_health import (
    WORKER_HEARTBEAT_KEY,
    evaluate_technical_metrics,
    technical_notification_config,
)
from app.services.telegram import setting_value

STATUS_RANK = {"healthy": 0, "warning": 1, "critical": 2}


def _host_metrics() -> dict[str, object]:
    cpu_percent: float | None = None
    memory_total: int | None = None
    memory_available: int | None = None
    uptime_seconds: int | None = None
    try:
        load_one = float(os.getloadavg()[0])
        cpu_count = os.cpu_count() or 1
        cpu_percent = round(min(load_one / cpu_count * 100, 100), 2)
    except (AttributeError, OSError):
        pass
    try:
        memory_values: dict[str, int] = {}
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            key, value = line.split(":", 1)
            memory_values[key] = int(value.strip().split()[0]) * 1024
        memory_total = memory_values.get("MemTotal")
        memory_available = memory_values.get("MemAvailable")
    except (OSError, ValueError, IndexError):
        pass
    try:
        uptime_seconds = int(
            float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0])
        )
    except (OSError, ValueError, IndexError):
        pass
    try:
        disk = shutil.disk_usage("/")
        disk_total = int(disk.total)
        disk_free = int(disk.free)
        disk_used_percent = round((disk_total - disk_free) / disk_total * 100, 2)
    except (OSError, ZeroDivisionError):
        disk_total = None
        disk_free = None
        disk_used_percent = None
    memory_used_percent = (
        round((memory_total - memory_available) / memory_total * 100, 2)
        if memory_total and memory_available is not None
        else None
    )
    return {
        "cpuPercent": cpu_percent,
        "memoryUsedPercent": memory_used_percent,
        "memoryTotalBytes": memory_total,
        "memoryAvailableBytes": memory_available,
        "diskUsedPercent": disk_used_percent,
        "diskTotalBytes": disk_total,
        "diskFreeBytes": disk_free,
        "uptimeSeconds": uptime_seconds,
    }


def _iso(value: object) -> str | None:
    return value.isoformat() if value is not None else None


def _warning_count(batch: ImportBatch | None) -> int:
    if batch is None or not batch.reconciliation_errors:
        return 0
    return len([line for line in batch.reconciliation_errors.splitlines() if line.strip()])


def _warning_details(batch: ImportBatch | None) -> str:
    if batch is None or not batch.reconciliation_errors:
        return ""
    lines = [line.strip() for line in batch.reconciliation_errors.splitlines() if line.strip()]
    return " · ".join(lines[:3])[:500]


def _overall_status(notices: list[dict[str, object]]) -> str:
    return max(
        (notice["level"] for notice in notices),
        key=lambda level: STATUS_RANK[str(level)],
        default="healthy",
    )


def _slow_queries(session: Session) -> tuple[bool, list[dict[str, object]]]:
    try:
        with session.begin_nested():
            rows = session.execute(
                text(
                    """
                    SELECT query, calls, mean_exec_time, total_exec_time, rows
                    FROM pg_stat_statements
                    WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
                      AND query NOT ILIKE '%pg_stat_statements%'
                    ORDER BY total_exec_time DESC
                    LIMIT 10
                    """
                )
            ).mappings().all()
    except SQLAlchemyError:
        return False, []
    return True, [
        {
            "query": " ".join(str(row["query"]).split())[:500],
            "calls": int(row["calls"] or 0),
            "meanTimeMs": round(float(row["mean_exec_time"] or 0), 3),
            "totalTimeMs": round(float(row["total_exec_time"] or 0), 3),
            "rows": int(row["rows"] or 0),
        }
        for row in rows
    ]


def collect_monitoring_metrics(session: Session) -> dict[str, object]:
    now = bangkok_now()
    fact_count = int(
        session.scalar(select(func.coalesce(func.sum(ImportBatch.row_count), 0))) or 0
    )
    sizes = session.execute(
        text(
            """
            SELECT
                pg_database_size(current_database()) AS database_size_bytes,
                pg_relation_size('sales_inventory_facts') AS fact_table_size_bytes,
                pg_indexes_size('sales_inventory_facts') AS fact_indexes_size_bytes
            """
        )
    ).mappings().one()
    table_stats = session.execute(
        text(
            """
            SELECT n_live_tup, n_dead_tup,
                   COALESCE(last_autovacuum, last_vacuum) AS last_vacuum_at,
                   COALESCE(last_autoanalyze, last_analyze) AS last_analyze_at
            FROM pg_stat_user_tables
            WHERE relname = 'sales_inventory_facts'
            """
        )
    ).mappings().one()
    connections = session.execute(
        text(
            """
            SELECT
                COUNT(*) FILTER (WHERE datname = current_database()) AS current_connections,
                current_setting('max_connections')::int AS max_connections
            FROM pg_stat_activity
            """
        )
    ).mappings().one()
    latest_batch = session.scalar(
        select(ImportBatch)
        .order_by(ImportBatch.finished_at.desc().nullslast(), ImportBatch.id.desc())
        .limit(1)
    )
    unresolved_warning_batches = session.scalars(
        select(ImportBatch)
        .where(
            ImportBatch.status == "imported_with_warnings",
            ImportBatch.warning_resolution.is_(None),
        )
        .order_by(ImportBatch.data_date.desc(), ImportBatch.id.desc())
        .limit(20)
    ).all()
    latest_data_date = session.scalar(select(func.max(ImportBatch.data_date)))
    modern_trade_rows = session.execute(
        select(
            ModernTrade.code,
            ModernTrade.name,
            func.max(ImportBatch.data_date).label("latest_data_date"),
        )
        .outerjoin(ImportBatch, ImportBatch.modern_trade_id == ModernTrade.id)
        .group_by(ModernTrade.code, ModernTrade.name)
        .order_by(ModernTrade.code)
    ).all()
    pg_stat_available, slow_queries = _slow_queries(session)

    live_tuples = int(table_stats["n_live_tup"] or 0)
    dead_tuples = int(table_stats["n_dead_tup"] or 0)
    tuple_total = live_tuples + dead_tuples
    dead_tuple_ratio = (dead_tuples / tuple_total * 100) if tuple_total else 0.0
    current_connections = int(connections["current_connections"] or 0)
    max_connections = int(connections["max_connections"] or 0)
    warning_count = _warning_count(latest_batch)
    notices: list[dict[str, object]] = []

    if latest_data_date is None:
        notices.append(
            {"level": "warning", "title": "ยังไม่มีข้อมูล", "detail": "ยังไม่พบ Import ที่สำเร็จ"}
        )
    elif (now.date() - latest_data_date).days > 2:
        notices.append(
            {
                "code": "data_delayed",
                "level": "warning",
                "title": "วันที่ข้อมูลล่าช้า",
                "detail": f"ข้อมูลล่าสุดคือ {latest_data_date:%d/%m/%Y}",
            }
        )
    for warning_batch in unresolved_warning_batches:
        batch_warning_count = _warning_count(warning_batch)
        notices.append(
            {
                "code": "import_warning",
                "batchId": warning_batch.id,
                "level": "warning",
                "title": (
                    f"Import Batch {warning_batch.id} "
                    f"มีคำเตือน {batch_warning_count} รายการ"
                ),
                "detail": _warning_details(warning_batch) or "ไม่พบรายละเอียดคำเตือน",
            }
        )
    if not pg_stat_available:
        notices.append(
            {
                "level": "warning",
                "title": "ยังไม่มี Query statistics",
                "detail": "pg_stat_statements ยังไม่พร้อมใช้งาน",
            }
        )

    modern_trades = [
        {
            "code": row.code,
            "name": row.name,
            "latestDataDate": _iso(row.latest_data_date),
            "lagDays": (
                (now.date() - row.latest_data_date).days
                if row.latest_data_date is not None
                else None
            ),
        }
        for row in modern_trade_rows
    ]
    host = _host_metrics()
    worker_heartbeat = setting_value(session, WORKER_HEARTBEAT_KEY)
    database = {
        "status": "healthy",
        "factCount": fact_count,
        "databaseSizeBytes": int(sizes["database_size_bytes"] or 0),
        "factTableSizeBytes": int(sizes["fact_table_size_bytes"] or 0),
        "factIndexesSizeBytes": int(sizes["fact_indexes_size_bytes"] or 0),
        "deadTupleCount": dead_tuples,
        "deadTupleRatio": round(dead_tuple_ratio, 4),
        "currentConnections": current_connections,
        "maxConnections": max_connections,
        "lastVacuumAt": _iso(table_stats["last_vacuum_at"]),
        "lastAnalyzeAt": _iso(table_stats["last_analyze_at"]),
    }
    technical_metrics = evaluate_technical_metrics(
        {"host": host, "database": database},
        technical_notification_config(session),
    )
    for item in technical_metrics:
        if item["status"] == "healthy":
            continue
        level = "warning" if item["status"] == "unknown" else item["status"]
        value = (
            "ไม่พร้อมใช้งาน"
            if item["value"] is None
            else f"{item['value']:.2f}%"
        )
        notices.append(
            {
                "code": f"technical_{item['code']}",
                "level": level,
                "title": f"{item['label']} {value}",
                "detail": item["recommendation"],
            }
        )
    host_statuses = [
        str(item["status"])
        for item in technical_metrics
        if item["code"] in {"cpu", "memory", "disk"}
    ]
    host["status"] = (
        "critical"
        if "critical" in host_statuses
        else "warning"
        if any(status in {"warning", "unknown"} for status in host_statuses)
        else "healthy"
    )
    database_statuses = [
        str(item["status"])
        for item in technical_metrics
        if item["code"] in {"connections", "deadTuples"}
    ]
    database["status"] = (
        "critical"
        if "critical" in database_statuses
        else "warning"
        if any(status in {"warning", "unknown"} for status in database_statuses)
        else "healthy"
    )
    return {
        "capturedAt": now.isoformat(),
        "overallStatus": _overall_status(notices),
        "notices": notices,
        "api": {"status": "healthy"},
        "host": host,
        "database": database,
        "workerHeartbeatAt": worker_heartbeat,
        "technicalMetrics": technical_metrics,
        "latestDataDate": _iso(latest_data_date),
        "latestImport": (
            {
                "batchId": latest_batch.id,
                "dataDate": latest_batch.data_date.isoformat(),
                "status": latest_batch.status,
                "finishedAt": _iso(latest_batch.finished_at),
                "rowCount": latest_batch.row_count,
                "warningCount": warning_count,
                "warningResolution": latest_batch.warning_resolution,
            }
            if latest_batch
            else None
        ),
        "modernTrades": modern_trades,
        "pgStatStatementsAvailable": pg_stat_available,
        "slowQueries": slow_queries,
    }


def capture_monitoring_snapshot(
    session: Session,
    *,
    trigger: str,
    upsert_today: bool,
) -> dict[str, object]:
    metrics = collect_monitoring_metrics(session)
    snapshot_date = bangkok_now().date()
    snapshot = session.scalar(
        select(MonitoringSnapshot).where(MonitoringSnapshot.snapshot_date == snapshot_date)
    )
    if snapshot is None:
        snapshot = MonitoringSnapshot(snapshot_date=snapshot_date)
        session.add(snapshot)
    elif not upsert_today:
        return metrics

    database = metrics["database"]
    host = metrics["host"]
    latest_import = metrics["latestImport"]
    assert isinstance(database, dict)
    assert isinstance(host, dict)
    assert latest_import is None or isinstance(latest_import, dict)
    snapshot.captured_at = datetime.fromisoformat(str(metrics["capturedAt"]))
    snapshot.trigger = trigger
    snapshot.overall_status = str(metrics["overallStatus"])
    snapshot.fact_count = int(database["factCount"])
    snapshot.database_size_bytes = int(database["databaseSizeBytes"])
    snapshot.fact_table_size_bytes = int(database["factTableSizeBytes"])
    snapshot.fact_indexes_size_bytes = int(database["factIndexesSizeBytes"])
    snapshot.dead_tuple_count = int(database["deadTupleCount"])
    snapshot.dead_tuple_ratio = Decimal(str(database["deadTupleRatio"]))
    snapshot.active_connections = int(database["currentConnections"])
    snapshot.max_connections = int(database["maxConnections"])
    snapshot.latest_data_date = (
        datetime.fromisoformat(str(metrics["latestDataDate"])).date()
        if metrics["latestDataDate"]
        else None
    )
    snapshot.latest_import_status = str(latest_import["status"]) if latest_import else None
    snapshot.warning_count = len(metrics["notices"])
    snapshot.last_vacuum_at = (
        datetime.fromisoformat(str(database["lastVacuumAt"]))
        if database["lastVacuumAt"]
        else None
    )
    snapshot.last_analyze_at = (
        datetime.fromisoformat(str(database["lastAnalyzeAt"]))
        if database["lastAnalyzeAt"]
        else None
    )
    snapshot.modern_trades_json = json.dumps(metrics["modernTrades"], ensure_ascii=False)
    snapshot.slow_queries_json = json.dumps(metrics["slowQueries"], ensure_ascii=False)
    snapshot.host_cpu_percent = host["cpuPercent"]
    snapshot.host_memory_used_percent = host["memoryUsedPercent"]
    snapshot.host_memory_total_bytes = host["memoryTotalBytes"]
    snapshot.host_disk_used_percent = host["diskUsedPercent"]
    snapshot.host_disk_total_bytes = host["diskTotalBytes"]
    snapshot.host_uptime_seconds = host["uptimeSeconds"]
    snapshot.worker_heartbeat_at = (
        datetime.fromisoformat(str(metrics["workerHeartbeatAt"]))
        if metrics["workerHeartbeatAt"]
        else None
    )
    try:
        session.flush()
        session.execute(
            delete(MonitoringSnapshot).where(
                MonitoringSnapshot.snapshot_date < snapshot_date - timedelta(days=364)
            )
        )
        session.commit()
    except IntegrityError:
        session.rollback()
        concurrent_snapshot = session.scalar(
            select(MonitoringSnapshot).where(
                MonitoringSnapshot.snapshot_date == snapshot_date
            )
        )
        if concurrent_snapshot is None:
            raise
    return metrics


def monitoring_history(session: Session) -> list[dict[str, object]]:
    snapshots = session.scalars(
        select(MonitoringSnapshot)
        .order_by(MonitoringSnapshot.snapshot_date.desc())
        .limit(365)
    ).all()
    return [
        {
            "date": snapshot.snapshot_date.isoformat(),
            "capturedAt": snapshot.captured_at.isoformat(),
            "trigger": snapshot.trigger,
            "status": snapshot.overall_status,
            "factCount": snapshot.fact_count,
            "databaseSizeBytes": snapshot.database_size_bytes,
            "deadTupleRatio": float(snapshot.dead_tuple_ratio),
            "connections": snapshot.active_connections,
            "latestDataDate": _iso(snapshot.latest_data_date),
            "warningCount": snapshot.warning_count,
            "hostCpuPercent": (
                float(snapshot.host_cpu_percent)
                if snapshot.host_cpu_percent is not None
                else None
            ),
            "hostMemoryUsedPercent": (
                float(snapshot.host_memory_used_percent)
                if snapshot.host_memory_used_percent is not None
                else None
            ),
            "hostDiskUsedPercent": (
                float(snapshot.host_disk_used_percent)
                if snapshot.host_disk_used_percent is not None
                else None
            ),
        }
        for snapshot in snapshots
    ]
