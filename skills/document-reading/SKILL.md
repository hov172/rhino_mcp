---
name: rhino-document-reading
description: Read PDFs, drawings, spreadsheets, SVGs, Word files, and images from inside a Rhino MCP session. Use when design information lives in a file that must inform the model.
---

# Reading design documents

These tools run on the MCP server, not inside Rhino. Paths must be under the user's home directory or a configured `RHINO_MCP_READ_ROOTS` entry, or you get `INVALID_PATH`. The server and Rhino must share a filesystem for a read path to be handed to Rhino later.

## PDFs
- `get_pdf_info(path)` first: page count and page sizes. Pick pages before rendering.
- `read_pdf(path, pages="1,3-5", dpi=150, extract_text=True, max_pages=10, scale_hint?)`. `pages` is 1-based. DPI 50 to 600; large sheets need lower DPI to stay under the 16 MP per page limit. `scale_hint` accepts `1/4" = 1'`, `1" = 10'`, or `1:100`.
- `calibrate_pdf_scale(pixel_point_1, pixel_point_2, real_distance, real_unit="feet"|"meters"|"inches"|"mm")` when the sheet has a known dimension but no scale note.
- `read_pdf_vectors(path, pages, real_units_per_px OR real_units_per_point, real_unit, dpi, min_length_px=2)` extracts line work from CAD-exported PDFs. The `dpi` must match the one used for `read_pdf` or calibration. Pass only one of the two scale ratios.
- `extract_pdf_dimensions(path, pages, real_units_per_px, real_unit, dpi)` finds dimension text with explicit units. It is heuristic and has no OCR.
- Limits: 50 MB input, 30 s per worker, two PDFs at once. `PDF_BUSY` means wait and retry.

## Images
`read_image(path, max_dimension=2048)` returns a PNG as base64. Accepts png, jpg, tif, bmp, webp, gif, heic. Look at the image, then describe what you see before modeling.

## Spreadsheets
`read_spreadsheet(path, sheet?, max_rows=500, header_row=True)` for `.csv` and `.xlsx`. CSV values are strings. Legacy `.xls` will usually fail; ask for an `.xlsx` export. Use it for room schedules, plant lists, and setback tables.

## SVG and Word
- `read_svg(path, include_raw=True, render_png=True)` returns markup and a preview. External references are blocked.
- `read_docx(path, include_tables=True, max_paragraphs?)` returns paragraphs and tables. Use it for briefs and specifications.

## Workflow
1. Read the file. Summarise the relevant facts in a short table: dimensions, counts, constraints.
2. Confirm the scale and units with the user when the document is ambiguous.
3. Hand off to `rhino-image-to-3d` or `rhino-text-to-3d` with those facts as the brief.
