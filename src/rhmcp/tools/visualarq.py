"""VisualARQ architectural BIM tools for Rhino.

VisualARQ has no public scripting API and its ``va*`` commands are
interactive: the creation tools below only launch the command, which then
expects mouse input.  Geometry, dimensions and styles cannot be passed
programmatically, so those parameters are not offered.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend
from rhmcp.tools_helpers import plugin_client
from rhmcp.tools_helpers.security import sanitise_rhino_path


def _check() -> str | None:
    result = plugin_client.send_command("list_plugins", {})
    plugins = result.get("result", {}).get("plugins", [])
    if not any("VisualARQ" in p.get("name", "") and p.get("loaded") for p in plugins):
        return "VisualARQ is not installed or not loaded. Install from visualarq.com."
    return None


def _run(command: str) -> dict:
    return backend.run_command(command)


def _py(code: str) -> dict:
    return backend.execute_python(code)


def _outcome(res: dict) -> tuple[bool, str | None]:
    """Extract (ok, error) from a backend response so failures propagate."""
    ok = bool(res.get("ok"))
    if ok:
        return True, None
    return False, str(res.get("error") or res.get("message") or "Rhino command failed")


# Guarded probe for a VisualARQ Python scripting module. VisualARQ does not
# document a Python API, so we only ever *look* for one (no blind imports) and
# fail honestly when none is found. Works in both IronPython 2 (imp) and
# CPython 3 (importlib.util.find_spec).
_VA_PROBE = r'''
def _find_va_module():
    names = ("VisualARQ", "visualarq")
    try:
        from importlib.util import find_spec
    except ImportError:
        find_spec = None
    for _name in names:
        if find_spec is not None:
            try:
                if find_spec(_name) is not None:
                    return _name
            except (ImportError, ValueError):
                continue
        else:
            try:
                import imp
                imp.find_module(_name)
                return _name
            except ImportError:
                continue
    return None

_VA_UNAVAILABLE = (
    "VisualARQ does not expose a documented Python scripting module in this "
    "Rhino Python environment (checked: VisualARQ, visualarq). Use VisualARQ's "
    "interactive commands or its Grasshopper components instead."
)
'''


def _va_script_result(operation: str) -> dict:
    """Run the probe inside Rhino and return an honest ok:False response."""
    code = _VA_PROBE + f"""
_mod = _find_va_module()
if _mod is None:
    result = {{"ok": False, "error": _VA_UNAVAILABLE}}
else:
    result = {{"ok": False, "error": (
        "Python module '%s' is present, but rhino_mcp has no verified "
        "VisualARQ scripting API for {operation}; refusing to guess at an "
        "undocumented API." % _mod)}}
"""
    return _py(code)


def _interactive(command: str, **extra: object) -> dict[str, object]:
    result = _run(command)
    ok, error = _outcome(result)
    out: dict[str, object] = {
        "success": ok,
        "command": command,
        "note": (
            f"{command} is an interactive VisualARQ command that expects mouse "
            "input; nothing can be applied programmatically."
        ),
        "result": result,
    }
    out.update(extra)
    if error:
        out["error"] = error
    return out


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: Create Wall", destructiveHint=True))
    def varq_create_wall() -> dict[str, object]:
        """Launch the interactive ``_vaWall`` command.

        VisualARQ has no scripting API: wall points, height and style are
        chosen with the mouse; nothing can be passed programmatically.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        return _interactive("_vaWall", applied={}, not_applied={})

    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: Add Opening (Window/Door)", destructiveHint=True))
    def varq_add_opening(opening_type: str = "window") -> dict[str, object]:
        """Launch the interactive ``_vaWindow`` or ``_vaDoor`` command.

        opening_type: window | door. The host wall, position, size and style
        are chosen with the mouse; nothing can be passed programmatically.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        cmd = "_vaWindow" if opening_type.lower() == "window" else "_vaDoor"
        return _interactive(cmd, opening_type=opening_type)

    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: Create Slab", destructiveHint=True))
    def varq_create_slab() -> dict[str, object]:
        """Launch the interactive ``_vaSlab`` command.

        Boundary curves, thickness and style are chosen with the mouse;
        nothing can be passed programmatically.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        return _interactive("_vaSlab")

    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: Create Column", destructiveHint=True))
    def varq_create_column() -> dict[str, object]:
        """Launch the interactive ``_vaColumn`` command.

        Position, height and style are chosen with the mouse; nothing can be
        passed programmatically.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        return _interactive("_vaColumn")

    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: Create Stair", destructiveHint=True))
    def varq_create_stair() -> dict[str, object]:
        """Launch the interactive ``_vaStair`` command.

        Start point, direction, width, rise/run and style are chosen with the
        mouse; nothing can be passed programmatically.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        return _interactive("_vaStair")

    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: Create Railing", destructiveHint=True))
    def varq_create_railing() -> dict[str, object]:
        """Launch the interactive ``_vaRailing`` command.

        Path curve, height and style are chosen with the mouse; nothing can
        be passed programmatically.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        return _interactive("_vaRailing")

    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: Set Level", destructiveHint=True))
    def varq_set_level() -> dict[str, object]:
        """Open the interactive ``_vaLevels`` dialog.

        Level names and elevations are edited in the dialog; nothing can be
        passed programmatically.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        return _interactive("_vaLevels")

    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: Export IFC", destructiveHint=True))
    def varq_export_ifc(output_path: str) -> dict[str, object]:
        """Export the model to IFC via ``_vaExportIFC``.

        The IFC schema version (IFC2x3 / IFC4) is taken from VisualARQ's IFC
        Export Options dialog; the command documents no version option, so
        none is offered here.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        safe_path = sanitise_rhino_path(output_path)
        result = _run('_vaExportIFC "' + safe_path + '"')
        ok, error = _outcome(result)
        out: dict[str, object] = {
            "success": ok,
            "output_path": output_path,
            "result": result,
        }
        if error:
            out["error"] = error
        return out

    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: Get Object Properties", readOnlyHint=True))
    def varq_get_object_properties(object_id: str) -> dict[str, object]:
        """Get VisualARQ type, style, level, and IFC properties for an object."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        res = _va_script_result("reading object properties")
        ok, error = _outcome(res)
        out: dict[str, object] = {"success": ok, "object_id": object_id, "result": res}
        if error:
            out["error"] = error
        return out

    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: List Styles", readOnlyHint=True))
    def varq_list_styles(object_type: str = "wall") -> dict[str, object]:
        """
        List available VisualARQ styles for an object type.
        object_type: wall | door | window | slab | column | stair | railing.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        valid = ("wall", "door", "window", "slab", "column", "stair", "railing")
        if object_type.lower() not in valid:
            return {"success": False, "message": f"Unknown object_type '{object_type}'. Valid: {', '.join(valid)}"}
        res = _va_script_result(f"listing {object_type.lower()} styles")
        ok, error = _outcome(res)
        out: dict[str, object] = {"success": ok, "object_type": object_type, "result": res}
        if error:
            out["error"] = error
        return out
