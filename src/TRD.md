# Technical Requirements Document (TRD)

**Product:** LPSE Tender Monitoring App
**TRD Version:** 1.0 (adapted to match the shipped codebase — see Section 0)
**Architecture:** Local-first, modular monolith (one Streamlit entrypoint + flat service/data modules)
**Primary Runtime:** Python
**UI Framework:** Streamlit
**Database:** SQLite

---

# 0. About This Document

This TRD started from a draft written before (or without close reference to) the actual codebase — it described an *idealized* target architecture (nested `ui/pages/`, `ui/components/`, a `database/repository.py`, a `notifications` table, a `CHANGELOG.md`, etc.) rather than what's actually built.

This version has been reconciled against the real repository (`D:\Github Repository\kalla-aspal`) so it's safe to hand to any future coding agent — human or AI — as an accurate map, not an aspiration. The biggest corrections:

* The UI is **one file** (`app.py`, using `st.tabs()`), not a multipage `ui/pages/` + `ui/components/` + `ui/styles/` split. `ui/` today only holds `branding.py` and `style.css`.
* `database/` is **two flat files** (`database.py`, `models.py`), not a `connection.py` / `models.py` / `repository.py` split.
* There is **no `activity_logs` table** — the "Aktivitas Terbaru" feed is computed live by merging the two snapshot tables.
* There is **no `notifications` table** — deadline reminders are fire-and-forget Windows toast notifications; the only persisted state is a same-day "already acknowledged" flag in a plain text file.
* `services/` has 10 real modules, named differently from the original draft's `scrape_service.py` / `package_service.py` / `notification_service.py` / `logging_service.py`.
* **No Playwright, no pandas, no ORM** are in use — `requirements.txt` is `streamlit`, `requests`, `beautifulsoup4`, `openpyxl`, `pytest`, and `win11toast` (Windows-only).
* `PROJECT_STATUS.md` already serves as the project's changelog — there is no separate `CHANGELOG.md`, and there shouldn't be one unless asked for.
* `logs/` exists as an empty placeholder folder (just `.gitkeep`) — file-based logging via Python's `logging` module is **not implemented yet**, despite being described as if it were.

Where the original draft's *principles* still hold (simplicity, modular monolith, SQLite, Streamlit, minimal dependencies, local-first, future-online-as-a-phase-not-a-rewrite), they're kept. Where it described structure that doesn't exist, this version describes what's actually there instead, and treats the idealized version as an optional future direction — not a refactor to do proactively.

This document pairs with `PRD.md` (product intent, kept as originally written) and `AGENTS.md` (working conventions for whoever — human or AI — picks this project up next).

---

# 1. Technical Philosophy

The application should be:

* Lightweight
* Simple to operate
* Professionally structured
* Easy to maintain
* Easy for an AI coding agent to understand
* Safe with user data
* Suitable for Windows
* Capable of future online deployment

The application should use the **simplest technology capable of solving the requirement reliably**.

Do not introduce infrastructure merely because it is technically possible.

The architecture is a:

> **Modular Monolith**

rather than a microservice architecture — and today, concretely, that means one Streamlit script plus a handful of flat, single-purpose modules. That's a feature, not a gap: don't "fix" it into a deeper folder structure just because a more elaborate structure exists in theory. See Section 7.

---

# 2. Technology Stack (Actual)

## 2.1 Core Language

**Python 3.x** — `run_app.bat` bootstraps the interpreter automatically on a machine that doesn't have it. There is no hard version pin enforced in code today; don't assume 3.12+ specifically unless you've checked what's actually installed on the target machine.

Python is used because the application primarily performs:

* Web scraping
* Data processing
* Database operations
* Excel manipulation
* Administrative automation

---

# 3. User Interface

## Streamlit

Streamlit is the UI framework, confirmed in active use throughout `app.py` (`st.tabs`, `st.popover`, `st.dataframe`, `st.status`, `st.session_state`, etc.).

Reasons it was chosen still apply:

* Lightweight
* Python-native
* Minimal frontend development
* Suitable for internal dashboards
* Easy local deployment
* Easy future online deployment
* Good support for tables and data-oriented interfaces

Do not introduce React, Vue, Angular, or a separate JavaScript frontend unless a future requirement makes Streamlit genuinely insufficient.

---

# 4. UI Architecture (Actual)

The entire UI lives in **one file**, `app.py` (~1,150 lines), using `st.tabs()` for:

```text
Dashboard | Cek Tender (Daftar Lengkap) | Ringkasan Beranda | Kata Kunci | Excel | Wilayah LPSE
```

Reusable rendering logic is a set of small `render_*` helper functions defined near the top of `app.py` itself — not in separate component files:

