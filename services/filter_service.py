"""
Dashboard filter/sort/summary helpers.

Kept as small, pure functions with no Streamlit dependency, so they're
unit testable on their own. `app.py` calls these with whatever rows came
back from database.py (sqlite3.Row objects support the same
`row["field"]` access dict rows do, so these work with either).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable, Optional, Sequence

# How long a package stays flagged "Baru" (new/updated) in the saved-package
# tables after `last_updated_at` moves - see is_recent(). `last_updated_at`
# gets touched both on first insert AND on any tracked-field update (see
# comparison_service.py / homepage_service.py), so checking it alone
# covers both "brand new" and "recently updated" packages.
RECENT_WINDOW_HOURS = 24


def _get(row, key, default=None):
    try:
        value = row[key]
    except (KeyError, IndexError):
        return default
    return default if value is None else value


def distinct_values(rows: Iterable, field: str) -> list:
    """All distinct non-empty values for `field`, sorted, for populating a
    filter multiselect's options."""
    seen = {str(_get(row, field)) for row in rows if _get(row, field) not in (None, "")}
    return sorted(seen)


def filter_rows(
    rows: Sequence,
    wilayah: Optional[Sequence[str]] = None,
    status: Optional[Sequence[str]] = None,
    kategori: Optional[Sequence[str]] = None,
    status_field: str = "tahapan",
    kategori_field: str = "kategori",
) -> list:
    """Keep only rows matching every ACTIVE filter (empty/None = no filter
    on that dimension). `status_field`/`kategori_field` let the same
    function serve both the Daftar Lengkap rows (status column: `tahapan`)
    and the Ringkasan Beranda rows (status column: `kategori`)."""
    result = list(rows)
    if wilayah:
        wanted = set(wilayah)
        result = [r for r in result if _get(r, "region_identifier") in wanted]
    if status:
        wanted = set(status)
        result = [r for r in result if _get(r, status_field) in wanted]
    if kategori:
        wanted = set(kategori)
        result = [r for r in result if _get(r, kategori_field) in wanted]
    return result


def sum_hps(rows: Iterable) -> float:
    """Total HPS across the given rows (whatever set that is - callers pass
    the FILTERED rows so the total recalculates with the active filter).
    Rows with no numeric hps_value are skipped, not treated as
    zero-but-counted."""
    total = 0.0
    for row in rows:
        value = _get(row, "hps_value")
        if isinstance(value, (int, float)):
            total += value
    return total


def is_recent(iso_timestamp: Optional[str], hours: int = RECENT_WINDOW_HOURS) -> bool:
    """True if `iso_timestamp` (a database `last_updated_at`/`first_seen_at`
    style ISO string) is within the last `hours` hours - powers the small
    "🆕 Baru" indicator on the saved-package tables, separate from the
    "Paket Baru"/"Paket Diperbarui" cards shown right after a check (which
    only exist for the session that just ran). This one is persistent:
    reopen the app the next morning and a package touched yesterday still
    shows the badge. Malformed/missing timestamps are treated as "not
    recent" rather than raising - a display helper should never crash the
    page over a bad date string."""
    if not iso_timestamp:
        return False
    try:
        touched_at = datetime.fromisoformat(iso_timestamp)
    except ValueError:
        return False
    return (datetime.now() - touched_at) <= timedelta(hours=hours)


SORT_OPTIONS = {
    "Terlama -> Terbaru (default)": ("_chronological", False),
    "Terbaru -> Terlama": ("_chronological", True),
    "Nama Paket (A-Z)": ("nama_paket", False),
    "Nama Paket (Z-A)": ("nama_paket", True),
    "HPS Tertinggi": ("hps_value", True),
    "HPS Terendah": ("hps_value", False),
}


def sort_rows(rows: Sequence, sort_label: str) -> list:
    """Sort a list of rows for display. `rows` is assumed to already be in
    chronological (earliest-first) order as returned by the database, so
    `_chronological` just optionally reverses that rather than re-deriving
    it - the DB's ordering (Package ID based) stays the single source of
    truth for "which one is earlier"."""
    result = list(rows)
    field, reverse = SORT_OPTIONS.get(sort_label, ("_chronological", False))
    if field == "_chronological":
        return list(reversed(result)) if reverse else result

    # Rows with no value for the sort field always sink to the bottom,
    # regardless of ascending/descending - "highest HPS first" shouldn't
    # surface a package with an unknown HPS at the very top.
    with_value = [r for r in result if _get(r, field) is not None]
    without_value = [r for r in result if _get(r, field) is None]
    with_value.sort(key=lambda r: _get(r, field), reverse=reverse)
    return with_value + without_value
