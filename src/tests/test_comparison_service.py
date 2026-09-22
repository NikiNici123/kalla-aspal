"""
End-to-end (but offline - no real HTTP) test of the new/existing/updated
detection logic, arguably the single most important thing this app gets
right. We monkeypatch the scraper's `get_packages` so the test controls
exactly what "was scraped" on each run, and use a temporary on-disk
SQLite database so nothing touches the real data/lpse_monitor.db.
"""

from scraper.lpse_scraper import Package
from database import database as db
from services import comparison_service


def make_pkg(package_id, nama_paket, tahapan="Tender", hps_value=1_000_000.0):
    return Package(
        package_id=package_id,
        fingerprint=None,
        region_identifier="singkawangkota",
        nama_paket=nama_paket,
        nama_paket_raw=nama_paket,
        badges=[],
        instansi="Kota Singkawang",
        tahapan=tahapan,
        metode_kualifikasi="Pascakualifikasi Satu File",
        jenis="Tender",
        metode_evaluasi="Harga Terendah Sistem Gugur",
        jenis_pengadaan="Pekerjaan Konstruksi",
        tahun_anggaran="2026",
        hps_text="1 Jt",
        hps_value=hps_value,
        nilai_kontrak_text="Nilai Kontrak belum dibuat",
        nilai_kontrak_value=None,
        package_url=f"https://spse.inaproc.id/singkawangkota/lelang/{package_id}/pengumumanlelang",
        scraped_at="2026-09-13T08:15:00",
    )


def test_first_run_marks_everything_new(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    db.init_db(db_path)

    first_batch = [
        make_pkg("1", "Peningkatan Jalan A"),
        make_pkg("2", "Rehabilitasi Jalan B"),
    ]
    monkeypatch.setattr(
        "scraper.lpse_scraper.get_packages", lambda region, tahun=None, timeout=20: first_batch
    )

    with db.connect(db_path) as conn:
        summary = comparison_service.run_scrape_and_compare(conn, ["singkawangkota"])

    assert len(summary.new_packages) == 2
    assert len(summary.updated_packages) == 0
    assert len(summary.existing_packages) == 0
    assert summary.region_results[0].success is True


def test_second_run_detects_new_updated_and_existing(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    db.init_db(db_path)

    first_batch = [
        make_pkg("1", "Peningkatan Jalan A", tahapan="Tender"),
        make_pkg("2", "Rehabilitasi Jalan B", tahapan="Tender"),
    ]
    monkeypatch.setattr(
        "scraper.lpse_scraper.get_packages", lambda region, tahun=None, timeout=20: first_batch
    )
    with db.connect(db_path) as conn:
        comparison_service.run_scrape_and_compare(conn, ["singkawangkota"])

    # Second scrape: package 1 unchanged, package 2's status changed
    # (-> "updated"), and a brand-new package 3 appears (-> "new").
    second_batch = [
        make_pkg("1", "Peningkatan Jalan A", tahapan="Tender"),
        make_pkg("2", "Rehabilitasi Jalan B", tahapan="Tender Sudah Selesai"),
        make_pkg("3", "Pembangunan Jalan C"),
    ]
    monkeypatch.setattr(
        "scraper.lpse_scraper.get_packages", lambda region, tahun=None, timeout=20: second_batch
    )
    with db.connect(db_path) as conn:
        summary = comparison_service.run_scrape_and_compare(conn, ["singkawangkota"])

    assert [p["package_id"] for p in summary.new_packages] == ["3"]
    assert [p["package_id"] for p in summary.updated_packages] == ["2"]
    assert [p["package_id"] for p in summary.existing_packages] == ["1"]

    # And the change should be recorded in package_snapshots for package 2.
    with db.connect(db_path) as conn:
        history = db.get_package_history(conn, "2")
    assert len(history) == 2  # "Pertama kali ditemukan" + the status-change snapshot
    assert "Tahapan berubah" in history[-1]["change_summary"]


def test_region_error_does_not_abort_other_regions(tmp_path, monkeypatch):
    from scraper.lpse_scraper import LPSERegionNotFoundError

    db_path = tmp_path / "test.db"
    db.init_db(db_path)

    def fake_get_packages(region, tahun=None, timeout=20):
        if region == "wilayahsalah":
            raise LPSERegionNotFoundError("Wilayah LPSE 'wilayahsalah' tidak ditemukan.")
        return [make_pkg("99", "Peningkatan Jalan Z")]

    monkeypatch.setattr("scraper.lpse_scraper.get_packages", fake_get_packages)

    with db.connect(db_path) as conn:
        summary = comparison_service.run_scrape_and_compare(conn, ["wilayahsalah", "singkawangkota"])

    results_by_region = {r.region_identifier: r for r in summary.region_results}
    assert results_by_region["wilayahsalah"].success is False
    assert "tidak ditemukan" in results_by_region["wilayahsalah"].error_message
    assert results_by_region["singkawangkota"].success is True
    assert len(summary.new_packages) == 1