```text
render_package_card()          - one package card (new/updated)
render_package_list()          - capped list + "Tampilkan Semua" button
render_result_banner()         - bell popover + sort control + N-baru banner
render_deadline_calendar_popover() - small calendar icon + month view
render_activity_card()         - one "Aktivitas Terbaru" card
render_filter_controls()       - filter/sort bar for the saved-package tables
render_excel_export_panel()    - one dataset's Excel export settings/buttons
```

`ui/` itself only holds:

```text
ui/
├── branding.py   - render_header(), render_road_strip(), CALENDAR_CONTAINER_KEY, inject_css()
└── style.css     - all custom CSS
```

There is currently **no** `ui/components/`, `ui/pages/`, or `ui/styles/` split, and no `st.Page`-based multipage app. This is intentional, not an oversight: Streamlit's top-to-bottom script model gets multipage-like behavior from `st.tabs()` without needing separate page files, and `app.py` has stayed navigable at its current size.

> **Rule:** UI code should display and collect information. It should not contain scraping or database business logic (this part of the original principle still holds — see Section 14 for the one accepted exception).

**When (not if) to split further:** if `app.py` gets to a size where a specific section can't be found by scrolling/searching in a few seconds, pull the `render_*` helpers out into a single new `ui/components.py` file first. Only reach for the fully nested `components/` + `pages/` + `styles/` structure if a single flat file genuinely stops being enough — don't restructure preemptively just because a deeper structure was once described as the target.

---

# 5. CSS Strategy

Custom CSS lives in one external file:

```text
ui/style.css
```

`branding.inject_css()` reads it fresh on every call (no caching), so a hand-edit shows up on the next browser refresh without restarting the app.

CSS is scoped to specific components using Streamlit's `st.container(key=...)` → `.st-key-<name>` selector mechanism (e.g. `branding.CALENDAR_CONTAINER_KEY` → `.st-key-kalla_calendar` in `style.css`), rather than one global stylesheet with no scoping.

Prefer:

```python
# CSS lives in ui/style.css, loaded once via branding.inject_css()
```

over:

```python
st.markdown("""<style> ... </style>""", unsafe_allow_html=True)
```

scattered through `app.py`. Follow the existing `.st-key-*` scoping pattern for any new CSS-scoped component rather than inventing a new mechanism.

---

# 6. Backend Architecture

No separate backend server is required for the local version. Streamlit acts as the application layer.

```text
                 STREAMLIT UI (app.py)
                      │
                      ▼
               APPLICATION SERVICES (services/)
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
       SCRAPER     DATABASE      EXCEL
     (scraper/)   (database/)  (openpyxl via
                                excel_service.py)
          │           │           │
          ▼           ▼           ▼
        LPSE        SQLite      XLSX
```

---

# 7. Application Layers (Actual)

## Layer 1 — UI

```text
app.py          - all tabs/pages + render_* helpers
ui/branding.py   - header/road-strip HTML, CSS container key, inject_css()
ui/style.css     - all custom CSS
```

## Layer 2 — Services

```text
services/
├── comparison_service.py     - Daftar Lengkap: scrape + compare + classify NEW/UPDATED/EXISTING
├── homepage_service.py       - Ringkasan Beranda: same idea, separate dataset
├── filter_service.py         - filter/sort/summary helpers for the saved-package tables
├── calendar_service.py       - month-grid + deadline-grouping for the calendar popover
├── activity_service.py       - merges both snapshot tables into "Aktivitas Terbaru"
├── excel_service.py          - safe Excel read/write/backup
├── keyword_service.py        - keyword matching logic
├── region_import_service.py  - bulk-import regions from pasted text / bookmarks
├── reminder_service.py       - pure date logic for deadline reminders (no Windows dependency)
└── status_flags.py           - detects "gagal"/"batal"/"diulang" etc. in package names
```

There is **no** `scrape_service.py`, `package_service.py`, `notification_service.py`, or `logging_service.py` as separate files. Their responsibilities landed elsewhere:

* Scrape orchestration lives inside `comparison_service.run_scrape_and_compare()` / `homepage_service.run_homepage_scrape_and_compare()`, not a standalone scraping service.
* There is no persisted "notification" concept beyond the reminder toast + same-day ack file (Section 13).
* There is no dedicated logging service (Section 22).

## Layer 3 — Scraper

```text
scraper/
├── lpse_scraper.py          - /lelang (Daftar Lengkap): fetch + parse + LPSEScraperError family
└── lpse_homepage_scraper.py - homepage summary (Ringkasan Beranda), incl. Akhir Pendaftaran
```

