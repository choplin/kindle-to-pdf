# 📖 Kindle to PDF

KindleのMacアプリからページをスクリーンショットで自動撮影し、PDFにまとめるツール。

## ⚡ Setup

```bash
uv sync
```

### 🔐 macOS Permission

スクリプトはキーボード操作をシミュレートするため、**Accessibility権限**が必要です。

1. **System Settings** > **Privacy & Security** > **Accessibility** を開く
2. 使用するターミナルアプリ（Terminal, iTerm2, Warp等）を追加して有効化

## 🚀 Usage

Kindleアプリで書籍を開いた状態で実行します。

### Basic

```bash
# 50ページ撮影してPDF化
uv run kindle_to_pdf.py -n 50 output.pdf

# 自動で末尾を検出（ページが変わらなくなったら停止）
uv run kindle_to_pdf.py output.pdf
```

### Options

```
uv run kindle_to_pdf.py [OPTIONS] OUTPUT

Positional:
  OUTPUT                          Output PDF file path

Options:
  -n, --num-pages N               Capture exactly N pages
  --delay SECONDS                 Delay between page turns (default: 1.5)
  --crop LEFT,TOP,RIGHT,BOTTOM    Crop Kindle UI elements (pixels)
  --keep-images                   Keep individual page PNGs
  --output-dir DIR                Directory for page images
  --resume DIR                    Resume from existing image directory
  --similarity-threshold FLOAT    End detection threshold (default: 0.998)
  --dpi N                         PDF resolution (default: 150)
```

### Examples

```bash
# UI要素をトリミング（左30px、上60px、右30px、下40px）
uv run kindle_to_pdf.py --crop 30,60,30,40 -n 100 book.pdf

# ページ画像を残す
uv run kindle_to_pdf.py --keep-images --output-dir ./my_book -n 50 book.pdf

# 中断後に再開
uv run kindle_to_pdf.py --resume ./my_book book.pdf

# ページ送りを遅くする（アニメーションが遅い場合）
uv run kindle_to_pdf.py --delay 3.0 book.pdf
```

## 💡 Tips

- **Ctrl+C** で中断すると、撮影済みのページでPDFを生成します
- Retina displayでは自動的に高解像度（2x）で撮影されます
- `--crop` の値はKindleのウィンドウサイズやレイアウトに応じて調整してください
- 撮影中はKindleウィンドウに触れないでください
