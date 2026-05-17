"""
Tools for AI-driven 3D model generation and import into Rhino.

Supports two generation services:
  - Hyper3D Rodin (https://hyperhuman.deemos.com) — commercial, requires API key
  - Hunyuan3D-2 (Tencent, open-source) — public Gradio demo or enterprise API

Typical workflow:
  1. Call ``generate_3d_from_text`` or ``generate_3d_from_images`` to start a job.
  2. Call ``poll_generation_job`` until ``status`` is ``"done"`` or ``"failed"``.
  3. Call ``import_generated_model`` with the ``job_id`` (or ``download_url``) to
     download the file and import it directly into the active Rhino document.
"""

from __future__ import annotations

import mimetypes
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino, plugin_client

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_RODIN_BASE = "https://hyperhuman.deemos.com/api/v2/rodin"
_RODIN_POLL_URL = "https://hyperhuman.deemos.com/api/v2/rodin/download_task_async"

_VALID_SERVICES = {"rodin", "hunyuan3d"}
_VALID_FORMATS = {"glb", "obj", "fbx", "stl", "usdz"}

# Internal in-memory job store: maps job_id -> metadata dict.
# This allows poll_generation_job to work without the caller persisting the
# remote task UUID separately.
_JOB_STORE: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Public register() entry-point
# ---------------------------------------------------------------------------