Both modules own their own parsing and return typed dataclasses directly — there's no separate `parser.py` / `models.py` split inside `scraper/`. Each dataset's scraper stays fully separate from the other's, on purpose (see `AGENTS.md`).

## Layer 4 — Data Access

```text
database/
├── database.py  - connection helper (get_connection/connect) + every query function, flat
└── models.py    - SCHEMA_SQL only (the raw DDL, plain string)
```

No ORM, no `repository.py`, no separate `connection.py`. Services call `db.*` functions directly.

**Accepted deviation:** `app.py` also calls `db.*` functions directly in a few places — notably keyword CRUD (Kata Kunci tab) and region CRUD (Wilayah LPSE tab) — rather than always going through a service. This is deliberate: there's no real business logic in "add a keyword" beyond a validated insert, so a service wrapper would add a layer without adding value. New logic with actual business rules (scraping, comparison, filtering, Excel writing) should still go through `services/`, per Section 14.

## Layer 5 — Configuration

```text
config/
├── default_keywords.py  - seed keyword list (used once, on first-ever init_db())
└── reminder_times.txt   - plain text, one HH:MM per line, read by check_reminders.py
```

No `settings.py` / `defaults.py` module exists. There hasn't been a need for one — add one only when a real cross-cutting setting shows up that doesn't fit either file above.

---

# 8. Scraping Technology

### Primary

```text
requests
```

for HTTP retrieval.

### Parsing

```text
BeautifulSoup
```

for HTML parsing.

### Browser Automation

```text
Playwright
```

**Not currently used.** Both scrapers work today with plain `requests` + `BeautifulSoup`. Only reach for Playwright if a specific LPSE page genuinely can't be retrieved without a real browser (e.g. JS-rendered content) — don't add it speculatively, and don't add it to `requirements.txt` until it's actually needed.

---

# 9. Scraper Design

```text
URL
 ↓
HTTP Request
 ↓
Response Validation
 ↓
HTML Parsing
 ↓
Normalization
 ↓
Package dataclass objects
```

Each scraper module exposes a simple top-level function (`lpse_scraper.get_packages(region)`, the homepage equivalent in `lpse_homepage_scraper.py`) returning normalized package data.

---

# 10. Scraper Error Handling

The scraper must handle:

* Timeout
* Connection error
* HTTP errors
* Invalid LPSE region
* Unexpected HTML
* Missing fields
* Website structure changes

Errors are converted into application-level exceptions — `LPSEScraperError` and its subtypes in `scraper/lpse_scraper.py` — each carrying a `user_message` the UI can show directly, so `app.py`/services never need to format a raw Python traceback for the user. Follow this same pattern (a typed exception with a `.user_message`) for any new failure mode.

---

# 11. Request Safety

The scraper should:

* Use reasonable timeouts.
* Avoid excessive or unnecessary repeated requests.
* Respect website availability.
* Avoid parallel scraping unless required.

For multiple regions, sequential requests are the default (confirmed: `run_scrape_and_compare`/`run_homepage_scrape_and_compare` loop region-by-region). Concurrency can be considered later only if scraping performance becomes a measured, real problem — not preemptively.

---

# 12. Database

**SQLite.** No PostgreSQL, MySQL, MongoDB, Redis, or other database for the local version.

```text
data/lpse_monitor.db
```

(`database.DEFAULT_DB_PATH`, relative to the project root — confirmed in `database.py`.)

---

# 13. Database Tables (Actual Schema)

Source of truth: `database/models.py`'s `SCHEMA_SQL`. Ten tables exist today:

