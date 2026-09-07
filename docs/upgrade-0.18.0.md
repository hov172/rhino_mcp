# Upgrading to 0.18.0

0.18.0 replaces PyMuPDF with pypdfium2 (PDFium) and pdfplumber, corrects the PDF review findings, and preserves all 358 tools. The Rhino plugin has matching version metadata; PDF processing runs in Python and does not require changes to the Rhino document.

Quit Rhino before installing the matching signed package, then restart Rhino and the AI client. The [0.17.1 registration repair](upgrade-0.17.1.md) and [TLS requirements](secure-operation.md) still apply. Builds do not automatically replace the installed package or a running container.

## PDF API changes

- `read_pdf_vectors` still returns `start`/`end` in PDF points (72 per paper inch), now explicitly labeled with `coordinate_units: points` and `coordinate_origin: rotated_crop_top_left`.
- Prefer `real_units_per_point` from `read_pdf`'s scale result. Alternatively, pass `real_units_per_px` with the **same `dpi` used for rendering/calibration**. The new vector `dpi` defaults to 150; use 200/300 explicitly if you rendered at that DPI. Old versions multiplied points by a pixel ratio and produced incorrect model dimensions.
- Cubic curves have `type: curve` and two `control_points`; they are not flattened or assigned a misleading straight-line length. Drawing commands do not prove clipped/layer-visible geometry; `visibility_verified` remains false. Unsupported commands set `partial`.
- Dimension annotations use rotated crop-relative pixels and explicit units. Results are marked estimated; bare part numbers are no longer treated as dimensions. Text grouping differs from the old span-based parser. No OCR is performed.
- `get_pdf_info` accepts `pages` and `max_pages` (default 50). Other readers default to 10. All cap a call at 50 and report `truncated`; request subsequent pages explicitly.
- DPI must be an integer from 50 to 600; invalid values now fail instead of being silently clamped. Scale ratios must be finite and positive. Out-of-range page requests fail instead of returning an empty success.

Example: render at 200 DPI, then call `read_pdf_vectors(path, dpi=200, real_units_per_px=render_result["scale"]["real_units_per_px"])`. A one-inch paper line at `1/4" = 1'` must produce four real feet at any supported DPI.

## Processing limits and errors

Workers are separate processes, capped at two concurrent calls per server. MCP cancellation propagates through compact dispatch and terminates the PDF worker. Limits: 50 MiB input, 30 seconds, 768 MiB monitored RSS, 16 million pixels per page / 32 million per request, 10000 output geometry/dimension items, 200000 characters per page, and 24 MiB JSON output. Lower DPI or select fewer pages when a request exceeds a budget. Linux adds an address-space ceiling; POSIX adds CPU/file-size ceilings. These limits do not replace OS account isolation.

Errors include `PDF_PASSWORD_REQUIRED`, `INVALID_PDF`, `INVALID_PAGE_RANGE`, `INVALID_VALUE`, `PDF_LIMIT_EXCEEDED`, `PDF_BUSY`, `PDF_CANCELLED`, `PDF_TIMEOUT`, `PDF_WORKER_FAILED`, `PDF_UNSUPPORTED_GEOMETRY`, and `NO_VECTORS`. Password-protected files must be unlocked outside this tool. Ambiguous crop/UserUnit geometry fails explicitly instead of returning misaligned coordinates.

## Dependency and release verification

The installer consumes exported hashed requirements from `uv.lock` for both architectures. Current cryptography no longer publishes Intel macOS wheels: `scripts/build-intel-cryptography.py` builds the locked source with hash-verified OpenSSL 3.6.4, records provenance, and includes its native notice. This requires Xcode command-line tools, Rust with the Intel target, and the bundled Intel Python runtime. A verified wheel cache is retained under `release/intel-wheels/`.

`third-party/` in the installer contains per-architecture Python inventories, CycloneDX package inventories, collected license notices (including PDFium's native notices), hashed requirements, and Intel cryptography provenance. Docker includes `/app/third-party/`. These package inventories do not claim a complete native binary dependency graph.

CI rejects PyMuPDF/MuPDF distributions in the environment, checks replacement-library notices, and scans locked production dependencies with pip-audit. The exact runtime inventories are checked again when building installers. New PDF regression tests cover geometry scaling, curves, rotation/crop, encrypted/malformed input, pagination, limits, and worker lifecycle.

## Licensing scope

Removing PyMuPDF addresses that dependency in new builds. It does not alter obligations for previous releases or establish that every other dependency is suitable for every proprietary use. Bundled components retain their own licenses; preserve the provided notices. This update does not make the Python source private or compile it into a proprietary executable.
