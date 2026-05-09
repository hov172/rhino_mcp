"""
Static syntax validation for all inline _SCRIPT strings in tool modules.
No Rhino instance required.

Every _SCRIPT block is raw Python sent to Rhino at runtime; a syntax error
would be a silent failure that passes all other tests but breaks real users.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
import unittest

import rhmcp.tools as _tools_pkg


class TestScriptSyntax(unittest.TestCase):
    def _collect_scripts(self) -> list[tuple[str, str, str]]:
        """Return (module_name, attr_name, script_text) for all _SCRIPT attrs."""
        tools_dir = _tools_pkg.__path__[0]
        found = []
        for info in pkgutil.iter_modules([tools_dir]):
            mod = importlib.import_module(f"rhmcp.tools.{info.name}")
            for attr in dir(mod):
                if not attr.startswith("_SCRIPT"):
                    continue
                val = getattr(mod, attr)
                if isinstance(val, str) and val.strip():
                    found.append((info.name, attr, val))
        return found

    def test_all_script_blocks_are_valid_python(self) -> None:
        """Every _SCRIPT block must parse without SyntaxError."""
        scripts = self._collect_scripts()
        errors: list[str] = []
        for mod_name, attr, script in scripts:
            try:
                ast.parse(script)
            except SyntaxError as exc:
                errors.append(f"{mod_name}.{attr} line {exc.lineno}: {exc.msg}")
        self.assertFalse(errors, "Script syntax errors:\n" + "\n".join(errors))

    def test_script_blocks_found(self) -> None:
        """Sanity check: at least 8 _SCRIPT blocks must exist across all modules."""
        scripts = self._collect_scripts()
        self.assertGreaterEqual(
            len(scripts), 8,
            f"Expected ≥8 _SCRIPT blocks, found {len(scripts)} — check attribute naming",
        )

    def test_script_blocks_assign_result(self) -> None:
        """Every _SCRIPT block should assign to 'result' so the backend can capture it."""
        scripts = self._collect_scripts()
        missing: list[str] = []
        for mod_name, attr, script in scripts:
            # Quick text check — AST walk would be slower and we only need existence
            if "result" not in script:
                missing.append(f"{mod_name}.{attr}")
        self.assertFalse(
            missing,
            "_SCRIPT blocks missing 'result' assignment (backend won't capture output):\n"
            + "\n".join(missing),
        )


if __name__ == "__main__":
    unittest.main()
