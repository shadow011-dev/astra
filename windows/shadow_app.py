#!/usr/bin/env python3
"""Astra system-tray app (Windows): hotkey -> screenshot -> AI -> Caps Lock LED blinks.
Karna = local Ollama, Arjuna = OpenRouter."""
import ctypes
import os
import threading
import time
import webbrowser

import pystray
from PIL import Image, ImageDraw

import mcq_blink as core
import popup
import settings_window
from config import CONFIG_FILE, VERSION, load_config, save_config
from ollama_util import base_url, has_model, ollama_running, pull_model

MB_OK = 0x00000000
MB_OKCANCEL = 0x00000001
MB_ICONINFORMATION = 0x00000040
IDOK = 1


def msgbox(title: str, text: str, ok_cancel: bool = False) -> bool:
    flags = (MB_OKCANCEL if ok_cancel else MB_OK) | MB_ICONINFORMATION
    res = ctypes.windll.user32.MessageBoxW(0, str(text), str(title), flags)
    return res == IDOK


def create_tray_icon() -> Image.Image:
    img = Image.new("RGBA", (64, 64), (24, 24, 28, 255))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((4, 4, 60, 60), radius=14, fill=(32, 32, 38, 255), outline=(212, 175, 55, 255), width=3)
    d.polygon([(32, 14), (16, 50), (24, 50), (32, 30), (40, 50), (48, 50)], fill=(255, 255, 255, 255))
    return img


