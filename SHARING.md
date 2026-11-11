# Sharing Shadow with friends

## You (builder) - once per version
```bash
cd ~/shadow
./build_app.sh
```
This makes `Shadow-mac-arm64.zip`. Send that zip to friends (AirDrop, Drive, WhatsApp...).
Test first without building: `./venv/bin/pip install -r requirements-app.txt && ./venv/bin/python shadow_app.py`

## Friend (user) - one-time setup
Needs: a Mac with Apple Silicon (M1 or newer), macOS 13+, 8 GB RAM or more (16 GB is smoother), ~5 GB free disk.

1. Install **Ollama** from https://ollama.com/download and open it once.
2. Unzip `Shadow-mac-arm64.zip`, drag **Shadow.app** into Applications.
3. The app is not notarized by Apple, so the first time: **right-click -> Open -> Open**.
   If macOS says it is "damaged", run: `xattr -cr /Applications/Shadow.app`
4. A **Shadow** item appears in the menu bar. It will offer to download the AI model (~3.4 GB). Say Download.
5. Menu bar -> **Permissions** -> enable **Astra** under Screen Recording, Accessibility and Input Monitoring. Quit and reopen the app after.
6. Menu bar -> **Test LED** should blink the Caps Lock light 3 times.

## Using it
Show the question + options on screen, press **Ctrl + Option + Cmd + K**.
LED on = thinking. Then blinks: 1 = A, 2 = B, 3 = C, 4 = D, 5 = E, 6 = F. 10 fast flickers = error.
Questions with no options (one-word answers) show a popup in the top-right corner for 1 second, no LED.

Change the hotkey/model: menu bar -> **Open config file** (`~/.shadow/config.json`), then quit and reopen.
Example hotkey: `"hotkey": "cmd+shift+9"`. Number of answer choices: `"options": 4` (default 6, range 2-6). Also: `"popup_seconds": 1.0`, `"thinking_led": false`.

## Notes
- Works on the built-in MacBook keyboard LED. External keyboards may not light up.
- Answers come from a small local AI model, so some will be wrong. Treat them as hints.
- Rebuilding the app changes its signature, so macOS may ask for the permissions again.
- Apple Developer signing + notarization ($99/yr) would remove the right-click -> Open step.
