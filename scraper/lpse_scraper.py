"""
LPSE / SPSE tender list scraper.

This module is responsible ONLY for talking to the LPSE (spse.inaproc.id)
website and turning its responses into plain Python dicts. It must not know
anything about the UI, the database, or Excel — see services/ for that.

--------------------------------------------------------------------------
HOW THIS WAS REVERSE-ENGINEERED (kept here so future maintainers don't have
to redo the investigation if the site changes):

  https://spse.inaproc.id/{region}/lelang  is a normal server-rendered page,
  but the actual tender table ("Nama Paket", etc.) is populated client-side
  by jQuery DataTables making a POST request to:

      https://spse.inaproc.id/{region}/dt/lelang?tahun={year}

  This endpoint returns standard DataTables JSON:
      {"draw": ..., "recordsTotal": ..., "recordsFiltered": ..., "data": [[...], ...]}

  Each row in "data" is a plain JSON array (NOT an object) with (at least)
  16 positions. Based on the page's own inline JavaScript
  (search the page source for "tbllelang" / "authenticityToken"), the
  columns are:

      row[0]  Kode Lelang (package id) - numeric string, e.g. "10144220000"
      row[1]  Nama Paket - may already contain inline HTML like
              <span class="badge badge-warning">Tender Ulang</span>
      row[2]  Instansi (K/L/PD) - e.g. "Kota Singkawang"
      row[3]  Tahapan (current tender stage/status) - e.g. "Tender Sudah Selesai"
      row[4]  HPS - abbreviated Indonesian currency text, e.g. "15,9 M", "414,4 Jt"
      row[5]  Metode Kualifikasi - e.g. "Pascakualifikasi Satu File" (hidden column in the UI)
      row[6]  Jenis - "Tender" / "Seleksi" / etc.
      row[7]  Metode Evaluasi - e.g. "Harga Terendah Sistem Gugur"
      row[8]  Jenis Pengadaan + Tahun Anggaran combined, e.g. "Pekerjaan Konstruksi - TA 2026"
      row[9]  Internal SPSE version flag (not directly useful, used by the site's own JS)
      row[10] Nilai Kontrak - text, e.g. "Rp. 15.602.948.688,00" or
              "Nilai Kontrak belum dibuat" if no contract has been signed yet
      row[11] evaluasi ulang flag ("1"/"0")
      row[12] penawaran ulang flag ("1"/"0")
      row[13] konsolidasi flag ("1"/"0")
      row[14] OAP-restricted flag ("1"/"0") - procurement reserved for Orang Asli Papua
      row[15] reserved / unused (observed as null)

  IMPORTANT LIMITATION: this list endpoint does NOT expose an exact HPS
  number (only the abbreviated text) nor a "Pagu Anggaran" field, and it
  does not include an announcement date. Those live on the per-package
  detail pages (".../lelang/{id}/pengumumanlelang" and ".../jadwal"), which
  would require one extra HTTP request per package. That is intentionally
  left out of this first version (see README "Limitations") to keep the
  scraper fast and simple; it can be added later as an optional
  per-package enrichment step.

  The POST to /dt/lelang requires:
    - the session cookies obtained from GETting the /{region}/lelang page
      first (a cookie is set even though it does not show up in
      document.cookie - it is HttpOnly, but `requests.Session` handles it
      transparently).
    - a form field "authenticityToken" whose value is embedded as a plain
      string literal in the page's inline <script> (see
      _extract_authenticity_token). It appears to be issued per page load.

  If the region identifier does not exist, the site redirects to the
  generic https://spse.inaproc.id/ portal page instead of the region's
  page, so we detect invalid regions by checking that the page we fetched
  actually looks like an LPSE tender list page.
--------------------------------------------------------------------------
"""

from __future__ import annotations

import re
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

PORTAL_BASE = "https://spse.inaproc.id"

# A real desktop-browser User-Agent. The site sits behind Cloudflare; an
# obviously non-browser UA increases the odds of being challenged/blocked.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
}


