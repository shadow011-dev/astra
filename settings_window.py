"""Settings window for the Astra menu-bar app (AppKit, runs on the app's main thread)."""
import objc
from AppKit import (NSApplication, NSBackingStoreBuffered, NSBezelStyleRounded, NSButton, NSFont,
                    NSMakeRect, NSTextField, NSWindow)
from Foundation import NSObject

_STYLE = 1 | 2 | 8      # titled | closable | miniaturizable
_WIN = {"window": None, "controller": None}


class _Controller(NSObject):
    def initWithActions_(self, actions):
        self = objc.super(_Controller, self).init()
        if self is None:
            return None
        self.actions = actions
        return self

    @objc.IBAction
    def clicked_(self, sender):
        fn = self.actions.get(int(sender.tag()))
        if fn:
            fn()


class _Closer(NSObject):
    def windowWillClose_(self, _n):
        _WIN["window"] = None
        _WIN["controller"] = None


def _label(view, text, x, y, w, h=20, bold=False, size=13):
    f = NSTextField.alloc().initWithFrame_(NSMakeRect(x, y, w, h))
    f.setStringValue_(text)
    f.setBezeled_(False)
    f.setDrawsBackground_(False)
    f.setEditable_(False)
    f.setSelectable_(False)
    f.setFont_(NSFont.boldSystemFontOfSize_(size) if bold else NSFont.systemFontOfSize_(size))
    view.addSubview_(f)
    return f


def _button(view, ctl, title, x, y, w, tag):
    b = NSButton.alloc().initWithFrame_(NSMakeRect(x, y, w, 28))
    b.setTitle_(title)
    b.setBezelStyle_(NSBezelStyleRounded)
    b.setTag_(tag)
    b.setTarget_(ctl)
    b.setAction_("clicked:")
    view.addSubview_(b)
    return b


def show_settings(on_check_setup, get_keys, save_keys, open_config):
    """Open (or focus) the settings window."""
    app = NSApplication.sharedApplication()
    if _WIN["window"] is not None:
        _WIN["window"].makeKeyAndOrderFront_(None)
        app.activateIgnoringOtherApps_(True)
        return

    W, H, M = 400, 360, 20
    win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, W, H), _STYLE, NSBackingStoreBuffered, False)
    win.setTitle_("Astra Settings")
    win.setReleasedWhenClosed_(False)
    win.center()
    view = win.contentView()

    saved = (list(get_keys()) + ["", "", ""])[:3]
    status = _label(view, "", M, 62, W - 2 * M, 18, size=11)

    def do_save():
        vals = [f.stringValue().strip() for f in key_fields]
        save_keys(vals)
        n = sum(1 for v in vals if v)
        status.setStringValue_(f"Saved {n} key(s)." if n else "No keys saved.")

    actions = {1: on_check_setup, 2: do_save, 3: open_config}
    ctl = _Controller.alloc().initWithActions_(actions)

    y = H - 44
    _label(view, "Setup", M, y, W - 2 * M, bold=True)
    _button(view, ctl, "Check setup", M, y - 34, 140, 1)

    y -= 50
    _label(view, "OpenRouter API keys (Arjuna)", M, y, W - 2 * M, bold=True)
    _label(view, "One key is enough. With more, Arjuna moves to the next key after 40 requests.",
           M, y - 36, W - 2 * M, 30, size=11)
    key_fields = []
    for i in range(3):
        f = NSTextField.alloc().initWithFrame_(NSMakeRect(M + 56, y - 66 - i * 30, W - 2 * M - 56, 24))
        f.setStringValue_(saved[i])
        f.setPlaceholderString_("sk-or-..." + ("" if i == 0 else " (optional)"))
        view.addSubview_(f)
        _label(view, f"Key {i + 1}", M, y - 64 - i * 30, 52)
        key_fields.append(f)
    _button(view, ctl, "Save keys", W - M - 100, 84, 100, 2)
    _button(view, ctl, "Open config file", M, 20, 140, 3)

    closer = _Closer.alloc().init()   # closing the window lets it be reopened
    win.setDelegate_(closer)

    _WIN.update(window=win, controller=(ctl, closer))
    win.makeKeyAndOrderFront_(None)
    app.activateIgnoringOtherApps_(True)
