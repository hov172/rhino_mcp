"""Generic Rhino plugin introspection and command execution tools."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import plugin_client

# Plugins installable via Yak (Rhino's package manager CLI) — confirmed package names
_YAK_PLUGINS: dict[str, str] = {
    "pufferfish": "pufferfish",
    "elefront": "elefront",
    "weaverbird": "weaverbird",
    "anemone": "anemone",
    "human": "human",
    "lunchbox": "lunchbox",
}

# Plugins not in Yak — user must install manually via Rhino Package Manager UI or vendor
# key → (friendly instructions, url)
_MANUAL_PLUGINS: dict[str, tuple[str, str]] = {
    "ladybug": ("Open Rhino Package Manager (_PackageManager), search 'Ladybug', install all Ladybug Tools components.", "https://www.food4rhino.com/en/app/ladybug-tools"),
    "honeybee": ("Open Rhino Package Manager (_PackageManager), search 'Honeybee', install Honeybee components.", "https://www.food4rhino.com/en/app/ladybug-tools"),
    "kangaroo": ("Kangaroo 2 is bundled with Rhino 8. Open Grasshopper — it should already be available.", "https://www.food4rhino.com/en/app/kangaroo-physics"),
    "visualarq": ("Download and install from the VisualARQ website. Requires a license.", "https://www.visualarq.com/download/"),
    "lands design": ("Download and install from the Lands Design website. Requires a license.", "https://www.lands-design.com/download/"),
    "lands": ("Download and install from the Lands Design website. Requires a license.", "https://www.lands-design.com/download/"),
}

# Vendor-only paid plugins
_VENDOR_PLUGINS: dict[str, str] = {
    "v-ray": "https://www.chaos.com/vray/rhino",
    "vray": "https://www.chaos.com/vray/rhino",
    "enscape": "https://enscape3d.com",
}


def _yak_path() -> str | None:
    """Return the Yak CLI path for the current platform, or None if not found."""
    candidates = [
        "/Applications/Rhino 8.app/Contents/Resources/bin/yak",
        "/Applications/Rhino 7.app/Contents/Resources/bin/yak",
        r"C:\Program Files\Rhino 8\System\yak.exe",
        r"C:\Program Files\Rhino 7\System\yak.exe",
    ]
    return next((p for p in candidates if os.path.isfile(p)), None)


def _gh_libraries_path() -> str:
    """Return the Grasshopper Libraries folder path for the current platform."""
    if platform.system() == "Darwin":
        return os.path.expanduser(
            "~/Library/Application Support/McNeel/Rhinoceros/8.0/Plug-ins/"
            "Grasshopper (b45a29b1-4343-4035-989e-044e8580d9cf)/Libraries"
        )
    return os.path.join(os.environ.get("APPDATA", ""), "Grasshopper", "Libraries")



def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="List Installed Plugins", readOnlyHint=True))
    def list_installed_plugins() -> dict[str, object]:
        """List all installed Rhino plugins with name, GUID, loaded status, and path."""
        return plugin_client.send_command("list_plugins", {})

    @mcp.tool(annotations=ToolAnnotations(title="Get Plugin Commands", readOnlyHint=True))
    def get_plugin_commands(
        plugin_name: str | None = None,
        plugin_id: str | None = None,
    ) -> dict[str, object]:
        """
        List all Rhino commands registered by a specific plugin.
        Provide plugin_name (partial, case-insensitive) or plugin_id (GUID).
        """
        return plugin_client.send_command(
            "get_plugin_commands",
            {"plugin_name": plugin_name, "plugin_id": plugin_id},
        )

    @mcp.tool(annotations=ToolAnnotations(title="Run Plugin Command", destructiveHint=True))
    def run_plugin_command(command: str, options_string: str = "") -> dict[str, object]:
        """
        Run any Rhino command string, including commands from third-party plugins.
        options_string is appended after the command name (e.g. '_Enter' to confirm prompts).
        """
        full = f"{command} {options_string}".strip()
        return plugin_client.send_command("run_command", {"command": full})

    @mcp.tool(annotations=ToolAnnotations(title="Check Plugin Loaded", readOnlyHint=True))
    def check_plugin_loaded(plugin_name: str) -> dict[str, object]:
        """
        Check whether a plugin is installed and loaded in Rhino.
        Returns {loaded: bool, message: str, plugin: {...}} .
        """
        result = plugin_client.send_command("list_plugins", {})
        plugins = result.get("result", {}).get("plugins", [])
        match = next(
            (p for p in plugins if plugin_name.lower() in p["name"].lower()), None
        )
        if match is None:
            return {
                "loaded": False,
                "message": f"'{plugin_name}' is not installed. Install it via the Rhino Package Manager or the plugin vendor.",
            }
        if not match["loaded"]:
            return {
                "loaded": False,
                "message": f"'{plugin_name}' is installed but not loaded. Use load_plugin to load it.",
            }
        return {"loaded": True, "plugin": match}

    @mcp.tool(annotations=ToolAnnotations(title="Install Plugin", destructiveHint=True))
    def install_plugin(
        plugin_name: str,
        file_path: str | None = None,
    ) -> dict[str, object]:
        """
        Install a Rhino or Grasshopper plugin.

        If file_path is provided (a locally downloaded .gha, .rhp, or .rhi file),
        the plugin is installed from that file — no internet required.
        - .gha  → copied to the Grasshopper Libraries folder (restart Grasshopper)
        - .rhp  → loaded immediately via Rhino's _LoadPlugin command
        - .rhi  → opened with the Rhino Installer (Mac/Windows native handler)

        If file_path is omitted, the tool attempts to install automatically:
        1. Rhino Package Manager — for most open-source plugins
        2. GitHub auto-download — fetches the latest release asset and installs it
        3. food4rhino / vendor — returns the download page URL (login required there)
        """
        key = plugin_name.lower().strip()

        # --- File-based install ---
        if file_path:
            if not os.path.isfile(file_path):
                return {"success": False, "message": f"File not found: {file_path}"}
            ext = os.path.splitext(file_path)[1].lower()

            if ext == ".gha":
                libs = _gh_libraries_path()
                os.makedirs(libs, exist_ok=True)
                dest = os.path.join(libs, os.path.basename(file_path))
                shutil.copy2(file_path, dest)
                return {
                    "success": True,
                    "method": "gha_copy",
                    "destination": dest,
                    "message": f"Copied to Grasshopper Libraries. Restart Grasshopper (or Rhino) to activate '{plugin_name}'.",
                }

            if ext == ".rhp":
                result = plugin_client.send_command("run_command", {"command": f'_LoadPlugin "{file_path}"'})
                return {
                    "success": True,
                    "method": "load_plugin",
                    "message": f"Loaded '{plugin_name}' via _LoadPlugin. No restart required.",
                    "result": result,
                }

            if ext == ".rhi":
                # Open with the OS-registered Rhino Installer handler
                if platform.system() == "Darwin":
                    subprocess.Popen(["open", file_path])
                else:
                    os.startfile(file_path)  # type: ignore[attr-defined]
                return {
                    "success": True,
                    "method": "rhi_installer",
                    "message": f"Rhino Installer opened for '{plugin_name}'. Follow the installer prompts, then restart Rhino.",
                }

            return {"success": False, "message": f"Unsupported file type '{ext}'. Expected .gha, .rhp, or .rhi."}

        # --- Yak silent install ---
        if key in _YAK_PLUGINS:
            package = _YAK_PLUGINS[key]
            yak = _yak_path()
            if not yak:
                return {
                    "success": False,
                    "message": "Yak CLI not found. Open Rhino, type '_PackageManager', search for "
                               f"'{package}', and click Install.",
                }
            proc = subprocess.run(
                [yak, "install", package],
                capture_output=True, text=True, timeout=120,
            )
            if proc.returncode != 0:
                return {
                    "success": False,
                    "method": "yak",
                    "package": package,
                    "message": f"Yak install failed: {proc.stderr.strip() or proc.stdout.strip()}",
                }
            return {
                "success": True,
                "method": "yak",
                "package": package,
                "output": proc.stdout.strip(),
                "message": f"'{plugin_name}' installed successfully. Restart Rhino to activate it.",
            }

        # --- Manual install (not in Yak) ---
        if key in _MANUAL_PLUGINS:
            instructions, url = _MANUAL_PLUGINS[key]
            return {
                "success": False,
                "method": "manual_required",
                "url": url,
                "message": instructions,
            }

        if key in _VENDOR_PLUGINS:
            url = _VENDOR_PLUGINS[key]
            return {
                "success": False,
                "method": "vendor_installer_required",
                "download_url": url,
                "message": (
                    f"'{plugin_name}' requires a paid license and vendor installer. "
                    f"Download and install from: {url}"
                ),
            }

        return {
            "success": False,
            "message": (
                f"'{plugin_name}' not found in known plugin sources. "
                "Try _PackageManager in Rhino to search manually, or provide a file_path to install from a downloaded file."
            ),
        }
