"""Entry point for kindle-to-pdf."""

from kindle_to_pdf.backend import get_backend
from kindle_to_pdf.capture import CaptureSession
from kindle_to_pdf.config import Config
from kindle_to_pdf.kindle import KindleWindow
from kindle_to_pdf.pdf import apply_ocr, generate_pdf


def main():
    config = Config.from_cli()

    backend = get_backend()
    kindle = KindleWindow.find(backend)
    kindle.activate()
    if not config.no_resize:
        kindle.resize(config.aspect)

    b = kindle.bounds
    print(f"Kindle window ({kindle.app_name}): x={b.x}, y={b.y}, w={b.width}, h={b.height}")

    session = CaptureSession(config, kindle)
    try:
        pages = session.run()
    except KeyboardInterrupt:
        pages = session.pages
        print(f"\n\nInterrupted. Captured {len(pages)} pages.")

    if pages:
        print(f"\nGenerating PDF from {len(pages)} pages...")
        generate_pdf(pages, config.output, dpi=config.dpi)
        if config.ocr:
            print("Running OCR...")
            apply_ocr(config.output, language=config.ocr_lang, dpi=config.dpi)
    else:
        print("No pages captured.")

    if not config.keep_images and pages:
        session.cleanup()
    elif pages:
        print(f"Page images kept in: {session.output_dir}")