```text
regions
    id, region_name, region_identifier (UNIQUE), base_url, is_active,
    created_at, updated_at

keywords
    id, keyword (UNIQUE), is_enabled, created_at, updated_at

packages                       -- Daftar Lengkap (/lelang), latest known state
    id, package_id (UNIQUE), fingerprint (UNIQUE), region_identifier,
    nama_paket, nama_paket_raw, badges (JSON), instansi, tahapan,
    metode_kualifikasi, jenis, metode_evaluasi, jenis_pengadaan,
    tahun_anggaran, hps_text, hps_value, nilai_kontrak_text,
    nilai_kontrak_value, evaluasi_ulang, penawaran_ulang, konsolidasi,
    oap_only, package_url, is_relevant, matched_keywords (JSON),
    first_seen_at, last_seen_at, last_updated_at

package_snapshots               -- change history for `packages`
    id, package_key, scrape_run_id, tahapan, hps_value,
    nilai_kontrak_value, change_summary, snapshot_json (JSON),
    created_at

scrape_runs                     -- one row per "Cek Tender" run
    id, started_at, finished_at, regions_scraped (JSON),
    total_packages_found, relevant_packages_found, new_packages_found,
    updated_packages_found, status, error_message

homepage_packages               -- Ringkasan Beranda, latest known state
    id, package_id (UNIQUE), fingerprint (UNIQUE), region_identifier,
    section, kategori, nama_paket, badges (JSON), hps_text, hps_value,
    akhir_pendaftaran_text, akhir_pendaftaran_at, display_position,
    package_url, is_relevant, matched_keywords (JSON),
    first_seen_at, last_seen_at, last_updated_at

homepage_scrape_runs            -- one row per "Cek Ringkasan Beranda" run
    (same shape as scrape_runs)

homepage_package_snapshots      -- change history for `homepage_packages`
    id, package_key, scrape_run_id, hps_value, akhir_pendaftaran_at,
    change_summary, snapshot_json (JSON), created_at

excel_config                    -- one row per dataset ('lelang' | 'beranda')
    dataset (PK), file_path, sheet_name, start_cell, enabled_columns (JSON),
    mode, use_excel_table, updated_at

excel_generated_rows            -- which (file, sheet, row) this app itself wrote
    id, file_path, sheet_name, package_key, row_number, written_at
```

**There is no `activity_logs` table.** The "Aktivitas Terbaru" dashboard tab is computed live, on every page load, by `activity_service.get_recent_activity()` merging `package_snapshots` + `homepage_package_snapshots` and sorting by `created_at`. If you need a persisted, queryable activity log independent of the snapshot tables, that's new work — it doesn't exist today.

**There is no `notifications` table.** Deadline reminders (`check_reminders.py` + `win11toast`) are fire-and-forget Windows toast notifications with no database-backed history, severity, or read/unread state. The only persisted reminder state is a single ISO date written to a plain text ack file by `services/reminder_service.mark_acknowledged()`, tracking "was today's reminder already acknowledged" — not per-package, not per-admin, resets automatically the next calendar day. If a real notification history/audit trail is wanted later, it needs a new table — don't assume one already backs the reminder feature.

---

# 14. Database Access

Prefer:

```text
UI (app.py)
 ↓
Service (services/*.py)
 ↓
database.py
 ↓
SQLite
```

for anything with real business logic (scraping, comparison, filtering, Excel writing).

**Accepted exception:** simple CRUD with no business logic — adding/renaming/toggling a keyword or region — calls `database.py` functions directly from `app.py`. This is existing, deliberate practice (Section 7, Layer 4), not something to "fix" by inserting a pass-through service wrapper that would just forward the same call.

---

# 15. Package Identity

Primary identifier:

```text
package_id  (the site's own "Kode Lelang")
```

