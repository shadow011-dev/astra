# Shadow

Hotkey -> screenshot -> Qwen3.5 4B -> answer as Caps Lock LED blinks.

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
- **One-word answer** question (no options) -> a small popup appears in the **top-right corner for 1 second**, and the LED does **not** blink at all.

Press the hotkey **again while the model is thinking** to stop it (no blink, no popup).

The LED stays dark while the model thinks (menu bar shows status). Set `"thinking_led": true` in the config to light it while thinking.

## Setup (MacBook Air M4)

```bash
# 1. Model runtime (runs on Apple GPU, ~3.4 GB for the 4B)
brew install ollama
brew services start ollama
ollama pull qwen3.5:4b

# 2. Python deps
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 3. Run
python mcq_blink.py
```

## Arjuna (OpenRouter)

Same pipeline and same output (Caps Lock blinks, one-word popup), but the screenshot goes to a model on OpenRouter instead of local Ollama.

- Karna hotkey: `Ctrl + Option + Cmd + K` (local Ollama). Arjuna hotkey: `Ctrl + Option + Cmd + M` (OpenRouter).
- Menu bar -> **Settings...** -> up to 3 OpenRouter API keys (one is enough; or edit `openrouter_api_key`, `openrouter_api_key_2`, `openrouter_api_key_3` in `~/.shadow/config.json`, or set `OPENROUTER_API_KEY` for key 1). Arjuna uses key 1 first and moves to the next saved key after 40 requests (`key_switch_after`); if there is no next key it stays on the current one.
- Model: `openrouter_model` in the config (any vision-capable slug), default `google/gemini-2.5-flash`.
- Menu bar shows **Last answer**, **Last confidence** and **Last model** (Karna or Arjuna). Confidence uses token probabilities when the provider returns them; otherwise Arjuna asks the model for its own estimate (shown with a `~`).
- **Arjuna + Gemma 4 31B (v025):** hold `Ctrl + Option + Cmd` and press `M` and `K` together. Same Arjuna pipeline (screenshot -> OpenRouter -> blink/popup) but with `openrouter_model_gemma` (default `google/gemma-4-31b-it`). Plain `M` still uses `openrouter_model`; plain `K` is still Karna. A lone M or K waits ~0.15 s to see whether the other key follows. Change the chord with `hotkey_arjuna_gemma`.
- Terminal: `python mcq_blink.py now arjuna` (or `now gemma`) runs Arjuna once.
- Note: Arjuna sends your screenshot to OpenRouter and the model provider; Karna stays on your Mac.

One-word / text answers are also copied to the clipboard automatically.

## Permissions (System Settings -> Privacy & Security)

Grant to the app you launch Python from (Terminal / iTerm / VS Code):

- **Screen & System Audio Recording** - for `screencapture`
- **Accessibility** and **Input Monitoring** - for the global hotkey

Restart the terminal after granting.

## Usage

Default hotkey: `Ctrl + Option + Cmd + K`. Change with `MCQ_HOTKEY` (modifiers + one letter/digit):

```bash
MCQ_HOTKEY="cmd+shift+9" python mcq_blink.py
```

Keep the full question + options visible on screen when you press it.

## Menu-bar app (shareable)

See `SHARING.md`. Build with `./build_app.sh` to get `Shadow-mac-arm64.zip`.

## Troubleshooting (test each part alone)

```bash
python mcq_blink.py led 3      # LED test: should blink 3 times
python mcq_blink.py now        # screenshot + model + blink once, no hotkey
MCQ_DEBUG=1 python mcq_blink.py  # prints every key press; hotkey prints "hotkey pressed"
```

- No key events printed -> grant Input Monitoring + Accessibility to your terminal, then restart it.
- `now` fails -> check Screen Recording permission and that Ollama is running (`ollama list`).

## Thinking mode

Off by default (fast, ~2-6s). For hard maths/logic questions:

```bash
MCQ_THINK=1 python mcq_blink.py
```

Slower (can take 15-40s+) but more accurate. Other model: `MCQ_MODEL=qwen2.5vl:7b` (thinking is ignored by it).

## Number of options

Looks for A-F (6 options) by default. If your tests only have 4, set `"options": 4` in `~/.shadow/config.json`
(or `MCQ_OPTIONS=4`). Fewer options = slightly more accurate. Range: 2-6.

## Notes

- First call is slow (model load, ~10-20s). Later ones ~3-8s. `keep_alive` holds it in RAM for 30 min.
- Caps Lock is briefly toggled for real, so don't type during blinks. The original state is restored afterwards.
- Caps Lock LED works on the built-in MacBook keyboard. External keyboards may not respond.
- A 7B model gets maybe 60-80% on typical MCQs, less on hard maths. Treat answers as hints.
- If answers are wrong due to small text, zoom the browser in or raise `MAX_WIDTH`.
