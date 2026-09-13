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


def _lelang_config(file_path, mode="replace", use_excel_table=True):
    return {
        "file_path": str(file_path), "sheet_name": "Daftar Lengkap", "start_cell": "A5",
        "enabled_columns": excel_service.DEFAULT_COLUMNS[excel_service.DATASET_LELANG],
        "mode": mode, "use_excel_table": use_excel_table,
    }


def test_create_new_excel_file_writes_header_above_start_cell(tmp_path):
    file_path = tmp_path / "monitoring.xlsx"
    excel_service.create_new_excel_file(
        file_path, "Daftar Lengkap", "A5", excel_service.DEFAULT_COLUMNS[excel_service.DATASET_LELANG],
    )

    assert file_path.exists()
    import openpyxl
    wb = openpyxl.load_workbook(file_path)
    ws = wb["Daftar Lengkap"]
    assert ws.cell(row=4, column=1).value == "No."
    assert ws.cell(row=4, column=2).value == "Nama Paket"


def test_create_new_excel_file_refuses_to_overwrite(tmp_path):
    file_path = tmp_path / "monitoring.xlsx"
    columns = excel_service.DEFAULT_COLUMNS[excel_service.DATASET_LELANG]
    excel_service.create_new_excel_file(file_path, "Daftar Lengkap", "A5", columns)
    try:
        excel_service.create_new_excel_file(file_path, "Daftar Lengkap", "A5", columns)
        assert False, "expected ExcelServiceError"
    except excel_service.ExcelServiceError as exc:
        assert "sudah ada" in exc.user_message


def test_export_packages_always_backs_up_first(tmp_path):
    db_path = tmp_path / "test.db"
    db.init_db(db_path)
    file_path = tmp_path / "monitoring.xlsx"
    excel_service.create_new_excel_file(
        file_path, "Daftar Lengkap", "A5", excel_service.DEFAULT_COLUMNS[excel_service.DATASET_LELANG],
    )
    excel_service.BACKUPS_DIR = tmp_path / "backups"

    with db.connect(db_path) as conn:
        _make_package_row(conn, "1001")
        rows = db.get_relevant_packages(conn)
        result = excel_service.export_packages(conn, rows, _lelang_config(file_path), dataset=excel_service.DATASET_LELANG)

    assert result.rows_written == 1
    assert (tmp_path / "backups").exists()
    assert len(list((tmp_path / "backups").glob("*.xlsx"))) == 1


def test_export_packages_replace_mode_clears_previous_rows(tmp_path):
    db_path = tmp_path / "test.db"
    db.init_db(db_path)
    file_path = tmp_path / "monitoring.xlsx"
    excel_service.create_new_excel_file(
        file_path, "Daftar Lengkap", "A5", excel_service.DEFAULT_COLUMNS[excel_service.DATASET_LELANG],
    )
    excel_service.BACKUPS_DIR = tmp_path / "backups"

    with db.connect(db_path) as conn:
        _make_package_row(conn, "1001", nama_paket="Paket Satu")
        _make_package_row(conn, "1002", nama_paket="Paket Dua")
        config = _lelang_config(file_path)
        rows = db.get_relevant_packages(conn)
        excel_service.export_packages(conn, rows, config, dataset=excel_service.DATASET_LELANG)

        # Now only one package remains relevant (simulate the other having
        # dropped off) - a second "replace" export should leave exactly one
        # data row behind, not two.
        rows2 = [r for r in db.get_relevant_packages(conn) if r["package_id"] == "1001"]
        excel_service.export_packages(conn, rows2, config, dataset=excel_service.DATASET_LELANG)

    import openpyxl
    wb = openpyxl.load_workbook(file_path)
    ws = wb["Daftar Lengkap"]
    assert ws.cell(row=5, column=2).value == "Paket Satu"
    assert ws.cell(row=6, column=2).value is None


def test_export_packages_append_new_mode_only_adds_untracked(tmp_path):
    db_path = tmp_path / "test.db"
    db.init_db(db_path)
    file_path = tmp_path / "monitoring.xlsx"
    excel_service.create_new_excel_file(
        file_path, "Daftar Lengkap", "A5", excel_service.DEFAULT_COLUMNS[excel_service.DATASET_LELANG],
    )
    excel_service.BACKUPS_DIR = tmp_path / "backups"

    with db.connect(db_path) as conn:
        _make_package_row(conn, "1001", nama_paket="Paket Satu")
        config = _lelang_config(file_path, mode="append_new")
        rows = db.get_relevant_packages(conn)
        r1 = excel_service.export_packages(conn, rows, config, dataset=excel_service.DATASET_LELANG)
        assert r1.rows_written == 1

        _make_package_row(conn, "1002", nama_paket="Paket Dua")
        rows2 = db.get_relevant_packages(conn)
        r2 = excel_service.export_packages(conn, rows2, config, dataset=excel_service.DATASET_LELANG)
        assert r2.rows_written == 1  # only the new one

    import openpyxl
    wb = openpyxl.load_workbook(file_path)
    ws = wb["Daftar Lengkap"]
    assert ws.cell(row=5, column=2).value == "Paket Satu"
    assert ws.cell(row=6, column=2).value == "Paket Dua"