class LPSEScraperError(Exception):
    """Base class for scraper errors. Carries a short Indonesian message
    suitable for showing directly to admin-staff users, plus the original
    technical detail for a collapsible "Detail Error" section."""

    def __init__(self, user_message: str, technical_detail: str = ""):
        super().__init__(user_message)
        self.user_message = user_message
        self.technical_detail = technical_detail or user_message


class LPSERegionNotFoundError(LPSEScraperError):
    """Raised when the region identifier does not correspond to a real LPSE."""


class LPSEConnectionError(LPSEScraperError):
    """Raised for network-level failures (timeout, DNS, connection refused)."""


@dataclass
class Package:
    """A single, cleaned-up tender package, ready for storage/display."""

    package_id: Optional[str]
    fingerprint: Optional[str]  # only set when package_id is missing
    region_identifier: str
    nama_paket: str
    nama_paket_raw: str
    badges: list = field(default_factory=list)  # e.g. ["Tender Ulang"]
    instansi: str = ""
    tahapan: str = ""
    metode_kualifikasi: str = ""
    jenis: str = ""
    metode_evaluasi: str = ""
    jenis_pengadaan: str = ""
    tahun_anggaran: str = ""
    hps_text: str = ""
    hps_value: Optional[float] = None
    nilai_kontrak_text: str = ""
    nilai_kontrak_value: Optional[float] = None
    evaluasi_ulang: bool = False
    penawaran_ulang: bool = False
    konsolidasi: bool = False
    oap_only: bool = False
    package_url: Optional[str] = None
    scraped_at: str = ""

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        return d


def build_lelang_url(region_identifier: str) -> str:
    return f"{PORTAL_BASE}/{region_identifier}/lelang"


def build_dt_url(region_identifier: str, tahun: int) -> str:
    return f"{PORTAL_BASE}/{region_identifier}/dt/lelang?tahun={tahun}"


def build_package_url(region_identifier: str, package_id: str) -> str:
    return f"{PORTAL_BASE}/{region_identifier}/lelang/{package_id}/pengumumanlelang"


_TOKEN_RE = re.compile(r"authenticityToken\s*=\s*['\"]([a-f0-9]+)['\"]")


def _extract_authenticity_token(html: str) -> str:
    match = _TOKEN_RE.search(html)
    if not match:
        raise LPSEScraperError(
            "Gagal membaca halaman LPSE (format halaman berubah).",
            "Could not find authenticityToken in page HTML; the site's "
            "front-end may have changed and the scraper needs updating.",
        )
    return match.group(1)


def _looks_like_valid_lelang_page(html: str) -> bool:
    """Heuristic check that we actually landed on a region's tender list
    page, rather than being redirected to the generic portal home (which
    happens for an unknown region identifier)."""
    return 'id="tbllelang"' in html or "tbllelang" in html


def fetch_authenticity_token(
    region_identifier: str, session: requests.Session, timeout: int = 20
) -> str:
    """GET the region's /lelang page to establish a session cookie and read
    the CSRF-style token needed for the data POST request."""
    url = build_lelang_url(region_identifier)
    try:
        resp = session.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        raise LPSEConnectionError(
            f"Gagal terhubung ke LPSE ({region_identifier}). Periksa koneksi internet Anda.",
            str(exc),
        ) from exc

    final_host_path = resp.url.rstrip("/")
    if final_host_path == PORTAL_BASE or not _looks_like_valid_lelang_page(resp.text):
        raise LPSERegionNotFoundError(
            f"Wilayah LPSE '{region_identifier}' tidak ditemukan.",
            f"GET {url} did not return a valid tender-list page "
            f"(final URL was {resp.url}); the region identifier is likely wrong.",
        )

    return _extract_authenticity_token(resp.text)


