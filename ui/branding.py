"""
Kalla Aspal visual identity for the Streamlit app.

Colors come from the real KALLA ASPAL wordmark (gold "K" + green "ALLA" +
charcoal "ASPAL"), used as a small set of named tokens everywhere - header,
buttons, tabs, metrics, dividers - instead of one-off colors scattered
around.

Three things get applied once, near the top of app.py:
  - `PAGE_CONFIG_KWARGS` -> passed to st.set_page_config()
  - `inject_css()` -> loads ui/style.css and injects it, styling buttons,
    tabs, metrics, dividers, headers, and the card system used by both
    the Dashboard feed and the scrape-result package cards
    (`.kalla-activity-*` / `.kalla-pkg-*`), plus a narrow rule (see
    CALENDAR_CONTAINER_KEY) that shrinks only the Ringkasan Beranda
    calendar.
  - `render_header()` -> a small banner in place of st.title(), using the
    real wordmark's colors.
  - `render_road_strip()` -> the gold dashed line under the header, meant
    to read like a road marking from above (Kalla Aspal builds roads).

Kept in its own module rather than inlined in app.py so the app's look is
one easy-to-find place.

The CSS itself used to live here as an inline Python f-string - it now
lives in `ui/style.css`, a plain file you can open and edit directly
(change a color, save, refresh the browser) without touching Python.
`inject_css()` just reads that file and injects it. **To change how the
app looks - colors, spacing, card style - edit `ui/style.css`, not this
file.** This module only keeps `render_header()`/`render_road_strip()`
(small HTML snippets) and `CALENDAR_CONTAINER_KEY`, which has to match
the `.st-key-kalla_calendar` selector over in style.css.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

# Path to the CSS file inject_css() reads - sits next to this module.
_STYLE_CSS_PATH = Path(__file__).parent / "style.css"

PAGE_CONFIG_KWARGS = dict(page_title="Kalla Aspal - LPSE Monitor", page_icon="\U0001F6E3", layout="wide")

# Key for st.container(key=...) around the deadline calendar, so the CSS
# can shrink just that calendar's buttons/spacing without touching
# buttons anywhere else. Streamlit turns this into a `st-key-{value}`
# class on the container's wrapper element.
CALENDAR_CONTAINER_KEY = "kalla_calendar"


def inject_css() -> None:
    """Read ui/style.css and inject it. Reads the file fresh every call
    instead of caching it, so a hand-edit shows up on the next rerun (just
    refresh the browser) without restarting the app. Warns instead of
    crashing if the file is somehow missing."""
    try:
        css_text = _STYLE_CSS_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        st.warning(f"Style file not found: {_STYLE_CSS_PATH} - app will use default Streamlit styling.")
        return
    st.markdown(f"<style>\n{css_text}\n</style>", unsafe_allow_html=True)


def render_header(subtitle: str = "LPSE Monitor") -> None:
    """Small banner in the real KALLA ASPAL wordmark's colors, in place of
    a plain st.title(). Plain text, no image file to keep track of."""
    st.markdown(
        f"""
        <div class="kalla-header">
            <span class="kalla-wordmark">
                <span class="kalla-k">K</span><span class="kalla-lla">ALLA</span><span class="kalla-aspal">ASPAL</span>
            </span>
            <span class="kalla-subtitle">{subtitle}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_road_strip() -> None:
    """The dashed gold line under the header - a dark band with a dashed
    center line, like a road marking. Shown once, right under the header;
    not reused as every divider (see .kalla-road / the plain hr rule in
    style.css) so it stays an accent instead of wallpaper."""
    st.markdown('<div class="kalla-road"></div>', unsafe_allow_html=True)
