from __future__ import annotations

import csv
import fcntl
from pathlib import Path
from typing import Protocol

from welcome.models import COLUMNS, HIRED, SENDING, Hire, now, stamp


class SchemaError(RuntimeError):
    pass


class HireSource(Protocol):
    def check_schema(self) -> None: ...
    def rows(self) -> list[Hire]: ...
    def add(self, hire: Hire) -> None: ...
    def claim(self, hire_id: str) -> bool: ...
    def update(self, hire_id: str, **fields: str) -> None: ...


class CsvSource:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def check_schema(self) -> None:
        with self.path.open(newline="", encoding="utf-8") as fh:
            header = next(csv.reader(fh), [])
        missing = [c for c in COLUMNS if c not in header]
        if missing:
            raise SchemaError(f"{self.path.name}: missing columns {', '.join(missing)}")

    def rows(self) -> list[Hire]:
        with self.path.open(newline="", encoding="utf-8") as fh:
            return [Hire.from_row(row) for row in csv.DictReader(fh)]

    def next_id(self) -> str:
        used = [int(h.hire_id[2:]) for h in self.rows() if h.hire_id[2:].isdigit()]
        return f"H-{max(used, default=1000) + 1}"

    def add(self, hire: Hire) -> None:
        def append(rows: list[dict[str, str]]) -> bool:
            rows.append(hire.as_row())
            return True

        self._rewrite(append)

    def claim(self, hire_id: str) -> bool:
        def take(rows: list[dict[str, str]]) -> bool:
            for row in rows:
                if row["hire_id"] != hire_id:
                    continue
                if row["status"].strip() != HIRED or row["welcome_sent_at"].strip():
                    return False
                row["status"] = SENDING
                row["note"] = f"claimed {stamp(now())}"
                return True
            return False

        return self._rewrite(take)

    def update(self, hire_id: str, **values: str) -> None:
        def apply(rows: list[dict[str, str]]) -> bool:
            for row in rows:
                if row["hire_id"] == hire_id:
                    row.update(values)
            return True

        self._rewrite(apply)

    def _rewrite(self, change) -> bool:
        with self.path.open("r+", newline="", encoding="utf-8") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                reader = csv.DictReader(fh)
                header = reader.fieldnames or list(COLUMNS)
                rows = list(reader)
                result = change(rows)
                if result:
                    fh.seek(0)
                    fh.truncate()
                    writer = csv.DictWriter(fh, fieldnames=header)
                    writer.writeheader()
                    writer.writerows(rows)
                return result
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)
