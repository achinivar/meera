import os
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gio", "2.0")
from gi.repository import Gtk, GLib, Gdk, Pango, Gio

import threading
from backend import stream_llm


class MeeraWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Meera")
        self.set_default_size(550, 800)

        # State for streaming
        self.is_streaming = False
        self.cancel_stream = False
        
        # Conversation history for context
        self.conversation_history = []

        # ---------- CSS (for bubbles & transparent chat bg) ----------
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        bg_path = os.path.join(base_dir, "assets", "meera_bg.png")

        css = """
        .meera-chat-view,
        .meera-input-view,
        .meera-scroll {
            background-color: rgba(20,20,20,0.7);
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode("utf-8"))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

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
        
        # About menu item
        about_item = Gtk.Button(label="About Meera")
        about_item.connect("clicked", lambda btn: (popover.popdown(), self._on_about_clicked()))
        about_item.set_halign(Gtk.Align.FILL)
        menu_box.append(about_item)
        
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

        # tag to force white text in chat
        self.white_tag = self.chat_buf.create_tag(
            "white_fg",
            foreground="#ffffff",
        )

        # Tag for right-aligned user bubble
        self.user_tag = self.chat_buf.create_tag(
            "user_right",
            justification=Gtk.Justification.RIGHT,
            background="#293548",
            foreground="#ffffff",
            left_margin=40,
            right_margin=4,
            pixels_above_lines=4,
            pixels_below_lines=4,
            pixels_inside_wrap=6,
        )

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

        # tag to force white text in the input box
        self.input_white_tag = self.input_buf.create_tag(
            "white_input",
            foreground="#ffffff",
        )

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

        # Initial greeting after UI is ready
        GLib.idle_add(self._initial_greeting)

    # ---------- helper methods ----------

    def _append_text(self, text: str):
        buf = self.chat_buf

        # Record where this chunk starts
        start_offset = buf.get_char_count()

        # Insert new text at the end
        buf.insert(buf.get_end_iter(), text)

        # Record where this chunk ends
        end_offset = buf.get_char_count()

        # Apply white text tag just to this new chunk
        start_iter = buf.get_iter_at_offset(start_offset)
        end_iter = buf.get_iter_at_offset(end_offset)
        buf.apply_tag(self.white_tag, start_iter, end_iter)

        # Scroll to bottom
        mark = buf.create_mark(None, buf.get_end_iter(), False)
        self.chat_view.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)

    def _append_message_line(self, sender: str, text: str):
        buf = self.chat_buf
        message = f"{sender}: {text}\n\n"
    
        start_offset = buf.get_char_count()
        end_iter = buf.get_end_iter()
        buf.insert(end_iter, message)
        end_offset = buf.get_char_count()
    
        start_iter = buf.get_iter_at_offset(start_offset)
        end_iter = buf.get_iter_at_offset(end_offset)
    
        # 🔹 Make everything white
        buf.apply_tag(self.white_tag, start_iter, end_iter)
    
        # User bubble styling on top
        if sender == "You":
            buf.apply_tag(self.user_tag, start_iter, end_iter)
    
        mark = buf.create_mark(None, buf.get_end_iter(), False)
        self.chat_view.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)

    def _set_button_state(self, streaming: bool):
        self.send_button.set_label("⏹" if streaming else "↑")

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

        # 🔹 ensure input text stays white
        start = buf.get_start_iter()
        end_iter = buf.get_end_iter()
        buf.apply_tag(self.input_white_tag, start, end_iter)

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

        self._append_text("Meera: ")

        thread = threading.Thread(
            target=self._stream_reply_worker,
            daemon=True,
        )
        thread.start()

    def _stream_reply_worker(self):
        try:
            # Collect the full response for conversation history
            full_response = ""
            for chunk in stream_llm(self.conversation_history):
                if self.cancel_stream:
                    break
                full_response += chunk
                GLib.idle_add(self._append_text, chunk)
            
            # Add assistant response to conversation history if not cancelled
            if not self.cancel_stream and full_response:
                self.conversation_history.append({"role": "assistant", "content": full_response})
        finally:
            GLib.idle_add(self._stream_finished)

    def _stream_finished(self):
        self._append_text("\n\n")
        self.is_streaming = False
        self.cancel_stream = False
        self._set_button_state(False)
        return False

    # ---------- menu actions ----------

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
        desc_label = Gtk.Label(label="AI companion for Prism OS")
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

