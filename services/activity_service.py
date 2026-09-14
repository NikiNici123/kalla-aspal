"""
Merges the two per-dataset change-history tables (package_snapshots for
Daftar Lengkap, homepage_package_snapshots for Ringkasan Beranda) into one
recency-sorted "Aktivitas Terbaru" feed for the dashboard tab.

Kept as its own small module (rather than inlined in app.py) so the merge/
sort/format logic is unit-testable without a live Streamlit runtime - see
tests/test_activity_service.py.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Optional

from database import database as db
from services import status_flags

DATASET_LELANG = "lelang"
DATASET_BERANDA = "beranda"

DATASET_LABELS = {
    DATASET_LELANG: "Daftar Lengkap",
    DATASET_BERANDA: "Ringkasan Beranda",
}


@dataclass
class ActivityEntry:
    dataset: str
    dataset_label: str
    nama_paket: str
    package_url: Optional[str]
    change_summary: str
    created_at: str
    is_new: bool
    status_flags: list


def _to_entry(row: sqlite3.Row, dataset: str) -> Optional[ActivityEntry]:
    try:
        snapshot = json.loads(row["snapshot_json"])
    except (TypeError, ValueError):
        return None

    nama_paket = snapshot.get("nama_paket") or "(Nama paket tidak diketahui)"
    change_summary = row["change_summary"] or ""

    return ActivityEntry(
        dataset=dataset,
        dataset_label=DATASET_LABELS[dataset],
        nama_paket=nama_paket,
        package_url=snapshot.get("package_url"),
        change_summary=change_summary,
        created_at=row["created_at"],
        is_new=(change_summary == "Pertama kali ditemukan"),
        status_flags=status_flags.detect_status_flags(nama_paket),
    )


def get_recent_activity(conn: sqlite3.Connection, limit: int = 20) -> list:
    """Newest-first feed combining both datasets' change history, capped at
    `limit` total entries (not `limit` per dataset) - matches what a user
    scanning "what changed recently" actually expects to see."""
    lelang_rows = db.get_recent_package_snapshots(conn, limit=limit)
    beranda_rows = db.get_recent_homepage_snapshots(conn, limit=limit)

    entries = []
    for row in lelang_rows:
        entry = _to_entry(row, DATASET_LELANG)
        if entry:
            entries.append(entry)
    for row in beranda_rows:
        entry = _to_entry(row, DATASET_BERANDA)
        if entry:
            entries.append(entry)

    entries.sort(key=lambda e: e.created_at, reverse=True)
    return entries[:limit]
