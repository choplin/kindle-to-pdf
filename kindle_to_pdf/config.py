"""Configuration and shared data models."""

from __future__ import annotations

import argparse
from dataclasses import dataclass


@dataclass(frozen=True)
class CropInsets:
    left: int
    top: int
    right: int
    bottom: int


@dataclass(frozen=True)
class WindowBounds:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class Config:
    output: str
    num_pages: int | None
    delay: float
    reverse: bool
    aspect: str
    no_resize: bool
    crop: CropInsets | None
    keep_images: bool
    output_dir: str | None
    resume: str | None
    similarity_threshold: float
    dpi: int

    @classmethod
    def from_cli(cls) -> Config:
        args = _parse_args()
        return cls(
            output=args.output,
            num_pages=args.num_pages,
            delay=args.delay,
            reverse=args.reverse,
            aspect=args.aspect,
            no_resize=args.no_resize,
            crop=CropInsets(*args.crop) if args.crop else None,
            keep_images=args.keep_images,
            output_dir=args.output_dir,
            resume=args.resume,
            similarity_threshold=args.similarity_threshold,
            dpi=args.dpi,
        )


def _parse_crop(value: str) -> tuple[int, int, int, int]:
    try:
        parts = [int(s.strip()) for s in value.split(",")]
        if len(parts) != 4:
            raise ValueError
        return tuple(parts)
    except ValueError:
        raise argparse.ArgumentTypeError(
            "Crop must be 4 comma-separated integers: LEFT,TOP,RIGHT,BOTTOM"
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture Kindle Mac app pages and compile into a PDF.",
    )
    parser.add_argument("output", help="Output PDF file path")
    parser.add_argument(
        "-n", "--num-pages", type=int, default=None,
        help="Number of pages to capture (default: auto-detect end)",
    )
    parser.add_argument(
        "--delay", type=float, default=3.0,
        help="Max wait time in seconds for page render (default: 3.0)",
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
        "--crop", type=_parse_crop, default=None,
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
