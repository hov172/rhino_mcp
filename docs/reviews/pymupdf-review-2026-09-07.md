# PyMuPDF usage review — 2026-09-07

> Remediation follow-up: the 0.18.0 implementation replaces PyMuPDF, corrects the tested PDF defects, isolates processing, and adds locked installer dependencies, notices, and CI audit checks. See [upgrade details](../upgrade-0.18.0.md). The findings below describe the reviewed 0.17.1 baseline; historical licensing obligations still require separate assessment.

Reviewed source: `dc3e8e01ab7fc8df2d769f607ebe256ac79d1296` (rhino-mcp 0.17.1).

## Conclusion

PyMuPDF is a mandatory packaged dependency used directly by four PDF-reading tools in one Python module. It is not used by the C# Rhino plugin or the urban PDF report generator. Replacement is therefore contained at the application level, although PDF rendering, geometry, text grouping, and coordinates need careful compatibility work.

For the proposed proprietary distribution, resolve the PyMuPDF licensing basis before release. Separately, correct verified geometry errors, isolate native PDF processing, and make installer dependency resolution reproducible. Compiling Python, disabling PDF tools in a profile, or moving the server into Docker does not resolve the dependency's licensing terms.

This is an engineering and licensing-evidence review, not a legal determination that an infringement has occurred. No commercial agreement was supplied or assessed. No application code, installed package, release, or repository visibility was changed during this review.

## Scope and method

- Searched source, manifests, lockfile, tests, installer scripts, Dockerfile, and C# plugin for PyMuPDF/MuPDF/fitz references; also inspected Python imports with AST.
- Read each PDF implementation and the MCP runtime's authorization/concurrency wrapper.
- Inspected local development and both installed macOS environments, the Python wheel, and the existing Docker image.
- Ran small synthetic PDF probes in development PyMuPDF 1.27.2.3 and installed Apple Silicon PyMuPDF 1.28.2. Probes used temporary documents; no user models or documents were read or changed.
- Queried OSV's PyPI package/version API for both exact versions. Both returned no matching advisories on this date. This is not a complete audit of MuPDF's bundled native dependencies or proof of safety.
- Consulted upstream licensing, coordinate, threading, and replacement-library documentation.

## Usage inventory

All four tools lazily `import fitz`, open local files in the Python MCP process, and are marked read-only. They do not dispatch PDF parsing to Rhino.

| Tool / source location | PyMuPDF operations | User-visible function |
|---|---|---|
| `get_pdf_info`, `src/rhmcp/tools/documents.py:182` | `open`, metadata, page iteration and `rect` | Page count, dimensions, title, author, subject, creator |
| `read_pdf`, same file:234 | `open`, `Matrix`, `get_pixmap`, PNG serialization, `get_text("text")` | Page images, extracted text, nominal drawing scale |
| `read_pdf_vectors`, same file:374 | `open`, `get_drawings`, Point/Rect values | Line and rectangle segments; optional real-world coordinates |
| `extract_pdf_dimensions`, same file:522 | `open`, `get_text("dict")`, span bounding boxes | Heuristically matched dimension strings and locations |

`calibrate_pdf_scale` is pure arithmetic and does not need PyMuPDF. Image, spreadsheet, SVG, and DOCX readers use other dependencies. `urban_report.py:74` uses DocRaptor for PDF generation and has no PyMuPDF import. No application calls to PyMuPDF OCR, document writing, redaction, merging, or form editing were found.

`documents` is in the `core` profile (`src/rhmcp/data/profiles.yml:22`) and inherited profiles; `full` loads it too. Imports are lazy, but dependency installation is mandatory regardless of whether these four tools are invoked. Four of 358 registered tools directly require this library. Removing only those tools would leave 354, but removing the entire documents module would remove additional, unrelated tools.

## Distribution inventory

| Surface | Observed PyMuPDF version / inclusion |
|---|---|
| `pyproject.toml:33` | Mandatory `pymupdf>=1.23.0`; no upper bound |
| `uv.lock:1191`, development environment | 1.27.2.3 |
| Local `rhino-mcp:0.17.1` Docker image | 1.27.2.3, confirmed inside `/app/.venv` |
| Installed universal package, Apple Silicon environment | 1.28.2 |
| Installed universal package, Intel environment | 1.28.2 (metadata inspection; PDF probes were not run on Intel) |
| Published Python wheel | Does not vendor PyMuPDF; declares it as an install dependency |
| C# `.rhp` / Yak plugin | No PyMuPDF dependency/use found in plugin source or package configuration |

