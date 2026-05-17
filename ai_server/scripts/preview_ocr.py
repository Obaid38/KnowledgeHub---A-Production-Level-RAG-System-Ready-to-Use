#!/usr/bin/env python3
"""
Quick OCR preview — shows raw text extracted from an image by Tesseract.

Usage:
    python scripts/preview_ocr.py <image_path>
    python scripts/preview_ocr.py E:/path/to/image.png
"""

import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/preview_ocr.py <image_path>")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"ERROR: file not found: {path}")
        sys.exit(1)

    from PIL import Image
    import pytesseract

    img = Image.open(path)
    text = pytesseract.image_to_string(img, lang="eng")

    print(f"File    : {path.name}")
    print(f"Size    : {path.stat().st_size:,} bytes")
    print(f"Dims    : {img.width}x{img.height}px")
    print(f"Chars   : {len(text.strip())}")
    print(f"{'─' * 60}")
    print(text)
    print(f"{'─' * 60}")


if __name__ == "__main__":
    main()
