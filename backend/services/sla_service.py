from datetime import datetime, timedelta, timezone

from backend.services.scoring_config import SLA_HOURS


def compute_sla_deadline(severity: str, created_at: datetime | None = None) -> datetime:
    if created_at is None:
        created_at = datetime.now(timezone.utc)
    hours = SLA_HOURS.get(severity.lower(), 720)
    return created_at + timedelta(hours=hours)


def sla_hours_remaining(deadline: datetime) -> float:
    now = datetime.now(timezone.utc)
    delta = deadline - now
    return max(0, delta.total_seconds() / 3600)


def is_sla_breached(deadline: datetime) -> bool:
    return datetime.now(timezone.utc) > deadline
