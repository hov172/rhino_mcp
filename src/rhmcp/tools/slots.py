from __future__ import annotations
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations


def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=ToolAnnotations(title="List Rhino Instances", readOnlyHint=True))
    def get_rhino_instances() -> dict:
        """Return all live Rhino instances with MCP plugin running.
        Each entry has rhino_id, host, port, version, rhino_version, started_at.
        Pass rhino_id to any other tool to target a specific..."""
        from rhmcp.tools_helpers import slot_registry
        slots = slot_registry.discover()
        return {
            "ok": True,
            "instances": [
                {
                    "rhino_id": s.rhino_id,
                    "host": s.host,
                    "port": s.port,
                    "version": s.version,
                    "rhino_version": s.rhino_version,
                    "started_at": s.started_at,
                }
                for s in slots.values()
            ],
            "count": len(slots),
        }

    @mcp.tool(annotations=ToolAnnotations(title="Launch Rhino"))
    def launch_rhino(
        rhino_path: str | None = None,
        timeout: float | None = None,
    ) -> dict:
        """Launch a new Rhino instance and wait for the MCP plugin to start.
        Returns rhino_id to pass to other tools to target this specific instance.

        rhino_path: Optional path to Rhino..."""
        from rhmcp.tools_helpers import rhino_launcher
        t = timeout or 60.0
        path = Path(rhino_path) if rhino_path else None
        try:
            pid = rhino_launcher.launch(path, timeout=t)
            return {"ok": True, "rhino_id": str(pid), "pid": pid}
        except (RuntimeError, TimeoutError) as ex:
            return {"ok": False, "error": str(ex)}
