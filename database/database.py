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
    return conn.execute("SELECT * FROM regions WHERE is_active = 1 ORDER BY region_name").fetchall()


def get_all_regions(conn: sqlite3.Connection) -> list:
    return conn.execute("SELECT * FROM regions ORDER BY region_name").fetchall()


def get_region_by_identifier(conn: sqlite3.Connection, region_identifier: str):
    return conn.execute(
        "SELECT * FROM regions WHERE region_identifier = ?", (region_identifier,)
    ).fetchone()


def add_region(conn: sqlite3.Connection, region_name: str, region_identifier: str, base_url: str) -> tuple:
    """Explicitly add a region from the Wilayah LPSE management UI.
    Returns (ok: bool, message: str) instead of raising, since this is
    meant to be called directly from a form submit and shown to a
    non-technical user."""
    region_identifier = region_identifier.strip()
    if not region_identifier:
        return False, "Region Identifier tidak boleh kosong."
    if get_region_by_identifier(conn, region_identifier):
        return False, f"Wilayah dengan identifier '{region_identifier}' sudah ada."
    now = _now()
    conn.execute(
        "INSERT INTO regions (region_name, region_identifier, base_url, is_active, created_at, updated_at) "
        "VALUES (?, ?, ?, 1, ?, ?)",
        (region_name.strip() or region_identifier, region_identifier, base_url, now, now),
    )
    return True, f"Wilayah '{region_name or region_identifier}' berhasil ditambahkan."


def set_region_active(conn: sqlite3.Connection, region_id: int, is_active: bool) -> None:
    conn.execute(
        "UPDATE regions SET is_active=?, updated_at=? WHERE id=?",
        (int(is_active), _now(), region_id),
    )


def delete_region(conn: sqlite3.Connection, region_id: int) -> None:
    """Removes the region from the monitored list. Packages already stored
    for it are kept (they're tied to region_identifier, not to this row) -
    deleting a region only stops future scrapes of it."""
    conn.execute("DELETE FROM regions WHERE id=?", (region_id,))


# ---------------------------------------------------------------------------
# Keywords
# ---------------------------------------------------------------------------

def get_enabled_keywords(conn: sqlite3.Connection) -> list:
    return conn.execute("SELECT * FROM keywords WHERE is_enabled = 1").fetchall()


def get_all_keywords(conn: sqlite3.Connection) -> list:
    return conn.execute("SELECT * FROM keywords ORDER BY keyword").fetchall()


def add_keyword(conn: sqlite3.Connection, keyword: str) -> tuple:
    """Returns (ok, message) - meant to be called straight from a form
    submit, same pattern as add_region."""
    keyword = keyword.strip()
    if not keyword:
        return False, "Kata kunci tidak boleh kosong."
    existing = conn.execute(
        "SELECT id FROM keywords WHERE keyword = ?", (keyword,)
    ).fetchone()
    if existing:
        return False, f"Kata kunci '{keyword}' sudah ada."
    now = _now()
    conn.execute(
        "INSERT INTO keywords (keyword, is_enabled, created_at, updated_at) VALUES (?, 1, ?, ?)",
        (keyword, now, now),
    )
    return True, f"Kata kunci '{keyword}' berhasil ditambahkan."


def update_keyword_text(conn: sqlite3.Connection, keyword_id: int, new_text: str) -> tuple:
    new_text = new_text.strip()
    if not new_text:
        return False, "Kata kunci tidak boleh kosong."
    conn.execute(
        "UPDATE keywords SET keyword=?, updated_at=? WHERE id=?",
        (new_text, _now(), keyword_id),
    )
    return True, "Kata kunci berhasil diperbarui."


def set_keyword_enabled(conn: sqlite3.Connection, keyword_id: int, is_enabled: bool) -> None:
    conn.execute(
        "UPDATE keywords SET is_enabled=?, updated_at=? WHERE id=?",
        (int(is_enabled), _now(), keyword_id),
    )


def delete_keyword(conn: sqlite3.Connection, keyword_id: int) -> None:
    conn.execute("DELETE FROM keywords WHERE id=?", (keyword_id,))


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


