# Shadow / Astra (Windows Edition)

Hotkey -> screenshot -> AI model (local Ollama or OpenRouter) -> answer as Caps Lock LED blinks.

| Blinks | Answer |
|--------|--------|
| 1 | A |
| 2 | B |
| 3 | C |
| 4 | D |
| 5 | E |
| 6 | F |
| 10 fast flickers | error / no answer |

Rules the AI follows:
- Several questions on screen -> only the **first (topmost)** is answered.
- Options ABOVE the question text are ignored (they belong to the previous question).
- **One-word answer** question (no options) -> a small click-through popup appears in the **top-right corner**, and the LED does **not** blink at all.

Press the hotkey **again while the model is thinking** to stop it (no blink, no popup).

## Setup (Windows 10 / 11)

```bat
:: 1. Install Ollama from https://ollama.com/download, then pull the model:
ollama pull qwen3.5:4b

:: 2. Python deps
python -m venv venv
call venv\Scripts\activate.bat
pip install -r requirements.txt

:: 3. Run CLI or System Tray App
python mcq_blink.py
:: OR double-click run_app.bat for the system tray app
```

## Hotkeys on Windows
The defaults are deliberately kept short to avoid Windows' reserved `Win+K` (Cast) and `Win+M` (minimize all) shortcuts:
- **Karna (local Ollama):** `Alt + K` (`alt+k` in config)
- **Arjuna (OpenRouter):** `Alt + M` (`alt+m` in config)
- **Arjuna + Gemma 4 31B:** hold `Alt`, then press `M` and `K` together (`alt+m+k` in config)

You can change these in `%USERPROFILE%\.shadow\config.json`. The three hotkeys must be distinct. If the tray app was already running when you edited the file, restart it to apply the changes.
