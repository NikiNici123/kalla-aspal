"""
Same idea as services/comparison_service.py, but for the homepage
("Beranda") summary scrape instead of the full /lelang list - see
scraper/lpse_homepage_scraper.py and database/models.py for why these two
datasets are kept separate end-to-end (separate scraper, separate tables,
separate service, separate UI tab).

This one is intentionally a bit simpler: no per-field change-history log
(package_snapshots has no homepage equivalent yet) - just new / existing /
updated counts, since the main point of this dataset is the registration
deadline, not tracking every field change over time.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Optional

from scraper import lpse_homepage_scraper
from scraper.lpse_scraper import LPSEScraperError
from services import keyword_service
from database import database as db

TRACKED_FIELDS = ("section", "kategori", "nama_paket", "hps_value", "akhir_pendaftaran_at")


@dataclass
class HomepageRegionResult:
    region_identifier: str
    success: bool
    error_message: Optional[str] = None
    total_found: int = 0
    relevant_found: int = 0


@dataclass
class HomepageScrapeSummary:
    run_id: int
    new_packages: list = field(default_factory=list)
    updated_packages: list = field(default_factory=list)
    existing_packages: list = field(default_factory=list)
    region_results: list = field(default_factory=list)

    @property
    def total_packages_found(self) -> int:
        return sum(r.total_found for r in self.region_results)

    @property
    def relevant_packages_found(self) -> int:
        return sum(r.relevant_found for r in self.region_results)


def _diff_summary(existing_row: sqlite3.Row, pkg_dict: dict) -> Optional[str]:
    changes = []
    if existing_row["section"] != pkg_dict["section"]:
        changes.append(f"Bagian berubah: {existing_row['section']} -> {pkg_dict['section']}")
    if existing_row["kategori"] != pkg_dict["kategori"]:
        changes.append(f"Kategori berubah: {existing_row['kategori']} -> {pkg_dict['kategori']}")
    if existing_row["hps_value"] != pkg_dict["hps_value"]:
        changes.append(f"HPS berubah: {existing_row['hps_text']} -> {pkg_dict['hps_text']}")
    if existing_row["akhir_pendaftaran_at"] != pkg_dict["akhir_pendaftaran_at"]:
        changes.append(
            f"Akhir Pendaftaran berubah: {existing_row['akhir_pendaftaran_text']} -> "
            f"{pkg_dict['akhir_pendaftaran_text']}"
        )
    if existing_row["nama_paket"] != pkg_dict["nama_paket"]:
        changes.append("Nama paket berubah")
    return "; ".join(changes) if changes else None


def run_homepage_scrape_and_compare(conn: sqlite3.Connection, region_identifiers: list) -> HomepageScrapeSummary:
    """Scrape each region's homepage summary, filter to road-related
    packages, and store/compare against `homepage_packages`. Mirrors
    comparison_service.run_scrape_and_compare's error-isolation behaviour:
    one region failing doesn't stop the others."""
    run_id = db.start_homepage_scrape_run(conn, region_identifiers)
    summary = HomepageScrapeSummary(run_id=run_id)

    keywords = [
        keyword_service.Keyword(id=row["id"], keyword=row["keyword"], is_enabled=bool(row["is_enabled"]))
        for row in db.get_enabled_keywords(conn)
    ]

    any_error = False

    for region_identifier in region_identifiers:
        result = HomepageRegionResult(region_identifier=region_identifier, success=False)
        try:
            packages = lpse_homepage_scraper.get_homepage_summary(region_identifier)
            result.total_found = len(packages)

            relevant = keyword_service.filter_relevant(packages, keywords)
            result.relevant_found = len(relevant)
            result.success = True

            for pkg in relevant:
                pkg_dict = pkg.to_dict()
                existing_row = db.get_homepage_package_by_key(conn, pkg.package_id, pkg.fingerprint)

                if existing_row is None:
                    db.insert_homepage_package(conn, pkg_dict)
                    summary.new_packages.append(pkg_dict)
                else:
                    diff = _diff_summary(existing_row, pkg_dict)
                    if diff:
                        db.update_homepage_package(conn, existing_row, pkg_dict)
                        pkg_dict["_change_summary"] = diff
                        summary.updated_packages.append(pkg_dict)
                    else:
                        db.touch_homepage_package_last_seen(conn, existing_row)
                        summary.existing_packages.append(pkg_dict)

        except LPSEScraperError as exc:
            result.error_message = exc.user_message
            any_error = True
        except Exception as exc:  # noqa: BLE001 - last-resort safety net
            result.error_message = f"Terjadi kesalahan tak terduga: {exc}"
            any_error = True

        summary.region_results.append(result)

    db.finish_homepage_scrape_run(
        conn,
        run_id,
        total_packages_found=summary.total_packages_found,
        relevant_packages_found=summary.relevant_packages_found,
        new_packages_found=len(summary.new_packages),
        updated_packages_found=len(summary.updated_packages),
        status="completed" if any(r.success for r in summary.region_results) or not any_error else "failed",
    )

    return summary
