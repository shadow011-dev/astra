#!/usr/bin/env python3
"""
mcq_blink (Windows): hotkey -> screenshot -> model -> blink Caps Lock LED.

Two models, same output:
  Karna  (hotkey ctrl+alt+cmd+k): Qwen3.5 4B running locally through Ollama.
  Arjuna (hotkey ctrl+alt+cmd+m): a vision model on OpenRouter (needs an API key).
  Arjuna + Gemma 4 (hold ctrl+alt+cmd and press M and K together): Arjuna with Gemma 4 31B (OpenRouter).

1 blink = A, 2 = B, 3 = C, 4 = D, 5 = E, 6 = F
Questions with no options (one-word answers): popup in the top-right corner for ~1s, LED does not blink.
10 fast flickers = error / couldn't find an answer.
Press the hotkey again while the model is thinking to stop it.
"""
import base64
import ctypes
from ctypes import wintypes
import http.client
import io
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import threading
import time
import urllib.parse

import requests
from PIL import Image, ImageGrab
from pynput import keyboard

# ------------------------- config -------------------------
from config import CONFIG_FILE, load_config, VERSION as CFG_VERSION
import popup

CFG = load_config()
HOTKEY = os.environ.get("MCQ_HOTKEY") or CFG["hotkey"]
DEBUG = os.environ.get("MCQ_DEBUG", "0") == "1"
MODEL = os.environ.get("MCQ_MODEL") or CFG["model"]
THINK = (os.environ.get("MCQ_THINK") == "1") if "MCQ_THINK" in os.environ else CFG["think"]
OLLAMA_URL = os.environ.get("OLLAMA_URL") or CFG["ollama_url"]
MAX_WIDTH = 1600
BLINK_ON = 0.35
BLINK_OFF = 0.35
PAUSE_BEFORE_BLINKS = 1.0
THINK_LED = CFG["thinking_led"]
POPUP_SECONDS = CFG["popup_seconds"]
TWO_STEP = (os.environ.get("MCQ_TWO_STEP") == "1") if "MCQ_TWO_STEP" in os.environ else CFG["two_step"]
HOTKEY_ARJUNA = os.environ.get("ARJUNA_HOTKEY") or CFG["hotkey_arjuna"]
OPENROUTER_URL = os.environ.get("OPENROUTER_URL") or CFG["openrouter_url"]
OPENROUTER_MODEL = os.environ.get("ARJUNA_MODEL") or CFG["openrouter_model"]
ARJUNA_TWO_STEP = (os.environ.get("ARJUNA_TWO_STEP") == "1") if "ARJUNA_TWO_STEP" in os.environ else CFG["arjuna_two_step"]
HOTKEY_GEMMA = os.environ.get("GEMMA_HOTKEY") or CFG["hotkey_arjuna_gemma"]
GEMMA_MODEL = os.environ.get("GEMMA_MODEL") or CFG["openrouter_model_gemma"]
CHORD_WAIT = 0.15
NAMES = {"karna": "Karna", "arjuna": "Arjuna", "gemma": "Arjuna (Gemma 4)"}
MODELS = {"arjuna": OPENROUTER_MODEL, "gemma": GEMMA_MODEL}
ANSWER_THINK = (os.environ.get("MCQ_ANSWER_THINK") == "1") if "MCQ_ANSWER_THINK" in os.environ else CFG["answer_think"]

try:
    _N = max(2, min(6, int(os.environ.get("MCQ_OPTIONS", CFG["options"]))))
except ValueError:
    _N = 6
LETTERS = "ABCDEF"[:_N]
_LIST = f"{', '.join(LETTERS[:-1])} or {LETTERS[-1]}"
PROMPT = (
    "The image is a screenshot of a quiz page. Follow these rules exactly.\n"
    "1. If more than one question is visible, answer ONLY the first (topmost) question.\n"
    "2. Answer options belong to a question only if they appear BELOW that question's text. "
    "Ignore any options that appear ABOVE the question text: they belong to a previous question.\n"
    f"3. If the question has answer options, reply with ONLY the letter of the correct option ({_LIST}).\n"
    "4. If the question has no answer options and needs a one-word (or very short) answer, "
    "reply exactly: ANSWER: <the answer>   (at most 3 words).\n"
    "No explanation, nothing else."
)
READ_PROMPT = (
    "This is a screenshot of a quiz. Copy ONLY the first (topmost) question and the answer options "
    "that appear BELOW it, word for word. Ignore options above the question. "
    "Label the options A), B), C)... in the order shown.\n"
    "Format:\nQ: <question>\nA) <option>\nB) <option>\n"
    "If it is a statement to judge true or false, write it as the Q: line only. "
    "If there are no options, write only the Q: line. Do not answer it."
)
SOLVE_PROMPT = (
    "{q}\n\n"
    f"If options are listed, reply with ONLY the letter of the correct option ({_LIST}). "
    "If it is a true/false statement, reply exactly: ANSWER: True or ANSWER: False. "
    "Otherwise reply exactly: ANSWER: <answer> (at most 3 words)."
)


