"""OS-specific window control and screen capture.

All platform-dependent operations are isolated behind the ``PlatformBackend``
interface so the rest of the codebase stays OS-agnostic. Exactly one concrete
backend is instantiated per run via :func:`get_backend`; no other module should
branch on the current platform.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from abc import ABC, abstractmethod

from kindle_to_pdf.config import WindowBounds

# Substring used to locate the Kindle window regardless of the exact app name.
_WINDOW_MATCH = "Kindle"


class PlatformError(Exception):
    """A platform operation failed with a user-facing message.

    Carries the message and the process exit code the CLI should use, so
    platform-specific guidance (e.g. macOS Accessibility permission) lives in
    the backend while control flow stays generic.
    """

    def __init__(self, message: str, exit_code: int = 1):
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code


class PlatformBackend(ABC):
    """Interface for all OS-dependent window and capture operations."""

    @abstractmethod
    def find_running_app(self, candidate_names: list[str]) -> str | None:
        """Return the first running app name from candidates, or None."""

    @abstractmethod
    def activate(self, app_name: str) -> None:
        """Bring the given app to the foreground."""

    @abstractmethod
    def screen_size(self) -> tuple[int, int]:
        """Return the usable screen size as (width, height)."""

    @abstractmethod
    def window_bounds(self, app_name: str) -> WindowBounds:
        """Return the Kindle window position and size. Raises PlatformError."""

    @abstractmethod
    def set_window_bounds(self, app_name: str, x: int, y: int, width: int, height: int) -> None:
        """Move and resize the Kindle window. Raises PlatformError on failure."""

    @abstractmethod
    def turn_page(self, reverse: bool) -> None:
        """Send the arrow key that turns to the next (or previous) page."""

    @abstractmethod
    def capture_region(self, bounds: WindowBounds, output_path: str) -> bool:
        """Capture a screen region to a PNG file. Returns success."""


class MacBackend(PlatformBackend):
    """macOS backend using ``screencapture`` and AppleScript/JXA."""

    def _osascript(self, script: str, timeout: int = 5) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=timeout,
        )

    def find_running_app(self, candidate_names: list[str]) -> str | None:
        for name in candidate_names:
            result = self._osascript(f'application "{name}" is running')
            if result.stdout.strip() == "true":
                return name
        return None

    def activate(self, app_name: str) -> None:
        self._osascript(f'tell application "{app_name}" to activate')
        time.sleep(0.5)

    def screen_size(self) -> tuple[int, int]:
        result = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e",
             'ObjC.import("AppKit"); var s = $.NSScreen.mainScreen.frame; '
             'JSON.stringify({w: s.size.width, h: s.size.height})'],
            capture_output=True, text=True, timeout=5,
        )
        data = json.loads(result.stdout.strip())
        return (int(data["w"]), int(data["h"]))

    def window_bounds(self, app_name: str) -> WindowBounds:
        script = f'''
            tell application "System Events"
                set p to first process whose name contains "{_WINDOW_MATCH}"
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
                raise PlatformError(
                    "Error: Accessibility permission is required.\n"
                    "Grant permission in:\n"
                    "  System Settings > Privacy & Security > Accessibility\n"
                    "Add your terminal app to the list.",
                    exit_code=2,
                )
            message = (
                "Error: Could not get Kindle window bounds.\n"
                "Make sure a book is open in Kindle."
            )
            if stderr:
                message += f"\n  Detail: {stderr}"
            raise PlatformError(message)
        except (ValueError, IndexError):
            raise PlatformError("Error: Failed to parse Kindle window bounds.")

    def set_window_bounds(self, app_name: str, x: int, y: int, width: int, height: int) -> None:
        script = f'''
            tell application "System Events"
                set p to first process whose name contains "{_WINDOW_MATCH}"
                set w to first window of p
                set position of w to {{{x}, {y}}}
                set size of w to {{{width}, {height}}}
            end tell
        '''
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            raise PlatformError(result.stderr.strip())

    def turn_page(self, reverse: bool) -> None:
        key = 123 if reverse else 124
        self._osascript(f'tell application "System Events" to key code {key}')

    def capture_region(self, bounds: WindowBounds, output_path: str) -> bool:
        result = subprocess.run(
            ["screencapture", "-x",
             f"-R{bounds.x},{bounds.y},{bounds.width},{bounds.height}",
             output_path],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0


class WindowsBackend(PlatformBackend):
    """Windows backend using pywin32 and Pillow's ImageGrab.

    Runs the process as per-monitor DPI aware so window rectangles, screen
    metrics and screenshots are all expressed in the same physical pixels
    (mirroring how macOS transparently handles Retina scaling).
    """

    def __init__(self):
        import win32api
        import win32con
        import win32gui
        from PIL import ImageGrab

        self._win32api = win32api
        self._win32con = win32con
        self._win32gui = win32gui
        self._ImageGrab = ImageGrab
        self._set_dpi_awareness()

    @staticmethod
    def _set_dpi_awareness() -> None:
        import ctypes

        try:
            # PROCESS_PER_MONITOR_DPI_AWARE = 2 (Windows 8.1+)
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except (AttributeError, OSError):
                pass

    def _find_hwnd(self) -> int | None:
        matches: list[int] = []

        def _collect(hwnd, _):
            if not self._win32gui.IsWindowVisible(hwnd):
                return
            title = self._win32gui.GetWindowText(hwnd)
            if title and _WINDOW_MATCH.lower() in title.lower():
                matches.append(hwnd)

        self._win32gui.EnumWindows(_collect, None)
        return matches[0] if matches else None

    def _require_hwnd(self) -> int:
        hwnd = self._find_hwnd()
        if hwnd is None:
            raise PlatformError(
                "Error: Could not find the Kindle window.\n"
                "Make sure the Kindle app is running with a book open."
            )
        return hwnd

    def find_running_app(self, candidate_names: list[str]) -> str | None:
        hwnd = self._find_hwnd()
        if hwnd is None:
            return None
        # Report the matching candidate name if any, else a generic label.
        title = self._win32gui.GetWindowText(hwnd)
        for name in candidate_names:
            if name.lower() in title.lower():
                return name
        return candidate_names[-1] if candidate_names else _WINDOW_MATCH

    def activate(self, app_name: str) -> None:
        hwnd = self._require_hwnd()
        try:
            self._win32gui.ShowWindow(hwnd, self._win32con.SW_RESTORE)
            self._win32gui.SetForegroundWindow(hwnd)
        except Exception:
            # SetForegroundWindow can fail depending on focus state; not fatal.
            pass
        time.sleep(0.5)

    def screen_size(self) -> tuple[int, int]:
        # Work area excludes the taskbar so the resized window stays visible.
        monitor = self._win32api.MonitorFromPoint(
            (0, 0), self._win32con.MONITOR_DEFAULTTOPRIMARY
        )
        left, top, right, bottom = self._win32api.GetMonitorInfo(monitor)["Work"]
        return (right - left, bottom - top)

    def window_bounds(self, app_name: str) -> WindowBounds:
        hwnd = self._require_hwnd()
        left, top, right, bottom = self._win32gui.GetWindowRect(hwnd)
        return WindowBounds(left, top, right - left, bottom - top)

    def set_window_bounds(self, app_name: str, x: int, y: int, width: int, height: int) -> None:
        hwnd = self._require_hwnd()
        try:
            self._win32gui.MoveWindow(hwnd, x, y, width, height, True)
        except Exception as e:
            raise PlatformError(str(e))

    def turn_page(self, reverse: bool) -> None:
        VK_LEFT = 0x25
        VK_RIGHT = 0x27
        KEYEVENTF_KEYUP = 0x0002
        vk = VK_LEFT if reverse else VK_RIGHT
        self._win32api.keybd_event(vk, 0, 0, 0)
        self._win32api.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)

    def capture_region(self, bounds: WindowBounds, output_path: str) -> bool:
        try:
            bbox = (bounds.x, bounds.y, bounds.x + bounds.width, bounds.y + bounds.height)
            img = self._ImageGrab.grab(bbox=bbox, all_screens=True)
            img.save(output_path)
            return True
        except Exception:
            return False


def get_backend() -> PlatformBackend:
    """Return the platform backend for the current OS."""
    if sys.platform == "darwin":
        return MacBackend()
    if sys.platform.startswith("win"):
        return WindowsBackend()
    raise PlatformError(
        f"Error: Unsupported platform '{sys.platform}'. "
        "Only macOS and Windows are supported."
    )
