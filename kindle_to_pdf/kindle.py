"""Kindle application window control, delegated to a platform backend."""

from __future__ import annotations

import sys

from kindle_to_pdf.backend import PlatformBackend, PlatformError
from kindle_to_pdf.config import WindowBounds

_APP_NAMES = ["Amazon Kindle", "Kindle"]


class KindleWindow:
    """Handle to the running Kindle application window."""

    def __init__(self, app_name: str, backend: PlatformBackend):
        self._app_name = app_name
        self._backend = backend
        self._bounds: WindowBounds | None = None

    @classmethod
    def find(cls, backend: PlatformBackend) -> KindleWindow:
        """Detect running Kindle app and return a window handle."""
        name = backend.find_running_app(_APP_NAMES)
        if name is None:
            print("Error: Kindle app is not running. Please open Kindle and a book first.")
            sys.exit(1)
        return cls(name, backend)

    @property
    def app_name(self) -> str:
        return self._app_name

    @property
    def backend(self) -> PlatformBackend:
        return self._backend

    @property
    def bounds(self) -> WindowBounds:
        if self._bounds is None:
            self.refresh_bounds()
        return self._bounds

    def activate(self):
        """Bring the Kindle app to the foreground."""
        self._backend.activate(self._app_name)

    def resize(self, aspect: str):
        """Resize and position window to max size within the given aspect ratio."""
        w_ratio, h_ratio = (int(x) for x in aspect.split(":"))
        target = w_ratio / h_ratio

        screen_w, screen_h = self._backend.screen_size()
        top_margin = 25
        avail_h = screen_h - top_margin

        if avail_h * target <= screen_w:
            new_h = avail_h
            new_w = int(avail_h * target)
        else:
            new_w = screen_w
            new_h = int(screen_w / target)

        new_x = (screen_w - new_w) // 2
        new_y = top_margin

        try:
            self._backend.set_window_bounds(self._app_name, new_x, new_y, new_w, new_h)
        except PlatformError as e:
            print(f"Warning: Could not resize Kindle window: {e.message}")

        self._bounds = WindowBounds(new_x, new_y, new_w, new_h)
        print(f"Resized window: {new_w}x{new_h} at ({new_x},{new_y}) (aspect {aspect})")

    def refresh_bounds(self):
        """Re-fetch window bounds from the platform backend."""
        try:
            self._bounds = self._backend.window_bounds(self._app_name)
        except PlatformError as e:
            print(e.message)
            sys.exit(e.exit_code)

    def turn_page(self, reverse: bool = False):
        """Simulate pressing arrow key to turn to the next page."""
        self._backend.turn_page(reverse)