def reload_runtime_config():
    """Reload settings live from ~/.shadow/config.json so changes take effect immediately."""
    global CFG, HOTKEY, MODEL, THINK, OLLAMA_URL, THINK_LED, POPUP_SECONDS, TWO_STEP
    global HOTKEY_ARJUNA, OPENROUTER_URL, OPENROUTER_MODEL, ARJUNA_TWO_STEP
    global HOTKEY_GEMMA, GEMMA_MODEL, MODELS, ANSWER_THINK, _N, LETTERS, _LIST, PROMPT, SOLVE_PROMPT
    CFG = load_config()
    HOTKEY = os.environ.get("MCQ_HOTKEY") or CFG["hotkey"]
    MODEL = os.environ.get("MCQ_MODEL") or CFG["model"]
    THINK = (os.environ.get("MCQ_THINK") == "1") if "MCQ_THINK" in os.environ else CFG["think"]
    OLLAMA_URL = os.environ.get("OLLAMA_URL") or CFG["ollama_url"]
    THINK_LED = CFG["thinking_led"]
    POPUP_SECONDS = CFG["popup_seconds"]
    TWO_STEP = (os.environ.get("MCQ_TWO_STEP") == "1") if "MCQ_TWO_STEP" in os.environ else CFG["two_step"]
    HOTKEY_ARJUNA = os.environ.get("ARJUNA_HOTKEY") or CFG["hotkey_arjuna"]
    OPENROUTER_URL = os.environ.get("OPENROUTER_URL") or CFG["openrouter_url"]
    OPENROUTER_MODEL = os.environ.get("ARJUNA_MODEL") or CFG["openrouter_model"]
    ARJUNA_TWO_STEP = (os.environ.get("ARJUNA_TWO_STEP") == "1") if "ARJUNA_TWO_STEP" in os.environ else CFG["arjuna_two_step"]
    HOTKEY_GEMMA = os.environ.get("GEMMA_HOTKEY") or CFG["hotkey_arjuna_gemma"]
    GEMMA_MODEL = os.environ.get("GEMMA_MODEL") or CFG["openrouter_model_gemma"]
    MODELS = {"arjuna": OPENROUTER_MODEL, "gemma": GEMMA_MODEL}
    ANSWER_THINK = (os.environ.get("MCQ_ANSWER_THINK") == "1") if "MCQ_ANSWER_THINK" in os.environ else CFG["answer_think"]
    try:
        _N = max(2, min(6, int(os.environ.get("MCQ_OPTIONS", CFG["options"]))))
    except ValueError:
        _N = 6
    LETTERS = "ABCDEF"[:_N]
    _LIST = f"{', '.join(LETTERS[:-1])} or {LETTERS[-1]}"
    PROMPT = (
        "The image is a screenshot of a quiz page. Follow these rules exactly.\n"
        "1. If more than one question is visible, answer ONLY the first (topmost) question.\n"
        "2. Answer options belong to a question only if they appear BELOW that question's text. "
        "Ignore any options that appear ABOVE the question text: they belong to a previous question.\n"
        f"3. If the question has answer options, reply with ONLY the letter of the correct option ({_LIST}).\n"
        "4. If the question has no answer options and needs a one-word (or very short) answer, "
        "reply exactly: ANSWER: <the answer>   (at most 3 words).\n"
        "No explanation, nothing else."
    )
    SOLVE_PROMPT = (
        "{q}\n\n"
        f"If options are listed, reply with ONLY the letter of the correct option ({_LIST}). "
        "If it is a true/false statement, reply exactly: ANSWER: True or ANSWER: False. "
        "Otherwise reply exactly: ANSWER: <answer> (at most 3 words)."
    )

# -----------------------------------------------------------

# ---- Caps Lock LED / state via Win32 keybd_event + Modifier Bypass (Windows) ----
_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32

