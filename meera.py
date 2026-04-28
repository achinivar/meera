#!/usr/bin/env python3

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from ui.window import MeeraWindow


def main():
    GLib.set_application_name("Meera")
    app = Gtk.Application(application_id="local.meera.Meera")

    def on_activate(app):
        win = getattr(app, "_meera_window", None)
        if win is None:
            win = MeeraWindow()
            win.set_application(app)
            app._meera_window = win

        win.present()

        # Focus the multi-line input box when the window opens
        win.input_view.grab_focus()

    app.connect("activate", on_activate)
    app.run(None)


if __name__ == "__main__":
    main()

