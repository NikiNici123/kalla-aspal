"""
Tests for scraper/lpse_homepage_scraper.py, using REAL HTML fragments
captured from https://spse.inaproc.id/kalbarprov/ (via browser devtools,
fetched with credentials:'omit' to confirm no login/session is needed)
during development. No network access needed to run these.
"""

from bs4 import BeautifulSoup

from scraper.lpse_homepage_scraper import (
    _extract_rows_from_table,
    _is_non_tender_table,
    parse_deadline_text,
)

# A trimmed but verbatim excerpt of the "Tender" table from kalbarprov's
# homepage: one empty category, then "Pekerjaan Konstruksi" with 2 of its
# real rows (trimmed from 5 for brevity - the parsing logic doesn't care
# how many rows a category has).
TENDER_TABLE_HTML = """
<table class="table table-sm">
    <thead>
    <tr><th width="5%">No</th><th scope="col">Nama Paket</th><th class="center" scope="col">HPS</th><th class="center" width="170">Akhir Pendaftaran</th></tr>
    </thead>
    <tbody>
    <tr><td colspan="4" style="background-color: #ffffff"><a href="#"><b>Pengadaan Barang</b></a><span class="badge badge-secondary float-right">0</span></td></tr>
    <tr><td colspan="4" style="background-color: #ffffff"><a href="#"><b>Pekerjaan Konstruksi</b></a><span class="badge badge-secondary float-right">2</span></td></tr>
    <tr class="Pekerjaan_Konstruksi" style="background-color: #f5f6f9">
        <td style="text-align: center;">1</td>
        <td><a href="/kalbarprov/lelang/10166709000/pengumumanlelang" target="_blank">PEMELIHARAAN RUTIN JALAN PROV. KALBAR WILAYAH II (KLASTER IV TERSEBAR)</a>&nbsp;
            <span class="badge badge-info">spse 4.5</span> <span class="badge badge-info">Tender</span>
            </td>
        <td class="table-hps"> Rp. 927.897.900,00 </td>
        <td class="center">18 September 2026 12:00</td>
    </tr>
    <tr class="Pekerjaan_Konstruksi" style="background-color: #f5f6f9">
        <td style="text-align: center;">2</td>
        <td><a href="/kalbarprov/lelang/10166425000/pengumumanlelang" target="_blank">PEMELIHARAAN RUTIN JEMBATAN PROVINSI KALIMANTAN BARAT WILAYAH II (TERSEBAR)</a>&nbsp;
            <span class="badge badge-info">spse 4.5</span> <span class="badge badge-info">Tender</span>
            </td>
        <td class="table-hps"> Rp. 1.763.180.700,00 </td>
        <td class="center">15 September 2026 07:30</td>
    </tr>
    </tbody>
</table>
"""

# A trimmed, verbatim excerpt of the "Non Tender" table (note the "pl" class
# and the /nontender/.../pengumumanpl link pattern, both different from Tender).
NON_TENDER_TABLE_HTML = """
<table class="table table-sm pl">
    <thead>
        <tr><th width="5%">No</th><th>Nama Paket</th><th class="center">HPS</th><th class="center" width="170">Akhir Pendaftaran</th></tr>
    </thead>
    <tbody>
    <tr><td colspan="4" style="background-color: #ffffff"><a href="#"><b>Jasa Konsultansi Badan Usaha Non Konstruksi</b></a><span class="badge badge-secondary float-right">1</span></td></tr>
    <tr class="Jasa_Konsultansi_Badan_Usaha_Non_Konstruksi_pl" style="background-color: #f5f6f9">
        <td style="text-align: center;">1</td>
        <td><a href="/kalbarprov/nontender/11040489000/pengumumanpl" target="_blank">Konsultansi Perencanaan Rehabilitasi Ruang Kelas (Program Khusus) SMAS Al - Islah Baitul Mal</a>
            &nbsp;<span class="badge badge-info">spse 4.5</span>
            &nbsp;<span class="badge  badge-info">Pengadaan Langsung</span>
        </td>
        <td class="table-hps">Rp. 9.999.000,00</td>
        <td class="center">14 September 2026 14:59</td>
    </tr>
    </tbody>
</table>
"""


def test_is_non_tender_table_detection():
    tender_soup = BeautifulSoup(TENDER_TABLE_HTML, "html.parser").find("table")
    non_tender_soup = BeautifulSoup(NON_TENDER_TABLE_HTML, "html.parser").find("table")
    assert _is_non_tender_table(tender_soup) is False
    assert _is_non_tender_table(non_tender_soup) is True


def test_parse_deadline_text():
    assert parse_deadline_text("18 September 2026 12:00") == "2026-09-18T12:00"
    assert parse_deadline_text("15 September 2026 07:30") == "2026-09-15T07:30"
    assert parse_deadline_text("") is None
    assert parse_deadline_text("not a date") is None


def test_extract_tender_rows():
    table = BeautifulSoup(TENDER_TABLE_HTML, "html.parser").find("table")
    rows = _extract_rows_from_table(table, "Tender", "kalbarprov")

    assert len(rows) == 2
    first, second = rows

    assert first.package_id == "10166709000"
    assert first.fingerprint is None
    assert first.kategori == "Pekerjaan Konstruksi"
    assert "PEMELIHARAAN RUTIN JALAN" in first.nama_paket
    assert first.badges == ["spse 4.5", "Tender"]
    assert first.hps_value == 927_897_900.0
    assert first.akhir_pendaftaran_text == "18 September 2026 12:00"
    assert first.akhir_pendaftaran_at == "2026-09-18T12:00"
    assert first.package_url == (
        "https://spse.inaproc.id/kalbarprov/lelang/10166709000/pengumumanlelang"
    )
    assert first.display_position == 1

    assert second.package_id == "10166425000"
    assert second.akhir_pendaftaran_at == "2026-09-15T07:30"


def test_extract_non_tender_rows_use_different_url_pattern():
    table = BeautifulSoup(NON_TENDER_TABLE_HTML, "html.parser").find("table")
    rows = _extract_rows_from_table(table, "Non Tender", "kalbarprov")

    assert len(rows) == 1
    row = rows[0]
    assert row.package_id == "11040489000"
    assert row.section == "Non Tender"
    assert row.kategori == "Jasa Konsultansi Badan Usaha Non Konstruksi"
    assert row.badges == ["spse 4.5", "Pengadaan Langsung"]
    assert row.package_url == (
        "https://spse.inaproc.id/kalbarprov/nontender/11040489000/pengumumanpl"
    )
    assert row.hps_value == 9_999_000.0
