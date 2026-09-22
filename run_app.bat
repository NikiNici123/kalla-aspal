@echo off
setlocal enabledelayedexpansion
REM ============================================================
REM  LPSE Monitor - one-click launcher (no need to type anything
REM  into a terminal). Double-click this file to run the app.
REM
REM  Also auto-installs Python and Git the FIRST time, IF you've
REM  placed their installer files in this same folder:
REM    - Python:  a file named like  python-3.xx.x-amd64.exe
REM    - Git:     a file named like  Git-2.xx.x-64-bit.exe
REM  (exact version number in the filename doesn't matter - this
REM  script just looks for anything starting with "python-" or
REM  "Git-"). Git isn't required to run the app itself - it's only
REM  used by push_to_github.bat - but it's installed here too if
REM  the installer is present, so everything is ready in one step.
REM  Don't have the installers? Skip them - see NOTE below.
REM ============================================================
cd /d "%~dp0"

set "NEED_NEW_WINDOW=0"

REM ---------- Python (required to run the app) ----------
where python >nul 2>&1
if errorlevel 1 (
    echo Python tidak ditemukan di komputer ini.
    set "PY_INSTALLER="
    for %%f in (python-*.exe) do if not defined PY_INSTALLER set "PY_INSTALLER=%%f"
    if defined PY_INSTALLER (
        echo Menginstall Python otomatis dari "!PY_INSTALLER!" ...
        echo ^(mohon tunggu 1-2 menit, jangan tutup jendela ini^)
        start /wait "" "!PY_INSTALLER!" /quiet InstallAllUsers=0 PrependPath=1
        echo Python selesai diinstall.
        set "NEED_NEW_WINDOW=1"
    ) else (
        echo.
        echo GAGAL: Python tidak ditemukan, dan tidak ada file installer Python
        echo ^(nama file diawali "python-", contoh: python-3.12.6-amd64.exe^) di
        echo folder ini. Download dari https://www.python.org/downloads/, taruh
        echo file installernya di folder ini ^(sejajar dengan run_app.bat^), lalu
        echo jalankan run_app.bat lagi. Atau install manual dan centang
        echo "Add python.exe to PATH" saat instalasi.
        pause
        exit /b 1
    )
)

REM ---------- Git (optional - only needed for push_to_github.bat) ----------
where git >nul 2>&1
if errorlevel 1 (
    set "GIT_INSTALLER="
    for %%f in (Git-*.exe) do if not defined GIT_INSTALLER set "GIT_INSTALLER=%%f"
    if defined GIT_INSTALLER (
        echo Menginstall Git otomatis dari "!GIT_INSTALLER!" ...
        start /wait "" "!GIT_INSTALLER!" /VERYSILENT /NORESTART /SP- /SUPPRESSMSGBOXES
        echo Git selesai diinstall.
        set "NEED_NEW_WINDOW=1"
    )
    REM No installer found and no git - that's fine, git is only needed
    REM for push_to_github.bat, not for running the app. Skip silently.
)

if "!NEED_NEW_WINDOW!"=="1" (
    echo.
    echo ============================================================
    echo  Instalasi awal selesai. Tutup jendela ini, lalu double-klik
    echo  run_app.bat SEKALI LAGI untuk membuka aplikasinya.
    echo  ^(Ini cuma perlu sekali - Windows baru "melihat" program yang
    echo  baru diinstall setelah jendela CMD-nya dibuka ulang.^)
    echo ============================================================
    pause
    exit /b 0
)

REM The app's own code (app.py, venv, requirements.txt, ...) lives in
REM src\, one folder deeper than this launcher - everything below this
REM point runs from there, so the app only has to be launched from a
REM single double-click at the top level.
cd /d "%~dp0src"

if not exist venv (
    echo Menyiapkan aplikasi untuk pertama kali, mohon tunggu ^(1-3 menit^)...
    python -m venv venv
    if errorlevel 1 (
        echo.
        echo GAGAL: Python tidak ditemukan. Install Python 3.11+ dari python.org
        echo dan centang "Add python.exe to PATH" saat instalasi, lalu coba lagi.
        pause
        exit /b 1
    )
)

call venv\Scripts\activate.bat

REM Always (re)install requirements, not just on first setup - this makes
REM sure that if requirements.txt gains a new package later (e.g. openpyxl
REM for the Excel feature), an already-existing venv from before still
REM picks it up automatically instead of erroring with "No module named
REM ...". pip skips anything already installed at the right version, so
REM this stays fast on every normal run.
echo Memeriksa dependensi...
pip install --quiet -r requirements.txt

echo Menjalankan LPSE Monitor... browser akan terbuka otomatis.
streamlit run app.py

pause
