"""Image utilities shared across tool modules."""
from __future__ import annotations

import io

# MCP tool results that exceed ~1 MB are rejected by Claude Desktop and
# written to disk instead of being returned inline.  A 1200×900 Rendered
# PNG encodes to ~500 KB base64, which — after MCP JSON wrapping —
# regularly crosses that ceiling.
#
# We cap the raw PNG at 280 KB.  At ~33 % base64 overhead that becomes
# ~375 KB; even a verbose MCP envelope stays well below 1 MB.
_MAX_PNG_BYTES = 280_000
_SCALE_STEP = 0.75  # multiply each dimension by this per iteration


def shrink_png(img_bytes: bytes) -> bytes:
    """Return img_bytes downsized until the PNG is ≤ _MAX_PNG_BYTES.

    Uses Pillow (already a project dependency).  Returns the original bytes
    unchanged when they already fit.
    """
    if len(img_bytes) <= _MAX_PNG_BYTES:
        return img_bytes

    from PIL import Image as PILImage  # local import — fast path avoids it

    img = PILImage.open(io.BytesIO(img_bytes))
    while len(img_bytes) > _MAX_PNG_BYTES:
        w, h = img.size
        new_w, new_h = max(1, int(w * _SCALE_STEP)), max(1, int(h * _SCALE_STEP))
        img = img.resize((new_w, new_h), PILImage.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        img_bytes = buf.getvalue()
    return img_bytes
