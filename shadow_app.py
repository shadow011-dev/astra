#!/usr/bin/env python3
"""Astra menu-bar app: hotkey -> screenshot -> AI -> Caps Lock LED blinks.
Karna = local Ollama, Arjuna = OpenRouter."""
import subprocess
import threading
import webbrowser

import rumps

import mcq_blink as core
import popup
import settings_window
from config import CONFIG_FILE, VERSION, load_config, save_config
from ollama_util import base_url, has_model, ollama_running, pull_model

PANES = {
    "Screen Recording": "Privacy_ScreenCapture",
    "Accessibility": "Privacy_Accessibility",
    "Input Monitoring": "Privacy_ListenEvent",
}


def open_pane(name):
    subprocess.run(["open", f"x-apple.systempreferences:com.apple.preference.security?{PANES[name]}"])


def notify(title, message):
    try:
        rumps.notification("Astra", title, message)
    except Exception:
        pass


class AstraApp(rumps.App):
    def __init__(self):
        super().__init__("Astra", title="Astra", quit_button=None)
        self.pull = {"active": False, "pct": None, "error": None, "done": False}
        self.ticks = 0
        self.screen_ok = True
        self.listener = None
        popup.IN_APP = True  # popups run on this app's main thread

        self.status_item = rumps.MenuItem("Starting...")
        self.answer_item = rumps.MenuItem("Last answer: -")
        self.conf_item = rumps.MenuItem("Last confidence: -")
        self.model_item = rumps.MenuItem("Last model: -")
        self.key_item = rumps.MenuItem("Arjuna API key: -")
        self.error_item = rumps.MenuItem("Last error: -", callback=self.show_error)
        perms = rumps.MenuItem("Permissions")
        for name in PANES:
            perms.add(rumps.MenuItem(f"Open {name} settings", callback=self.make_pane_cb(name)))
        self.menu = [
            self.status_item,
            self.answer_item,
            self.conf_item,
            self.model_item,
            self.error_item,
            self.key_item,
            None,
            rumps.MenuItem("Run Karna now", callback=self.run_now),
            rumps.MenuItem("Run Arjuna now", callback=self.run_arjuna_now),
            rumps.MenuItem("Run Arjuna (Gemma 4 31B) now", callback=self.run_gemma_now),
            rumps.MenuItem("Test LED", callback=self.test_led),
            None,
            perms,
            None,
            rumps.MenuItem(f"Version {VERSION}"),
            rumps.MenuItem("Settings...", callback=self.open_settings),
            rumps.MenuItem("Quit Astra", callback=self.quit_app),
        ]
        self.tick_timer = rumps.Timer(self.tick, 0.5)
        self.tick_timer.start()
        self.start_timer = rumps.Timer(self.startup, 1)
        self.start_timer.start()

    # ---- startup ----
    def startup(self, timer):
        timer.stop()
        try:
            self.listener = core.make_listener()
            self.listener.start()
        except SystemExit as e:
            rumps.alert("Bad hotkey in config", str(e))
        if not core.have_screen_access():
            core.request_screen_access()
        self.check_setup(silent_ok=True)

    # ---- status in the menu bar ----
    def tick(self, _):
        self.ticks += 1
        if self.ticks % 10 == 1:
            self.screen_ok = core.have_screen_access()
        p = self.pull
        if p["active"]:
            pct = "" if p["pct"] is None else f" {p['pct']}%"
            self.title = "Astra dl"
            self.status_item.title = f"Downloading {core.MODEL}...{pct}"
        elif core.STATUS["state"] == "thinking":
            who = core.STATUS.get("who", "karna")
            hk = {"arjuna": core.HOTKEY_ARJUNA, "gemma": core.HOTKEY_GEMMA}.get(who, core.HOTKEY)
            self.title = f"{core.NAMES[who]} ..."
            self.status_item.title = f"{core.NAMES[who]} thinking... (press {hk} to stop)"
        else:
            self.title = "Astra"
            if not self.screen_ok:
                self.status_item.title = "Needs Screen Recording permission"
            else:
                self.status_item.title = f"Karna {core.HOTKEY} | Arjuna {core.HOTKEY_ARJUNA} | Gemma {core.HOTKEY_GEMMA}"
        ans = core.STATUS.get("answer")
        self.answer_item.title = f"Last answer: {ans}" if ans else "Last answer: -"
        c = core.STATUS.get("conf")
        self.conf_item.title = (f"Last confidence: {'~' if core.STATUS.get('conf_self') else ''}{c}%"
                                if c is not None else "Last confidence: -")
        m = core.STATUS.get("model")
        self.model_item.title = f"Last model: {m}" if m else "Last model: -"
        n, cur, used = core.key_status()
        if n:
            self.key_item.title = (f"Arjuna API keys: {n} saved, using #{cur} "
                                   f"({used}/{core.load_config()['key_switch_after']})")
        else:
            self.key_item.title = "Arjuna API key: NOT SET"
        le = core.STATUS.get("last_error")
        self.error_item.title = ("Last error: " + le[:70]) if le else "Last error: -"
        if core.STATUS.get("error"):
            err, core.STATUS["error"] = core.STATUS["error"], None
            notify(f"{core.STATUS.get('model') or 'Astra'} error", err)
        if p["done"]:
            p["done"] = False
            notify("Model ready", f"{core.MODEL} downloaded. You can use the hotkey now.")
        if p["error"]:
            err, p["error"] = p["error"], None
            notify("Model download failed", err)

    # ---- setup checks ----
    def check_setup(self, silent_ok=False):
        base = base_url(core.OLLAMA_URL)
        if not ollama_running(base):
            if rumps.alert(
                title="Ollama isn't running",
                message="Astra runs the AI model locally through Ollama.\n\n"
                        "Install it from ollama.com/download, open it once, then choose Check setup again.",
                ok="Open download page", cancel="Later",
            ):
                webbrowser.open("https://ollama.com/download")
            return False
        if not has_model(base, core.MODEL):
            if rumps.alert(
                title="Download the AI model?",
                message=f"{core.MODEL} isn't installed yet (about 3.4 GB). Download it now?",
                ok="Download", cancel="Later",
            ):
                self.start_pull()
            return False
        if not silent_ok:
            rumps.alert("All set", f"Ollama and {core.MODEL} are ready.\nPress {core.HOTKEY} on a question.")
        return True

    def on_check_setup(self, _):
        self.check_setup()

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
    def show_error(self, _):
        le = core.STATUS.get("last_error")
        if le:
            rumps.alert("Last error", le + "\n\n(full log: ~/.shadow/error.log)")

    def run_now(self, _):
        core.on_hotkey("karna")

    def run_arjuna_now(self, _):
        core.on_hotkey("arjuna")

    def run_gemma_now(self, _):
        core.on_hotkey("gemma")

    def open_settings(self, _):
        settings_window.show_settings(
            on_check_setup=self.check_setup,
            get_keys=self.get_keys, save_keys=self.save_keys, open_config=lambda: self.open_config(None))

    KEY_FIELDS = ("openrouter_api_key", "openrouter_api_key_2", "openrouter_api_key_3")

    def get_keys(self):
        cfg = load_config()
        return [cfg[k] for k in self.KEY_FIELDS]

    def save_keys(self, keys):
        cfg = load_config()
        for field, v in zip(self.KEY_FIELDS, keys):
            cfg[field] = v.strip()
        save_config(cfg)
        notify("Arjuna", f"{sum(1 for v in keys if v.strip())} API key(s) saved. Model: {core.OPENROUTER_MODEL}")

    def test_led(self, _):
        threading.Thread(target=core.blink, args=(3,), daemon=True).start()

    def make_pane_cb(self, name):
        return lambda _sender: open_pane(name)

    def open_config(self, _):
        load_config()  # make sure the file exists
        subprocess.run(["open", "-t", str(CONFIG_FILE)])

    def quit_app(self, _):
        rumps.quit_application()


if __name__ == "__main__":
    AstraApp().run()
