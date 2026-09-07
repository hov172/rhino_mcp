# Release 0.18.0 validation — 2026-09-07

- 512 nonintegration tests plus five subtests passed; lint and whitespace checks passed.
- GitHub CI passed on Python 3.10, 3.11, and 3.12, with the new dependency-policy/advisory job.
- Locked production dependencies: pip-audit reported no known vulnerabilities. This does not certify every bundled native component.
- All 358 tools remain registered; Python, C# assembly, Yak, installer, and Docker version metadata is 0.18.0.
- Both packaged macOS runtimes passed all four PDF tool smoke checks and the one-inch-to-four-feet scaling regression. All packaged Python source files match the release source, and plugin payload files match the released plugin by content.
- Both runtime inventories contain 70 Python packages, no PyMuPDF, collected license notices, and CycloneDX Python component inventories. The installer includes hashed requirements and Intel cryptography/OpenSSL provenance.
- Intel cryptography 50.0.1 uses statically linked OpenSSL 3.6.4 and built-in providers. Apple Silicon uses the upstream cryptography 50.0.1 wheel with OpenSSL 4.0.2. These are different native builds of the same locked Python dependency version.
- Docker image `rhino-mcp:0.18.0` (also tagged `latest`) built successfully. All four PDF tools passed again in the completed image with networking disabled.
- No Rhino MCP container was running during validation. Building the image does not establish a running Docker deployment.
- The local installation now reports 0.18.0. Both installed Python source trees and cryptography binaries match the corrected package; the installed Intel provenance records static libraries/providers. No PyMuPDF directories remain in either environment. All seven installed Rhino bundle files match the final plugin payload. A clean-machine installation test was not performed.
- Live plugin ping reports version 0.18.0. Both extracted MCP servers initialized as 0.18.0, performed a PDF call through compact stdio dispatch, and completed a read-only document-summary round trip to Rhino 8.34.26223.11002. This does not validate every tool or document mutation/recovery.

## Signed package verification

- Installer and uninstaller: Apple notarization accepted; tickets stapled and validated; Gatekeeper accepted as Notarized Developer ID.
- Installer submission: f316c33e-01c5-4be8-bbd8-918d930f634a.
- Uninstaller submission: 2fd60520-ef52-493f-bb3b-41be82a50ae6.
- Both installed runtimes passed PDF smoke checks and imported cryptography with warnings treated as errors.
- `SHA256SUMS-0.18.0` records the final stapled packages and six other release artifacts, including the third-party notice/inventory archive.

