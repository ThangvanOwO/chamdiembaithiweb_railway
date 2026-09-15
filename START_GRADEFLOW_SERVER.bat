@echo off
setlocal EnableExtensions

title GradeFlow - Local Server
color 0A
cls

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

echo ================================================================
echo                 GRADEFLOW LOCAL SERVER
echo ================================================================
echo.
echo Thu muc du an: %PROJECT_DIR%

rem Uu tien Python trong virtual environment cua du an.
set "PYTHON_EXE=%PROJECT_DIR%.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=%PROJECT_DIR%venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

"%PYTHON_EXE%" --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [LOI] Khong tim thay Python.
    echo Hay cai Python 3.10+ hoac tao .venv/venv trong thu muc du an.
    pause
    exit /b 1
)

echo Python dang dung:
"%PYTHON_EXE%" --version
echo.
echo Dang kiem tra Django...
"%PYTHON_EXE%" manage.py check
if errorlevel 1 (
    echo.
    echo [LOI] Django check that bai. Server chua duoc khoi dong.
    pause
    exit /b 1
)

echo.
echo Server dang chay tai:
echo   - May nay:   http://127.0.0.1:8000
echo   - Cung Wi-Fi: http://^<IP-MAY-TINH^>:8000
echo.
echo Nhan Ctrl+C de dung server.
echo ================================================================
echo.

rem Bind 0.0.0.0 de dien thoai trong cung mang co the ket noi.
"%PYTHON_EXE%" manage.py runserver 0.0.0.0:8000

echo.
echo GradeFlow server da dung.
pause
