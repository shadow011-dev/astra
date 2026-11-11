"""Settings window for the Astra system-tray app (Windows Tkinter)."""
import threading
import tkinter as tk
from tkinter import ttk

_LOCK = threading.Lock()
_OPEN = False


def show_settings(on_check_setup, get_keys, save_keys, open_config):
    """Open the settings window on its own UI thread."""
    global _OPEN
    with _LOCK:
        if _OPEN:
            return
        _OPEN = True

    def _run():
        global _OPEN
        try:
            root = tk.Tk()
            root.title("Astra Settings")
            W, H = 420, 340
            sw = root.winfo_screenwidth()
            sh = root.winfo_screenheight()
            root.geometry(f"{W}x{H}+{(sw - W) // 2}+{(sh - H) // 2}")
            root.resizable(False, False)
            root.attributes("-topmost", True)

            pad = 18
            frame = ttk.Frame(root, padding=pad)
            frame.pack(fill="both", expand=True)

            ttk.Label(frame, text="Setup", font=("Segoe UI", 10, "bold")).pack(anchor="w")
            ttk.Button(
                frame,
                text="Check setup",
                width=18,
                command=lambda: threading.Thread(target=on_check_setup, daemon=True).start(),
            ).pack(anchor="w", pady=(6, 14))

            ttk.Label(frame, text="OpenRouter API keys (Arjuna)", font=("Segoe UI", 10, "bold")).pack(anchor="w")
            ttk.Label(
                frame,
                text="One key is enough. With more, Arjuna moves to the next key after 40 requests.",
                wraplength=W - 2 * pad,
                font=("Segoe UI", 8),
            ).pack(anchor="w", pady=(2, 8))

            saved = (list(get_keys()) + ["", "", ""])[:3]
            entries = []
            for i in range(3):
                row = ttk.Frame(frame)
                row.pack(fill="x", pady=3)
                ttk.Label(row, text=f"Key {i + 1}", width=8).pack(side="left")
                ent = ttk.Entry(row)
                ent.insert(0, saved[i])
                ent.pack(side="left", fill="x", expand=True)
                entries.append(ent)

            status_var = tk.StringVar(value="")
            status_lbl = ttk.Label(frame, textvariable=status_var, font=("Segoe UI", 8))
            status_lbl.pack(anchor="w", pady=(8, 4))

            def do_save():
                vals = [e.get().strip() for e in entries]
                save_keys(vals)
                n = sum(1 for v in vals if v)
                status_var.set(f"Saved {n} key(s)." if n else "No keys saved.")

            btn_row = ttk.Frame(frame)
            btn_row.pack(fill="x", side="bottom", pady=(6, 0))
            ttk.Button(btn_row, text="Open config file", command=open_config).pack(side="left")
            ttk.Button(btn_row, text="Save keys", command=do_save).pack(side="right")

            root.mainloop()
        finally:
            with _LOCK:
                _OPEN = False

    threading.Thread(target=_run, daemon=True).start()
