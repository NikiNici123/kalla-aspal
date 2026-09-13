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
"""
