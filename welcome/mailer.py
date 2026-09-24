from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol


class SendError(RuntimeError):
    def __init__(self, message: str, permanent: bool = False) -> None:
        super().__init__(message)
        self.permanent = permanent


class Mailer(Protocol):
    def send(self, to: str, subject: str, body: str) -> str: ...


@dataclass
class RecordingMailer:
    sent: list[tuple[str, str, str]] = field(default_factory=list)
    fail_with: dict[str, SendError] = field(default_factory=dict)

    def send(self, to: str, subject: str, body: str) -> str:
        if to in self.fail_with:
            raise self.fail_with[to]
        self.sent.append((to, subject, body))
        return f"demo-{uuid.uuid4().hex[:12]}"
