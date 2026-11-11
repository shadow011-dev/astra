@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python 3 was not found. Install 64-bit Python and enable Add Python to PATH.
  pause
  exit /b 1
)
python -c "import struct,sys; sys.exit(0 if struct.calcsize('P')*8 == 64 else 1)"
if errorlevel 1 (
  echo ERROR: Astra must be built with 64-bit Python.
  pause
  exit /b 1
)

if not exist build-venv\Scripts\python.exe python -m venv build-venv
if errorlevel 1 goto fail
call build-venv\Scripts\activate.bat
if errorlevel 1 goto fail
python -m pip install --upgrade pip
if errorlevel 1 goto fail
pip install -r requirements.txt -r requirements-app.txt
if errorlevel 1 goto fail

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist Astra.spec del /q Astra.spec
if exist Astra-win-x64.zip del /q Astra-win-x64.zip

pyinstaller --noconfirm --clean --windowed --onedir --name Astra ^
  --hidden-import mcq_blink --hidden-import config --hidden-import ollama_util ^
  --hidden-import popup --hidden-import settings_window ^
  --hidden-import certifi --collect-data certifi ^
  --hidden-import pystray._win32 ^
  --hidden-import pynput.keyboard._win32 --hidden-import pynput.mouse._win32 ^
  shadow_app.py
if errorlevel 1 goto fail
if not exist dist\Astra\Astra.exe goto fail

powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'dist\Astra\*' -DestinationPath 'Astra-win-x64.zip' -Force"
if errorlevel 1 goto fail
if not exist Astra-win-x64.zip goto fail

echo.
echo SUCCESS: %cd%\dist\Astra\Astra.exe
echo SUCCESS: %cd%\Astra-win-x64.zip
pause
exit /b 0

:fail
echo.
echo ERROR: Build failed. Scroll up for the first error; no new ZIP should be shared.
pause
exit /b 1
