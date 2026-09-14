"""
Best-effort detection of status words LPSE sometimes appends directly INTO
a package's own name - e.g. "PEMELIHARAAN RUTIN JALAN ... (Tender Gagal)"
or "... (Diulang)" - as opposed to the site's separate badge elements
(`<span class="badge">`, already captured in the `badges` field by both
scrapers). Without this, a renamed/failed/re-tendered package would just
blend in with everything else in the list.

Just a plain word-boundary check on the package name text - not a
guarantee, and it never hides, removes, or re-categorizes a package on
its own. It only adds a visible label the UI can show next to a
package's name; a person still makes the call on what it means.
"""

from __future__ import annotations

import re

# Order matters only for output order, not detection - each pattern is
# checked independently. Kept intentionally small and literal rather than
# clever, so it's obvious at a glance what triggers a flag.
_STATUS_FLAG_PATTERNS = (
    (re.compile(r"\bgagal\b", re.IGNORECASE), "Kemungkinan Tender Gagal"),
    (re.compile(r"\bdibatalkan\b", re.IGNORECASE), "Kemungkinan Dibatalkan"),
    (re.compile(r"\bbatal\b", re.IGNORECASE), "Kemungkinan Dibatalkan"),
    (re.compile(r"\bdiulang\b", re.IGNORECASE), "Kemungkinan Ditenderkan Ulang"),
    (re.compile(r"\bgugur\b", re.IGNORECASE), "Kemungkinan Gugur"),
)


def detect_status_flags(nama_paket: str) -> list:
    """Returns a list of human-readable Indonesian labels for whichever
    status words were found in `nama_paket` (deduplicated, in a stable
    order) - an empty list means nothing was detected. Safe to call on
    any string, including None/empty."""
    if not nama_paket:
        return []
    found = []
    for pattern, label in _STATUS_FLAG_PATTERNS:
        if pattern.search(nama_paket) and label not in found:
            found.append(label)
    return found