If `package_id` is unavailable, a deterministic fallback `fingerprint` is used instead (built in `scraper/lpse_scraper.py`'s `make_fallback_fingerprint`). Exactly one of `package_id` / `fingerprint` is non-null per row — both columns are declared `UNIQUE` in the schema.

---

# 16. Package Comparison

Handled by `services/comparison_service.py` (Daftar Lengkap) and `services/homepage_service.py` (Ringkasan Beranda) — same logic shape, kept as two separate modules because the two datasets never mix (see `AGENTS.md`).

```text
Scraped Package
      ↓
Find Existing Package (by package_id, else fingerprint)
      ↓
       ┌───────────────┐
       │               │
      NO              YES
       │               │
       ▼               ▼
      NEW         Compare TRACKED_FIELDS
                       │
                ┌──────┴──────┐
                ▼             ▼
             Changed       Unchanged
                │             │
                ▼             ▼
             UPDATED       EXISTING
```

`TRACKED_FIELDS` in `comparison_service.py` is `("tahapan", "hps_value", "nilai_kontrak_value", "nama_paket")` — only a change in one of these fields produces an UPDATED classification and a new snapshot row.

---

# 17. Keyword Filtering

Handled by `services/keyword_service.py` (matching) with relevance flags stored on each package row (`is_relevant`, `matched_keywords`). Filtering is separate from scraping — the scraper retrieves everything, the keyword service decides relevance — so future keyword categories can be introduced without touching the scraper.

---

# 18. Keyword Matching

* Case-insensitive
* Partial text matching
* Configurable via the Kata Kunci tab (no source-code edit needed)
* Deterministic and testable (`tests/test_keyword_service.py`)

---

# 19. Excel Integration

**openpyxl**, isolated in `services/excel_service.py`.

The application does not use pandas to modify the existing workbook, so workbook structure/formatting is preserved. (Confirmed: `pandas` is not in `requirements.txt`.) Pandas may be used for temporary in-memory manipulation if genuinely useful, but it must not control the workbook-writing process.

**`PROJECT_ROOT` vs `REPO_ROOT`:** `excel_service.py` defines both. `PROJECT_ROOT` is `src/` (the app's own code, same convention as `database.py`'s `PROJECT_ROOT`) - used for `BACKUPS_DIR`, since backups are an internal artifact of this app. `REPO_ROOT` is `PROJECT_ROOT.parent` (the true top-level folder) - used as the default scan root for `discover_excel_files()`, specifically because Nikol's real workbook is kept outside `src/`, next to `run_app.bat` (Section 29). Anything that needs to find or reference the user's own workbook should use `REPO_ROOT`, not `PROJECT_ROOT`.

---

# 20. Excel Safety Workflow

```text
Check File
   ↓
Create Backup   (backups/ folder — confirmed present in the project root)
   ↓
Open Workbook
   ↓
Validate Target Sheet/Range
   ↓
Modify Application-Owned Data Only
   ↓
Save
   ↓
Validate Output
```

If any stage fails, the original workbook stays untouched.

---

# 21. Excel File Locking

If the workbook is currently open in Microsoft Excel and can't safely be modified, show:

> "File Excel sedang digunakan. Tutup file terlebih dahulu kemudian coba lagi."

Do not forcibly overwrite the file.

---

# 22. Application-Owned Excel Data

The application knows exactly which rows it owns via the `excel_generated_rows` table (Section 13) — it tracks every `(file_path, sheet_name, package_key, row_number)` triple this app itself wrote, so:

* **Replace mode** only clears rows this app previously wrote — never a row the user typed in by hand.
* **Append-new mode** knows which packages already have a row, so it never duplicates one.

This is already implemented, not aspirational — don't re-derive "which rows are ours" by position or by re-scanning the sheet; use `excel_generated_rows`.

---

# 23. Logging

**Not yet implemented.** `logs/` exists in the project root but currently holds only a `.gitkeep` placeholder — nothing writes to it today.

Historical/activity information is currently visible only through:

* The "Aktivitas Terbaru" dashboard tab (derived live from the snapshot tables — Section 13).
* Streamlit's own `st.status()` / `st.error()` output during a live scrape (not persisted after the page reruns).

If file-based logging is added later, use Python's stdlib `logging` module writing to `logs/app.log` / `logs/errors.log` as originally planned — don't introduce a third-party logging framework. But don't claim or build against logging that isn't there yet; verify with a fresh `device_list_dir` on `logs/` before assuming otherwise, since this is exactly the kind of gap that's easy to inherit from an old draft.

---

# 24. Activity History

Distinct from Section 23 (Logging): "Aktivitas Terbaru" already works today, computed live rather than stored in its own table. See Section 13 and `services/activity_service.py`.

---

# 25. Notifications / Reminders (Actual)

Implemented as:

```text
config/reminder_times.txt   - editable list of HH:MM check times (e.g. 08:00 / 13:00 / 16:00)
services/reminder_service.py - pure date logic: which deadlines fall in the warning window,
                                plus the "already acknowledged today" file-based flag
check_reminders.py          - the actual firing side: reads the above, calls win11toast
setup_reminders.bat         - registers/re-registers the Windows Task Scheduler entries
```

There is no database-backed notification history, severity levels, or read/unread state (see Section 13). Clicking or dismissing a toast marks *today* acknowledged (via a plain ack file, not a DB row) so a later scheduled check the same day stays quiet; it resets automatically the next day. If persisted notification history is wanted later, it's new work — extend `check_reminders.py`/`reminder_service.py` to write to a new table rather than assuming one exists.

Future external channels (email, Telegram, WhatsApp) remain deferred — see `PRD.md` Section 31. Don't build toward them proactively.

---

# 26. UI Components

Today's reusable pieces are the `render_*` functions inside `app.py` (Section 4) — there is no separate `ui/components/` module yet. If/when one is warranted, prefer a single flat `ui/components.py` before a nested `components/` folder (Section 4's "when to split further" rule).

---

# 27. UI Styling

```text
ui/style.css
```

One file, loaded centrally via `branding.inject_css()` (Section 5). CSS variables/custom properties may be introduced there for a design-system feel, but check what's already defined in `style.css` before adding new color/spacing values — don't duplicate an existing token under a new name.

---

# 28. Design System

Keep the existing restrained, professional look already established (Notion-style cards, small popover icons for secondary detail, Indonesian-language labels, compact spacing). Don't introduce a new visual language without checking with Nikol first — recent UI work (the bell status popover, the calendar popover) already set the house style; match it rather than reinventing it. See `AGENTS.md` for the specific conventions to follow.

---

# 29. Project Structure (Actual)