VK_CAPITAL = 0x14
VK_SHIFT = 0x10
VK_LSHIFT = 0xA0
VK_RSHIFT = 0xA1
VK_CONTROL = 0x11
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_MENU = 0x12
VK_LMENU = 0xA4
VK_RMENU = 0xA5
VK_LWIN = 0x5B
VK_RWIN = 0x5C

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002

_led_lock = threading.Lock()
_SYNTHETIC_EVENT = False  # Prevents synthetic modifier key-ups from confusing the hotkey listener


def have_screen_access() -> bool:
    return True


def request_screen_access() -> bool:
    return True


def _os_caps_state() -> bool:
    """GetKeyState(VK_CAPITAL) is cached per GUI thread in Windows.
    Because the hotkey callback runs on a non-GUI worker thread, we attach briefly
    to the foreground window's thread so GetKeyState always returns the live Caps Lock state."""
    fg = _user32.GetForegroundWindow()
    cur_tid = _kernel32.GetCurrentThreadId()
    fg_tid = _user32.GetWindowThreadProcessId(fg, None) if fg else 0
    attached = False
    try:
        if fg_tid and fg_tid != cur_tid:
            attached = bool(_user32.AttachThreadInput(cur_tid, fg_tid, True))
        return bool(_user32.GetKeyState(VK_CAPITAL) & 0x0001)
    finally:
        if attached:
            _user32.AttachThreadInput(cur_tid, fg_tid, False)


def caps_get() -> bool:
    return _os_caps_state()


def _tap_key(vk: int, scan: int = 0, down: bool = True, up: bool = True) -> None:
    if not scan:
        scan = _user32.MapVirtualKeyW(vk, 0)
    if down:
        _user32.keybd_event(vk, scan, KEYEVENTF_EXTENDEDKEY, 0)
    if up:
        _user32.keybd_event(vk, scan, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)


def caps_set(on: bool) -> None:
    """Toggle Caps Lock LED reliably whether triggered from the tray menu OR a keyboard shortcut.
    When triggered from the tray menu, no modifiers (Ctrl/Alt/Shift/Win) are held down, so
    keybd_event(VK_CAPITAL) works immediately.
    When triggered from a keyboard shortcut, the user's fingers are still holding Ctrl/Alt/Shift/Win,
    and Windows ignores VK_CAPITAL while modifiers are down in the OS input state.
    By sending KEYUP via keybd_event for any held modifiers right before tapping VK_CAPITAL,
    the LED lights up immediately on hotkey press just like it does from the tray menu."""
    global _SYNTHETIC_EVENT
    target = bool(on)
    with _led_lock:
        if _os_caps_state() == target:
            return

        _SYNTHETIC_EVENT = True
        try:
            # 1. Logically release any held modifiers in the Windows input queue so VK_CAPITAL isn't blocked
            for mvk in (VK_LCONTROL, VK_RCONTROL, VK_CONTROL,
                        VK_LMENU, VK_RMENU, VK_MENU,
                        VK_LSHIFT, VK_RSHIFT, VK_SHIFT,
                        VK_LWIN, VK_RWIN):
                if (_user32.GetAsyncKeyState(mvk) & 0x8000) or (_user32.GetKeyState(mvk) & 0x8000):
                    _tap_key(mvk, down=False, up=True)

            # 2. Tap Caps Lock using the exact keybd_event call that works from the tray menu
            _user32.keybd_event(VK_CAPITAL, 0x3A, KEYEVENTF_EXTENDEDKEY, 0)
            time.sleep(0.015)
            _user32.keybd_event(VK_CAPITAL, 0x3A, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)
            time.sleep(0.025)
        finally:
            _SYNTHETIC_EVENT = False


def blink(n: int, on=BLINK_ON, off=BLINK_OFF) -> None:
    caps_set(False)
    time.sleep(off)
    for _ in range(n):
        caps_set(True)
        time.sleep(on)
        caps_set(False)
        time.sleep(off)


