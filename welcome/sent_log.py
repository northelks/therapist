from __future__ import annotations

import json
from pathlib import Path


class SentLog:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._seen: dict[str, dict] | None = None

    def _load(self) -> dict[str, dict]:
        if self._seen is None:
            self._seen = {}
            if self.path.exists():
                for line in self.path.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        entry = json.loads(line)
                        self._seen[entry["hire_id"]] = entry
        return self._seen

    def entry(self, hire_id: str) -> dict | None:
        return self._load().get(hire_id)

    def already_sent(self, hire_id: str) -> bool:
        return hire_id in self._load()

    def record(self, hire_id: str, email: str, message_id: str, at: str) -> None:
        entry = {"hire_id": hire_id, "email": email, "message_id": message_id, "at": at}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
        self._load()[hire_id] = entry
