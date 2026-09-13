# PyInstaller spec for LPSE Monitor.
#
# Bundles the app + a copy of app.py, database/, scraper/, services/,
# config/ (as data, since launcher.py resolves app.py's path at runtime),
# plus Streamlit's own metadata/static files, which PyInstaller does not
# pick up automatically. Build with build_exe.bat (which just runs
# `pyinstaller lpse_monitor.spec`) - NOT with a plain `pyinstaller
# launcher.py`, because these extra data files are required for Streamlit
# to run at all inside the bundle.
#
# NOTE: this spec was written by an assistant that cannot run Windows or
# PyInstaller itself (see PROJECT_STATUS.md). It follows the standard,
# documented pattern for bundling Streamlit apps, but has NOT been test-
# built - if it errors, see the troubleshooting notes in build_exe.bat.

import importlib.util
from pathlib import Path

block_cipher = None

streamlit_spec = importlib.util.find_spec("streamlit")
streamlit_path = Path(streamlit_spec.submodule_search_locations[0])

datas = [
    (str(streamlit_path / "static"), "streamlit/static"),
    (str(streamlit_path / "runtime"), "streamlit/runtime"),
    ("app.py", "."),
    ("database", "database"),
    ("scraper", "scraper"),
    ("services", "services"),
    ("config", "config"),
]

a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "streamlit",
        "openpyxl",
        "bs4",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="LPSE_Monitor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