def test_export_packages_untracked_cells_outside_range_untouched(tmp_path):
    db_path = tmp_path / "test.db"
    db.init_db(db_path)
    file_path = tmp_path / "monitoring.xlsx"
    excel_service.create_new_excel_file(
        file_path, "Daftar Lengkap", "A5", excel_service.DEFAULT_COLUMNS[excel_service.DATASET_LELANG],
    )
    excel_service.BACKUPS_DIR = tmp_path / "backups"

    import openpyxl
    wb = openpyxl.load_workbook(file_path)
    ws = wb["Daftar Lengkap"]
    ws.cell(row=1, column=1).value = "Catatan manual staff - jangan dihapus"
    ws.cell(row=30, column=1).value = "Data lain milik user"
    wb.save(file_path)

    with db.connect(db_path) as conn:
        _make_package_row(conn, "1001")
        rows = db.get_relevant_packages(conn)
        excel_service.export_packages(conn, rows, _lelang_config(file_path), dataset=excel_service.DATASET_LELANG)

    wb2 = openpyxl.load_workbook(file_path)
    ws2 = wb2["Daftar Lengkap"]
    assert ws2.cell(row=1, column=1).value == "Catatan manual staff - jangan dihapus"
    assert ws2.cell(row=30, column=1).value == "Data lain milik user"


def test_export_packages_missing_file_raises_friendly_error(tmp_path):
    db_path = tmp_path / "test.db"
    db.init_db(db_path)
    with db.connect(db_path) as conn:
        config = _lelang_config(tmp_path / "tidak_ada.xlsx")
        try:
            excel_service.export_packages(conn, [], config, dataset=excel_service.DATASET_LELANG)
            assert False, "expected ExcelServiceError"
        except excel_service.ExcelServiceError as exc:
            assert "tidak ditemukan" in exc.user_message


def test_export_packages_creates_excel_table_by_default(tmp_path):
    db_path = tmp_path / "test.db"
    db.init_db(db_path)
    file_path = tmp_path / "monitoring.xlsx"
    excel_service.create_new_excel_file(
        file_path, "Daftar Lengkap", "A5", excel_service.DEFAULT_COLUMNS[excel_service.DATASET_LELANG],
    )
    excel_service.BACKUPS_DIR = tmp_path / "backups"

    with db.connect(db_path) as conn:
        _make_package_row(conn, "1001")
        _make_package_row(conn, "1002")
        rows = db.get_relevant_packages(conn)
        result = excel_service.export_packages(conn, rows, _lelang_config(file_path), dataset=excel_service.DATASET_LELANG)

    assert result.table_applied is True
    import openpyxl
    wb = openpyxl.load_workbook(file_path)
    ws = wb["Daftar Lengkap"]
    table_name = excel_service.TABLE_NAMES[excel_service.DATASET_LELANG]
    assert table_name in ws.tables
    assert ws.tables[table_name].ref == "A4:H6"


def test_export_packages_table_ref_grows_on_second_export(tmp_path):
    db_path = tmp_path / "test.db"
    db.init_db(db_path)
    file_path = tmp_path / "monitoring.xlsx"
    excel_service.create_new_excel_file(
        file_path, "Daftar Lengkap", "A5", excel_service.DEFAULT_COLUMNS[excel_service.DATASET_LELANG],
    )
    excel_service.BACKUPS_DIR = tmp_path / "backups"
    config = _lelang_config(file_path, mode="append_new")
    table_name = excel_service.TABLE_NAMES[excel_service.DATASET_LELANG]

    with db.connect(db_path) as conn:
        _make_package_row(conn, "1001")
        excel_service.export_packages(conn, db.get_relevant_packages(conn), config, dataset=excel_service.DATASET_LELANG)

        _make_package_row(conn, "1002")
        excel_service.export_packages(conn, db.get_relevant_packages(conn), config, dataset=excel_service.DATASET_LELANG)

    import openpyxl
    wb = openpyxl.load_workbook(file_path)
    ws = wb["Daftar Lengkap"]
    # Same table name, not a second "TabelDaftarLengkap1" - and its range
    # now covers both rows.
    assert list(ws.tables.keys()) == [table_name]
    assert ws.tables[table_name].ref == "A4:H6"