# ---- screenshot + model ----
def take_screenshot() -> str:
    """Returns base64 PNG of the primary display (downscaled)."""
    img = ImageGrab.grab(all_screens=False).convert("RGB")
    if img.width > MAX_WIDTH:
        h = int(img.height * MAX_WIDTH / img.width)
        img = img.resize((MAX_WIDTH, h), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


class Cancelled(Exception):
    """The user pressed the hotkey again while the model was thinking."""


_cancel = threading.Event()
_conn_lock = threading.Lock()
_conn = None


def _abort_connection() -> None:
    """Hard-close the connection to Ollama: Ollama sees the disconnect and stops generating."""
    with _conn_lock:
        c = _conn
    if c is None:
        return
    try:
        if c.sock is not None:
            c.sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        c.close()
    except Exception:
        pass


LAST_LP = None
LAST_SELF_CONF = None
CONF_SUFFIX = "\nAfter your answer, add a new line: CONF: <0-100> (how sure you are, as a percentage)."


def _split_conf(text: str) -> str:
    global LAST_SELF_CONF
    m = re.search(r"\n?\s*CONF(?:IDENCE)?\s*[:=]\s*(\d{1,3})\s*%?\s*$", text or "", re.IGNORECASE)
    if not m:
        return text
    LAST_SELF_CONF = max(0, min(100, int(m.group(1))))
    return text[:m.start()].strip()


def _ssl_ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _post_json(url: str, body: str, headers: dict, timeout: float):
    global _conn
    u = urllib.parse.urlparse(url)
    if u.scheme == "https":
        conn = http.client.HTTPSConnection(u.hostname, u.port, timeout=timeout, context=_ssl_ctx())
    else:
        conn = http.client.HTTPConnection(u.hostname, u.port, timeout=timeout)
    headers = {"User-Agent": "Astra/" + CFG_VERSION, **headers}
    with _conn_lock:
        _conn = conn
    try:
        if _cancel.is_set():
            raise Cancelled()
        try:
            path = (u.path or "/") + (("?" + u.query) if u.query else "")
            conn.request("POST", path, body=body, headers=headers)
            resp = conn.getresponse()
            data = resp.read()
        except Exception:
            if _cancel.is_set():
                raise Cancelled()
            raise
        if _cancel.is_set():
            raise Cancelled()
        return resp.status, data
    finally:
        with _conn_lock:
            _conn = None
        try:
            conn.close()
        except Exception:
            pass


def _chat(content: str, images, think: bool, num_predict: int, lp: bool = False) -> str:
    global LAST_LP
    msg = {"role": "user", "content": content}
    if images:
        msg["images"] = images
    body = json.dumps({
        "model": MODEL,
        "stream": False,
        "think": think,
        "keep_alive": "30m",
        "options": {"temperature": 0, "num_predict": num_predict},
        "messages": [msg],
        **({"logprobs": True, "top_logprobs": 5} if lp else {}),
    })
    status, data = _post_json(OLLAMA_URL, body, {"Content-Type": "application/json"},
                              300 if think else 120)
    if status >= 400:
        raise RuntimeError(f"Ollama HTTP {status}: {data[:200]!r}")
    j = json.loads(data)
    LAST_LP = (j.get("logprobs") or j["message"].get("logprobs")) if lp else None
    return j["message"].get("content", "") or ""


KEY_STATE_FILE = CONFIG_FILE.parent / "key_state.json"
_key_lock = threading.Lock()


def openrouter_keys() -> list:
    cfg = load_config()
    keys = [cfg["openrouter_api_key"], cfg["openrouter_api_key_2"], cfg["openrouter_api_key_3"]]
    env = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if env:
        keys[0] = env
    return [k for k in keys if k]


def _load_key_state() -> dict:
    try:
        d = json.loads(KEY_STATE_FILE.read_text(encoding="utf-8"))
        return {"idx": int(d.get("idx", 0)), "count": int(d.get("count", 0))}
    except Exception:
        return {"idx": 0, "count": 0}


def key_status() -> tuple:
    keys = openrouter_keys()
    st = _load_key_state()
    return len(keys), min(st["idx"], max(0, len(keys) - 1)) + 1, st["count"]


def openrouter_key() -> str:
    keys = openrouter_keys()
    if not keys:
        return ""
    with _key_lock:
        idx = min(_load_key_state()["idx"], len(keys) - 1)
    return keys[idx]


def _count_key_use():
    try:
        keys = openrouter_keys()
        limit = load_config()["key_switch_after"]
        with _key_lock:
            st = _load_key_state()
            st["idx"] = min(st["idx"], max(0, len(keys) - 1))
            st["count"] += 1
            if st["count"] >= limit and st["idx"] + 1 < len(keys):
                st["idx"] += 1
                st["count"] = 0
            KEY_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            KEY_STATE_FILE.write_text(json.dumps(st), encoding="utf-8")
    except Exception as e:
        print("key counter failed:", e)


def _chat_openrouter(content: str, images, max_tokens: int, lp: bool = False, model: str = None) -> str:
    global LAST_LP
    key = openrouter_key()
    if not key:
        raise RuntimeError("OpenRouter API key missing: set openrouter_api_key in ~/.shadow/config.json "
                           "(menu: Settings) or the OPENROUTER_API_KEY env var")
    parts = [{"type": "text", "text": content}]
    for b in images or []:
        parts.append({"type": "image_url", "image_url": {"url": "data:image/png;base64," + b}})
    def build(with_lp):
        return json.dumps({
            "model": model or OPENROUTER_MODEL,
            "temperature": 0,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": parts}],
            **({"logprobs": True, "top_logprobs": 5} if with_lp else {}),
        })
    hdrs = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + key,
        "HTTP-Referer": "https://localhost",
        "X-Title": "Astra",
    }
    try:
        status, data = _post_json(OPENROUTER_URL, build(lp), hdrs, 120)
        if status == 400 and lp:
            status, data = _post_json(OPENROUTER_URL, build(False), hdrs, 120)
            lp = False
    finally:
        _count_key_use()
    if status >= 400:
        raise RuntimeError(f"OpenRouter HTTP {status}: {data[:300]!r}")
    j = json.loads(data)
    if j.get("error"):
        raise RuntimeError(f"OpenRouter error: {str(j['error'])[:300]}")
    choice = j["choices"][0]
    LAST_LP = ((choice.get("logprobs") or {}).get("content")) if lp else None
    text = (choice.get("message") or {}).get("content") or ""
    if isinstance(text, list):
        text = "".join(p.get("text", "") for p in text if isinstance(p, dict))
    return text