class AstraApp:
    KEY_FIELDS = ("openrouter_api_key", "openrouter_api_key_2", "openrouter_api_key_3")

    def __init__(self):
        self.pull = {"active": False, "pct": None, "error": None, "done": False}
        self.listener = None
        popup.IN_APP = True
        self.icon = pystray.Icon("Astra", create_tray_icon(), "Astra", menu=self._build_menu())

    def notify(self, title: str, message: str):
        try:
            self.icon.notify(str(message)[:250], str(title)[:60])
        except Exception:
            pass

    # ---- dynamic menu text callbacks ----
    def _status_text(self, _item):
        p = self.pull
        if p["active"]:
            pct = "" if p["pct"] is None else f" {p['pct']}%"
            return f"Downloading {core.MODEL}...{pct}"
        if core.STATUS["state"] == "thinking":
            who = core.STATUS.get("who", "karna")
            hk = {"arjuna": core.HOTKEY_ARJUNA, "gemma": core.HOTKEY_GEMMA}.get(who, core.HOTKEY)
            return f"{core.NAMES[who]} thinking... (press {hk} to stop)"
        return f"Karna {core.HOTKEY} | Arjuna {core.HOTKEY_ARJUNA} | Gemma {core.HOTKEY_GEMMA}"

    def _answer_text(self, _item):
        ans = core.STATUS.get("answer")
        return f"Last answer: {ans}" if ans else "Last answer: -"

    def _conf_text(self, _item):
        c = core.STATUS.get("conf")
        return (f"Last confidence: {'~' if core.STATUS.get('conf_self') else ''}{c}%"
                if c is not None else "Last confidence: -")

    def _model_text(self, _item):
        m = core.STATUS.get("model")
        return f"Last model: {m}" if m else "Last model: -"

    def _error_text(self, _item):
        le = core.STATUS.get("last_error")
        return ("Last error: " + le[:70]) if le else "Last error: -"

    def _key_text(self, _item):
        n, cur, used = core.key_status()
        if n:
            return f"Arjuna API keys: {n} saved, using #{cur} ({used}/{core.load_config()['key_switch_after']})"
        return "Arjuna API key: NOT SET"

    def _build_menu(self):
        return pystray.Menu(
            pystray.MenuItem(self._status_text, None, enabled=False),
            pystray.MenuItem(self._answer_text, None, enabled=False),
            pystray.MenuItem(self._conf_text, None, enabled=False),
            pystray.MenuItem(self._model_text, None, enabled=False),
            pystray.MenuItem(self._error_text, self.show_error),
            pystray.MenuItem(self._key_text, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Run Karna now", self.run_now),
            pystray.MenuItem("Run Arjuna now", self.run_arjuna_now),
            pystray.MenuItem("Run Arjuna (Gemma 4 31B) now", self.run_gemma_now),
            pystray.MenuItem("Test LED", self.test_led),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(f"Version {VERSION}", None, enabled=False),
            pystray.MenuItem("Settings...", self.open_settings),
            pystray.MenuItem("Quit Astra", self.quit_app),
        )

    def _background_loop(self):
        try:
            self.listener = core.make_listener()
            self.listener.start()
        except SystemExit as e:
            msgbox("Bad hotkey in config", str(e))
        threading.Thread(target=self.check_setup, kwargs={"silent_ok": True}, daemon=True).start()

        last_state = None
        while self.icon.visible:
            p = self.pull
            cur_state = (core.STATUS["state"], core.STATUS.get("runs"), p["active"], p["pct"])
            if cur_state != last_state:
                last_state = cur_state
                if p["active"]:
                    self.icon.title = f"Astra: Downloading {core.MODEL}..."
                elif core.STATUS["state"] == "thinking":
                    who = core.STATUS.get("who", "karna")
                    self.icon.title = f"{core.NAMES[who]} thinking..."
                else:
                    self.icon.title = "Astra"
                try:
                    self.icon.update_menu()
                except Exception:
                    pass

            if core.STATUS.get("error"):
                err, core.STATUS["error"] = core.STATUS["error"], None
                self.notify(f"{core.STATUS.get('model') or 'Astra'} error", err)
            if p["done"]:
                p["done"] = False
                self.notify("Model ready", f"{core.MODEL} downloaded. You can use the hotkey now.")
            if p["error"]:
                err, p["error"] = p["error"], None
                self.notify("Model download failed", err)
            time.sleep(0.5)

    # ---- setup checks ----
    def check_setup(self, silent_ok=False):
        base = base_url(core.OLLAMA_URL)
        if not ollama_running(base):
            if msgbox(
                "Ollama isn't running",
                "Astra runs the AI model locally through Ollama.\n\n"
                "Click OK to open ollama.com/download, install and open it once, then click Check setup again.",
                ok_cancel=True,
            ):
                webbrowser.open("https://ollama.com/download")
            return False
        if not has_model(base, core.MODEL):
            if msgbox(
                "Download the AI model?",
                f"{core.MODEL} isn't installed yet (about 3.4 GB). Click OK to download it now.",
                ok_cancel=True,
            ):
                self.start_pull()
            return False
        if not silent_ok:
            msgbox("All set", f"Ollama and {core.MODEL} are ready.\nPress {core.HOTKEY} on a question.")
        return True

    def start_pull(self):
        if self.pull["active"]:
            return
        self.pull.update(active=True, pct=None, error=None, done=False)
        base = base_url(core.OLLAMA_URL)

        def work():
            try:
                def cb(status, pct):
                    if pct is not None:
                        self.pull["pct"] = pct
                pull_model(base, core.MODEL, cb)
                self.pull["done"] = True
            except Exception as e:
                self.pull["error"] = str(e)
            finally:
                self.pull["active"] = False

        threading.Thread(target=work, daemon=True).start()

    # ---- menu actions ----
    def show_error(self, _icon=None, _item=None):
        le = core.STATUS.get("last_error")
        if le:
            msgbox("Last error", le + "\n\n(full log: ~/.shadow/error.log)")

    def run_now(self, _icon=None, _item=None):
        core.on_hotkey("karna")

    def run_arjuna_now(self, _icon=None, _item=None):
        core.on_hotkey("arjuna")

    def run_gemma_now(self, _icon=None, _item=None):
        core.on_hotkey("gemma")

    def open_settings(self, _icon=None, _item=None):
        settings_window.show_settings(
            on_check_setup=self.check_setup,
            get_keys=self.get_keys,
            save_keys=self.save_keys,
            open_config=lambda: self.open_config(),
        )

    def get_keys(self):
        cfg = load_config()
        return [cfg[k] for k in self.KEY_FIELDS]

    def save_keys(self, keys):
        cfg = load_config()
        for field, v in zip(self.KEY_FIELDS, keys):
            cfg[field] = v.strip()
        save_config(cfg)
        self.notify("Arjuna", f"{sum(1 for v in keys if v.strip())} API key(s) saved. Model: {core.OPENROUTER_MODEL}")

    def test_led(self, _icon=None, _item=None):
        threading.Thread(target=core.blink, args=(3,), daemon=True).start()

    def open_config(self, _icon=None, _item=None):
        load_config()
        os.startfile(str(CONFIG_FILE))

    def quit_app(self, _icon=None, _item=None):
        if self.listener:
            try:
                self.listener.stop()
            except Exception:
                pass
        self.icon.stop()

    def run(self):
        self.icon.run(setup=lambda icon: (setattr(icon, "visible", True), self._background_loop()))


if __name__ == "__main__":
    AstraApp().run()
