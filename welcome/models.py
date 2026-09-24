from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime, timezone

HIRED = "Hired"
SENDING = "Sending"
SENT = "Sent"
NEEDS_REVIEW = "Needs review"

COLUMNS = (
    "hire_id",
    "name",
    "email",
    "status",
    "hired_at",
    "start_date",
    "welcome_sent_at",
    "welcome_message_id",
    "attempts",
    "last_attempt_at",
    "note",
)


def now() -> datetime:
    return datetime.now(timezone.utc)


def stamp(at: datetime) -> str:
    return at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_stamp(text: str) -> datetime | None:
    try:
        return datetime.strptime(text.strip(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


@dataclass(slots=True)
class Hire:
    hire_id: str
    name: str = ""
    email: str = ""
    status: str = ""
    hired_at: str = ""
    start_date: str = ""
    welcome_sent_at: str = ""
    welcome_message_id: str = ""
    attempts: str = ""
    last_attempt_at: str = ""
    note: str = ""

    @classmethod
    def from_row(cls, row: dict[str, str]) -> Hire:
        known = {f.name for f in fields(cls)}
        return cls(**{k: (row.get(k) or "").strip() for k in known})

    def as_row(self) -> dict[str, str]:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @property
    def welcomed(self) -> bool:
        return bool(self.welcome_sent_at and self.welcome_message_id)

    @property
    def tries(self) -> int:
        try:
            return int(self.attempts)
        except ValueError:
            return 0

    def waiting_since(self) -> datetime | None:
        return parse_stamp(self.hired_at)
