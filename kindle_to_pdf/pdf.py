"""PDF generation from page images."""

from __future__ import annotations

import os

from PIL import Image


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
