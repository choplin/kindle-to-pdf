#!/usr/bin/env python3
"""Capture Kindle Mac app pages as screenshots and compile them into a PDF."""

import argparse
import glob
import os
import re
import subprocess
import sys
import time

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow is required. Install it with:")
    print("  uv sync")
    sys.exit(1)

KINDLE_APP_NAMES = ["Amazon Kindle", "Kindle"]


def _run_osascript(script: str, timeout: int = 5) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=timeout,
    )


def find_kindle_app() -> str:
    """Detect the running Kindle app name."""
    for name in KINDLE_APP_NAMES:
        result = _run_osascript(f'application "{name}" is running')
        if result.stdout.strip() == "true":
            return name
    return ""


def activate_kindle(app_name: str):
    """Bring the Kindle app to the foreground."""
    _run_osascript(f'tell application "{app_name}" to activate')
    time.sleep(0.5)


def get_screen_size() -> tuple[int, int]:
    """Get the main screen size (width, height) in points."""
    result = subprocess.run(
        ["osascript", "-l", "JavaScript", "-e",
         'ObjC.import("AppKit"); var s = $.NSScreen.mainScreen.frame; '
         'JSON.stringify({w: s.size.width, h: s.size.height})'],
        capture_output=True, text=True, timeout=5,
    )
    import json
    data = json.loads(result.stdout.strip())
    return (int(data["w"]), int(data["h"]))


def resize_kindle_window(aspect: str):
    """Resize and position Kindle window to max size within the given aspect ratio."""
    w_ratio, h_ratio = (int(x) for x in aspect.split(":"))
    target = w_ratio / h_ratio

    screen_w, screen_h = get_screen_size()
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
    print(f"Resized window: {new_w}x{new_h} at ({new_x},{new_y}) (aspect {aspect})")


def get_kindle_window() -> tuple[int, int, int, int]:
    """Get Kindle window bounds as (x, y, width, height) via System Events."""
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
        return (x, y, w, h)
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


def capture_page(region: tuple[int, int, int, int], output_path: str) -> bool:
    """Capture a screenshot of the specified region."""
    x, y, w, h = region
    for attempt in range(2):
        result = subprocess.run(
            ["screencapture", "-x", f"-R{x},{y},{w},{h}", output_path],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and os.path.exists(output_path):
            return True
        if attempt == 0:
            time.sleep(1)
    return False


def crop_image(image_path: str, crop_insets: tuple[int, int, int, int]):
    """Crop an image by the given insets (left, top, right, bottom)."""
    left, top, right, bottom = crop_insets
    with Image.open(image_path) as img:
        w, h = img.size
        box = (left, top, w - right, h - bottom)
        cropped = img.crop(box)
        cropped.save(image_path)


def turn_page(reverse: bool = False):
    """Simulate pressing arrow key to turn to the next page."""
    # key code 123 = left arrow, 124 = right arrow
    key = 123 if reverse else 124
    subprocess.run(
        ["osascript", "-e",
         f'tell application "System Events" to key code {key}'],
        capture_output=True, text=True, timeout=5,
    )


def compute_similarity(path_a: str, path_b: str) -> float:
    """Compute similarity (0.0 to 1.0) between two images using downscaled pixel comparison."""
    with Image.open(path_a) as img_a, Image.open(path_b) as img_b:
        # Downscale to 64x64 grayscale for fast comparison
        thumb_a = img_a.resize((64, 64)).convert("L")
        thumb_b = img_b.resize((64, 64)).convert("L")
        pixels_a = list(thumb_a.getdata())
        pixels_b = list(thumb_b.getdata())
        total_diff = sum(abs(a - b) for a, b in zip(pixels_a, pixels_b))
        mean_diff = total_diff / (64 * 64 * 255)
        return 1.0 - mean_diff


def find_existing_pages(directory: str) -> list[str]:
    """Find existing page images in a directory, sorted numerically."""
    pattern = os.path.join(directory, "page_*.png")
    files = glob.glob(pattern)
    files.sort(key=lambda f: int(re.search(r"page_(\d+)", f).group(1)))
    return files


def generate_pdf(image_paths: list[str], output_path: str, dpi: int = 150):
    """Combine page images into a single PDF."""
    if not image_paths:
        print("No images to combine.")
        return

    images = []
    for path in image_paths:
        img = Image.open(path).convert("RGB")
        images.append(img)

    images[0].save(
        output_path, "PDF",
        save_all=True,
        append_images=images[1:],
        resolution=dpi,
    )

    for img in images:
        img.close()

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"PDF created: {output_path} ({len(image_paths)} pages, {size_mb:.1f} MB)")


