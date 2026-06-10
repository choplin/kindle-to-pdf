"""Kindle application window control via AppleScript."""

from __future__ import annotations

import json
import subprocess
import sys
import time

from kindle_to_pdf.config import WindowBounds

_APP_NAMES = ["Amazon Kindle", "Kindle"]


def _run_osascript(script: str, timeout: int = 5) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=timeout,
    )


def _get_screen_size() -> tuple[int, int]:
    result = subprocess.run(
        ["osascript", "-l", "JavaScript", "-e",
         'ObjC.import("AppKit"); var s = $.NSScreen.mainScreen.frame; '
         'JSON.stringify({w: s.size.width, h: s.size.height})'],
        capture_output=True, text=True, timeout=5,
    )
    data = json.loads(result.stdout.strip())
    return (int(data["w"]), int(data["h"]))


class KindleWindow:
    """Handle to the running Kindle application window."""

    def __init__(self, app_name: str):
        self._app_name = app_name
        self._bounds: WindowBounds | None = None

    @classmethod
    def find(cls) -> KindleWindow:
        """Detect running Kindle app and return a window handle."""
        for name in _APP_NAMES:
            result = _run_osascript(f'application "{name}" is running')
            if result.stdout.strip() == "true":
                return cls(name)
        print("Error: Kindle app is not running. Please open Kindle and a book first.")
        sys.exit(1)

    @property
    def app_name(self) -> str:
        return self._app_name

    @property
    def bounds(self) -> WindowBounds:
        if self._bounds is None:
            self.refresh_bounds()
        return self._bounds

    def activate(self):
        """Bring the Kindle app to the foreground."""
        _run_osascript(f'tell application "{self._app_name}" to activate')
        time.sleep(0.5)

    def resize(self, aspect: str):
        """Resize and position window to max size within the given aspect ratio."""
        w_ratio, h_ratio = (int(x) for x in aspect.split(":"))
        target = w_ratio / h_ratio

        screen_w, screen_h = _get_screen_size()
        menu_bar = 25
        avail_h = screen_h - menu_bar

        if avail_h * target <= screen_w:
            new_h = avail_h
            new_w = int(avail_h * target)
        else:
            new_w = screen_w
            new_h = int(screen_w / target)

        new_x = (screen_w - new_w) // 2
        new_y = menu_bar

        script = f'''
            tell application "System Events"
                set p to first process whose name contains "Kindle"
                set w to first window of p
                set position of w to {{{new_x}, {new_y}}}
                set size of w to {{{new_w}, {new_h}}}
            end tell
        '''
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            print(f"Warning: Could not resize Kindle window: {result.stderr.strip()}")
        time.sleep(0.5)
        self._bounds = WindowBounds(new_x, new_y, new_w, new_h)
        print(f"Resized window: {new_w}x{new_h} at ({new_x},{new_y}) (aspect {aspect})")

    def refresh_bounds(self):
        """Re-fetch window bounds from System Events."""
        self._bounds = self._fetch_bounds()

    def turn_page(self, reverse: bool = False):
        """Simulate pressing arrow key to turn to the next page."""
        key = 123 if reverse else 124
        _run_osascript(f'tell application "System Events" to key code {key}')

    def _fetch_bounds(self) -> WindowBounds:
        script = '''
            tell application "System Events"
                set p to first process whose name contains "Kindle"
                set pos to position of first window of p
                set sz to size of first window of p
                return ((item 1 of pos) as text) & " " & ((item 2 of pos) as text) & " " & ((item 1 of sz) as text) & " " & ((item 2 of sz) as text)
            end tell
        '''
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, check=True, timeout=5,
            )
            parts = [int(s) for s in result.stdout.strip().split()]
            x, y, w, h = parts
            return WindowBounds(x, y, w, h)
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.strip() if e.stderr else ""
            if "-1719" in stderr:
                print("Error: Accessibility permission is required.")
                print("Grant permission in:")
                print("  System Settings > Privacy & Security > Accessibility")
                print("Add your terminal app to the list.")
                sys.exit(2)
            print("Error: Could not get Kindle window bounds.")
            print("Make sure a book is open in Kindle.")
            if stderr:
                print(f"  Detail: {stderr}")
            sys.exit(1)
        except (ValueError, IndexError):
            print("Error: Failed to parse Kindle window bounds.")
            sys.exit(1)
