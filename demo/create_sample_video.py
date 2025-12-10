"""Create a short sample MP4 for demo use (simulated worker movement frames).

This script creates a few frames with text noting frame index and encodes them to MP4
using imageio-ffmpeg. It's lightweight and suitable for testing the pipeline.
"""
from PIL import Image, ImageDraw, ImageFont
import imageio
import os


def create_video(out_path: str, frames: int = 90, fps: int = 15):
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    imgs = []
    for i in range(frames):
        img = Image.new("RGB", (640, 360), color=(255, 255, 255))
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
        text = f"Frame {i}"
        d.text((50, 160), text, fill=(0, 0, 0), font=font)
        # Draw a simulated worker box moving across the frame
        x = 50 + (i * 4) % 500
        d.rectangle([x, 120, x + 60, 300], outline=(255, 0, 0), width=3)
        import numpy as _np
        imgs.append(_np.array(img))

    imageio.mimsave(out_path, imgs, fps=fps)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("out", nargs="?", default="demo/sample.mp4")
    args = p.parse_args()
    create_video(args.out)
    print("Wrote sample video to", args.out)
