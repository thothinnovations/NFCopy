"""
Runtime-generated system tray icons (no external image files required).
"""
from __future__ import annotations

from PIL import Image, ImageDraw


def draw_icon_connected(size: int = 64) -> Image.Image:
    """Create a green checkmark-in-circle icon."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    margin = 4
    d.ellipse((margin, margin, size - margin, size - margin),
              fill=(230, 255, 230, 255), outline=(0, 140, 0, 255), width=3)
    d.line([(18, 34), (28, 44), (48, 22)], fill=(0, 140, 0, 255), width=8)
    return img


def draw_icon_disconnected(size: int = 64) -> Image.Image:
    """Create a red cross-in-circle icon."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    margin = 4
    d.ellipse((margin, margin, size - margin, size - margin),
              fill=(255, 230, 230, 255), outline=(170, 0, 0, 255), width=3)
    d.line([(20, 20), (44, 44)], fill=(170, 0, 0, 255), width=8)
    d.line([(44, 20), (20, 44)], fill=(170, 0, 0, 255), width=8)
    return img
