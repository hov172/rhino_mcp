# Upgrading to 0.17.1

0.17.1 fixes the macOS installer issue where `MCPStart` was missing after installation or a Rhino update. The 0.17.0 installer copied files into `Plug-ins`, while Rhino for Mac discovers plugin bundles in `MacPlugIns`. A cached path could also still point to a removed application-bundle copy.

1. Quit Rhino completely before running the signed 0.17.1 installer.
2. Install `rhino-mcp-0.17.1-universal-signed.pkg` from the [GitHub release](https://github.com/hov172/rhino_mcp/releases/tag/v0.17.1).
3. Restart Rhino and run `MCPStatus`. The plugin should start automatically and report version 0.17.1 to a health query.
4. Restart the AI client to load the matching Python server.

The installer places the assembly and dependencies at `~/Library/Application Support/McNeel/Rhinoceros/8.0/MacPlugIns/rhino-mcp.rhp/` (and the equivalent Rhino 9 folder). It repairs this plugin's cached file path, backs up misplaced files/settings, and retires conflicting legacy installations. Backups are retained under the user's `Library/Application Support/rhino-mcp/backups` and, for application copies, `/Users/Shared/rhino-mcp-legacy-plugin.*`.

Plugin registration is checked before the client-configuration version marker, so rerunning `/usr/local/bin/rhino-mcp-configure` repairs missing plugin files even if that version was configured before. Rhino must be closed for that command. The uninstaller removes the correct bundle.

Python, C#, Yak, Docker metadata, and macOS packages use 0.17.1; the tool count stays 358. The [0.17.0 TLS and behavior changes](secure-operation.md) still apply. Rhino licensing is independent: installing this package does not enable saving with an expired evaluation license.

The bundle location follows [McNeel's macOS installation guidance](https://developer.rhino3d.com/guides/rhinocommon/plugin-installers-mac/).

Regression coverage includes bundle discovery, cached-path migration with unrelated settings preserved, missing dependency repair, and failure before mutation when the source assembly is absent. The full non-integration suite contains 476 tests plus five subtests.

## Verified installation

On 2026-09-07, the installed plugin and all dependencies matched the release, and Rhino’s cached registration pointed to the correct bundle. Live `ping` returned plugin **0.17.1** on Rhino **8.34.26223.11002**. The installed Python server initialized as **0.17.1** and completed a read-only `get_document_summary` call through MCP with `ok: true` and `backend: plugin`. See the [full validation record](../release/validation-0.17.1.md).

To check your installation, run `MCPStatus` in Rhino, then ask your AI client to call `get_rhino_backend_status` and `get_document_summary`. For compact mode, invoke the latter through `call_rhino_tool`. Listener status alone does not establish that the AI client can complete a request.

The [GitHub release](https://github.com/hov172/rhino_mcp/releases/tag/v0.17.1) includes signed and notarized universal installer/uninstaller packages, the plugin ZIP, `.rhp`, `.yak`, Python wheel and source distribution, checksums, and validation notes. Both package tickets passed stapler and Gatekeeper checks. GitHub publication does not publish to PyPI, the McNeel package server, or a Docker registry; rebuilding an image does not replace a running container.
