from __future__ import annotations

import json
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent, ImportBatch, ModernTrade, SystemSetting
from app.sales_grain import SALES_GRAIN_DAILY
from app.services.telegram import set_setting, setting_value

ACTIVE_CUTOFF_KEY = "sale_out_active_common_cutoff"
CUTOFF_FROZEN_KEY = "sale_out_common_cutoff_frozen"
AUTO_ADVANCE_KEY = "sale_out_common_cutoff_auto_advance"
AVAILABLE_BATCH_STATUSES = ("imported", "imported_with_warnings")


@dataclass(frozen=True)
class SaleOutMemberCoverage:
    code: str
    start_date: date
    covered_through: date | None
    latest_source_date: date | None
    blocking_date: date | None


@dataclass(frozen=True)
class CommonCutoffEvaluation:
    active_date: date | None
    candidate_date: date | None
    frozen: bool
    auto_advance_enabled: bool
    advanced: bool
    members: tuple[SaleOutMemberCoverage, ...]


def comparison_period_end(cutoff: date, target_year: int) -> date:
    day = min(cutoff.day, monthrange(target_year, cutoff.month)[1])
    return date(target_year, cutoff.month, day)


def growth_percent(current: Decimal, base: Decimal) -> Decimal | None:
    if base == 0:
        return None
    return (current - base) / base * Decimal("100")


def average_price(amount: Decimal, quantity: Decimal) -> Decimal | None:
    if quantity == 0:
        return None
    return amount / quantity


def _date_setting(session: Session, key: str) -> date | None:
    value = setting_value(session, key)
    return date.fromisoformat(value) if value else None


def _bool_setting(session: Session, key: str, *, default: bool = False) -> bool:
    value = setting_value(session, key)
    return default if value is None else value == "true"


def _member_coverage(session: Session, modern_trade: ModernTrade) -> SaleOutMemberCoverage:
    assert modern_trade.sale_out_start_date is not None
    batches = session.scalars(
        select(ImportBatch)
        .where(
            ImportBatch.modern_trade_id == modern_trade.id,
            ImportBatch.data_date >= modern_trade.sale_out_start_date,
        )
        .order_by(ImportBatch.data_date)
    ).all()
    latest_source_date = max((batch.data_date for batch in batches), default=None)
    valid_daily_dates = {
        batch.data_date
        for batch in batches
        if batch.status in AVAILABLE_BATCH_STATUSES
        and batch.sales_grain == SALES_GRAIN_DAILY
        and (
            not batch.reconciliation_errors
            or batch.warning_resolution == "acknowledged"
        )
    }
    expected = modern_trade.sale_out_start_date
    covered_through: date | None = None
    while expected in valid_daily_dates:
        covered_through = expected
        expected += timedelta(days=1)
    blocking_date = expected if latest_source_date and expected <= latest_source_date else None
    return SaleOutMemberCoverage(
        code=modern_trade.code,
        start_date=modern_trade.sale_out_start_date,
        covered_through=covered_through,
        latest_source_date=latest_source_date,
        blocking_date=blocking_date,
    )


def evaluate_common_cutoff(session: Session) -> CommonCutoffEvaluation:
    modern_trades = session.scalars(
        select(ModernTrade)
        .where(
            ModernTrade.sale_out_include_in_total.is_(True),
            ModernTrade.sale_out_start_date.is_not(None),
        )
        .order_by(ModernTrade.code)
    ).all()
    members = tuple(_member_coverage(session, modern_trade) for modern_trade in modern_trades)
    covered_dates = [member.covered_through for member in members]
    candidate = min(covered_dates) if covered_dates and all(covered_dates) else None
    return CommonCutoffEvaluation(
        active_date=_date_setting(session, ACTIVE_CUTOFF_KEY),
        candidate_date=candidate,
        frozen=_bool_setting(session, CUTOFF_FROZEN_KEY),
        auto_advance_enabled=_bool_setting(session, AUTO_ADVANCE_KEY, default=True),
        advanced=False,
        members=members,
    )


def refresh_common_cutoff(session: Session, *, actor: str) -> CommonCutoffEvaluation:
    session.scalar(
        select(SystemSetting)
        .where(SystemSetting.key == ACTIVE_CUTOFF_KEY)
        .with_for_update()
    )
    evaluation = evaluate_common_cutoff(session)
    should_advance = (
        not evaluation.frozen
        and evaluation.auto_advance_enabled
        and evaluation.candidate_date is not None
        and (
            evaluation.active_date is None
            or evaluation.candidate_date > evaluation.active_date
        )
    )
    if not should_advance:
        return evaluation
    new_active = evaluation.candidate_date
    set_setting(
        session,
        ACTIVE_CUTOFF_KEY,
        new_active.isoformat(),
        secret=False,
        actor=actor,
    )
    session.add(
        AuditEvent(
            entity_type="system_setting",
            entity_id="sale_out_common_cutoff",
            action="advance",
            actor=actor,
            before_json=json.dumps(
                {"active_date": evaluation.active_date.isoformat()}
                if evaluation.active_date
                else {"active_date": None}
            ),
            after_json=json.dumps({"active_date": new_active.isoformat()}),
        )
    )
    session.commit()
    return CommonCutoffEvaluation(
        active_date=new_active,
        candidate_date=evaluation.candidate_date,
        frozen=False,
        auto_advance_enabled=True,
        advanced=True,
        members=evaluation.members,
    )


def set_cutoff_frozen(session: Session, *, frozen: bool, actor: str) -> bool:
    before = _bool_setting(session, CUTOFF_FROZEN_KEY)
    if before == frozen:
        return frozen
    set_setting(
        session,
        CUTOFF_FROZEN_KEY,
        "true" if frozen else "false",
        secret=False,
        actor=actor,
    )
    session.add(
        AuditEvent(
            entity_type="system_setting",
            entity_id="sale_out_common_cutoff",
            action="freeze" if frozen else "unfreeze",
            actor=actor,
            before_json=json.dumps({"frozen": before}),
            after_json=json.dumps({"frozen": frozen}),
        )
    )
    session.commit()
    return frozen


def set_cutoff_auto_advance(session: Session, *, enabled: bool, actor: str) -> bool:
    before = _bool_setting(session, AUTO_ADVANCE_KEY, default=True)
    if before == enabled:
        return enabled
    set_setting(
        session,
        AUTO_ADVANCE_KEY,
        "true" if enabled else "false",
        secret=False,
        actor=actor,
    )
    session.add(
        AuditEvent(
            entity_type="system_setting",
            entity_id="sale_out_common_cutoff",
            action="enable_auto_advance" if enabled else "disable_auto_advance",
            actor=actor,
            before_json=json.dumps({"auto_advance_enabled": before}),
            after_json=json.dumps({"auto_advance_enabled": enabled}),
        )
    )
    session.commit()
    return enabled
