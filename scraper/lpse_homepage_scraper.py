"""
LPSE / SPSE *homepage* summary scraper.

This is a SEPARATE, deliberately independent scraper from
scraper/lpse_scraper.py (which handles the full tender list at
/{region}/lelang). This module handles the region's homepage:

    https://spse.inaproc.id/{region}/

The user asked to keep these two scrapes clearly apart ("kinda separate
them too so easier for me to notice") because they answer different
questions:

  - lpse_scraper.py (/lelang)      -> EVERY package ever posted this year,
                                       any status (open, closed, failed, ...).
                                       No registration-deadline date.
  - lpse_homepage_scraper.py (/)   -> only what the region's homepage is
                                       currently featuring, grouped by
                                       category, WITH an "Akhir Pendaftaran"
                                       (registration deadline) date/time.
                                       Covers both "Tender" (formal tender)
                                       and "Non Tender" (Pengadaan Langsung /
                                       direct procurement) packages.

--------------------------------------------------------------------------
HOW THIS WAS REVERSE-ENGINEERED:

  Unlike /lelang, the homepage does NOT need a session, cookie, or CSRF
  token at all - a plain anonymous GET to https://spse.inaproc.id/{region}/
  returns the data already baked into the server-rendered HTML (confirmed
  with a `fetch(..., {credentials: 'omit'})` from a fresh browser context -
  the exact same rows show up with zero cookies sent). That makes this
  scraper simpler than the /lelang one: no token, no POST, just GET + parse.

  The page contains exactly two `<table class="table table-sm ...">`
  elements:
    - the "Tender" table:      class="table table-sm"      (no "pl" token)
    - the "Non Tender" table:  class="table table-sm pl"   (has "pl" token,
                                short for "Pengadaan Langsung")
  We tell them apart by checking for that "pl" class token rather than by
  position on the page, so this keeps working even if the page's layout
  order ever changes.

  Inside each table, rows come in two shapes:
    1. A CATEGORY HEADER row: a single <td colspan="4"> containing a <b>
       category name (e.g. "Pekerjaan Konstruksi") and a
       <span class="badge ...">N</span> showing how many packages are in
       that category. All the data rows that immediately follow (until the
       next header row) belong to that category.
    2. A DATA row (4 plain <td> cells): No / Nama Paket (with a link to the
       package + badges like "spse 4.5" and "Tender"/"Pengadaan Langsung")
       / HPS / Akhir Pendaftaran.

  The package link differs by section:
    - Tender:     /{region}/lelang/{package_id}/pengumumanlelang
    - Non Tender: /{region}/nontender/{package_id}/pengumumanpl
  Both embed the same kind of numeric Package ID used by /lelang's "Kode
  Lelang", so a package_id found here can, in principle, be cross-referenced
  with the main packages table later (not done automatically yet - see
  README "Limitations").

  IMPORTANT ASSUMPTION (not fully verified): the badge count next to each
  category (e.g. "5") appears to equal the number of rows actually present
  for that category in every case observed so far, suggesting the homepage
  shows ALL currently-open packages per category rather than a truncated
  preview. If a region ever has a lot of open packages in one category,
  double-check whether the site truncates the list - this hasn't been
  tested against a large category.
--------------------------------------------------------------------------
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from scraper.lpse_scraper import (
    PORTAL_BASE,
    DEFAULT_HEADERS,
    LPSEConnectionError,
    LPSERegionNotFoundError,
    LPSEScraperError,
    parse_rupiah_text,
    make_fallback_fingerprint,
)

_MONTHS_ID = {
    "januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "agustus": 8, "september": 9, "oktober": 10, "november": 11,
    "desember": 12,
}
_DEADLINE_RE = re.compile(r"(\d{1,2})\s+(\w+)\s+(\d{4})\s+(\d{1,2}):(\d{2})")

_PACKAGE_ID_RE = re.compile(r"/(?:lelang|nontender)/(\d+)/")


@dataclass
class HomepagePackage:
    """One row from the region homepage's Tender/Non Tender summary."""

    package_id: Optional[str]
    region_identifier: str
    section: str  # "Tender" or "Non Tender"
    kategori: str  # e.g. "Pekerjaan Konstruksi"
    nama_paket: str
    fingerprint: Optional[str] = None  # only set when package_id couldn't be read from the link
    badges: list = field(default_factory=list)  # e.g. ["spse 4.5", "Tender"]
    hps_text: str = ""
    hps_value: Optional[float] = None
    akhir_pendaftaran_text: str = ""
    akhir_pendaftaran_at: Optional[str] = None  # ISO datetime string, or None
    display_position: Optional[int] = None  # the site's own "No" column
    package_url: Optional[str] = None
    scraped_at: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def parse_deadline_text(text: str) -> Optional[str]:
    """Parse an Indonesian-formatted deadline like '18 September 2026 12:00'
    into an ISO datetime string. Returns None if it doesn't match (e.g.
    empty / unexpected format)."""
    if not text:
        return None
    match = _DEADLINE_RE.search(text.strip())
    if not match:
        return None
    day, month_name, year, hour, minute = match.groups()
    month = _MONTHS_ID.get(month_name.strip().lower())
    if not month:
        return None
    try:
        dt = datetime(int(year), month, int(day), int(hour), int(minute))
    except ValueError:
        return None
    return dt.isoformat(timespec="minutes")