def test_export_packages_skips_table_when_header_cell_blank(tmp_path):
    db_path = tmp_path / "test.db"
    db.init_db(db_path)
    file_path = tmp_path / "monitoring.xlsx"

    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Daftar Lengkap"
    ws["A4"] = "No."
    # B4 (Nama Paket header) left blank on purpose.
    wb.save(file_path)
    excel_service.BACKUPS_DIR = tmp_path / "backups"

    with db.connect(db_path) as conn:
        _make_package_row(conn, "1001")
        rows = db.get_relevant_packages(conn)
        result = excel_service.export_packages(conn, rows, _lelang_config(file_path), dataset=excel_service.DATASET_LELANG)

    assert result.table_applied is False
    assert "header" in result.table_skip_reason.lower()
    # Values are still written even though the table wasn't applied.
    wb2 = openpyxl.load_workbook(file_path)
    assert wb2["Daftar Lengkap"].cell(row=5, column=2).value is not None


def test_export_packages_respects_users_own_manual_table(tmp_path):
    db_path = tmp_path / "test.db"
    db.init_db(db_path)
    file_path = tmp_path / "monitoring.xlsx"
    excel_service.create_new_excel_file(
        file_path, "Daftar Lengkap", "A5", excel_service.DEFAULT_COLUMNS[excel_service.DATASET_LELANG],
    )
    excel_service.BACKUPS_DIR = tmp_path / "backups"

    import openpyxl
    from openpyxl.worksheet.table import Table
    wb = openpyxl.load_workbook(file_path)
    ws = wb["Daftar Lengkap"]
    ws.add_table(Table(displayName="TabelBuatanUser", ref="A4:H6"))
    wb.save(file_path)

    with db.connect(db_path) as conn:
        _make_package_row(conn, "1001")
        rows = db.get_relevant_packages(conn)
        result = excel_service.export_packages(conn, rows, _lelang_config(file_path), dataset=excel_service.DATASET_LELANG)

    assert result.table_applied is False
    wb2 = openpyxl.load_workbook(file_path)
    ws2 = wb2["Daftar Lengkap"]
    assert list(ws2.tables.keys()) == ["TabelBuatanUser"]  # untouched, not replaced


def test_export_packages_beranda_dataset_uses_its_own_columns(tmp_path):
    db_path = tmp_path / "test.db"
    db.init_db(db_path)
    file_path = tmp_path / "beranda.xlsx"
    columns = excel_service.DEFAULT_COLUMNS[excel_service.DATASET_BERANDA]
    excel_service.create_new_excel_file(file_path, "Ringkasan Beranda", "A5", columns)
    excel_service.BACKUPS_DIR = tmp_path / "backups"

    with db.connect(db_path) as conn:
        db.insert_homepage_package(
            conn,
            {
                "package_id": "2001", "fingerprint": None, "region_identifier": "kalbarprov",
                "section": "Tender", "kategori": "Pekerjaan Konstruksi", "nama_paket": "Peningkatan Jalan Z",
                "badges": [], "hps_text": "2 M", "hps_value": 2_000_000_000.0,
                "akhir_pendaftaran_text": "20 Sep 2026 23:59", "akhir_pendaftaran_at": "2026-09-20T23:59:00",
                "display_position": 1, "package_url": "https://spse.inaproc.id/kalbarprov/nontender/2001/pengumumanlelang",
                "is_relevant": True, "matched_keywords": ["jalan"],
            },
        )
        rows = db.get_relevant_homepage_packages(conn)
        config = {
            "file_path": str(file_path), "sheet_name": "Ringkasan Beranda", "start_cell": "A5",
            "enabled_columns": columns, "mode": "replace", "use_excel_table": True,
        }
        result = excel_service.export_packages(conn, rows, config, dataset=excel_service.DATASET_BERANDA)

    assert result.rows_written == 1
    import openpyxl
    wb = openpyxl.load_workbook(file_path)
    ws = wb["Ringkasan Beranda"]
    header = [ws.cell(row=4, column=c).value for c in range(1, len(columns) + 1)]
    assert "Bagian" in header and "Akhir Pendaftaran" in header
    row_values = {ws.cell(row=4, column=c).value: ws.cell(row=5, column=c).value for c in range(1, len(columns) + 1)}
    assert row_values["Bagian"] == "Tender"
    assert row_values["Akhir Pendaftaran"] == "20 Sep 2026 23:59"


def test_discover_excel_files_finds_xlsx_and_skips_backups(tmp_path):
    (tmp_path / "backups").mkdir()
    (tmp_path / "backups" / "old_backup.xlsx").write_bytes(b"")
    (tmp_path / "Monitoring LPSE.xlsx").write_bytes(b"")
    (tmp_path / "~$Monitoring LPSE.xlsx").write_bytes(b"")  # Excel lock file

    found = excel_service.discover_excel_files(tmp_path)
    assert found == ["Monitoring LPSE.xlsx"]