def ask_model(b64: str, who: str = "karna") -> str:
    global LAST_LP, LAST_SELF_CONF
    LAST_LP = None
    LAST_SELF_CONF = None
    if who in MODELS:
        model = MODELS[who]
        def chat(content, images, think, n, lp=False):
            if content == PROMPT or (not images and "reply with ONLY the letter" in content):
                return _split_conf(_chat_openrouter(content + CONF_SUFFIX, images, 1024, lp, model))
            return _chat_openrouter(content, images, 1024, lp, model)
        two_step, think, answer_think = ARJUNA_TWO_STEP, False, False
    else:
        chat, two_step, think, answer_think = _chat, TWO_STEP, THINK, ANSWER_THINK
    if not two_step:
        return chat(PROMPT, [b64], think, 4096 if think else 48, lp=not think)
    q = chat(READ_PROMPT, [b64], False, 600).strip()
    if DEBUG or os.environ.get("MCQ_SHOW", "0") == "1":
        print("read:", q)
    if not q:
        raise RuntimeError("could not read the question")
    p = SOLVE_PROMPT.format(q=q)
    if answer_think:
        r = chat(p, None, True, 1500)
        if r.strip():
            return r
    return chat(p, None, False, 48, lp=True)


def parse_letter(text: str):
    text = text.strip()
    m0 = re.fullmatch(r"\W*(?:answer\s*[:\-]?\s*)?\(?([A-Fa-f])\)?\W*", text, re.IGNORECASE)
    if m0 and m0.group(1).upper() in LETTERS:
        return m0.group(1).upper()
    m = [c.upper() for c in re.findall(r"\b\(?([A-Za-z])\)?\b", text) if c.upper() in LETTERS]
    if m:
        return m[-1]
    m = [int(d) for d in re.findall(r"\b([1-9])\b", text) if int(d) <= len(LETTERS)]
    if m:
        return LETTERS[m[-1] - 1]
    return None


def parse_reply(text: str):
    text = (text or "").strip()
    m = re.search(r"ANSWER\s*[:\-]\s*(.+)", text, re.IGNORECASE)
    if m:
        word = re.sub(r"^[\s\"'`*]+|[\s\"'`*.!]+$", "", m.group(1).strip().splitlines()[0])
        if word:
            as_letter = parse_letter(word) if len(re.sub(r"[()\s.]", "", word)) == 1 else None
            if as_letter:
                return "letter", as_letter
            return "word", word
    if re.fullmatch(r"\W*(?:answer\s*[:\-]?\s*)?\(?[A-Fa-f]\)?\W*", text):
        letter = parse_letter(text)
        if letter:
            return "letter", letter
    up = [c for c in re.findall(r"\b([A-F])\b", text) if c in LETTERS]
    if up:
        return "letter", up[-1]
    if text and len(text.split()) <= 4:
        return "word", text.strip(" .\"'*")
    letter = parse_letter(text)
    if letter:
        return "letter", letter
    return None, None


