# Kalla Aspal - LPSE Monitor

A local-first tool for admin staff to keep an eye on LPSE/SPSE government
procurement tenders and get told when a new road-construction package
shows up.

Runs entirely on your own Windows PC. No cloud database, no login, no
internet-facing deployment - everything (settings, keyword list, region
list, every package ever seen) lives in one local SQLite file under
`data/`.

**For the full project status - what's done, what's not, dated changelog,
architecture diagram - see [`PROJECT_STATUS.md`](PROJECT_STATUS.md).**
This file is the quick-start guide; that one is the detailed log.

## Installation (Windows) - easiest way

1. Install Python 3.11+ from [python.org](https://www.python.org/downloads/)
   (tick "Add python.exe to PATH" during setup). This is the only step
   that needs a terminal-ish install wizard - everything else below is
   double-clicking.
2. Double-click **`run_app.bat`** in this folder. The first time, it sets
   itself up automatically (1-3 minutes); every time after that it just
   opens the app straight away. No typing commands required.

The first run creates `data/lpse_monitor.db` automatically (with the
default road-related keyword list already seeded in).

### Alternative: manual setup (if you prefer a terminal)

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

### Standalone .exe (optional, no Python required to RUN it)

`build_exe.bat` packages the app into `dist\LPSE_Monitor\LPSE_Monitor.exe`
using PyInstaller, so it can run on a PC without Python installed at all.
Run `run_app.bat` at least once first, then double-click `build_exe.bat`.
**Honest note:** this build step has not been verified on a real Windows
machine yet (see PROJECT_STATUS.md) - if it errors on first try, that's
expected to be fixable, not a dead end.

## How to use it

1. Go to the **Wilayah LPSE** tab and add every LPSE region you want to
   monitor (name + region identifier, e.g. `singkawangkota` or
   `kalbarprov`). This only needs doing once per region - it's remembered.
   Adding many regions at once? Open **Import Massal Wilayah** on that
   same tab instead of the one-by-one form - paste a list of LPSE URLs
   (or bare identifiers), or upload an exported browser bookmarks file
   (Chrome/Edge/Firefox all export the same format: **chrome://bookmarks**
   → ⋮ menu → **Export bookmarks**) and every LPSE link in it is picked up
   automatically.
2. Go to **Cek Tender (Daftar Lengkap)** and click **CEK TENDER** - this
   checks the full tender list (every status) for all active regions.
3. Go to **Ringkasan Beranda** and click **CEK RINGKASAN BERANDA** - this
   checks each region's homepage summary, which additionally carries a
   registration deadline ("Akhir Pendaftaran"), shown on a built-in
   calendar further down the tab (hover a marked day for a quick list,
   click a day for full detail - each package name shown is itself a
   clickable link straight to its LPSE page).
4. Either check will tell you **X PAKET BARU DITEMUKAN** (or "tidak ada
   paket baru") and list what's new/changed. Both keep a running,
   earliest-first table of everything relevant found so far - use the
   filter/sort controls above each table to narrow it down (e.g. only
   "Masa Sanggah") and see the HPS total recalculate for just that filter.
5. Go to **Dashboard** (the first tab) any time to see **Aktivitas
   Terbaru** - a clean, card-based feed of every new/changed package
   across BOTH datasets, newest first, including a warning badge when a
   package's own name suggests it was canceled/failed/re-tendered (see
   "Catatan" below).
6. Go to **Kata Kunci** to add/rename/enable/disable the keywords used to
   decide what counts as "terkait jalan", any time.
7. Go to **Excel** - it has its own sub-tab per dataset ("Daftar Lengkap"
   and "Ringkasan Beranda"), each exporting to its own configurable
   file/sheet/cell/columns, with automatic backup before every write. If
   you've already dropped an `.xlsx` file inside this project's folder,
   it'll show up as a one-click button instead of needing a typed path.
   Exports are written as a proper Excel Table (banded rows + filter
   dropdowns already on) by default.
8. Run it again in the morning and at night, per your normal workflow -
   the database remembers everything between runs.

**Catatan (nama paket berubah):** LPSE sometimes appends a status word
straight into a package's own name later on - e.g. "... (Tender Gagal)" or
"... (Diulang)". The app detects "gagal"/"batal"/"dibatalkan"/"diulang"/
"gugur" in a package's name and shows a visible warning/badge for it (in
the Dashboard feed, the per-check result cards, and a "Catatan" column on
both saved-package tables) - see `services/status_flags.py`. This is a
plain text check, not a guarantee; a human still makes the final call.

## Why two separate checks?

They answer different questions and come from different pages on the
site - see `scraper/lpse_homepage_scraper.py`'s module docstring for the
full technical reasoning:

| | Daftar Lengkap (`/lelang`) | Ringkasan Beranda (`/`) |
|---|---|---|
| Covers | every package this year, any status | only what the homepage currently features |
| Registration deadline | not available | yes ("Akhir Pendaftaran") |
| Needs login/session | yes (handled automatically) | no - plain public page |

## Pushing changes to GitHub

Double-click **`push_to_github.bat`** in this folder. It stages, commits
(asking for an optional short message), and pushes everything in one go -
no need to type git commands.

## Customizing the look (colors, spacing, cards)

All of the app's styling lives in one plain CSS file: `ui/style.css`. It's
organized into numbered, commented sections (palette, header, buttons,
tabs, metrics, cards, etc.) - open it, find the section for the thing you
want to change, edit the value, save, then just refresh the app in your
browser. No restart needed, no Python involved. The 10 color values at the
very top of the file (`:root { --kalla-green: ...; }`) control the whole
app's palette - change one there and it updates everywhere that color is
used.

