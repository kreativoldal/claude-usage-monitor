"""
Claude Code Usage Monitor - Windows System Tray Application
Elegant glass-effect floating widget with Claude-style design.
Tracks both Claude Code CLI and Claude Desktop usage.
"""

import json
import os
import sys
import threading
import time
import ctypes
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
import tkinter as tk
from tkinter import ttk
import pystray
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pystray import MenuItem as item
import math
import webbrowser
import tempfile

# Windows transparency support
try:
    from ctypes import windll, byref, sizeof, c_int
    DWMWA_USE_IMMERSIVE_DARK_MODE = 20
    DWMWA_SYSTEMBACKDROP_TYPE = 38
except:
    pass

# Configuration
REFRESH_INTERVAL = 30  # seconds
CLAUDE_CODE_DIR = Path.home() / ".claude"
CLAUDE_DESKTOP_DIRS = [
    Path(os.environ.get('APPDATA', '')) / "Claude",
    Path(os.environ.get('LOCALAPPDATA', '')) / "Claude",
    Path(os.environ.get('APPDATA', '')) / "claude-desktop",
    Path(os.environ.get('LOCALAPPDATA', '')) / "claude-desktop",
    Path(os.environ.get('LOCALAPPDATA', '')) / "Packages" / "Claude",  # Windows Store version
]

# Claude brand colors
CLAUDE_ORANGE = "#E07A4E"
CLAUDE_CORAL = "#D4826A"
CLAUDE_CREAM = "#F5EDE4"
CLAUDE_DARK = "#1A1915"


