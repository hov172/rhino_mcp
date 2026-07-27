"""
Tools for image format conversion and viewport image export.
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Convert Image", destructiveHint=True))
    def convert_image(
        source_path: str,
        output_path: str,
        width: int | None = None,
        height: int | None = None,
        quality: int = 90,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Convert an existing image file from one format to another.

        Supports PNG, JPG, BMP, TIFF, and GIF as input and output formats.
        EXR and WebP are not natively supported by..."""
        code = (
            "_mcp_source = {source}\n"
            "_mcp_output = {output}\n"
            "_mcp_width = {width}\n"
            "_mcp_height = {height}\n"
            "_mcp_quality = {quality}\n"
            "{script}"
        ).format(
            source=json.dumps(source_path),
            output=json.dumps(output_path),
            width=repr(width),
            height=repr(height),
            quality=json.dumps(quality),
            script=_CONVERT_IMAGE_SCRIPT,
        )
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Export Viewport Image", destructiveHint=True))
    def export_viewport_image(
        path: str,
        width: int = 1920,
        height: int = 1080,
        display_mode: str = "Shaded",
        transparent_background: bool = False,
        quality: int = 95,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Capture the active Rhino viewport and save it to an image file.

        ``path`` extension controls the output format (.png, .jpg, .bmp,
        .tiff).  ``display_mode`` may be one of: Wireframe,..."""
        from rhmcp.tools_helpers.security import clamp
        width = clamp(width, 1, 8192)
        height = clamp(height, 1, 8192)
        quality = clamp(quality, 1, 100)
        code = (
            "_mcp_path = {path}\n"
            "_mcp_width = {width}\n"
            "_mcp_height = {height}\n"
            "_mcp_display_mode = {display_mode}\n"
            "_mcp_transparent = {transparent}\n"
            "_mcp_quality = {quality}\n"
            "{script}"
        ).format(
            path=json.dumps(path),
            width=json.dumps(width),
            height=json.dumps(height),
            display_mode=json.dumps(display_mode),
            transparent=repr(transparent_background),
            quality=json.dumps(quality),
            script=_EXPORT_VIEWPORT_SCRIPT,
        )
        return rhino.execute_python(code, rhino_id=rhino_id)


# ---------------------------------------------------------------------------
# Embedded Python scripts executed inside Rhino
# ---------------------------------------------------------------------------

_CONVERT_IMAGE_SCRIPT = r'''
import os
import System.Drawing
import System.Drawing.Imaging as _Imaging

_EXT_MAP = {
    ".png":  _Imaging.ImageFormat.Png,
    ".jpg":  _Imaging.ImageFormat.Jpeg,
    ".jpeg": _Imaging.ImageFormat.Jpeg,
    ".bmp":  _Imaging.ImageFormat.Bmp,
    ".tiff": _Imaging.ImageFormat.Tiff,
    ".tif":  _Imaging.ImageFormat.Tiff,
    ".gif":  _Imaging.ImageFormat.Gif,
}

_UNSUPPORTED = {".exr", ".webp"}

src_ext = os.path.splitext(_mcp_source)[1].lower()
dst_ext = os.path.splitext(_mcp_output)[1].lower()

if src_ext in _UNSUPPORTED:
    result = {
        "ok": False,
        "error": (
            "Source format '{}' is not natively supported by System.Drawing. "
            "EXR and WebP require a third-party codec. "
            "Convert the file to PNG or TIFF first."
        ).format(src_ext),
    }
elif dst_ext in _UNSUPPORTED:
    result = {
        "ok": False,
        "error": (
            "Output format '{}' is not natively supported by System.Drawing. "
            "EXR and WebP cannot be written without a third-party codec. "
            "Use PNG, JPG, BMP, or TIFF instead."
        ).format(dst_ext),
    }
elif dst_ext not in _EXT_MAP:
    result = {
        "ok": False,
        "error": "Unrecognised output extension '{}'. Supported: .png .jpg .bmp .tiff .gif".format(dst_ext),
    }
else:
    try:
        bitmap = System.Drawing.Bitmap(_mcp_source)
        orig_w = bitmap.Width
        orig_h = bitmap.Height

        # Resize if requested
        target_w = int(_mcp_width)  if _mcp_width  is not None else orig_w
        target_h = int(_mcp_height) if _mcp_height is not None else orig_h

        if target_w != orig_w or target_h != orig_h:
            resized = System.Drawing.Bitmap(target_w, target_h)
            g = System.Drawing.Graphics.FromImage(resized)
            g.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.HighQualityBicubic
            g.DrawImage(bitmap, 0, 0, target_w, target_h)
            g.Dispose()
            bitmap.Dispose()
            bitmap = resized

        img_format = _EXT_MAP[dst_ext]

        # Ensure output directory exists
        out_dir = os.path.dirname(_mcp_output)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir)

        if dst_ext in (".jpg", ".jpeg"):
            # Use EncoderParameters to control JPEG quality
            jpeg_codec = None
            for codec in _Imaging.ImageCodecInfo.GetImageEncoders():
                if codec.FormatID == _Imaging.ImageFormat.Jpeg.Guid:
                    jpeg_codec = codec
                    break

            if jpeg_codec is not None:
                enc_params = _Imaging.EncoderParameters(1)
                enc_params.Param[0] = _Imaging.EncoderParameter(
                    _Imaging.Encoder.Quality,
                    int(max(1, min(100, int(_mcp_quality))))
                )
                bitmap.Save(_mcp_output, jpeg_codec, enc_params)
            else:
                bitmap.Save(_mcp_output, img_format)
        else:
            bitmap.Save(_mcp_output, img_format)

        bitmap.Dispose()

        result = {
            "ok": True,
            "source_path": _mcp_source,
            "output_path": _mcp_output,
            "format": dst_ext.lstrip(".").upper(),
            "width": target_w,
            "height": target_h,
        }
    except Exception as _ex:
        result = {"ok": False, "error": str(_ex)}
'''


_EXPORT_VIEWPORT_SCRIPT = r'''
import os
import Rhino
import System.Drawing
import System.Drawing.Imaging as _Imaging

_EXT_MAP = {
    ".png":  _Imaging.ImageFormat.Png,
    ".jpg":  _Imaging.ImageFormat.Jpeg,
    ".jpeg": _Imaging.ImageFormat.Jpeg,
    ".bmp":  _Imaging.ImageFormat.Bmp,
    ".tiff": _Imaging.ImageFormat.Tiff,
    ".tif":  _Imaging.ImageFormat.Tiff,
}

dst_ext = os.path.splitext(_mcp_path)[1].lower()

if dst_ext not in _EXT_MAP:
    result = {
        "ok": False,
        "error": "Unrecognised output extension '{}'. Supported: .png .jpg .bmp .tiff".format(dst_ext),
    }
else:
    try:
        doc = Rhino.RhinoDoc.ActiveDoc
        view = doc.Views.ActiveView
        if view is None:
            result = {"ok": False, "error": "No active viewport found."}
        else:
            # Switch display mode if requested
            vp = view.ActiveViewport
            _DM_MAP = {
                "wireframe": "Wireframe",
                "shaded":    "Shaded",
                "rendered":  "Rendered",
                "arctic":    "Arctic",
                "raytraced": "Raytraced",
            }
            dm_key = _mcp_display_mode.strip().lower()
            dm_name = _DM_MAP.get(dm_key, "Shaded")
            display_mode_desc = Rhino.Display.DisplayModeDescription.FindByName(dm_name)
            if display_mode_desc is not None:
                vp.DisplayMode = display_mode_desc

            # Configure ViewCapture
            capture = Rhino.Display.ViewCapture()
            capture.Width = int(_mcp_width)
            capture.Height = int(_mcp_height)
            capture.TransparentBackground = bool(_mcp_transparent) and dst_ext == ".png"
            capture.ScaleScreenItems = False

            bitmap = capture.CaptureToBitmap(view)

            if bitmap is None:
                result = {"ok": False, "error": "CaptureToBitmap returned None — check display mode compatibility."}
            else:
                # Ensure output directory exists
                out_dir = os.path.dirname(_mcp_path)
                if out_dir and not os.path.exists(out_dir):
                    os.makedirs(out_dir)

                img_format = _EXT_MAP[dst_ext]

                if dst_ext in (".jpg", ".jpeg"):
                    jpeg_codec = None
                    for codec in _Imaging.ImageCodecInfo.GetImageEncoders():
                        if codec.FormatID == _Imaging.ImageFormat.Jpeg.Guid:
                            jpeg_codec = codec
                            break

                    if jpeg_codec is not None:
                        enc_params = _Imaging.EncoderParameters(1)
                        enc_params.Param[0] = _Imaging.EncoderParameter(
                            _Imaging.Encoder.Quality,
                            int(max(1, min(100, int(_mcp_quality))))
                        )
                        bitmap.Save(_mcp_path, jpeg_codec, enc_params)
                    else:
                        bitmap.Save(_mcp_path, img_format)
                else:
                    bitmap.Save(_mcp_path, img_format)

                bitmap.Dispose()

                result = {
                    "ok": True,
                    "path": _mcp_path,
                    "width": int(_mcp_width),
                    "height": int(_mcp_height),
                    "display_mode": dm_name,
                }
    except Exception as _ex:
        result = {"ok": False, "error": str(_ex)}
'''