The installed `pymupdf` directories occupy approximately 57.6 MiB on Apple Silicon and 59.1 MiB on Intel, excluding dist-info and other dependencies. Removing them would not save those exact amounts from the compressed installer, and a replacement renderer has its own size.

## Findings

### 1. High release priority: proprietary licensing basis is unresolved

Evidence: all inspected PyMuPDF package metadata declares dual licensing under GNU AGPL 3.0 or an Artifex commercial license. The project declares MIT in `pyproject.toml:10,18`; the installer presents MIT in `scripts/installer/resources/license.txt`. The inspected PyMuPDF dist-info `COPYING` contains a one-line dual-license declaration. That declaration is not, by itself, evidence of a commercial grant or a complete source-compliance process.

Artifex states that incorporating its AGPL software into a server application requires application-source disclosure under its licensing interpretation, and offers commercial terms for proprietary applications. See [Artifex licensing](https://artifex.com/licensing). The AGPL defines corresponding source and distribution/network obligations, while distinguishing separate independent aggregates from combined works; see [the license text](https://artifex.com/licensing/gnu-agpl-v3).

Engineering conclusion: this is direct in-process Python integration, not merely a link to an independently installed PDF viewer. Do not assume publishing only PyMuPDF's source satisfies the obligations for the combined server. Conversely, this review does not establish that the separate C# Rhino plugin is part of the same covered work. A socket boundary alone does not settle that legal question.

Action: obtain a commercial agreement covering the actual distribution/deployment, replace the library, or document and implement AGPL compliance for the applicable work. Inventory notices and corresponding source for distributed dependencies. Public application source alone does not establish complete compliance for bundled native libraries. Have counsel assess any existing distribution obligations; replacement affects future builds and does not erase earlier distributions.

### 2. High correctness: vector scale is wrong at non-72 DPI

Evidence: `documents.py:444` and `:478` multiply raw PDF point coordinates by `real_units_per_px`. There is no DPI argument or point-to-pixel conversion in `read_pdf_vectors`. The README explicitly instructs users to pass the ratio from `read_pdf` or pixel calibration. PyMuPDF coordinates use points, with 72 points per inch; see [coordinate documentation](https://pymupdf.readthedocs.io/en/latest/app3.html).

Reproduced in both tested versions: a 72-point (one paper inch) line, rendered at 150 DPI with `1/4" = 1'`, should represent 4 feet. `read_pdf_vectors` returns **1.920024 feet**, approximately 48% of the correct value. The tiny difference from 1.92 comes from rounding the scale ratio. `min_length_px` is likewise compared against lengths in PDF points.

Action: define and return explicit coordinate units. Prefer point-based vector coordinates with a `real_units_per_point` conversion, or accept the render DPI and convert points to matching pixels before applying pixel calibration. Preserve compatibility through a documented migration, and add fixtures at 72/150/300 DPI.

### 3. High reliability: native PDF calls can run concurrently on worker threads

Evidence: `tool_runtime.py:112` only locks mutating tools, while these tools are read-only. At `:133`, synchronous calls execute through `asyncio.to_thread`. Consequently, simultaneous PDF requests can enter PyMuPDF from different worker threads.

Upstream explicitly says multithreaded PyMuPDF use is unsupported and may cause incorrect behavior or crash Python; it recommends multiprocessing. See [PyMuPDF multiprocessing guidance](https://pymupdf.readthedocs.io/en/latest/recipes-multiprocessing.html).

Action: use a bounded process worker design, opening each document inside its worker. Include cancellation, timeout, crash recovery, and concurrency limits. Do not rely on the Rhino mutation lock. This finding is based on the call path and upstream contract; no crash or destructive concurrency stress was attempted.

### 4. High availability for untrusted PDFs: processing has no resource budget

Evidence: `read_pdf` clamps DPI to 50–600 and page count to 1–50, but does not cap pixel area, input size, output bytes, or render time. `get_pdf_info` enumerates every page. `read_pdf_vectors` materializes all drawings for each selected page without a segment budget. `extract_pdf_dimensions` obtains full text dictionaries before skipping non-text blocks, potentially including image data.

A 36×48-inch sheet at the allowed 600 DPI is 21,600×28,800 pixels: approximately **1.74 GiB for one RGB bitmap alone**, before PNG encoding, text, responses, and concurrent work. This estimate was calculated; that allocation was not attempted. Returning images as base64 further increases the encoded payload compared with PNG bytes.

Action: enforce per-page/total pixel budgets, input/output limits, page/segment/text limits, and a killable worker timeout. Paginate metadata and report truncation. Request text without embedded image content when only dimensions are needed. Severity depends on granting access to untrusted documents; local trusted use still risks accidental exhaustion on large CAD sheets.

### 5. Medium correctness: curves and rotation are mishandled

Evidence: `read_pdf_vectors` handles only `l` and `re` drawing operations, despite advertising curves. It ignores Bézier/quad operations and path closure semantics. In both tested versions, a valid curve-only PDF returned `no_vectors` and suggested the file might be a raster scan.

`extract_pdf_dimensions` multiplies unrotated span coordinates by DPI without applying the page rotation matrix. A 90-degree fixture produced `[10.0, 48.17, 52.79, 63.29]` instead of the rotated image-space box approximately `[224.71, 10.0, 239.825, 52.79]` at 72 DPI. Vector extraction also lacks an explicit transformation into rendered-page space. See [PyMuPDF page coordinate APIs](https://pymupdf.readthedocs.io/en/latest/page.html).

Action: represent supported curves explicitly, or report unsupported paths and partial extraction instead of classifying the page as raster-only. Normalize crop/rotation/origin consistently for rendering, vectors, and annotations, with fixture-based comparisons. Treat extracted paths as drawing commands, not automatically visible CAD geometry; clipping/visibility and layers need separate handling.

### 6. Medium reliability: validation and exception handling are incomplete

Reproduced in both versions:

- Password-protected PDFs raise `ValueError: document closed or encrypted` from all four tools after `open` succeeds. These exceptions escape the tool implementation instead of producing its structured error dictionary. The MCP framework may turn them into a protocol error; this is not a claim that every such request crashes the server.
- `extract_pdf_dimensions(dpi=-150)` returns success with negative/inverted coordinates.
- Requesting page `999` of a one-page document returns success with zero pages.

Additional confirmed development-version probe: a PNG renamed to `.pdf` passes the suffix check and is accepted by `get_pdf_info`, because PyMuPDF recognizes its actual format. Suffix validation does not enforce PDF input.

`real_units_per_px` and `min_length_px` lack finite/positive validation. Both vector and dimension tools silently truncate at ten pages. Document cleanup uses manual `close()` calls rather than a context manager/finally around every processing branch. Exceptions therefore skip deterministic cleanup, although Python may later release the object.

Action: validate types, finite ranges, actual PDF type, password state, and page selection. Use `with`/`finally`; return stable error codes such as `PDF_PASSWORD_REQUIRED`, `INVALID_PAGE_RANGE`, and `PDF_PROCESSING_FAILED`. Disclose truncation and partial extraction. Dimension strings are heuristic matches, not validated measurements; bare-number matching also catches unrelated identifiers.

### 7. Medium supply chain: installer ignores the dependency lock

Evidence: `scripts/build-installer.sh:157,160` runs `pip install` on the project wheel and resolves dependencies afresh. This produced PyMuPDF 1.28.2 while development and Docker use locked 1.27.2.3. Installer validation checks the project version and registration count, but does not exercise PDF operations. The observed installed version also prints a warning that the `fitz` API is deprecated in favor of `import pymupdf`.

Action: generate and consume audited, hashed dependency constraints/wheel sets for both architectures, record installed versions in a release SBOM, and run PDF smoke fixtures using the packaged runtimes. If retaining PyMuPDF, migrate the import name with version-tested compatibility. The current `>=1.23.0` requirement permits old installations as well as future behavior changes; choose a supported version policy rather than simply adding an arbitrary upper bound.

### 8. Medium assurance: dedicated PDF behavior coverage is absent

The test search found document security/clamping helpers and generic tool registration coverage, but no dedicated tests invoking these four PDF tools on PDF fixtures. Existing report-generator tests concern DocRaptor/HTML export and do not validate PyMuPDF reading. The repository CI workflow runs unit tests and lint, but no dependency advisory/license scan is configured there.

Action: add fixtures for CAD lines/rectangles/curves, text grouping, rotated/cropped pages, raster-only scans, encrypted/corrupt files, oversized page dimensions, invalid scale/page inputs, and deterministic cleanup. Exercise the same fixtures under packaged dependencies. Add dependency/advisory and license checks, including bundled native components. An empty OSV query does not replace those checks.

## Existing controls and scope limits

The four tools validate resolved input paths against `RHINO_MCP_READ_ROOTS` or the user's home directory. The runtime checks tool grants and authorized project/instance values. These are useful controls, but the read roots are process-wide, not per-project filesystem boundaries. A granted PDF tool can read files throughout those shared roots; use narrow roots and separate OS accounts/processes when tenant isolation is required.

Processing is local and read-only with respect to the source file, but extracted text/images are returned to the MCP caller and can enter an AI client. No automatic PyMuPDF document upload or cloud service call was found in these four implementations. No exploit, malicious PDF fuzzing, memory-exhaustion test, commercial-contract audit, or full bundled-native CVE audit was performed.

## Replacement options

| Option | Assessment |
|---|---|
| Commercial PyMuPDF license | Smallest API migration; retains current capabilities, but does not fix scale, rotation, concurrency, limits, or validation bugs. Contract must cover intended use. |
| `pypdfium2` + `pdfplumber` | Recommended prototype for proprietary distribution without PyMuPDF. PDFium can render pages; pdfplumber exposes text/character positions, lines, rectangles, and curves. Needs coordinate normalization, text-grouping comparisons, performance tests, and native notice review. |
| Remove the four PDF tools | Smallest feature-level removal. Preserve unrelated document tools and calibration as appropriate; update counts, profiles, prompts, docs, and client expectations. |
| Keep an AGPL-compliant edition | Preserve library use and implement the applicable source/notice obligations; assess the combined application's licensing with counsel. |

The pypdfium2 publisher documents Apache-2.0/BSD-3-Clause terms for its wrapper and build-specific notices for PDFium and its dependencies: [package/licensing documentation](https://pypi.org/project/pypdfium2/). pdfplumber uses MIT: [license](https://github.com/jsvine/pdfplumber/blob/stable/LICENSE.txt); its [API documentation](https://github.com/jsvine/pdfplumber/blob/stable/README.md) describes geometry and text extraction. These are candidate replacements, not demonstrated drop-in substitutes. No new replacement dependencies were installed in this review.

PDFium is also not thread-safe, so replacement still needs process isolation or an appropriate serialization design; see [pypdfium2 threading constraints](https://pypdfium2.readthedocs.io/en/stable/python_api.html). Replacing one native parser with another does not by itself solve untrusted-file risks.

## Recommended sequence and acceptance criteria

1. Resolve commercial-license versus replacement versus AGPL-edition direction before a proprietary release.
2. Capture the reproducible bugs as regression tests; establish a fixture corpus and explicit coordinate contract.
3. Implement one PDF backend interface for metadata, rendering, text, and paths, with process isolation and budgets.
4. Prototype pypdfium2/pdfplumber against that interface if replacement is chosen. Require correct 4-foot scale, rotated coordinates, honest curve/partial results, bounded resource behavior, and structured encrypted-file errors.
5. Preserve the four tool names and useful output fields where possible; explicitly migrate ambiguous pixel/point parameters. Verify actual registration counts after changes.
6. Remove PyMuPDF from the manifest and regenerate the lockfile only once replacement tests pass. Rebuild wheel, sdist, Docker, and both installer architectures from clean staging; verify PyMuPDF/MuPDF are absent from all intended distributions and dependency trees.
7. Add third-party notices/SBOMs, rerun application and packaged-runtime tests, sign/notarize, and publish a new version. Do not overwrite the existing 0.17.1 binaries to disguise dependency changes.

## Reproduction record

Temporary probe scripts and JSON outputs were written to `/private/tmp/rhino-pymupdf-review/` during review (temporary files are not permanent report attachments).

- `probe.py`: creates one-page PDFs using `new_page`, `draw_line`, `draw_bezier`, `insert_text`, and AES-256 encryption; calls the four registered tool functions sequentially.
- Development run: `.venv/bin/python /private/tmp/rhino-pymupdf-review/probe.py` (1.27.2.3).
- Installed run: `/Users/Shared/rhino_mcp/.venv-arm64/bin/python /private/tmp/rhino-pymupdf-review/probe.py` (1.28.2).
- `edge_probe.py`: compares rotated text bounds against `Rect(span["bbox"]) * page.rotation_matrix` and tests a small PNG renamed to `.pdf`.
- OSV POST queries: `https://api.osv.dev/v1/query`, package `{name: "pymupdf", ecosystem: "PyPI"}`, versions `1.27.2.3` and `1.28.2`; no matching vulnerability IDs returned.

The same four core defects reproduced under both versions: wrong real-world vector scale, curve-only false negative, negative-DPI success, and unhandled encrypted-document errors. Rotation and disguised-file probes were run on the development version only.
