# Token Reduction Design

**Date:** 2026-05-19  
**Status:** Approved  
**Goal:** Reduce the MCP tool schema token footprint from ~62k tokens to ~28k tokens (core profile + trimmed descriptions) — a 55% reduction.

---

## Baseline

| Metric | Value |
|--------|-------|
| Tools | 358 |
| Total schema tokens | ~62,000 |
| Largest tool | `create_pbr_material` (~886 tok) |
| Mean per tool | ~173 tok |

Dominant cost drivers:
1. **Verbose docstrings** — NumPy-style `Parameters` sections in description text duplicate what's already in `inputSchema`
2. **Specialty modules loaded unconditionally** — GH, V-Ray, Enscape, urban, BIM tools loaded even when unused

---

## Three Changes

### 1. Description Trimming (one-time script)

**What:** A script `scripts/trim_descriptions.py` rewrites all `@mcp.tool()` function docstrings in `src/rhmcp/tools/*.py` to keep only the first paragraph.

**Rule:** Strip everything from the first `Parameters`, `Args`, `Returns`, `Notes`, `Examples`, or `Raises` section header (detected as a header word followed by a `---` or `===` underline on the next line). Trim to max 200 chars, breaking at a word boundary.

**Why this is safe:** FastMCP already parses Google/NumPy docstrings and puts parameter descriptions into `inputSchema.properties[*].description`. The top-level description is redundant for parameter docs — it only needs to tell the model *what the tool does*, not enumerate every parameter.

**Estimated savings:** 46% reduction in description text → ~9,100 tokens.

**Execution:** Run once, commit the diff. The script is idempotent (already-trimmed descriptions pass through unchanged).

---

### 2. Profile System

**What:** A `--profile` CLI flag (and `RHMCP_PROFILE` env var fallback) selects which tool modules to load at startup.

**Where profiles are defined:** `src/rhmcp/data/profiles.yml` — a YAML file mapping profile names to lists of module names. `null` means load all modules (the `full` profile).

**Profiles:**

| Profile | Tools | Tokens (post-trim) | Savings vs full |
|---------|-------|---------------------|-----------------|
| `full` | 358 | ~53,000 | 0% |
| `core` | 194 | ~28,000 | **~47%** |
| `grasshopper` | 277 | ~40,000 | ~25% |
| `rendering` | 225 | ~35,000 | ~34% |
| `urban` | 226 | ~34,000 | ~36% |
| `bim` | 212 | ~31,000 | ~41% |

**Module assignments:**

```yaml
core:
  - advanced_geometry
  - analysis
  - annotations
  - blocks
  - boolean_operations
  - curve_operations
  - docs
  - document
  - documents
  - export_cad
  - export_images
  - export_native
  - export_print
  - export_visual
  - geometry
  - geometry_validation
  - groups
  - layers
  - materials
  - mesh_ops
  - objects
  - plugin_socket
  - plugins
  - python
  - reference_compat
  - session
  - slots
  - surface_ops
  - transforms
  - undo
  - userdata
  - view

grasshopper:
  - _extends: core
  - gh2
  - gh_anemone
  - gh_canvas
  - gh_document
  - gh_human_elefront
  - gh_intelligence
  - gh_kangaroo
  - gh_ladybug
  - gh_lunchbox
  - gh_params
  - gh_pufferfish
  - gh_solution
  - gh_weaverbird

rendering:
  - _extends: core
  - asset_libraries
  - enscape
  - pbr_materials
  - vray

urban:
  - _extends: core
  - ai_generation
  - urban
  - urban_design_language
  - urban_pipeline
  - urban_prompt
  - urban_renders
  - urban_report

bim:
  - _extends: core
  - lands_design
  - visualarq

full: null
```

**`_extends` semantics:** When loading a profile, if `_extends: <name>` appears, resolve the named profile's module list first and union with the additional modules listed.

**CLI change in `__init__.py`:**
- Add `--profile` arg, default `"full"`
- Read `RHMCP_PROFILE` env var as fallback before the default
- Load `profiles.yml` from `data/`
- Resolve `_extends` recursively (max depth 3 to prevent cycles)
- Filter `pkgutil.iter_modules` to only load modules in the resolved set
- Print active profile name to stderr at startup alongside the plugin health check line

---

### 3. Trim Script (`scripts/trim_descriptions.py`)

Standalone script, no new dependencies. Algorithm:

```
for each .py file in src/rhmcp/tools/:
    read source text
    find all triple-quoted strings that are the first statement of a def body
    for each docstring:
        find first occurrence of section-header pattern:
            r'\n\s*(?:Parameters|Args|Returns|Notes|Examples|Raises)\s*\n\s*[-=]{3,}'
        if found: keep only text[:match.start()].strip()
        if len > 200: truncate at last word boundary before 200, append '...'
        if changed: replace in source
    write file back (only if any change was made)
print before/after token summary
```

The script operates on raw source text with regex, not AST manipulation. This avoids adding `libcst` as a dependency and is sufficient for the consistent docstring style used in this codebase.

---

## Architecture — How They Compose

```
startup
  ├── load profiles.yml
  ├── resolve active profile (--profile / RHMCP_PROFILE / "full")
  ├── for each module in tools/:
  │     if module in active_set: register(mcp)   ← profile filter
  │     else: skip
  └── each registered tool has trimmed description   ← permanent change in source
```

The two changes are independent:
- Trimming is a permanent source change (committed once)
- Profile filtering is a runtime concern

---

## Error Handling

- Unknown profile name → print error + list valid profiles, exit 1
- `_extends` cycle → raise ValueError at load time (not silently ignore)
- Profile with a module name that doesn't exist → warning to stderr, skip (not a hard error — allows profiles.yml to reference optional future modules)

---

## Testing

- Existing 130 unit tests must pass unchanged (they don't test descriptions)
- Add `tests/test_profiles.py` with unit tests:
  - `full` profile loads all modules
  - `core` profile loads exactly the listed modules and no others
  - `_extends` resolution works correctly
  - Unknown profile raises SystemExit
- Trim script: run on a temp copy, verify token count drops, verify no function signatures changed
- CI: no changes needed (tests run `full` profile implicitly)

---

## Non-Goals

- No per-request dynamic tool filtering (not in MCP spec)
- No AI-generated description rewrites
- No separate PyPI packages for core vs full
- No changes to the Rhino plugin side