Two tiers, as of the 2026-09-22 cleanup: a thin repo root holding only what Nikol touches directly, and `src/` holding the entire application (code + its own docs) as one self-contained unit — since `app.py` isn't standalone, it imports `database/`, `scraper/`, `services/`, `ui/`, and `config/` as siblings, so those all had to move together, not just the loose files.

```text
kalla-aspal/                     (repo root - only what Nikol opens directly)
│
├── run_app.bat                 - double-click to launch (cd's into src/, then runs the app there)
├── push_to_github.bat          - git add/commit/push helper
├── Kalla_Aspal Scraper.xlsx    - Nikol's real workbook - deliberately kept OUTSIDE src/
├── .gitignore                  - stays at the true repo root (git-correct); patterns updated
│                                  for the src/ prefix (Section 32)
├── venv/                       - OLD virtualenv from before the 2026-09-22 move; orphaned,
│                                  safe to delete (a fresh one auto-creates inside src/) -
│                                  can't move a venv (baked-in absolute paths), only recreate it
├── web-prototype/               - unused scaffold, untouched by the move, do not build out
│
└── src/                        - the entire application, self-contained
    │
    ├── app.py                    - the entire Streamlit UI (all tabs, all render_* helpers)
    ├── launcher.py                - PyInstaller entrypoint (see Section 29a)
    ├── requirements.txt
    ├── README.md
    ├── PROJECT_STATUS.md          - the living changelog/status doc (Section 43)
    ├── PRD.md
    ├── TRD.md                     - this file
    ├── AGENTS.md                  - working conventions for AI coding agents (Section 44)
    │
    ├── build_exe.bat                - optional PyInstaller packaging (not the primary distribution path)
    ├── lpse_monitor.spec           - PyInstaller spec for build_exe.bat
    ├── check_reminders.py           - deadline reminder firing (Windows Task Scheduler entrypoint)
    ├── setup_reminders.bat          - registers/removes the Task Scheduler entries
    │
    ├── .streamlit/
    │   └── config.toml             - color theme; must live in the CWD streamlit runs from
    │
    ├── config/
    │   ├── default_keywords.py
    │   └── reminder_times.txt
    │
    ├── database/
    │   ├── database.py
    │   └── models.py               - SCHEMA_SQL only
    │
    ├── scraper/
    │   ├── lpse_scraper.py
    │   └── lpse_homepage_scraper.py
    │
    ├── services/
    │   ├── activity_service.py
    │   ├── calendar_service.py
    │   ├── comparison_service.py
    │   ├── excel_service.py        - PROJECT_ROOT = src/; REPO_ROOT = its parent, used
    │   │                              specifically for finding Nikol's .xlsx outside src/
    │   ├── filter_service.py
    │   ├── homepage_service.py
    │   ├── keyword_service.py
    │   ├── region_import_service.py
    │   ├── reminder_service.py
    │   └── status_flags.py
    │
    ├── ui/
    │   ├── branding.py
    │   └── style.css
    │
    ├── data/                       - lpse_monitor.db lives here (gitignored)
    ├── backups/                    - Excel backups, timestamped (internal to the app,
    │                                  unlike the real workbook itself, which stays outside src/)
    ├── logs/                       - currently empty (Section 23)
    ├── tests/                      - flat pytest files, one per module (see Section 33)
    └── venv/                       - local virtualenv (gitignored), created fresh inside
                                       src/ the first time run_app.bat runs after the move
```

Every path inside `src/` resolves relative to its own file's location (`Path(__file__).resolve().parent...`) or to the script's own directory (`cd /d "%~dp0"` in the `.bat` files), so nothing inside `src/` needed a code change for the move — moving the whole folder down one level just shifts everyone's shared anchor point together. The two things that DID need a code change were the ones that reach *across* the `src/` boundary: `run_app.bat` (adds one `cd` into `src/` before running anything) and `services/excel_service.py`'s file-discovery default (must look at the true repo root, not `src/`, or it stops finding Nikol's workbook — see the `excel_service.py` entry above and Section 19's `REPO_ROOT` note below).

The original draft's more elaborate nested structure (`ui/pages/`, `ui/components/`, `database/repository.py`, etc.) is not a mistake to fix — it's simply not what exists, and shouldn't be built out preemptively. Treat it as an option for if/when a specific layer genuinely outgrows its current flat shape (Section 4's rule), not a target to migrate toward on principle.

## 29a. Packaging note

`launcher.py`, `lpse_monitor.spec`, and `build_exe.bat` exist for optional PyInstaller `.exe` packaging — this was discussed as a "nice to have, not necessary" alternative to `run_app.bat`. Treat `run_app.bat` (double-click, auto-bootstraps Python/dependencies) as the actual primary way this app is run, unless Nikol says otherwise.

