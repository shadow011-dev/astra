@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

python -m venv build-venv
call build-venv\Scripts\activate.bat
python -m pip install -q --upgrade pip
pip install -q -r requirements.txt -r requirements-app.txt

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist Astra.spec del /q Astra.spec

pyinstaller --noconfirm --windowed --name Astra ^
  --hidden-import mcq_blink --hidden-import config --hidden-import ollama_util ^
  --hidden-import popup --hidden-import settings_window ^
  --hidden-import certifi --collect-data certifi ^
  --hidden-import pystray._win32 ^
  --hidden-import pynput.keyboard._win32 --hidden-import pynput.mouse._win32 ^
  shadow_app.py

if exist Astra-win-x64.zip del /q Astra-win-x64.zip
powershell -Command "Compress-Archive -Path 'dist\Astra\*' -DestinationPath 'Astra-win-x64.zip' -Force"

echo.
echo Built: %cd%\dist\Astra\Astra.exe
echo Share: %cd%\Astra-win-x64.zip
