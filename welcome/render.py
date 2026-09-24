from __future__ import annotations

from pathlib import Path
from string import Template

from welcome.models import Hire

ALLOWED = ("name", "first_name", "start_date", "hire_id")


class TemplateError(RuntimeError):
    pass


def fields(hire: Hire) -> dict[str, str]:
    return {
        "name": hire.name,
        "first_name": hire.name.split()[0] if hire.name else "",
        "start_date": hire.start_date,
        "hire_id": hire.hire_id,
    }


def render(path: str | Path, hire: Hire) -> tuple[str, str]:
    text = Path(path).read_text(encoding="utf-8")
    subject_line, _, body = text.partition("\n")
    if not subject_line.lower().startswith("subject:"):
        raise TemplateError(f"{Path(path).name}: the first line must start with 'Subject:'")

    values = fields(hire)
    try:
        subject = Template(subject_line[len("subject:"):].strip()).substitute(values)
        rendered = Template(body.strip("\n")).substitute(values)
    except KeyError as exc:
        raise TemplateError(
            f"{Path(path).name}: unknown placeholder {exc}, allowed: {', '.join(ALLOWED)}"
        ) from exc
    return subject, rendered
