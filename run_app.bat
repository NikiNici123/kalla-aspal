@echo off
REM ============================================================
REM  LPSE Monitor - one-click launcher (no need to type anything
REM  into a terminal). Double-click this file to run the app.
REM ============================================================
cd /d "%~dp0"

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
