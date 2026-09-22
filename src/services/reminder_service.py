"""
Pure date logic behind the deadline reminder feature - deciding WHICH
already-saved relevant packages (Ringkasan Beranda dataset, since that's
the one with Akhir Pendaftaran dates - see calendar_service's docstring)
fall inside the "warn me starting D days before" window.

Deliberately has no dependency on win11toast or anything Windows-only,
so it runs and gets tested the same way as every other service in this
folder (plain `pytest`, no real Windows machine needed). The actual
notification-firing side lives in `check_reminders.py` at the project
root, which imports this module.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional


def _get(row, key, default=None):
    try:
        value = row[key]
    except (KeyError, IndexError):
        return default
    return default if value is None else value


def _parse_deadline(value) -> Optional[date]:
    """Akhir Pendaftaran is stored as an ISO datetime string
    ("2026-09-20T23:59:00") - only the date part matters here."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def get_upcoming_deadlines(rows: Iterable, within_days: int, today: Optional[date] = None) -> list:
    """Rows (whatever db.get_relevant_homepage_packages(conn) returns, or
    a list of plain dicts in tests) whose Akhir Pendaftaran is today or up
    to `within_days` days from now - inclusive on both ends. Already-passed
    deadlines, ones further out, and packages with no parseable deadline
    are all left out. Returned soonest-deadline-first, as
    (deadline_date, row) pairs so callers don't have to re-parse the date."""
    today = today or date.today()
    cutoff = today + timedelta(days=within_days)

    upcoming = []
    for row in rows:
        deadline = _parse_deadline(_get(row, "akhir_pendaftaran_at"))
        if deadline is not None and today <= deadline <= cutoff:
            upcoming.append((deadline, row))

    upcoming.sort(key=lambda pair: pair[0])
    return upcoming


# ---------------------------------------------------------------------------
# "Already acknowledged today" tracking - supports multiple reminder checks
# a day (e.g. 08:00 / 13:00 / 16:00, see config/reminder_times.txt) without
# nagging again once someone has clicked/dismissed an earlier one the same
# day. Deliberately dead simple: one text file holding a single date - not
# per-package, not per-admin (this app already assumes one admin per
# device). If a *different* package becomes urgent later the same day, it
# still stays quiet until tomorrow - a known simplification, not a bug.
# ---------------------------------------------------------------------------

def is_acknowledged_today(ack_file: Path, today: Optional[date] = None) -> bool:
    """True if an earlier reminder check today already got clicked/
    acknowledged (mark_acknowledged wrote today's date into ack_file) -
    meaning a later scheduled check the same day should stay silent."""
    today = today or date.today()
    try:
        stored = ack_file.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return False
    return stored == today.isoformat()


def mark_acknowledged(ack_file: Path, today: Optional[date] = None) -> None:
    """Record that today's reminder was seen - overwrites ack_file with
    just today's ISO date, so is_acknowledged_today() returns True for
    the rest of today (and naturally "resets" tomorrow on its own, since
    tomorrow's date won't match what's stored)."""
    today = today or date.today()
    ack_file.parent.mkdir(parents=True, exist_ok=True)
    ack_file.write_text(today.isoformat(), encoding="utf-8")
