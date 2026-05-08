"""
Tools for Physically-Based Rendering (PBR) materials, HDRI environments,
and rendering in Rhino 3D.

These tools complement the basic diffuse/specular material tools in
``materials.py`` and target Rhino's Physically Based Material workflow and
Cycles renderer that ships with Rhino 8.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def register(mcp: FastMCP) -> None:
    # ------------------------------------------------------------------
    # PBR material creation
    # ------------------------------------------------------------------

    @mcp.tool(annotations=ToolAnnotations(title="Create PBR Material", destructiveHint=True))
    def create_pbr_material(
        name: str,
        base_color: list[float] | None = None,
        metallic: float = 0.0,
        roughness: float = 0.5,
        opacity: float = 1.0,
        ior: float = 1.5,
        emission: list[float] | None = None,
        emission_multiplier: float = 0.0,
        base_color_texture: str | None = None,
        roughness_texture: str | None = None,
        metallic_texture: str | None = None,
        normal_texture: str | None = None,
        bump_scale: float = 1.0,
        displacement_texture: str | None = None,
        displacement_scale: float = 1.0,
        ao_texture: str | None = None,
        opacity_texture: str | None = None,
    ) -> dict[str, object]:
        """
        Create a Physically-Based Rendering (PBR) material in the active Rhino document.

        PBR materials produce photorealistic results when rendered with Rhino's
        Cycles engine. All color channels use normalised float values (0.0–1.0).

        Parameters
        ----------
        name:
            Unique name for the new material.
        base_color:
            Albedo/base colour as [r, g, b] with values in the range 0.0–1.0.
            Defaults to a neutral grey ``[0.5, 0.5, 0.5]`` when omitted.
        metallic:
            Metalness factor (0 = dielectric, 1 = fully metallic).
        roughness:
            Surface roughness (0 = mirror-smooth, 1 = fully diffuse).
        opacity:
            Surface opacity (0 = fully transparent, 1 = fully opaque).
        ior:
            Index of refraction used for transparent/refractive surfaces.
        emission:
            Emission colour as [r, g, b] with values in the range 0.0–1.0.
        emission_multiplier:
            Multiplier applied to the emission colour.  Set > 0 to make the
            surface self-luminous.
        base_color_texture:
            Absolute file path to a bitmap texture used as the albedo channel.
        roughness_texture:
            Absolute file path to a greyscale roughness texture.
        metallic_texture:
            Absolute file path to a greyscale metalness texture.
        normal_texture:
            Absolute file path to a tangent-space normal map.
        bump_scale:
            Bump/normal map intensity multiplier.
        displacement_texture:
            Absolute file path to a greyscale displacement/height map.
        displacement_scale:
            Displacement height scale in model units.
        ao_texture:
            Absolute file path to an ambient-occlusion texture.
        opacity_texture:
            Absolute file path to a greyscale opacity/alpha mask texture.

        Returns
        -------
        dict with keys:
            ok (bool), material_index (int), material_name (str)
        """
        # Validate numeric ranges
        metallic = max(0.0, min(1.0, float(metallic)))
        roughness = max(0.0, min(1.0, float(roughness)))
        opacity = max(0.0, min(1.0, float(opacity)))
        ior = max(1.0, float(ior))
        emission_multiplier = max(0.0, float(emission_multiplier))
        bump_scale = float(bump_scale)
        displacement_scale = float(displacement_scale)

        if base_color is not None and len(base_color) < 3:
            return {"ok": False, "error": "base_color must have at least 3 elements [r, g, b]."}
        if emission is not None and len(emission) < 3:
            return {"ok": False, "error": "emission must have at least 3 elements [r, g, b]."}

        params: dict[str, object] = {
            "name": name,
            "metallic": metallic,
            "roughness": roughness,
            "opacity": opacity,
            "ior": ior,
            "emission_multiplier": emission_multiplier,
            "bump_scale": bump_scale,
            "displacement_scale": displacement_scale,
        }
        if base_color is not None:
            params["base_color"] = [max(0.0, min(1.0, float(v))) for v in base_color[:3]]
        if emission is not None:
            params["emission"] = [max(0.0, min(1.0, float(v))) for v in emission[:3]]
        for key, value in [
            ("base_color_texture", base_color_texture),
            ("roughness_texture", roughness_texture),
            ("metallic_texture", metallic_texture),
            ("normal_texture", normal_texture),
            ("displacement_texture", displacement_texture),
            ("ao_texture", ao_texture),
            ("opacity_texture", opacity_texture),
        ]:
            if value is not None:
                params[key] = value

        try:
            result = _plugin("create_pbr_material", params)
            if result is None:
                return {"ok": False, "error": "Plugin backend unavailable and no fallback script."}
            raw = result.get("result", result)
            ok = bool(raw.get("success", False)) if isinstance(raw, dict) else False
            return {
                "ok": ok,
                "material_index": int(raw.get("material_index", -1)) if isinstance(raw, dict) else -1,
                "material_name": str(raw.get("material_name", name)) if isinstance(raw, dict) else name,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ------------------------------------------------------------------
    # HDRI / environment map
    # ------------------------------------------------------------------

    @mcp.tool(annotations=ToolAnnotations(title="Set Environment Map", destructiveHint=True))
    def set_environment_map(
        filepath: str,
        rotation: float = 0.0,
        intensity: float = 1.0,
        use_for_background: bool = True,
        use_for_lighting: bool = True,
        use_for_reflections: bool = True,
    ) -> dict[str, object]:
        """
        Load an HDRI or EXR image file as the document's render environment.

        The environment is used for image-based lighting (IBL), background
        display, and reflection sampling according to the flags provided.

        Parameters
        ----------
        filepath:
            Absolute path to the environment image.  Supported formats are
            ``.hdr`` (Radiance RGBE) and ``.exr`` (OpenEXR).
        rotation:
            Rotation of the environment around the world Y-axis in degrees
            (0–360).  Useful for aligning the dominant light direction.
        intensity:
            Brightness multiplier for the environment (default 1.0).
        use_for_background:
            If True, the environment image is displayed as the viewport/render
            background.
        use_for_lighting:
            If True, the environment contributes to image-based lighting.
        use_for_reflections:
            If True, the environment is sampled for reflections.

        Returns
        -------
        dict with keys:
            ok (bool), filepath (str), message (str)
        """
        rotation = float(rotation) % 360.0
        intensity = max(0.0, float(intensity))

        params: dict[str, object] = {
            "filepath": filepath,
            "rotation": rotation,
            "intensity": intensity,
            "use_for_background": bool(use_for_background),
            "use_for_lighting": bool(use_for_lighting),
            "use_for_reflections": bool(use_for_reflections),
        }

        try:
            result = _plugin("set_environment_map", params)
            if result is None:
                return {"ok": False, "error": "Plugin backend unavailable."}
            raw = result.get("result", result)
            ok = bool(raw.get("success", False)) if isinstance(raw, dict) else False
            return {
                "ok": ok,
                "filepath": str(raw.get("filepath", filepath)) if isinstance(raw, dict) else filepath,
                "message": str(raw.get("message", "")) if isinstance(raw, dict) else "",
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Render to image
    # ------------------------------------------------------------------

    @mcp.tool(annotations=ToolAnnotations(title="Render Viewport to Image", destructiveHint=False))
    def render_to_image(
        output_path: str | None = None,
        width: int = 1920,
        height: int = 1080,
        view_name: str | None = None,
        return_base64: bool = True,
    ) -> dict[str, object]:
        """
        Trigger a Rhino render and return the resulting image.

        The active render engine (e.g. Rhino Cycles) is used. Rhino must
        not already be rendering when this command is issued.

        Parameters
        ----------
        output_path:
            Absolute file path where the render image will be saved.  If
            omitted, a temporary ``.png`` file is created automatically.
        width:
            Render output width in pixels (default 1920).
        height:
            Render output height in pixels (default 1080).
        view_name:
            Name of a named view or viewport to render.  When ``None`` the
            currently active viewport is rendered.
        return_base64:
            If True, the raw PNG bytes are returned as a base-64 encoded
            string in the ``base64`` field.  Set to False for large renders
            where you only need the file path.

        Returns
        -------
        dict with keys:
            ok (bool), filepath (str), base64 (str | None),
            width (int), height (int), format (str)
        """
        width = max(1, min(8192, int(width)))
        height = max(1, min(8192, int(height)))

        params: dict[str, object] = {
            "width": width,
            "height": height,
            "return_base64": bool(return_base64),
        }
        if output_path is not None:
            params["output_path"] = output_path
        if view_name is not None:
            params["view_name"] = view_name

        try:
            result = _plugin("render_viewport", params)
            if result is None:
                return {"ok": False, "error": "Plugin backend unavailable."}
            raw = result.get("result", result)
            if not isinstance(raw, dict):
                return {"ok": False, "error": "Unexpected response from plugin."}
            ok = bool(raw.get("success", False))
            return {
                "ok": ok,
                "filepath": str(raw.get("filepath", "")),
                "base64": raw.get("base64") if return_base64 else None,
                "width": int(raw.get("width", width)),
                "height": int(raw.get("height", height)),
                "format": str(raw.get("format", "png")),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Assign PBR material to objects
    # ------------------------------------------------------------------

    @mcp.tool(annotations=ToolAnnotations(title="Assign PBR Material to Objects", destructiveHint=True))
    def assign_pbr_material_to_objects(
        material_name: str,
        object_ids: list[str] | None = None,
        all_objects: bool = False,
    ) -> dict[str, object]:
        """
        Assign an existing PBR material to one or more Rhino objects.

        Either ``object_ids`` or ``all_objects=True`` must be provided.

        Parameters
        ----------
        material_name:
            Name of the PBR material (as previously created with
            ``create_pbr_material``) to assign.
        object_ids:
            List of object GUIDs to assign the material to.  Each string
            must be a valid UUID as returned by Rhino's object table.
        all_objects:
            If True, the material is applied to every object in the
            document, ignoring ``object_ids``.

        Returns
        -------
        dict with keys:
            ok (bool), assigned_count (int), material_name (str)
        """
        if not all_objects and not object_ids:
            return {"ok": False, "error": "Provide either 'object_ids' or set 'all_objects=True'."}

        params: dict[str, object] = {
            "material_name": material_name,
            "all_objects": bool(all_objects),
        }
        if object_ids is not None:
            params["object_ids"] = object_ids

        try:
            result = _plugin("assign_pbr_material", params)
            if result is None:
                return {"ok": False, "error": "Plugin backend unavailable."}
            raw = result.get("result", result)
            ok = bool(raw.get("success", False)) if isinstance(raw, dict) else False
            return {
                "ok": ok,
                "assigned_count": int(raw.get("assigned_count", 0)) if isinstance(raw, dict) else 0,
                "material_name": material_name,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Get PBR material info
    # ------------------------------------------------------------------

    @mcp.tool(annotations=ToolAnnotations(title="Get PBR Material Info", readOnlyHint=True))
    def get_pbr_material_info(
        material_name: str | None = None,
        material_index: int | None = None,
    ) -> dict[str, object]:
        """
        Return the full PBR property set for a material in the document.

        The returned dictionary mirrors the parameters accepted by
        ``create_pbr_material``, making it straightforward to inspect and
        re-create or duplicate materials.

        Parameters
        ----------
        material_name:
            Name of the material to look up.
        material_index:
            Integer index of the material in the document material table.
            Takes precedence over ``material_name`` when both are supplied.

        Returns
        -------
        dict with keys:
            ok (bool), material (dict of PBR properties)
        """
        if material_name is None and material_index is None:
            return {"ok": False, "error": "Provide either 'material_name' or 'material_index'."}

        params: dict[str, object] = {}
        if material_index is not None:
            params["material_index"] = int(material_index)
        if material_name is not None:
            params["material_name"] = material_name

        try:
            result = _plugin("get_pbr_material", params)
            if result is None:
                return {"ok": False, "error": "Plugin backend unavailable."}
            raw = result.get("result", result)
            ok = bool(raw.get("success", False)) if isinstance(raw, dict) else False
            return {
                "ok": ok,
                "material": raw.get("material") if isinstance(raw, dict) else None,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ------------------------------------------------------------------
    # List PBR materials
    # ------------------------------------------------------------------

    @mcp.tool(annotations=ToolAnnotations(title="List PBR Materials", readOnlyHint=True))
    def list_pbr_materials() -> dict[str, object]:
        """
        Return all Physically-Based materials present in the active document.

        Each entry in the ``materials`` list includes the material index,
        name, and all PBR channel values (metallic, roughness, opacity, IOR,
        emission, and texture file paths where configured).

        Returns
        -------
        dict with keys:
            ok (bool), materials (list[dict]), count (int)
        """
        try:
            result = _plugin("list_pbr_materials", {})
            if result is None:
                return {"ok": False, "error": "Plugin backend unavailable."}
            raw = result.get("result", result)
            ok = bool(raw.get("success", False)) if isinstance(raw, dict) else False
            materials = raw.get("materials", []) if isinstance(raw, dict) else []
            return {
                "ok": ok,
                "materials": materials,
                "count": int(raw.get("count", len(materials))) if isinstance(raw, dict) else len(materials),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Render settings
    # ------------------------------------------------------------------

    @mcp.tool(annotations=ToolAnnotations(title="Set Render Settings", destructiveHint=True))
    def set_render_settings(
        engine: str | None = None,
        samples: int | None = None,
        background_color: list[int] | None = None,
        use_transparent_background: bool | None = None,
        enable_shadows: bool | None = None,
        ambient_occlusion: bool | None = None,
        enable_ground_plane: bool | None = None,
        ground_plane_altitude: float | None = None,
    ) -> dict[str, object]:
        """
        Update document-level render settings.

        Only the parameters explicitly passed are modified; all others retain
        their current values.

        Parameters
        ----------
        engine:
            Render engine identifier.  Supported values: ``"rhino"``
            (Rhino's built-in Cycles-based engine) and ``"cycles"``
            (explicit Cycles selection).  Rhino 8 uses Cycles internally
            for its default PBR renderer.
        samples:
            Number of render samples (path-tracing passes).  Higher values
            reduce noise at the cost of longer render time.
        background_color:
            Solid background colour as [r, g, b] with values 0–255.  Only
            applied when the background style is set to solid colour mode.
        use_transparent_background:
            If True, the render background is written as a transparent
            alpha channel (useful for compositing).
        enable_shadows:
            Enable or disable shadow casting in the render.
        ambient_occlusion:
            Enable or disable ambient-occlusion post-processing.
        enable_ground_plane:
            Enable or disable the infinite reflective ground plane.
        ground_plane_altitude:
            Altitude (Z-height) of the ground plane in document units.

        Returns
        -------
        dict with keys:
            ok (bool), settings (dict of applied settings)
        """
        if background_color is not None and len(background_color) < 3:
            return {"ok": False, "error": "background_color must have at least 3 elements [r, g, b]."}

        params: dict[str, object] = {}
        if engine is not None:
            params["engine"] = str(engine).lower()
        if samples is not None:
            params["samples"] = max(1, int(samples))
        if background_color is not None:
            params["background_color"] = [max(0, min(255, int(v))) for v in background_color[:3]]
        if use_transparent_background is not None:
            params["use_transparent_background"] = bool(use_transparent_background)
        if enable_shadows is not None:
            params["enable_shadows"] = bool(enable_shadows)
        if ambient_occlusion is not None:
            params["ambient_occlusion"] = bool(ambient_occlusion)
        if enable_ground_plane is not None:
            params["enable_ground_plane"] = bool(enable_ground_plane)
        if ground_plane_altitude is not None:
            params["ground_plane_altitude"] = float(ground_plane_altitude)

        try:
            result = _plugin("set_render_settings", params)
            if result is None:
                return {"ok": False, "error": "Plugin backend unavailable."}
            raw = result.get("result", result)
            ok = bool(raw.get("success", False)) if isinstance(raw, dict) else False
            return {
                "ok": ok,
                "settings": raw.get("settings", params) if isinstance(raw, dict) else params,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _plugin(command_type: str, params: dict[str, object]) -> dict[str, object] | None:
    """
    Send a command to the Rhino MCP plugin socket.

    Returns None when the plugin backend is not configured.
    Raises OSError when the socket is configured but unreachable.
    """
    if rhino.preferred_backend() not in {"auto", "plugin"}:
        return None
    try:
        return rhino.plugin_result(command_type, params)
    except OSError:
        return None
