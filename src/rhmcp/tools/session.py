"""
Tools for discovering Rhino instances and running direct Rhino commands.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="List Rhino Instances", readOnlyHint=True))
    def get_rhino_instances() -> dict[str, object]:
        """
        List running Rhino instances known to ``rhinocode``.

        Rhino must be running and ``StartScriptServer`` must have been executed
        inside Rhino for instances to appear.
        """
        return rhino.list_instances()

    @mcp.tool(annotations=ToolAnnotations(title="Get Rhino Commands", readOnlyHint=True))
    def get_rhino_commands(
        filter: str = "",
        loaded_only: bool = True,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        List all available Rhino command names, optionally filtered by substring.

        ``loaded_only=True`` (default) returns only commands from currently loaded
        plugins. Set ``False`` to include commands from unloaded plugins as well.
        Use this before ``run_rhino_command`` to discover exact command names
        rather than guessing.
        """
        code = "__mcp_filter = {!r}\n__mcp_loaded_only = {!r}\n".format(filter, loaded_only) + r"""
import Rhino
names = []
try:
    names = list(Rhino.Commands.Command.GetCommandNames(__mcp_loaded_only, True))
except Exception:
    try:
        names = list(Rhino.Commands.Command.GetCommandNames())
    except Exception:
        pass
if __mcp_filter:
    names = [n for n in names if __mcp_filter.lower() in n.lower()]
names.sort()
result = {"commands": names, "count": len(names)}
"""
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Run Rhino Command", destructiveHint=True))
    def run_rhino_command(
        command: str,
        echo: bool = False,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Run a Rhino command macro such as ``_Circle 0,0,0 20``.

        ``echo=True`` echoes the command string to Rhino's command history so users
        can follow along in the Rhino window. Only supported when routing through
        the plugin backend (has no effect via rhinocode).
        Use ``rhino_id`` from ``get_rhino_instances`` when more than one Rhino
        process is running.
        """
        return rhino.run_command(command, echo=echo, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Get Rhino Backend Status", readOnlyHint=True))
    def get_rhino_backend_status(rhino_id: str | None = None) -> dict[str, object]:
        """
        Report available Rhino backends: Rhino 8 rhinocode, RhinoMCP plug-in socket, and selected mode.
        """
        return rhino.status(rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Health Check", readOnlyHint=True))
    def health_check(timeout: float = 3.0) -> dict[str, object]:
        """
        Ping the RhinoMCP plugin socket and return connection latency and Rhino version.

        Returns ``ok: true`` with ``latency_ms`` and ``rhino`` version string when
        the plugin is reachable. Returns ``ok: false`` with ``error_code`` when the
        socket is unavailable or Rhino does not respond.
        """
        from rhmcp.tools_helpers.plugin_client import health_check as _hc
        return _hc(timeout=timeout)

    @mcp.tool(annotations=ToolAnnotations(title="List Rhino Plugins", readOnlyHint=True))
    def list_rhino_plugins(rhino_id: str | None = None) -> dict[str, object]:
        """
        List installed Rhino plug-ins when the plug-in backend is available.

        Falls back to a Rhino Python query on Rhino 8 if script execution works.
        """
        try:
            return rhino.plugin_result("list_plugins", {})
        except OSError:
            code = """
import Rhino
from Rhino.PlugIns import PlugIn
plugins = []
for item in PlugIn.GetInstalledPlugIns():
    plugins.append({"id": str(item.Key), "name": item.Value, "loaded": PlugIn.Find(item.Key) is not None})
result = {"plugins": plugins, "count": len(plugins)}
"""
            return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Load Rhino Plugin", destructiveHint=True))
    def load_rhino_plugin(id: str | None = None, path: str | None = None, rhino_id: str | None = None) -> dict[str, object]:
        """
        Load an installed Rhino plug-in by id, or install/load a plug-in from a full path.
        """
        params = {"id": id, "path": path}
        params = {key: value for key, value in params.items() if value is not None}
        try:
            return rhino.plugin_result("load_plugin", params)
        except OSError:
            import json

            code = "__mcp_plugin = {!s}\n{}".format(json.dumps(params), """
from System import Guid
from Rhino.PlugIns import PlugIn
if __mcp_plugin.get("path"):
    loaded_id = Guid.Empty
    status = PlugIn.LoadPlugIn(__mcp_plugin["path"], loaded_id)
    result = {"success": str(loaded_id) != str(Guid.Empty), "id": str(loaded_id), "status": str(status)}
else:
    plugin_id = Guid(__mcp_plugin["id"])
    result = {"success": bool(PlugIn.LoadPlugIn(plugin_id, True, True)), "id": str(plugin_id)}
""")
            return rhino.execute_python(code, rhino_id=rhino_id)
