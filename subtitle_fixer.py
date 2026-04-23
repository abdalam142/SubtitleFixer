"""
Subtitle Encoding Fixer
A desktop application to fix subtitle encoding issues, especially for Arabic subtitles.

Requirements:
    pip install charset-normalizer

Usage:
    python subtitle_fixer.py
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import sys
from pathlib import Path
from charset_normalizer import from_bytes

try:
    import charset_normalizer as chardet
    HAS_CHARDET = True
except ImportError:
    HAS_CHARDET = False

# =============================================================================
# THEME CONFIGURATION
# =============================================================================

class Theme:
    """Dark theme color palette"""
    BG_MAIN = "#1E1E2E"
    BG_SURFACE = "#2A2A3E"
    BG_ELEVATED = "#353550"
    PRIMARY = "#7C3AED"
    PRIMARY_HOVER = "#8B5CF6"
    SECONDARY = "#22D3EE"
    SUCCESS = "#10B981"
    ERROR = "#EF4444"
    WARNING = "#F59E0B"
    TEXT_PRIMARY = "#F8FAFC"
    TEXT_SECONDARY = "#94A3B8"
    TEXT_MUTED = "#64748B"
    BORDER = "#3F3F5A"
    HIGHLIGHT = "#22D3EE"


# =============================================================================
# ENCODING PRIORITY LIST
# =============================================================================

class EncodingPriority:
    """
    Smart encoding priority order for subtitle files.
    Arabic subtitles typically use: windows-1256, iso-8859-6, utf-8
    """

    HIGH = ["utf-8", "utf-8-sig", "windows-1256", "iso-8859-6"]
    MEDIUM = ["cp1252", "latin-1"]
    LOW = ["utf-16", "utf-16-le", "utf-16-be", "cp720", "koi8-r", "mac_arabic"]

    ALL = HIGH + MEDIUM + LOW

    @classmethod
    def get_group(cls, encoding):
        """Get priority group for an encoding"""
        if encoding in cls.HIGH:
            return 1, cls.HIGH.index(encoding)
        elif encoding in cls.MEDIUM:
            return 2, cls.MEDIUM.index(encoding)
        elif encoding in cls.LOW:
            return 3, cls.LOW.index(encoding)
        return 4, 0

    @classmethod
    def sort_key(cls, encoding):
        """Sort key for ordering encodings"""
        group, idx = cls.get_group(encoding)
        return (group, idx)


# =============================================================================
# ENCODING LOGIC
# =============================================================================

class EncodingDetector:
    """Auto-detect file encoding using charset-normalizer"""

    @staticmethod
    def detect(data: bytes):
        """
        Detect encoding from binary data.
        Returns: (encoding_name, confidence)
        """
        if not HAS_CHARDET:
            return "utf-8", 0.0

        try:
            result = from_bytes(data).best()
            if result:
                encoding = result.encoding.lower()
                confidence = result.ratio
                return encoding, confidence
        except Exception:
            pass

        return "utf-8", 0.0

    @staticmethod
    def is_arabic_broken(text: str) -> bool:
        """
        Detect if Arabic text appears broken/garbled.
        Common garbled patterns: Ø§, Ù„, Ù, §
        """
        if not text:
            return False

        garbled_patterns = ["Ø§", "Ù„", "Ùƒ", "��§Ù„", "Ù„Ù", "§Ù"]

        for pattern in garbled_patterns:
            if pattern in text:
                return True

        return False


class EncodingEngine:
    """Core encoding/decoding engine"""

    @staticmethod
    def try_decode(data: bytes, encoding: str) -> tuple:
        """
        Try to decode binary data with given encoding.
        Returns: (success, decoded_text_or_error)
        """
        if not data:
            return False, "Empty file"

        try:
            text = data.decode(encoding)
            return True, text
        except UnicodeDecodeError as e:
            return False, f"Decode error: {e.reason}"
        except Exception as e:
            return False, f"Error: {str(e)}"

    @staticmethod
    def decode_all(data: bytes) -> dict:
        """
        Try all encodings and return results.
        Returns: {encoding: (success, text_or_error)}
        """
        results = {}

        for encoding in EncodingPriority.ALL:
            success, result = EncodingEngine.try_decode(data, encoding)
            results[encoding] = (success, result)

        return results


# =============================================================================
# UI WIDGETS
# =============================================================================

class StyledButton(tk.Button):
    """Custom styled button matching theme"""

    def __init__(self, parent, text, command, style="primary", **kwargs):
        self.style = style
        self.command = command

        colors = {
            "primary": (Theme.PRIMARY, Theme.PRIMARY_HOVER, "#6D28D9"),
            "secondary": (Theme.BG_SURFACE, Theme.BG_ELEVATED, Theme.BORDER),
            "success": (Theme.SUCCESS, "#34D399", "#059669"),
            "danger": (Theme.ERROR, "#F87171", "#DC2626"),
        }

        bg, hover, pressed = colors.get(style, colors["primary"])

        super().__init__(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=Theme.TEXT_PRIMARY,
            activebackground=hover,
            activeforeground=Theme.TEXT_PRIMARY,
            relief=tk.FLAT,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
            padx=20,
            pady=10,
            **kwargs
        )

        self.bind("<Enter>", lambda e: self.config(bg=hover))
        self.bind("<Leave>", lambda e: self.config(bg=bg))

        self._bg = bg
        self._hover = hover
        self._pressed = pressed


class EncodingCard(tk.Frame):
    """
    Preview card for a single encoding result.
    Shows encoding name, status, text preview, and select button.
    """

    def __init__(self, parent, encoding, is_detected=False, on_select=None, is_selected=False):
        super().__init__(parent, bg=Theme.BG_SURFACE, padx=10, pady=10)

        self.encoding = encoding
        self.is_detected = is_detected
        self.on_select = on_select
        self.is_selected = is_selected
        self.select_btn = None

        self._create_widgets()

    def set_selected(self, selected):
        """Update button state based on selection"""
        self.is_selected = selected
        if self.select_btn:
            if selected:
                self.select_btn.config(text="✓ Selected", bg=Theme.SUCCESS)
            else:
                self.select_btn.config(text="Select", bg=Theme.PRIMARY)

    def _create_widgets(self):
        """Create card widgets"""

        header_frame = tk.Frame(self, bg=Theme.BG_SURFACE)
        header_frame.pack(fill=tk.X, pady=(0, 8))

        self.encoding_label = tk.Label(
            header_frame,
            text=self.encoding.upper(),
            font=("Segoe UI", 12, "bold"),
            fg=Theme.TEXT_PRIMARY if not self.is_detected else Theme.HIGHLIGHT,
            bg=Theme.BG_SURFACE
        )
        self.encoding_label.pack(side=tk.LEFT)

        self.status_label = tk.Label(
            header_frame,
            text="✓",
            font=("Segoe UI", 12),
            fg=Theme.SUCCESS,
            bg=Theme.BG_SURFACE
        )
        self.status_label.pack(side=tk.RIGHT)

        if self.on_select:
            btn_bg = Theme.SUCCESS if self.is_selected else Theme.PRIMARY
            btn_text = "✓ Selected" if self.is_selected else "Select"
            self.select_btn = tk.Button(
                header_frame,
                text=btn_text,
                font=("Segoe UI", 9, "bold"),
                fg=Theme.TEXT_PRIMARY,
                bg=btn_bg,
                activebackground=Theme.PRIMARY_HOVER,
                activeforeground=Theme.TEXT_PRIMARY,
                relief=tk.FLAT,
                cursor="hand2",
                padx=12,
                pady=4,
                command=lambda: self.on_select(self.encoding)
            )
            self.select_btn.pack(side=tk.RIGHT, padx=(8, 0))

        if self.is_detected:
            detected_badge = tk.Label(
                header_frame,
                text="DETECTED",
                font=("Segoe UI", 9, "bold"),
                fg=Theme.BG_MAIN,
                bg=Theme.HIGHLIGHT,
                padx=8,
                pady=2
            )
            detected_badge.pack(side=tk.RIGHT, padx=(0, 8))

        text_frame = tk.Frame(self, bg=Theme.BG_SURFACE, highlightbackground=Theme.BORDER, highlightthickness=1)
        text_frame.pack(fill=tk.BOTH, expand=True)

        self.preview = tk.Text(
            text_frame,
            font=("Consolas", 10),
            fg=Theme.TEXT_PRIMARY,
            bg=Theme.BG_MAIN,
            relief=tk.FLAT,
            height=6,
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        self.preview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=1, pady=1)

        scrollbar = tk.Scrollbar(text_frame, command=self.preview.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.preview.config(yscrollcommand=scrollbar.set)

        if self.is_detected:
            self.config(highlightbackground=Theme.HIGHLIGHT, highlightthickness=2)

    def update_content(self, success: bool, text_or_error: str):
        """Update card with decoding result"""

        if success:
            self.status_label.config(text="✓", fg=Theme.SUCCESS)
            preview_text = text_or_error[:400]
            self.preview.config(state=tk.NORMAL)
            self.preview.delete("1.0", tk.END)
            self.preview.insert("1.0", preview_text)
            self.preview.config(state=tk.DISABLED)
        else:
            self.status_label.config(text="✗", fg=Theme.ERROR)
            self.preview.config(state=tk.NORMAL)
            self.preview.delete("1.0", tk.END)
            self.preview.insert("1.0", f"FAILED: {text_or_error}", "error")
            self.preview.tag_config("error", foreground=Theme.ERROR)
            self.preview.config(state=tk.DISABLED)


# =============================================================================
# MAIN APPLICATION
# =============================================================================

class SubtitleFixerApp:
    """Main application window"""

    def __init__(self, root):
        self.root = root
        self.root.title("Subtitle Encoding Fixer")
        self.root.geometry("900x750")
        self.root.minsize(800, 650)
        self.root.configure(bg=Theme.BG_MAIN)

        self.current_file = None
        self.current_data = None
        self.detected_encoding = None
        self.detected_confidence = 0.0
        self.encoding_results = {}
        self.selected_encoding = None
        self.encoding_cards = {}

        self._setup_styles()
        self._create_layout()

    def _setup_styles(self):
        """Setup ttk styles"""
        style = tk.ttk.Style()
        style.theme_use("clam")

    def _create_layout(self):
        """Create main UI layout"""

        main_container = tk.Frame(self.root, bg=Theme.BG_MAIN)
        main_container.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        self._create_header(main_container)
        self._create_toolbar(main_container)
        self._create_content_area(main_container)
        self._create_status_bar(main_container)

    def _create_header(self, parent):
        """Create header with title and detection result"""

        header = tk.Frame(parent, bg=Theme.BG_MAIN)
        header.pack(fill=tk.X, pady=(0, 16))

        title = tk.Label(
            header,
            text="Subtitle Encoding Fixer",
            font=("Segoe UI", 18, "bold"),
            fg=Theme.TEXT_PRIMARY,
            bg=Theme.BG_MAIN
        )
        title.pack(side=tk.LEFT)

        self.detection_label = tk.Label(
            header,
            text="No file loaded",
            font=("Segoe UI", 11),
            fg=Theme.TEXT_SECONDARY,
            bg=Theme.BG_MAIN
        )
        self.detection_label.pack(side=tk.RIGHT)

        subtitle = tk.Label(
            parent,
            text="Fix Arabic & subtitle encoding issues instantly",
            font=("Segoe UI", 10),
            fg=Theme.TEXT_MUTED,
            bg=Theme.BG_MAIN
        )
        subtitle.pack(fill=tk.X, pady=(0, 8))

    def _create_toolbar(self, parent):
        """Create toolbar with action buttons"""

        toolbar = tk.Frame(parent, bg=Theme.BG_MAIN)
        toolbar.pack(fill=tk.X, pady=(0, 16))

        self.btn_open = StyledButton(
            toolbar,
            "📂 Open File",
            self.open_file,
            style="primary"
        )
        self.btn_open.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_save = StyledButton(
            toolbar,
            "💾 Save as UTF-8",
            self.save_file,
            style="secondary"
        )
        self.btn_save.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_save.config(state=tk.DISABLED)

        self._update_save_button_text()

        self.btn_quick_fix = StyledButton(
            toolbar,
            "⚡ Quick Fix",
            self.quick_fix,
            style="success"
        )
        self.btn_quick_fix.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_quick_fix.config(state=tk.DISABLED)

        self.btn_clear = StyledButton(
            toolbar,
            "✕ Clear",
            self.clear_all,
            style="danger"
        )
        self.btn_clear.pack(side=tk.RIGHT)

    def _create_content_area(self, parent):
        """Create main content area with encoding列表 and previews"""

        content = tk.Frame(parent, bg=Theme.BG_MAIN)
        content.pack(fill=tk.BOTH, expand=True)

        left_panel = tk.Frame(content, bg=Theme.BG_MAIN, width=200)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 16))
        left_panel.pack_propagate(False)

        left_label = tk.Label(
            left_panel,
            text="Encodings",
            font=("Segoe UI", 12, "bold"),
            fg=Theme.TEXT_SECONDARY,
            bg=Theme.BG_MAIN
        )
        left_label.pack(pady=(0, 8))

        self.encoding_listbox = tk.Listbox(
            left_panel,
            font=("Segoe UI", 10),
            fg=Theme.TEXT_PRIMARY,
            bg=Theme.BG_SURFACE,
            selectbackground=Theme.PRIMARY,
            selectforeground=Theme.TEXT_PRIMARY,
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=1,
            highlightcolor=Theme.PRIMARY,
            highlightbackground=Theme.BORDER
        )
        self.encoding_listbox.pack(fill=tk.BOTH, expand=True)

        for enc in EncodingPriority.ALL:
            self.encoding_listbox.insert(tk.END, enc.upper())

        self.encoding_listbox.bind("<<ListboxSelect>>", self._on_encoding_select)

        right_panel = tk.Frame(content, bg=Theme.BG_MAIN)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        right_label = tk.Label(
            right_panel,
            text="Preview",
            font=("Segoe UI", 12, "bold"),
            fg=Theme.TEXT_SECONDARY,
            bg=Theme.BG_MAIN
        )
        right_label.pack(pady=(0, 8))

        self.preview_canvas = tk.Canvas(
            right_panel,
            bg=Theme.BG_SURFACE,
            highlightthickness=1,
            highlightcolor=Theme.BORDER
        )
        self.preview_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.preview_vscroll = tk.Scrollbar(
            right_panel,
            orient=tk.VERTICAL,
            command=self.preview_canvas.yview
        )
        self.preview_vscroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.preview_canvas.config(yscrollcommand=self.preview_vscroll.set)

        self.preview_frame = tk.Frame(
            self.preview_canvas,
            bg=Theme.BG_SURFACE
        )
        self.preview_canvas.create_window(
            (0, 0),
            window=self.preview_frame,
            anchor=tk.NW
        )

    def _create_status_bar(self, parent):
        """Create status bar"""

        status = tk.Frame(parent, bg=Theme.BG_MAIN)
        status.pack(fill=tk.X, pady=(16, 0))

        self.status_label = tk.Label(
            status,
            text="Ready - Open a .srt file to get started",
            font=("Segoe UI", 9),
            fg=Theme.TEXT_MUTED,
            bg=Theme.BG_MAIN
        )
        self.status_label.pack(side=tk.LEFT)

    def _update_status(self, message: str):
        """Update status bar message"""
        self.status_label.config(text=message)

    def _update_save_button_text(self):
        """Update save button text based on selected encoding"""
        if self.selected_encoding:
            enc = self.selected_encoding.upper()
            self.btn_save.config(text=f"💾 Save as {enc}")
        else:
            self.btn_save.config(text="💾 Save as UTF-8")

    def _update_detection_label(self):
        """Update detection result in header"""
        if self.detected_encoding:
            conf_pct = self.detected_confidence * 100
            self.detection_label.config(
                text=f"Detected: {self.detected_encoding.upper()} ({conf_pct:.0f}% confidence)",
                fg=Theme.HIGHLIGHT
            )
        else:
            self.detection_label.config(
                text="No file loaded",
                fg=Theme.TEXT_SECONDARY
            )

    def _clear_preview_cards(self):
        """Clear encoding preview cards"""
        for widget in self.preview_frame.winfo_children():
            widget.destroy()

    def _create_preview_cards(self):
        """Create preview cards for all encodings"""
        self._clear_preview_cards()
        self.selected_encoding = None
        self.encoding_cards = {}

        if not self.current_data:
            return

        detected_enc = (self.detected_encoding or "").lower()

        def on_select_encoding(enc):
            self.selected_encoding = enc
            for card_enc, card in self.encoding_cards.items():
                card.set_selected(card_enc == enc)
            self._update_save_button_text()
            self._update_status(f"Selected: {enc.upper()} - Click 'Save as {enc.upper()}' to convert")

        for encoding in EncodingPriority.ALL:
            is_detected = encoding.lower() == detected_enc
            card = EncodingCard(
                self.preview_frame,
                encoding,
                is_detected,
                on_select=on_select_encoding,
                is_selected=False
            )
            card.pack(fill=tk.X, pady=(0, 8))
            self.encoding_cards[encoding] = card

            if encoding in self.encoding_results:
                success, text = self.encoding_results[encoding]
                card.update_content(success, text)
            else:
                card.update_content(False, "Not tested")

        self.preview_frame.update_idletasks()
        w = self.preview_frame.winfo_reqwidth()
        h = self.preview_frame.winfo_reqheight()
        self.preview_canvas.configure(scrollregion=(0, 0, w, h))

    def open_file(self):
        """Open file dialog and load subtitle file"""

        filename = filedialog.askopenfilename(
            title="Open Subtitle File",
            filetypes=[
                ("Subtitle files", "*.srt"),
                ("All files", "*.*")
            ]
        )

        if not filename:
            return

        try:
            with open(filename, "rb") as f:
                self.current_data = f.read()

            if not self.current_data:
                messagebox.showerror("Error", "File is empty!")
                return

            self.current_file = filename
            self._update_status(f"Loaded: {os.path.basename(filename)}")

            self._process_file()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file: {str(e)}")
            self._update_status("Error opening file")

    def _process_file(self):
        """Process loaded file - detect encoding and create previews"""

        self._update_status("Detecting encoding...")

        detected, confidence = EncodingDetector.detect(self.current_data)
        self.detected_encoding = detected
        self.detected_confidence = confidence

        self._update_detection_label()

        self._update_status("Testing all encodings...")

        self.encoding_results = EncodingEngine.decode_all(self.current_data)

        is_broken = False
        test_text = ""
        if self.detected_encoding in self.encoding_results:
            success, text = self.encoding_results[self.detected_encoding]
            if success:
                test_text = text
                is_broken = EncodingDetector.is_arabic_broken(text)

        if is_broken:
            self.detection_label.config(
                text=f"⚠ BROKEN ARABIC DETECTED - Try windows-1256",
                fg=Theme.WARNING
            )

        self._create_preview_cards()

        self.btn_save.config(state=tk.NORMAL)
        self.btn_quick_fix.config(state=tk.NORMAL)

        self._update_status("Ready - Select an encoding and save as UTF-8")

    def _on_encoding_select(self, event):
        """Handle encoding selection from listbox"""
        selection = self.encoding_listbox.curselection()
        if not selection:
            return

        index = selection[0]
        encoding = EncodingPriority.ALL[index]

        self.preview_canvas.yview_moveto(index / len(EncodingPriority.ALL))

    def save_file(self):
        """Save file as UTF-8"""

        if self.selected_encoding:
            selected_encoding = self.selected_encoding
        else:
            selected_encoding = self.detected_encoding or "utf-8"

        if not self.current_file or not self.current_data:
            messagebox.showerror("Error", "Please load a file first!")
            return

        if selected_encoding not in self.encoding_results:
            messagebox.showerror("Error", "Please select a valid encoding first!")
            return

        success, text = self.encoding_results.get(selected_encoding, (False, None))

        if not success:
            messagebox.showerror("Error", f"Cannot save - {selected_encoding} decoding failed!")
            return

        original_name = os.path.splitext(os.path.basename(self.current_file))[0]

        save_path = filedialog.asksaveasfilename(
            title="Save as UTF-8",
            defaultextension=".srt",
            filetypes=[("Subtitle files", "*.srt")],
            initialfile=f"{original_name}_utf8.srt"
        )

        if not save_path:
            return

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(text)

            messagebox.showinfo("Success", f"File saved as UTF-8!\n\n{save_path}")
            self._update_status(f"Saved: {os.path.basename(save_path)}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {str(e)}")

    def quick_fix(self):
        """Quick fix - auto detect, convert and save"""

        if not self.current_file or not self.current_data:
            messagebox.showerror("Error", "Please load a file first!")
            return

        detected = self.detected_encoding or "utf-8"

        if detected not in self.encoding_results:
            messagebox.showerror("Error", "Detection failed!")
            return

        success, text = self.encoding_results.get(detected, (False, None))

        if not success:
            messagebox.showerror(
                "Error",
                f"Auto-detection chose {detected.upper()} but it failed to decode.\n\n"
                "Please manually select an encoding from the list."
            )
            return

        original_name = os.path.splitext(os.path.basename(self.current_file))[0]
        base_dir = os.path.dirname(self.current_file)
        save_path = os.path.join(base_dir, f"{original_name}_fixed.srt")

        answer = messagebox.askyesno(
            "Quick Fix",
            f"Auto-detected encoding: {detected.upper()}\n"
            f"Save as: {os.path.basename(save_path)}?"
        )

        if not answer:
            return

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(text)

            messagebox.showinfo(
                "Success!",
                f"File fixed and saved!\n\n{save_path}"
            )
            self._update_status(f"Quick fixed: {os.path.basename(save_path)}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {str(e)}")

    def clear_all(self):
        """Clear all loaded data"""
        self.current_file = None
        self.current_data = None
        self.detected_encoding = None
        self.detected_confidence = 0.0
        self.encoding_results = {}
        self.selected_encoding = None
        self.encoding_cards = {}

        self._clear_preview_cards()
        self._update_detection_label()
        self._update_save_button_text()
        self._update_status("Ready - Open a .srt file to get started")

        self.btn_save.config(state=tk.DISABLED)
        self.btn_quick_fix.config(state=tk.DISABLED)


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    """Application entry point"""
    root = tk.Tk()

    app = SubtitleFixerApp(root)

    root.mainloop()


if __name__ == "__main__":
    main()