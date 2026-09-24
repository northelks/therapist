from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from welcome.models import HIRED, NEEDS_REVIEW, SENDING, Hire, now, stamp
from welcome.sent_log import SentLog

LATE = timedelta(hours=1)


@dataclass(frozen=True)
class Alert:
    level: str
    text: str

    def __str__(self) -> str:
        return f"[{self.level}] {self.text}"


def late(rows: list[Hire], at: datetime, limit: timedelta = LATE) -> list[Hire]:
    out = []
    for hire in rows:
        if hire.status != HIRED or hire.welcomed:
            continue
        since = hire.waiting_since()
        if since is not None and at - since > limit:
            out.append(hire)
    return out


def undated(rows: list[Hire]) -> list[Hire]:
    return [h for h in rows if h.status == HIRED and not h.welcomed and not h.waiting_since()]


def held(rows: list[Hire]) -> list[Hire]:
    return [h for h in rows if h.status == NEEDS_REVIEW]


def stuck_claims(rows: list[Hire]) -> list[Hire]:
    return [h for h in rows if h.status == SENDING]


def drift(rows: list[Hire], log: SentLog, at: datetime, days: int = 7) -> tuple[int, int]:
    start, end = stamp(at - timedelta(days=days)), stamp(at - timedelta(days=1))
    hires = [h for h in rows if h.hired_at and start <= h.hired_at <= end]
    return len(hires), sum(1 for h in hires if log.already_sent(h.hire_id) or h.welcomed)


def check(rows: list[Hire], log: SentLog, at: datetime | None = None) -> list[Alert]:
    at = at or now()
    alerts: list[Alert] = []

    for hire in late(rows, at):
        alerts.append(Alert("page", f"{hire.hire_id} has been Hired since {hire.hired_at}, no email"))
    for hire in stuck_claims(rows):
        alerts.append(Alert("page", f"{hire.hire_id} is stuck mid-send since {hire.last_attempt_at or '?'}"))
    for hire in held(rows):
        alerts.append(Alert("warn", f"{hire.hire_id} needs review: {hire.note}"))
    for hire in undated(rows):
        alerts.append(Alert("warn", f"{hire.hire_id} is Hired with no hired_at, so lateness is unknown"))

    hired, sent = drift(rows, log, at)
    if hired and sent < hired:
        alerts.append(Alert("warn", f"last 7 days: {hired} hired, {sent} welcomed"))
    return alerts
