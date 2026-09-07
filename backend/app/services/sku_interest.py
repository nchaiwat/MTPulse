from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.importers.twd import TwdExtract
from app.local_time import bangkok_now
from app.models import AuditEvent, SkuInterest

STORED_STATUSES = {"active", "pending"}


@dataclass(frozen=True)
class SkuInterestSync:
    stored_skus: frozenset[str]
    new_pending_skus: tuple[str, ...]
    new_ignored_skus: tuple[str, ...]


def sync_sku_interests(
    session: Session,
    modern_trade_id: int,
    extract: TwdExtract,
    *,
    baseline: bool,
) -> SkuInterestSync:
    descriptions: dict[str, str | None] = {}
    for row in extract.rows:
        if row.sku not in descriptions or not descriptions[row.sku]:
            descriptions[row.sku] = row.description
    source_skus = tuple(descriptions)
    existing = (
        {
            row.source_sku: row
            for row in session.scalars(
                select(SkuInterest).where(
                    SkuInterest.modern_trade_id == modern_trade_id,
                    SkuInterest.source_sku.in_(source_skus),
                )
            )
        }
        if source_skus
        else {}
    )
    now = bangkok_now()
    new_pending: list[str] = []
    new_ignored: list[str] = []
    for source_sku, description in descriptions.items():
        interest = existing.get(source_sku)
        if interest is None:
            status = "ignored" if baseline else "pending"
            interest = SkuInterest(
                modern_trade_id=modern_trade_id,
                source_sku=source_sku,
                source_description=description,
                status=status,
                first_seen_date=extract.data_date,
                last_seen_date=extract.data_date,
                first_seen_at=now,
                last_seen_at=now,
                decided_by="system:initial-scan" if baseline else None,
                decided_at=now if baseline else None,
            )
            session.add(interest)
            existing[source_sku] = interest
            (new_ignored if baseline else new_pending).append(source_sku)
        else:
            interest.last_seen_date = max(interest.last_seen_date, extract.data_date)
            interest.first_seen_date = min(interest.first_seen_date, extract.data_date)
            interest.last_seen_at = now
            if description and not interest.source_description:
                interest.source_description = description
    return SkuInterestSync(
        stored_skus=frozenset(
            source_sku
            for source_sku, interest in existing.items()
            if interest.status in STORED_STATUSES
        ),
        new_pending_skus=tuple(sorted(new_pending)),
        new_ignored_skus=tuple(sorted(new_ignored)),
    )


def decide_sku_interest(
    session: Session,
    interest: SkuInterest,
    *,
    decision: str,
    actor: str,
) -> SkuInterest:
    before_status = interest.status
    if decision == "accept":
        interest.status = "active"
    elif decision == "ignore":
        interest.status = "ignored"
    else:
        raise ValueError("decision ต้องเป็น accept หรือ ignore")
    interest.decided_by = actor
    interest.decided_at = bangkok_now()
    session.add(
        AuditEvent(
            entity_type="sku_interest",
            entity_id=f"{interest.modern_trade_id}:{interest.source_sku}",
            action=decision,
            actor=actor,
            before_json=json.dumps({"status": before_status}),
            after_json=json.dumps({"status": interest.status}),
        )
    )
    session.commit()
    session.refresh(interest)
    return interest


def activate_mapped_sku_interest(
    session: Session,
    *,
    modern_trade_id: int,
    source_sku: str,
    source_description: str | None,
    effective_from: date,
    actor: str,
) -> SkuInterest:
    interest = session.scalar(
        select(SkuInterest).where(
            SkuInterest.modern_trade_id == modern_trade_id,
            SkuInterest.source_sku == source_sku,
        )
    )
    now = bangkok_now()
    if interest is None:
        interest = SkuInterest(
            modern_trade_id=modern_trade_id,
            source_sku=source_sku,
            source_description=source_description,
            status="active",
            first_seen_date=effective_from,
            last_seen_date=effective_from,
            first_seen_at=now,
            last_seen_at=now,
            decided_by=actor,
            decided_at=now,
        )
        session.add(interest)
        before = None
    elif interest.status != "active":
        before = {"status": interest.status}
        interest.status = "active"
        interest.decided_by = actor
        interest.decided_at = now
        if source_description and not interest.source_description:
            interest.source_description = source_description
    else:
        return interest
    session.add(
        AuditEvent(
            entity_type="sku_interest",
            entity_id=f"{modern_trade_id}:{source_sku}",
            action="activate_from_confirmed_mapping",
            actor=actor,
            before_json=json.dumps(before) if before else None,
            after_json=json.dumps({"status": "active"}, ensure_ascii=False),
        )
    )
    return interest
