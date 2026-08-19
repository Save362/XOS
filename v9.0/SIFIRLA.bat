@echo off
setlocal
title X OS v9.0 Sifirlama
color 0B

cd /d "%~dp0"

echo.
echo ==============================
echo       X OS v9.0 RESET
echo ==============================
echo.

if not exist "xos_gui_admin_v7_v9.py" (
    echo HATA: v9.0 yedek dosyasi bulunamadi!
    echo.
    echo Olmasi gereken:
    echo %~dp0xos_gui_admin_v7_v9.py
    echo.
    pause
    exit /b 1
)

echo X OS kapatiliyor...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$p=Get-CimInstance Win32_Process | Where-Object {$_.CommandLine -like '*xos_gui_admin_v7.py*'}; if($p){$p | ForEach-Object {Stop-Process -Id $_.ProcessId -Force}}"

timeout /t 2 /nobreak >nul

echo v9.0 dosyasi geri yukleniyor...
echo.

copy /Y "xos_gui_admin_v7_v9.py" "xos_gui_admin_v7.py"

if errorlevel 1 (
    echo.
    echo ==============================
    echo       HATA
    echo ==============================
    echo.
    echo Dosya hala degistirilemiyor.
    echo.
    echo BAT dosyasini YONETICI olarak
    echo calistirmayi dene.
    echo.
    pause
    exit /b 1
)

echo.
echo ==============================
echo       TAMAMLANDI
echo ==============================
echo.
echo X OS v9.0'a geri dondu!
echo.

timeout /t 2 /nobreak >nul

start "" python "xos_gui_admin_v7.py"

exit