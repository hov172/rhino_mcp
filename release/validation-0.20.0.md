# Release 0.20.0 validation — 2026-10-04

- 547 nonintegration tests plus five subtests passed; ruff passed; `scripts/check_skill_tools.py` passed.
- C# plugin built with 0 warnings and 0 errors. All 358 tools remain registered; Python, C# assembly, Yak, installer, and Docker version metadata is 0.20.0.
- Commit `a72e8eb` carries the source changes and version bump; the release-records commit on top of it is tagged `v0.20.0`. GitHub release v0.20.0 published with ten assets: signed installer, signed uninstaller, plugin ZIP, `rhino-mcp.rhp`, Yak package, Python wheel and sdist, third-party archive, `SHA256SUMS-0.20.0`, and this record.
- The repository is private, so unauthenticated `releases/download` URLs return 404, including the ones linked from the README. Unchanged from 0.19.0.
- Docker image `rhino-mcp:0.20.0` (also tagged `latest`, id `3ced58c2c003`) built successfully. Inside the image: package version 0.20.0, 358 tools in the compact registry, the GH2 `solve` flag and GH1 `type_name` parameter are present, and an HTTP server bound to loopback returned `{"status":"ok"}` from `/health`. No rhino-mcp container is deployed; Docker Desktop was quit after the check.
- The local installation reports 0.20.0. All seven installed Rhino bundle files in `~/Library/Application Support/McNeel/Rhinoceros/8.0/MacPlugIns/rhino-mcp.rhp/` and `/Users/Shared/rhino_mcp/plugin/` match the released plugin by content (`rhino-mcp.rhp` MD5 `11e33309…`), and `/Users/Shared/rhino_mcp/VERSION` reads 0.20.0. The bundles were swapped by directory rename while Rhino 8 was running, so the 0.20.0 plugin loads on the next Rhino restart. A clean-machine installation test was not performed.
- Not live-verified: name-based `gh_add_component`, index-based GH1 wire ports, and the GH2 `solve` summary on `gh2_apply_graph`, `gh2_place_component`, `gh2_place_slider`, and `gh2_solve_graph` (Grasshopper 2 needs Rhino 9 WIP). The 0.19.0 unverified items (environment maps, script component port reshaping, V-Ray and Enscape macros) remain unverified. No live plugin ping or integration test was run against 0.20.0.

## Signed package verification

- Installer and uninstaller: Apple notarization accepted; tickets stapled and validated; Gatekeeper accepted both as Notarized Developer ID.
- Notarization submissions: 04f92607-3e43-4889-9579-c22829f6fb5a and 980e6cf5-b5a8-47a4-b073-314252084df8.
- `SHA256SUMS-0.20.0` records the two stapled packages, the plugin zip, the plugin assembly, the Yak package, the Python wheel and sdist, and the third-party notice/inventory archive. The third-party archive was extracted from the signed installer payload.
