# 📖 Kindle to PDF

> Turn a book open in the Kindle desktop app into a PDF, one screenshot at a time.

Kindle to PDF drives the Kindle app on **macOS** and **Windows**: it brings the window to the front, captures each page, turns to the next one, and compiles everything into a single PDF — optionally with a searchable OCR text layer.

```bash
uv run kindle-to-pdf book.pdf
```

An example session, auto-detecting the end of the book:

```
Kindle window (Amazon Kindle): x=380, y=25, w=1140, h=1520
Resized window: 1140x1520 at (380,25) (aspect 3:4)
Saving pages to: pages_1752200000
Mode: auto-detect, max wait: 3.0s
Press Ctrl+C to stop and generate PDF from captured pages.

  Captured page 1
  Captured page 2
  ...
  Captured page 312 (identical: 3/3)
End of book detected.

Generating PDF from 309 pages...
PDF created: book.pdf (309 pages, 84.3 MB)
```

## ✨ Why Kindle to PDF?

- **Stop babysitting the capture.** Page turns wait for the page to actually finish rendering, and the run stops on its own once the book stops changing — you do not have to count pages or guess a delay.
- **Survive interruptions.** Ctrl+C still produces a PDF from what was captured, and a later run picks up from the images already on disk.
- **Read it anywhere.** Page images become one PDF, and `--ocr` adds a text layer so the result is searchable and selectable.
- **Same workflow on macOS and Windows.** Every OS-dependent operation lives behind a single backend interface, so the commands and options are identical on both.

## 📋 Requirements