def register(mcp: FastMCP) -> None:  # noqa: C901 – register is intentionally long

    # ------------------------------------------------------------------
    # 1. generate_3d_from_text
    # ------------------------------------------------------------------

    @mcp.tool(annotations=ToolAnnotations(title="Generate 3D Model from Text", destructiveHint=False))
    def generate_3d_from_text(
        prompt: str,
        service: str = "rodin",
        output_format: str = "glb",
        api_key: str | None = None,
        tier: str = "Regular",
    ) -> dict[str, object]:
        """
        Submit a text-to-3D generation job to Hyper3D Rodin or Hunyuan3D-2.

        Parameters
        ----------
        prompt:
            Natural-language description of the object to generate.
        service:
            Which backend to use: ``"rodin"`` (Hyper3D, requires API key) or
            ``"hunyuan3d"`` (Tencent public Gradio demo — no key required).
        output_format:
            Desired mesh format: ``"glb"`` (default), ``"obj"``, ``"fbx"``,
            ``"stl"``, or ``"usdz"``.  Not all formats are supported by every
            service; unsupported formats fall back to ``"glb"``.
        api_key:
            Override API key.  Falls back to the ``HYPER3D_API_KEY`` environment
            variable (Rodin) or ``HUNYUAN3D_API_KEY`` (Hunyuan3D).
        tier:
            Rodin quality tier: ``"Regular"`` (default) or ``"Sketch"``
            (faster, lower quality).  Ignored by Hunyuan3D.

        Returns
        -------
        dict with keys ``job_id``, ``status`` (``"pending"``), ``service``, and
        ``message``.  Pass ``job_id`` to ``poll_generation_job`` to check
        progress, and to ``import_generated_model`` when done.
        """
        service = service.lower()
        if service not in _VALID_SERVICES:
            return {"ok": False, "error": f"Unknown service '{service}'. Choose 'rodin' or 'hunyuan3d'."}

        output_format = output_format.lower()
        if output_format not in _VALID_FORMATS:
            return {"ok": False, "error": f"Unknown format '{output_format}'. Choose from: {', '.join(sorted(_VALID_FORMATS))}."}

        if service == "rodin":
            return _rodin_text_job(prompt, output_format, api_key, tier)
        else:
            return _hunyuan3d_text_job(prompt, output_format, api_key)

    # ------------------------------------------------------------------
    # 2. generate_3d_from_images
    # ------------------------------------------------------------------

    @mcp.tool(annotations=ToolAnnotations(title="Generate 3D Model from Images", destructiveHint=False))
    def generate_3d_from_images(
        image_paths: list[str],
        service: str = "rodin",
        output_format: str = "glb",
        api_key: str | None = None,
        prompt: str | None = None,
    ) -> dict[str, object]:
        """
        Submit an image-to-3D generation job using one or more reference images.

        The images are uploaded as multi-view conditioning inputs.  Each image
        should be a different view of the same object for best results.

        Parameters
        ----------
        image_paths:
            List of absolute paths to local image files (JPEG, PNG, WebP).
            Maximum 5 images.
        service:
            Backend: ``"rodin"`` or ``"hunyuan3d"``.
        output_format:
            Desired mesh format (``"glb"``, ``"obj"``, ``"fbx"``, ``"stl"``).
        api_key:
            Override API key; falls back to env vars ``HYPER3D_API_KEY`` /
            ``HUNYUAN3D_API_KEY``.
        prompt:
            Optional text prompt to condition generation alongside the images.

        Returns
        -------
        dict with keys ``job_id``, ``status`` (``"pending"``), ``service``.
        """
        service = service.lower()
        if service not in _VALID_SERVICES:
            return {"ok": False, "error": f"Unknown service '{service}'. Choose 'rodin' or 'hunyuan3d'."}

        output_format = output_format.lower()
        if output_format not in _VALID_FORMATS:
            return {"ok": False, "error": f"Unknown format '{output_format}'."}

        if not image_paths:
            return {"ok": False, "error": "Provide at least one image path."}

        if len(image_paths) > 5:
            return {"ok": False, "error": "Maximum 5 images are supported."}

        # Validate all paths exist before starting the upload.
        for p in image_paths:
            if not Path(p).is_file():
                return {"ok": False, "error": f"Image file not found: {p}"}

        if service == "rodin":
            return _rodin_image_job(image_paths, output_format, api_key, prompt)
        else:
            return _hunyuan3d_image_job(image_paths, output_format, api_key, prompt)

    # ------------------------------------------------------------------
    # 3. poll_generation_job
    # ------------------------------------------------------------------

    @mcp.tool(annotations=ToolAnnotations(title="Poll 3D Generation Job", readOnlyHint=True))
    def poll_generation_job(
        job_id: str,
        service: str,
        api_key: str | None = None,
    ) -> dict[str, object]:
        """
        Check the current status of a previously submitted generation job.

        Poll this tool repeatedly (every ~5–15 seconds) until ``status`` is
        ``"done"`` or ``"failed"``.  When done, ``download_url`` will contain
        a direct link to the generated file (where available).

        Parameters
        ----------
        job_id:
            The ``job_id`` returned by ``generate_3d_from_text`` or
            ``generate_3d_from_images``.
        service:
            The service that owns the job: ``"rodin"`` or ``"hunyuan3d"``.
        api_key:
            Override API key; falls back to env vars.

        Returns
        -------
        dict with keys:
          - ``job_id`` (str)
          - ``status``: ``"pending"``, ``"processing"``, ``"done"``, or ``"failed"``
          - ``progress``: float 0.0–1.0
          - ``download_url``: direct download URL when status is ``"done"``, else ``None``
          - ``message``: human-readable status description
        """
        service = service.lower()
        if service not in _VALID_SERVICES:
            return {"ok": False, "error": f"Unknown service '{service}'."}

        if service == "rodin":
            return _rodin_poll(job_id, api_key)
        else:
            return _hunyuan3d_poll(job_id, api_key)

    # ------------------------------------------------------------------
    # 4. import_generated_model
    # ------------------------------------------------------------------

    @mcp.tool(annotations=ToolAnnotations(title="Import Generated 3D Model into Rhino", destructiveHint=True))
    def import_generated_model(
        job_id: str | None = None,
        service: str | None = None,
        download_url: str | None = None,
        api_key: str | None = None,
        output_dir: str | None = None,
        scale: float = 1.0,
        position: list[float] | None = None,
    ) -> dict[str, object]:
        """
        Download a completed generation job and import it into the active Rhino document.

        You must supply either ``job_id`` + ``service`` (to look up the download
        URL automatically) or a direct ``download_url``.

        Parameters
        ----------
        job_id:
            Job ID returned by a generate_* tool.  Used together with
            ``service`` to resolve the download URL.
        service:
            ``"rodin"`` or ``"hunyuan3d"``.  Required when ``job_id`` is given.
        download_url:
            Direct URL to the generated file.  If supplied, ``job_id`` and
            ``service`` are not needed for the download (but ``api_key`` may
            still be required for authenticated endpoints).
        api_key:
            Override API key; falls back to env vars.
        output_dir:
            Local directory where the downloaded file will be saved.  Defaults
            to a system temporary directory.
        scale:
            Uniform scale factor applied to the imported geometry (default 1.0).
        position:
            Optional [x, y, z] translation applied after import.

        Returns
        -------
        dict with keys ``ok``, ``filepath``, ``object_count``, ``message``.
        """
        # ---- Resolve download URL ----------------------------------------
        url: str | None = download_url
        resolved_service = (service or "").lower()

        if url is None:
            if not job_id:
                return {"ok": False, "error": "Provide either 'job_id' + 'service' or 'download_url'."}
            if not service:
                return {"ok": False, "error": "Provide 'service' when using 'job_id'."}
            if resolved_service not in _VALID_SERVICES:
                return {"ok": False, "error": f"Unknown service '{service}'."}

            poll = poll_generation_job(job_id=job_id, service=resolved_service, api_key=api_key)
            if poll.get("status") != "done":
                return {
                    "ok": False,
                    "error": f"Job is not ready. Current status: {poll.get('status', 'unknown')}. "
                             "Call poll_generation_job until status is 'done'.",
                    "poll": poll,
                }
            url = poll.get("download_url")
            if not url:
                return {"ok": False, "error": "Job is done but no download URL is available in the poll response."}

        # ---- Download file -----------------------------------------------
        download_result = _download_file(url, api_key=api_key, output_dir=output_dir, service=resolved_service)
        if not download_result.get("ok"):
            return download_result

        filepath: str = str(download_result["filepath"])

        # ---- Import into Rhino -------------------------------------------
        return _import_file_into_rhino(filepath, scale=scale, position=position)

    # ------------------------------------------------------------------
    # 5. get_generation_services_status
    # ------------------------------------------------------------------

    @mcp.tool(annotations=ToolAnnotations(title="Get 3D Generation Services Status", readOnlyHint=True))
    def get_generation_services_status() -> dict[str, object]:
        """
        Return availability and configuration status for all supported 3D
        generation services.

        Checks for the presence of API keys in environment variables and
        tests basic network reachability of each service endpoint.  This tool
        does not create any jobs or consume API credits.

        Returns
        -------
        dict with a ``services`` key containing per-service status dicts, each
        with:
          - ``available``: whether the service can be used right now
          - ``api_key_set``: whether an API key was found (env or hard-coded)
          - ``note``: human-readable status/hint
        """
        rodin_key = bool(os.environ.get("HYPER3D_API_KEY"))
        hunyuan_key = bool(os.environ.get("HUNYUAN3D_API_KEY"))

        # Probe Rodin endpoint
        rodin_reachable = _probe_url("https://hyperhuman.deemos.com", timeout=4.0)
        # Probe HuggingFace Gradio demo
        hunyuan_reachable = _probe_url("https://huggingface.co", timeout=4.0)

        # Check gradio_client availability
        gradio_available = _check_gradio_client()

        rodin_status: dict[str, object] = {
            "available": rodin_key and rodin_reachable,
            "api_key_set": rodin_key,
            "endpoint_reachable": rodin_reachable,
            "note": (
                "Ready — API key found and endpoint reachable."
                if rodin_key and rodin_reachable
                else "API key missing — set HYPER3D_API_KEY."
                if not rodin_key
                else "Endpoint unreachable — check network."
            ),
        }

        hunyuan_status: dict[str, object] = {
            "available": hunyuan_reachable and gradio_available,
            "api_key_set": hunyuan_key,
            "endpoint_reachable": hunyuan_reachable,
            "gradio_client_installed": gradio_available,
            "note": (
                "Ready — using public Gradio demo (no API key required)."
                if hunyuan_reachable and gradio_available
                else "gradio_client not installed — run: pip install gradio_client"
                if not gradio_available
                else "HuggingFace endpoint unreachable — check network."
            ),
        }

        plugin_probe = plugin_client.probe(timeout=1.0)

        return {
            "services": {
                "rodin": rodin_status,
                "hunyuan3d": hunyuan_status,
            },
            "rhino_plugin_connected": plugin_probe.get("ok", False),
            "rhino_plugin_address": f"{plugin_probe.get('host')}:{plugin_probe.get('port')}",
            "env_vars": {
                "HYPER3D_API_KEY": "set" if rodin_key else "not set",
                "HUNYUAN3D_API_KEY": "set" if hunyuan_key else "not set",
            },
        }


