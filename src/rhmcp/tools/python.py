"""
Tools for executing Python inside Rhino.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino

# R6-3: Maximum code length for execution tools (200 KB)
_MAX_CODE_LEN = 200_000


def _wrap_with_revert(code: str, clear_objects: list[str] | None = None) -> str:
    code = code.expandtabs(4)
    indented = "\n".join("    " + line for line in code.splitlines())

    # Build a pre-execution block that deletes all objects on the requested layers.
    if clear_objects:
        layer_list = repr(clear_objects)
        clear_block = (
            'for _mcp_ln in ' + layer_list + ':\n'
            '    _mcp_layer = _mcp_doc.Layers.FindName(_mcp_ln)\n'
            '    if _mcp_layer is not None:\n'
            '        _mcp_objs = _mcp_doc.Objects.FindByLayer(_mcp_layer)\n'
            '        if _mcp_objs:\n'
            '            for _mcp_o in _mcp_objs:\n'
            '                _mcp_doc.Objects.Delete(_mcp_o.Id, True)\n'
        )
    else:
        clear_block = ''

    return (
        'import rhinoscriptsyntax as rs\n'
        'import Rhino as _mcp_Rhino\n'
        '_mcp_doc = _mcp_Rhino.RhinoDoc.ActiveDoc\n'
        + clear_block +
        '_mcp_ids_before = set(str(o.Id) for o in _mcp_doc.Objects)\n'
        'try:\n'
        f'{indented}\n'
        'except Exception as _mcp_ex:\n'
        '    try:\n'
        '        for _o in list(_mcp_doc.Objects):\n'
        '            if str(_o.Id) not in _mcp_ids_before:\n'
        '                _mcp_doc.Objects.Delete(_o.Id, True)\n'
        '        _mcp_doc.Views.Redraw()\n'
        '    except Exception:\n'
        '        pass\n'
        '    raise _mcp_ex\n'
    )


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Execute Rhino Python", destructiveHint=True))
    def execute_rhino_python(
        code: str,
        rhino_id: str | None = None,
        verified_functions: list[str] | None = None,
        clear_objects: list[str] | None = None,
    ) -> dict[str, object]:
        """Execute Python code inside Rhino.

        The code runs with access to Rhino's Python environment, including
        ``rhinoscriptsyntax`` and RhinoCommon. Assign a JSON-serialisable value..."""
        # R6-3: Enforce maximum code length
        if len(code) > _MAX_CODE_LEN:
            return {"ok": False, "error": f"Code exceeds maximum length of {_MAX_CODE_LEN} characters."}
        result = rhino.execute_python(_wrap_with_revert(code, clear_objects), rhino_id=rhino_id)
        if not verified_functions:
            result["api_warning"] = (
                "verified_functions not provided — consider using "
                "search_rhinoscript_functions before writing code to avoid "
                "hallucinated API calls."
            )
        return result

    @mcp.tool(annotations=ToolAnnotations(title="Execute RhinoCommon CSharp", destructiveHint=True))
    def execute_rhino_csharp(code: str, rhino_id: str | None = None) -> dict[str, object]:
        """Execute C# code inside Rhino through ``rhinocode script``.

        This requires RhinoCode C# script support in the target Rhino version.
        Return information through stdout or by changing..."""
        # R6-3: Enforce maximum code length
        if len(code) > _MAX_CODE_LEN:
            return {"ok": False, "error": f"Code exceeds maximum length of {_MAX_CODE_LEN} characters."}
        return rhino.execute_script(code, ".cs", rhino_id=rhino_id)
