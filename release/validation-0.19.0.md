# Release 0.19.0 validation — 2026-10-04

- 538 nonintegration tests plus five subtests passed; ruff passed; `scripts/check_skill_tools.py` passed.
- C# plugin built with 0 warnings and 0 errors. All 358 tools remain registered; Python, C# assembly, Yak, installer, and Docker version metadata is 0.19.0.
- Commit `fbf69b3` on main, tag `v0.19.0` pushed. GitHub release v0.19.0 published and marked latest with five assets: signed installer, signed uninstaller, Yak package, `rhino-mcp.rhp`, `SHA256SUMS-0.19.0`. An authenticated download of the checksum asset matched the local file byte for byte.
- The repository is private, so unauthenticated `releases/download` URLs return 404, including the ones linked from the README. This is unchanged from 0.18.0.
- Docker image `rhino-mcp:0.19.0` (also tagged `latest`) built successfully. Inside the image: package version 0.19.0, 358 tools in the compact registry, the GH2 wire normalisation, FBX `file_type`, and `current_massing_layer` state field are present, and an HTTP server bound to loopback returned `{"status":"ok"}` from `/health`. The default non-loopback command still refuses to start without TLS, as documented. No container is deployed.
- The local installation reports 0.19.0. All seven installed Rhino bundle files in `~/Library/Application Support/McNeel/Rhinoceros/8.0/MacPlugIns/rhino-mcp.rhp/` and `/Users/Shared/rhino_mcp/plugin/` match the released plugin by content (`rhino-mcp.rhp` MD5 `fea6495a…`), and `/Users/Shared/rhino_mcp/VERSION` reads 0.19.0. Rhino was closed during installation. A clean-machine installation test was not performed.
- Not live-verified: environment map assignment (`set_environment_map`), script component port reshaping (`gh_add_script_component`), Grasshopper 2 placement and wiring (needs Rhino 9 WIP), and the V-Ray and Enscape command macros. No live plugin ping or integration test was run against 0.19.0; Rhino was not started after installation.

## Signed package verification

- Installer and uninstaller: Apple notarization accepted; tickets stapled and validated; Gatekeeper accepted both as Notarized Developer ID.
- Installer submission: 4ea63f4b-317b-442d-a0d3-41e73d9a522c.
- Uninstaller submission: bd09a831-4ed6-445c-830e-9c44369fe0b2.
- `SHA256SUMS-0.19.0` records the two stapled packages, the plugin zip, the plugin assembly, the Yak package, the Python wheel and sdist, and the third-party notice/inventory archive. The third-party archive was extracted from the signed installer payload.