# ---------------------------------------------------------------------------
# Rodin helpers
# ---------------------------------------------------------------------------


def _rodin_api_key(override: str | None) -> str | None:
    return override or os.environ.get("HYPER3D_API_KEY")


def _rodin_headers(api_key: str | None) -> dict[str, str]:
    key = _rodin_api_key(api_key)
    if not key:
        raise ValueError("Rodin API key not provided. Set HYPER3D_API_KEY or pass api_key.")
    return {"Authorization": f"Bearer {key}"}


def _rodin_text_job(
    prompt: str,
    output_format: str,
    api_key: str | None,
    tier: str,
) -> dict[str, object]:
    """Submit a text-to-3D job to Rodin and store metadata in _JOB_STORE."""
    try:
        headers = _rodin_headers(api_key)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    payload: dict[str, Any] = {
        "prompt": prompt,
        "condition_mode": "concat",
        "geometry_file_format": output_format.upper() if output_format in {"glb", "fbx", "obj", "stl", "usdz"} else "GLB",
        "material": "PBR",
        "quality": "high",
        "tier": tier if tier in {"Regular", "Sketch"} else "Regular",
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(_RODIN_BASE, json=payload, headers=headers)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
    except httpx.HTTPStatusError as exc:
        return {"ok": False, "error": f"Rodin API error {exc.response.status_code}: {exc.response.text}"}
    except httpx.RequestError as exc:
        return {"ok": False, "error": f"Network error contacting Rodin: {exc}"}
    except Exception as exc:
        return {"ok": False, "error": f"Unexpected error: {exc}"}

    task_uuid: str = data.get("uuid", "")
    if not task_uuid:
        return {"ok": False, "error": "Rodin did not return a task UUID.", "raw": data}

    job_id = str(uuid.uuid4())
    _JOB_STORE[job_id] = {
        "service": "rodin",
        "task_uuid": task_uuid,
        "output_format": output_format,
        "api_key": api_key,
        "jobs": data.get("jobs", {}),
    }

    return {
        "job_id": job_id,
        "status": "pending",
        "service": "rodin",
        "task_uuid": task_uuid,
        "message": f"Rodin text-to-3D job submitted. task_uuid={task_uuid}. "
                   "Call poll_generation_job to track progress.",
    }


def _rodin_image_job(
    image_paths: list[str],
    output_format: str,
    api_key: str | None,
    prompt: str | None,
) -> dict[str, object]:
    """Submit an image-to-3D job to Rodin (multipart form)."""
    try:
        headers = _rodin_headers(api_key)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    try:
        files: list[tuple[str, Any]] = []
        opened: list[Any] = []
        for p in image_paths:
            mime, _ = mimetypes.guess_type(p)
            mime = mime or "image/jpeg"
            fh = open(p, "rb")  # noqa: WPS515
            opened.append(fh)
            files.append(("images", (Path(p).name, fh, mime)))

        data_fields: dict[str, str] = {
            "condition_mode": "concat",
            "geometry_file_format": output_format.upper(),
            "material": "PBR",
            "quality": "high",
        }
        if prompt:
            data_fields["prompt"] = prompt

        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(_RODIN_BASE, data=data_fields, files=files, headers=headers)
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
        finally:
            for fh in opened:
                fh.close()

    except httpx.HTTPStatusError as exc:
        return {"ok": False, "error": f"Rodin API error {exc.response.status_code}: {exc.response.text}"}
    except httpx.RequestError as exc:
        return {"ok": False, "error": f"Network error contacting Rodin: {exc}"}
    except OSError as exc:
        return {"ok": False, "error": f"Failed to read image file: {exc}"}
    except Exception as exc:
        return {"ok": False, "error": f"Unexpected error: {exc}"}

    task_uuid: str = data.get("uuid", "")
    if not task_uuid:
        return {"ok": False, "error": "Rodin did not return a task UUID.", "raw": data}

    job_id = str(uuid.uuid4())
    _JOB_STORE[job_id] = {
        "service": "rodin",
        "task_uuid": task_uuid,
        "output_format": output_format,
        "api_key": api_key,
        "jobs": data.get("jobs", {}),
    }

    return {
        "job_id": job_id,
        "status": "pending",
        "service": "rodin",
        "task_uuid": task_uuid,
        "message": f"Rodin image-to-3D job submitted with {len(image_paths)} image(s). "
                   "Call poll_generation_job to track progress.",
    }


def _rodin_poll(job_id: str, api_key: str | None) -> dict[str, object]:
    """Poll the status of a Rodin job."""
    meta = _JOB_STORE.get(job_id)
    if not meta:
        return {
            "ok": False,
            "error": f"Job '{job_id}' not found in this session. "
                     "Ensure you are using the job_id returned by generate_3d_from_text or generate_3d_from_images.",
        }

    task_uuid: str = meta["task_uuid"]
    output_format: str = meta.get("output_format", "glb")
    resolved_key = api_key or meta.get("api_key")

    try:
        headers = _rodin_headers(resolved_key)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    # Use the async-download poll endpoint which returns status and progress.
    payload = {
        "task_uuid": task_uuid,
        "formats": [output_format.upper()],
    }

    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(_RODIN_POLL_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
    except httpx.HTTPStatusError:
        # Fall back to simpler GET poll
        return _rodin_poll_simple_get(job_id, task_uuid, output_format, headers)
    except httpx.RequestError as exc:
        return {"ok": False, "error": f"Network error polling Rodin: {exc}"}
    except Exception as exc:
        return {"ok": False, "error": f"Unexpected error: {exc}"}

    items: list[dict[str, Any]] = data.get("list", [])
    if not items:
        return _rodin_poll_simple_get(job_id, task_uuid, output_format, headers)

    item = items[0]
    raw_status: str = item.get("status", "")
    raw_progress: int = int(item.get("progress", 0))

    status, progress = _rodin_map_status(raw_status, raw_progress)

    download_url: str | None = item.get("url") or (
        f"{_RODIN_BASE}/{task_uuid}/mesh.{output_format}" if status == "done" else None
    )

    if status == "done" and download_url:
        meta["download_url"] = download_url

    return {
        "job_id": job_id,
        "status": status,
        "progress": progress,
        "download_url": download_url,
        "task_uuid": task_uuid,
        "message": f"Rodin job {raw_status} ({raw_progress}%)",
    }


def _rodin_poll_simple_get(
    job_id: str,
    task_uuid: str,
    output_format: str,
    headers: dict[str, str],
) -> dict[str, object]:
    """Fallback polling via GET /{task_uuid}."""
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(f"{_RODIN_BASE}/{task_uuid}", headers=headers)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
    except httpx.HTTPStatusError as exc:
        return {"ok": False, "error": f"Rodin poll error {exc.response.status_code}: {exc.response.text}"}
    except httpx.RequestError as exc:
        return {"ok": False, "error": f"Network error polling Rodin: {exc}"}
    except Exception as exc:
        return {"ok": False, "error": f"Unexpected error: {exc}"}

    raw_status: str = data.get("status", "")
    raw_progress: int = int(data.get("progress", 0))
    status, progress = _rodin_map_status(raw_status, raw_progress)

    download_url: str | None = None
    if status == "done":
        download_url = f"{_RODIN_BASE}/{task_uuid}/mesh.{output_format}"
        if job_id in _JOB_STORE:
            _JOB_STORE[job_id]["download_url"] = download_url

    return {
        "job_id": job_id,
        "status": status,
        "progress": progress,
        "download_url": download_url,
        "task_uuid": task_uuid,
        "message": f"Rodin job {raw_status} ({raw_progress}%)",
    }


def _rodin_map_status(raw: str, progress: int) -> tuple[str, float]:
    """Map Rodin status strings to normalised status + 0.0–1.0 progress."""
    raw_lower = raw.lower()
    if raw_lower == "succeeded":
        return "done", 1.0
    if raw_lower == "failed":
        return "failed", float(progress) / 100.0
    if raw_lower in {"running", "processing", "queued"}:
        status = "processing" if raw_lower in {"running", "processing"} else "pending"
        return status, float(progress) / 100.0
    # Unknown — treat as pending
    return "pending", float(progress) / 100.0


# ---------------------------------------------------------------------------
# Hunyuan3D helpers
# ---------------------------------------------------------------------------


def _hunyuan3d_api_key(override: str | None) -> str | None:
    return override or os.environ.get("HUNYUAN3D_API_KEY")


def _check_gradio_client() -> bool:
    try:
        import gradio_client  # noqa: F401
        return True
    except ImportError:
        return False


def _hunyuan3d_text_job(
    prompt: str,
    output_format: str,
    api_key: str | None,
) -> dict[str, object]:
    """Submit a text-to-3D job to Hunyuan3D-2 via Gradio."""
    if not _check_gradio_client():
        return {
            "ok": False,
            "error": "gradio_client is not installed. Install it with: pip install gradio_client",
        }

    try:
        from gradio_client import Client  # type: ignore[import]
    except ImportError:
        return {
            "ok": False,
            "error": "gradio_client is not installed. Install it with: pip install gradio_client",
        }

    job_id = str(uuid.uuid4())
    try:
        client = Client("tencent/Hunyuan3D-2")
        gradio_job = client.submit(
            caption=prompt,
            steps=30,
            guidance_scale=7.5,
            api_name="/generation_all",
        )
    except Exception as exc:
        return {
            "ok": False,
            "error": f"Failed to submit Hunyuan3D job: {exc}",
        }

    _JOB_STORE[job_id] = {
        "service": "hunyuan3d",
        "status": "processing",
        "prompt": prompt,
        "output_format": output_format,
        "api_key": api_key,
        "gradio_job": gradio_job,
        "result_path": None,
    }

    return {
        "job_id": job_id,
        "status": "processing",
        "service": "hunyuan3d",
        "message": "Hunyuan3D job submitted. Call poll_generation_job to check progress.",
    }


def _hunyuan3d_image_job(
    image_paths: list[str],
    output_format: str,
    api_key: str | None,
    prompt: str | None,
) -> dict[str, object]:
    """Submit an image-to-3D job to Hunyuan3D-2 via Gradio."""
    if not _check_gradio_client():
        return {
            "ok": False,
            "error": "gradio_client is not installed. Install it with: pip install gradio_client",
        }

    try:
        from gradio_client import Client, handle_file  # type: ignore[import]
    except ImportError:
        return {
            "ok": False,
            "error": "gradio_client is not installed. Install it with: pip install gradio_client",
        }

    job_id = str(uuid.uuid4())
    try:
        client = Client("tencent/Hunyuan3D-2")
        gradio_job = client.submit(
            image=handle_file(image_paths[0]),
            caption=prompt or "",
            steps=30,
            guidance_scale=7.5,
            api_name="/generation_all",
        )
    except Exception as exc:
        return {
            "ok": False,
            "error": f"Failed to submit Hunyuan3D image job: {exc}",
        }

    _JOB_STORE[job_id] = {
        "service": "hunyuan3d",
        "status": "processing",
        "prompt": prompt or "",
        "image_paths": image_paths,
        "output_format": output_format,
        "api_key": api_key,
        "gradio_job": gradio_job,
        "result_path": None,
    }

    return {
        "job_id": job_id,
        "status": "processing",
        "service": "hunyuan3d",
        "message": f"Hunyuan3D image job submitted ({len(image_paths)} image(s)). "
                   "Call poll_generation_job to check progress.",
    }


def _hunyuan3d_poll(job_id: str, api_key: str | None) -> dict[str, object]:
    """Execute / check a Hunyuan3D Gradio job."""
    meta = _JOB_STORE.get(job_id)
    if not meta:
        return {
            "ok": False,
            "error": f"Job '{job_id}' not found in this session.",
        }

    # If already done or failed, return cached result.
    cached_status = meta.get("status", "pending")
    if cached_status == "done":
        return {
            "job_id": job_id,
            "status": "done",
            "progress": 1.0,
            "download_url": None,  # Hunyuan3D returns a local file path
            "local_path": meta.get("result_path"),
            "message": "Hunyuan3D generation complete.",
        }
    if cached_status == "failed":
        return {
            "job_id": job_id,
            "status": "failed",
            "progress": 0.0,
            "download_url": None,
            "message": meta.get("error", "Hunyuan3D generation failed."),
        }

    try:
        from gradio_client.utils import Status  # type: ignore[import]
    except ImportError:
        meta["status"] = "failed"
        meta["error"] = "gradio_client not available."
        return {"ok": False, "error": "gradio_client not installed. Run: pip install gradio_client"}

    gradio_job = meta.get("gradio_job")
    if gradio_job is None:
        # Should not happen with the new submit-on-create flow, but guard anyway.
        meta["status"] = "failed"
        meta["error"] = "No Gradio job object found — job may have been created by an older session."
        return {
            "job_id": job_id,
            "status": "failed",
            "progress": 0.0,
            "download_url": None,
            "message": "No Gradio job object found. Please resubmit the generation request.",
        }

    try:
        status_update = gradio_job.status()
        code = status_update.code

        if code == Status.FINISHED:
            result = gradio_job.result()

            # Gradio returns the output file path or a dict with file info.
            result_path: str | None = None
            if isinstance(result, str):
                result_path = result
            elif isinstance(result, dict):
                result_path = result.get("name") or result.get("path") or result.get("url")
            elif isinstance(result, (list, tuple)) and result:
                first = result[0]
                if isinstance(first, str):
                    result_path = first
                elif isinstance(first, dict):
                    result_path = first.get("name") or first.get("path") or first.get("url")

            meta["status"] = "done"
            meta["result_path"] = result_path

            return {
                "job_id": job_id,
                "status": "done",
                "progress": 1.0,
                "download_url": None,
                "local_path": result_path,
                "message": "Hunyuan3D generation complete.",
            }

        if code in (Status.CANCELLED, Status.CLOSED):
            meta["status"] = "failed"
            meta["error"] = f"Gradio job ended with status: {code}"
            return {
                "job_id": job_id,
                "status": "failed",
                "progress": 0.0,
                "download_url": None,
                "message": f"Hunyuan3D job ended unexpectedly: {code}",
            }

        # Still running (PENDING, IN_QUEUE, PROCESSING, GENERATING, etc.)
        meta["status"] = "processing"
        progress_pct: float | None = getattr(status_update, "progress_data", None)
        progress = float(progress_pct) / 100.0 if isinstance(progress_pct, (int, float)) else 0.5

        return {
            "job_id": job_id,
            "status": "processing",
            "progress": progress,
            "download_url": None,
            "message": f"Hunyuan3D job in progress (status: {code}).",
        }

    except Exception as exc:
        meta["status"] = "failed"
        meta["error"] = str(exc)
        return {
            "job_id": job_id,
            "status": "failed",
            "progress": 0.0,
            "download_url": None,
            "message": f"Hunyuan3D generation failed: {exc}",
        }


# ---------------------------------------------------------------------------
# Download helper
# ---------------------------------------------------------------------------


def _download_file(
    url: str,
    api_key: str | None,
    output_dir: str | None,
    service: str,
) -> dict[str, object]:
    """
    Download a remote file (or copy a local Gradio path) to output_dir.

    Returns ``{"ok": True, "filepath": str}`` on success.
    """
    from rhmcp.tools_helpers.security import validate_download_url
    try:
        validate_download_url(url)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    # Determine output path.
    save_dir = output_dir if output_dir else tempfile.mkdtemp(prefix="rhmcp_ai_")
    os.makedirs(save_dir, exist_ok=True)

    # Guess filename from URL.
    url_path = url.split("?")[0]
    filename = url_path.rstrip("/").rsplit("/", 1)[-1] or f"generated_{int(time.time())}.glb"
    if "." not in filename:
        filename += ".glb"

    filepath = os.path.join(save_dir, filename)

    # Build headers.
    headers: dict[str, str] = {}
    if service == "rodin":
        key = _rodin_api_key(api_key)
        if key:
            headers["Authorization"] = f"Bearer {key}"
    elif service == "hunyuan3d":
        key = _hunyuan3d_api_key(api_key)
        if key:
            headers["Authorization"] = f"Bearer {key}"

    try:
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            with client.stream("GET", url, headers=headers) as resp:
                resp.raise_for_status()
                with open(filepath, "wb") as fout:
                    for chunk in resp.iter_bytes(chunk_size=65536):
                        fout.write(chunk)
    except httpx.HTTPStatusError as exc:
        return {"ok": False, "error": f"Download failed {exc.response.status_code}: {exc.response.text}"}
    except httpx.RequestError as exc:
        return {"ok": False, "error": f"Network error during download: {exc}"}
    except OSError as exc:
        return {"ok": False, "error": f"Failed to write file: {exc}"}
    except Exception as exc:
        return {"ok": False, "error": f"Unexpected error during download: {exc}"}

    return {"ok": True, "filepath": filepath}


# ---------------------------------------------------------------------------
# Rhino import helper
# ---------------------------------------------------------------------------


def _import_file_into_rhino(
    filepath: str,
    scale: float = 1.0,
    position: list[float] | None = None,
) -> dict[str, object]:
    """
    Import a mesh file into the active Rhino document via the plugin socket.

    Uses ``execute_rhinocommon_csharp_code`` to call
    ``RhinoDoc.ActiveDoc.Import()`` and optionally scale / translate the result.
    """
    # Normalise path separators for the C# verbatim string literal.
    safe_path = filepath.replace("\\", "/")

    scale_code = ""
    if abs(scale - 1.0) > 1e-9:
        scale_code = f"""
var xform = Rhino.Geometry.Transform.Scale(Rhino.Geometry.Point3d.Origin, {scale});
foreach (var id in importedIds) {{
    doc.Objects.Transform(id, xform, true);
}}
"""

    position_code = ""
    if position and len(position) >= 3:
        px, py, pz = float(position[0]), float(position[1]), float(position[2])
        position_code = f"""
var move = Rhino.Geometry.Transform.Translation({px}, {py}, {pz});
foreach (var id in importedIds) {{
    doc.Objects.Transform(id, move, true);
}}
"""

    code = f"""
var filePath = @"{safe_path}";
var beforeIds = new System.Collections.Generic.HashSet<System.Guid>(
    doc.Objects.Select(o => o.Id)
);
var opts = new Rhino.FileIO.FileReadOptions();
opts.ImportMode = true;
bool importOk = doc.Import(filePath, opts);
var importedIds = doc.Objects
    .Select(o => o.Id)
    .Where(id => !beforeIds.Contains(id))
    .ToList();
int importedCount = importedIds.Count;
{scale_code}
{position_code}
doc.Views.Redraw();
output.AppendLine(importOk
    ? $"Imported {{importedCount}} object(s) from: {{filePath}}"
    : $"Failed to import: {{filePath}}");
output.AppendLine($"IMPORT_OK={{importOk}}");
output.AppendLine($"OBJECT_COUNT={{importedCount}}");
"""

    try:
        result = plugin_client.send_command("execute_rhinocommon_csharp_code", {"code": code})
    except OSError as exc:
        return {
            "ok": False,
            "filepath": filepath,
            "object_count": 0,
            "message": f"Could not connect to Rhino plugin socket: {exc}",
        }
    except Exception as exc:
        return {
            "ok": False,
            "filepath": filepath,
            "object_count": 0,
            "message": f"Unexpected error sending command to Rhino: {exc}",
        }

    # Parse the text output for structured values.
    output_text: str = ""
    if isinstance(result, dict):
        output_text = str(result.get("result", "") or result.get("output", "") or "")

    import_ok = "IMPORT_OK=True" in output_text
    object_count = 0
    for line in output_text.splitlines():
        if line.startswith("OBJECT_COUNT="):
            try:
                object_count = int(line.split("=", 1)[1].strip())
            except ValueError:
                pass

    # If we couldn't parse, treat a non-error result as success.
    if not output_text and result.get("status") == "ok":
        import_ok = True

    materials_normalized = 0
    if import_ok:
        from rhmcp.tools.asset_libraries import _NORMALIZE_ALL_BAKED_SCRIPT
        norm = rhino.execute_python(_NORMALIZE_ALL_BAKED_SCRIPT)
        materials_normalized = norm.get("script_result", {}).get("normalized", 0)

    return {
        "ok": import_ok,
        "filepath": filepath,
        "object_count": object_count,
        "materials_normalized": materials_normalized,
        "message": (
            f"Successfully imported {object_count} object(s) from {filepath}."
            if import_ok
            else f"Import failed for {filepath}. Rhino response: {output_text or result}"
        ),
    }


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _probe_url(url: str, timeout: float = 4.0) -> bool:
    """Return True if *url* is reachable (HTTP 2xx or 3xx)."""
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.head(url)
            return resp.status_code < 500
    except Exception:
        return False
