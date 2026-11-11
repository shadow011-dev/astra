@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python was not found. Install 64-bit Python 3 and enable PATH.
    pause
    exit /b 1
)
if not exist venv\Scripts\python.exe python -m venv venv
if errorlevel 1 goto fail
call venv\Scripts\activate.bat
if errorlevel 1 goto fail
python -m pip install --upgrade pip
if errorlevel 1 goto fail
python -m pip install -r requirements.txt -r requirements-app.txt
if errorlevel 1 goto fail
start "" venv\Scripts\pythonw.exe shadow_app.py
exit /b 0
:fail
echo.
echo ERROR: Setup failed. Check the first error above.
pause
exit /b 1
