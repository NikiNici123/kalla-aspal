"""
Tests for scraper/lpse_scraper.py parsing logic, using REAL sample rows
captured from https://spse.inaproc.id/singkawangkota/dt/lelang?tahun=2026
(via browser devtools) during development - not invented data. No network
access is needed to run these.
"""

from scraper.lpse_scraper import (
    parse_hps_text,
    parse_rupiah_text,
    parse_row,
    make_fallback_fingerprint,
    _clean_nama_paket,
)

# A row with an embedded status badge in the package name, and a contract
# that HAS been signed.
ROW_WITH_BADGE_AND_CONTRACT = [
    "10144220000",
    "Peningkatan Perkuatan Tebing Sungai Singkawang Segmen II "
    "<span class='badge  badge-warning'>Tender Ulang</span>",
    "Kota Singkawang",
    "Tender Sudah Selesai",
    "15,9 M",
    "Pascakualifikasi Satu File",
    "Tender",
    "Harga Terendah Sistem Gugur",
    "Pekerjaan Konstruksi - TA 2026",
    "5",
    "Rp. 15.602.948.688,00",
    None,
    None,
    "0",
    "0",
    None,
]

# A row that hasn't been awarded yet (no contract value) and has no badge -
# this is the shape we expect for most currently-open tenders.
ROW_PLAIN_JALAN = [
    "10130232000",
    "Peningkatan Jalan Cu Jong Hin (Kong Mui)",
    "Kota Singkawang",
    "Tender Sudah Selesai",
    "3 M",
    "Pascakualifikasi Satu File",
    "Tender",
    "Harga Terendah Sistem Gugur",
    "Pekerjaan Konstruksi - TA 2026",
    "5",
    "Nilai Kontrak belum dibuat",
    "0",
    "0",
    "0",
    "0",
    None,
]


def test_parse_hps_text_miliar():
    assert parse_hps_text("15,9 M") == 15_900_000_000.0


def test_parse_hps_text_juta():
    assert parse_hps_text("414,4 Jt") == 414_400_000.0


def test_parse_hps_text_no_decimal():
    assert parse_hps_text("3 M") == 3_000_000_000.0


def test_parse_hps_text_empty():
    assert parse_hps_text("") is None
    assert parse_hps_text(None) is None


def test_parse_rupiah_text_full_value():
    assert parse_rupiah_text("Rp. 15.602.948.688,00") == 15_602_948_688.00


def test_parse_rupiah_text_not_yet_awarded():
    assert parse_rupiah_text("Nilai Kontrak belum dibuat") is None


def test_clean_nama_paket_strips_badge():
    clean, badges = _clean_nama_paket(ROW_WITH_BADGE_AND_CONTRACT[1])
    assert clean == "Peningkatan Perkuatan Tebing Sungai Singkawang Segmen II"
    assert badges == ["Tender Ulang"]


def test_parse_row_full_fields():
    pkg = parse_row(ROW_WITH_BADGE_AND_CONTRACT, "singkawangkota")
    assert pkg.package_id == "10144220000"
    assert pkg.fingerprint is None  # package_id present, so no fallback needed
    assert pkg.nama_paket == "Peningkatan Perkuatan Tebing Sungai Singkawang Segmen II"
    assert pkg.badges == ["Tender Ulang"]
    assert pkg.instansi == "Kota Singkawang"
    assert pkg.tahapan == "Tender Sudah Selesai"
    assert pkg.hps_value == 15_900_000_000.0
    assert pkg.jenis == "Tender"
    assert pkg.jenis_pengadaan == "Pekerjaan Konstruksi"
    assert pkg.tahun_anggaran == "2026"
    assert pkg.nilai_kontrak_value == 15_602_948_688.00
    assert pkg.package_url == (
        "https://spse.inaproc.id/singkawangkota/lelang/10144220000/pengumumanlelang"
    )


def test_parse_row_road_keyword_candidate():
    pkg = parse_row(ROW_PLAIN_JALAN, "singkawangkota")
    assert "Jalan" in pkg.nama_paket
    assert pkg.nilai_kontrak_value is None  # "belum dibuat" -> unparsable -> None
    assert pkg.hps_value == 3_000_000_000.0


def test_fallback_fingerprint_is_stable():
    fp1 = make_fallback_fingerprint("singkawangkota", "Contoh Paket", "Tender", 1_000_000.0)
    fp2 = make_fallback_fingerprint("singkawangkota", "Contoh Paket", "Tender", 1_000_000.0)
    fp3 = make_fallback_fingerprint("singkawangkota", "Paket Lain", "Tender", 1_000_000.0)
    assert fp1 == fp2
    assert fp1 != fp3


def test_parse_row_missing_package_id_uses_fallback():
    row = ROW_PLAIN_JALAN.copy()
    row[0] = None
    pkg = parse_row(row, "singkawangkota")
    assert pkg.package_id is None
    assert pkg.fingerprint is not None
    assert pkg.package_url is None
