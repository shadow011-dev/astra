#!/bin/bash
# Builds Astra.app and Astra-mac-arm64.zip (the file you share). Run on a Mac.
set -euo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"

$PY -m venv build-venv
source build-venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt -r requirements-app.txt

rm -rf build dist Astra.spec
pyinstaller --noconfirm --windowed --name Astra \
  --osx-bundle-identifier com.astra.app \
  --hidden-import mcq_blink --hidden-import config --hidden-import ollama_util --hidden-import popup \
  --hidden-import certifi --collect-data certifi --hidden-import AppKit --hidden-import PyObjCTools.AppHelper \
  --hidden-import pynput.keyboard._darwin --hidden-import pynput.mouse._darwin \
  shadow_app.py

PL="dist/Astra.app/Contents/Info.plist"
setkey() {  # setkey KEY TYPE VALUE  (add, or overwrite if it already exists)
  /usr/libexec/PlistBuddy -c "Add :$1 $2 $3" "$PL" 2>/dev/null || /usr/libexec/PlistBuddy -c "Set :$1 $3" "$PL"
}
setkey LSUIElement bool true                          # menu-bar only, no Dock icon
setkey NSScreenCaptureUsageDescription string "Astra reads the question on your screen."
setkey NSInputMonitoringUsageDescription string "Astra listens for your hotkey."

codesign --force --deep --sign - dist/Astra.app    # ad-hoc signature (required on Apple Silicon)
rm -f Astra-mac-arm64.zip
ditto -c -k --keepParent dist/Astra.app Astra-mac-arm64.zip

echo
echo "Built: $(pwd)/dist/Astra.app"
echo "Share: $(pwd)/Astra-mac-arm64.zip   (read SHARING.md for what friends must do)"
