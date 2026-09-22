from services import status_flags


def test_detects_gagal_in_parentheses():
    flags = status_flags.detect_status_flags("Peningkatan Jalan Raya (Tender Gagal)")
    assert "Kemungkinan Tender Gagal" in flags


def test_detects_dibatalkan():
    flags = status_flags.detect_status_flags("Rehabilitasi Jembatan (Dibatalkan)")
    assert "Kemungkinan Dibatalkan" in flags


def test_detects_diulang():
    flags = status_flags.detect_status_flags("Pemeliharaan Jalan - Diulang")
    assert "Kemungkinan Ditenderkan Ulang" in flags


def test_no_false_positive_on_ordinary_name():
    assert status_flags.detect_status_flags("PEMELIHARAAN RUTIN JALAN PROV. KALBAR WILAYAH II (KLASTER I TERSEBAR)") == []


def test_does_not_flag_substring_inside_another_word():
    # "batal" is embedded inside "Pembatalan" (pem-BATAL-an), but the
    # word-boundary regex must not match there - only a standalone
    # "batal"/"dibatalkan" word should trigger the flag.
    assert status_flags.detect_status_flags("Sosialisasi Pembatalan Proyek Non-Jalan") == []


def test_handles_empty_and_none():
    assert status_flags.detect_status_flags("") == []
    assert status_flags.detect_status_flags(None) == []


def test_deduplicates_and_detects_multiple_flags():
    flags = status_flags.detect_status_flags("Jalan Batal Diulang")
    assert flags.count("Kemungkinan Dibatalkan") == 1
    assert "Kemungkinan Ditenderkan Ulang" in flags


def test_comparison_service_reports_old_and_new_name():
    from services.comparison_service import _diff_summary

    # A plain dict already supports row["field"] access, same as the
    # sqlite3.Row objects _diff_summary receives for real - no need for a
    # fake row class.
    existing = {"tahapan": "Tender", "hps_value": 1.0, "nilai_kontrak_value": None, "nama_paket": "Nama Lama"}
    updated = {"tahapan": "Tender", "hps_value": 1.0, "nilai_kontrak_value": None, "nama_paket": "Nama Lama (Tender Gagal)"}
    diff = _diff_summary(existing, updated)
    assert diff is not None
    assert "Nama Lama" in diff and "Nama Lama (Tender Gagal)" in diff


def test_homepage_service_reports_old_and_new_name():
    from services.homepage_service import _diff_summary

    existing = {
        "section": "Tender", "kategori": "Konstruksi", "hps_value": 1.0,
        "akhir_pendaftaran_at": "2026-09-20T00:00:00", "nama_paket": "Nama Lama",
    }
    updated = {
        "section": "Tender", "kategori": "Konstruksi", "hps_value": 1.0,
        "akhir_pendaftaran_at": "2026-09-20T00:00:00", "nama_paket": "Nama Lama (Diulang)",
    }
    diff = _diff_summary(existing, updated)
    assert diff is not None
    assert "Nama Lama" in diff and "Nama Lama (Diulang)" in diff
