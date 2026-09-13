"""
Keyword-based package relevance filtering.

Kept deliberately separate and simple so it can be swapped out later
(e.g. for word-boundary matching, regex patterns, or a small classifier)
without touching the scraper or the UI - anything that calls
`match_package` doesn't need to know HOW relevance is decided.

CURRENT ALGORITHM (v1): case-insensitive substring match against
"Nama Paket". This is intentionally simple and will produce some false
positives (e.g. a very short keyword like "jl" could theoretically match
inside an unrelated word). That's a known, accepted trade-off for v1 -
see the "Design notes / future improvements" section below.

Design notes / future improvements (not implemented yet):
  - Word-boundary matching (regex \\b) instead of raw substring, to avoid
    matching a keyword that's only part of a longer unrelated word.
  - Per-keyword "whole word only" toggle, since some keywords in this
    project (e.g. "jl", "jl.") are deliberately meant to catch abbreviated
    forms and can't use word-boundary matching safely.
  - Score-based ranking instead of a plain boolean match, if false
    positives become a real problem in practice.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass
class Keyword:
    id: int | None
    keyword: str
    is_enabled: bool = True


@dataclass
class MatchResult:
    is_relevant: bool
    matched_keywords: list  # list[str] - which enabled keywords matched


def match_package(nama_paket: str, keywords: Iterable[Keyword]) -> MatchResult:
    """Check a single package's Nama Paket against the active keyword list.

    Matching rules (v1):
      - case-insensitive
      - partial/substring match (a keyword anywhere in the text counts)
      - disabled keywords are ignored entirely
    """
    text = (nama_paket or "").lower()
    matched = []
    for kw in keywords:
        if not kw.is_enabled:
            continue
        needle = kw.keyword.strip().lower()
        if needle and needle in text:
            matched.append(kw.keyword)
    return MatchResult(is_relevant=bool(matched), matched_keywords=matched)


def filter_relevant(packages: list, keywords: Iterable[Keyword]) -> list:
    """Return only the packages that match at least one enabled keyword.
    Each returned package gets two extra attributes set for convenience:
    `.is_relevant` and `.matched_keywords`.
    """
    keywords = list(keywords)  # allow re-use across many packages
    relevant = []
    for pkg in packages:
        result = match_package(pkg.nama_paket, keywords)
        pkg.is_relevant = result.is_relevant
        pkg.matched_keywords = result.matched_keywords
        if result.is_relevant:
            relevant.append(pkg)
    return relevant
