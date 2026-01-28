# Claude Usage Monitor

A Windows system tray application that monitors your Claude Code and Claude Desktop usage in real-time.

![Claude Usage Monitor](screenshot.png)

## Features

- **System tray icon** with dynamic usage indicator (changes color based on usage level)
- **Elegant glass-effect widget** with Claude's brand colors
- **Tracks multiple sources:**
  - Claude Code CLI sessions
  - Claude Desktop app (local data)
- **Visual indicators:**
  - Session usage (current Claude Code session)
  - Weekly Code usage
  - Total weekly usage (Code + Desktop)
- **Color-coded warnings:**
  - Orange (normal) → Amber (75%) → Orange-Red (90%) → Red (critical)
- **Quick access button** to open claude.ai usage page
- **Auto-refresh** every 30 seconds

## Installation

### Option 1: Run from source (requires Python)

1. Make sure you have Python 3.8+ installed
2. Clone or download this repository
3. Install dependencies:
   ```bash
   pip install pystray Pillow
   ```
4. Run the monitor:
   ```bash
   python claude_usage_monitor.py
   ```
   Or double-click `run.bat`

### Option 2: Download release (no Python needed)

Download the latest `ClaudeUsageMonitor.exe` from the [Releases](../../releases) page.

## Usage

- **Left-click** the tray icon to show/hide the widget
- **Right-click** the tray icon for menu (Refresh, Quit)
- Click **"Open claude.ai Usage"** to view your Max/Pro subscription usage in browser

## Auto-start with Windows

Run `add_to_startup.bat` to add the monitor to Windows startup.

## Configuration

Edit the following values in `claude_usage_monitor.py` to customize:

```python
REFRESH_INTERVAL = 30  # seconds between updates
session_limit = 1_000_000  # session token limit estimate
weekly_limit = 10_000_000  # weekly token limit estimate
```

## How it works

The monitor reads usage data from:
- **Claude Code:** `~/.claude/projects/` JSONL log files
- **Claude Desktop:** Various local storage locations

Note: Claude Max/Pro subscription usage from claude.ai cannot be queried via API. Use the "Open claude.ai Usage" button to check it manually.

## Requirements

- Windows 10/11
- Python 3.8+ (if running from source)
- Dependencies: `pystray`, `Pillow`

## License

MIT License - feel free to use and modify.

## Credits

Built with Claude Code by Anthropic.
