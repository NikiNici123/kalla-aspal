"""
Calendar helpers for the "Ringkasan Beranda" tab.

Marks each Akhir Pendaftaran (registration deadline) date on a small,
built-in calendar without cluttering the screen - a day just gets a
small marker, and the packages due that day show up on hover/click.
This module does the date math (which package falls on which day,
building a month grid) using only the standard library's `calendar`/
`datetime` - not a third-party Streamlit calendar widget, so there's no
extra dependency to install or keep working. `app.py` renders the grid
this returns as a plain table of buttons.
"""

from __future__ import annotations

import calendar as _calendar
from collections import defaultdict
from datetime import date
from typing import Iterable, Optional


def _get(row, key, default=None):
    try:
        value = row[key]
    except (KeyError, IndexError):
        return default
    return default if value is None else value


def group_by_deadline_date(rows: Iterable) -> dict:
    """Group homepage packages by their Akhir Pendaftaran date (YYYY-MM-DD
    string key). Packages with no parseable deadline (akhir_pendaftaran_at
    is None) are skipped - they simply don't appear on the calendar, same
    as the underlying data has no date to plot."""
    grouped = defaultdict(list)
    for row in rows:
        at = _get(row, "akhir_pendaftaran_at")
        if not at:
            continue
        day_key = str(at)[:10]  # ISO datetime -> just the date part
        grouped[day_key].append(row)
    return dict(grouped)


def build_month_grid(year: int, month: int) -> list:
    """Weeks x days grid (Monday-first, matching Indonesian convention) for
    the given month, as `datetime.date` objects - `None` for the leading/
    trailing blanks that pad the first and last week. Just wraps stdlib
    `calendar.Calendar` so the logic is trivially correct and doesn't need
    its own from-scratch date arithmetic."""
    cal = _calendar.Calendar(firstweekday=0)
    weeks = []
    for week in cal.monthdatescalendar(year, month):
        row = [d if d.month == month else None for d in week]
        weeks.append(row)
    return weeks


MONTH_NAMES_ID = [
    "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]

WEEKDAY_NAMES_ID = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]


def add_months(year: int, month: int, delta: int) -> tuple:
    """Shift (year, month) by `delta` months, wrapping the year - used for
    the "previous/next month" navigation buttons."""
    zero_based = (month - 1) + delta
    new_year = year + zero_based // 12
    new_month = zero_based % 12 + 1
    return new_year, new_month
