@echo off
REM ============================================================
REM  One-click "save my changes to GitHub" - stages, commits, and
REM  pushes everything in this folder in one go. No need to type
REM  any git commands.
REM
REM  Needs Git for Windows installed (run_app.bat installs it
REM  automatically if you put its installer file in this folder -
REM  see the note at the top of run_app.bat).
REM ============================================================
cd /d "%~dp0"

where git >nul 2>&1
if errorlevel 1 (
    echo.
    echo GAGAL: Git tidak ditemukan di komputer ini. Jalankan run_app.bat
    echo terlebih dahulu ^(itu akan menginstall Git otomatis kalau ada file
    echo installernya di folder ini^), atau install Git for Windows manual
    echo dari https://git-scm.com/download/win
    pause
    exit /b 1
)

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
    echo.
    echo GAGAL: Folder ini belum terhubung ke repository GitHub manapun.
    echo Clone dulu repository-nya lewat GitHub Desktop, baru pakai file ini.
    pause
    exit /b 1
)

git add -A

set "COMMIT_MSG="
set /p COMMIT_MSG="Pesan singkat untuk perubahan ini (boleh dikosongkan, tekan Enter saja): "
if "%COMMIT_MSG%"=="" set "COMMIT_MSG=Update"

git commit -m "%COMMIT_MSG%"
if errorlevel 1 (
    echo.
    echo Tidak ada perubahan untuk di-commit ^(atau commit gagal^). Selesai.
    pause
    exit /b 0
)

echo.
echo Mengirim perubahan ke GitHub...
git push

if errorlevel 1 (
    echo.
    echo GAGAL push. Kemungkinan perlu login/autentikasi GitHub dulu - coba
    echo buka GitHub Desktop sekali untuk memastikan sudah login, lalu coba
    echo lagi di sini. Perubahan kamu tetap aman ^(sudah ter-commit secara
    echo lokal^), tinggal push-nya saja yang perlu diulang.
    pause
    exit /b 1
)

echo.
echo SELESAI - perubahan sudah tersimpan di GitHub.
pause