---

# 30. Dependency Philosophy

Keep dependencies minimal. Actual `requirements.txt`:

```text
streamlit>=1.37
requests>=2.31
beautifulsoup4>=4.12
openpyxl>=3.1
pytest>=7.4
win11toast>=0.36   ; sys_platform == "win32"   (deadline reminders only, Windows-only)
```

Potential future dependency: `playwright`, only if the scraper genuinely needs it (Section 8) — not added today.

Python standard-library modules should be preferred whenever sufficient. Avoid adding packages for trivial functionality.

---

# 31. Environment Configuration

No `.env` file is in use, and the local application doesn't need one to run. Introduce one only if secrets or real deployment configuration become necessary (e.g. for a future online deployment).

---

# 32. Local Data Paths

Confirmed relative, not hardcoded:

```text
src/data/lpse_monitor.db      (database.DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "lpse_monitor.db")
src/backups/
src/logs/
```

The application works when the whole project folder is moved to another computer — this already held true when it was one flat folder, and still holds now that it's `run_app.bat`/`push_to_github.bat`/the workbook at the repo root plus everything else in `src/` (Section 29): every one of these paths is still computed relative to a file's own location, never hardcoded to a specific machine's absolute path.

---

# 33. Testing

**pytest**, and it's already in active use — `tests/` has one file per real module (`test_activity_service.py`, `test_calendar_service.py`, `test_comparison_service.py`, `test_database_regions.py`, `test_excel_service.py`, `test_filter_service.py`, `test_homepage_scraper_parsing.py`, `test_homepage_service.py`, `test_keyword_crud.py`, `test_keyword_service.py`, `test_region_import_service.py`, `test_reminder_service.py`, `test_scraper_parsing.py`, `test_status_flags.py`), not just the four broad files the original draft suggested (`test_scraper.py`/`test_filter.py`/`test_comparison.py`/`test_excel.py`). Keep the existing one-file-per-module convention for new tests rather than consolidating into fewer, broader files.

**Known limitation:** an AI coding agent working from Anthropic's cloud sandbox cannot run `pytest` there directly — no PyPI network access. Verify pure-logic changes with a manual `python3 -c` assertion script instead, and say so plainly rather than claiming the real test suite was run. `python3 -m py_compile` remains available and should be used before delivering any changed `.py` file, at minimum.

---

# 34. Test Philosophy

Do not attempt 100% code coverage. Prioritize tests around operations where mistakes could cause:

* Data loss
* Duplicate records
* Incorrect NEW/UPDATED classification
* Excel corruption

---

# 35. Performance

No Redis, Celery, background workers, message queues, or distributed processing. Synchronous processing is sufficient for the expected administrative-scale workload. Optimize only when actual measurements show a problem.

---

# 36. Concurrency

The local application is for one administrator at a time. SQLite is sufficient. Don't implement complex concurrency handling unless future online deployment genuinely requires it.

---

# 37. Security — Local Version

No login/auth/OAuth/API keys/cloud secrets required locally. Still:

* Don't execute arbitrary user input as code.
* Validate file paths.
* Validate LPSE URLs.
* Validate imported Excel/bookmark files.
* Don't expose local files through the UI unintentionally.

---

# 38. Future Online Architecture

Deferred, not required now.

```text
User Browser
     ↓
Streamlit Application
     ↓
Services
     ↓
Cloud Database (if/when multi-user access is actually needed)
     ↓
LPSE
```

SQLite may remain suitable for a single-user online deployment. Don't migrate to PostgreSQL merely because the app is deployed online — only if concurrent multi-user access actually requires it.

---

# 39. Automatic Online Data Updates

Deferred. If/when built:

```text
Scheduled Trigger
       ↓
Scrape Service
       ↓
LPSE
       ↓
Comparison Service
       ↓
Database
       ↓
Notification Service
```

The scheduler should stay separate from the scraper so both manual ("Cek Tender" button) and scheduled checks call the exact same scrape/compare functions that exist today (`run_scrape_and_compare` / `run_homepage_scrape_and_compare`) — no rewrite of scraping logic needed.

---

# 40. Online Scheduling

No local background daemon for the current version (the Windows Task Scheduler entries from `setup_reminders.bat` are for deadline reminders specifically, not general re-scraping). When online deployment happens, use the hosting platform's scheduled-execution mechanism, configurable (morning / night / every X hours / custom).

---

# 41. Deployment Philosophy

> **Local-first and deployment-ready, not cloud-dependent.**

