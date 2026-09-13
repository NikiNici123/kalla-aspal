from services import filter_service


ROWS = [
    {"region_identifier": "singkawangkota", "tahapan": "Tender", "kategori": "Konstruksi",
     "nama_paket": "Peningkatan Jalan A", "hps_value": 1_000_000.0},
    {"region_identifier": "singkawangkota", "tahapan": "Masa Sanggah", "kategori": "Konstruksi",
     "nama_paket": "Peningkatan Jalan B", "hps_value": 2_000_000.0},
    {"region_identifier": "kalbarprov", "tahapan": "Masa Sanggah", "kategori": "Konsultansi",
     "nama_paket": "Peningkatan Jalan C", "hps_value": 500_000.0},
    {"region_identifier": "kalbarprov", "tahapan": "Tender", "kategori": "Konstruksi",
     "nama_paket": "Peningkatan Jalan D", "hps_value": None},
]


def test_distinct_values():
    assert filter_service.distinct_values(ROWS, "region_identifier") == ["kalbarprov", "singkawangkota"]
    assert filter_service.distinct_values(ROWS, "tahapan") == ["Masa Sanggah", "Tender"]


def test_filter_rows_by_status_only():
    filtered = filter_service.filter_rows(ROWS, status=["Masa Sanggah"])
    assert len(filtered) == 2
    assert all(r["tahapan"] == "Masa Sanggah" for r in filtered)


def test_filter_rows_by_wilayah_and_status_combined():
    filtered = filter_service.filter_rows(ROWS, wilayah=["kalbarprov"], status=["Masa Sanggah"])
    assert len(filtered) == 1
    assert filtered[0]["nama_paket"] == "Peningkatan Jalan C"


def test_filter_rows_no_filters_returns_everything():
    assert filter_service.filter_rows(ROWS) == ROWS


def test_sum_hps_recalculates_per_filter():
    assert filter_service.sum_hps(ROWS) == 3_500_000.0  # None skipped, not treated as 0-but-counted
    masa_sanggah_only = filter_service.filter_rows(ROWS, status=["Masa Sanggah"])
    assert filter_service.sum_hps(masa_sanggah_only) == 2_500_000.0


def test_sort_rows_chronological_reverse():
    forward = filter_service.sort_rows(ROWS, "Terlama -> Terbaru (default)")
    assert [r["nama_paket"] for r in forward] == [r["nama_paket"] for r in ROWS]

    backward = filter_service.sort_rows(ROWS, "Terbaru -> Terlama")
    assert [r["nama_paket"] for r in backward] == [r["nama_paket"] for r in reversed(ROWS)]


def test_sort_rows_by_hps_highest_first():
    sorted_rows = filter_service.sort_rows(ROWS, "HPS Tertinggi")
    values = [r["hps_value"] for r in sorted_rows if r["hps_value"] is not None]
    assert values == sorted(values, reverse=True)
