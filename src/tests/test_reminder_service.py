from datetime import date

from services import reminder_service


def test_not_acknowledged_when_file_missing(tmp_path):
    ack_file = tmp_path / "reminder_ack.txt"
    assert reminder_service.is_acknowledged_today(ack_file, today=date(2026, 9, 15)) is False


def test_mark_then_is_acknowledged_same_day(tmp_path):
    ack_file = tmp_path / "reminder_ack.txt"
    today = date(2026, 9, 15)
    reminder_service.mark_acknowledged(ack_file, today=today)
    assert reminder_service.is_acknowledged_today(ack_file, today=today) is True


def test_acknowledgment_does_not_carry_over_to_next_day(tmp_path):
    ack_file = tmp_path / "reminder_ack.txt"
    reminder_service.mark_acknowledged(ack_file, today=date(2026, 9, 15))
    assert reminder_service.is_acknowledged_today(ack_file, today=date(2026, 9, 16)) is False


def test_mark_acknowledged_creates_parent_dir(tmp_path):
    ack_file = tmp_path / "logs" / "reminder_ack.txt"
    reminder_service.mark_acknowledged(ack_file, today=date(2026, 9, 15))
    assert ack_file.exists()


def test_includes_deadline_today_and_excludes_past():
    today = date(2026, 9, 15)
    rows = [
        {"nama_paket": "Sudah Lewat", "akhir_pendaftaran_at": "2026-09-14T23:59:00"},
        {"nama_paket": "Hari Ini", "akhir_pendaftaran_at": "2026-09-15T23:59:00"},
    ]
    upcoming = reminder_service.get_upcoming_deadlines(rows, within_days=3, today=today)
    names = [row["nama_paket"] for _, row in upcoming]
    assert names == ["Hari Ini"]


def test_includes_up_to_and_excludes_beyond_cutoff():
    today = date(2026, 9, 15)
    rows = [
        {"nama_paket": "Pas di Batas", "akhir_pendaftaran_at": "2026-09-18T23:59:00"},  # +3 days
        {"nama_paket": "Lewat Batas", "akhir_pendaftaran_at": "2026-09-19T23:59:00"},  # +4 days
    ]
    upcoming = reminder_service.get_upcoming_deadlines(rows, within_days=3, today=today)
    names = [row["nama_paket"] for _, row in upcoming]
    assert names == ["Pas di Batas"]


def test_skips_packages_with_no_deadline():
    rows = [
        {"nama_paket": "Tidak Ada Tanggal", "akhir_pendaftaran_at": None},
        {"nama_paket": "Kolom Hilang"},  # missing key entirely, not just None
    ]
    upcoming = reminder_service.get_upcoming_deadlines(rows, within_days=5, today=date(2026, 9, 15))
    assert upcoming == []


def test_sorted_soonest_deadline_first():
    today = date(2026, 9, 15)
    rows = [
        {"nama_paket": "Lusa", "akhir_pendaftaran_at": "2026-09-17T10:00:00"},
        {"nama_paket": "Besok", "akhir_pendaftaran_at": "2026-09-16T10:00:00"},
        {"nama_paket": "Hari Ini", "akhir_pendaftaran_at": "2026-09-15T10:00:00"},
    ]
    upcoming = reminder_service.get_upcoming_deadlines(rows, within_days=5, today=today)
    names = [row["nama_paket"] for _, row in upcoming]
    assert names == ["Hari Ini", "Besok", "Lusa"]


def test_zero_within_days_means_only_today():
    today = date(2026, 9, 15)
    rows = [
        {"nama_paket": "Hari Ini", "akhir_pendaftaran_at": "2026-09-15T10:00:00"},
        {"nama_paket": "Besok", "akhir_pendaftaran_at": "2026-09-16T10:00:00"},
    ]
    upcoming = reminder_service.get_upcoming_deadlines(rows, within_days=0, today=today)
    names = [row["nama_paket"] for _, row in upcoming]
    assert names == ["Hari Ini"]
