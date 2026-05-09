"""
Tools for executing Python inside Rhino.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def _wrap_with_revert(code: str) -> str:
    indented = "\n".join("    " + line for line in code.splitlines())
    return (
        'import rhinoscriptsyntax as rs\n'
        'import Rhino as _mcp_Rhino\n'
        '_mcp_doc = _mcp_Rhino.RhinoDoc.ActiveDoc\n'
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
    ) -> dict[str, object]:
        """
        Execute Python code inside Rhino.

        The code runs with access to Rhino's Python environment, including
        ``rhinoscriptsyntax`` and RhinoCommon. Assign a JSON-serialisable value
        to ``result`` to return data.

        :param verified_functions: List of RhinoScript/RhinoCommon function names
            that the caller has looked up (e.g. via ``search_rhinoscript_functions``)
            before writing this code. Providing this list documents that API calls
            have been verified and suppresses the api_warning in the response.
        """
        result = rhino.execute_python(_wrap_with_revert(code), rhino_id=rhino_id)
        if not verified_functions:
            result["api_warning"] = (
                "verified_functions not provided — consider using "
                "search_rhinoscript_functions before writing code to avoid "
                "hallucinated API calls."
            )
        return result

    @mcp.tool(annotations=ToolAnnotations(title="Execute RhinoCommon CSharp", destructiveHint=True))
    def execute_rhino_csharp(code: str, rhino_id: str | None = None) -> dict[str, object]:
        """
        Execute C# code inside Rhino through ``rhinocode script``.

        This requires RhinoCode C# script support in the target Rhino version.
        Return information through stdout or by changing the active document.
        """
        return rhino.execute_script(code, ".cs", rhino_id=rhino_id)
