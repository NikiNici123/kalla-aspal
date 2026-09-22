from services import region_import_service as ris


def test_extract_from_text_full_urls():
    text = "https://spse.inaproc.id/singkawangkota/lelang\nhttps://spse.inaproc.id/kalbarprov/"
    assert ris.extract_region_identifiers_from_text(text) == ["singkawangkota", "kalbarprov"]


def test_extract_from_text_bare_identifiers():
    text = "singkawangkota\nkalbarprov"
    assert ris.extract_region_identifiers_from_text(text) == ["singkawangkota", "kalbarprov"]


def test_extract_from_text_mixed_urls_bare_and_blank_lines():
    text = "\nhttps://spse.inaproc.id/singkawangkota/lelang\n\nkalbarprov\n   \n"
    assert ris.extract_region_identifiers_from_text(text) == ["singkawangkota", "kalbarprov"]


def test_extract_from_text_dedupes_preserving_first_seen_order():
    text = "kalbarprov\nsingkawangkota\nhttps://spse.inaproc.id/kalbarprov/lelang"
    assert ris.extract_region_identifiers_from_text(text) == ["kalbarprov", "singkawangkota"]


def test_extract_from_text_ignores_unrelated_urls_and_junk_lines():
    text = "https://example.com/not-lpse\n!!! not a url or identifier with spaces\nkalbarprov"
    assert ris.extract_region_identifiers_from_text(text) == ["kalbarprov"]


def test_extract_from_text_empty_input():
    assert ris.extract_region_identifiers_from_text("") == []
    assert ris.extract_region_identifiers_from_text("   \n  \n") == []


def test_extract_from_text_handles_any_path_after_identifier():
    text = "https://spse.inaproc.id/pontianakkota/nontender/123/pengumumanpl"
    assert ris.extract_region_identifiers_from_text(text) == ["pontianakkota"]


BOOKMARKS_HTML = """
<!DOCTYPE NETSCAPE-Bookmark-file-1>
<DL><p>
    <DT><H3>LPSE Kalimantan</H3>
    <DL><p>
        <DT><A HREF="https://spse.inaproc.id/singkawangkota/lelang" ADD_DATE="1">Singkawang</A>
        <DT><A HREF="https://spse.inaproc.id/kalbarprov/" ADD_DATE="2">Kalbar Prov</A>
        <DT><A HREF="https://www.google.com/" ADD_DATE="3">Google</A>
    </DL><p>
    <DT><A HREF="https://spse.inaproc.id/singkawangkota/lelang" ADD_DATE="4">Singkawang duplicate</A>
</DL><p>
"""


def test_extract_from_bookmarks_html_finds_lpse_links_only():
    result = ris.extract_region_identifiers_from_bookmarks_html(BOOKMARKS_HTML)
    assert result == ["singkawangkota", "kalbarprov"]


def test_extract_from_bookmarks_html_firefox_lowercase_href():
    html = '<DT><A href="https://spse.inaproc.id/pontianakkota/lelang">Pontianak</A>'
    assert ris.extract_region_identifiers_from_bookmarks_html(html) == ["pontianakkota"]


def test_extract_from_bookmarks_html_empty_or_no_matches():
    assert ris.extract_region_identifiers_from_bookmarks_html("") == []
    assert ris.extract_region_identifiers_from_bookmarks_html("<A HREF=\"https://example.com\">x</A>") == []
