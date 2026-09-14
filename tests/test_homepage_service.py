from scraper.lpse_homepage_scraper import HomepagePackage
from database import database as db
from services import homepage_service


def make_hp(package_id, nama_paket, deadline="2026-09-18T12:00", hps_value=1_000_000.0):
    return HomepagePackage(
        package_id=package_id,
        region_identifier="kalbarprov",
        section="Tender",
        kategori="Pekerjaan Konstruksi",
        nama_paket=nama_paket,
        badges=["spse 4.5", "Tender"],
        hps_text="Rp 1.000.000,00",
        hps_value=hps_value,
        akhir_pendaftaran_text="18 September 2026 12:00",
        akhir_pendaftaran_at=deadline,
        display_position=1,
        package_url=f"https://spse.inaproc.id/kalbarprov/lelang/{package_id}/pengumumanlelang",
        scraped_at="2026-09-13T08:15:00",
    )


def test_first_run_marks_everything_new(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    db.init_db(db_path)

    batch = [make_hp("1", "Peningkatan Jalan A"), make_hp("2", "Rehabilitasi Jalan B")]
    monkeypatch.setattr("scraper.lpse_homepage_scraper.get_homepage_summary", lambda region, timeout=20: batch)

    with db.connect(db_path) as conn:
        summary = homepage_service.run_homepage_scrape_and_compare(conn, ["kalbarprov"])

    assert len(summary.new_packages) == 2
    assert summary.region_results[0].success is True


def test_second_run_detects_deadline_change_as_updated(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    db.init_db(db_path)

    first_batch = [make_hp("1", "Peningkatan Jalan A", deadline="2026-09-18T12:00")]
    monkeypatch.setattr(
        "scraper.lpse_homepage_scraper.get_homepage_summary", lambda region, timeout=20: first_batch
    )
    with db.connect(db_path) as conn:
        homepage_service.run_homepage_scrape_and_compare(conn, ["kalbarprov"])

    # Deadline extended -> should show up as "updated", not "existing".
    second_batch = [make_hp("1", "Peningkatan Jalan A", deadline="2026-09-20T12:00")]
    monkeypatch.setattr(
        "scraper.lpse_homepage_scraper.get_homepage_summary", lambda region, timeout=20: second_batch
    )
    with db.connect(db_path) as conn:
        summary = homepage_service.run_homepage_scrape_and_compare(conn, ["kalbarprov"])

    assert len(summary.updated_packages) == 1
    assert "Akhir Pendaftaran berubah" in summary.updated_packages[0]["_change_summary"]


def test_new_and_updated_packages_are_persisted_to_snapshot_history(tmp_path, monkeypatch):
    """Regression test for the "Aktivitas Terbaru" dashboard tab: both a
    brand-new package and a subsequently-updated one must show up in
    homepage_package_snapshots, mirroring package_snapshots for the
    Daftar Lengkap dataset (see services/activity_service.py)."""
    db_path = tmp_path / "test.db"
    db.init_db(db_path)

    first_batch = [make_hp("1", "Peningkatan Jalan A", deadline="2026-09-18T12:00")]
    monkeypatch.setattr(
        "scraper.lpse_homepage_scraper.get_homepage_summary", lambda region, timeout=20: first_batch
    )
    with db.connect(db_path) as conn:
        homepage_service.run_homepage_scrape_and_compare(conn, ["kalbarprov"])
        history_after_new = db.get_recent_homepage_snapshots(conn)

    assert len(history_after_new) == 1
    assert history_after_new[0]["change_summary"] == "Pertama kali ditemukan"

    second_batch = [make_hp("1", "Peningkatan Jalan A (Diulang)", deadline="2026-09-18T12:00")]
    monkeypatch.setattr(
        "scraper.lpse_homepage_scraper.get_homepage_summary", lambda region, timeout=20: second_batch
    )
    with db.connect(db_path) as conn:
        homepage_service.run_homepage_scrape_and_compare(conn, ["kalbarprov"])
        history_after_update = db.get_recent_homepage_snapshots(conn)

    assert len(history_after_update) == 2
    newest = history_after_update[0]
    assert "Peningkatan Jalan A" in newest["change_summary"]
    assert "Diulang" in newest["change_summary"]


def test_relevant_homepage_packages_sorted_earliest_id_first(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    db.init_db(db_path)

    # Deliberately scraped/inserted out of numeric order.
    batch = [
        make_hp("300", "Peningkatan Jalan C"),
        make_hp("100", "Peningkatan Jalan A"),
        make_hp("200", "Peningkatan Jalan B"),
    ]
    monkeypatch.setattr("scraper.lpse_homepage_scraper.get_homepage_summary", lambda region, timeout=20: batch)

    with db.connect(db_path) as conn:
        homepage_service.run_homepage_scrape_and_compare(conn, ["kalbarprov"])
        rows = db.get_relevant_homepage_packages(conn)

    assert [r["package_id"] for r in rows] == ["100", "200", "300"]