def confidence(kind, value):
    import math
    try:
        ents = LAST_LP
        if not ents:
            return LAST_SELF_CONF
        clean = lambda t: re.sub(r"[\s()*.:'\"`]", "", t or "")
        if kind == "letter":
            for e in ents:
                if clean(e.get("token")).upper() == value:
                    probs = {}
                    for t in (e.get("top_logprobs") or [{"token": e["token"], "logprob": e["logprob"]}]):
                        c = clean(t.get("token")).upper()
                        if c in LETTERS:
                            probs[c] = probs.get(c, 0) + math.exp(t["logprob"])
                    tot = sum(probs.values())
                    mine = probs.get(value, math.exp(e["logprob"]))
                    return round(100 * mine / (tot or mine))
            return None
        start = 0
        for i, e in enumerate(ents[:5]):
            if ":" in (e.get("token") or ""):
                start = i + 1
                break
        p = 1.0
        n = 0
        for e in ents[start:]:
            if not clean(e.get("token")):
                continue
            p *= math.exp(e["logprob"])
            n += 1
        return round(100 * p) if n else None
    except Exception:
        return None


# ---- main flow ----
_busy = threading.Lock()
STATUS = {"state": "idle", "last": "", "conf": None, "answer": None, "model": None,
          "who": "karna", "error": None, "last_error": None, "conf_self": False, "runs": 0}


def copy_to_clipboard(text: str) -> None:
    try:
        subprocess.run(
            ["clip"],
            input=text.encode("utf-16le"),
            check=True,
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
        )
    except Exception as e:
        print("clipboard copy failed:", e)


def record_error(msg: str) -> None:
    msg = str(msg)
    STATUS["error"] = msg[:200]
    STATUS["last_error"] = msg
    print("error:", msg)
    try:
        from pathlib import Path
        log = Path.home() / ".shadow" / "error.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except Exception:
        pass


def _keep_thinking_led_alive(stop_evt: threading.Event):
    """Continuously assert the Caps Lock LED during the thinking phase."""
    while not stop_evt.is_set() and STATUS["state"] == "thinking":
        try:
            if not _os_caps_state():
                caps_set(True)
        except Exception:
            pass
        stop_evt.wait(0.08)


def run_once(who: str = "karna"):
    if not _busy.acquire(blocking=False):
        return
    reload_runtime_config()
    original = _os_caps_state()
    _cancel.clear()
    STATUS.update(who=who, model=NAMES[who], answer=None, conf=None, error=None)
    STATUS["state"] = "thinking"
    led_stop = threading.Event()
    try:
        if THINK_LED:
            caps_set(True)
            threading.Thread(target=_keep_thinking_led_alive, args=(led_stop,), daemon=True).start()
        b64 = take_screenshot()
        if _cancel.is_set():
            raise Cancelled()
        raw = ask_model(b64, who)
        if _cancel.is_set():
            raise Cancelled()
        kind, value = parse_reply(raw)
        STATUS["conf"] = confidence(kind, value)
        STATUS["conf_self"] = bool(STATUS["conf"] is not None and not LAST_LP)
        STATUS["answer"] = value if kind else None
        STATUS["state"] = "answering"
        led_stop.set()
        print(f"{NAMES[who]} said: {raw!r} -> {kind}: {value}")
        if kind == "word":
            STATUS["last"] = value[:14]
            if THINK_LED:
                caps_set(False)
            copy_to_clipboard(value)
            popup.show_popup(value, POPUP_SECONDS)
        elif kind == "letter":
            STATUS["last"] = value
            if THINK_LED:
                caps_set(False)
            time.sleep(PAUSE_BEFORE_BLINKS)
            blink(LETTERS.index(value) + 1)
        else:
            STATUS["last"] = "?"
            record_error(f"{NAMES[who]} gave no usable answer. Raw reply: {raw!r}")
            blink(10, 0.08, 0.08)
    except Cancelled:
        led_stop.set()
        print("cancelled by hotkey")
        STATUS["last"] = "stopped"
        if THINK_LED:
            caps_set(False)
    except Exception as e:
        led_stop.set()
        STATUS["last"] = "error"
        record_error(f"{NAMES[who]}: {type(e).__name__}: {e}")
        blink(10, 0.08, 0.08)
    finally:
        led_stop.set()
        try:
            caps_set(original)
        except Exception:
            pass
        STATUS["runs"] = STATUS.get("runs", 0) + 1
        STATUS["state"] = "idle"
        _busy.release()


def cancel_thinking() -> bool:
    if STATUS["state"] != "thinking":
        return False
    _cancel.set()
    _abort_connection()
    return True


