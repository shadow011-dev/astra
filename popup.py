"""Small always-on-top popup in the top-right corner of the screen (macOS).

In the menu-bar app it runs on the app's own main thread (IN_APP = True).
From the plain script there is no GUI loop, so it runs `python popup.py "text" secs`
as a tiny helper process instead.
"""
import os
import subprocess
import sys
import threading

IN_APP = False   # set to True by the menu-bar app
_KEEP = []       # keeps window objects alive while shown


def _show_window(text, seconds=1.0):
    """Create the popup window. Must run on the main thread."""
    from AppKit import NSColor, NSFont, NSMakeRect, NSScreen, NSTextField, NSWindow
    from PyObjCTools import AppHelper

    vf = NSScreen.mainScreen().visibleFrame()          # area below the menu bar
    w = max(140, min(460, 11 * len(text) + 48))
    h = 46
    x = vf.origin.x + vf.size.width - w - 12
    y = vf.origin.y + vf.size.height - h - 12

    win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(x, y, w, h), 0, 2, False)           # borderless, buffered
    win.setLevel_(1000)                                # above normal and full-screen windows
    win.setOpaque_(False)
    win.setBackgroundColor_(NSColor.clearColor())
    win.setIgnoresMouseEvents_(True)                   # clicks pass through
    win.setHasShadow_(True)
    win.setReleasedWhenClosed_(False)
    win.setCollectionBehavior_((1 << 0) | (1 << 8))    # all Spaces + over full-screen apps

    view = win.contentView()
    try:
        view.setWantsLayer_(True)
        view.layer().setCornerRadius_(10.0)
        view.layer().setBackgroundColor_(NSColor.colorWithCalibratedWhite_alpha_(0.10, 0.92).CGColor())
    except Exception:
        pass

    label = NSTextField.alloc().initWithFrame_(NSMakeRect(8, 10, w - 16, h - 20))
    label.setStringValue_(text)
    label.setBezeled_(False)
    label.setDrawsBackground_(False)
    label.setEditable_(False)
    label.setSelectable_(False)
    label.setTextColor_(NSColor.whiteColor())
    label.setFont_(NSFont.boldSystemFontOfSize_(18))
    label.setAlignment_(1)                             # centered
    view.addSubview_(label)

    win.orderFrontRegardless()
    _KEEP.append(win)

    def close():
        win.orderOut_(None)
        if win in _KEEP:
            _KEEP.remove(win)

    threading.Timer(seconds, lambda: AppHelper.callAfter(close)).start()


def show_popup(text, seconds=1.0):
    text = " ".join(str(text).split())[:60]
    if not text:
        return
    if IN_APP:
        from PyObjCTools import AppHelper
        AppHelper.callAfter(_show_window, text, seconds)
    else:
        subprocess.Popen([sys.executable, os.path.abspath(__file__), text, str(seconds)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    from AppKit import NSApplication
    from PyObjCTools import AppHelper

    msg = sys.argv[1] if len(sys.argv) > 1 else "Shadow"
    secs = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(1)                        # accessory: no Dock icon
    _show_window(msg, secs)
    threading.Timer(secs + 0.3, lambda: AppHelper.callAfter(AppHelper.stopEventLoop)).start()
    AppHelper.runEventLoop()