def fetch_raw_rows(
    region_identifier: str,
    tahun: Optional[int] = None,
    session: Optional[requests.Session] = None,
    page_size: int = 100,
    max_pages: int = 50,
    timeout: int = 20,
) -> list:
    """Fetch every raw DataTables row for a region/year, handling pagination
    defensively (some LPSE deployments appear to ignore start/length and just
    return everything in one go; others paginate normally - we handle both
    without assuming which one we're talking to)."""

    tahun = tahun or datetime.now().year
    own_session = session is None
    session = session or requests.Session()

    try:
        token = fetch_authenticity_token(region_identifier, session, timeout=timeout)
        dt_url = build_dt_url(region_identifier, tahun)

        all_rows = []
        seen_ids = set()
        start = 0
        draw = 1

        for _ in range(max_pages):
            body = {
                "draw": str(draw),
                "start": str(start),
                "length": str(page_size),
                "authenticityToken": token,
            }
            try:
                resp = session.post(
                    dt_url,
                    data=body,
                    headers={**DEFAULT_HEADERS, "X-Requested-With": "XMLHttpRequest"},
                    timeout=timeout,
                )
                resp.raise_for_status()
                payload = resp.json()
            except requests.exceptions.RequestException as exc:
                raise LPSEConnectionError(
                    f"Gagal mengambil data dari LPSE {region_identifier}.", str(exc)
                ) from exc
            except ValueError as exc:
                raise LPSEScraperError(
                    f"Data dari LPSE {region_identifier} tidak dapat dibaca (bukan format JSON).",
                    f"Response was not valid JSON: {resp.text[:500]!r}",
                ) from exc

            page_rows = payload.get("data", [])
            if not page_rows:
                break

            new_rows_this_page = 0
            for row in page_rows:
                row_id = row[0] if row else None
                if row_id is not None and row_id in seen_ids:
                    continue
                if row_id is not None:
                    seen_ids.add(row_id)
                all_rows.append(row)
                new_rows_this_page += 1

            # Safety net: if the server ignored start/length and just handed
            # back the same full set again, new_rows_this_page will be 0 and
            # we stop instead of looping forever.
            if new_rows_this_page == 0:
                break
            if len(page_rows) < page_size:
                break

            start += page_size
            draw += 1
            time.sleep(0.2)  # be polite to the server between pages

        return all_rows
    finally:
        if own_session:
            session.close()


# ---------------------------------------------------------------------------
# Row cleaning / parsing helpers
# ---------------------------------------------------------------------------

def _clean_nama_paket(raw: str) -> tuple:
    """Split the raw 'Nama Paket' HTML fragment into (clean_text, badges).

    The list endpoint can already embed status badges directly into the
    package name, e.g.:
        "Peningkatan Jalan XYZ <span class='badge badge-warning'>Tender Ulang</span>"

    The badge spans are removed from the text (not just skipped) before
    extracting the plain package name, so their label text ("Tender Ulang")
    doesn't end up duplicated inside `nama_paket` - it's only returned in
    `badges`.
    """
    if not raw:
        return "", []
    soup = BeautifulSoup(raw, "html.parser")
    badges = []
    for span in soup.find_all("span", class_="badge"):
        badges.append(span.get_text(strip=True))
        span.decompose()
    clean = soup.get_text(separator=" ", strip=True)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean, badges


_HPS_RE = re.compile(r"^\s*([\d.,]+)\s*(M|Jt|Rb)?\s*$", re.I)
_MULTIPLIERS = {"m": 1_000_000_000, "jt": 1_000_000, "rb": 1_000}


def parse_hps_text(text: str) -> Optional[float]:
    """Parse abbreviated Indonesian currency text like '15,9 M' or '414,4 Jt'
    into a float (in full Rupiah). Returns None if it can't be parsed
    (e.g. empty string)."""
    if not text:
        return None
    match = _HPS_RE.match(text.strip())
    if not match:
        return None
    number_part, suffix = match.groups()
    # Indonesian formatting: '.' groups thousands, ',' is the decimal point.
    number_part = number_part.replace(".", "").replace(",", ".")
    try:
        value = float(number_part)
    except ValueError:
        return None
    if suffix:
        value *= _MULTIPLIERS.get(suffix.lower(), 1)
    return value