def on_hotkey(who: str = "karna"):
    if _busy.locked():
        if cancel_thinking():
            print("hotkey pressed again: stopping")
        return
    threading.Thread(target=run_once, args=(who,), daemon=True).start()


# ---- hotkey: Windows Virtual-Key (VK) codes & physical key matching ----
_VK = {
    **{chr(c).lower(): c for c in range(ord("A"), ord("Z") + 1)},
    **{chr(c): c for c in range(ord("0"), ord("9") + 1)},
    **{f"f{i}": 0x6F + i for i in range(1, 13)},  # F1-F12 support
    "space": 0x20,
    "tab": 0x09,
    "enter": 0x0D,
    "return": 0x0D,
    "esc": 0x1B,
    "escape": 0x1B,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "`": 0xC0,
    "~": 0xC0,
    "-": 0xBD,
    "=": 0xBB,
    "[": 0xDB,
    "]": 0xDD,
    "\\": 0xDC,
    ";": 0xBA,
    "'": 0xDE,
    ",": 0xBC,
    ".": 0xBE,
    "/": 0xBF,
}
_ALIASES = {
    "control": "ctrl",
    "ctl": "ctrl",
    "option": "alt",
    "opt": "alt",
    "menu": "alt",
    "command": "cmd",
    "super": "cmd",
    "win": "cmd",
    "windows": "cmd",
    "meta": "cmd",
    "shft": "shift",
}


def parse_hotkey(spec: str):
    """'ctrl+alt+cmd+k' -> ({mods}, {keycodes}). More than one letter/digit = a chord (all held together)."""
    parts = [p.strip().lower() for p in str(spec).replace("<", "").replace(">", "").replace(" ", "").split("+")]
    parts = [_ALIASES.get(p, p) for p in parts if p]
    mods = {p for p in parts if p in ("ctrl", "alt", "cmd", "shift")}
    keys = [p for p in parts if p not in mods]
    if not keys or any(k not in _VK for k in keys):
        raise SystemExit(f"Bad hotkey {spec!r}: use modifiers + letters/digits/F-keys, e.g. ctrl+alt+cmd+k")
    return mods, frozenset(_VK[k] for k in keys)


def _mod_of(key):
    name = getattr(key, "name", "") or ""
    for m in ("ctrl", "alt", "cmd", "shift"):
        if name.startswith(m):
            return m
    vk = getattr(key, "vk", None)
    if vk in (160, 161, 16):
        return "shift"
    if vk in (162, 163, 17):
        return "ctrl"
    if vk in (164, 165, 18):
        return "alt"
    if vk in (91, 92):
        return "cmd"
    return None


def _vk_of(key):
    """Extract the physical Windows Virtual-Key (VK) code reliably even when Ctrl/Alt/Shift are held."""
    vk = getattr(key, "vk", None)
    if vk is not None:
        return int(vk)
    value = getattr(key, "value", None)
    if value is not None and getattr(value, "vk", None) is not None:
        return int(value.vk)
    ch = getattr(key, "char", None)
    if ch and len(ch) == 1:
        code = ord(ch)
        if 1 <= code <= 26:  # Ctrl+A..Z control characters (..)
            return 64 + code
        return _VK.get(ch.lower())
    name = (getattr(key, "name", "") or "").lower()
    return _VK.get(name)


def _async_mods_down() -> set:
    """Query Win32 hardware key state directly so stuck or missed modifier releases never desync hotkeys."""
    mods = set()
    if _user32.GetAsyncKeyState(VK_CONTROL) & 0x8000 or _user32.GetAsyncKeyState(VK_LCONTROL) & 0x8000 or _user32.GetAsyncKeyState(VK_RCONTROL) & 0x8000:
        mods.add("ctrl")
    if _user32.GetAsyncKeyState(VK_MENU) & 0x8000 or _user32.GetAsyncKeyState(VK_LMENU) & 0x8000 or _user32.GetAsyncKeyState(VK_RMENU) & 0x8000:
        mods.add("alt")
    if _user32.GetAsyncKeyState(VK_SHIFT) & 0x8000 or _user32.GetAsyncKeyState(VK_LSHIFT) & 0x8000 or _user32.GetAsyncKeyState(VK_RSHIFT) & 0x8000:
        mods.add("shift")
    if _user32.GetAsyncKeyState(VK_LWIN) & 0x8000 or _user32.GetAsyncKeyState(VK_RWIN) & 0x8000:
        mods.add("cmd")
    return mods


