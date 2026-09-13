# Kalla Aspal - LPSE Monitor

A local-first tool for admin staff to keep an eye on LPSE/SPSE government
procurement tenders (`https://spse.inaproc.id/{region}/lelang`) and get
told when a new road-construction package shows up.

Runs entirely on your own Windows PC. No cloud database, no login, no
internet-facing deployment - everything (settings, keyword list, every
tender ever seen) lives in one local SQLite file under `data/`.

**Current status: Phase 1 + Phase 2 of the development plan** (see
"Development phases" below) - the scraper, keyword filtering, local
database, and new/updated/existing detection all work end-to-end through
a minimal Streamlit screen. Region management, keyword management, Excel
export, scheduling and the fuller multi-page UI come in later phases.

## Installation (Windows)

1. Install Python 3.11+ from [python.org](https://www.python.org/downloads/)
   (tick "Add python.exe to PATH" during setup).
2. Open a terminal in this folder and create a virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Run the app:
   ```
   streamlit run app.py
   ```
   Your browser will open automatically at `http://localhost:8501`.

The first run creates `data/lpse_monitor.db` automatically (with the
default road-related keyword list already seeded in).

## How to use it

1. Enter one or more LPSE region identifiers (the part of the URL right
   after `spse.inaproc.id/`, e.g. `singkawangkota`). Separate multiple
   regions with commas.
2. Click **CEK TENDER**.
3. The app fetches the current tender list for each region, keeps only
   packages whose name matches one of your road-related keywords, and
   compares them against everything it has seen before. You'll see:
   - **X PAKET BARU DITEMUKAN** (X new packages found) - packages never
     seen before.
   - Packages whose status/HPS/contract value changed since last time.
   - A running table of every relevant package known so far.
4. Run it again in the morning and at night, per your normal workflow -
   the database remembers everything between runs.

## What data is being retrieved

The site loads its tender table via an internal JSON API
(`POST /{region}/dt/lelang?tahun={year}`) rather than plain HTML - see the
big comment at the top of `scraper/lpse_scraper.py` for exactly how that
was found and what each field means. For every relevant package we store:
package ID (Kode Lelang), package name, institution, current stage/status,
abbreviated HPS, procurement type/method, contract value (once awarded),
several status flags (tender ulang, konsolidasi, etc.), and the package's
own LPSE URL.

## Limitations (honest, so nothing surprises you later)

- **HPS is abbreviated, not exact.** The list API only gives values like
  "15,9 M" or "414,4 Jt", not the precise Rupiah figure. Pagu Anggaran and
  exact announcement dates aren't in this API at all - the site only shows
  those on each package's own detail page, which would mean one extra
  request per package. Left out of v1 to keep things fast; a good Phase 3+
  candidate if you need exact figures often.
- **No Excel export yet** (Phase 6) - for now, results live in the app and
  the SQLite database only.
- **No region/keyword management screens yet** (Phases 4-5) - regions and
  keywords already live in the database and get used automatically
  (whatever region you type gets remembered; the default keyword list is
  seeded on first run), but there's no UI to add/edit/disable them yet
  beyond editing `config/default_keywords.py` before the very first run.
- **No scheduling/notifications yet** (later phase) - you run it manually,
  twice a day, as planned for v1.
- **Keyword matching is plain substring matching.** "jalan" matches inside
  "Jalan", "JALAN", "jalanan", etc. This is deliberate for v1 but can
  produce occasional false positives - see the notes at the top of
  `services/keyword_service.py`.
- Tested against `singkawangkota` (real data, live site) during
  development. If a region shows an error, double check the identifier
  matches the one in that region's LPSE URL exactly.

## Project structure

```
kalla-aspal/
    app.py                     Streamlit UI (Phase 1+2 prototype)
    requirements.txt
    data/                      SQLite database lives here (gitignored)
    scraper/
        lpse_scraper.py        All HTTP + parsing logic, UI-agnostic
    database/
        models.py              SQL schema
        database.py            Connection + queries
    services/
        keyword_service.py     Keyword matching (Phase 1)
        comparison_service.py  New/existing/updated detection (Phase 2)
    config/
        default_keywords.py    Seed keyword list (first run only)
    tests/
        test_scraper_parsing.py
        test_keyword_service.py
        test_comparison_service.py
```

## Running the tests

```
pip install -r requirements.txt
pytest
```

(These were written and verified offline against real sample data captured
from the live site, so they don't need network access to run.)

## Development phases

1. ✅ Basic LPSE scraper - region input, scrape, filter by keyword.
2. ✅ SQLite database - save packages, detect duplicates/new packages.
3. ◻ Dashboard polish (a basic one already exists inside `app.py`).
4. ◻ Region management (add/edit/delete/activate - table already exists).
5. ◻ Keyword management (add/edit/delete/enable - table already exists).
6. ◻ Excel integration (import/update one reused workbook, with backups).
7. ◻ Scrape history page, package change-history page, better error UI.
