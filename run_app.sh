#!/bin/bash
# Run Shadow from source (no build needed). Needs Python 3 and Ollama.
cd "$(dirname "$0")"
[ -d venv ] || python3 -m venv venv
./venv/bin/pip install -q -r requirements.txt rumps
exec ./venv/bin/python shadow_app.py
