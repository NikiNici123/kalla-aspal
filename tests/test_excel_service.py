from database import database as db
from services import excel_service


def _make_package_row(conn, package_id, nama_paket="Peningkatan Jalan Raya", hps_value=1_500_000_000.0):
    """Insert a minimal relevant package directly (bypassing the scraper),
    then return it as it would come back from get_relevant_packages."""
    db.insert_package(
        conn,
        {
            "package_id": package_id, "fingerprint": None, "region_identifier": "singkawangkota",
            "nama_paket": nama_paket, "nama_paket_raw": nama_paket, "badges": [],
            "instansi": "Dinas PU", "tahapan": "Tender", "metode_kualifikasi": "",
            "jenis": "Tender", "metode_evaluasi": "", "jenis_pengadaan": "Konstruksi",
            "tahun_anggaran": "2026", "hps_text": "1,5 M", "hps_value": hps_value,
            "nilai_kontrak_text": None, "nilai_kontrak_value": None,
            "evaluasi_ulang": False, "penawaran_ulang": False, "konsolidasi": False, "oap_only": False,
            "package_url": f"https://spse.inaproc.id/singkawangkota/lelang/{package_id}/pengumumanlelang",
            "is_relevant": True, "matched_keywords": ["jalan"],
        },
    )


def test_create_new_excel_file_writes_header_above_start_cell(tmp_path):
    file_path = tmp_path / "monitoring.xlsx"
    excel_service.create_new_excel_file(file_path, "Data LPSE", "A5", excel_service.DEFAULT_COLUMN_ORDER)

    assert file_path.exists()
    import openpyxl
    wb = openpyxl.load_workbook(file_path)
    ws = wb["Data LPSE"]
    assert ws.cell(row=4, column=1).value == "No."
    assert ws.cell(row=4, column=2).value == "Nama Paket"


def test_create_new_excel_file_refuses_to_overwrite(tmp_path):
    file_path = tmp_path / "monitoring.xlsx"
    excel_service.create_new_excel_file(file_path, "Data LPSE", "A5", excel_service.DEFAULT_COLUMN_ORDER)
    try:
        excel_service.create_new_excel_file(file_path, "Data LPSE", "A5", excel_service.DEFAULT_COLUMN_ORDER)
        assert False, "expected ExcelServiceError"
    except excel_service.ExcelServiceError as exc:
        assert "sudah ada" in exc.user_message


def test_export_packages_always_backs_up_first(tmp_path):
    db_path = tmp_path / "test.db"
    db.init_db(db_path)
    file_path = tmp_path / "monitoring.xlsx"
    excel_service.create_new_excel_file(file_path, "Data LPSE", "A5", excel_service.DEFAULT_COLUMN_ORDER)

    excel_service.BACKUPS_DIR = tmp_path / "backups"

    with db.connect(db_path) as conn:
        _make_package_row(conn, "1001")
        rows = db.get_relevant_packages(conn)
        config = {
            "file_path": str(file_path), "sheet_name": "Data LPSE", "start_cell": "A5",
            "enabled_columns": excel_service.DEFAULT_COLUMN_ORDER, "mode": "replace",
        }
        result = excel_service.export_packages(conn, rows, config)

    assert result.rows_written == 1
    assert (tmp_path / "backups").exists()
    assert len(list((tmp_path / "backups").glob("*.xlsx"))) == 1


def test_export_packages_replace_mode_clears_previous_rows(tmp_path):
    db_path = tmp_path / "test.db"
    db.init_db(db_path)
    file_path = tmp_path / "monitoring.xlsx"
    excel_service.create_new_excel_file(file_path, "Data LPSE", "A5", excel_service.DEFAULT_COLUMN_ORDER)
    excel_service.BACKUPS_DIR = tmp_path / "backups"

    with db.connect(db_path) as conn:
        _make_package_row(conn, "1001", nama_paket="Paket Satu")
        _make_package_row(conn, "1002", nama_paket="Paket Dua")
        config = {
            "file_path": str(file_path), "sheet_name": "Data LPSE", "start_cell": "A5",
            "enabled_columns": excel_service.DEFAULT_COLUMN_ORDER, "mode": "replace",
        }
        rows = db.get_relevant_packages(conn)
        excel_service.export_packages(conn, rows, config)

        # Now only one package remains relevant (simulate the other having
        # dropped off) - a second "replace" export should leave exactly one
        # data row behind, not two.
        rows2 = [r for r in db.get_relevant_packages(conn) if r["package_id"] == "1001"]
        excel_service.export_packages(conn, rows2, config)

    import openpyxl
    wb = openpyxl.load_workbook(file_path)
    ws = wb["Data LPSE"]
    assert ws.cell(row=5, column=2).value == "Paket Satu"
    assert ws.cell(row=6, column=2).value is None


