@echo off
REM ============================================================
REM  Builds LPSE_Monitor.exe (a standalone Windows program) from
REM  this project, using PyInstaller. Run this ONCE whenever you
REM  want a fresh .exe after making changes - not needed for
REM  everyday use (use run_app.bat for that).
REM
REM  IMPORTANT / HONEST NOTE: this script was written and reviewed
REM  by an assistant that could not actually run it (no Windows
REM  machine available to it). It follows the standard, documented
REM  way to package a Streamlit app with PyInstaller, but if
REM  something goes wrong, copy the FULL error text and share it -
REM  don't assume the .exe approach has failed for good; these
REM  builds are usually fixable with one extra PyInstaller option.
REM ============================================================
cd /d "%~dp0"

if not exist venv (
    echo Jalankan run_app.bat terlebih dahulu minimal sekali sebelum ini.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
pip install --quiet pyinstaller

echo.
echo Membangun LPSE_Monitor.exe ... ini bisa memakan waktu beberapa menit.
pyinstaller --noconfirm lpse_monitor.spec

if errorlevel 1 (
    echo.
    echo GAGAL membangun .exe. Salin teks error lengkap di atas dan tanyakan
    echo untuk bantuan - biasanya ini bisa diperbaiki.
    pause
    exit /b 1
)

echo.
echo SELESAI. File aplikasi ada di: dist\LPSE_Monitor\LPSE_Monitor.exe
echo Salin SELURUH folder "dist\LPSE_Monitor" jika ingin memindahkannya -
echo bukan hanya file .exe-nya saja.
pause
