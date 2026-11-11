"""Settings stored in ~/.shadow/config.json (shared by the CLI script and the tray app)."""
import json
from pathlib import Path

VERSION = "028"
CONFIG_DIR = Path.home() / ".shadow"
CONFIG_FILE = CONFIG_DIR / "config.json"
LEGACY_FILES = [  # settings from before the renames
    Path.home() / ".agnimcq" / "config.json",
    Path.home() / ".mcqblink" / "config.json",
]
DEFAULTS = {
    "hotkey": "ctrl+alt+cmd+k",  # Karna
    "model": "qwen3.5:4b",
    "think": False,
    "two_step": True,       # read screen to text first, then answer with thinking (more accurate)
    "answer_think": False,   # thinking during the answer step
    "options": 6,  # how many answer choices (A-F) to look for; 2-6
    "thinking_led": True,   # keep Caps Lock LED on while the model works (off = LED stays dark)
    "popup_seconds": 2.0,   # how long the one-word-answer popup stays on screen
    "ollama_url": "http://localhost:11434/api/chat",
    # ---- Arjuna: same pipeline, but the request goes to OpenRouter instead of local Ollama ----
    "hotkey_arjuna": "ctrl+alt+cmd+m",  # Arjuna: press Alt+M
    "openrouter_api_key": "",          # key 1 (or set the OPENROUTER_API_KEY environment variable)
    "openrouter_api_key_2": "",        # optional: used after key 1 has made `key_switch_after` requests
    "openrouter_api_key_3": "",        # optional: used after key 2 has made `key_switch_after` requests
    "key_switch_after": 40,            # requests per key before moving on to the next saved key
    "openrouter_model": "google/gemini-2.5-flash",   # any vision-capable model slug from openrouter.ai/models
    "openrouter_url": "https://openrouter.ai/api/v1/chat/completions",
    # ---- Arjuna + Gemma 4: press all of Ctrl+Alt+Win+M+K together. Same Arjuna pipeline, Gemma 4 31B vision ----
    "hotkey_arjuna_gemma": "ctrl+alt+cmd+m+k",
    "openrouter_model_gemma": "google/gemma-4-31b-it",
    "arjuna_two_step": False,          # False = one call (screenshot -> answer); True = read, then solve
}


def save_config(cfg, path=None):
    path = Path(path) if path else CONFIG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _read(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if k in DEFAULTS} if isinstance(data, dict) else {}


def load_config(path=None):
    using_default = path is None
    path = Path(path) if path else CONFIG_FILE
    cfg = dict(DEFAULTS)
    try:
        if path.exists():
            cfg.update(_read(path))
            # v028: restore documented, distinct Ctrl+Alt+Win hotkeys.
            if cfg["hotkey"] == cfg["hotkey_arjuna"]:
                cfg["hotkey"], cfg["hotkey_arjuna"] = DEFAULTS["hotkey"], DEFAULTS["hotkey_arjuna"]
                save_config(cfg, path)
        else:
            if using_default:
                for legacy in LEGACY_FILES:
                    if legacy.exists():
                        cfg.update(_read(legacy))
                        break
            save_config(cfg, path)
    except Exception:
        pass
    cfg["think"] = bool(cfg["think"])
    cfg["thinking_led"] = bool(cfg["thinking_led"])
    cfg["two_step"] = bool(cfg["two_step"])
    cfg["answer_think"] = bool(cfg["answer_think"])
    cfg["arjuna_two_step"] = bool(cfg["arjuna_two_step"])
    for k in ("openrouter_api_key", "openrouter_api_key_2", "openrouter_api_key_3"):
        cfg[k] = str(cfg[k] or "").strip()
    try:
        cfg["key_switch_after"] = max(1, int(cfg["key_switch_after"]))
    except (TypeError, ValueError):
        cfg["key_switch_after"] = DEFAULTS["key_switch_after"]
    try:
        cfg["popup_seconds"] = max(0.3, min(10.0, float(cfg["popup_seconds"])))
    except (TypeError, ValueError):
        cfg["popup_seconds"] = DEFAULTS["popup_seconds"]
    try:
        cfg["options"] = max(2, min(6, int(cfg["options"])))
    except (TypeError, ValueError):
        cfg["options"] = DEFAULTS["options"]
    return cfg
