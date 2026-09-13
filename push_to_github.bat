@echo off
cd /d "%~dp0"

echo ===================================
echo   Kalla Aspal - Push ke GitHub
echo ===================================
echo.

git add -A

set msg=
set /p msg="Tulis pesan singkat tentang perubahan ini (atau langsung tekan Enter): "
if "%msg%"=="" set msg=Update otomatis

git commit -m "%msg%"
echo.
echo Mengirim ke GitHub...
git push

echo.
echo ===================================
echo Selesai. Jika ada tulisan merah "error" di atas, screenshot dan
echo tunjukkan ke Claude untuk dibantu.
echo ===================================
pause
