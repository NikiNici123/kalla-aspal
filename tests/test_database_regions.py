from database import database as db


def test_add_region_then_duplicate_is_rejected(tmp_path):
    db_path = tmp_path / "test.db"
    db.init_db(db_path)

    with db.connect(db_path) as conn:
        ok, msg = db.add_region(conn, "Kota Singkawang", "singkawangkota", "https://spse.inaproc.id/singkawangkota/lelang")
        assert ok is True

        ok2, msg2 = db.add_region(conn, "Kota Singkawang Lagi", "singkawangkota", "https://spse.inaproc.id/singkawangkota/lelang")
        assert ok2 is False
        assert "sudah ada" in msg2


def test_set_region_active_and_delete(tmp_path):
    db_path = tmp_path / "test.db"
    db.init_db(db_path)

    with db.connect(db_path) as conn:
        db.add_region(conn, "Kota Pontianak", "pontianakkota", "https://spse.inaproc.id/pontianakkota/lelang")
        region = db.get_region_by_identifier(conn, "pontianakkota")
        assert region["is_active"] == 1

        db.set_region_active(conn, region["id"], False)
        assert len(db.get_active_regions(conn)) == 0
        assert len(db.get_all_regions(conn)) == 1

        db.delete_region(conn, region["id"])
        assert len(db.get_all_regions(conn)) == 0


def test_relevant_packages_sorted_earliest_first(tmp_path, monkeypatch):
    from scraper.lpse_scraper import Package
    from services import comparison_service

    db_path = tmp_path / "test.db"
    db.init_db(db_path)

    def make_pkg(pid):
        return Package(
            package_id=pid, fingerprint=None, region_identifier="singkawangkota",
            nama_paket="Peningkatan Jalan", nama_paket_raw="Peningkatan Jalan", badges=[],
            instansi="X", tahapan="Tender", metode_kualifikasi="", jenis="Tender",
            metode_evaluasi="", jenis_pengadaan="Konstruksi", tahun_anggaran="2026",
            hps_text="1 Jt", hps_value=1_000_000.0, nilai_kontrak_text="", nilai_kontrak_value=None,
            package_url=f"https://spse.inaproc.id/singkawangkota/lelang/{pid}/pengumumanlelang",
            scraped_at="2026-09-13T08:15:00",
        )

    batch = [make_pkg("500"), make_pkg("100"), make_pkg("300")]
    monkeypatch.setattr("scraper.lpse_scraper.get_packages", lambda region, tahun=None, timeout=20: batch)

    with db.connect(db_path) as conn:
        comparison_service.run_scrape_and_compare(conn, ["singkawangkota"])
        rows = db.get_relevant_packages(conn)

    assert [r["package_id"] for r in rows] == ["100", "300", "500"]
