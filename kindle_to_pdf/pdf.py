"""PDF generation from page images."""

from __future__ import annotations

import os
import shutil
import sys

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


def apply_ocr(pdf_path: str, language: str = "jpn", dpi: int = 150):
    """Add OCR text layer to an existing PDF."""
    if not shutil.which("tesseract"):
        print("Error: tesseract is not installed.")
        if sys.platform == "darwin":
            print("  Install with: brew install tesseract tesseract-lang")
        elif sys.platform.startswith("win"):
            print("  Install from: https://github.com/UB-Mannheim/tesseract/wiki")
        else:
            print("  Install the 'tesseract-ocr' package for your distribution.")
        return False

    import ocrmypdf

    ocr_output = pdf_path + ".ocr.tmp"
    try:
        ocrmypdf.ocr(
            pdf_path,
            ocr_output,
            language=language,
            deskew=False,
            image_dpi=dpi,
            skip_text=True,
        )
        os.replace(ocr_output, pdf_path)
        size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
        print(f"OCR applied: {pdf_path} (lang={language}, {size_mb:.1f} MB)")
        return True
    except ocrmypdf.exceptions.MissingDependencyError as e:
        print(f"Error: OCR dependency missing: {e}")
        return False
    except ocrmypdf.exceptions.OcrMyPdfError as e:
        print(f"Error: OCR failed: {e}")
        if os.path.exists(ocr_output):
            os.remove(ocr_output)
        return False