def parse_crop(value: str) -> tuple[int, int, int, int]:
    """Parse crop insets from 'L,T,R,B' string."""
    try:
        parts = [int(s.strip()) for s in value.split(",")]
        if len(parts) != 4:
            raise ValueError
        return tuple(parts)
    except ValueError:
        raise argparse.ArgumentTypeError(
            "Crop must be 4 comma-separated integers: LEFT,TOP,RIGHT,BOTTOM"
        )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Capture Kindle Mac app pages and compile into a PDF.",
    )
    parser.add_argument("output", help="Output PDF file path")
    parser.add_argument(
        "-n", "--num-pages", type=int, default=None,
        help="Number of pages to capture (default: auto-detect end)",
    )
    parser.add_argument(
        "--delay", type=float, default=1.5,
        help="Delay in seconds between page turns (default: 1.5)",
    )
    parser.add_argument(
        "--reverse", action="store_true",
        help="Use left arrow for page turn (for right-to-left books)",
    )
    parser.add_argument(
        "--aspect", default="3:4", metavar="W:H",
        help="Resize Kindle window to aspect ratio (default: 3:4)",
    )
    parser.add_argument(
        "--no-resize", action="store_true",
        help="Skip window resize, use current window as-is",
    )
    parser.add_argument(
        "--crop", type=parse_crop, default=None,
        help="Crop insets as LEFT,TOP,RIGHT,BOTTOM pixels",
    )
    parser.add_argument(
        "--keep-images", action="store_true",
        help="Keep individual page images after PDF creation",
    )
    parser.add_argument(
        "--output-dir", default=None,
        help="Directory for page images (default: ./pages_<timestamp>)",
    )
    parser.add_argument(
        "--resume", default=None, metavar="DIR",
        help="Resume capture from an existing image directory",
    )
    parser.add_argument(
        "--similarity-threshold", type=float, default=0.998,
        help="Threshold for end-of-book detection (default: 0.998)",
    )
    parser.add_argument(
        "--dpi", type=int, default=150,
        help="DPI for PDF output (default: 150)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Preflight checks
    app_name = find_kindle_app()
    if not app_name:
        print("Error: Kindle app is not running. Please open Kindle and a book first.")
        sys.exit(1)

    activate_kindle(app_name)

    if not args.no_resize:
        resize_kindle_window(args.aspect)

    region = get_kindle_window()
    print(f"Kindle window ({app_name}): x={region[0]}, y={region[1]}, w={region[2]}, h={region[3]}")

    # Set up output directory
    if args.resume:
        output_dir = args.resume
        if not os.path.isdir(output_dir):
            print(f"Error: Resume directory not found: {output_dir}")
            sys.exit(1)
    elif args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = f"pages_{int(time.time())}"

    os.makedirs(output_dir, exist_ok=True)
    print(f"Saving pages to: {output_dir}")

    # Determine starting page
    existing = find_existing_pages(output_dir)
    start_page = len(existing) + 1
    if existing:
        print(f"Found {len(existing)} existing pages, resuming from page {start_page}")

    auto_mode = args.num_pages is None
    max_pages = args.num_pages or 10000  # Safety limit for auto mode
    stall_count = 0
    prev_page_path = existing[-1] if existing else None
    captured_pages = list(existing)

    mode_str = "auto-detect" if auto_mode else f"{max_pages} pages"
    print(f"Mode: {mode_str}, delay: {args.delay}s")
    print("Press Ctrl+C to stop and generate PDF from captured pages.\n")

    try:
        for page_num in range(start_page, start_page + max_pages):
            page_path = os.path.join(output_dir, f"page_{page_num:04d}.png")

            # Re-fetch window bounds every 10 pages
            if (page_num - start_page) % 10 == 0 and page_num != start_page:
                region = get_kindle_window()

            if not capture_page(region, page_path):
                print(f"Warning: Failed to capture page {page_num}, skipping.")
                continue

            # Apply crop if specified
            if args.crop:
                crop_image(page_path, args.crop)

            captured_pages.append(page_path)
            print(f"  Captured page {page_num}", end="")

            # Auto-detect end of book
            if auto_mode and prev_page_path:
                similarity = compute_similarity(prev_page_path, page_path)
                if similarity > args.similarity_threshold:
                    stall_count += 1
                    print(f" (identical: {stall_count}/3)", end="")
                    if stall_count >= 3:
                        print("\nEnd of book detected.")
                        # Remove duplicate pages
                        for dup in captured_pages[-3:]:
                            os.remove(dup)
                        captured_pages = captured_pages[:-3]
                        break
                else:
                    stall_count = 0

            print()
            prev_page_path = page_path

            # Check if we've reached the target
            if not auto_mode and page_num >= start_page + max_pages - 1:
                break

            # Turn page and wait
            turn_page(reverse=args.reverse)
            time.sleep(args.delay)

    except KeyboardInterrupt:
        print(f"\n\nInterrupted. Captured {len(captured_pages)} pages.")

    # Generate PDF
    if captured_pages:
        print(f"\nGenerating PDF from {len(captured_pages)} pages...")
        generate_pdf(captured_pages, args.output, dpi=args.dpi)
    else:
        print("No pages captured.")

    # Cleanup
    if not args.keep_images and captured_pages:
        import shutil
        shutil.rmtree(output_dir, ignore_errors=True)
        print(f"Cleaned up: {output_dir}")
    elif captured_pages:
        print(f"Page images kept in: {output_dir}")


if __name__ == "__main__":
    main()
