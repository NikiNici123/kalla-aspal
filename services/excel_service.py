"""
Excel export for LPSE Monitor (Phase 6).

Exports relevant packages from the `packages` table (the "Daftar Lengkap"
dataset) into ONE reused Excel workbook that senior staff already work
with, rather than generating a new file every time - per the project
brief's "VERY IMPORTANT" Excel section.

Safety rules this module enforces (all non-negotiable, per the brief):
  1. ALWAYS back up the target file before touching it (see backup_file).
  2. NEVER write outside the configured sheet/start-cell area - other
     sheets, and any cell in this sheet the app didn't itself write, are
     left completely alone.
  3. Only ever clear/overwrite rows THIS APP previously wrote, tracked in
     the `excel_generated_rows` table by (file_path, sheet_name,
     row_number) - never "row N happens to look empty, so I'll use it."
  4. Use openpyxl (not pandas) to load/save, which preserves existing
     formatting, formulas, and every other sheet untouched.

Two modes (user picks per export, from the Excel tab):
  - "replace":     clear every row this app previously wrote in that sheet,
                    then write the full current relevant-package list fresh.
  - "append_new":  leave existing rows alone, only add rows for packages
                    that don't have a tracked row yet.

Column mapping is configurable (which columns, in a fixed sensible order -
see DEFAULT_COLUMN_ORDER) rather than hardcoded, per the brief. Note: the
original spec's suggested columns included "Pagu Anggaran", which isn't
available from either scraper (see PROJECT_STATUS.md limitations) - it's
left out rather than filled with a misleading duplicate of HPS.
"""

from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import openpyxl
from openpyxl.utils.cell import coordinate_to_tuple

from database import database as db

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKUPS_DIR = PROJECT_ROOT / "backups"

COLUMN_LABELS = {
    "no": "No.",
    "nama_paket": "Nama Paket",
    "lpse": "LPSE",
    "jenis_pengadaan": "Jenis Pengadaan",
    "status": "Status",
    "hps": "HPS",
    "tanggal_ditemukan": "Tanggal Ditemukan",
    "url": "Package URL",
}
DEFAULT_COLUMN_ORDER = [
    "no", "nama_paket", "lpse", "jenis_pengadaan", "status", "hps", "tanggal_ditemukan", "url",
]


class ExcelServiceError(Exception):
    """Same pattern as LPSEScraperError: a short Indonesian message safe to
    show directly to admin staff, plus technical detail for a collapsible
    "Detail Error" section."""

    def __init__(self, user_message: str, technical_detail: str = ""):
        super().__init__(user_message)
        self.user_message = user_message
        self.technical_detail = technical_detail or user_message


@dataclass
class ExcelExportResult:
    rows_written: int
    mode: str
    backup_path: str
    file_path: str
    sheet_name: str


def _package_key(row: sqlite3.Row) -> str:
    return row["package_id"] or row["fingerprint"]


def _column_value(field_key: str, row: sqlite3.Row, no_value: int):
    if field_key == "no":
        return no_value
    if field_key == "nama_paket":
        return row["nama_paket"]
    if field_key == "lpse":
        return row["region_identifier"]
    if field_key == "jenis_pengadaan":
        return row["jenis_pengadaan"]
    if field_key == "status":
        return row["tahapan"]
    if field_key == "hps":
        return row["hps_value"]
    if field_key == "tanggal_ditemukan":
        return (row["first_seen_at"] or "")[:10] or None
    if field_key == "url":
        return row["package_url"]
    return None


def backup_file(file_path: Path) -> Path:
    """Copy file_path into backups/ with a timestamped name, BEFORE any
    write. Never skipped - see module docstring rule 1."""
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_path = BACKUPS_DIR / f"{file_path.stem}_{timestamp}{file_path.suffix}"
    shutil.copy2(file_path, backup_path)
    return backup_path


def create_new_excel_file(file_path: Path, sheet_name: str, start_cell: str, enabled_columns: list) -> None:
    """Convenience action for a user with no existing workbook yet: creates
    one with a header row directly above start_cell. This is the ONLY
    place this module ever writes a header row - the normal export path
    (export_packages) never touches anything above start_cell, since a
    real office template's headers must be preserved exactly as they are.
    """
    if file_path.exists():
        raise ExcelServiceError(
            f"File '{file_path.name}' sudah ada - tidak akan ditimpa. Gunakan file yang sudah ada, "
            "atau pilih nama/lokasi lain.",
            f"{file_path} already exists.",
        )
    file_path.parent.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name

    start_row, start_col = coordinate_to_tuple(start_cell)
    header_row = start_row - 1
    if header_row >= 1:
        for col_offset, field_key in enumerate(enabled_columns):
            ws.cell(row=header_row, column=start_col + col_offset).value = COLUMN_LABELS.get(field_key, field_key)

    wb.save(file_path)


