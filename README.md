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

1. Go to the **Wilayah LPSE** tab and add every LPSE region you want to
   monitor (name + region identifier, e.g. `singkawangkota` or
   `kalbarprov`). This only needs doing once per region - it's remembered.
2. Go to **Cek Tender (Daftar Lengkap)** and click **CEK TENDER** - this
   checks the full tender list (every status) for all active regions.
3. Go to **Ringkasan Beranda** and click **CEK RINGKASAN BERANDA** - this
   checks each region's homepage summary, which additionally carries a
   registration deadline ("Akhir Pendaftaran").
4. Either check will tell you **X PAKET BARU DITEMUKAN** (or "tidak ada
   paket baru") and list what's new/changed. Both keep a running,
   earliest-first table of everything relevant found so far.
5. Run it again in the morning and at night, per your normal workflow -
   the database remembers everything between runs.

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
- **No keyword management screen yet** - the default keyword list is
  seeded on first run and used automatically, but editing it today means
  editing `config/default_keywords.py` before that first run, or directly
  in the `keywords` SQLite table.
- **No Excel export, no scheduling/notifications yet** - both are later
  phases; you run the app manually, twice a day, as planned for v1.
- **Keyword matching is plain substring matching** - see the notes at the
  top of `services/keyword_service.py` for the accepted trade-offs.
- The homepage scraper assumes each category's badge count equals the
  number of rows shown (i.e. nothing is silently truncated) - only
  verified against categories with a handful of packages so far.

## Project structure

```
kalla-aspal/
    app.py                          Streamlit UI
    requirements.txt
    PROJECT_STATUS.md                Detailed status log - read this first
    push_to_github.bat                One-click add+commit+push
    data/                             SQLite database lives here (gitignored)
    scraper/
        lpse_scraper.py               Full /lelang list - session + JSON API
        lpse_homepage_scraper.py      Homepage summary - plain HTML, no session
    database/
        models.py                     SQL schema (7 tables)
        database.py                   Connection + queries
    services/
        keyword_service.py            Keyword matching (shared by both scrapers)
        comparison_service.py         New/existing/updated - /lelang dataset
        homepage_service.py           New/existing/updated - homepage dataset
    config/
        default_keywords.py           Seed keyword list (first run only)
    tests/                            28 offline unit tests (see below)
```

## Running the tests

```
pip install -r requirements.txt
pytest
```

(Written and verified offline against real sample data captured from the
live site, so they don't need network access to run.)
