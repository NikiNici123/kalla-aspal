"""
SQLite connection handling + small data-access helpers for LPSE Monitor.

Everything here is plain sqlite3 (no ORM) - see models.py for why. Callers
get back sqlite3.Row objects (dict-like access by column name) rather than
raw tuples, and JSON-ish columns (badges, matched_keywords, snapshot_json,
regions_scraped) are encoded/decoded here so the rest of the app just deals
in normal Python lists/dicts.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from database.models import SCHEMA_SQL
from config.default_keywords import DEFAULT_KEYWORDS

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "lpse_monitor.db"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Create tables if they don't exist yet, and seed the default keyword
    list the very first time (i.e. only when the keywords table is empty -
    this will never overwrite keywords the user has since edited)."""
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()

        existing = conn.execute("SELECT COUNT(*) AS c FROM keywords").fetchone()["c"]
        if existing == 0:
            now = _now()
            conn.executemany(
                "INSERT INTO keywords (keyword, is_enabled, created_at, updated_at) "
                "VALUES (?, 1, ?, ?)",
                [(kw, now, now) for kw in DEFAULT_KEYWORDS],
            )
            conn.commit()
    finally:
        conn.close()


@contextmanager
def connect(db_path: Path = DEFAULT_DB_PATH):
    """Convenience context manager: `with connect() as conn: ...` that
    commits on success and always closes the connection."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Regions
# ---------------------------------------------------------------------------

def upsert_region(conn: sqlite3.Connection, region_name: str, region_identifier: str, base_url: str) -> None:
    """Create the region if it's new; otherwise leave its name/active-state
    alone (so re-scraping an existing region never silently reactivates one
    the user deliberately turned off, and never clobbers a name they edited).
    """
    now = _now()
    existing = conn.execute(
        "SELECT id FROM regions WHERE region_identifier = ?", (region_identifier,)
    ).fetchone()
    if existing:
        return
    conn.execute(
        "INSERT INTO regions (region_name, region_identifier, base_url, is_active, created_at, updated_at) "
        "VALUES (?, ?, ?, 1, ?, ?)",
        (region_name, region_identifier, base_url, now, now),
    )


def get_active_regions(conn: sqlite3.Connection) -> list:
    return conn.execute("SELECT * FROM regions WHERE is_active = 1").fetchall()


def get_all_regions(conn: sqlite3.Connection) -> list:
    return conn.execute("SELECT * FROM regions ORDER BY region_name").fetchall()


# ---------------------------------------------------------------------------
# Keywords
# ---------------------------------------------------------------------------

def get_enabled_keywords(conn: sqlite3.Connection) -> list:
    return conn.execute("SELECT * FROM keywords WHERE is_enabled = 1").fetchall()


def get_all_keywords(conn: sqlite3.Connection) -> list:
    return conn.execute("SELECT * FROM keywords ORDER BY keyword").fetchall()


# ---------------------------------------------------------------------------
# Packages
# ---------------------------------------------------------------------------

def get_package_by_key(conn: sqlite3.Connection, package_id: Optional[str], fingerprint: Optional[str]):
    if package_id:
        return conn.execute("SELECT * FROM packages WHERE package_id = ?", (package_id,)).fetchone()
    if fingerprint:
        return conn.execute("SELECT * FROM packages WHERE fingerprint = ?", (fingerprint,)).fetchone()
    return None


def insert_package(conn: sqlite3.Connection, pkg_dict: dict) -> None:
    now = _now()
    conn.execute(
        """
        INSERT INTO packages (
            package_id, fingerprint, region_identifier, nama_paket, nama_paket_raw,
            badges, instansi, tahapan, metode_kualifikasi, jenis, metode_evaluasi,
            jenis_pengadaan, tahun_anggaran, hps_text, hps_value, nilai_kontrak_text,
            nilai_kontrak_value, evaluasi_ulang, penawaran_ulang, konsolidasi, oap_only,
            package_url, is_relevant, matched_keywords, first_seen_at, last_seen_at, last_updated_at
        ) VALUES (?,?,?,?,?, ?,?,?,?,?,?, ?,?,?,?,?, ?,?,?,?,?, ?,?,?,?,?,?)
        """,
        (
            pkg_dict["package_id"], pkg_dict["fingerprint"], pkg_dict["region_identifier"],
            pkg_dict["nama_paket"], pkg_dict["nama_paket_raw"],
            json.dumps(pkg_dict.get("badges", [])), pkg_dict["instansi"], pkg_dict["tahapan"],
            pkg_dict["metode_kualifikasi"], pkg_dict["jenis"], pkg_dict["metode_evaluasi"],
            pkg_dict["jenis_pengadaan"], pkg_dict["tahun_anggaran"], pkg_dict["hps_text"],
            pkg_dict["hps_value"], pkg_dict["nilai_kontrak_text"],
            pkg_dict["nilai_kontrak_value"], int(pkg_dict["evaluasi_ulang"]), int(pkg_dict["penawaran_ulang"]),
            int(pkg_dict["konsolidasi"]), int(pkg_dict["oap_only"]),
            pkg_dict["package_url"], int(pkg_dict.get("is_relevant", False)),
            json.dumps(pkg_dict.get("matched_keywords", [])), now, now, now,
        ),
    )


def update_package(conn: sqlite3.Connection, existing_row: sqlite3.Row, pkg_dict: dict) -> None:
    now = _now()
    conn.execute(
        """
        UPDATE packages SET
            nama_paket=?, nama_paket_raw=?, badges=?, instansi=?, tahapan=?,
            metode_kualifikasi=?, jenis=?, metode_evaluasi=?, jenis_pengadaan=?, tahun_anggaran=?,
            hps_text=?, hps_value=?, nilai_kontrak_text=?, nilai_kontrak_value=?,
            evaluasi_ulang=?, penawaran_ulang=?, konsolidasi=?, oap_only=?,
            package_url=?, is_relevant=?, matched_keywords=?, last_seen_at=?, last_updated_at=?
        WHERE id=?
        """,
        (
            pkg_dict["nama_paket"], pkg_dict["nama_paket_raw"], json.dumps(pkg_dict.get("badges", [])),
            pkg_dict["instansi"], pkg_dict["tahapan"], pkg_dict["metode_kualifikasi"], pkg_dict["jenis"],
            pkg_dict["metode_evaluasi"], pkg_dict["jenis_pengadaan"], pkg_dict["tahun_anggaran"],
            pkg_dict["hps_text"], pkg_dict["hps_value"], pkg_dict["nilai_kontrak_text"],
            pkg_dict["nilai_kontrak_value"], int(pkg_dict["evaluasi_ulang"]), int(pkg_dict["penawaran_ulang"]),
            int(pkg_dict["konsolidasi"]), int(pkg_dict["oap_only"]), pkg_dict["package_url"],
            int(pkg_dict.get("is_relevant", False)), json.dumps(pkg_dict.get("matched_keywords", [])),
            now, now, existing_row["id"],
        ),
    )


def touch_package_last_seen(conn: sqlite3.Connection, existing_row: sqlite3.Row) -> None:
    """Package matched an existing DB row with no tracked-field changes:
    just bump last_seen_at so we know it's still listed."""
    conn.execute(
        "UPDATE packages SET last_seen_at=? WHERE id=?", (_now(), existing_row["id"])
    )


