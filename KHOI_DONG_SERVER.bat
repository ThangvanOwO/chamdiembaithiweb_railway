@echo off
title GradeFlow Server (Direct Window)
color 0A
cls
echo ===================================================================
echo               KHOI DONG HE THONG MAY CHU GRADEFLOW
echo ===================================================================
echo.

cd /d "%~dp0"

echo [1/2] Dang giai phong cong 8000 neu dang bi chiem...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do taskkill /f /pid %%a 2>nul

echo.
echo ===================================================================
echo               CAC LINK KET NOI (COPY VA DAN VAO BROWSER/APP)
echo ===================================================================
echo.
echo  [CHAY TREN MAY TINH - KHONG LO FIREWALL]:
echo      =^> http://127.0.0.1:8000
echo      =^> http://localhost:8000
echo.
echo  [CHAY TREN DIEN THOAI - CUNG MANG WI-FI]:
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
    for /f "tokens=1" %%b in ("%%a") do (
        echo      =^> http://%%b:8000
    )
)
echo.
echo ===================================================================
echo  [HUONG DAN]: TAT BANG NAY (CMD) LA MAY CHU SE TU DONG TAT THEO!
echo ===================================================================
echo.

python manage.py runserver 0.0.0.0:8000
