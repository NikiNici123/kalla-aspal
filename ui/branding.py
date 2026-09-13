"""
Kalla Aspal visual identity for the Streamlit app.

Colors are taken from the KALLA ASPAL wordmark (a gold "K" + deep green
"ALLA" + charcoal "ASPAL"), turned into a small, deliberate palette rather
than Streamlit's generic defaults - a handful of named tokens used
consistently everywhere (header, buttons, tabs, metrics, dividers) instead
of scattered one-off colors.

Two things get applied once, near the top of app.py:
  - `PAGE_CONFIG_KWARGS` -> passed to st.set_page_config()
  - `inject_css()` -> a single st.markdown(..., unsafe_allow_html=True)
    call that styles buttons/tabs/metrics/dividers app-wide, PLUS a
    narrow, deliberately scoped rule (see CALENDAR_CONTAINER_KEY) that
    only shrinks the Ringkasan Beranda calendar - nothing else.
  - `render_header()` -> replaces the plain st.title() with a small
    banner that echoes the real wordmark's colors.

Kept in its own module (rather than inlined in app.py) so the "look" of
the app is a single, easy-to-find place to tweak later - change a hex
value here and it updates everywhere at once.
"""

from __future__ import annotations

import streamlit as st

# --- Palette -----------------------------------------------------------
# Named, not scattered: every color used anywhere in the app's custom CSS
# traces back to one of these.
GREEN = "#00693C"
GREEN_DARK = "#004F2C"
GREEN_TINT = "#E7F2EC"       # pale green, for subtle backgrounds/hovers
GOLD = "#F2A900"
GOLD_DARK = "#C98800"
CHARCOAL = "#33383D"
GRAY_MUTED = "#6B7280"
BORDER = "#E1E6E1"
BG = "#FFFFFF"
BG_SOFT = "#F5F7F5"

PAGE_CONFIG_KWARGS = dict(page_title="Kalla Aspal - LPSE Monitor", page_icon="\U0001F6E3", layout="wide")

# A stable key for st.container(key=...) around the deadline calendar, so
# the CSS below can shrink ONLY that calendar's buttons/spacing without
# touching buttons anywhere else in the app. Streamlit turns this key into
# a `st-key-{value}` CSS class on the container's own wrapper element.
CALENDAR_CONTAINER_KEY = "kalla_calendar"


def inject_css() -> None:
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

        .stApp {{
            font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
            background-color: {BG};
        }}

        /* --- Header banner (see render_header) --- */
        .kalla-header {{
            display: flex; align-items: baseline; gap: 0.6rem;
            padding-bottom: 0.35rem; margin-bottom: 0.25rem;
            border-bottom: 3px solid {GOLD};
        }}
        .kalla-header .kalla-wordmark {{ font-size: 1.9rem; font-weight: 700; letter-spacing: 0.01em; }}
        .kalla-header .kalla-k {{ color: {GOLD}; }}
        .kalla-header .kalla-lla {{ color: {GREEN}; }}
        .kalla-header .kalla-aspal {{ color: {CHARCOAL}; margin-left: 0.15rem; }}
        .kalla-header .kalla-subtitle {{
            font-size: 0.95rem; color: {GRAY_MUTED}; font-weight: 400;
        }}

        /* --- Buttons --- */
        div[data-testid="stButton"] button {{
            border-radius: 6px; border: 1px solid {BORDER}; transition: all 0.1s ease-in;
        }}
        div[data-testid="stButton"] button[kind="primary"] {{
            background-color: {GREEN}; border-color: {GREEN};
        }}
        div[data-testid="stButton"] button[kind="primary"]:hover {{
            background-color: {GREEN_DARK}; border-color: {GREEN_DARK};
        }}
        div[data-testid="stButton"] button[kind="secondary"]:hover {{
            border-color: {GOLD}; color: {GOLD_DARK};
        }}

        /* --- Tabs --- */
        button[data-baseweb="tab"] {{ font-weight: 600; color: {GRAY_MUTED}; }}
        button[data-baseweb="tab"][aria-selected="true"] {{ color: {GREEN}; }}
        div[data-baseweb="tab-highlight"] {{ background-color: {GOLD} !important; }}

        /* --- Metrics --- */
        div[data-testid="stMetric"] {{
            background-color: {BG_SOFT}; border: 1px solid {BORDER}; border-radius: 8px;
            padding: 0.6rem 0.8rem; border-top: 3px solid {GOLD};
        }}
        div[data-testid="stMetricLabel"] {{ color: {GRAY_MUTED}; }}
        div[data-testid="stMetricValue"] {{ color: {CHARCOAL}; }}

        /* --- Dividers: a slim green-to-gold line instead of a plain rule --- */
        div[data-testid="stMarkdownContainer"] hr {{
            height: 3px; border: none; border-radius: 2px;
            background: linear-gradient(90deg, {GREEN} 0%, {GOLD} 100%);
        }}

        /* --- Deadline calendar (Ringkasan Beranda): smaller footprint --- */
        .st-key-{CALENDAR_CONTAINER_KEY} div[data-testid="stButton"] button {{
            font-size: 0.72rem !important; min-height: 1.9rem !important;
            padding: 0.1rem 0 !important; line-height: 1.1 !important;
        }}
        .st-key-{CALENDAR_CONTAINER_KEY} div[data-testid="column"] {{ padding: 0 2px !important; }}
        .st-key-{CALENDAR_CONTAINER_KEY} h4, .st-key-{CALENDAR_CONTAINER_KEY} h6 {{ margin: 0.2rem 0 !important; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(subtitle: str = "LPSE Monitor") -> None:
    """Small banner echoing the real KALLA ASPAL wordmark's colors, in
    place of a plain st.title(). Plain text, no external image - keeps the
    app self-contained (no logo file to lose track of) while still looking
    like it belongs to Kalla Aspal."""
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