def parse_rupiah_text(text: str) -> Optional[float]:
    """Parse a full Rupiah string like 'Rp. 15.602.948.688,00' into a float.
    Returns None for placeholder text such as 'Nilai Kontrak belum dibuat'."""
    if not text:
        return None
    digits = re.sub(r"[^\d,.-]", "", text)
    if not digits:
        return None
    digits = digits.replace(".", "").replace(",", ".")
    try:
        return float(digits)
    except ValueError:
        return None


def _flag(row: list, index: int) -> bool:
    try:
        return str(row[index]).strip() == "1"
    except (IndexError, TypeError):
        return False


def _safe_get(row: list, index: int, default=""):
    try:
        value = row[index]
        return value if value is not None else default
    except IndexError:
        return default


def make_fallback_fingerprint(
    region_identifier: str, nama_paket: str, jenis: str, hps_value: Optional[float]
) -> str:
    """Build a stable fingerprint for packages that (unexpectedly) have no
    Package ID, so we can still detect duplicates/new packages.

    Fallback logic (per project spec - documented explicitly):
        fingerprint = sha256("region|nama_paket(lowercased, trimmed)|jenis|hps_value")

    This is deliberately based on fields that should stay stable for the
    same real-world package across scrapes, while still being sensitive to
    genuinely different packages that happen to share a similar name.
    """
    import hashlib

    key = f"{region_identifier}|{nama_paket.strip().lower()}|{jenis.strip().lower()}|{hps_value}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def parse_row(row: list, region_identifier: str) -> Package:
    """Turn one raw DataTables row into a clean Package."""
    package_id = _safe_get(row, 0, None)
    package_id = str(package_id) if package_id not in (None, "") else None

    nama_paket_raw = _safe_get(row, 1, "")
    nama_paket, badges = _clean_nama_paket(nama_paket_raw)

    instansi = _safe_get(row, 2, "")
    tahapan = _safe_get(row, 3, "")
    hps_text = _safe_get(row, 4, "")
    metode_kualifikasi = _safe_get(row, 5, "")
    jenis = _safe_get(row, 6, "")
    metode_evaluasi = _safe_get(row, 7, "")
    jenis_pengadaan_tahun = _safe_get(row, 8, "")
    nilai_kontrak_text = _safe_get(row, 10, "")

    jenis_pengadaan = jenis_pengadaan_tahun
    tahun_anggaran = ""
    if " - TA " in jenis_pengadaan_tahun:
        jenis_pengadaan, _, tahun_anggaran = jenis_pengadaan_tahun.partition(" - TA ")

    hps_value = parse_hps_text(hps_text)
    nilai_kontrak_value = parse_rupiah_text(nilai_kontrak_text)

    fingerprint = None
    if not package_id:
        fingerprint = make_fallback_fingerprint(region_identifier, nama_paket, jenis, hps_value)

    package_url = build_package_url(region_identifier, package_id) if package_id else None

    return Package(
        package_id=package_id,
        fingerprint=fingerprint,
        region_identifier=region_identifier,
        nama_paket=nama_paket,
        nama_paket_raw=nama_paket_raw,
        badges=badges,
        instansi=instansi,
        tahapan=tahapan,
        metode_kualifikasi=metode_kualifikasi,
        jenis=jenis,
        metode_evaluasi=metode_evaluasi,
        jenis_pengadaan=jenis_pengadaan.strip(),
        tahun_anggaran=tahun_anggaran.strip(),
        hps_text=hps_text,
        hps_value=hps_value,
        nilai_kontrak_text=nilai_kontrak_text,
        nilai_kontrak_value=nilai_kontrak_value,
        evaluasi_ulang=_flag(row, 11),
        penawaran_ulang=_flag(row, 12),
        konsolidasi=_flag(row, 13),
        oap_only=_flag(row, 14),
        package_url=package_url,
        scraped_at=datetime.now().isoformat(timespec="seconds"),
    )


def get_packages(
    region_identifier: str, tahun: Optional[int] = None, timeout: int = 20
) -> list:
    """Main entry point: scrape a region and return a list of Package."""
    raw_rows = fetch_raw_rows(region_identifier, tahun=tahun, timeout=timeout)
    return [parse_row(row, region_identifier) for row in raw_rows]
