"""
Ties the scraper + keyword filter + database together: scrape one or more
regions, keep only road-related packages, and work out what's NEW,
EXISTING (unchanged), or UPDATED compared to what's already in SQLite.

This is the module app.py (and, later, a scheduler) should call - it's the
one place that knows the end-to-end "check for new tenders" workflow.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Optional

from scraper import lpse_scraper
from scraper.lpse_scraper import LPSEScraperError
from services import keyword_service
from database import database as db

# Fields that, if changed, make an already-known package "Updated" rather
# than just "seen again unchanged". Kept as a simple tuple so it's obvious
# at a glance what we consider a meaningful change.
TRACKED_FIELDS = ("tahapan", "hps_value", "nilai_kontrak_value", "nama_paket")


@dataclass
class RegionResult:
    region_identifier: str
    success: bool
    error_message: Optional[str] = None
    total_found: int = 0
    relevant_found: int = 0


@dataclass
class ScrapeSummary:
    run_id: int
    new_packages: list = field(default_factory=list)
    updated_packages: list = field(default_factory=list)
    existing_packages: list = field(default_factory=list)
    region_results: list = field(default_factory=list)  # list[RegionResult]

    @property
    def total_packages_found(self) -> int:
        return sum(r.total_found for r in self.region_results)

    @property
    def relevant_packages_found(self) -> int:
        return sum(r.relevant_found for r in self.region_results)


def _row_key(row_or_dict) -> str:
    """The identifier used to match a package across scrapes: package_id
    when present, otherwise the fallback fingerprint."""
    package_id = row_or_dict["package_id"] if row_or_dict["package_id"] else None
    return package_id or row_or_dict["fingerprint"]


def _diff_summary(existing_row: sqlite3.Row, pkg_dict: dict) -> Optional[str]:
    """Human-readable (Indonesian) description of what changed, or None if
    nothing tracked actually changed."""
    changes = []
    if existing_row["tahapan"] != pkg_dict["tahapan"]:
        changes.append(f"Tahapan berubah: {existing_row['tahapan']} -> {pkg_dict['tahapan']}")
    if existing_row["hps_value"] != pkg_dict["hps_value"]:
        changes.append(f"HPS berubah: {existing_row['hps_text']} -> {pkg_dict['hps_text']}")
    if existing_row["nilai_kontrak_value"] != pkg_dict["nilai_kontrak_value"]:
        changes.append(
            f"Nilai Kontrak berubah: {existing_row['nilai_kontrak_text']} -> {pkg_dict['nilai_kontrak_text']}"
        )
    if existing_row["nama_paket"] != pkg_dict["nama_paket"]:
        changes.append("Nama paket berubah")
    return "; ".join(changes) if changes else None


def run_scrape_and_compare(conn: sqlite3.Connection, region_identifiers: list) -> ScrapeSummary:
    """Scrape every given region, filter to road-related packages, store/
    compare them against the database, and return a categorized summary.

    A region that fails to scrape (network error, invalid identifier, etc.)
    does NOT abort the whole run - it's recorded in `region_results` with
    the error, and the remaining regions still get processed. This matters
    because the user may be monitoring several regions at once and one
    LPSE being briefly down shouldn't hide results from the others.
    """
    run_id = db.start_scrape_run(conn, region_identifiers)
    summary = ScrapeSummary(run_id=run_id)

    keywords = [
        keyword_service.Keyword(id=row["id"], keyword=row["keyword"], is_enabled=bool(row["is_enabled"]))
        for row in db.get_enabled_keywords(conn)
    ]

    any_error = False

    for region_identifier in region_identifiers:
        result = RegionResult(region_identifier=region_identifier, success=False)
        try:
            packages = lpse_scraper.get_packages(region_identifier)
            result.total_found = len(packages)

            relevant = keyword_service.filter_relevant(packages, keywords)
            result.relevant_found = len(relevant)
            result.success = True

            for pkg in relevant:
                pkg_dict = pkg.to_dict()
                existing_row = db.get_package_by_key(conn, pkg.package_id, pkg.fingerprint)

                if existing_row is None:
                    db.insert_package(conn, pkg_dict)
                    key = pkg.package_id or pkg.fingerprint
                    db.insert_snapshot(
                        conn, key, run_id, pkg.tahapan, pkg.hps_value, pkg.nilai_kontrak_value,
                        "Pertama kali ditemukan", pkg_dict,
                    )
                    summary.new_packages.append(pkg_dict)
                else:
                    key = _row_key(existing_row)
                    diff = _diff_summary(existing_row, pkg_dict)
                    if diff:
                        db.update_package(conn, existing_row, pkg_dict)
                        db.insert_snapshot(
                            conn, key, run_id, pkg.tahapan, pkg.hps_value, pkg.nilai_kontrak_value,
                            diff, pkg_dict,
                        )
                        pkg_dict["_change_summary"] = diff
                        summary.updated_packages.append(pkg_dict)
                    else:
                        db.touch_package_last_seen(conn, existing_row)
                        summary.existing_packages.append(pkg_dict)

        except LPSEScraperError as exc:
            result.error_message = exc.user_message
            any_error = True
        except Exception as exc:  # noqa: BLE001 - last-resort safety net, see README error handling
            result.error_message = f"Terjadi kesalahan tak terduga: {exc}"
            any_error = True

        summary.region_results.append(result)

    db.finish_scrape_run(
        conn,
        run_id,
        total_packages_found=summary.total_packages_found,
        relevant_packages_found=summary.relevant_packages_found,
        new_packages_found=len(summary.new_packages),
        updated_packages_found=len(summary.updated_packages),
        status="completed" if not any_error or any(r.success for r in summary.region_results) else "failed",
    )

    return summary
