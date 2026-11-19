"""Images in prompts: scanned handwriting, photos and screenshots.

A prompt is either plain text or a list of parts, where each part is a text
string or a Path to an image. Images keep their place among the text parts, so
"PROBLEM: <image> PROPOSED SOLUTION: <image>" reaches the model in that order.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Union

Part = Union[str, Path]
Content = Union[str, list[Part]]

IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".gif": "image/gif", ".webp": "image/webp"}
MAX_BYTES = 5 * 1024 * 1024   # API limit per image
MAX_EDGE = 4096               # larger scans are downscaled; models resize anyway


def check_image(path: Path) -> None:
    if path.suffix.lower() not in IMAGE_TYPES:
        raise ValueError(f"{path}: unsupported image type {path.suffix!r}; "
                         f"use one of {', '.join(sorted(IMAGE_TYPES))} (convert HEIC/PDF scans first)")
    if not path.is_file():
        raise FileNotFoundError(f"image not found: {path}")


def load_image(path: Path) -> tuple[str, bytes]:
    """(media type, bytes) ready to send. Phone photos are rotated upright using
    their EXIF tag, and oversized scans are shrunk to fit the API limits."""
    check_image(path)
    data = path.read_bytes()
    media_type = IMAGE_TYPES[path.suffix.lower()]
    from PIL import Image, ImageOps  # installed with matplotlib

    with Image.open(path) as img:
        rotated = img.getexif().get(0x0112, 1) != 1
        too_big = len(data) > MAX_BYTES or max(img.size) > MAX_EDGE
        if not (rotated or too_big) or getattr(img, "is_animated", False):
            return media_type, data
        img = ImageOps.exif_transpose(img)
        img.thumbnail((MAX_EDGE, MAX_EDGE))
        buf = io.BytesIO()
        if img.mode in ("RGBA", "LA", "P"):
            img.save(buf, format="PNG", optimize=True)
            media_type = "image/png"
        else:
            img.convert("RGB").save(buf, format="JPEG", quality=90)
            media_type = "image/jpeg"
        return media_type, buf.getvalue()


def parts(content: Content) -> list[Part]:
    return [content] if isinstance(content, str) else list(content)


def text_only(content: Content) -> str:
    """The text of a prompt, with images shown as placeholders."""
    return "\n".join(p if isinstance(p, str) else f"[image: {p.name}]" for p in parts(content))


def to_anthropic(content: Content) -> str | list[dict]:
    if isinstance(content, str):
        return content
    blocks = []
    for p in content:
        if isinstance(p, str):
            blocks.append({"type": "text", "text": p})
        else:
            media_type, data = load_image(p)
            blocks.append({"type": "image", "source": {"type": "base64", "media_type": media_type,
                                                       "data": base64.b64encode(data).decode()}})
    return blocks


def to_openai(content: Content) -> str | list[dict]:
    if isinstance(content, str):
        return content
    blocks = []
    for p in content:
        if isinstance(p, str):
            blocks.append({"type": "text", "text": p})
        else:
            media_type, data = load_image(p)
            url = f"data:{media_type};base64,{base64.b64encode(data).decode()}"
            blocks.append({"type": "image_url", "image_url": {"url": url}})
    return blocks