def _load_specs():
    """Always read the latest hotkeys from ~/.shadow/config.json (and env overrides)."""
    reload_runtime_config()
    return [
        (*parse_hotkey(HOTKEY), "karna"),
        (*parse_hotkey(HOTKEY_ARJUNA), "arjuna"),
        (*parse_hotkey(HOTKEY_GEMMA), "gemma"),
    ]


def make_listener():
    """One keyboard listener, three hotkeys: Karna, Arjuna, and Arjuna+Gemma 4.
    Hotkeys are re-read from config.json automatically whenever the file is modified."""
    specs = _load_specs()
    if len({(frozenset(m), k) for m, k, _ in specs}) < len(specs):
        raise SystemExit("Two hotkeys are the same; change hotkey / hotkey_arjuna / hotkey_arjuna_gemma in the config")

    last_mtime = [CONFIG_FILE.stat().st_mtime if CONFIG_FILE.exists() else 0]
    held = set()
    held_keys = set()
    g = {"keys": set(), "mods": set(), "done": False, "timer": None, "waiting": False}

    def refresh_specs_if_changed():
        nonlocal specs
        try:
            mtime = CONFIG_FILE.stat().st_mtime if CONFIG_FILE.exists() else 0
            if mtime != last_mtime[0]:
                last_mtime[0] = mtime
                specs = _load_specs()
                if DEBUG:
                    print(f"Reloaded config hotkeys -> Karna: {HOTKEY}, Arjuna: {HOTKEY_ARJUNA}, Gemma: {HOTKEY_GEMMA}")
        except Exception as e:
            if DEBUG:
                print("Config reload error:", e)

    def reset_if_idle():
        if not held_keys and not g["waiting"]:
            g.update(keys=set(), mods=set(), done=False)

    def fire(final):
        if final:
            g["waiting"] = False
        try:
            _fire(final)
        finally:
            reset_if_idle()

    def _fire(final):
        if g["done"] or not g["keys"]:
            return
        refresh_specs_if_changed()
        exact_hits = [s for s in specs if s[1] <= g["keys"] and s[0] == g["mods"]]
        hits = exact_hits or [s for s in specs if s[1] <= g["keys"] and s[0] <= g["mods"]]
        if not hits:
            return
        best = max(hits, key=lambda s: (len(s[1]), len(s[0])))
        if not final and any(len(s[1]) > len(best[1]) and best[1] <= s[1] and s[0] <= g["mods"] for s in specs):
            if g["timer"]:
                g["timer"].cancel()
            g["waiting"] = True
            g["timer"] = threading.Timer(CHORD_WAIT, fire, (True,))
            g["timer"].daemon = True
            g["timer"].start()
            return
        g["done"] = True
        who = best[2]
        print(f"{NAMES[who]} hotkey pressed ({HOTKEY if who == 'karna' else HOTKEY_ARJUNA if who == 'arjuna' else HOTKEY_GEMMA})")
        on_hotkey(who)

    def press(key):
        if _SYNTHETIC_EVENT:
            return
        m = _mod_of(key)
        if m:
            held.add(m)
            return
        vk = _vk_of(key)
        if vk == VK_CAPITAL:
            return
        live_mods = _async_mods_down()
        held.clear()
        held.update(live_mods)
        if DEBUG:
            print("press", key, "vk=", vk, "held=", sorted(held))
        if vk is None:
            return
        if vk in held_keys:
            return
        held_keys.add(vk)
        g["keys"].add(vk)
        g["mods"] = set(held)
        fire(False)

    def release(key):
        if _SYNTHETIC_EVENT:
            return
        m = _mod_of(key)
        if m:
            held.discard(m)
            return
        vk = _vk_of(key)
        if vk == VK_CAPITAL:
            return
        held_keys.discard(vk)
        if not held_keys:
            held.clear()
            held.update(_async_mods_down())
        reset_if_idle()

    return keyboard.Listener(on_press=press, on_release=release)


def listen():
    with make_listener() as l:
        l.join()


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["now"]:
        run_once(args[1] if args[1:2] and args[1] in NAMES else "karna")
        sys.exit(0)
    if args[:1] == ["led"]:
        blink(int(args[1]) if len(args) > 1 else 2)
        sys.exit(0)
    print(f"Ready. Karna: {HOTKEY} ({MODEL}, Thinking: {THINK})   Arjuna: {HOTKEY_ARJUNA} ({OPENROUTER_MODEL})   Arjuna+Gemma: {HOTKEY_GEMMA} ({GEMMA_MODEL})")
    print("Ctrl+C to quit.")
    try:
        listen()
    except KeyboardInterrupt:
        print("\nbye")
