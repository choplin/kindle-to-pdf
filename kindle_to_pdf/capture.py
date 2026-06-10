"""Page capture session and image utilities."""

from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
import sys
import time

from PIL import Image

from kindle_to_pdf.config import Config, CropInsets, WindowBounds
from kindle_to_pdf.kindle import KindleWindow


def _capture_screenshot(bounds: WindowBounds, output_path: str) -> bool:
    for attempt in range(2):
        result = subprocess.run(
            ["screencapture", "-x",
             f"-R{bounds.x},{bounds.y},{bounds.width},{bounds.height}",
             output_path],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and os.path.exists(output_path):
            return True
        if attempt == 0:
            time.sleep(1)
    return False


def _crop_image(image_path: str, insets: CropInsets):
    with Image.open(image_path) as img:
        w, h = img.size
        box = (insets.left, insets.top, w - insets.right, h - insets.bottom)
        cropped = img.crop(box)
        cropped.save(image_path)


def _compute_similarity(path_a: str, path_b: str) -> float:
    with Image.open(path_a) as img_a, Image.open(path_b) as img_b:
        thumb_a = img_a.resize((64, 64)).convert("L")
        thumb_b = img_b.resize((64, 64)).convert("L")
        pixels_a = list(thumb_a.getdata())
        pixels_b = list(thumb_b.getdata())
        total_diff = sum(abs(a - b) for a, b in zip(pixels_a, pixels_b))
        mean_diff = total_diff / (64 * 64 * 255)
        return 1.0 - mean_diff


def _find_existing_pages(directory: str) -> list[str]:
    pattern = os.path.join(directory, "page_*.png")
    files = glob.glob(pattern)
    files.sort(key=lambda f: int(re.search(r"page_(\d+)", f).group(1)))
    return files


class CaptureSession:
    """Manages the page capture loop and output directory."""

    _STALL_LIMIT = 3
    _BOUNDS_REFRESH_INTERVAL = 10

    def __init__(self, config: Config, kindle: KindleWindow):
        self._config = config
        self._kindle = kindle
        self._output_dir = self._resolve_output_dir()
        self._pages: list[str] = []

    @property
    def pages(self) -> list[str]:
        return list(self._pages)

    @property
    def output_dir(self) -> str:
        return self._output_dir

    def run(self) -> list[str]:
        """Execute the capture loop. Returns list of captured page paths."""
        os.makedirs(self._output_dir, exist_ok=True)
        print(f"Saving pages to: {self._output_dir}")

        existing = _find_existing_pages(self._output_dir)
        start_page = len(existing) + 1
        if existing:
            print(f"Found {len(existing)} existing pages, resuming from page {start_page}")

        self._pages = list(existing)
        prev_page_path = existing[-1] if existing else None

        auto_mode = self._config.num_pages is None
        max_pages = self._config.num_pages or 10000
        stall_count = 0

        mode_str = "auto-detect" if auto_mode else f"{max_pages} pages"
        print(f"Mode: {mode_str}, delay: {self._config.delay}s")
        print("Press Ctrl+C to stop and generate PDF from captured pages.\n")

        for page_num in range(start_page, start_page + max_pages):
            page_path = os.path.join(self._output_dir, f"page_{page_num:04d}.png")

            if (page_num - start_page) % self._BOUNDS_REFRESH_INTERVAL == 0 and page_num != start_page:
                self._kindle.refresh_bounds()

            if not _capture_screenshot(self._kindle.bounds, page_path):
                print(f"Warning: Failed to capture page {page_num}, skipping.")
                continue

            if self._config.crop:
                _crop_image(page_path, self._config.crop)

            self._pages.append(page_path)
            print(f"  Captured page {page_num}", end="")

            if auto_mode and prev_page_path:
                similarity = _compute_similarity(prev_page_path, page_path)
                if similarity > self._config.similarity_threshold:
                    stall_count += 1
                    print(f" (identical: {stall_count}/{self._STALL_LIMIT})", end="")
                    if stall_count >= self._STALL_LIMIT:
                        print("\nEnd of book detected.")
                        for dup in self._pages[-self._STALL_LIMIT:]:
                            os.remove(dup)
                        self._pages = self._pages[:-self._STALL_LIMIT]
                        break
                else:
                    stall_count = 0

            print()
            prev_page_path = page_path

            if not auto_mode and page_num >= start_page + max_pages - 1:
                break

            self._kindle.turn_page(self._config.reverse)
            time.sleep(self._config.delay)

        return list(self._pages)

    def cleanup(self):
        """Remove the output directory."""
        if os.path.isdir(self._output_dir):
            shutil.rmtree(self._output_dir, ignore_errors=True)
            print(f"Cleaned up: {self._output_dir}")

    def _resolve_output_dir(self) -> str:
        if self._config.resume:
            if not os.path.isdir(self._config.resume):
                print(f"Error: Resume directory not found: {self._config.resume}")
                sys.exit(1)
            return self._config.resume
        if self._config.output_dir:
            return self._config.output_dir
        return f"pages_{int(time.time())}"
