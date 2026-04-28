import json
import os
import re
import shutil
import subprocess
import gi  # type: ignore
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gio", "2.0")
from gi.repository import Gtk, GLib, Gdk, Pango, Gio  # type: ignore

# Try to import Adw for theme detection
try:
    gi.require_version("Adw", "1")
    from gi.repository import Adw
    ADW_AVAILABLE = True
except (ValueError, ImportError):
    ADW_AVAILABLE = False

import threading
from retrieval import get_index
from inference import stream_llm
from history import save_session, list_sessions, load_session

from agent import (
    TOOL_FEEDBACK_PREFIX,
    TOOL_MEMORY_PREFIX,
    agent_tools_enabled,
    run_agent_turn,
)
from tools.runner import detect_distro


_LEGACY_TOOL_CALL_RE = re.compile(r'\{\s*"tool"\s*:\s*"[A-Za-z_][A-Za-z0-9_]*"', re.DOTALL)


def _looks_like_legacy_tool_call(content: str) -> bool:
    """True for old Phase 3 sessions where assistant messages stored raw {"tool": ...} JSON."""
    if not isinstance(content, str) or not content.strip():
        return False
    return _LEGACY_TOOL_CALL_RE.search(content) is not None


class MeeraWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Meera")
        self.set_default_size(550, 800)
        self._css_provider = Gtk.CssProvider()
        self._css_provider_installed = False

        # State for streaming
        self.is_streaming = False
        self.cancel_stream = False
        
        # Conversation history for context
        self.conversation_history = []
        self._streaming_message_active = False
        self._streaming_body_start_mark = None
        self._streaming_render_buffer = ""
        self._streaming_render_dirty = False
        self._streaming_refresh_active = False
        self._typing_start_mark = None
        self._typing_end_mark = None

        # Base system identity (Phase 3 augments with tools catalog when MEERA_AGENT_TOOLS is on).
        self._system_identity = (
            "You are Meera, an AI Puppy for Linux desktops. You are helpful, playful, and designed to "
            "assist users with their tasks and questions on Linux desktops, software recommendations, "
            "configuring settings and debugging issues. You are also brief and to the point in your responses. "
            "If you are uncertain about an answer or don't have enough information, politely refuse to answer and state your limitations"
            "and suggest the user to ask a different question. You are not a general purpose AI, you are specific to Linux desktops."
        )

        # Detect theme and set up styling
        self.is_dark_theme = self._detect_theme()
        
        # ---------- CSS (for bubbles & transparent chat bg) ----------
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        bg_path = os.path.join(base_dir, "assets", "meera_bg.png")

        self._setup_theme_styling()

        # ---------- HEADER BAR (Titlebar) ----------
        header_bar = Gtk.HeaderBar()
        header_bar.set_show_title_buttons(True)
        
        # Menu button
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_tooltip_text("Menu")
        
        # Create popover (using regular Popover instead of PopoverMenu)
        popover = Gtk.Popover()
        popover.set_has_arrow(False)
        menu_button.set_popover(popover)
        
        # Create menu box
        menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        menu_box.set_margin_top(6)
        menu_box.set_margin_bottom(6)
        menu_box.set_margin_start(6)
        menu_box.set_margin_end(6)
        popover.set_child(menu_box)
        
        # New Chat menu item
        new_chat_item = Gtk.Button(label="New Chat")
        new_chat_item.connect("clicked", lambda btn: (popover.popdown(), self._on_new_chat_clicked()))
        new_chat_item.set_halign(Gtk.Align.FILL)
        menu_box.append(new_chat_item)
        
        # Chat History menu item
        history_item = Gtk.Button(label="Chat History")
        history_item.connect("clicked", lambda btn: (popover.popdown(), self._on_history_clicked()))
        history_item.set_halign(Gtk.Align.FILL)
        menu_box.append(history_item)

        # Auto-start toggle menu item
        self.autostart_item = Gtk.Button(label="")
        self.autostart_item.connect(
            "clicked",
            lambda btn: (popover.popdown(), self._on_autostart_toggle_clicked()),
        )
        self.autostart_item.set_halign(Gtk.Align.FILL)
        menu_box.append(self.autostart_item)
        self._refresh_autostart_menu_label()

        shortcut_item = Gtk.Button(label="Keyboard Shortcut")
        shortcut_item.connect(
            "clicked",
            lambda btn: (popover.popdown(), self._on_keyboard_shortcut_clicked()),
        )
        shortcut_item.set_halign(Gtk.Align.FILL)
        menu_box.append(shortcut_item)
        
        # Separator
        separator = Gtk.Separator()
        menu_box.append(separator)
        
        # About menu item
        about_item = Gtk.Button(label="About Meera")
        about_item.connect("clicked", lambda btn: (popover.popdown(), self._on_about_clicked()))
        about_item.set_halign(Gtk.Align.FILL)
        menu_box.append(about_item)

        quit_item = Gtk.Button(label="Quit Meera")
        quit_item.connect("clicked", lambda btn: (popover.popdown(), self._on_quit_clicked()))
        quit_item.set_halign(Gtk.Align.FILL)
        menu_box.append(quit_item)
        
        # Add menu button to header bar (on the left, before title)
        header_bar.pack_start(menu_button)
        
        # Set titlebar after everything is configured
        self.set_titlebar(header_bar)

        # ---------- Root layout (no global background image) ----------
        root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root_box.set_margin_top(12)
        root_box.set_margin_bottom(12)
        root_box.set_margin_start(12)
        root_box.set_margin_end(12)
        self.set_child(root_box)

        # Inner container for chat + input
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.set_margin_top(6)
        vbox.set_margin_bottom(6)
        vbox.set_margin_start(6)
        vbox.set_margin_end(6)
        root_box.append(vbox)

        # ---------- CHAT AREA WITH OVERLAY BACKGROUND ----------
        # Chat TextView
        self.chat_view = Gtk.TextView()
        self.chat_view.set_editable(False)
        self.chat_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.chat_view.add_css_class("meera-chat-view")
        self.chat_buf = self.chat_view.get_buffer()
        self._link_tags: dict[str, str] = {}

        click_controller = Gtk.GestureClick()
        click_controller.connect("released", self._on_chat_click_released)
        self.chat_view.add_controller(click_controller)

        # Create theme-aware text tags
        self._create_text_tags()

        # Overlay ONLY for the chat area
        chat_overlay = Gtk.Overlay()
        vbox.append(chat_overlay)

        # Background image inside chat area
        bg_picture = Gtk.Picture.new_for_filename(bg_path)
        bg_picture.set_can_shrink(True)
        chat_overlay.set_child(bg_picture)

        # Scrolled chat view on top of the image
        scroll = Gtk.ScrolledWindow()
        scroll.set_child(self.chat_view)
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)
        scroll.add_css_class("meera-scroll")
        chat_overlay.add_overlay(scroll)

        # ---------- INPUT AREA (NO IMAGE HERE) ----------
        input_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        # Multi-line input
        self.input_view = Gtk.TextView()
        self.input_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.input_view.add_css_class("meera-input-view")
        self.input_buf = self.input_view.get_buffer()

        # Create theme-aware input text tag
        self._create_input_text_tag()

        # Auto-grow height based on content (1–6 lines)
        self.input_buf.connect("changed", self._on_input_changed)

        # Capture Enter / Shift+Enter
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.input_view.add_controller(key_controller)

        input_scroll = Gtk.ScrolledWindow()
        self.input_scroll = input_scroll
        input_scroll.set_child(self.input_view)
        input_scroll.set_hexpand(True)
        input_scroll.set_vexpand(False)
        input_scroll.set_min_content_height(30)
        input_scroll.set_max_content_height(160)
        input_scroll.add_css_class("meera-scroll")

        input_box.append(input_scroll)

        # Send/Stop button
        self.send_button = Gtk.Button(label="↑")
        self.send_button.set_hexpand(False)
        self.send_button.connect("clicked", self.on_send_clicked)
        input_box.append(self.send_button)

        vbox.append(input_box)

        # Connect window close event to save history
        self.connect("close-request", self._on_window_close)
        self._connect_theme_watchers()
        
        # Initial greeting after UI is ready
        GLib.idle_add(self._initial_greeting)

        # Warm retrieval index in background so first prompt is faster.
        self._start_retrieval_prewarm()

    # ---------- theme detection and styling ----------
    
    def _detect_theme(self) -> bool:
        """Detect if the system is using dark theme. Returns True for dark, False for light."""
        # Try using Adw StyleManager if available (most reliable)
        if ADW_AVAILABLE:
            try:
                style_manager = Adw.StyleManager.get_default()
                color_scheme = style_manager.get_color_scheme()
                if color_scheme == Adw.ColorScheme.FORCE_DARK:
                    return True
                elif color_scheme == Adw.ColorScheme.FORCE_LIGHT:
                    return False
                # PREFER_DARK or DEFAULT - check system preference
                return style_manager.get_dark()
            except:
                pass
        
        # Fallback: Check GTK settings
        try:
            settings = Gtk.Settings.get_default()
            if settings:
                prefer_dark = settings.get_property("gtk-application-prefer-dark-theme")
                return prefer_dark
        except:
            pass
        
        # Default to dark theme if detection fails
        return True
    
    def _setup_theme_styling(self):
        """Set up CSS styling based on current theme."""
        if self.is_dark_theme:
            # Dark theme: dark background with white text
            css = """
            .meera-chat-view,
            .meera-input-view,
            .meera-scroll {
                background-color: rgba(20,20,20,0.7);
            }
            """
        else:
            # Light theme: light background
            css = """
            .meera-chat-view,
            .meera-input-view,
            .meera-scroll {
                background-color: rgba(230,230,230,0.75);
            }
            """
        
        self._css_provider.load_from_data(css.encode("utf-8"))
        if not self._css_provider_installed:
            display = Gdk.Display.get_default()
            if display is not None:
                Gtk.StyleContext.add_provider_for_display(
                    display,
                    self._css_provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                )
                self._css_provider_installed = True

    def _ensure_tag(self, buf: Gtk.TextBuffer, name: str, **properties) -> Gtk.TextTag:
        tag_table = buf.get_tag_table()
        tag = tag_table.lookup(name)
        if tag is None:
            tag = buf.create_tag(name)
        for key, value in properties.items():
            tag.set_property(key, value)
        return tag
    
    def _create_text_tags(self):
        """Create text tags for chat view based on current theme."""
        if self.is_dark_theme:
            # Dark theme: white text
            self.text_tag = self._ensure_tag(
                self.chat_buf,
                "text_fg",
                foreground="#ffffff",
            )
            # Bold tag for sender names
            self.bold_tag = self._ensure_tag(
                self.chat_buf,
                "bold_fg",
                foreground="#ffffff",
                weight=Pango.Weight.BOLD,
            )
            # Right alignment tag for user messages
            self.user_right_tag = self._ensure_tag(
                self.chat_buf,
                "user_right",
                justification=Gtk.Justification.RIGHT,
            )
            self.italic_tag = self._ensure_tag(
                self.chat_buf,
                "italic_fg",
                foreground="#ffffff",
                style=Pango.Style.ITALIC,
            )
            self.inline_code_tag = self._ensure_tag(
                self.chat_buf,
                "inline_code",
                foreground="#d4d4d4",
                family="monospace",
                background="#2b2b2b",
            )
            self.code_block_tag = self._ensure_tag(
                self.chat_buf,
                "code_block",
                foreground="#d4d4d4",
                family="monospace",
                background="#1f1f1f",
            )
        else:
            # Light theme: black text
            self.text_tag = self._ensure_tag(
                self.chat_buf,
                "text_fg",
                foreground="#000000",
            )
            # Bold tag for sender names
            self.bold_tag = self._ensure_tag(
                self.chat_buf,
                "bold_fg",
                foreground="#000000",
                weight=Pango.Weight.BOLD,
            )
            # Right alignment tag for user messages
            self.user_right_tag = self._ensure_tag(
                self.chat_buf,
                "user_right",
                justification=Gtk.Justification.RIGHT,
            )
            self.italic_tag = self._ensure_tag(
                self.chat_buf,
                "italic_fg",
                foreground="#000000",
                style=Pango.Style.ITALIC,
            )
            self.inline_code_tag = self._ensure_tag(
                self.chat_buf,
                "inline_code",
                foreground="#1f1f1f",
                family="monospace",
                background="#e8e8e8",
            )
            self.code_block_tag = self._ensure_tag(
                self.chat_buf,
                "code_block",
                foreground="#1f1f1f",
                family="monospace",
                background="#efefef",
            )
        # Keep white_tag as alias for backward compatibility
        self.white_tag = self.text_tag
    
    def _create_input_text_tag(self):
        """Create text tag for input view based on current theme."""
        if self.is_dark_theme:
            # Dark theme: white text
            self.input_text_tag = self._ensure_tag(
                self.input_buf,
                "input_fg",
                foreground="#ffffff",
            )
        else:
            # Light theme: black text
            self.input_text_tag = self._ensure_tag(
                self.input_buf,
                "input_fg",
                foreground="#000000",
            )
        # Keep input_white_tag as alias for backward compatibility
        self.input_white_tag = self.input_text_tag

    def _connect_theme_watchers(self):
        if ADW_AVAILABLE:
            try:
                style_manager = Adw.StyleManager.get_default()
                style_manager.connect("notify::dark", self._on_theme_changed)
            except Exception:
                pass

        try:
            settings = Gtk.Settings.get_default()
            if settings is not None:
                settings.connect("notify::gtk-application-prefer-dark-theme", self._on_theme_changed)
                settings.connect("notify::gtk-theme-name", self._on_theme_changed)
        except Exception:
            pass

    def _on_theme_changed(self, *_args):
        GLib.idle_add(self._refresh_theme_after_change)

    def _refresh_theme_after_change(self):
        new_is_dark = self._detect_theme()
        if new_is_dark == self.is_dark_theme:
            return False
        self.is_dark_theme = new_is_dark
        self._setup_theme_styling()
        self._create_text_tags()
        self._create_input_text_tag()
        start = self.input_buf.get_start_iter()
        end_iter = self.input_buf.get_end_iter()
        self.input_buf.apply_tag(self.input_text_tag, start, end_iter)
        self.chat_view.queue_draw()
        self.input_view.queue_draw()
        return False

    # ---------- helper methods ----------

    def _append_text(self, text: str):
        buf = self.chat_buf

        # Record where this chunk starts
        start_offset = buf.get_char_count()

        # Insert new text at the end
        buf.insert(buf.get_end_iter(), text)

        # Record where this chunk ends
        end_offset = buf.get_char_count()

        # Apply theme-aware text tag just to this new chunk
        start_iter = buf.get_iter_at_offset(start_offset)
        end_iter = buf.get_iter_at_offset(end_offset)
        buf.apply_tag(self.text_tag, start_iter, end_iter)

        # Scroll to bottom
        mark = buf.create_mark(None, buf.get_end_iter(), False)
        self.chat_view.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)

    def _append_tool_running_line(self, tool_name: str):
        """UI hint while executing a laptop tool (main thread)."""
        self._append_text(f"\n⟳ Running {tool_name}...\n")
        return False

    def _append_streaming_message_chunk(self, chunk: str):
        if not chunk:
            return False
        if not self._streaming_message_active:
            self._clear_typing_indicator()
            self._insert_with_tags("Meera: ", [self.text_tag, self.bold_tag])
            self._streaming_body_start_mark = self.chat_buf.create_mark(None, self.chat_buf.get_end_iter(), True)
            self._streaming_message_active = True
            self._streaming_render_buffer = ""
            self._streaming_render_dirty = False
            self._ensure_streaming_refresh_timer()
        self._streaming_render_buffer += chunk
        self._streaming_render_dirty = True
        return False

    def _finish_streaming_message_line(self, full_response: str | None = None):
        if self._streaming_message_active:
            if isinstance(full_response, str):
                self._streaming_render_buffer = full_response
                self._streaming_render_dirty = True
            self._refresh_streaming_message_preview()
            self._insert_with_tags("\n\n", [self.text_tag])
            mark = self.chat_buf.create_mark(None, self.chat_buf.get_end_iter(), False)
            self.chat_view.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)
            self._streaming_message_active = False
        self._streaming_render_buffer = ""
        self._streaming_render_dirty = False
        if self._streaming_body_start_mark is not None:
            self.chat_buf.delete_mark(self._streaming_body_start_mark)
            self._streaming_body_start_mark = None
        return False

    def _ensure_streaming_refresh_timer(self):
        if self._streaming_refresh_active:
            return
        self._streaming_refresh_active = True
        GLib.timeout_add(100, self._streaming_refresh_tick)

    def _streaming_refresh_tick(self):
        if not self._streaming_message_active:
            self._streaming_refresh_active = False
            return False
        self._refresh_streaming_message_preview()
        return True

    def _refresh_streaming_message_preview(self):
        if not self._streaming_render_dirty or self._streaming_body_start_mark is None:
            return
        buf = self.chat_buf
        start_iter = buf.get_iter_at_mark(self._streaming_body_start_mark)
        end_iter = buf.get_end_iter()
        buf.delete(start_iter, end_iter)
        self._insert_markdown(self._streaming_render_buffer)
        self._streaming_render_dirty = False
        mark = buf.create_mark(None, buf.get_end_iter(), False)
        self.chat_view.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)

    def _insert_with_tags(self, text: str, tags: list[Gtk.TextTag]):
        if not text:
            return
        buf = self.chat_buf
        start = buf.get_char_count()
        buf.insert(buf.get_end_iter(), text)
        end = buf.get_char_count()
        start_iter = buf.get_iter_at_offset(start)
        end_iter = buf.get_iter_at_offset(end)
        for tag in tags:
            buf.apply_tag(tag, start_iter, end_iter)

    def _link_tag_for_url(self, url: str) -> Gtk.TextTag:
        existing_name = None
        for name, value in self._link_tags.items():
            if value == url:
                existing_name = name
                break
        if existing_name is not None:
            return self.chat_buf.get_tag_table().lookup(existing_name)

        tag_name = f"link_{len(self._link_tags) + 1}"
        link_tag = self.chat_buf.create_tag(
            tag_name,
            foreground="#4a90e2",
            underline=Pango.Underline.SINGLE,
        )
        self._link_tags[tag_name] = url
        return link_tag

    def _insert_inline_markdown(self, text: str):
        token_pattern = re.compile(
            r"(\[([^\]]+)\]\((https?://[^\s)]+)\))|(\*\*([^*]+)\*\*)|(__([^_]+)__)|(`([^`]+)`)|(\*([^*]+)\*)|(_([^_]+)_)"
        )
        pos = 0
        for match in token_pattern.finditer(text):
            start, end = match.span()
            if start > pos:
                self._insert_with_tags(text[pos:start], [self.text_tag])

            if match.group(1):
                label = match.group(2)
                url = match.group(3)
                self._insert_with_tags(label, [self.text_tag, self._link_tag_for_url(url)])
            elif match.group(4):
                self._insert_with_tags(match.group(5), [self.text_tag, self.bold_tag])
            elif match.group(6):
                self._insert_with_tags(match.group(7), [self.text_tag, self.bold_tag])
            elif match.group(8):
                self._insert_with_tags(match.group(9), [self.inline_code_tag])
            elif match.group(10):
                self._insert_with_tags(match.group(11), [self.text_tag, self.italic_tag])
            elif match.group(12):
                self._insert_with_tags(match.group(13), [self.text_tag, self.italic_tag])
            pos = end

        if pos < len(text):
            self._insert_with_tags(text[pos:], [self.text_tag])

    def _insert_markdown(self, text: str):
        lines = text.splitlines(keepends=True)
        in_code_block = False

        for line in lines:
            stripped = line.rstrip("\n")
            if stripped.lstrip().startswith("```"):
                in_code_block = not in_code_block
                continue

            if in_code_block:
                self._insert_with_tags(line, [self.code_block_tag])
                continue

            has_newline = line.endswith("\n")
            content = line[:-1] if has_newline else line
            self._insert_inline_markdown(content)
            if has_newline:
                self._insert_with_tags("\n", [self.text_tag])

    def _on_chat_click_released(self, gesture, n_press, x, y):
        try:
            ok, iter_at_click = self.chat_view.get_iter_at_location(int(x), int(y))
        except Exception:
            return
        if not ok:
            return
        for tag in iter_at_click.get_tags():
            name = tag.get_property("name")
            url = self._link_tags.get(name)
            if url:
                try:
                    Gio.AppInfo.launch_default_for_uri(url, None)
                except Exception:
                    pass
                break

    def _append_message_line(self, sender: str, text: str):
        buf = self.chat_buf
        if sender == "Meera":
            self._clear_typing_indicator()
        start_offset = buf.get_char_count()
        self._insert_with_tags(f"{sender}: ", [self.text_tag, self.bold_tag])

        if sender == "Meera":
            self._insert_markdown(text)
        else:
            self._insert_with_tags(text, [self.text_tag])

        self._insert_with_tags("\n\n", [self.text_tag])

        if sender == "You":
            end_offset = buf.get_char_count()
            start_iter = buf.get_iter_at_offset(start_offset)
            end_iter = buf.get_iter_at_offset(end_offset)
            buf.apply_tag(self.user_right_tag, start_iter, end_iter)

        mark = buf.create_mark(None, buf.get_end_iter(), False)
        self.chat_view.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)

    def _show_typing_indicator(self):
        if self._typing_start_mark is not None:
            return
        buf = self.chat_buf
        start_iter = buf.get_end_iter()
        self._typing_start_mark = buf.create_mark(None, start_iter, True)
        self._insert_with_tags("Meera: ", [self.text_tag, self.bold_tag])
        self._insert_with_tags("Thinking...", [self.text_tag, self.italic_tag])
        self._insert_with_tags("\n\n", [self.text_tag])
        end_iter = buf.get_end_iter()
        self._typing_end_mark = buf.create_mark(None, end_iter, False)
        mark = buf.create_mark(None, buf.get_end_iter(), False)
        self.chat_view.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)

    def _clear_typing_indicator(self):
        if self._typing_start_mark is None or self._typing_end_mark is None:
            self._typing_start_mark = None
            self._typing_end_mark = None
            return
        buf = self.chat_buf
        start_iter = buf.get_iter_at_mark(self._typing_start_mark)
        end_iter = buf.get_iter_at_mark(self._typing_end_mark)
        buf.delete(start_iter, end_iter)
        buf.delete_mark(self._typing_start_mark)
        buf.delete_mark(self._typing_end_mark)
        self._typing_start_mark = None
        self._typing_end_mark = None

    def _set_button_state(self, streaming: bool):
        self.send_button.set_label("⏹" if streaming else "↑")

    def _start_retrieval_prewarm(self):
        def _worker():
            try:
                get_index()
            except Exception:
                # Best-effort warmup only; runtime retrieval will gracefully degrade.
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def _initial_greeting(self):
        welcome = "Hi, I'm Meera. How can I help you today?"
        self._append_message_line("Meera", welcome)
        return False

    # ---------- input box auto-grow ----------

    def _on_input_changed(self, buf):
        start = buf.get_start_iter()
        end = buf.get_end_iter()
        text = buf.get_text(start, end, False)

        width = self.input_view.get_allocated_width()
        if width <= 0:
            return

        context = self.input_view.get_pango_context()
        layout = Pango.Layout.new(context)
        layout.set_text(text, -1)
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        layout.set_width(width * Pango.SCALE)

        line_count = layout.get_line_count() or 1
        line_count = max(1, min(6, line_count))

        line = layout.get_line(0)
        if line is not None:
            _, logical = line.get_extents()
            line_height = logical.height / Pango.SCALE
        else:
            line_height = 18

        height = int(line_height * line_count + 8)
        self.input_scroll.set_min_content_height(height)

        # Ensure input text uses theme-aware color
        start = buf.get_start_iter()
        end_iter = buf.get_end_iter()
        buf.apply_tag(self.input_text_tag, start, end_iter)

    # ---------- input handling ----------

    def _on_key_pressed(self, controller, keyval, keycode, state):
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            if state & Gdk.ModifierType.SHIFT_MASK:
                return False  # newline
            self.on_send()
            return True
        return False

    def on_send_clicked(self, button):
        self.on_send()

    def on_send(self):
        if self.is_streaming:
            self.cancel_stream = True
            return

        start = self.input_buf.get_start_iter()
        end = self.input_buf.get_end_iter()
        prompt = self.input_buf.get_text(start, end, False).strip()

        if not prompt:
            return

        self._append_message_line("You", prompt)
        self.input_buf.set_text("")

        # Add user message to conversation history
        self.conversation_history.append({"role": "user", "content": prompt})

        self.is_streaming = True
        self.cancel_stream = False
        self._set_button_state(True)
        self._show_typing_indicator()

        thread = threading.Thread(
            target=self._stream_reply_worker,
            daemon=True,
        )
        thread.start()

    def _stream_reply_worker(self):
        if agent_tools_enabled():
            self._stream_reply_worker_agent()
        else:
            self._stream_reply_worker_plain()

    def _stream_reply_worker_plain(self):
        try:
            messages = [{"role": "system", "content": self._system_identity}] + self.conversation_history

            full_response = ""
            for chunk in stream_llm(messages):
                if self.cancel_stream:
                    break
                full_response += chunk
                GLib.idle_add(self._append_streaming_message_chunk, chunk)

            if not self.cancel_stream:
                if full_response:
                    self.conversation_history.append({"role": "assistant", "content": full_response})
                GLib.idle_add(self._finish_streaming_message_line, full_response)
        finally:
            GLib.idle_add(self._stream_finished)

    def _stream_reply_worker_agent(self):
        """Phase 4: drive one turn through the retrieval-first agent loop."""
        debug_tool_calls = os.environ.get("MEERA_DEBUG_TOOL_CALLS", "").strip().lower() in (
            "1", "true", "yes", "on",
        )
        if debug_tool_calls:
            # Keep debug lines visible: typing indicator clears would remove them.
            GLib.idle_add(self._clear_typing_indicator)

        try:
            distro = detect_distro()
        except Exception:
            distro = "unknown"

        # The user message has already been appended in on_send(); pass everything
        # before it as history and the prompt itself separately.
        history_for_agent = list(self.conversation_history[:-1])
        if not self.conversation_history or self.conversation_history[-1].get("role") != "user":
            GLib.idle_add(self._stream_finished)
            return
        user_text = str(self.conversation_history[-1].get("content") or "")

        full_response = ""
        memory_messages: list[str] = []

        try:
            for event in run_agent_turn(
                history_for_agent,
                user_text,
                distro=distro,
                base_identity=self._system_identity,
            ):
                if self.cancel_stream:
                    break
                kind = event.get("kind")
                if kind == "thinking":
                    if debug_tool_calls:
                        stage = event.get("stage", "?")
                        tools = event.get("tools") or []
                        rag = event.get("rag") or []
                        GLib.idle_add(
                            self._append_text,
                            f"\n[debug] stage={stage} tools={tools} rag={rag}\n",
                        )
                elif kind == "tool_running":
                    tool = str(event.get("tool") or "?")
                    params = event.get("params") or {}
                    if debug_tool_calls:
                        GLib.idle_add(
                            self._append_text,
                            f"\n[debug] tool={tool!r} params={json.dumps(params, sort_keys=True, ensure_ascii=False)}\n",
                        )
                    GLib.idle_add(self._append_tool_running_line, tool)
                elif kind == "tool_result":
                    mm = event.get("memory_message")
                    if isinstance(mm, str) and mm:
                        memory_messages.append(mm)
                    if debug_tool_calls:
                        GLib.idle_add(
                            self._append_text,
                            f"\n[debug] tool_result: ok={getattr(event.get('result'), 'ok', '?')}\n",
                        )
                elif kind == "content":
                    chunk = event.get("text") or ""
                    if chunk:
                        full_response += chunk
                        GLib.idle_add(self._append_streaming_message_chunk, chunk)
                elif kind == "done":
                    break

            if not self.cancel_stream:
                # Persist any tool-memory messages first so future turns see the
                # tool outputs in context, then the final natural-language reply.
                for mm in memory_messages:
                    self.conversation_history.append({"role": "assistant", "content": mm})
                if full_response:
                    self.conversation_history.append({"role": "assistant", "content": full_response})
                GLib.idle_add(self._finish_streaming_message_line, full_response)
        finally:
            GLib.idle_add(self._stream_finished)

    def _stream_finished(self):
        self._finish_streaming_message_line()
        self._clear_typing_indicator()
        self.is_streaming = False
        self.cancel_stream = False
        self._set_button_state(False)
        return False

    # ---------- menu actions ----------

    def _on_new_chat_clicked(self, button=None):
        """Start a new chat session"""
        self.conversation_history = []
        self.chat_buf.set_text("")
        self._initial_greeting()

    def _on_history_clicked(self, button=None):
        """Show the Chat History dialog"""
        sessions = list_sessions()
        
        history_window = Gtk.Window()
        history_window.set_title("Chat History")
        history_window.set_default_size(500, 400)
        history_window.set_modal(True)
        history_window.set_transient_for(self)
        
        # Main container
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        vbox.set_margin_top(20)
        vbox.set_margin_bottom(20)
        vbox.set_margin_start(20)
        vbox.set_margin_end(20)
        history_window.set_child(vbox)
        
        if not sessions:
            # No sessions message
            no_sessions_label = Gtk.Label(label="No saved sessions yet.")
            no_sessions_label.set_margin_top(20)
            vbox.append(no_sessions_label)
        else:
            # Scrolled window for session list
            scroll = Gtk.ScrolledWindow()
            scroll.set_vexpand(True)
            scroll.set_min_content_height(250)
            vbox.append(scroll)
            
            # List box for sessions
            list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            scroll.set_child(list_box)
            
            # Add each session
            for session in sessions:
                session_row = self._create_session_row(session, history_window)
                list_box.append(session_row)
        
        # Close button
        close_button = Gtk.Button(label="Close")
        close_button.set_margin_top(20)
        close_button.connect("clicked", lambda btn: history_window.close())
        vbox.append(close_button)
        
        history_window.present()
    
    def _create_session_row(self, session, history_window):
        """Create a row widget for a session"""
        from datetime import datetime
        
        # Parse timestamp for display (date only)
        try:
            dt = datetime.fromisoformat(session["timestamp"])
            date_str = dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            date_str = session.get("timestamp", "Unknown")[:10] if len(session.get("timestamp", "")) >= 10 else "Unknown"
        
        # Get last user message (up to 30 characters)
        last_question = "No messages"
        messages = load_session(session["filepath"])
        if messages:
            # Iterate in reverse to find the last user message
            for msg in reversed(messages):
                if msg.get("role") == "user" and msg.get("content"):
                    last_question = msg["content"][:50]
                    if len(msg["content"]) > 50:
                        last_question += "..."
                    break
        
        # Create row box
        row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row_box.set_margin_start(6)
        row_box.set_margin_end(6)
        row_box.set_margin_top(6)
        row_box.set_margin_bottom(6)
        
        # Session info
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info_box.set_hexpand(True)
        info_box.set_halign(Gtk.Align.START)
        
        date_label = Gtk.Label(label=date_str)
        date_label.set_halign(Gtk.Align.START)
        info_box.append(date_label)
        
        question_label = Gtk.Label(label=last_question)
        question_label.add_css_class("dim-label")
        question_label.set_halign(Gtk.Align.START)
        question_label.set_wrap(True)
        info_box.append(question_label)
        
        row_box.append(info_box)
        
        # Load button
        load_button = Gtk.Button(label="Load")
        load_button.connect("clicked", lambda btn: self._load_session(session["filepath"], history_window))
        row_box.append(load_button)
        
        return row_box
    
    def _load_session(self, filepath, history_window):
        """Load a session into the current conversation"""
        messages = load_session(filepath)
        if messages:
            # Drop legacy synthetic tool-result rows (no longer stored in new sessions)
            self.conversation_history = [
                m
                for m in messages
                if not (
                    m.get("role") == "user"
                    and str(m.get("content") or "").startswith(TOOL_FEEDBACK_PREFIX)
                )
            ]
            # Clear chat view
            self.chat_buf.set_text("")

            # Display loaded messages (skip synthetic tool-feedback/memory rows
            # and legacy raw tool-call JSON from pre-Phase-4 sessions).
            for msg in messages:
                role = msg.get("role")
                content = msg.get("content") or ""
                if role == "user":
                    if content.startswith(TOOL_FEEDBACK_PREFIX):
                        continue
                    self._append_message_line("You", content)
                elif role == "assistant":
                    if content.startswith(TOOL_MEMORY_PREFIX):
                        continue
                    if _looks_like_legacy_tool_call(content):
                        self._append_message_line("Meera", "[Laptop tool was used — see following messages.]")
                    else:
                        self._append_message_line("Meera", content)
            
            # Close history window
            history_window.close()
        else:
            # Show error dialog
            error_dialog = Gtk.MessageDialog(
                transient_for=history_window,
                modal=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Failed to load session"
            )
            error_dialog.format_secondary_text("The session file could not be loaded or is corrupted.")
            error_dialog.run()
            error_dialog.destroy()

    def _on_about_clicked(self, button=None):
        """Show the About dialog"""
        about_window = Gtk.Window()
        about_window.set_title("About Meera")
        about_window.set_default_size(400, 200)
        about_window.set_modal(True)
        about_window.set_transient_for(self)
        about_window.set_resizable(False)

        # Main container
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        vbox.set_margin_top(20)
        vbox.set_margin_bottom(20)
        vbox.set_margin_start(20)
        vbox.set_margin_end(20)
        about_window.set_child(vbox)

        # Title
        title_label = Gtk.Label(label="Meera")
        title_label.add_css_class("title-1")
        vbox.append(title_label)

        # Description
        desc_label = Gtk.Label(label="AI companion for Linux desktops")
        desc_label.set_margin_top(10)
        vbox.append(desc_label)

        # Website button
        website_button = Gtk.LinkButton(uri="https://github.com/achinivar/meera", label="Website")
        website_button.set_margin_top(20)
        vbox.append(website_button)

        # Close button
        close_button = Gtk.Button(label="Close")
        close_button.set_margin_top(20)
        close_button.connect("clicked", lambda btn: about_window.close())
        vbox.append(close_button)

        about_window.present()

    def _autostart_file_path(self) -> str:
        xdg_config_home = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
        return os.path.join(xdg_config_home, "autostart", "meera.desktop")

    def _desktop_file_path(self) -> str:
        xdg_data_home = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
        return os.path.join(xdg_data_home, "applications", "local.meera.Meera.desktop")

    def _is_autostart_enabled(self) -> bool:
        return os.path.isfile(self._autostart_file_path())

    def _refresh_autostart_menu_label(self) -> None:
        if self._is_autostart_enabled():
            self.autostart_item.set_label("Disable auto-start")
        else:
            self.autostart_item.set_label("Enable auto-start")

    def _on_autostart_toggle_clicked(self, button=None):
        autostart_file = self._autostart_file_path()
        try:
            if self._is_autostart_enabled():
                os.remove(autostart_file)
                self._append_message_line("Meera", "Auto-start disabled.")
            else:
                os.makedirs(os.path.dirname(autostart_file), exist_ok=True)
                desktop_file = self._desktop_file_path()
                if os.path.isfile(desktop_file):
                    shutil.copyfile(desktop_file, autostart_file)
                else:
                    launcher = os.path.expanduser("~/.local/bin/meera")
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
                self._append_message_line("Meera", "Auto-start enabled.")
        except OSError as exc:
            self._append_message_line("Meera", f"Could not update auto-start: {exc}")

        self._refresh_autostart_menu_label()

    def _keyboard_shortcut_helper_path(self) -> str:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_dir, "scripts", "keyboard_shortcut.py")

    def _shortcut_modifiers(self, state):
        return state & (
            Gdk.ModifierType.CONTROL_MASK
            | Gdk.ModifierType.SHIFT_MASK
            | Gdk.ModifierType.ALT_MASK
            | Gdk.ModifierType.SUPER_MASK
            | Gdk.ModifierType.HYPER_MASK
            | Gdk.ModifierType.META_MASK
        )

    def _set_keyboard_shortcut(self, binding: str) -> tuple[bool, str]:
        helper = self._keyboard_shortcut_helper_path()
        launcher = os.path.expanduser("~/.local/bin/meera")
        if not os.path.isfile(helper):
            return False, "Keyboard shortcut helper is missing."
        result = subprocess.run(
            ["python3", helper, "set", binding, launcher],
            capture_output=True,
            check=False,
            text=True,
        )
        if result.returncode == 0:
            return True, f"Keyboard shortcut set to {binding}."
        message = (result.stderr or result.stdout or "Could not set keyboard shortcut.").strip()
        return False, message

    def _on_keyboard_shortcut_clicked(self, button=None):
        shortcut_window = Gtk.Window()
        shortcut_window.set_title("Keyboard Shortcut")
        shortcut_window.set_modal(True)
        shortcut_window.set_transient_for(self)
        shortcut_window.set_default_size(420, 180)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        vbox.set_margin_top(20)
        vbox.set_margin_bottom(20)
        vbox.set_margin_start(20)
        vbox.set_margin_end(20)
        shortcut_window.set_child(vbox)

        message = Gtk.Label(label="Press the keyboard shortcut you want to use for Meera.")
        message.set_wrap(True)
        message.set_xalign(0)
        vbox.append(message)

        detail = Gtk.Label(label="Use at least one modifier key, such as Ctrl, Alt, or Super.")
        detail.set_wrap(True)
        detail.set_xalign(0)
        detail.add_css_class("dim-label")
        vbox.append(detail)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        button_box.set_halign(Gtk.Align.END)
        vbox.append(button_box)

        close_button = Gtk.Button(label="Close")
        close_button.connect("clicked", lambda btn: shortcut_window.close())
        button_box.append(close_button)

        def on_key_pressed(controller, keyval, keycode, state):
            modifiers = self._shortcut_modifiers(state)
            if not Gtk.accelerator_valid(keyval, modifiers):
                detail.set_text("That shortcut is not valid. Try another one.")
                return True
            binding = Gtk.accelerator_name(keyval, modifiers)
            ok, result_message = self._set_keyboard_shortcut(binding)
            if ok:
                detail.set_text(result_message)
                GLib.timeout_add(900, lambda: (shortcut_window.close(), False)[1])
            else:
                detail.set_text(f"{result_message} Try a different shortcut.")
            return True

        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", on_key_pressed)
        shortcut_window.add_controller(key_controller)
        shortcut_window.present()

    def _on_quit_clicked(self, button=None):
        """Confirm quit, then stop local model servers and close Meera."""
        confirm_window = Gtk.Window()
        confirm_window.set_title("Quit Meera?")
        confirm_window.set_modal(True)
        confirm_window.set_transient_for(self)
        confirm_window.set_default_size(380, 160)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        vbox.set_margin_top(20)
        vbox.set_margin_bottom(20)
        vbox.set_margin_start(20)
        vbox.set_margin_end(20)
        confirm_window.set_child(vbox)

        message = Gtk.Label(
            label="Quit Meera and stop the local model servers?"
        )
        message.set_wrap(True)
        message.set_xalign(0)
        vbox.append(message)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        button_box.set_halign(Gtk.Align.END)
        vbox.append(button_box)

        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", lambda btn: confirm_window.close())
        button_box.append(cancel_button)

        quit_button = Gtk.Button(label="Quit Meera")
        quit_button.add_css_class("destructive-action")
        quit_button.connect("clicked", lambda btn: self._confirm_quit(confirm_window))
        button_box.append(quit_button)

        confirm_window.present()

    def _confirm_quit(self, confirm_window):
        confirm_window.close()
        self.cancel_stream = True
        if self.conversation_history:
            save_session(self.conversation_history)
        self._stop_installed_model_servers()
        self.close()

    def _stop_installed_model_servers(self):
        launcher = os.path.expanduser("~/.local/bin/meera")
        if not os.path.exists(launcher) or not os.access(launcher, os.X_OK):
            return
        try:
            subprocess.run(
                [launcher, "unload-model"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
            )
        except Exception:
            # Quitting the UI should not be blocked by cleanup failures.
            return

    # ---------- window lifecycle ----------

    def _on_window_close(self, window):
        """Handle window close event - save conversation history"""
        if self.conversation_history:
            save_session(self.conversation_history)
        return False  # Allow window to close normally