def test_export_packages_append_new_mode_only_adds_untracked(tmp_path):
    db_path = tmp_path / "test.db"
    db.init_db(db_path)
    file_path = tmp_path / "monitoring.xlsx"
    excel_service.create_new_excel_file(file_path, "Data LPSE", "A5", excel_service.DEFAULT_COLUMN_ORDER)
    excel_service.BACKUPS_DIR = tmp_path / "backups"

    with db.connect(db_path) as conn:
        _make_package_row(conn, "1001", nama_paket="Paket Satu")
        config = {
            "file_path": str(file_path), "sheet_name": "Data LPSE", "start_cell": "A5",
            "enabled_columns": excel_service.DEFAULT_COLUMN_ORDER, "mode": "append_new",
        }
        rows = db.get_relevant_packages(conn)
        r1 = excel_service.export_packages(conn, rows, config)
        assert r1.rows_written == 1

        _make_package_row(conn, "1002", nama_paket="Paket Dua")
        rows2 = db.get_relevant_packages(conn)
        r2 = excel_service.export_packages(conn, rows2, config)
        assert r2.rows_written == 1  # only the new one

    import openpyxl
    wb = openpyxl.load_workbook(file_path)
    ws = wb["Data LPSE"]
    assert ws.cell(row=5, column=2).value == "Paket Satu"
    assert ws.cell(row=6, column=2).value == "Paket Dua"


def test_export_packages_untracked_cells_outside_range_untouched(tmp_path):
    db_path = tmp_path / "test.db"
    db.init_db(db_path)
    file_path = tmp_path / "monitoring.xlsx"
    excel_service.create_new_excel_file(file_path, "Data LPSE", "A5", excel_service.DEFAULT_COLUMN_ORDER)
    excel_service.BACKUPS_DIR = tmp_path / "backups"

    import openpyxl
    wb = openpyxl.load_workbook(file_path)
    ws = wb["Data LPSE"]
    ws.cell(row=1, column=1).value = "Catatan manual staff - jangan dihapus"
    ws.cell(row=20, column=1).value = "Data lain milik user"
    wb.save(file_path)

    with db.connect(db_path) as conn:
        _make_package_row(conn, "1001")
        config = {
            "file_path": str(file_path), "sheet_name": "Data LPSE", "start_cell": "A5",
            "enabled_columns": excel_service.DEFAULT_COLUMN_ORDER, "mode": "replace",
        }
        rows = db.get_relevant_packages(conn)
        excel_service.export_packages(conn, rows, config)

    wb2 = openpyxl.load_workbook(file_path)
    ws2 = wb2["Data LPSE"]
    assert ws2.cell(row=1, column=1).value == "Catatan manual staff - jangan dihapus"
    assert ws2.cell(row=20, column=1).value == "Data lain milik user"


def test_export_packages_missing_file_raises_friendly_error(tmp_path):
    db_path = tmp_path / "test.db"
    db.init_db(db_path)
    with db.connect(db_path) as conn:
        config = {
            "file_path": str(tmp_path / "tidak_ada.xlsx"), "sheet_name": "Data LPSE",
            "start_cell": "A5", "enabled_columns": excel_service.DEFAULT_COLUMN_ORDER, "mode": "replace",
        }
        try:
            excel_service.export_packages(conn, [], config)
            assert False, "expected ExcelServiceError"
        except excel_service.ExcelServiceError as exc:
            assert "tidak ditemukan" in exc.user_message
