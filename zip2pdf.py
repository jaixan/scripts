#!/usr/bin/env python3
"""Turn a .zip of images into a .pdf with one image per page.

Usage: python3 zip2pdf.py [--progress] images.zip [output.pdf]
  --progress  print "PROGRESS <done> <total>" after each page (used by zip2pptx-progress.js)
Requires: pip install img2pdf pillow
JPEG and PNG images are embedded as-is (no recompression); other formats are converted to PNG.
"""
import io
import re
import sys
import zipfile
from pathlib import Path

import img2pdf
from PIL import Image

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".webp"}


def natural_key(name):
    # Sort "img2" before "img10".
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", name)]


def main():
    args = sys.argv[1:]
    progress = "--progress" in args
    args = [a for a in args if a != "--progress"]
    if not args:
        sys.exit(__doc__)
    zip_path = Path(args[0])
    out_path = Path(args[1]) if len(args) > 1 else zip_path.with_suffix(".pdf")

    pages = []
    with zipfile.ZipFile(zip_path) as zf:
        names = sorted(
            (n for n in zf.namelist()
             if Path(n).suffix.lower() in IMAGE_EXTS
             and not n.startswith("__MACOSX/")
             and not Path(n).name.startswith(".")),
            key=natural_key,
        )
        if not names:
            sys.exit(f"No images found in {zip_path}")

        for i, name in enumerate(names, 1):
            data = zf.read(name)
            with Image.open(io.BytesIO(data)) as img:
                # img2pdf only embeds JPEG/PNG without an alpha channel; convert the rest to PNG.
                has_alpha = img.mode in ("RGBA", "LA", "PA") or "transparency" in img.info
                if img.format not in ("JPEG", "PNG") or has_alpha:
                    img.seek(0)  # first frame of animated GIF/WebP
                    rgba = img.convert("RGBA")
                    flat = Image.new("RGB", rgba.size, "white")  # transparency → white
                    flat.paste(rgba, mask=rgba.getchannel("A"))
                    buf = io.BytesIO()
                    flat.save(buf, "PNG")
                    data = buf.getvalue()
            pages.append(data)
            if progress:
                print(f"PROGRESS {i} {len(names)}", flush=True)

    if progress:
        print("SAVING", flush=True)

    out_path.write_bytes(img2pdf.convert(pages))
    print(f"Wrote {len(names)} pages to {out_path}")


if __name__ == "__main__":
    main()
