"""Create a simple sample PDF for testing the demo pipeline.

This script uses Pillow to render a multi-paragraph sample contract into a PDF file.
"""
from PIL import Image, ImageDraw, ImageFont
import os


def create_sample(out_path: str):
    text = """
Sample Agreement

This Agreement is made between Example Corp. ("Example") and Supplier LLC ("Supplier").

1. Term. The term starts on 2025-01-01 and ends on 2026-01-01.

2. Payment. Total amount payable is $12,345.00. Payments shall be made within 30 days.

3. Confidentiality. Both parties agree to keep confidential information secret.

IN WITNESS WHEREOF, the parties have executed this Agreement.
"""

    img = Image.new("RGB", (1200, 1600), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    d.multiline_text((50, 50), text, fill=(0, 0, 0), font=font)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    img.save(out_path, "PDF", resolution=100.0)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("out", nargs="?", default="demo/sample.pdf")
    args = p.parse_args()
    create_sample(args.out)
    print("Wrote sample PDF to", args.out)
