"""
Default keyword seed list, used only the very first time the database is
created (see database/database.py init_db). After that, keywords live in
the SQLite `keywords` table and are managed through the Kata Kunci tab in
the app - this file is not read again.

Keeping the seed list here (instead of hardcoding it inside the database
init code) makes it easy to see/tweak the starting keyword set before
first run.
"""

DEFAULT_KEYWORDS = [
    "jalan",
    "jl.",
    "jl",
    "jalan raya",
    "peningkatan jalan",
    "pembangunan jalan",
    "rehabilitasi jalan",
    "preservasi jalan",
    "pemeliharaan jalan",
    "rekonstruksi jalan",
    "ruas jalan",
    "infrastruktur jalan",
]
