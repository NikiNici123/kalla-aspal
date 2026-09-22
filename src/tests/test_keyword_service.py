from services.keyword_service import Keyword, match_package, filter_relevant
from scraper.lpse_scraper import parse_row
from tests.test_scraper_parsing import ROW_PLAIN_JALAN, ROW_WITH_BADGE_AND_CONTRACT


def test_match_package_case_insensitive_partial():
    keywords = [Keyword(id=1, keyword="jalan", is_enabled=True)]
    result = match_package("PEMBANGUNAN JALAN XYZ", keywords)
    assert result.is_relevant
    assert result.matched_keywords == ["jalan"]


def test_match_package_disabled_keyword_ignored():
    keywords = [Keyword(id=1, keyword="jalan", is_enabled=False)]
    result = match_package("Pembangunan Jalan XYZ", keywords)
    assert not result.is_relevant


def test_match_package_no_match():
    keywords = [Keyword(id=1, keyword="jalan", is_enabled=True)]
    result = match_package("Pengadaan Alat Tulis Kantor", keywords)
    assert not result.is_relevant
    assert result.matched_keywords == []


def test_filter_relevant_marks_and_filters():
    keywords = [Keyword(id=1, keyword="jalan", is_enabled=True)]
    jalan_pkg = parse_row(ROW_PLAIN_JALAN, "singkawangkota")
    tebing_pkg = parse_row(ROW_WITH_BADGE_AND_CONTRACT, "singkawangkota")  # no "jalan" in name

    relevant = filter_relevant([jalan_pkg, tebing_pkg], keywords)

    assert relevant == [jalan_pkg]
    assert jalan_pkg.is_relevant is True
    assert tebing_pkg.is_relevant is False
