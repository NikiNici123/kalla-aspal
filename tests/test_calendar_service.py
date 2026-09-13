from datetime import date

from services import calendar_service


def test_group_by_deadline_date_groups_same_day():
    rows = [
        {"nama_paket": "Paket A", "akhir_pendaftaran_at": "2026-09-20T23:59:00"},
        {"nama_paket": "Paket B", "akhir_pendaftaran_at": "2026-09-20T15:00:00"},
        {"nama_paket": "Paket C", "akhir_pendaftaran_at": "2026-09-21T10:00:00"},
        {"nama_paket": "Paket D", "akhir_pendaftaran_at": None},
    ]
    grouped = calendar_service.group_by_deadline_date(rows)
    assert set(grouped.keys()) == {"2026-09-20", "2026-09-21"}
    assert len(grouped["2026-09-20"]) == 2
    assert len(grouped["2026-09-21"]) == 1


def test_build_month_grid_covers_whole_month_with_padding():
    grid = calendar_service.build_month_grid(2026, 9)
    all_days = [d for week in grid for d in week if d is not None]
    assert date(2026, 9, 1) in all_days
    assert date(2026, 9, 30) in all_days
    assert len(all_days) == 30
    # every week row has exactly 7 slots (padding included)
    assert all(len(week) == 7 for week in grid)


def test_add_months_wraps_year_forward_and_backward():
    assert calendar_service.add_months(2026, 12, 1) == (2027, 1)
    assert calendar_service.add_months(2026, 1, -1) == (2025, 12)
    assert calendar_service.add_months(2026, 6, 3) == (2026, 9)
