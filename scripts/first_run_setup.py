#!/usr/bin/env python3
"""First-run setup UI for downloading Meera's local model."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import threading
import tempfile
import urllib.request

import gi  # type: ignore

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # type: ignore  # noqa: E402


def _verify_sha(path: str, expected_sha: str) -> None:
    if not expected_sha:
        return

    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    actual = digest.hexdigest()
    if actual != expected_sha:
        raise RuntimeError(f"SHA256 mismatch: expected {expected_sha}, got {actual}")


class SetupWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application, model_name: str):
        super().__init__(application=app, title="Setting up Meera")
        self._model_name = model_name
        self._key_controller: Gtk.EventControllerKey | None = None
        self.set_default_size(440, 120)
        self.set_resizable(False)

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.box.set_margin_top(18)
        self.box.set_margin_bottom(18)
        self.box.set_margin_start(18)
        self.box.set_margin_end(18)
        self.set_child(self.box)

        message = Gtk.Label(
            label=(
                "Meera is being set up with a local AI model. "
                "It should be ready soon. Thanks for your patience."
            )
        )
        message.set_wrap(True)
        message.set_xalign(0)
        self.message = message
        self.box.append(message)

        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)
        self.progress.set_text("Preparing download...")
        self.box.append(self.progress)

        self.detail = Gtk.Label(label=model_name)
        self.detail.set_xalign(0)
        self.detail.add_css_class("dim-label")
        self.box.append(self.detail)
        self.button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.button_box.set_halign(Gtk.Align.END)
        self.box.append(self.button_box)

    def set_progress(self, downloaded: int, total: int) -> bool:
        if total > 0:
            fraction = min(downloaded / total, 1.0)
            self.progress.set_fraction(fraction)
            self.progress.set_text(f"{fraction * 100:.0f}%")
            self.detail.set_text(
                f"{self._model_name} - {downloaded / (1024 ** 2):.0f} "
                f"of {total / (1024 ** 2):.0f} MB"
            )
        else:
            self.progress.pulse()
            self.progress.set_text("Downloading...")
            self.detail.set_text(
                f"{self._model_name} - {downloaded / (1024 ** 2):.0f} MB"
            )
        return False

    def set_status(self, text: str) -> bool:
        self.detail.set_text(text)
        return False

    def set_message(self, text: str) -> None:
        self.message.set_text(text)

    def clear_buttons(self) -> None:
        child = self.button_box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.button_box.remove(child)
            child = next_child

    def add_button(self, label: str, callback) -> Gtk.Button:
        button = Gtk.Button(label=label)
        button.connect("clicked", callback)
        self.button_box.append(button)
        return button

    def show_progress(self) -> None:
        self.progress.set_visible(True)
        self.detail.set_visible(True)

    def hide_progress(self) -> None:
        self.progress.set_visible(False)
        self.detail.set_visible(False)

    def set_key_capture(self, callback) -> None:
        if self._key_controller is not None:
            self.remove_controller(self._key_controller)
        controller = Gtk.EventControllerKey()
        controller.connect("key-pressed", callback)
        self.add_controller(controller)
        self._key_controller = controller

    def clear_key_capture(self) -> None:
        if self._key_controller is not None:
            self.remove_controller(self._key_controller)
            self._key_controller = None


def _download(
    window: SetupWindow,
    app: Gtk.Application,
    url: str,
    dest: str,
    expected_sha: str,
    exit_code: list[int],
) -> None:
    part = dest + ".part"
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        request = urllib.request.Request(url, headers={"User-Agent": "Meera installer"})
        with urllib.request.urlopen(request, timeout=60) as response:
            total = int(response.headers.get("Content-Length") or 0)
            downloaded = 0
            with open(part, "wb") as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                    downloaded += len(chunk)
                    GLib.idle_add(window.set_progress, downloaded, total)

        _verify_sha(part, expected_sha)
        os.replace(part, dest)
        GLib.idle_add(window.set_status, "Local model download complete.")
    except Exception as exc:  # noqa: BLE001 - show setup failure to user
        exit_code[0] = 1
        try:
            if os.path.exists(part):
                os.remove(part)
        except OSError:
            pass
        GLib.idle_add(window.set_status, f"Setup failed: {exc}")
        GLib.timeout_add(3500, app.quit)
        return

    GLib.timeout_add(400, app.quit)


def _desktop_file_path() -> str:
    xdg_data_home = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    return os.path.join(xdg_data_home, "applications", "local.meera.Meera.desktop")


def _autostart_file_path() -> str:
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return os.path.join(xdg_config_home, "autostart", "meera.desktop")


def _enable_autostart(launcher: str) -> None:
    autostart_file = _autostart_file_path()
    os.makedirs(os.path.dirname(autostart_file), exist_ok=True)
    desktop_file = _desktop_file_path()
    if os.path.isfile(desktop_file):
        shutil.copyfile(desktop_file, autostart_file)
        return
    with open(autostart_file, "w", encoding="utf-8") as handle:
        handle.write(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=Meera\n"
            "Comment=Local GNOME AI Assistant\n"
            f"Exec={launcher}\n"
            "Icon=meera\n"
            "Terminal=false\n"
            "Categories=Utility;GTK;\n"
            "StartupNotify=true\n"
        )


def _keyboard_helper_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "keyboard_shortcut.py")


def _shortcut_modifiers(state: Gdk.ModifierType) -> Gdk.ModifierType:
    return state & (
        Gdk.ModifierType.CONTROL_MASK
        | Gdk.ModifierType.SHIFT_MASK
        | Gdk.ModifierType.ALT_MASK
        | Gdk.ModifierType.SUPER_MASK
        | Gdk.ModifierType.HYPER_MASK
        | Gdk.ModifierType.META_MASK
    )


def _set_shortcut(binding: str, launcher: str) -> tuple[bool, str]:
    helper = _keyboard_helper_path()
    result = subprocess.run(
        [sys.executable, helper, "set", binding, launcher],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode == 0:
        return True, f"Keyboard shortcut set to {binding}."
    message = (result.stderr or result.stdout or "Could not set keyboard shortcut.").strip()
    return False, message


def _run_full_setup(
    window: SetupWindow,
    app: Gtk.Application,
    command: list[str],
    progress_file: str,
    exit_code: list[int],
    setup_done: list[bool],
) -> None:
    try:
        env = {
            **os.environ,
            "MEERA_SUPPRESS_SETUP_UI": "1",
            "MEERA_SETUP_PROGRESS_FILE": progress_file,
        }
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
        assert process.stdout is not None
        for _raw_line in process.stdout:
            # Keep setup details out of the UI; only Qwen byte progress drives it.
            pass
        exit_code[0] = process.wait()
        if exit_code[0] == 0:
            setup_done[0] = True
            GLib.idle_add(window.set_status, f"{window._model_name} - ready")
            GLib.idle_add(window.progress.set_fraction, 1.0)
            GLib.idle_add(window.progress.set_text, "100%")
            GLib.timeout_add(500, app.quit)
        else:
            GLib.idle_add(
                window.set_status,
                f"Setup failed with exit code {exit_code[0]}. Run 'meera logs' for details.",
            )
            GLib.timeout_add(4000, app.quit)
    except Exception as exc:  # noqa: BLE001 - show setup failure to user
        exit_code[0] = 1
        GLib.idle_add(window.set_status, f"Setup failed: {exc}")
        GLib.timeout_add(4000, app.quit)


def _poll_progress_file(window: SetupWindow, progress_file: str) -> bool:
    try:
        with open(progress_file, encoding="utf-8") as handle:
            raw = handle.read().strip()
    except OSError:
        return True

    if not raw:
        return True

    try:
        downloaded_s, total_s = raw.split(" ", 1)
        downloaded = int(downloaded_s)
        total = int(total_s)
    except (ValueError, TypeError):
        return True

    window.set_progress(downloaded, total)
    return True


def _run_full_setup_ui(command: list[str]) -> int:
    exit_code = [0]
    setup_done = [False]
    app = Gtk.Application(application_id="local.meera.Setup")
    progress_fd, progress_file = tempfile.mkstemp(prefix="meera-qwen-progress-")
    os.close(progress_fd)
    launcher = command[0] if command else "meera"

    def start_model_setup(window: SetupWindow) -> None:
        window.clear_key_capture()
        window.clear_buttons()
        window.show_progress()
        window.set_message(
            "Meera is being set up with a local AI model. "
            "It should be ready soon. Thanks for your patience."
        )
        window.progress.set_fraction(0.0)
        window.progress.set_text("Waiting for model download...")
        GLib.timeout_add(250, _poll_progress_file, window, progress_file)
        threading.Thread(
            target=_run_full_setup,
            args=(window, app, command, progress_file, exit_code, setup_done),
            daemon=True,
        ).start()

    def show_shortcut_step(window: SetupWindow) -> None:
        window.clear_key_capture()
        window.clear_buttons()
        window.hide_progress()
        window.set_message("Would you like to set a keyboard shortcut to open Meera?")
        window.add_button("Skip", lambda _button: start_model_setup(window))

        def begin_capture(_button) -> None:
            window.clear_buttons()
            window.set_message("Press the keyboard shortcut you want to use for Meera.")
            window.detail.set_visible(True)
            window.detail.set_text("Use at least one modifier key, such as Ctrl, Alt, or Super.")

            def on_key_pressed(_controller, keyval, _keycode, state) -> bool:
                modifiers = _shortcut_modifiers(state)
                if not Gtk.accelerator_valid(keyval, modifiers):
                    window.detail.set_text("That shortcut is not valid. Try another one.")
                    return True
                binding = Gtk.accelerator_name(keyval, modifiers)
                ok, message = _set_shortcut(binding, launcher)
                if ok:
                    window.detail.set_text(message)
                    GLib.timeout_add(700, lambda: (start_model_setup(window), False)[1])
                else:
                    window.detail.set_text(f"{message} Try a different shortcut, or skip.")
                    window.clear_buttons()
                    window.add_button("Skip", lambda _button: start_model_setup(window))
                return True

            window.set_key_capture(on_key_pressed)

        window.add_button("Set keyboard shortcut", begin_capture)

    def show_autostart_step(window: SetupWindow) -> None:
        window.clear_buttons()
        window.hide_progress()
        window.set_message("Start Meera automatically when you log in?")
        window.detail.set_visible(False)
        window.add_button("No", lambda _button: show_shortcut_step(window))

        def enable_and_continue(_button) -> None:
            try:
                _enable_autostart(launcher)
            except OSError:
                pass
            show_shortcut_step(window)

        window.add_button("Yes", enable_and_continue)

    def on_activate(app: Gtk.Application) -> None:
        window = SetupWindow(app, "Qwen3.5-2B-Q4_K_M.gguf")

        def on_close(_window) -> bool:
            if not setup_done[0] and exit_code[0] == 0:
                exit_code[0] = 130
            return False

        window.connect("close-request", on_close)
        window.present()
        show_autostart_step(window)

    app.connect("activate", on_activate)
    try:
        app.run(None)
        return exit_code[0]
    finally:
        try:
            os.remove(progress_file)
        except OSError:
            pass


def main(argv: list[str]) -> int:
    if len(argv) >= 3 and argv[1] == "--full-setup":
        return _run_full_setup_ui(argv[2:])

    if len(argv) != 5:
        print(
            "Usage: first_run_setup.py URL DEST SHA256 MODEL_NAME\n"
            "   or: first_run_setup.py --full-setup COMMAND [ARGS...]",
            file=sys.stderr,
        )
        return 2

    url, dest, expected_sha, model_name = argv[1:5]
    exit_code = [0]

    app = Gtk.Application(application_id="local.meera.Setup")

    def on_activate(app: Gtk.Application) -> None:
        window = SetupWindow(app, model_name)
        window.present()
        threading.Thread(
            target=_download,
            args=(window, app, url, dest, expected_sha, exit_code),
            daemon=True,
        ).start()

    app.connect("activate", on_activate)
    app.run(None)
    return exit_code[0]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
