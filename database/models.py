"""
SQLite schema for LPSE Monitor.

Kept as plain SQL (rather than an ORM) to stay dependency-light for v1,
per the "avoid unnecessary complexity" rule in the project brief. If the
app grows, this is the natural place to introduce SQLAlchemy models later
without changing how the rest of the app calls into database.py.

Tables:
    regions            - LPSE regions the user monitors (add/edit/activate in the app)
    keywords           - road-related keyword list (Phase 5 manages these)
    packages           - latest known state of every /lelang package we've ever seen
    package_snapshots  - history of changes to a package over time
    scrape_runs        - a log entry for every time "Cek Tender" (full list) was run
    homepage_packages  - latest known state of every homepage-summary package seen
                         (kept DELIBERATELY SEPARATE from `packages` - see
                         scraper/lpse_homepage_scraper.py docstring for why)
    homepage_scrape_runs - a log entry for every homepage-summary check run
    excel_config       - current Excel export settings, one row per dataset
                         ('lelang' / 'beranda')
    excel_generated_rows - which (file, sheet, row) triples this app wrote,
                         so exports never touch rows/data the user entered
                         by hand - see services/excel_service.py
"""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS regions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    region_name         TEXT NOT NULL,
    region_identifier   TEXT NOT NULL UNIQUE,
    base_url            TEXT NOT NULL,
    is_active           INTEGER NOT NULL DEFAULT 1,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS keywords (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword     TEXT NOT NULL UNIQUE,
    is_enabled  INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- One row per distinct package we've ever seen, holding its LATEST known
-- state. `package_id` is the site's own "Kode Lelang" and is the primary
-- way we recognize the same package across scrapes. When a package has no
-- package_id (shouldn't normally happen, but the site's format could
-- change), we fall back to a computed `fingerprint` instead - see
-- scraper/lpse_scraper.py:make_fallback_fingerprint for exactly how that's
-- built. Exactly one of package_id / fingerprint should be non-null.
CREATE TABLE IF NOT EXISTS packages (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    package_id              TEXT UNIQUE,
    fingerprint             TEXT UNIQUE,
    region_identifier       TEXT NOT NULL,
    nama_paket              TEXT NOT NULL,
    nama_paket_raw          TEXT,
    badges                  TEXT,      -- JSON list, e.g. ["Tender Ulang"]
    instansi                TEXT,
    tahapan                 TEXT,
    metode_kualifikasi      TEXT,
    jenis                   TEXT,
    metode_evaluasi         TEXT,
    jenis_pengadaan         TEXT,
    tahun_anggaran          TEXT,
    hps_text                TEXT,
    hps_value               REAL,
    nilai_kontrak_text      TEXT,
    nilai_kontrak_value     REAL,
    evaluasi_ulang          INTEGER NOT NULL DEFAULT 0,
    penawaran_ulang         INTEGER NOT NULL DEFAULT 0,
    konsolidasi             INTEGER NOT NULL DEFAULT 0,
    oap_only                INTEGER NOT NULL DEFAULT 0,
    package_url             TEXT,
    is_relevant             INTEGER NOT NULL DEFAULT 0,
    matched_keywords        TEXT,      -- JSON list
    first_seen_at           TEXT NOT NULL,
    last_seen_at            TEXT NOT NULL,
    last_updated_at         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_packages_region ON packages(region_identifier);
CREATE INDEX IF NOT EXISTS idx_packages_relevant ON packages(is_relevant);

-- One row every time a package's tracked fields change (status, HPS,
-- contract value, ...). This is what powers the "Package Change History"
-- shown on the package detail page.
CREATE TABLE IF NOT EXISTS package_snapshots (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    package_key             TEXT NOT NULL,  -- package_id or fingerprint
    scrape_run_id           INTEGER,
    tahapan                 TEXT,
    hps_value               REAL,
    nilai_kontrak_value     REAL,
    change_summary          TEXT,      -- human-readable, e.g. "Tahapan changed: Tender -> Evaluasi"
    snapshot_json           TEXT NOT NULL,
    created_at              TEXT NOT NULL,
    FOREIGN KEY (scrape_run_id) REFERENCES scrape_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_package_key ON package_snapshots(package_key);

-- One row per "Cek Tender" click / scheduled run.
CREATE TABLE IF NOT EXISTS scrape_runs (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at                  TEXT NOT NULL,
    finished_at                  TEXT,
    regions_scraped             TEXT,   -- JSON list of region identifiers
    total_packages_found        INTEGER DEFAULT 0,
    relevant_packages_found     INTEGER DEFAULT 0,
    new_packages_found          INTEGER DEFAULT 0,
    updated_packages_found      INTEGER DEFAULT 0,
    status                      TEXT NOT NULL DEFAULT 'running', -- running | completed | failed
    error_message               TEXT
);

-- Homepage ("Beranda") summary packages - see scraper/lpse_homepage_scraper.py.
-- These come from https://spse.inaproc.id/{region}/ rather than /lelang, and
-- carry an "Akhir Pendaftaran" (registration deadline) that the main
-- `packages` table doesn't have. Kept as its own table on purpose so the two
-- datasets never get mixed together in the UI.
CREATE TABLE IF NOT EXISTS homepage_packages (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    package_id              TEXT UNIQUE,
    fingerprint             TEXT UNIQUE,
    region_identifier       TEXT NOT NULL,
    section                 TEXT NOT NULL,  -- "Tender" or "Non Tender"
    kategori                TEXT,            -- e.g. "Pekerjaan Konstruksi"
    nama_paket              TEXT NOT NULL,
    badges                  TEXT,            -- JSON list, e.g. ["spse 4.5", "Tender"]
    hps_text                TEXT,
    hps_value               REAL,
    akhir_pendaftaran_text  TEXT,
    akhir_pendaftaran_at    TEXT,            -- parsed ISO datetime, if parseable
    display_position        INTEGER,         -- the site's own "No" column (reference only)
    package_url             TEXT,
    is_relevant             INTEGER NOT NULL DEFAULT 0,
    matched_keywords        TEXT,            -- JSON list
    first_seen_at           TEXT NOT NULL,
    last_seen_at            TEXT NOT NULL,
    last_updated_at         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_homepage_packages_region ON homepage_packages(region_identifier);
CREATE INDEX IF NOT EXISTS idx_homepage_packages_relevant ON homepage_packages(is_relevant);

-- One row per "Cek Ringkasan Beranda" run (separate log from scrape_runs,
-- same reasoning as homepage_packages above).
CREATE TABLE IF NOT EXISTS homepage_scrape_runs (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at                  TEXT NOT NULL,
    finished_at                 TEXT,
    regions_scraped             TEXT,   -- JSON list of region identifiers
    total_packages_found        INTEGER DEFAULT 0,
    relevant_packages_found     INTEGER DEFAULT 0,
    new_packages_found          INTEGER DEFAULT 0,
    updated_packages_found      INTEGER DEFAULT 0,
    status                      TEXT NOT NULL DEFAULT 'running',
    error_message               TEXT
);

-- Excel export settings - ONE row per dataset ('lelang' = Daftar Lengkap,
-- 'beranda' = Ringkasan Beranda), since Nikol asked for the two datasets
-- to export separately rather than sharing one config. Kept in the
-- database (not a config file) so it survives app restarts and is easy to
-- change from the UI. See services/excel_service.py for how this is used.
--
-- NOTE: this replaced an earlier single-row (id=1) shape. Existing
-- databases are migrated automatically the first time this version of the
-- app runs - see database.py's _migrate_excel_config_table().
CREATE TABLE IF NOT EXISTS excel_config (
    dataset             TEXT PRIMARY KEY CHECK (dataset IN ('lelang', 'beranda')),
    file_path           TEXT,
    sheet_name          TEXT NOT NULL,
    start_cell          TEXT NOT NULL DEFAULT 'A5',
    enabled_columns     TEXT,      -- JSON list of column field-keys, in order
    mode                TEXT NOT NULL DEFAULT 'replace',  -- 'replace' | 'append_new'
    use_excel_table     INTEGER NOT NULL DEFAULT 1,  -- write/update a native Excel Table, not just plain cells
    updated_at          TEXT NOT NULL
);

-- Tracks exactly which (file, sheet, row) triples were written by THIS
-- app, so a "replace" export only ever clears rows we ourselves wrote
-- (never a row the user entered by hand), and an "append new only" export
-- knows which packages already have a row so it doesn't duplicate them.
CREATE TABLE IF NOT EXISTS excel_generated_rows (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path       TEXT NOT NULL,
    sheet_name      TEXT NOT NULL,
    package_key     TEXT NOT NULL,  -- package_id or fingerprint, from `packages`
    row_number      INTEGER NOT NULL,
    written_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_excel_rows_file_sheet
    ON excel_generated_rows(file_path, sheet_name);
"""
