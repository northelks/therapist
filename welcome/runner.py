from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from welcome.mailer import Mailer, SendError
from welcome.models import HIRED, NEEDS_REVIEW, SENDING, SENT, Hire, now, parse_stamp, stamp
from welcome.render import TemplateError, render
from welcome.sent_log import SentLog
from welcome.source import HireSource
from welcome.validate import problems

MAX_ATTEMPTS = 3
BACKOFF = timedelta(minutes=15)
STALE_CLAIM = timedelta(minutes=30)


@dataclass
class Report:
    checked: int = 0
    sent: list[str] = field(default_factory=list)
    would_send: list[tuple[str, str, str]] = field(default_factory=list)
    held: list[tuple[str, str]] = field(default_factory=list)
    retrying: list[tuple[str, str]] = field(default_factory=list)
    repaired: list[str] = field(default_factory=list)
    released: list[str] = field(default_factory=list)
    raced: list[str] = field(default_factory=list)

    def line(self) -> str:
        return (
            f"checked {self.checked}, sent {len(self.sent)}, held {len(self.held)}, "
            f"retrying {len(self.retrying)}, repaired {len(self.repaired)}, "
            f"released {len(self.released)}"
        )


def run(
    source: HireSource,
    mailer: Mailer,
    log: SentLog,
    template: str,
    dry_run: bool = False,
    at: datetime | None = None,
) -> Report:
    source.check_schema()
    at = at or now()
    report = Report()

    for hire in source.rows():
        if hire.status == SENDING and not dry_run:
            _recover(source, log, hire, at, report)
            continue
        if hire.status != HIRED or hire.welcomed:
            continue

        report.checked += 1

        if log.already_sent(hire.hire_id):
            entry = log.entry(hire.hire_id) or {}
            if not dry_run:
                source.update(
                    hire.hire_id,
                    status=SENT,
                    welcome_sent_at=entry.get("at", ""),
                    welcome_message_id=entry.get("message_id", ""),
                    note="restored from the send log, not resent",
                )
            report.repaired.append(hire.hire_id)
            continue

        found = problems(hire)
        if found:
            _hold(source, hire, "; ".join(found), report, dry_run)
            continue

        if not _due(hire, at):
            report.retrying.append((hire.hire_id, f"waiting out attempt {hire.tries}"))
            continue

        try:
            subject, body = render(template, hire)
        except (TemplateError, OSError) as exc:
            _hold(source, hire, str(exc), report, dry_run)
            continue

        if dry_run:
            report.would_send.append((hire.hire_id, hire.email, subject))
            continue

        if not source.claim(hire.hire_id):
            report.raced.append(hire.hire_id)
            continue

        try:
            message_id = mailer.send(hire.email, subject, body)
        except SendError as exc:
            _after_failure(source, hire, exc, at, report)
            continue

        sent_at = stamp(at)
        log.record(hire.hire_id, hire.email, message_id, sent_at)
        source.update(
            hire.hire_id,
            status=SENT,
            welcome_sent_at=sent_at,
            welcome_message_id=message_id,
            last_attempt_at=sent_at,
            note="",
        )
        report.sent.append(hire.hire_id)

    return report


def _due(hire: Hire, at: datetime) -> bool:
    if hire.tries == 0:
        return True
    last = parse_stamp(hire.last_attempt_at)
    if last is None:
        return True
    return at - last >= BACKOFF * (2 ** (hire.tries - 1))


def _hold(source: HireSource, hire: Hire, reason: str, report: Report, dry_run: bool) -> None:
    if not dry_run:
        source.update(hire.hire_id, status=NEEDS_REVIEW, note=reason)
    report.held.append((hire.hire_id, reason))


def _after_failure(
    source: HireSource, hire: Hire, exc: SendError, at: datetime, report: Report
) -> None:
    tries = hire.tries + 1
    if exc.permanent or tries >= MAX_ATTEMPTS:
        source.update(
            hire.hire_id,
            status=NEEDS_REVIEW,
            attempts=str(tries),
            last_attempt_at=stamp(at),
            note=f"gave up after {tries}: {exc}",
        )
        report.held.append((hire.hire_id, str(exc)))
        return
    source.update(
        hire.hire_id,
        status=HIRED,
        attempts=str(tries),
        last_attempt_at=stamp(at),
        note=f"attempt {tries} failed: {exc}",
    )
    report.retrying.append((hire.hire_id, str(exc)))


def _recover(source: HireSource, log: SentLog, hire: Hire, at: datetime, report: Report) -> None:
    entry = log.entry(hire.hire_id)
    if entry:
        source.update(
            hire.hire_id,
            status=SENT,
            welcome_sent_at=entry["at"],
            welcome_message_id=entry["message_id"],
            note="recovered: the send completed, the tracker did not",
        )
        report.repaired.append(hire.hire_id)
        return

    claimed = parse_stamp(hire.last_attempt_at) or _claim_time(hire)
    if claimed is not None and at - claimed < STALE_CLAIM:
        return
    source.update(hire.hire_id, status=HIRED, note="released: the run that claimed it died")
    report.released.append(hire.hire_id)


def _claim_time(hire: Hire) -> datetime | None:
    if hire.note.startswith("claimed "):
        return parse_stamp(hire.note[len("claimed "):])
    return None
