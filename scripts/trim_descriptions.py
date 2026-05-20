#!/usr/bin/env python3
"""
Trim verbose docstring sections from MCP tool functions.

Run once to strip Parameters/Args/Returns/Notes/Examples/Raises sections
from function docstrings in src/rhmcp/tools/*.py. Only actual function
docstrings are touched (identified via AST); module-level constants and
multi-line strings used as script templates are left alone.

Usage:
    python scripts/trim_descriptions.py                 # default: src/rhmcp/tools/
    python scripts/trim_descriptions.py path/to/tools/  # custom directory
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

SECTION_RE = re.compile(
    r"\n[ \t]*(?:Parameters|Args|Returns|Notes|Examples|Raises)[ \t]*\n[ \t]*[-=]{3,}",
    re.MULTILINE,
)
MAX_DESC = 200


def trim(doc: str) -> str:
    """Return only the first paragraph of *doc*, capped at MAX_DESC chars."""
    m = SECTION_RE.search(doc)
    text = doc[: m.start()].strip() if m else doc.strip()
    if len(text) > MAX_DESC:
        text = text[:MAX_DESC].rsplit(None, 1)[0] + "..."
    return text


def process_file(path: Path) -> tuple[int, int]:
    """Trim all function docstrings in *path*. Returns (before_chars, after_chars)."""
    source = path.read_text(encoding="utf-8")

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0, 0

    # Build byte-offset lookup: line index (0-based) → start offset
    lines = source.splitlines(keepends=True)
    line_offsets = [0]
    for line in lines:
        line_offsets.append(line_offsets[-1] + len(line))

    # Collect all function docstring AST constant nodes
    docstring_nodes: list[ast.Constant] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                docstring_nodes.append(node.body[0].value)

    if not docstring_nodes:
        return 0, 0

    before_total = after_total = 0
    replacements: list[tuple[int, int, str]] = []

    for const in docstring_nodes:
        value: str = const.value
        before_total += len(value)
        trimmed = trim(value)
        after_total += len(trimmed)

        if trimmed == value.strip():
            continue  # no change needed

        start = line_offsets[const.lineno - 1] + const.col_offset
        end = line_offsets[const.end_lineno - 1] + const.end_col_offset

        raw_token = source[start:end]
        quote = '"""' if raw_token.startswith('"""') else "'''"
        replacements.append((start, end, f"{quote}{trimmed}{quote}"))

    if not replacements:
        return before_total, after_total

    # Apply in reverse order so earlier offsets stay valid
    new_source = source
    for start, end, replacement in sorted(replacements, key=lambda t: t[0], reverse=True):
        new_source = new_source[:start] + replacement + new_source[end:]

    path.write_text(new_source, encoding="utf-8")
    return before_total, after_total


def main(tools_dir: Path) -> None:
    total_before = total_after = files_changed = 0

    for path in sorted(tools_dir.glob("*.py")):
        if path.name.startswith("_"):
            continue
        before, after = process_file(path)
        total_before += before
        total_after += after
        if before != after:
            files_changed += 1
            pct = 100 * (before - after) / before if before else 0
            print(f"  {path.name}: {before:,} → {after:,} chars  ({pct:.0f}% saved)")

    saved = total_before - total_after
    pct = 100 * saved / total_before if total_before else 0
    print(f"\nTotal description chars: {total_before:,} → {total_after:,}")
    print(f"Saved: {saved:,} chars  (~{saved // 4:,} tokens,  {pct:.0f}%)")
    print(f"Files changed: {files_changed}")


if __name__ == "__main__":
    tools_dir = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path(__file__).parent.parent / "src" / "rhmcp" / "tools"
    )
    main(tools_dir)