def export_packages(conn: sqlite3.Connection, packages: list, config: dict) -> ExcelExportResult:
    """Write `packages` (already the relevant, earliest-first list from
    database.get_relevant_packages) into the configured workbook/sheet/
    cell, in the given mode. Always backs up first. Raises
    ExcelServiceError with a ready-to-display Indonesian message on any
    problem (missing file, file locked, bad start cell, ...)."""

    file_path_str = config.get("file_path")
    if not file_path_str:
        raise ExcelServiceError("Belum ada file Excel yang dipilih. Atur di bagian atas tab Excel.")

    file_path = Path(file_path_str)
    if not file_path.exists():
        raise ExcelServiceError(
            f"File Excel tidak ditemukan: {file_path}. Periksa lokasinya, atau buat file baru dahulu.",
            f"Path does not exist: {file_path}",
        )

    sheet_name = config.get("sheet_name") or "Data LPSE"
    start_cell = config.get("start_cell") or "A5"
    enabled_columns = config.get("enabled_columns") or DEFAULT_COLUMN_ORDER
    mode = config.get("mode") or "replace"

    try:
        start_row, start_col = coordinate_to_tuple(start_cell)
    except Exception as exc:
        raise ExcelServiceError(
            f"Sel awal '{start_cell}' tidak valid. Gunakan format seperti 'A5'.", str(exc)
        ) from exc

    backup_path = backup_file(file_path)

    try:
        wb = openpyxl.load_workbook(file_path)
    except PermissionError as exc:
        raise ExcelServiceError(
            f"File Excel '{file_path.name}' sedang terbuka di program lain (mis. Microsoft Excel). "
            "Tutup file tersebut lalu coba lagi.",
            str(exc),
        ) from exc
    except Exception as exc:
        raise ExcelServiceError(
            f"Gagal membuka file Excel '{file_path.name}'. Pastikan ini file .xlsx yang valid.", str(exc)
        ) from exc

    is_new_sheet = sheet_name not in wb.sheetnames
    ws = wb[sheet_name] if not is_new_sheet else wb.create_sheet(sheet_name)

    tracked_rows = db.get_tracked_excel_rows(conn, str(file_path), sheet_name)
    tracked_keys = {r["package_key"] for r in tracked_rows}

    if mode == "replace":
        for tr in tracked_rows:
            for col_offset in range(len(enabled_columns)):
                ws.cell(row=tr["row_number"], column=start_col + col_offset).value = None
        db.clear_tracked_excel_rows(conn, str(file_path), sheet_name)

        rows_to_write = list(packages)
        write_start_row = start_row
        no_start = 1
    elif mode == "append_new":
        rows_to_write = [p for p in packages if _package_key(p) not in tracked_keys]
        write_start_row = (max(tr["row_number"] for tr in tracked_rows) + 1) if tracked_rows else start_row
        no_start = len(tracked_rows) + 1
    else:
        raise ExcelServiceError(f"Mode Excel tidak dikenali: '{mode}'.")

    for i, pkg_row in enumerate(rows_to_write):
        current_row = write_start_row + i
        for col_offset, field_key in enumerate(enabled_columns):
            value = _column_value(field_key, pkg_row, no_start + i)
            ws.cell(row=current_row, column=start_col + col_offset).value = value
        db.add_tracked_excel_row(conn, str(file_path), sheet_name, _package_key(pkg_row), current_row)

    try:
        wb.save(file_path)
    except PermissionError as exc:
        raise ExcelServiceError(
            f"File Excel '{file_path.name}' sedang terbuka di program lain (mis. Microsoft Excel). "
            "Tutup file tersebut lalu coba lagi. Data BELUM ditulis (backup sudah dibuat, file asli aman).",
            str(exc),
        ) from exc

    return ExcelExportResult(
        rows_written=len(rows_to_write), mode=mode, backup_path=str(backup_path),
        file_path=str(file_path), sheet_name=sheet_name,
    )
