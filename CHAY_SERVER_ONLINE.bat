@echo off
title GradeFlow Server
color 0A
cls
echo ===================================================================
echo               KHOI DONG HE THONG MAY CHU GRADEFLOW
echo ===================================================================
echo.

cd /d "d:\chamtrac nghien v2"

echo [1/2] Dang khoi dong Django Backend tren cong 8000...
start "GradeFlow Django" cmd /c "cd /d "d:\chamtrac nghien v2" && python manage.py runserver 0.0.0.0:8000"
timeout /t 3 /nobreak > nul

echo.
echo ===================================================================
echo                    DIA CHI KET NOI CHO APP
echo ===================================================================
echo.
echo [CACH 1 - DUNG CUNG MANG WI-FI] (Khuyen dung - Cuc nhanh va on dinh):
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
    for /f "tokens=1" %%b in ("%%a") do (
        echo     =^>  http://%%b:8000
    )
)
echo.
echo [CACH 2 - DUNG KHI DIEN THOAI BAT 4G / KHAC MANG]:
echo Dang khoi tao link internet...
echo.
npx -y localtunnel --port 8000
pause