Per `devices-and-workflow.md` (in the project's claude.ai docs, not this repo): Streamlit Community Cloud is confirmed to work for this app; Vercel does not. `web-prototype/` is an unused scaffold — leave it alone unless explicitly asked to build it out.

Online deployment is a **deployment upgrade**, not an application rewrite.

---

# 42. Versioning

If/when release tags are introduced, use semantic versioning (`MAJOR.MINOR.PATCH`). Not currently in active use — don't assume git tags exist without checking.

---

# 43. Change Management

**`PROJECT_STATUS.md` is already the project's changelog** — confirmed present at the repo root and described in `devices-and-workflow.md` as the authoritative detailed history. There is no separate `CHANGELOG.md`, and one should not be created — that would fork the change history into two places that inevitably drift apart. Keep appending significant changes to `PROJECT_STATUS.md`.

---

# 44. AI Coding Rules

AI coding agents working on this project must:

1. Read `PRD.md` before significant product changes.
2. Read this file (`TRD.md`) before significant architectural changes.
3. Read `AGENTS.md` before making any non-trivial change — it holds working conventions specific to this project and this user that aren't "architecture" but matter just as much.
4. Read `PROJECT_STATUS.md` for recent history before assuming something hasn't been tried or built yet.
5. Inspect existing code before modifying it — check `database/models.py`'s `SCHEMA_SQL` before assuming a table exists, and check `services/` before assuming a service module exists, rather than trusting a document's description alone (including this one — documents drift, code is ground truth).
6. Avoid rewriting working modules unnecessarily. A module not matching this document's "ideal" shape (Section 29's aspirational nested structure) is not, by itself, a reason to rewrite it.
7. Avoid introducing dependencies without justification.
8. Preserve existing functionality.
9. Keep UI, services, scraper, database, and Excel logic separated — for *new* logic; don't retroactively "fix" the accepted CRUD exception in Section 14.
10. Prefer simple solutions.
11. Explain architectural changes before implementing them when they affect the overall design, and wait for confirmation before large-scope changes.

---

# 45. Definition of Technical Success

The application is technically successful when:

* It runs locally without cloud infrastructure.
* An administrator can operate it without programming knowledge.
* LPSE data can be retrieved reliably.
* New and updated packages are detected correctly.
* Historical data persists.
* Activity is visible and Excel files can be safely updated and backed up.
* UI styling can be modified without rewriting business logic.
* The project remains understandable to another developer or AI coding agent — including by this document staying honest about what's actually built versus what's aspirational.
* Future Streamlit deployment can occur without a fundamental rewrite.

---

# 46. Explicit Non-Requirements

Intentionally NOT required for the current version:

* React / Vue / Angular / Node.js backend
* PostgreSQL / MongoDB / Redis
* Docker / Kubernetes / microservices / message queues
* Authentication
* Cloud storage / cloud database
* Automatic scheduling (beyond the existing deadline-reminder Task Scheduler entries)
* External notification services (email/Telegram/WhatsApp)
* pandas as the Excel-writing mechanism
* Playwright (until requests+BeautifulSoup genuinely stop being enough)
* A separate `CHANGELOG.md` (Section 43)
* File-based logging via a third-party framework (Section 23 — stdlib `logging` only, if/when added)

These may be reconsidered only when an actual requirement justifies them.

---

# 47. Final Architecture

```text
┌───────────────────────────────────────────┐
│         STREAMLIT UI  (app.py)             │
│                                             │
│ Dashboard │ Cek Tender │ Ringkasan Beranda │
│ Kata Kunci │ Excel │ Wilayah LPSE          │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
┌───────────────────────────────────────────┐
│          SERVICE LAYER (services/)         │
│                                             │
│ comparison │ homepage │ filter │ calendar  │
│ activity │ excel │ keyword │ region_import │
│ reminder │ status_flags                    │
└───────┬───────────────┬─────────────┬───────┘
        │               │             │
        ▼               ▼             ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│    SCRAPER   │ │    SQLite    │ │   openpyxl   │
│  (scraper/)  │ │ (database/)  │ │(excel_service)│
│              │ │              │ │              │
│ requests     │ │ 10 tables,   │ │ Existing XLSX │
│ BeautifulSoup│ │ flat access  │ │ + backups/    │
│ (Playwright* │ │              │ │              │
│  not in use) │ │              │ │              │
└──────┬───────┘ └──────────────┘ └──────────────┘
       │
       ▼
┌──────────────────────┐
│     LPSE / SPSE      │
└──────────────────────┘

* Playwright: not currently in use, only if requests+BeautifulSoup genuinely stop being enough.
```

The core principle is unchanged from the original draft:

> **Keep the application technically simple, but organize the simple components professionally.**
