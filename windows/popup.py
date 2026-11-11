"""Small always-on-top click-through popup in the top-right corner of the screen (Windows)."""
import ctypes
import os
import subprocess
import sys
import threading
import tkinter as tk

IN_APP = False  # set to True by the tray app

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000


def _show_window(text: str, seconds: float = 1.0):
    root = tk.Tk()
    root.withdraw()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.92)
    root.configure(bg="#1a1a1a")

    w = max(140, min(460, 11 * len(text) + 48))
    h = 46
    screen_w = root.winfo_screenwidth()
    x = screen_w - w - 16
    y = 16
    root.geometry(f"{w}x{h}+{x}+{y}")

    label = tk.Label(
        root,
        text=text,
        fg="white",
        bg="#1a1a1a",
        font=("Segoe UI", 14, "bold"),
        justify="center",
    )
    label.pack(expand=True, fill="both", padx=8, pady=6)

    root.update_idletasks()
    try:
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
        ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(
            hwnd,
            GWL_EXSTYLE,
            ex_style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
        )
    except Exception:
        pass

    root.deiconify()
    root.after(int(max(0.3, float(seconds)) * 1000), root.destroy)
    root.mainloop()


def show_popup(text, seconds=1.0):
    text = " ".join(str(text).split())[:60]
    if not text:
        return
    if getattr(sys, "frozen", False) or IN_APP:
        threading.Thread(target=_show_window, args=(text, float(seconds)), daemon=True).start()
    else:
        subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), text, str(seconds)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
        )


if __name__ == "__main__":
    msg = sys.argv[1] if len(sys.argv) > 1 else "Shadow"
    secs = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    _show_window(msg, secs)
