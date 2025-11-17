#!/usr/bin/env python3

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ui.window import MeeraWindow


def main():
    app = Gtk.Application()

    def on_activate(app):
        win = MeeraWindow()
        win.set_application(app)
        win.present()

        # Focus the multi-line input box when the window opens
        win.input_view.grab_focus()

    app.connect("activate", on_activate)
    app.run(None)


if __name__ == "__main__":
    main()