class UsageData:
    """Handles reading and parsing Claude Code and Desktop usage data."""

    def __init__(self):
        self.code_session_tokens = 0
        self.code_weekly_tokens = 0
        self.desktop_tokens = 0
        self.total_tokens = 0
        self.session_limit = 1_000_000
        self.weekly_limit = 10_000_000
        self.last_updated = None
        self.cost_estimate = 0.0
        self.sources_found = []

    def find_claude_code_jsonl_files(self) -> List[Path]:
        """Find all JSONL log files from Claude Code."""
        projects_dir = CLAUDE_CODE_DIR / "projects"
        if not projects_dir.exists():
            return []

        jsonl_files = []
        for root, dirs, files in os.walk(projects_dir):
            for file in files:
                if file.endswith('.jsonl'):
                    filepath = Path(root) / file
                    jsonl_files.append(filepath)
        return jsonl_files

    def find_claude_desktop_data(self) -> List[Path]:
        """Find Claude Desktop data files."""
        found_files = []

        for base_dir in CLAUDE_DESKTOP_DIRS:
            if not base_dir.exists():
                continue

            # Look for common data file patterns
            patterns = [
                "**/*.json",
                "**/*.jsonl",
                "**/logs/*.json",
                "**/usage*.json",
                "**/conversations/*.json",
            ]

            for pattern in patterns:
                for filepath in base_dir.glob(pattern):
                    if filepath.is_file():
                        found_files.append(filepath)

        return found_files

    def parse_usage_from_jsonl(self, filepath: Path) -> Dict[str, int]:
        """Parse usage statistics from a JSONL file."""
        total_input_tokens = 0
        total_output_tokens = 0

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())

                        if 'usage' in entry:
                            usage = entry['usage']
                            total_input_tokens += usage.get('input_tokens', 0)
                            total_output_tokens += usage.get('output_tokens', 0)

                        if 'message' in entry and isinstance(entry['message'], dict):
                            msg = entry['message']
                            if 'usage' in msg:
                                usage = msg['usage']
                                total_input_tokens += usage.get('input_tokens', 0)
                                total_output_tokens += usage.get('output_tokens', 0)

                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass

        return {
            'input_tokens': total_input_tokens,
            'output_tokens': total_output_tokens,
            'total_tokens': total_input_tokens + total_output_tokens,
        }

    def parse_desktop_json(self, filepath: Path) -> Dict[str, int]:
        """Parse usage from Claude Desktop JSON files."""
        total_tokens = 0

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Handle different possible structures
            if isinstance(data, dict):
                # Direct usage object
                if 'usage' in data:
                    usage = data['usage']
                    total_tokens += usage.get('input_tokens', 0)
                    total_tokens += usage.get('output_tokens', 0)

                # Conversations with messages
                if 'messages' in data:
                    for msg in data['messages']:
                        if isinstance(msg, dict) and 'usage' in msg:
                            total_tokens += msg['usage'].get('input_tokens', 0)
                            total_tokens += msg['usage'].get('output_tokens', 0)

            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and 'usage' in item:
                        total_tokens += item['usage'].get('input_tokens', 0)
                        total_tokens += item['usage'].get('output_tokens', 0)

        except Exception:
            pass

        return {'total_tokens': total_tokens}

    def calculate_weekly_code_usage(self) -> int:
        """Calculate Claude Code usage for the current week."""
        today = datetime.now()
        week_start = today - timedelta(days=today.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

        total_tokens = 0
        jsonl_files = self.find_claude_code_jsonl_files()

        for filepath in jsonl_files:
            try:
                if datetime.fromtimestamp(filepath.stat().st_mtime) >= week_start:
                    usage = self.parse_usage_from_jsonl(filepath)
                    total_tokens += usage['total_tokens']
            except Exception:
                continue

        return total_tokens

    def calculate_session_usage(self) -> int:
        """Calculate current session usage (most recent JSONL file)."""
        jsonl_files = self.find_claude_code_jsonl_files()
        if not jsonl_files:
            return 0

        # Sort by modification time, get most recent
        jsonl_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        latest = jsonl_files[0]

        usage = self.parse_usage_from_jsonl(latest)
        return usage['total_tokens']

    def calculate_desktop_usage(self) -> int:
        """Calculate Claude Desktop usage for the current week."""
        today = datetime.now()
        week_start = today - timedelta(days=today.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

        total_tokens = 0
        desktop_files = self.find_claude_desktop_data()

        for filepath in desktop_files:
            try:
                if datetime.fromtimestamp(filepath.stat().st_mtime) >= week_start:
                    if filepath.suffix == '.jsonl':
                        usage = self.parse_usage_from_jsonl(filepath)
                    else:
                        usage = self.parse_desktop_json(filepath)
                    total_tokens += usage['total_tokens']
            except Exception:
                continue

        return total_tokens

    def get_usage_percentage(self) -> float:
        """Get the higher of session or weekly usage percentage."""
        session_pct = self.code_session_tokens / max(self.session_limit, 1)
        weekly_pct = self.total_tokens / max(self.weekly_limit, 1)
        return max(session_pct, weekly_pct)

    def refresh(self):
        """Refresh all usage data."""
        self.sources_found = []

        # Claude Code usage
        self.code_session_tokens = self.calculate_session_usage()
        self.code_weekly_tokens = self.calculate_weekly_code_usage()

        if self.code_weekly_tokens > 0:
            self.sources_found.append("Code")

        # Claude Desktop usage
        self.desktop_tokens = self.calculate_desktop_usage()

        if self.desktop_tokens > 0:
            self.sources_found.append("Desktop")

        # Combined total
        self.total_tokens = self.code_weekly_tokens + self.desktop_tokens

        # Cost estimate (average ~$9/M tokens)
        self.cost_estimate = (self.total_tokens / 1_000_000) * 9
        self.last_updated = datetime.now()


def create_claude_icon(size: int = 64, usage_pct: float = 0) -> Image.Image:
    """Create Claude-style icon with usage meter."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    center = size // 2
    radius = size // 2 - 4

    # Determine color based on usage
    if usage_pct < 0.5:
        main_color = (224, 122, 78)  # Claude orange
    elif usage_pct < 0.75:
        main_color = (245, 158, 11)  # Amber
    elif usage_pct < 0.9:
        main_color = (249, 115, 22)  # Orange-Red
    else:
        main_color = (239, 68, 68)   # Red

    # Outer glow effect
    for i in range(3, 0, -1):
        alpha = 30 * i
        glow = (*main_color[:3], alpha)
        draw.ellipse([
            center - radius - i*2,
            center - radius - i*2,
            center + radius + i*2,
            center + radius + i*2
        ], fill=glow)

    # Main circle background (dark)
    draw.ellipse([
        center - radius,
        center - radius,
        center + radius,
        center + radius
    ], fill=(26, 25, 21))

    # Usage arc
    if usage_pct > 0:
        start_angle = -90
        end_angle = -90 + (360 * min(usage_pct, 1.0))
        inner_radius = radius - 6

        draw.pieslice([
            center - inner_radius,
            center - inner_radius,
            center + inner_radius,
            center + inner_radius
        ], start=start_angle, end=end_angle, fill=main_color)

        # Cut out center to make ring
        center_radius = inner_radius - 8
        draw.ellipse([
            center - center_radius,
            center - center_radius,
            center + center_radius,
            center + center_radius
        ], fill=(26, 25, 21))

    # Claude sparkle in center
    spark_size = 8
    draw.line([center, center - spark_size, center, center + spark_size],
              fill=main_color, width=2)
    draw.line([center - spark_size, center, center + spark_size, center],
              fill=main_color, width=2)
    ds = spark_size - 3
    draw.line([center - ds, center - ds, center + ds, center + ds],
              fill=main_color, width=1)
    draw.line([center - ds, center + ds, center + ds, center - ds],
              fill=main_color, width=1)

    return img


def create_window_icon() -> str:
    """Create an ICO file for the window icon and return the path."""
    icon_img = create_claude_icon(64, 0.3)

    # Create multiple sizes for ICO
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64)]
    icons = []
    for size in sizes:
        resized = icon_img.resize(size, Image.Resampling.LANCZOS)
        icons.append(resized)

    # Save to temp file
    ico_path = os.path.join(tempfile.gettempdir(), "claude_usage_icon.ico")
    icons[0].save(ico_path, format='ICO', sizes=[(s, s) for s, _ in sizes], append_images=icons[1:])

    return ico_path


# Global icon path (created once)
WINDOW_ICON_PATH = None


class GlassWidget(tk.Toplevel):
    """Elegant glass-effect floating widget."""

    def __init__(self, usage_data: UsageData):
        super().__init__()
        self.usage_data = usage_data
        self.setup_window()
        self.create_widgets()
        self.apply_glass_effect()

    def setup_window(self):
        """Configure the floating window with glass effect."""
        global WINDOW_ICON_PATH

        self.title("Claude Usage")
        self.geometry("320x320")  # Increased height for button
        self.resizable(False, False)
        self.attributes('-topmost', True)
        self.attributes('-alpha', 0.95)

        # Set custom window icon
        try:
            if WINDOW_ICON_PATH is None:
                WINDOW_ICON_PATH = create_window_icon()
            self.iconbitmap(WINDOW_ICON_PATH)
        except Exception:
            pass  # Fallback to default if icon creation fails

        # Colors for glass theme
        self.bg_color = "#1A1915"
        self.glass_bg = "#252420"
        self.fg_color = "#F5EDE4"
        self.dim_color = "#8B8680"
        self.accent = "#E07A4E"

        self.configure(bg=self.bg_color)

        # Position in bottom right
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = screen_width - 340
        y = screen_height - 400
        self.geometry(f"+{x}+{y}")

    def apply_glass_effect(self):
        """Apply Windows acrylic/mica effect if available."""
        try:
            hwnd = windll.user32.GetParent(self.winfo_id())
            value = c_int(1)
            windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, byref(value), sizeof(value))
            value = c_int(2)
            windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, byref(value), sizeof(value))
        except:
            pass

    def create_widgets(self):
        """Create the elegant UI elements."""
        # Main container with padding
        main_frame = tk.Frame(self, bg=self.bg_color, padx=20, pady=15)
        main_frame.pack(fill='both', expand=True)

        # Header with Claude branding
        header_frame = tk.Frame(main_frame, bg=self.bg_color)
        header_frame.pack(fill='x', pady=(0, 12))

        title_label = tk.Label(
            header_frame,
            text="Claude",
            font=('Segoe UI', 16, 'normal'),
            fg=self.accent,
            bg=self.bg_color
        )
        title_label.pack(side='left')

        subtitle_label = tk.Label(
            header_frame,
            text=" Usage",
            font=('Segoe UI', 16, 'normal'),
            fg=self.fg_color,
            bg=self.bg_color
        )
        subtitle_label.pack(side='left')

        # Session usage section
        self.session_bar, self.session_glow, self.session_label = self.create_usage_section(
            main_frame, "Session", "Current session"
        )

        # Weekly Code usage section
        self.code_bar, self.code_glow, self.code_label = self.create_usage_section(
            main_frame, "Code Weekly", "Claude Code this week"
        )

        # Weekly Total (Code + Desktop)
        self.total_bar, self.total_glow, self.total_label = self.create_usage_section(
            main_frame, "Total Weekly", "Code + Desktop combined"
        )

        # Bottom info section
        info_frame = tk.Frame(main_frame, bg=self.bg_color)
        info_frame.pack(fill='x', pady=(12, 0))

        self.cost_label = tk.Label(
            info_frame,
            text="~$0.00 this week",
            font=('Segoe UI', 10),
            fg=self.dim_color,
            bg=self.bg_color
        )
        self.cost_label.pack(side='left')

        self.updated_label = tk.Label(
            info_frame,
            text="--:--",
            font=('Segoe UI', 9),
            fg=self.dim_color,
            bg=self.bg_color
        )
        self.updated_label.pack(side='right')

        # Sources indicator
        self.sources_label = tk.Label(
            main_frame,
            text="Sources: --",
            font=('Segoe UI', 9),
            fg=self.dim_color,
            bg=self.bg_color
        )
        self.sources_label.pack(anchor='w', pady=(8, 0))

        # Button to open claude.ai usage page
        btn_frame = tk.Frame(main_frame, bg=self.bg_color)
        btn_frame.pack(fill='x', pady=(12, 0))

        self.usage_btn = tk.Label(
            btn_frame,
            text="Open claude.ai Usage",
            font=('Segoe UI', 9),
            fg=self.accent,
            bg="#2A2925",
            cursor="hand2",
            padx=12,
            pady=6
        )
        self.usage_btn.pack(side='left')
        self.usage_btn.bind("<Button-1>", lambda e: webbrowser.open("https://claude.ai/settings/usage"))
        self.usage_btn.bind("<Enter>", lambda e: self.usage_btn.configure(bg="#3A3935"))
        self.usage_btn.bind("<Leave>", lambda e: self.usage_btn.configure(bg="#2A2925"))

    def create_usage_section(self, parent, title, subtitle):
        """Create a usage bar section with glass effect."""
        frame = tk.Frame(parent, bg=self.bg_color)
        frame.pack(fill='x', pady=6)

        # Title row
        title_row = tk.Frame(frame, bg=self.bg_color)
        title_row.pack(fill='x')

        tk.Label(
            title_row,
            text=title,
            font=('Segoe UI', 10, 'bold'),
            fg=self.fg_color,
            bg=self.bg_color
        ).pack(side='left')

        value_label = tk.Label(
            title_row,
            text="0",
            font=('Segoe UI', 10),
            fg=self.accent,
            bg=self.bg_color
        )
        value_label.pack(side='right')

        # Glass-effect progress bar container
        bar_container = tk.Frame(frame, bg=self.glass_bg, height=10)
        bar_container.pack(fill='x', pady=(4, 0))
        bar_container.pack_propagate(False)

        # Glow effect layer
        glow_bar = tk.Frame(bar_container, bg=self.glass_bg, height=10)
        glow_bar.place(x=0, y=0, relwidth=0, relheight=1)

        # Main progress bar
        progress_bar = tk.Frame(bar_container, bg=self.accent, height=10)
        progress_bar.place(x=0, y=0, relwidth=0, relheight=1)

        return progress_bar, glow_bar, value_label

    def get_color_for_percentage(self, pct: float) -> tuple:
        """Get appropriate color based on usage percentage."""
        if pct < 0.5:
            return self.accent, "#3D2A22"  # Normal - Claude orange
        elif pct < 0.75:
            return "#F59E0B", "#3D3415"    # Warning - Amber
        elif pct < 0.9:
            return "#F97316", "#3D2815"    # High - Orange
        else:
            return "#EF4444", "#3D1515"    # Critical - Red

    def update_bar(self, bar, glow, label, tokens, limit, name=""):
        """Update a single progress bar."""
        def format_tokens(n):
            if n >= 1_000_000:
                return f"{n/1_000_000:.2f}M"
            elif n >= 1_000:
                return f"{n/1_000:.1f}K"
            return str(n)

        pct = min(tokens / max(limit, 1), 1.0)
        color, glow_color = self.get_color_for_percentage(pct)

        bar.configure(bg=color)
        bar.place(relwidth=max(pct, 0.005))
        glow.configure(bg=glow_color)
        glow.place(relwidth=min(pct + 0.03, 1.0))
        label.configure(text=format_tokens(tokens), fg=color)

    def update_display(self):
        """Update the display with current usage data."""
        # Session bar
        self.update_bar(
            self.session_bar, self.session_glow, self.session_label,
            self.usage_data.code_session_tokens, self.usage_data.session_limit
        )

        # Code weekly bar
        self.update_bar(
            self.code_bar, self.code_glow, self.code_label,
            self.usage_data.code_weekly_tokens, self.usage_data.weekly_limit
        )

        # Total weekly bar (Code + Desktop)
        self.update_bar(
            self.total_bar, self.total_glow, self.total_label,
            self.usage_data.total_tokens, self.usage_data.weekly_limit
        )

        # Cost estimate
        self.cost_label.configure(text=f"~${self.usage_data.cost_estimate:.2f} this week")

        # Last updated
        if self.usage_data.last_updated:
            self.updated_label.configure(
                text=self.usage_data.last_updated.strftime('%H:%M')
            )

        # Sources found
        if self.usage_data.sources_found:
            sources_text = "Sources: " + ", ".join(self.usage_data.sources_found)
        else:
            sources_text = "Sources: No data found"
        self.sources_label.configure(text=sources_text)


class SystemTrayApp:
    """Main application with system tray icon."""

    def __init__(self):
        self.usage_data = UsageData()
        self.widget = None
        self.root = None
        self.running = True

    def toggle_widget(self, icon=None, item=None):
        """Toggle the visibility of the usage widget."""
        if self.widget is None or not self.widget.winfo_exists():
            self.root.after(0, self.show_widget)
        else:
            self.root.after(0, self.hide_widget)

    def show_widget(self):
        """Show the usage widget."""
        if self.widget is None or not self.widget.winfo_exists():
            self.widget = GlassWidget(self.usage_data)
            self.widget.protocol("WM_DELETE_WINDOW", self.hide_widget)
            self.update_widget()
        else:
            self.widget.deiconify()
            self.widget.lift()

    def hide_widget(self):
        """Hide the usage widget."""
        if self.widget and self.widget.winfo_exists():
            self.widget.withdraw()

    def update_widget(self):
        """Update widget display if visible."""
        if self.widget and self.widget.winfo_exists():
            self.widget.update_display()

    def refresh_data(self):
        """Refresh usage data and update display."""
        self.usage_data.refresh()
        if self.root:
            self.root.after(0, self.update_widget)

        # Update tray icon
        if hasattr(self, 'icon') and self.icon:
            pct = self.usage_data.get_usage_percentage()
            self.icon.icon = create_claude_icon(64, pct)

    def refresh_loop(self):
        """Background thread for periodic data refresh."""
        while self.running:
            self.refresh_data()
            time.sleep(REFRESH_INTERVAL)

    def quit_app(self, icon=None, item=None):
        """Quit the application."""
        self.running = False
        if self.icon:
            self.icon.stop()
        if self.root:
            self.root.quit()

    def run(self):
        """Start the application."""
        self.root = tk.Tk()
        self.root.withdraw()

        # Initial data load
        self.usage_data.refresh()

        # Create system tray menu
        menu = pystray.Menu(
            item('Show/Hide', self.toggle_widget, default=True),
            item('Refresh', lambda: self.refresh_data()),
            pystray.Menu.SEPARATOR,
            item('Quit', self.quit_app)
        )

        # Create icon
        pct = self.usage_data.get_usage_percentage()
        self.icon = pystray.Icon(
            "claude_usage",
            create_claude_icon(64, pct),
            "Claude Code Usage Monitor",
            menu
        )

        # Start background refresh
        refresh_thread = threading.Thread(target=self.refresh_loop, daemon=True)
        refresh_thread.start()

        # Run tray icon
        icon_thread = threading.Thread(target=self.icon.run, daemon=True)
        icon_thread.start()

        # Show widget on startup
        self.root.after(100, self.show_widget)

        # Run main loop
        self.root.mainloop()


def main():
    """Entry point."""
    app = SystemTrayApp()
    app.run()


if __name__ == "__main__":
    main()