def build_homepage_url(region_identifier: str) -> str:
    return f"{PORTAL_BASE}/{region_identifier}/"


def _is_non_tender_table(table) -> bool:
    classes = table.get("class") or []
    return "pl" in classes


def _extract_rows_from_table(table, section: str, region_identifier: str) -> list:
    packages = []
    current_category = None
    now = datetime.now().isoformat(timespec="seconds")

    for row in table.find_all("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) == 1 and cells[0].get("colspan"):
            # Category header row, e.g. "Pekerjaan Konstruksi (5)"
            bold = cells[0].find("b")
            current_category = bold.get_text(strip=True) if bold else cells[0].get_text(strip=True)
            continue

        if len(cells) != 4:
            continue  # not a data row we recognise - skip defensively

        no_cell, nama_cell, hps_cell, deadline_cell = cells

        link = nama_cell.find("a", href=True)
        nama_paket = link.get_text(strip=True) if link else nama_cell.get_text(strip=True)
        href = link["href"] if link else ""
        id_match = _PACKAGE_ID_RE.search(href)
        package_id = id_match.group(1) if id_match else None
        package_url = f"{PORTAL_BASE}{href}" if href.startswith("/") else (href or None)

        badges = [span.get_text(strip=True) for span in nama_cell.find_all("span", class_="badge")]

        hps_text = hps_cell.get_text(strip=True)
        deadline_text = deadline_cell.get_text(strip=True)

        try:
            display_position = int(no_cell.get_text(strip=True))
        except ValueError:
            display_position = None

        hps_value = parse_rupiah_text(hps_text)
        fingerprint = None
        if not package_id:
            # Same fallback approach as scraper/lpse_scraper.py - see
            # make_fallback_fingerprint's docstring for the reasoning.
            fingerprint = make_fallback_fingerprint(
                region_identifier, nama_paket, section, hps_value
            )

        packages.append(
            HomepagePackage(
                package_id=package_id,
                region_identifier=region_identifier,
                section=section,
                kategori=current_category or "",
                nama_paket=nama_paket,
                fingerprint=fingerprint,
                badges=badges,
                hps_text=hps_text,
                hps_value=hps_value,
                akhir_pendaftaran_text=deadline_text,
                akhir_pendaftaran_at=parse_deadline_text(deadline_text),
                display_position=display_position,
                package_url=package_url,
                scraped_at=now,
            )
        )

    return packages


def get_homepage_summary(region_identifier: str, timeout: int = 20) -> list:
    """Fetch and parse https://spse.inaproc.id/{region}/'s Tender + Non
    Tender summary tables. No session/token needed - see module docstring."""
    url = build_homepage_url(region_identifier)
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        raise LPSEConnectionError(
            f"Gagal terhubung ke beranda LPSE ({region_identifier}). Periksa koneksi internet Anda.",
            str(exc),
        ) from exc

    final_host_path = resp.url.rstrip("/")
    if final_host_path == PORTAL_BASE.rstrip("/") and region_identifier not in resp.url:
        raise LPSERegionNotFoundError(
            f"Wilayah LPSE '{region_identifier}' tidak ditemukan.",
            f"GET {url} redirected away from the region ({resp.url}); the region identifier is likely wrong.",
        )

    soup = BeautifulSoup(resp.text, "html.parser")
    tables = soup.find_all("table", class_="table-sm")
    if not tables:
        raise LPSEScraperError(
            f"Gagal membaca beranda LPSE {region_identifier} (format halaman berubah).",
            "No table.table-sm elements found on the homepage; the site's front-end may have changed.",
        )

    all_packages = []
    for table in tables:
        section = "Non Tender" if _is_non_tender_table(table) else "Tender"
        all_packages.extend(_extract_rows_from_table(table, section, region_identifier))

    return all_packages
