from __future__ import annotations

import re

from welcome.models import Hire

ADDRESS = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[A-Za-z]{2,}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def problems(hire: Hire) -> list[str]:
    found: list[str] = []
    if not hire.hire_id:
        found.append("no hire_id")
    if not hire.name:
        found.append("no name")
    if not hire.email:
        found.append("no email")
    elif not ADDRESS.match(hire.email):
        found.append(f"email does not look like an address: {hire.email!r}")
    elif hire.email.lower().endswith((".con", ".cmo", ".comm")):
        found.append(f"likely typo in the domain: {hire.email!r}")
    if not hire.start_date:
        found.append("no start date")
    elif not DATE.match(hire.start_date):
        found.append(f"start date is not YYYY-MM-DD: {hire.start_date!r}")
    return found
