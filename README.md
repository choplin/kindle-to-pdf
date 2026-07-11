# 📖 Kindle to PDF

A tool that automatically captures Kindle app pages as screenshots and compiles them into a PDF. Supports both **macOS** and **Windows**.

## ⚡ Setup

```bash
uv sync
```

All OS-dependent work (window control, screenshots, page turns) is consolidated in `PlatformBackend` in `kindle_to_pdf/backend.py`, and the appropriate `MacBackend` / `WindowsBackend` is selected automatically at runtime.

### 🔐 macOS Permission

Because the script simulates keyboard input, it requires **Accessibility permission**.

1. Open **System Settings** > **Privacy & Security** > **Accessibility**
2. Add and enable your terminal app (Terminal, iTerm2, Warp, etc.)

Capturing screenshots also requires **Screen Recording permission** (granted from the same Privacy & Security section).

### 🪟 Windows

No extra permission setup is needed. `uv sync` installs `pywin32` automatically (on Windows only).

- On high-DPI setups the process runs as per-monitor DPI aware, so window coordinates and screenshots are aligned in physical pixels.
- Page-turn keys are sent to the foreground Kindle window, so do not interact with other windows while capturing.

## 🚀 Usage

Run it with a book open in the Kindle app.

### Basic

```bash
# Capture 50 pages and build a PDF
uv run kindle_to_pdf.py -n 50 output.pdf

# Auto-detect the end (stop when the page stops changing)
uv run kindle_to_pdf.py output.pdf
```

### Options

```
uv run kindle_to_pdf.py [OPTIONS] OUTPUT

Positional:
  OUTPUT                          Output PDF file path

Options:
  -n, --num-pages N               Capture exactly N pages
  --delay SECONDS                 Max wait for page render (default: 3.0)
  --crop LEFT,TOP,RIGHT,BOTTOM    Crop Kindle UI elements (pixels)
  --keep-images                   Keep individual page PNGs
  --output-dir DIR                Directory for page images
  --resume DIR                    Resume from existing image directory
  --similarity-threshold FLOAT    End detection threshold (default: 0.998)
  --dpi N                         PDF resolution (default: 150)
```

### Examples

```bash
# Crop UI elements (left 30px, top 60px, right 30px, bottom 40px)
uv run kindle_to_pdf.py --crop 30,60,30,40 -n 100 book.pdf

# Keep the page images
uv run kindle_to_pdf.py --keep-images --output-dir ./my_book -n 50 book.pdf

# Resume after an interruption
uv run kindle_to_pdf.py --resume ./my_book book.pdf

# Slow down page turns (for slow animations)
uv run kindle_to_pdf.py --delay 3.0 book.pdf
```

## 💡 Tips

- Interrupting with **Ctrl+C** generates a PDF from the pages captured so far
- On Retina displays, pages are automatically captured at high resolution (2x)
- Adjust the `--crop` values to match the Kindle window size and layout
- Do not touch the Kindle window while capturing
