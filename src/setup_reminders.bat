@echo off
setlocal enabledelayedexpansion
REM ============================================================
REM  Turns on automatic deadline reminders. Run this ONCE - and
REM  again any time you edit config\reminder_times.txt.
REM
REM  What it does: installs the notification library into the
REM  existing venv, then registers one Windows Task Scheduler
REM  entry per time listed in config\reminder_times.txt (default:
REM  08:00, 13:00, 16:00). From then on, if a saved relevant
REM  package's Akhir Pendaftaran is coming up soon, you get a
REM  normal Windows notification automatically at each of those
REM  times - even on a day you never open the app. Click a
REM  notification (or its "Sudah Saya Cek" button) and the rest of
REM  that day's checks stay quiet - see README.md for details.
REM  No email, no account, nothing leaves this PC.
REM
REM  Requirement: the PC has to be ON (not asleep/shut down) at a
REM  scheduled time for that check to fire - if it's off, that
REM  one's simply skipped until the next time on the list.
REM
REM  Safe to run again any time - it clears out any reminder
REM  schedule this script registered before and re-creates it from
REM  the current config\reminder_times.txt and current folder
REM  location, so it stays correct after editing the file or
REM  moving the project.
REM ============================================================
cd /d "%~dp0"

if not exist venv (
    echo Jalankan run_app.bat terlebih dahulu minimal sekali sebelum ini.
    pause
    exit /b 1
)

if not exist config\reminder_times.txt (
    echo GAGAL: config\reminder_times.txt tidak ditemukan.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
echo Menginstall pustaka notifikasi...
pip install --quiet win11toast

echo.
echo Menghapus jadwal reminder lama ^(kalau ada^)...
REM schtasks doesn't support a wildcard task name for /delete (only an
REM exact name, or "*" for literally every task on the machine) - so we
REM list every task, keep only the ones whose name contains ours, and
REM delete those one at a time by their exact reported name instead.
for /f "usebackq tokens=1 delims=," %%A in (`schtasks /query /fo csv /nh 2^>nul`) do (
    set "TN=%%~A"
    set "STRIPPED=!TN:Kalla Aspal - Reminder Deadline=!"
    if not "!STRIPPED!"=="!TN!" schtasks /delete /tn "!TN!" /f >nul 2>&1
)

echo Membaca config\reminder_times.txt dan mendaftarkan jadwal baru...
set "ANY_REGISTERED=0"
for /f "usebackq eol=# tokens=* delims= " %%T in ("config\reminder_times.txt") do (
    if not "%%T"=="" (
        set "RAW=%%T"
        set "SAFE=!RAW::=!"
        echo   - !RAW!
        schtasks /create /tn "Kalla Aspal - Reminder Deadline !SAFE!" /tr "\"%~dp0venv\Scripts\pythonw.exe\" \"%~dp0check_reminders.py\"" /sc daily /st !RAW! /f >nul
        if not errorlevel 1 set "ANY_REGISTERED=1"
    )
)

if "!ANY_REGISTERED!"=="0" (
    echo.
    echo GAGAL mendaftarkan jadwal apa pun. Cek isi config\reminder_times.txt
    echo ^(format: satu jam per baris, contoh "08:00"^), atau salin teks error
    echo di atas dan tanyakan untuk bantuan.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  SELESAI. Mulai jadwal berikutnya, Windows akan otomatis
echo  memberi notifikasi kalau ada paket relevan yang Akhir
echo  Pendaftarannya mendekat ^(dalam 3 hari - ubah di
echo  check_reminders.py kalau mau angka lain^).
echo.
echo  Mau coba sekarang juga, tanpa menunggu jadwal? Ketik:
echo    venv\Scripts\python check_reminders.py
echo  ^(tidak akan muncul apa-apa kalau kebetulan tidak ada deadline
echo  yang jatuh dalam 3 hari ke depan saat ini - itu normal^)
echo.
echo  Mau ubah jam-jamnya? Edit config\reminder_times.txt ^(satu jam
echo  per baris^), lalu jalankan setup_reminders.bat ini lagi.
echo.
echo  Mau lihat/matikan langsung dari Windows? Buka "Task Scheduler"
echo  dari Start Menu, cari task yang namanya diawali
echo  "Kalla Aspal - Reminder Deadline".
echo ============================================================
pause