def get_relevant_packages(conn: sqlite3.Connection, region_identifier: Optional[str] = None) -> list:
    if region_identifier:
        return conn.execute(
            "SELECT * FROM packages WHERE is_relevant = 1 AND region_identifier = ? "
            "ORDER BY last_updated_at DESC",
            (region_identifier,),
        ).fetchall()
    return conn.execute(
        "SELECT * FROM packages WHERE is_relevant = 1 ORDER BY last_updated_at DESC"
    ).fetchall()


# ---------------------------------------------------------------------------
# Package snapshots (change history)
# ---------------------------------------------------------------------------

def insert_snapshot(
    conn: sqlite3.Connection,
    package_key: str,
    scrape_run_id: Optional[int],
    tahapan: str,
    hps_value: Optional[float],
    nilai_kontrak_value: Optional[float],
    change_summary: str,
    snapshot_json: dict,
) -> None:
    conn.execute(
        """
        INSERT INTO package_snapshots
            (package_key, scrape_run_id, tahapan, hps_value, nilai_kontrak_value,
             change_summary, snapshot_json, created_at)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            package_key, scrape_run_id, tahapan, hps_value, nilai_kontrak_value,
            change_summary, json.dumps(snapshot_json), _now(),
        ),
    )


def get_package_history(conn: sqlite3.Connection, package_key: str) -> list:
    return conn.execute(
        "SELECT * FROM package_snapshots WHERE package_key = ? ORDER BY created_at ASC",
        (package_key,),
    ).fetchall()


# ---------------------------------------------------------------------------
# Scrape runs
# ---------------------------------------------------------------------------

def start_scrape_run(conn: sqlite3.Connection, regions_scraped: list) -> int:
    cur = conn.execute(
        "INSERT INTO scrape_runs (started_at, regions_scraped, status) VALUES (?, ?, 'running')",
        (_now(), json.dumps(regions_scraped)),
    )
    return cur.lastrowid


def finish_scrape_run(
    conn: sqlite3.Connection,
    run_id: int,
    total_packages_found: int,
    relevant_packages_found: int,
    new_packages_found: int,
    updated_packages_found: int,
    status: str = "completed",
    error_message: Optional[str] = None,
) -> None:
    conn.execute(
        """
        UPDATE scrape_runs SET
            finished_at=?, total_packages_found=?, relevant_packages_found=?,
            new_packages_found=?, updated_packages_found=?, status=?, error_message=?
        WHERE id=?
        """,
        (
            _now(), total_packages_found, relevant_packages_found,
            new_packages_found, updated_packages_found, status, error_message, run_id,
        ),
    )


def get_scrape_history(conn: sqlite3.Connection, limit: int = 50) -> list:
    return conn.execute(
        "SELECT * FROM scrape_runs ORDER BY started_at DESC LIMIT ?", (limit,)
    ).fetchall()


def get_last_completed_run(conn: sqlite3.Connection):
    return conn.execute(
        "SELECT * FROM scrape_runs WHERE status = 'completed' ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
