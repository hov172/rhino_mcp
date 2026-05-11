"""
Tools for integrating external 3D asset libraries with Rhino.

Provides access to Poly Haven (HDRIs, textures, models) and Sketchfab
(community 3D models) with download and auto-import capabilities.
"""

from __future__ import annotations

import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino
from rhmcp.tools_helpers import plugin_client

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_POLYHAVEN_BASE = "https://api.polyhaven.com"
_SKETCHFAB_BASE = "https://api.sketchfab.com/v3"

_DEFAULT_RESOLUTION = os.environ.get("POLYHAVEN_RESOLUTION", "2k")
_TIMEOUT = 30.0  # seconds for HTTP requests
_DOWNLOAD_TIMEOUT = 120.0  # seconds for file downloads


# ---------------------------------------------------------------------------
# Register function
# ---------------------------------------------------------------------------


def register(mcp: FastMCP) -> None:  # noqa: PLR0915 – many tools, acceptable length

    # -----------------------------------------------------------------------
    # Poly Haven: categories
    # -----------------------------------------------------------------------

    @mcp.tool(annotations=ToolAnnotations(title="Get Poly Haven Categories", readOnlyHint=True))
    def get_polyhaven_categories(
        asset_type: str = "all",
    ) -> dict[str, Any]:
        """
        Return the available categories from Poly Haven for a given asset type.

        ``asset_type`` must be one of ``"hdris"``, ``"textures"``, ``"models"``,
        or ``"all"`` (default).  The response is a dict mapping each category
        slug to metadata returned by the Poly Haven API.

        Example return value::

            {
                "categories": {"abstract": 12, "nature": 45, ...},
                "asset_type": "hdris"
            }
        """
        valid = {"hdris", "textures", "models", "all"}
        if asset_type not in valid:
            return {"ok": False, "error": f"asset_type must be one of {sorted(valid)}, got {asset_type!r}"}
        try:
            url = f"{_POLYHAVEN_BASE}/categories/{asset_type}"
            with httpx.Client(timeout=_TIMEOUT) as client:
                resp = client.get(url)
                resp.raise_for_status()
            return {"categories": resp.json(), "asset_type": asset_type}
        except httpx.HTTPStatusError as exc:
            return {"ok": False, "error": f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    # -----------------------------------------------------------------------
    # Poly Haven: search assets
    # -----------------------------------------------------------------------

    @mcp.tool(annotations=ToolAnnotations(title="Search Poly Haven Assets", readOnlyHint=True))
    def search_polyhaven_assets(
        asset_type: str,
        categories: list[str] | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """
        Search Poly Haven for free CC0 assets by type and optional categories.

        ``asset_type`` — one of ``"hdris"``, ``"textures"``, or ``"models"``.
        ``categories`` — optional list of category slugs to filter by (e.g.
            ``["nature", "outdoor"]``).  Only assets that belong to ALL listed
            categories are returned.
        ``limit`` — maximum number of results (default 20).

        Each returned asset includes:

        * ``id`` — the asset slug used for downloads
        * ``name`` — human-readable name
        * ``categories`` — list of category slugs
        * ``download_count`` — popularity indicator
        * ``evs_cap`` — EV range (HDRIs only)
        * ``dimensions`` — pixel size tuple (textures only)
        """
        valid = {"hdris", "textures", "models"}
        if asset_type not in valid:
            return {"ok": False, "error": f"asset_type must be one of {sorted(valid)}, got {asset_type!r}"}
        try:
            url = f"{_POLYHAVEN_BASE}/assets?type={asset_type}"
            with httpx.Client(timeout=_TIMEOUT) as client:
                resp = client.get(url)
                resp.raise_for_status()
            raw: dict[str, Any] = resp.json()
        except httpx.HTTPStatusError as exc:
            return {"ok": False, "error": f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

        results: list[dict[str, Any]] = []
        filter_cats = {c.lower() for c in categories} if categories else None
        for asset_id, meta in raw.items():
            asset_cats: list[str] = list(meta.get("categories", {}).keys())
            if filter_cats and not filter_cats.issubset({c.lower() for c in asset_cats}):
                continue
            entry: dict[str, Any] = {
                "id": asset_id,
                "name": meta.get("name", asset_id),
                "categories": asset_cats,
                "download_count": meta.get("download_count", 0),
            }
            if asset_type == "hdris":
                entry["evs_cap"] = meta.get("evs_cap")
            if asset_type == "textures":
                entry["dimensions"] = meta.get("dimensions")
            results.append(entry)
            if len(results) >= limit:
                break

        return {
            "assets": results,
            "total_returned": len(results),
            "asset_type": asset_type,
            "categories_filter": categories,
        }

    # -----------------------------------------------------------------------
    # Poly Haven: download asset
    # -----------------------------------------------------------------------

    @mcp.tool(annotations=ToolAnnotations(title="Download Poly Haven Asset", destructiveHint=False))
    def download_polyhaven_asset(
        asset_id: str,
        asset_type: str,
        resolution: str = _DEFAULT_RESOLUTION,
        format: str | None = None,  # noqa: A002 – intentional public parameter name
        output_dir: str | None = None,
    ) -> dict[str, Any]:
        """
        Download a Poly Haven asset to disk.

        ``asset_id`` — the asset slug (e.g. ``"autumn_park"``).
        ``asset_type`` — one of ``"hdris"``, ``"textures"``, ``"models"``.
        ``resolution`` — ``"1k"``, ``"2k"`` (default), ``"4k"``, or ``"8k"``.
        ``format`` — file format.  Defaults: ``"hdr"`` for HDRIs, ``"jpg"`` for
            textures, ``"gltf"`` for models.  Accepted values:

            * HDRIs: ``"hdr"`` or ``"exr"``
            * Textures: ``"jpg"``, ``"png"``, ``"exr"``
            * Models: ``"blend"`` or ``"gltf"``

        ``output_dir`` — destination directory; uses the system temp directory
            when omitted.

        Returns::

            {
                "ok": True,
                "filepath": "/tmp/autumn_park_2k.hdr",
                "asset_id": "autumn_park",
                "asset_type": "hdris",
                "resolution": "2k"
            }
        """
        valid_types = {"hdris", "textures", "models"}
        if asset_type not in valid_types:
            return {"ok": False, "error": f"asset_type must be one of {sorted(valid_types)}"}

        # Resolve default format per type.
        _default_formats = {"hdris": "hdr", "textures": "jpg", "models": "gltf"}
        resolved_format = format or _default_formats[asset_type]

        dest_dir = output_dir or tempfile.gettempdir()
        os.makedirs(dest_dir, exist_ok=True)

        try:
            files_url = f"{_POLYHAVEN_BASE}/files/{asset_id}"
            with httpx.Client(timeout=_TIMEOUT) as client:
                resp = client.get(files_url)
                resp.raise_for_status()
            files_data: dict[str, Any] = resp.json()
        except httpx.HTTPStatusError as exc:
            return {"ok": False, "error": f"Failed to fetch file list: HTTP {exc.response.status_code}"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"Failed to fetch file list: {exc}"}

        # Navigate the nested file structure to find the download URL.
        # Structure varies by type but generally:
        #   hdris:    files_data[resolution][format]["url"]
        #   textures: files_data["diffuse"][resolution][format]["url"]  (per channel)
        #   models:   files_data[format][resolution]["url"]
        download_url: str | None = None
        filename: str | None = None

        if asset_type == "hdris":
            try:
                entry = files_data[resolution][resolved_format]
                download_url = entry["url"]
                filename = entry.get("filename") or f"{asset_id}_{resolution}.{resolved_format}"
            except (KeyError, TypeError):
                available = list(files_data.keys())
                return {"ok": False, "error": f"Resolution/format not available. Available resolutions: {available}"}

        elif asset_type == "textures":
            # For textures we download the diffuse (colour) map by default.
            try:
                channel_data = files_data.get("diffuse") or files_data.get("nor_gl") or next(iter(files_data.values()))
                entry = channel_data[resolution][resolved_format]
                download_url = entry["url"]
                filename = entry.get("filename") or f"{asset_id}_{resolution}.{resolved_format}"
            except (KeyError, TypeError, StopIteration):
                return {"ok": False, "error": "Could not locate texture file at requested resolution/format."}

        elif asset_type == "models":
            try:
                entry = files_data[resolved_format][resolution]
                download_url = entry["url"]
                filename = entry.get("filename") or f"{asset_id}_{resolution}.{resolved_format}"
            except (KeyError, TypeError):
                available = list(files_data.keys())
                return {"ok": False, "error": f"Format/resolution not available. Available formats: {available}"}

        if not download_url:
            return {"ok": False, "error": "Could not determine download URL from file list."}

        filepath = os.path.join(dest_dir, filename)
        try:
            with httpx.Client(timeout=_DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
                with client.stream("GET", download_url) as stream:
                    stream.raise_for_status()
                    with open(filepath, "wb") as fh:
                        for chunk in stream.iter_bytes(chunk_size=65536):
                            fh.write(chunk)
        except httpx.HTTPStatusError as exc:
            return {"ok": False, "error": f"Download failed: HTTP {exc.response.status_code}"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"Download failed: {exc}"}

        return {
            "ok": True,
            "filepath": filepath,
            "asset_id": asset_id,
            "asset_type": asset_type,
            "resolution": resolution,
            "format": resolved_format,
        }

    # -----------------------------------------------------------------------
    # Poly Haven: apply HDRI to Rhino render environment
    # -----------------------------------------------------------------------

    @mcp.tool(annotations=ToolAnnotations(title="Apply Poly Haven HDRI", destructiveHint=True))
    def apply_polyhaven_hdri(
        asset_id: str | None = None,
        filepath: str | None = None,
        resolution: str = _DEFAULT_RESOLUTION,
        rotation: float = 0.0,
        intensity: float = 1.0,
    ) -> dict[str, Any]:
        """
        Download (if needed) and apply a Poly Haven HDRI to Rhino's render environment.

        Provide either ``asset_id`` (to download from Poly Haven) or ``filepath``
        (to use a previously downloaded ``.hdr`` / ``.exr`` file).

        ``resolution`` — ``"1k"``, ``"2k"`` (default), ``"4k"``, ``"8k"``.
        ``rotation`` — horizontal rotation in degrees (default 0.0).
        ``intensity`` — environment brightness multiplier (default 1.0).

        The tool sets Rhino's background style to the loaded environment and
        triggers a viewport redraw.

        Returns::

            {"ok": True, "filepath": "/tmp/autumn_park_2k.hdr", "message": "HDRI applied"}
        """
        if not asset_id and not filepath:
            return {"ok": False, "error": "Provide either 'asset_id' or 'filepath'."}

        # Download if needed.
        if asset_id and not filepath:
            dl = download_polyhaven_asset(asset_id, "hdris", resolution=resolution)
            if not dl.get("ok"):
                return {"ok": False, "error": f"Download failed: {dl.get('error', 'unknown')}"}
            filepath = dl["filepath"]

        if not filepath or not os.path.isfile(filepath):
            return {"ok": False, "error": f"HDRI file not found: {filepath}"}

        # Build C# code that applies the HDRI inside Rhino.
        safe_path = filepath.replace("\\", "\\\\").replace('"', '\\"')
        csharp_code = f"""
var doc = RhinoDoc.ActiveDoc;
var hdriPath = @"{safe_path}";
var sb = new System.Text.StringBuilder();

try
{{
    // Use the scripted Environment command to set HDRI background.
    bool scriptOk = Rhino.RhinoApp.RunScript(
        "_-Environment _Background _Image \\\"" + hdriPath + "\\\" _Enter _Enter",
        false
    );
    doc.RenderSettings.BackgroundStyle = Rhino.DocObjects.BackgroundStyle.Wallpaper;

    // Apply intensity if supported.
    var env = doc.RenderEnvironments.Find(doc.RenderEnvironments.CurrentEnvironment(Rhino.Render.RenderEnvironmentUsage.Background));
    if (env != null)
    {{
        // Attempt to set rotation/intensity via parameters.
        var rotParam = env.GetParameter("rotation");
        if (rotParam != null)
            env.SetParameter("rotation", {rotation});
        var intensParam = env.GetParameter("multiplier");
        if (intensParam != null)
            env.SetParameter("multiplier", {intensity});
    }}

    doc.Views.Redraw();
    sb.AppendLine("HDRI applied: " + hdriPath);
    output.AppendLine(sb.ToString());
}}
catch (Exception ex)
{{
    output.AppendLine("Error applying HDRI: " + ex.Message);
}}
"""
        try:
            result = plugin_client.send_command(
                "execute_rhinocommon_csharp_code", {"code": csharp_code}
            )
        except OSError as exc:
            return {"ok": False, "error": f"Rhino plugin socket unavailable: {exc}", "filepath": filepath}

        status = result.get("status", "")
        if status == "error":
            return {"ok": False, "error": result.get("message", "Unknown error"), "filepath": filepath}

        return {
            "ok": True,
            "filepath": filepath,
            "message": "HDRI applied successfully.",
            "rotation": rotation,
            "intensity": intensity,
            "rhino_response": result,
        }

    # -----------------------------------------------------------------------
    # Poly Haven: apply texture as PBR material
    # -----------------------------------------------------------------------

    @mcp.tool(annotations=ToolAnnotations(title="Apply Poly Haven Texture", destructiveHint=True))
    def apply_polyhaven_texture(
        asset_id: str,
        object_id: str,
        resolution: str = _DEFAULT_RESOLUTION,
        channel: str = "all",
        material_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Download a Poly Haven texture set and apply it as a PBR material to a Rhino object.

        ``asset_id`` — Poly Haven texture slug (e.g. ``"rock_moss_001"``).
        ``object_id`` — GUID of the target Rhino object.
        ``resolution`` — ``"1k"``, ``"2k"`` (default), ``"4k"``, ``"8k"``.
        ``channel`` — which map(s) to apply: ``"diffuse"``, ``"roughness"``,
            ``"normal"``, ``"displacement"``, ``"ao"``, or ``"all"`` (default).
        ``material_name`` — optional name for the new PBR material; defaults to
            ``"{asset_id}_{resolution}"``.

        All available maps are downloaded and assembled into a Physically Based
        Rendering (PBR) material in Rhino with separate texture slots for
        albedo, roughness, normal, displacement, and ambient occlusion.

        Returns::

            {
                "ok": True,
                "material_name": "rock_moss_001_2k",
                "textures_applied": ["diffuse", "normal", "roughness"],
                "object_id": "..."
            }
        """
        valid_channels = {"diffuse", "roughness", "normal", "displacement", "ao", "all"}
        if channel not in valid_channels:
            return {"ok": False, "error": f"channel must be one of {sorted(valid_channels)}"}

        dest_dir = os.path.join(tempfile.gettempdir(), f"polyhaven_{asset_id}_{resolution}")
        os.makedirs(dest_dir, exist_ok=True)

        mat_name = material_name or f"{asset_id}_{resolution}"

        # Fetch the full file manifest.
        try:
            files_url = f"{_POLYHAVEN_BASE}/files/{asset_id}"
            with httpx.Client(timeout=_TIMEOUT) as client:
                resp = client.get(files_url)
                resp.raise_for_status()
            files_data: dict[str, Any] = resp.json()
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"Failed to fetch texture manifest: {exc}"}

        # Map Poly Haven channel names → our channel labels.
        ph_channel_map = {
            "diffuse": ["diffuse", "col"],
            "roughness": ["rough", "roughness"],
            "normal": ["nor_gl", "nor_dx", "normal"],
            "displacement": ["disp", "displacement"],
            "ao": ["ao", "arm"],
        }
        selected_channels = list(ph_channel_map.keys()) if channel == "all" else [channel]

        textures_applied: list[str] = []
        channel_paths: dict[str, str] = {}

        with httpx.Client(timeout=_DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
            for ch_label in selected_channels:
                ph_names = ph_channel_map[ch_label]
                # Find the first matching key in the manifest.
                ch_data: dict[str, Any] | None = None
                for ph_name in ph_names:
                    if ph_name in files_data:
                        ch_data = files_data[ph_name]
                        break
                if ch_data is None:
                    continue  # channel not available for this asset

                # Try jpg then png then exr.
                entry: dict[str, Any] | None = None
                chosen_fmt: str = "jpg"
                for fmt in ("jpg", "png", "exr"):
                    if resolution in ch_data and fmt in ch_data[resolution]:
                        entry = ch_data[resolution][fmt]
                        chosen_fmt = fmt
                        break
                if entry is None:
                    continue

                download_url: str = entry["url"]
                fname: str = entry.get("filename") or f"{asset_id}_{ch_label}_{resolution}.{chosen_fmt}"
                fpath = os.path.join(dest_dir, fname)

                if not os.path.isfile(fpath):
                    try:
                        with client.stream("GET", download_url) as stream:
                            stream.raise_for_status()
                            with open(fpath, "wb") as fh:
                                for blob in stream.iter_bytes(chunk_size=65536):
                                    fh.write(blob)
                    except Exception:  # noqa: BLE001
                        continue  # skip channels that fail to download

                channel_paths[ch_label] = fpath
                textures_applied.append(ch_label)

        if not channel_paths:
            return {"ok": False, "error": "No texture maps could be downloaded for this asset."}

        # Build C# to create a PBR material and assign it to the object.
        safe_name = mat_name.replace('"', '\\"')
        safe_obj_id = object_id.replace('"', '\\"')

        def _cs_path(p: str) -> str:
            return p.replace("\\", "\\\\").replace('"', '\\"')

        diffuse_path = _cs_path(channel_paths.get("diffuse", ""))
        roughness_path = _cs_path(channel_paths.get("roughness", ""))
        normal_path = _cs_path(channel_paths.get("normal", ""))
        disp_path = _cs_path(channel_paths.get("displacement", ""))
        ao_path = _cs_path(channel_paths.get("ao", ""))

        csharp_code = f"""
var doc = RhinoDoc.ActiveDoc;
var matName = "{safe_name}";
var objGuid = new System.Guid("{safe_obj_id}");

try
{{
    // Create a Physically Based Material (Rhino 8 PBR workflow).
    var pbr = new Rhino.Render.PhysicallyBasedMaterial();

    // Helper: assign a texture to a PBR slot if the path is non-empty.
    System.Action<string, Rhino.Render.PhysicallyBasedMaterial.TextureUseEnums> setTex =
        (path, slot) =>
        {{
            if (!string.IsNullOrEmpty(path))
            {{
                var tex = new Rhino.DocObjects.Texture();
                tex.FileName = path;
                tex.Enabled = true;
                pbr.SetTexture(tex, slot);
            }}
        }};

    // Albedo / diffuse
    setTex("{diffuse_path}", Rhino.Render.PhysicallyBasedMaterial.TextureUseEnums.Albedo);
    // Roughness
    setTex("{roughness_path}", Rhino.Render.PhysicallyBasedMaterial.TextureUseEnums.Roughness);
    // Normal / bump
    setTex("{normal_path}", Rhino.Render.PhysicallyBasedMaterial.TextureUseEnums.Bump);
    // Displacement
    setTex("{disp_path}", Rhino.Render.PhysicallyBasedMaterial.TextureUseEnums.Displacement);
    // Ambient occlusion
    setTex("{ao_path}", Rhino.Render.PhysicallyBasedMaterial.TextureUseEnums.AmbientOcclusion);

    // Convert PBR to a document material and set its name.
    var mat = pbr.Material;
    mat.Name = matName;

    // Add material to document.
    int matIndex = doc.Materials.Add(mat);
    doc.Materials.Modify(mat, matIndex, true);

    // Assign to object.
    var obj = doc.Objects.FindId(objGuid);
    if (obj != null)
    {{
        obj.Attributes.MaterialIndex = matIndex;
        obj.Attributes.MaterialSource = Rhino.DocObjects.ObjectMaterialSource.MaterialFromObject;
        obj.CommitChanges();
        output.AppendLine("Material assigned: " + matName + " -> index " + matIndex);
    }}
    else
    {{
        output.AppendLine("Warning: object not found: {safe_obj_id}");
    }}

    doc.Views.Redraw();
}}
catch (Exception ex)
{{
    output.AppendLine("Error: " + ex.Message);
}}
"""
        try:
            result = plugin_client.send_command(
                "execute_rhinocommon_csharp_code", {"code": csharp_code}
            )
        except OSError as exc:
            return {
                "ok": False,
                "error": f"Rhino plugin socket unavailable: {exc}",
                "textures_applied": textures_applied,
                "channel_paths": channel_paths,
            }

        if result.get("status") == "error":
            return {
                "ok": False,
                "error": result.get("message", "Unknown Rhino error"),
                "textures_applied": textures_applied,
            }

        return {
            "ok": True,
            "material_name": mat_name,
            "textures_applied": textures_applied,
            "object_id": object_id,
            "channel_paths": channel_paths,
            "rhino_response": result,
        }

    # -----------------------------------------------------------------------
    # Sketchfab: search models
    # -----------------------------------------------------------------------

    @mcp.tool(annotations=ToolAnnotations(title="Search Sketchfab Models", readOnlyHint=True))
    def search_sketchfab_models(
        query: str,
        categories: list[str] | None = None,
        license: str | None = None,  # noqa: A002
        downloadable: bool = True,
        animated: bool | None = None,
        staffpicked: bool | None = None,
        count: int = 10,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        """
        Search the Sketchfab model library.

        ``query`` — free-text search term.
        ``categories`` — optional list of Sketchfab category slugs.
        ``license`` — filter by Creative Commons license type.  Accepted values:
            ``"by"``, ``"by-sa"``, ``"by-nd"``, ``"by-nc"``, ``"by-nc-sa"``,
            ``"by-nc-nd"``, ``"cc0"``.
        ``downloadable`` — only return models with a download option (default
            ``True``).
        ``animated`` — ``True`` to require animation; ``False`` to exclude; omit
            to accept any.
        ``staffpicked`` — filter by Sketchfab staff pick status.
        ``count`` — number of results (default 10, maximum 24).
        ``api_key`` — Sketchfab API key.  Falls back to the ``SKETCHFAB_API_KEY``
            environment variable.  Required for download operations but optional
            for public searches.

        Returns a list of models with: uid, name, description snippet,
        thumbnail_url, face_count, vertex_count, license, and download_size.
        """
        resolved_key = api_key or os.environ.get("SKETCHFAB_API_KEY")

        params: dict[str, Any] = {
            "q": query,
            "downloadable": str(downloadable).lower(),
            "count": max(1, min(24, count)),
            "type": "models",
        }
        if license:
            params["license"] = license
        if animated is not None:
            params["animated"] = str(animated).lower()
        if staffpicked is not None:
            params["staff_picked"] = str(staffpicked).lower()
        if categories:
            params["categories"] = ",".join(categories)

        headers: dict[str, str] = {}
        if resolved_key:
            headers["Authorization"] = f"Token {resolved_key}"

        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                resp = client.get(f"{_SKETCHFAB_BASE}/models", params=params, headers=headers)
                resp.raise_for_status()
            data: dict[str, Any] = resp.json()
        except httpx.HTTPStatusError as exc:
            return {"ok": False, "error": f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

        models: list[dict[str, Any]] = []
        for item in data.get("results", []):
            thumbnail_url: str | None = None
            thumbs = item.get("thumbnails", {}).get("images", [])
            if thumbs:
                thumbnail_url = thumbs[0].get("url")

            lic_info = item.get("license") or {}
            models.append(
                {
                    "uid": item.get("uid"),
                    "name": item.get("name"),
                    "description": (item.get("description") or "")[:300],
                    "thumbnail_url": thumbnail_url,
                    "face_count": item.get("faceCount"),
                    "vertex_count": item.get("vertexCount"),
                    "license": lic_info.get("label") or lic_info.get("slug"),
                    "download_size": item.get("archives", {}).get("gltf", {}).get("size"),
                    "is_downloadable": item.get("isDownloadable", False),
                    "animated": item.get("animationCount", 0) > 0,
                    "view_count": item.get("viewCount"),
                    "like_count": item.get("likeCount"),
                }
            )

        return {
            "models": models,
            "total": data.get("count", len(models)),
            "next_cursor": data.get("cursors", {}).get("next"),
        }

    # -----------------------------------------------------------------------
    # Sketchfab: get model info
    # -----------------------------------------------------------------------

    @mcp.tool(annotations=ToolAnnotations(title="Get Sketchfab Model Info", readOnlyHint=True))
    def get_sketchfab_model_info(
        model_uid: str,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        """
        Retrieve full metadata for a Sketchfab model by its UID.

        ``model_uid`` — the Sketchfab model UID (24-character string visible in
            the model URL on sketchfab.com).
        ``api_key`` — Sketchfab API key; falls back to ``SKETCHFAB_API_KEY`` env
            var.

        Returns the full model record plus a ``download_formats`` list
        enumerating which format archives are available.
        """
        resolved_key = api_key or os.environ.get("SKETCHFAB_API_KEY")
        headers: dict[str, str] = {}
        if resolved_key:
            headers["Authorization"] = f"Token {resolved_key}"

        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                resp = client.get(f"{_SKETCHFAB_BASE}/models/{model_uid}", headers=headers)
                resp.raise_for_status()
            data: dict[str, Any] = resp.json()
        except httpx.HTTPStatusError as exc:
            return {"ok": False, "error": f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

        archives = data.get("archives") or {}
        download_formats = [
            {"format": fmt, "size": info.get("size"), "face_count": info.get("faceCount")}
            for fmt, info in archives.items()
            if info
        ]

        thumbnail_url: str | None = None
        thumbs = data.get("thumbnails", {}).get("images", [])
        if thumbs:
            thumbnail_url = max(thumbs, key=lambda t: t.get("width", 0)).get("url")

        return {
            "uid": data.get("uid"),
            "name": data.get("name"),
            "description": data.get("description"),
            "author": (data.get("user") or {}).get("displayName"),
            "license": (data.get("license") or {}).get("label"),
            "is_downloadable": data.get("isDownloadable", False),
            "face_count": data.get("faceCount"),
            "vertex_count": data.get("vertexCount"),
            "animated": (data.get("animationCount") or 0) > 0,
            "animation_count": data.get("animationCount"),
            "created_at": data.get("createdAt"),
            "published_at": data.get("publishedAt"),
            "thumbnail_url": thumbnail_url,
            "view_count": data.get("viewCount"),
            "like_count": data.get("likeCount"),
            "download_formats": download_formats,
            "tags": [t.get("name") for t in (data.get("tags") or [])],
        }

    # -----------------------------------------------------------------------
    # Sketchfab: download model
    # -----------------------------------------------------------------------

    @mcp.tool(annotations=ToolAnnotations(title="Download Sketchfab Model", destructiveHint=True))
    def download_sketchfab_model(
        model_uid: str,
        api_key: str | None = None,
        format: str = "gltf",  # noqa: A002
        output_dir: str | None = None,
        import_to_rhino: bool = True,
        scale: float = 1.0,
    ) -> dict[str, Any]:
        """
        Download a Sketchfab model and optionally import it into Rhino.

        ``model_uid`` — 24-character Sketchfab model UID.
        ``api_key`` — Sketchfab API key (required for downloads); falls back to
            the ``SKETCHFAB_API_KEY`` environment variable.
        ``format`` — download archive format: ``"gltf"`` (default), ``"usdz"``,
            or ``"source"``.
        ``output_dir`` — directory to save the extracted files; uses the system
            temp directory when omitted.
        ``import_to_rhino`` — when ``True`` (default), the downloaded model is
            immediately imported into the active Rhino document.
        ``scale`` — uniform scale factor applied after import (default 1.0 =
            no scaling).

        The archive is downloaded as a ``.zip``, extracted in-place, and the
        primary model file is identified for import.

        Returns::

            {
                "ok": True,
                "filepath": "/tmp/sketchfab_abc123/scene.gltf",
                "model_uid": "abc123...",
                "imported": True
            }
        """
        resolved_key = api_key or os.environ.get("SKETCHFAB_API_KEY")
        if not resolved_key:
            return {"ok": False, "error": "Sketchfab API key required. Pass api_key or set SKETCHFAB_API_KEY env var."}

        valid_formats = {"gltf", "usdz", "source"}
        if format not in valid_formats:
            return {"ok": False, "error": f"format must be one of {sorted(valid_formats)}"}

        headers = {"Authorization": f"Token {resolved_key}"}

        # Step 1: Request a download URL from Sketchfab.
        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                resp = client.get(
                    f"{_SKETCHFAB_BASE}/models/{model_uid}/download",
                    headers=headers,
                    params={"format": format},
                )
                resp.raise_for_status()
            dl_data: dict[str, Any] = resp.json()
        except httpx.HTTPStatusError as exc:
            body = ""
            try:
                body = exc.response.text[:300]
            except Exception:  # noqa: BLE001
                pass
            return {"ok": False, "error": f"Failed to get download URL: HTTP {exc.response.status_code} {body}"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"Failed to get download URL: {exc}"}

        # Sketchfab returns format-keyed URLs.
        fmt_data = dl_data.get(format) or dl_data.get("gltf") or next(iter(dl_data.values()), None)
        if not fmt_data or not isinstance(fmt_data, dict):
            return {"ok": False, "error": f"No download URL in response: {dl_data}"}

        archive_url: str = fmt_data.get("url", "")
        if not archive_url:
            return {"ok": False, "error": "Download URL is empty."}

        # Step 2: Download the zip archive.
        dest_dir = output_dir or os.path.join(tempfile.gettempdir(), f"sketchfab_{model_uid}")
        os.makedirs(dest_dir, exist_ok=True)
        zip_path = os.path.join(dest_dir, f"{model_uid}.zip")

        try:
            with httpx.Client(timeout=_DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
                with client.stream("GET", archive_url) as stream:
                    stream.raise_for_status()
                    with open(zip_path, "wb") as fh:
                        for blob in stream.iter_bytes(chunk_size=65536):
                            fh.write(blob)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"Archive download failed: {exc}"}

        # Step 3: Extract the archive.
        extract_dir = os.path.join(dest_dir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)
        except zipfile.BadZipFile as exc:
            return {"ok": False, "error": f"Archive is not a valid zip: {exc}"}

        # Step 4: Find the primary model file.
        ext_priority = {
            "gltf": [".gltf", ".glb"],
            "usdz": [".usdz", ".usdc", ".usda"],
            "source": [".fbx", ".obj", ".3dm", ".step", ".stl", ".gltf", ".glb"],
        }
        primary_file: str | None = None
        search_exts = ext_priority.get(format, [".gltf", ".glb"])
        for ext in search_exts:
            for root, _dirs, files in os.walk(extract_dir):
                for fname in files:
                    if fname.lower().endswith(ext):
                        primary_file = os.path.join(root, fname)
                        break
                if primary_file:
                    break
            if primary_file:
                break

        if not primary_file:
            # Fall back to any file that looks importable.
            importable_exts = {".gltf", ".glb", ".fbx", ".obj", ".3dm", ".stl", ".usdz", ".usdc"}
            for root, _dirs, files in os.walk(extract_dir):
                for fname in files:
                    if Path(fname).suffix.lower() in importable_exts:
                        primary_file = os.path.join(root, fname)
                        break
                if primary_file:
                    break

        if not primary_file:
            return {
                "ok": False,
                "error": "Could not find an importable model file after extraction.",
                "extract_dir": extract_dir,
            }

        # Step 5: Import into Rhino if requested.
        imported = False
        import_result: dict[str, Any] = {}
        if import_to_rhino:
            import_result = _import_file_to_rhino(primary_file, scale=scale)
            imported = import_result.get("ok", False) or import_result.get("status") == "ok"

        return {
            "ok": True,
            "filepath": primary_file,
            "extract_dir": extract_dir,
            "model_uid": model_uid,
            "format": format,
            "imported": imported,
            "import_result": import_result if import_to_rhino else None,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _import_file_to_rhino(filepath: str, scale: float = 1.0) -> dict[str, Any]:
    """
    Import a file into the active Rhino document via the plugin socket.

    Sends C# code that calls ``RhinoDoc.ActiveDoc.Import()``.  When ``scale``
    differs from 1.0 a uniform scale transform is applied to every newly added
    object immediately after import.

    Args:
        filepath: Absolute path to the file to import.
        scale: Uniform scale factor (default 1.0 = no scaling).

    Returns:
        The raw dict returned by the plugin socket, augmented with an ``ok``
        key derived from the response status.
    """
    safe_path = filepath.replace("\\", "\\\\").replace('"', '\\"')
    scale_str = repr(float(scale))
    csharp_code = f"""
var filePath = @"{safe_path}";
var opts = new Rhino.FileIO.FileReadOptions {{ ImportMode = true }};
bool ok = RhinoDoc.ActiveDoc.Import(filePath, opts);

if (ok && {scale_str} != 1.0)
{{
    var xf = Rhino.Geometry.Transform.Scale(Rhino.Geometry.Point3d.Origin, {scale_str});
    foreach (var obj in RhinoDoc.ActiveDoc.Objects)
        RhinoDoc.ActiveDoc.Objects.Transform(obj.Id, xf, true);
}}

RhinoDoc.ActiveDoc.Views.Redraw();
output.AppendLine(ok ? "Imported: " + filePath : "Failed: " + filePath);
"""
    try:
        result = plugin_client.send_command(
            "execute_rhinocommon_csharp_code", {"code": csharp_code}
        )
        result.setdefault("ok", result.get("status") not in {"error"})
    except OSError as exc:
        return {"ok": False, "error": f"Plugin socket unavailable: {exc}"}

    # Normalize import-baked materials so ObjectColor and material changes
    # work correctly after this import.  3DS/FBX/OBJ importers stamp every
    # mesh with MaterialFromObject; ModifyAttributes alone won't fix the
    # display cache — only delete+readd clears it.
    if result.get("ok"):
        norm = rhino.execute_python(_NORMALIZE_ALL_BAKED_SCRIPT)
        result["materials_normalized"] = (
            norm.get("script_result", {}).get("normalized", 0)
        )

    return result


_NORMALIZE_ALL_BAKED_SCRIPT = r'''
import Rhino
import Rhino.Geometry as rg

doc = Rhino.RhinoDoc.ActiveDoc
candidates = []
for obj in doc.Objects:
    if obj.IsDeleted or obj.ObjectType.ToString() == "Light":
        continue
    src = obj.Attributes.MaterialSource.ToString()
    if src == "MaterialFromObject" and obj.Attributes.MaterialIndex >= 0:
        candidates.append((obj.Id, obj.Attributes.LayerIndex, obj.Attributes.Name or ""))

normalized = 0
skipped = 0
for obj_id, layer_idx, obj_name in candidates:
    obj = doc.Objects.Find(obj_id)
    if obj is None or obj.IsDeleted:
        skipped += 1
        continue
    geo = obj.Geometry
    otype = obj.ObjectType.ToString()
    new_geo = geo.DuplicateMesh() if otype == "Mesh" else geo.Duplicate()
    if new_geo is None:
        skipped += 1
        continue
    oa = Rhino.DocObjects.ObjectAttributes()
    oa.LayerIndex = layer_idx
    oa.Name = obj_name
    oa.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromLayer
    oa.MaterialSource = Rhino.DocObjects.ObjectMaterialSource.MaterialFromParent
    doc.Objects.Delete(obj_id, True)
    if otype == "Mesh":
        doc.Objects.AddMesh(new_geo, oa)
    elif otype == "Brep":
        doc.Objects.AddBrep(new_geo, oa)
    elif otype == "Surface":
        doc.Objects.AddSurface(new_geo, oa)
    elif otype == "Curve":
        doc.Objects.AddCurve(new_geo, oa)
    else:
        doc.Objects.Add(new_geo, oa)
    normalized += 1
doc.Views.Redraw()
result = {"normalized": normalized, "skipped": skipped}
'''
