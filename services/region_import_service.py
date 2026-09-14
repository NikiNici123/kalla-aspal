"""
Bulk region-import helpers for the Wilayah LPSE tab.

Lets an admin add many LPSE regions at once instead of one at a time.
Two input shapes are supported, both reduced to the same output - a
list of unique region identifiers, in the order first seen:

  1. Free-form pasted text, one entry per line - either a full LPSE URL
     (`https://spse.inaproc.id/singkawangkota/lelang`) or a bare
     identifier (`singkawangkota`). Lets someone paste a list from
     anywhere (email, a spreadsheet column, a chat message) without
     touching a browser at all.
  2. An exported browser bookmarks file. Chrome, Edge, and Firefox all
     export bookmarks in the same standard "Netscape Bookmark File
     Format" - a plain HTML file where every bookmark is one
     `<A HREF="...">` tag - so this works for any of them. Only links
     pointing at spse.inaproc.id are recognized; every other bookmarked
     site in the file is ignored, so someone can export their whole
     bookmarks bar instead of needing a dedicated LPSE-only folder.

Kept as small, pure functions with no Streamlit dependency (same
convention as filter_service.py), so they're unit testable on their own.
`app.py`'s bulk-import UI calls these and loops `db.add_region` over the
result, same as the single-region form already does.
"""

from __future__ import annotations

import re

# Every LPSE region lives under the same national portal domain, one
# path segment per region (https://spse.inaproc.id/<region>/...). Defined
# here rather than imported from scraper/lpse_scraper.py's PORTAL_BASE so
# this module has no dependency on `requests` - that keeps it importable
# and testable even in environments where `requests` isn't installed.
_LPSE_URL_RE = re.compile(r"https?://spse\.inaproc\.id/([a-zA-Z0-9_-]+)", re.IGNORECASE)

# A bare identifier typed on its own line, with no URL around it at all.
_BARE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z0-9_-]+$")

# Matches one bookmark entry's href out of an exported bookmarks HTML
# file. Browsers write this attribute as HREF="..." (Chrome/Edge) or
# href="..." (Firefox) - case-insensitive covers both.
_BOOKMARK_HREF_RE = re.compile(r'href\s*=\s*"([^"]*)"', re.IGNORECASE)


def _dedupe_preserving_order(identifiers) -> list:
    seen: set = set()
    result = []
    for identifier in identifiers:
        if identifier not in seen:
            seen.add(identifier)
            result.append(identifier)
    return result


def extract_region_identifiers_from_text(text: str) -> list:
    """Parse pasted free-form text into a deduped list of region
    identifiers, one candidate per non-blank line. Each line may be a
    full LPSE URL (any path/query after the identifier is ignored, so
    `.../lelang`, `.../`, and `.../nontender/123/...` all resolve to the
    same identifier) or a bare identifier with no URL around it at all.
    Lines that are neither are skipped, not treated as an error - a
    pasted list can freely mix URLs, bare identifiers, and blank lines
    for readability."""
    if not text:
        return []
    candidates = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        url_match = _LPSE_URL_RE.search(line)
        if url_match:
            candidates.append(url_match.group(1))
        elif _BARE_IDENTIFIER_RE.match(line):
            candidates.append(line)
        # else: not recognized as either shape - silently skipped, the
        # caller can compare len(input lines) vs len(result) if it wants
        # to warn about unrecognized lines.
    return _dedupe_preserving_order(candidates)


def extract_region_identifiers_from_bookmarks_html(html: str) -> list:
    """Parse an exported browser bookmarks file (Chrome/Edge/Firefox -
    all use the same Netscape Bookmark File Format) and return every
    unique LPSE region identifier found among its links, in the order
    first encountered. Bookmarks unrelated to spse.inaproc.id (any other
    website, any folder structure) are ignored rather than raising -
    an admin's whole bookmarks export is a valid input, not just an
    LPSE-only folder."""
    if not html:
        return []
    candidates = []
    for href in _BOOKMARK_HREF_RE.findall(html):
        match = _LPSE_URL_RE.search(href)
        if match:
            candidates.append(match.group(1))
    return _dedupe_preserving_order(candidates)
