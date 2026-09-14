import json

from database import database as db
from services import activity_service


def _insert_lelang_snapshot(conn, created_at, nama_paket="Contoh Paket", package_url="https://x/1",
                             change_summary="Pertama kali ditemukan"):
    conn.execute(
        """
        INSERT INTO package_snapshots
            (package_key, scrape_run_id, tahapan, hps_value, nilai_kontrak_value,
             change_summary, snapshot_json, created_at)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            "lelang-key", None, "Tender", 1.0, None, change_summary,
            json.dumps({"nama_paket": nama_paket, "package_url": package_url}), created_at,
        ),
    )


def _insert_beranda_snapshot(conn, created_at, nama_paket="Contoh Beranda", package_url="https://x/2",
                              change_summary="Pertama kali ditemukan"):
    conn.execute(
        """
        INSERT INTO homepage_package_snapshots
            (package_key, scrape_run_id, hps_value, akhir_pendaftaran_at,
             change_summary, snapshot_json, created_at)
        VALUES (?,?,?,?,?,?,?)
        """,
        (
            "beranda-key", None, 1.0, None, change_summary,
            json.dumps({"nama_paket": nama_paket, "package_url": package_url}), created_at,
        ),
    )


def test_merges_both_datasets_sorted_newest_first(tmp_path):
    db_path = tmp_path / "test.db"
    db.init_db(db_path)
    with db.connect(db_path) as conn:
        _insert_lelang_snapshot(conn, "2026-09-10T08:00:00", nama_paket="Paket Lelang Lama")
        _insert_beranda_snapshot(conn, "2026-09-12T08:00:00", nama_paket="Paket Beranda Baru")
        _insert_lelang_snapshot(conn, "2026-09-11T08:00:00", nama_paket="Paket Lelang Tengah")
        conn.commit()

        activity = activity_service.get_recent_activity(conn, limit=10)

    assert [e.nama_paket for e in activity] == ["Paket Beranda Baru", "Paket Lelang Tengah", "Paket Lelang Lama"]
    assert activity[0].dataset == activity_service.DATASET_BERANDA
    assert activity[1].dataset == activity_service.DATASET_LELANG


def test_is_new_flag_and_status_flags_detected(tmp_path):
    db_path = tmp_path / "test.db"
    db.init_db(db_path)
    with db.connect(db_path) as conn:
        _insert_lelang_snapshot(
            conn, "2026-09-10T08:00:00", nama_paket="Jalan Provinsi (Tender Gagal)",
            change_summary="Pertama kali ditemukan",
        )
        _insert_lelang_snapshot(
            conn, "2026-09-11T08:00:00", nama_paket="Jalan Kabupaten",
            change_summary="Tahapan berubah: Tender -> Evaluasi",
        )
        conn.commit()

        activity = activity_service.get_recent_activity(conn, limit=10)

    newest, oldest = activity[0], activity[1]
    assert oldest.is_new is True
    assert newest.is_new is False
    assert newest.change_summary == "Tahapan berubah: Tender -> Evaluasi"
    assert "Kemungkinan Tender Gagal" in oldest.status_flags


def test_limit_applies_to_combined_total_not_per_dataset(tmp_path):
    db_path = tmp_path / "test.db"
    db.init_db(db_path)
    with db.connect(db_path) as conn:
        for i in range(5):
            _insert_lelang_snapshot(conn, f"2026-09-{10 + i:02d}T08:00:00", nama_paket=f"Paket {i}")
        conn.commit()

        activity = activity_service.get_recent_activity(conn, limit=3)

    assert len(activity) == 3
    # Newest 3 of the 5 inserted (indices 4, 3, 2), not the oldest.
    assert [e.nama_paket for e in activity] == ["Paket 4", "Paket 3", "Paket 2"]


def test_handles_missing_or_unparseable_snapshot_gracefully(tmp_path):
    db_path = tmp_path / "test.db"
    db.init_db(db_path)
    with db.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO package_snapshots
                (package_key, scrape_run_id, tahapan, hps_value, nilai_kontrak_value,
                 change_summary, snapshot_json, created_at)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            ("bad-key", None, "Tender", None, None, "Pertama kali ditemukan", "not valid json", "2026-09-10T08:00:00"),
        )
        conn.commit()

        activity = activity_service.get_recent_activity(conn, limit=10)

    assert activity == []