- Python 3.13 (the version pinned in `.python-version`; `pyproject.toml` requires 3.12+)
- [uv](https://docs.astral.sh/uv/)
- The Kindle desktop app, running with a book open
- macOS or Windows — no other platform is supported
- `tesseract` on `PATH`, only if you use `--ocr`

## ⚡ Setup

```bash
uv sync
```

This installs the dependencies and the `kindle-to-pdf` command into the project environment. `uv run python -m kindle_to_pdf` runs the same entry point if you prefer the module form.

### 🔐 macOS permissions

The tool simulates keyboard input and takes screenshots, so grant your terminal app (Terminal, iTerm2, Warp, …) two permissions under **System Settings > Privacy & Security**:

1. **Accessibility** — required to read the Kindle window position and send page-turn keys.
2. **Screen Recording** — required to capture the window.

Without Accessibility permission the run exits with a message pointing at this setting.

### 🪟 Windows

No extra permission setup is needed; `uv sync` installs `pywin32` automatically on Windows only.

- The process runs as per-monitor DPI aware, so window coordinates and screenshots line up in physical pixels on high-DPI displays.
- Page-turn keys go to the foreground window, so leave other windows alone while capturing.

### 🔤 OCR (optional)

`--ocr` drives `tesseract` through [OCRmyPDF](https://ocrmypdf.readthedocs.io/):

- macOS: `brew install tesseract tesseract-lang`
- Windows: [UB Mannheim installer](https://github.com/UB-Mannheim/tesseract/wiki)

If `tesseract` is missing, the PDF is still produced and only the OCR step is skipped.

## 🚀 Quick start

1. Open the Kindle app and the book you want, at the first page to capture.
2. Run the tool and leave the machine alone until it finishes:

   ```bash
   uv run kindle-to-pdf book.pdf
   ```

3. The window is resized to a 3:4 aspect ratio, pages are captured into `pages_<timestamp>/`, and capture stops once three consecutive pages look identical.
4. `book.pdf` is written, and the page images are deleted unless you passed `--keep-images`.

To capture a fixed number of pages instead of detecting the end:

```bash
uv run kindle-to-pdf -n 50 book.pdf
```

## 🛠 Usage

```
uv run kindle-to-pdf [OPTIONS] OUTPUT
```

`OUTPUT` is the path of the PDF to create.

### Capture

| Option | Default | Description |
| --- | --- | --- |
| `-n`, `--num-pages N` | auto-detect | Capture exactly N pages instead of detecting the end |
| `--delay SECONDS` | `3.0` | Maximum wait for a page to finish rendering |
| `--reverse` | off | Turn pages with the left arrow, for right-to-left books |
| `--similarity-threshold FLOAT` | `0.998` | How similar two pages must be to count as unchanged |

### Window

| Option | Default | Description |
| --- | --- | --- |
| `--aspect W:H` | `3:4` | Resize the Kindle window to this aspect ratio before capturing |
| `--no-resize` | off | Leave the window size and position as-is |
| `--crop L,T,R,B` | none | Crop that many pixels off each edge of every page |

### Images and output

| Option | Default | Description |
| --- | --- | --- |
| `--output-dir DIR` | `./pages_<timestamp>` | Where page PNGs are written |
| `--keep-images` | off | Keep the page PNGs after the PDF is built |
| `--resume DIR` | none | Continue a run from an existing image directory |
| `--resize-width PX` | none | Cap the image width; height scales proportionally |
| `--resize-scale PERCENT` | none | Scale images by a percentage, e.g. `50` for half size |
| `--dpi N` | `150` | Resolution recorded in the PDF |

### OCR

| Option | Default | Description |
| --- | --- | --- |
| `--ocr` | off | Add a searchable text layer with tesseract |
| `--ocr-lang LANG` | `jpn` | OCR language; combine with `+`, e.g. `jpn+eng` |

### Examples

```bash
# Crop the Kindle UI: 30px left, 60px top, 30px right, 40px bottom
uv run kindle-to-pdf --crop 30,60,30,40 -n 100 book.pdf

# Right-to-left book, with a searchable Japanese + English text layer
uv run kindle-to-pdf --reverse --ocr --ocr-lang jpn+eng book.pdf

# Keep the page images in a named directory
uv run kindle-to-pdf --keep-images --output-dir ./my_book book.pdf

# Resume after an interruption, reusing the images already captured
uv run kindle-to-pdf --resume ./my_book book.pdf

# Halve the image size to keep the PDF small
uv run kindle-to-pdf --resize-scale 50 book.pdf
```

## 🧩 How it works

Every run walks the same path: find the window, capture, turn, repeat, then build the PDF.

| Module | Responsibility |
| --- | --- |
| `kindle_to_pdf/main.py` | Orchestrates one run: window setup, capture session, PDF generation, cleanup |
| `kindle_to_pdf/config.py` | CLI argument parsing and the shared `Config`, `CropInsets`, `WindowBounds` models |
| `kindle_to_pdf/backend.py` | `PlatformBackend` interface plus `MacBackend` / `WindowsBackend`, chosen by `get_backend()` |
| `kindle_to_pdf/kindle.py` | `KindleWindow` — locating, activating and resizing the app window, and turning pages |
| `kindle_to_pdf/capture.py` | `CaptureSession` — the capture loop, render waiting, cropping, resizing, end detection |
| `kindle_to_pdf/pdf.py` | `generate_pdf()` and the optional `apply_ocr()` step |

Two details are worth knowing because they shape the options above:

- **Render waiting is adaptive.** After a page turn the tool polls screenshots every 0.2s and continues as soon as two consecutive shots match. `--delay` is the ceiling on that wait, not a fixed sleep.
- **End detection is visual.** In auto mode a page more similar to its predecessor than `--similarity-threshold` counts as a stall; after three in a row the run stops and those three duplicates are discarded.

All OS-dependent work — window control, screenshots, key events — is confined to `backend.py`. No other module branches on the platform.

## 💡 Tips and limitations

- **Do not touch the machine while capturing.** Page-turn keys go to the foreground window, and screenshots capture whatever is on screen.
- **Ctrl+C is safe.** It stops the loop and builds a PDF from the pages captured so far.
- **Resuming is per-directory.** Pointing `--output-dir` or `--resume` at a directory that already holds `page_*.png` continues from the next number, so leave the book on the right page before restarting.
- **Retina displays capture at 2x** with no extra configuration; use `--resize-width` or `--resize-scale` if the resulting PDF is too large.
- **Tune `--crop` per book.** Kindle UI chrome differs by window size and layout, so capture a few pages with `--keep-images` and check them before running a whole book.
- **The output is images, not text.** Without `--ocr` the PDF has no selectable text, and OCR quality depends entirely on tesseract.