# Ordering note: the user wants the STORED/DISPLAYED list to run earliest
# package first, latest package last - i.e. the opposite of "most recently
# touched by us first". The site doesn't expose an explicit upload
# timestamp, but Package ID (Kode Lelang) is assigned in increasing order
# as packages are created, so we use it as a chronology proxy: ascending
# package_id = earliest-to-latest. Rows without a numeric package_id (the
# fallback-fingerprint case) are pushed to the end, ordered by when we
# first saw them.
_CHRONOLOGICAL_ORDER_SQL = (
    "ORDER BY (package_id IS NULL) ASC, CAST(package_id AS INTEGER) ASC, first_seen_at ASC"
)


def get_relevant_packages(conn: sqlite3.Connection, region_identifier: Optional[str] = None) -> list:
    if region_identifier:
        return conn.execute(
            f"SELECT * FROM packages WHERE is_relevant = 1 AND region_identifier = ? "
            f"{_CHRONOLOGICAL_ORDER_SQL}",
            (region_identifier,),
        ).fetchall()
    return conn.execute(
        f"SELECT * FROM packages WHERE is_relevant = 1 {_CHRONOLOGICAL_ORDER_SQL}"
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


# ---------------------------------------------------------------------------
# Homepage ("Beranda") summary packages - see scraper/lpse_homepage_scraper.py
# and models.py for why this is a separate table from `packages`.
# ---------------------------------------------------------------------------

def get_homepage_package_by_key(conn: sqlite3.Connection, package_id: Optional[str], fingerprint: Optional[str]):
    if package_id:
        return conn.execute(
            "SELECT * FROM homepage_packages WHERE package_id = ?", (package_id,)
        ).fetchone()
    if fingerprint:
        return conn.execute(
            "SELECT * FROM homepage_packages WHERE fingerprint = ?", (fingerprint,)
        ).fetchone()
    return None


def insert_homepage_package(conn: sqlite3.Connection, pkg_dict: dict) -> None:
    now = _now()
    conn.execute(
        """
        INSERT INTO homepage_packages (
            package_id, fingerprint, region_identifier, section, kategori, nama_paket,
            badges, hps_text, hps_value, akhir_pendaftaran_text, akhir_pendaftaran_at,
            display_position, package_url, is_relevant, matched_keywords,
            first_seen_at, last_seen_at, last_updated_at
        ) VALUES (?,?,?,?,?,?, ?,?,?,?,?, ?,?,?,?, ?,?,?)
        """,
        (
            pkg_dict["package_id"], pkg_dict["fingerprint"], pkg_dict["region_identifier"],
            pkg_dict["section"], pkg_dict["kategori"], pkg_dict["nama_paket"],
            json.dumps(pkg_dict.get("badges", [])), pkg_dict["hps_text"], pkg_dict["hps_value"],
            pkg_dict["akhir_pendaftaran_text"], pkg_dict["akhir_pendaftaran_at"],
            pkg_dict["display_position"], pkg_dict["package_url"],
            int(pkg_dict.get("is_relevant", False)), json.dumps(pkg_dict.get("matched_keywords", [])),
            now, now, now,
        ),
    )


def update_homepage_package(conn: sqlite3.Connection, existing_row: sqlite3.Row, pkg_dict: dict) -> None:
    now = _now()
    conn.execute(
        """
        UPDATE homepage_packages SET
            section=?, kategori=?, nama_paket=?, badges=?, hps_text=?, hps_value=?,
            akhir_pendaftaran_text=?, akhir_pendaftaran_at=?, display_position=?,
            package_url=?, is_relevant=?, matched_keywords=?, last_seen_at=?, last_updated_at=?
        WHERE id=?
        """,
        (
            pkg_dict["section"], pkg_dict["kategori"], pkg_dict["nama_paket"],
            json.dumps(pkg_dict.get("badges", [])), pkg_dict["hps_text"], pkg_dict["hps_value"],
            pkg_dict["akhir_pendaftaran_text"], pkg_dict["akhir_pendaftaran_at"], pkg_dict["display_position"],
            pkg_dict["package_url"], int(pkg_dict.get("is_relevant", False)),
            json.dumps(pkg_dict.get("matched_keywords", [])), now, now, existing_row["id"],
        ),
    )


def touch_homepage_package_last_seen(conn: sqlite3.Connection, existing_row: sqlite3.Row) -> None:
    conn.execute(
        "UPDATE homepage_packages SET last_seen_at=? WHERE id=?", (_now(), existing_row["id"])
    )


def get_relevant_homepage_packages(conn: sqlite3.Connection, region_identifier: Optional[str] = None) -> list:
    if region_identifier:
        return conn.execute(
            f"SELECT * FROM homepage_packages WHERE is_relevant = 1 AND region_identifier = ? "
            f"{_CHRONOLOGICAL_ORDER_SQL}",
            (region_identifier,),
        ).fetchall()
    return conn.execute(
        f"SELECT * FROM homepage_packages WHERE is_relevant = 1 {_CHRONOLOGICAL_ORDER_SQL}"
    ).fetchall()


def start_homepage_scrape_run(conn: sqlite3.Connection, regions_scraped: list) -> int:
    cur = conn.execute(
        "INSERT INTO homepage_scrape_runs (started_at, regions_scraped, status) VALUES (?, ?, 'running')",
        (_now(), json.dumps(regions_scraped)),
    )
    return cur.lastrowid


def finish_homepage_scrape_run(
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
        UPDATE homepage_scrape_runs SET
            finished_at=?, total_packages_found=?, relevant_packages_found=?,
            new_packages_found=?, updated_packages_found=?, status=?, error_message=?
        WHERE id=?
        """,
        (
            _now(), total_packages_found, relevant_packages_found,
            new_packages_found, updated_packages_found, status, error_message, run_id,
        ),
    )


def get_last_completed_homepage_run(conn: sqlite3.Connection):
    return conn.execute(
        "SELECT * FROM homepage_scrape_runs WHERE status = 'completed' ORDER BY started_at DESC LIMIT 1"
    ).fetchone()


# ---------------------------------------------------------------------------
# Excel export config + row tracking - see services/excel_service.py
# ---------------------------------------------------------------------------

def get_excel_config(conn: sqlite3.Connection):
    return conn.execute("SELECT * FROM excel_config WHERE id = 1").fetchone()


def save_excel_config(
    conn: sqlite3.Connection,
    file_path: str,
    sheet_name: str,
    start_cell: str,
    enabled_columns: list,
    mode: str,
) -> None:
    now = _now()
    conn.execute(
        """
        INSERT INTO excel_config (id, file_path, sheet_name, start_cell, enabled_columns, mode, updated_at)
        VALUES (1, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            file_path=excluded.file_path, sheet_name=excluded.sheet_name,
            start_cell=excluded.start_cell, enabled_columns=excluded.enabled_columns,
            mode=excluded.mode, updated_at=excluded.updated_at
        """,
        (file_path, sheet_name, start_cell, json.dumps(enabled_columns), mode, now),
    )


def get_tracked_excel_rows(conn: sqlite3.Connection, file_path: str, sheet_name: str) -> list:
    return conn.execute(
        "SELECT * FROM excel_generated_rows WHERE file_path=? AND sheet_name=? ORDER BY row_number ASC",
        (file_path, sheet_name),
    ).fetchall()


def get_tracked_excel_package_keys(conn: sqlite3.Connection, file_path: str, sheet_name: str) -> set:
    rows = conn.execute(
        "SELECT package_key FROM excel_generated_rows WHERE file_path=? AND sheet_name=?",
        (file_path, sheet_name),
    ).fetchall()
    return {r["package_key"] for r in rows}


def clear_tracked_excel_rows(conn: sqlite3.Connection, file_path: str, sheet_name: str) -> None:
    conn.execute(
        "DELETE FROM excel_generated_rows WHERE file_path=? AND sheet_name=?",
        (file_path, sheet_name),
    )


def add_tracked_excel_row(
    conn: sqlite3.Connection, file_path: str, sheet_name: str, package_key: str, row_number: int
) -> None:
    conn.execute(
        "INSERT INTO excel_generated_rows (file_path, sheet_name, package_key, row_number, written_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (file_path, sheet_name, package_key, row_number, _now()),
    )