Saved packages also get a small **"🆕 Baru"** marker in their table if
they were added or updated in roughly the last 24 hours (controlled by
`RECENT_WINDOW_HOURS` in `services/filter_service.py`, if you want that
window longer or shorter).

## Using it on another device

The easiest no-typing way to get this project (and future updates) onto a
second PC:

1. Install [GitHub Desktop](https://desktop.github.com/) on the other
   device and sign in with the same GitHub account.
2. In GitHub Desktop: **File → Clone repository**, pick `kalla-aspal`,
   choose a folder, click Clone. No command line involved.
3. Double-click `run_app.bat` there - same as the main PC.
4. Whenever you push updates from one device (via `push_to_github.bat`),
   open GitHub Desktop on the other device and click **Fetch origin / Pull
   origin** to get them - again, no typing.

Note: the SQLite database under `data/` and any Excel workbook you point
the Excel tab at are **not** synced between devices by this - only the
app's code/config is. Each device keeps its own local data unless you
manually copy `data/lpse_monitor.db` over yourself.

## What data is being retrieved

See the big comments at the top of `scraper/lpse_scraper.py` and
`scraper/lpse_homepage_scraper.py` for exactly how each was reverse
engineered and what every field means. Short version: `/lelang` is
scraped via the site's own internal JSON API (a real `requests` session +
one POST, no browser automation), and the homepage is scraped via a plain
anonymous HTTP GET + HTML parsing (no session needed at all).

## Limitations (honest, so nothing surprises you later)

- **HPS in the full list is abbreviated, not exact** ("15,9 M" rather than
  a precise Rupiah figure). The homepage's HPS values ARE exact.
- **Pagu Anggaran isn't exposed by either page** - only HPS and (once
  awarded) Nilai Kontrak. Getting Pagu Anggaran would need an extra
  request per package to its own detail page - not done yet.
- **Ordering is a best-effort proxy, not a confirmed upload timestamp.**
  Neither page exposes an explicit "uploaded at" field, so lists are
  sorted earliest-to-latest by Package ID (assumed to increase over time).
  This held true in every sample checked so far, but hasn't been
  independently confirmed against LKPP documentation.
- **No scheduling/notifications yet** - you run the app manually, twice a
  day, as planned for v1.
- **Keyword matching is plain substring matching** - see the notes at the
  top of `services/keyword_service.py` for the accepted trade-offs.
- The homepage scraper assumes each category's badge count equals the
  number of rows shown (i.e. nothing is silently truncated) - only
  verified against categories with a handful of packages so far.
- **Excel export always exports the full relevant-package list** for
  whichever dataset you export, not whatever the dashboard's filter is
  currently narrowed to.
- **Excel Table formatting needs a fully-filled header row.** If any
  header cell above your start cell is blank, the export still writes the
  data (as plain values) but skips turning it into a formatted Table for
  that run - use "Buat File Baru" for a file that's guaranteed to qualify.
- **In-project Excel file auto-discovery only looks inside this project's
  own folder** (not your whole computer) - drop your workbook in here (or
  a subfolder) and it'll show up as a one-click button in the Excel tab.
- **`LPSE_Monitor.exe` (via `build_exe.bat`) is unverified** - it was
  written following the standard way to package a Streamlit app with
  PyInstaller, but has not been built/tested on a real Windows machine.
- **The Kalla Aspal color theme hasn't been visually checked** in a real
  browser by the assistant (no Streamlit runtime available in its own
  sandbox) - the colors/layout should look right, but a first look is
  worth doing.

## Project structure

```
kalla-aspal/
    app.py                          Streamlit UI (6 tabs)
    launcher.py                     Entry point used only by the .exe build
    lpse_monitor.spec               PyInstaller build spec
    requirements.txt
    PROJECT_STATUS.md                Detailed status log - read this first
    run_app.bat                       One-click launcher (no CMD typing)
    build_exe.bat                     Builds LPSE_Monitor.exe (unverified - see limitations)
    push_to_github.bat                One-click add+commit+push
    .streamlit/config.toml            Base color theme (Kalla Aspal green/gold)
    data/                             SQLite database lives here (gitignored)
    backups/                           Auto-created Excel backups (gitignored)
    scraper/
        lpse_scraper.py               Full /lelang list - session + JSON API
        lpse_homepage_scraper.py      Homepage summary - plain HTML, no session
    database/
        models.py                     SQL schema (10 tables)
        database.py                   Connection + queries + schema migrations
    services/
        keyword_service.py            Keyword matching (shared by both scrapers)
        comparison_service.py         New/existing/updated - /lelang dataset
        homepage_service.py           New/existing/updated - homepage dataset
        filter_service.py             Dashboard filter/sort/HPS-sum helpers
        calendar_service.py           Akhir Pendaftaran calendar helpers
        excel_service.py              Excel export (Phase 6) - two datasets, Excel Tables, file discovery
        status_flags.py               Detects "gagal"/"batal"/"diulang"/etc. inside a package's name
        activity_service.py           Merges both datasets' change history for the Dashboard tab
    ui/
        branding.py                    Header banner + road-strip HTML, reads style.css for all CSS
        style.css                      All colors/CSS in one plain file - edit this to change the look
    config/
        default_keywords.py           Seed keyword list (first run only)
    tests/                            70 offline unit tests (see below)
```

## Running the tests

```
pip install -r requirements.txt
pytest
```

(Written and verified offline against real sample data captured from the
live site, and synthetic `.xlsx` files for the Excel tests, so none of
them need network access to run.)
