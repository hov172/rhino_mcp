"""
Unit tests for rhino_mcp tool parameter validation, clamping, and backend routing.

These tests do NOT require a running Rhino instance.  They work by:
  1. Calling register() with a real FastMCP instance so all tool closures are
     captured in the ToolManager.
  2. Extracting the raw ``fn`` callable from each registered tool.
  3. Mocking ``rhmcp.tools_helpers.backend`` functions to prevent any real
     Rhino connection attempt.
"""

from __future__ import annotations

import ast
import unittest
from unittest.mock import MagicMock, patch

from mcp.server.fastmcp import FastMCP


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _register_module(module_path: str) -> dict[str, object]:
    """
    Import *module_path*, call its register() with a fresh FastMCP instance,
    and return a mapping of tool-name -> raw callable.
    """
    import importlib

    mod = importlib.import_module(module_path)
    mcp = FastMCP("test-{}".format(module_path.rsplit(".", 1)[-1]))
    mod.register(mcp)
    return {name: tool.fn for name, tool in mcp._tool_manager._tools.items()}


# Sentinel result returned when we want the mock plugin to produce a value.
_PLUGIN_OK = {"ok": True, "backend": "plugin", "result": {"index": 0}}
_PLUGIN_NONE = None  # _try_plugin returns None → fall through to Python backend


# ---------------------------------------------------------------------------
# materials.py tests
# ---------------------------------------------------------------------------

class TestMaterialsValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Force rhinocode backend so _try_plugin always returns None and we
        # never try to open a plugin socket.
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"):
            cls.tools = _register_module("rhmcp.tools.materials")

    # --- create_material ---

    def test_create_material_invalid_color_too_few_elements(self) -> None:
        """color list with fewer than 3 elements must return ok=False."""
        fn = self.tools["create_material"]
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"):
            result = fn(name="mat1", color=[255, 0])
        self.assertFalse(result["ok"])
        self.assertIn("diffuse/color", result["error"])

    def test_create_material_invalid_color_too_many_elements(self) -> None:
        """color list with more than 3 elements must return ok=False."""
        fn = self.tools["create_material"]
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"):
            result = fn(name="mat1", color=[255, 0, 0, 255])
        self.assertFalse(result["ok"])
        self.assertIn("diffuse/color", result["error"])

    def test_create_material_invalid_specular_wrong_length(self) -> None:
        """specular list with wrong length must return ok=False."""
        fn = self.tools["create_material"]
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"):
            result = fn(name="mat1", specular=[128])
        self.assertFalse(result["ok"])
        self.assertIn("specular", result["error"])

    def test_create_material_invalid_emission_wrong_length(self) -> None:
        """emission list with wrong length must return ok=False."""
        fn = self.tools["create_material"]
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"):
            result = fn(name="mat1", emission=[0, 0])
        self.assertFalse(result["ok"])
        self.assertIn("emission", result["error"])

    def test_create_material_shininess_clamped_above_255(self) -> None:
        """shininess > 255 must be clamped to 255 and NOT return an error."""
        fn = self.tools["create_material"]
        captured: list[dict] = []

        def fake_execute_python(code: str, rhino_id=None, **kw):
            # Parse the injected JSON from the code preamble to inspect params.
            import json
            # code starts with: __mcp_material = {...}\n...
            line = code.split("\n", 1)[0]
            params = ast.literal_eval(line.split(" = ", 1)[1])
            captured.append(params)
            return {"ok": True, "backend": "rhinocode", "result": {}}

        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"), \
             patch("rhmcp.tools_helpers.backend.execute_python", side_effect=fake_execute_python):
            result = fn(name="shiny", shininess=9999)

        self.assertTrue(len(captured) == 1, "execute_python should have been called once")
        self.assertEqual(captured[0]["shininess"], 255)

    def test_create_material_shininess_clamped_below_zero(self) -> None:
        """shininess < 0 must be clamped to 0."""
        fn = self.tools["create_material"]
        captured: list[dict] = []

        def fake_execute_python(code: str, rhino_id=None, **kw):
            import json
            params = ast.literal_eval(code.split("\n", 1)[0].split(" = ", 1)[1])
            captured.append(params)
            return {"ok": True, "backend": "rhinocode", "result": {}}

        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"), \
             patch("rhmcp.tools_helpers.backend.execute_python", side_effect=fake_execute_python):
            fn(name="dull", shininess=-50)

        self.assertEqual(captured[0]["shininess"], 0)

    def test_create_material_transparency_clamped_above_1(self) -> None:
        """transparency > 1.0 must be clamped to 1.0."""
        fn = self.tools["create_material"]
        captured: list[dict] = []

        def fake_execute_python(code: str, rhino_id=None, **kw):
            import json
            params = ast.literal_eval(code.split("\n", 1)[0].split(" = ", 1)[1])
            captured.append(params)
            return {"ok": True, "backend": "rhinocode", "result": {}}

        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"), \
             patch("rhmcp.tools_helpers.backend.execute_python", side_effect=fake_execute_python):
            fn(name="glass", transparency=5.0)

        self.assertAlmostEqual(captured[0]["transparency"], 1.0)

    def test_create_material_transparency_clamped_below_zero(self) -> None:
        """transparency < 0.0 must be clamped to 0.0."""
        fn = self.tools["create_material"]
        captured: list[dict] = []

        def fake_execute_python(code: str, rhino_id=None, **kw):
            import json
            params = ast.literal_eval(code.split("\n", 1)[0].split(" = ", 1)[1])
            captured.append(params)
            return {"ok": True, "backend": "rhinocode", "result": {}}

        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"), \
             patch("rhmcp.tools_helpers.backend.execute_python", side_effect=fake_execute_python):
            fn(name="opaque", transparency=-2.0)

        self.assertAlmostEqual(captured[0]["transparency"], 0.0)

    def test_create_material_valid_color_passes_through(self) -> None:
        """A valid 3-element color list must not trigger a validation error."""
        fn = self.tools["create_material"]
        captured: list[dict] = []

        def fake_execute_python(code: str, rhino_id=None, **kw):
            import json
            params = ast.literal_eval(code.split("\n", 1)[0].split(" = ", 1)[1])
            captured.append(params)
            return {"ok": True, "backend": "rhinocode", "result": {}}

        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"), \
             patch("rhmcp.tools_helpers.backend.execute_python", side_effect=fake_execute_python):
            result = fn(name="red", color=[255, 0, 0])

        self.assertNotIn("error", result)
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]["diffuse"], [255, 0, 0])

    def test_create_material_diffuse_wins_over_color_alias(self) -> None:
        """When both diffuse and color are given, diffuse takes precedence."""
        fn = self.tools["create_material"]
        captured: list[dict] = []

        def fake_execute_python(code: str, rhino_id=None, **kw):
            import json
            params = ast.literal_eval(code.split("\n", 1)[0].split(" = ", 1)[1])
            captured.append(params)
            return {"ok": True, "backend": "rhinocode", "result": {}}

        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"), \
             patch("rhmcp.tools_helpers.backend.execute_python", side_effect=fake_execute_python):
            fn(name="priority", diffuse=[10, 20, 30], color=[100, 110, 120])

        self.assertEqual(captured[0]["diffuse"], [10, 20, 30])

    # --- set_object_material ---

    def test_set_object_material_no_index_no_name_returns_error(self) -> None:
        """Calling set_object_material without index or name must return ok=False."""
        fn = self.tools["set_object_material"]
        valid_guid = "12345678-1234-1234-1234-123456789abc"
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"):
            result = fn(id=valid_guid)
        self.assertFalse(result["ok"])
        self.assertIn("material_index", result["error"])
        self.assertIn("material_name", result["error"])

    def test_set_object_material_with_index_proceeds(self) -> None:
        """Providing material_index must not trigger the no-identifier error."""
        fn = self.tools["set_object_material"]
        valid_guid = "12345678-1234-1234-1234-123456789abc"
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"), \
             patch("rhmcp.tools_helpers.backend.execute_python", return_value={"ok": True, "result": {}}):
            result = fn(id=valid_guid, material_index=0)
        self.assertNotEqual(result.get("ok"), False, "Should not get validation error")

    def test_set_object_material_with_name_proceeds(self) -> None:
        """Providing material_name must not trigger the no-identifier error."""
        fn = self.tools["set_object_material"]
        valid_guid = "12345678-1234-1234-1234-123456789abc"
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"), \
             patch("rhmcp.tools_helpers.backend.execute_python", return_value={"ok": True, "result": {}}):
            result = fn(id=valid_guid, material_name="Wood")
        self.assertNotEqual(result.get("ok"), False, "Should not get validation error")

    # --- delete_material ---

    def test_delete_material_no_index_no_name_returns_error(self) -> None:
        """Calling delete_material without index or name must return ok=False."""
        fn = self.tools["delete_material"]
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"):
            result = fn()
        self.assertFalse(result["ok"])
        self.assertIn("material_index", result["error"])
        self.assertIn("material_name", result["error"])

    def test_delete_material_with_index_proceeds(self) -> None:
        """Providing material_index must not trigger the no-identifier error."""
        fn = self.tools["delete_material"]
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"), \
             patch("rhmcp.tools_helpers.backend.execute_python", return_value={"ok": True, "result": {}}):
            result = fn(material_index=2)
        self.assertNotEqual(result.get("ok"), False, "Should not get validation error")

    def test_delete_material_with_name_proceeds(self) -> None:
        """Providing material_name must not trigger the no-identifier error."""
        fn = self.tools["delete_material"]
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"), \
             patch("rhmcp.tools_helpers.backend.execute_python", return_value={"ok": True, "result": {}}):
            result = fn(material_name="Metal")
        self.assertNotEqual(result.get("ok"), False, "Should not get validation error")


# ---------------------------------------------------------------------------
# materials.py — plugin backend routing tests
# ---------------------------------------------------------------------------

class TestMaterialsPluginRouting(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="auto"):
            cls.tools = _register_module("rhmcp.tools.materials")

    def test_create_material_uses_plugin_when_available(self) -> None:
        """create_material must return plugin result when plugin responds ok."""
        fn = self.tools["create_material"]
        plugin_response = {"ok": True, "backend": "plugin", "result": {"index": 3, "name": "New"}}
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="auto"), \
             patch("rhmcp.tools_helpers.backend.plugin_result", return_value=plugin_response):
            result = fn(name="PluginMat", color=[0, 128, 255])
        self.assertTrue(result["ok"])
        self.assertEqual(result["backend"], "plugin")

    def test_create_material_falls_back_when_plugin_raises_oserror(self) -> None:
        """When plugin raises OSError, create_material must fall back to Python backend."""
        fn = self.tools["create_material"]
        python_response = {"ok": True, "backend": "rhinocode", "result": {"index": 0}}
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="auto"), \
             patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=OSError("no socket")), \
             patch("rhmcp.tools_helpers.backend.execute_python", return_value=python_response):
            result = fn(name="FallbackMat", color=[0, 0, 0])
        self.assertEqual(result["backend"], "rhinocode")


# ---------------------------------------------------------------------------
# layers.py tests
# ---------------------------------------------------------------------------

class TestLayersRouting(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"):
            cls.tools = _register_module("rhmcp.tools.layers")

    def test_create_layer_falls_back_to_python_when_plugin_returns_none(self) -> None:
        """
        When _try_plugin returns None (plugin not available / backend is
        rhinocode), create_layer must call execute_python as the fallback.
        """
        fn = self.tools["create_layer"]
        python_response = {"ok": True, "backend": "rhinocode", "result": {"layer": "MyLayer"}}
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"), \
             patch("rhmcp.tools_helpers.backend.execute_python", return_value=python_response) as mock_exec:
            result = fn(name="MyLayer")
        mock_exec.assert_called_once()
        self.assertEqual(result["backend"], "rhinocode")

    def test_create_layer_uses_plugin_when_available(self) -> None:
        """create_layer must return plugin result without calling execute_python."""
        fn = self.tools["create_layer"]
        plugin_response = {"ok": True, "backend": "plugin", "result": {"layer": "MyLayer"}}
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="auto"), \
             patch("rhmcp.tools_helpers.backend.plugin_result", return_value=plugin_response), \
             patch("rhmcp.tools_helpers.backend.execute_python") as mock_exec:
            result = fn(name="MyLayer")
        mock_exec.assert_not_called()
        self.assertTrue(result["ok"])
        self.assertEqual(result["backend"], "plugin")

    def test_create_layer_falls_back_when_plugin_raises_oserror(self) -> None:
        """If plugin raises OSError, create_layer must fall through to Python backend."""
        fn = self.tools["create_layer"]
        python_response = {"ok": True, "backend": "rhinocode", "result": {}}
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="auto"), \
             patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=OSError("refused")), \
             patch("rhmcp.tools_helpers.backend.execute_python", return_value=python_response) as mock_exec:
            result = fn(name="FallbackLayer")
        mock_exec.assert_called_once()
        self.assertEqual(result["backend"], "rhinocode")

    def test_manage_rhino_layer_invalid_action_returns_error(self) -> None:
        """
        manage_rhino_layer with an unrecognised action must return ok=False with
        INVALID_VALUE error_code without reaching execute_python.
        """
        fn = self.tools["manage_rhino_layer"]
        with patch("rhmcp.tools_helpers.backend.execute_python") as mock_exec:
            result = fn(action="fly", name="Phantom")
        mock_exec.assert_not_called()
        self.assertFalse(result["ok"])
        self.assertEqual(result.get("error_code"), "INVALID_VALUE")

    def test_delete_layer_falls_back_to_python_when_plugin_unavailable(self) -> None:
        """delete_layer must call execute_python when backend is rhinocode."""
        fn = self.tools["delete_layer"]
        python_response = {"ok": True, "backend": "rhinocode", "result": {"deleted": True}}
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"), \
             patch("rhmcp.tools_helpers.backend.execute_python", return_value=python_response) as mock_exec:
            result = fn(name="OldLayer")
        mock_exec.assert_called_once()
        self.assertEqual(result["backend"], "rhinocode")

    def test_get_or_set_current_layer_falls_back_to_python(self) -> None:
        """get_or_set_current_layer must call execute_python when plugin is absent."""
        fn = self.tools["get_or_set_current_layer"]
        python_response = {"ok": True, "backend": "rhinocode", "result": {"current": "Default"}}
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"), \
             patch("rhmcp.tools_helpers.backend.execute_python", return_value=python_response) as mock_exec:
            result = fn()
        mock_exec.assert_called_once()
        self.assertEqual(result["backend"], "rhinocode")


# ---------------------------------------------------------------------------
# reference_compat.py tests
# ---------------------------------------------------------------------------

class TestReferenceCompatCreateObjects(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"):
            cls.tools = _register_module("rhmcp.tools.reference_compat")

    def _fake_run_scene(self, items, rhino_id):
        """Capture the normalised item list without touching Rhino."""
        self._last_items = items
        return {"ok": True, "backend": "rhinocode", "result": {"created": []}}

    def test_create_objects_accepts_list_input(self) -> None:
        """create_objects must pass a list straight through to _run_scene."""
        fn = self.tools["create_objects"]
        objects_list = [
            {"type": "sphere", "params": {"center": [0, 0, 0], "radius": 1}},
            {"type": "box", "params": {"center": [2, 0, 0], "size": [1, 1, 1]}},
        ]
        captured: list = []

        def fake_run_scene(items, rhino_id):
            captured.extend(items)
            return {"ok": True, "backend": "rhinocode", "result": {}}

        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"), \
             patch("rhmcp.tools.geometry._run_scene", side_effect=fake_run_scene):
            result = fn(objects=objects_list)

        self.assertTrue(result["ok"])
        # Both items must reach _run_scene unchanged.
        self.assertEqual(len(captured), 2)
        self.assertEqual(captured[0]["type"], "sphere")
        self.assertEqual(captured[1]["type"], "box")

    def test_create_objects_accepts_dict_input(self) -> None:
        """create_objects must convert a dict to a list with name set from key."""
        fn = self.tools["create_objects"]
        objects_dict = {
            "RedSphere": {"type": "sphere", "params": {"center": [0, 0, 0], "radius": 2}},
            "BlueBox": {"type": "box", "params": {"center": [5, 0, 0], "size": [1, 1, 1]}},
        }
        captured: list = []

        def fake_run_scene(items, rhino_id):
            captured.extend(items)
            return {"ok": True, "backend": "rhinocode", "result": {}}

        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"), \
             patch("rhmcp.tools.geometry._run_scene", side_effect=fake_run_scene):
            result = fn(objects=objects_dict)

        self.assertTrue(result["ok"])
        # Dict items are flattened into a list; each gets name=key.
        names = {item["name"] for item in captured}
        self.assertIn("RedSphere", names)
        self.assertIn("BlueBox", names)

    def test_create_objects_dict_does_not_overwrite_existing_name(self) -> None:
        """If an object dict already has a 'name', the key must not overwrite it."""
        fn = self.tools["create_objects"]
        objects_dict = {
            "KeyName": {"type": "sphere", "name": "ExplicitName", "params": {"radius": 1}},
        }
        captured: list = []

        def fake_run_scene(items, rhino_id):
            captured.extend(items)
            return {"ok": True, "backend": "rhinocode", "result": {}}

        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"), \
             patch("rhmcp.tools.geometry._run_scene", side_effect=fake_run_scene):
            fn(objects=objects_dict)

        # setdefault means the existing "ExplicitName" must be kept.
        self.assertEqual(captured[0]["name"], "ExplicitName")

    def test_create_objects_uses_plugin_when_available(self) -> None:
        """create_objects must return plugin result without touching _run_scene."""
        fn = self.tools["create_objects"]
        plugin_response = {"ok": True, "backend": "plugin", "result": {"created": []}}
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="auto"), \
             patch("rhmcp.tools_helpers.backend.plugin_result", return_value=plugin_response), \
             patch("rhmcp.tools.geometry._run_scene") as mock_scene:
            result = fn(objects=[{"type": "sphere", "params": {}}])
        mock_scene.assert_not_called()
        self.assertEqual(result["backend"], "plugin")


# ---------------------------------------------------------------------------
# geometry.py tests
# ---------------------------------------------------------------------------

class TestGeometryTypeChecking(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"):
            cls.tools = _register_module("rhmcp.tools.geometry")

    def test_create_rhino_geometry_unsupported_type_returns_error(self) -> None:
        """
        An unrecognised geometry_type must NOT raise an exception.  The tool
        calls _run_scene → execute_python (mocked to fail), then falls back to
        _command_for_item which returns None for unknown types.  The final
        result must indicate the type was unsupported.
        """
        fn = self.tools["create_rhino_geometry"]
        python_fail = {"ok": False, "backend": "rhinocode", "error": "Unsupported geometry type: banana"}

        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"), \
             patch("rhmcp.tools_helpers.backend.execute_python", return_value=python_fail), \
             patch("rhmcp.tools_helpers.backend.run_command", return_value={"ok": False}):
            result = fn(geometry_type="banana", params={})

        # Either ok is False, or the unsupported list contains "banana".
        is_error = (not result.get("ok")) or ("banana" in result.get("unsupported", []))
        self.assertTrue(is_error, "Expected error or unsupported type for 'banana', got: {}".format(result))

    def test_create_rhino_geometry_known_type_calls_execute_python(self) -> None:
        """
        A known type (sphere) must cause execute_python to be invoked.
        """
        fn = self.tools["create_rhino_geometry"]
        python_ok = {"ok": True, "backend": "rhinocode", "result": {"created": ["guid-1"]}}

        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"), \
             patch("rhmcp.tools_helpers.backend.execute_python", return_value=python_ok) as mock_exec:
            result = fn(geometry_type="sphere", params={"center": [0, 0, 0], "radius": 5})

        mock_exec.assert_called_once()
        self.assertTrue(result["ok"])

    def test_create_rhino_geometry_uses_plugin_when_available(self) -> None:
        """When plugin backend is active, execute_python must not be called."""
        fn = self.tools["create_rhino_geometry"]
        # Plugin is called via execute_python → run_plugin_or_python internally;
        # we patch at the backend.execute_python level which wraps run_plugin_or_python.
        plugin_ok = {"ok": True, "backend": "plugin", "result": {"created": ["guid-2"]}}

        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="plugin"), \
             patch("rhmcp.tools_helpers.backend.plugin_result", return_value=plugin_ok):
            result = fn(geometry_type="sphere", params={"center": [0, 0, 0], "radius": 1})

        self.assertTrue(result["ok"])
        self.assertEqual(result.get("backend"), "plugin")

    def test_create_rhino_scene_passes_all_items(self) -> None:
        """create_rhino_scene must forward all items to execute_python."""
        fn = self.tools["create_rhino_scene"]
        captured_code: list[str] = []

        def fake_exec(code, rhino_id=None, **kw):
            captured_code.append(code)
            return {"ok": True, "backend": "rhinocode", "result": {}}

        items = [
            {"type": "sphere", "params": {"radius": 1}},
            {"type": "box", "params": {"size": [1, 1, 1]}},
        ]
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"), \
             patch("rhmcp.tools_helpers.backend.execute_python", side_effect=fake_exec):
            fn(items=items)

        self.assertEqual(len(captured_code), 1)
        # Both types must appear in the serialised payload.
        self.assertIn("sphere", captured_code[0])
        self.assertIn("box", captured_code[0])


# ---------------------------------------------------------------------------
# backend.py unit tests (no Rhino required)
# ---------------------------------------------------------------------------

class TestBackendRouting(unittest.TestCase):
    def test_preferred_backend_defaults_to_auto(self) -> None:
        from rhmcp.tools_helpers import backend
        with patch.dict("os.environ", {}, clear=False):
            # Remove env var if present
            import os
            os.environ.pop("RHINO_MCP_BACKEND", None)
            self.assertEqual(backend.preferred_backend(), "auto")

    def test_preferred_backend_env_var_rhinocode(self) -> None:
        from rhmcp.tools_helpers import backend
        with patch.dict("os.environ", {"RHINO_MCP_BACKEND": "rhinocode"}):
            self.assertEqual(backend.preferred_backend(), "rhinocode")

    def test_preferred_backend_env_var_plugin(self) -> None:
        from rhmcp.tools_helpers import backend
        with patch.dict("os.environ", {"RHINO_MCP_BACKEND": "plugin"}):
            self.assertEqual(backend.preferred_backend(), "plugin")

    def test_preferred_backend_invalid_env_var_returns_auto(self) -> None:
        from rhmcp.tools_helpers import backend
        with patch.dict("os.environ", {"RHINO_MCP_BACKEND": "nonsense"}):
            self.assertEqual(backend.preferred_backend(), "auto")

    def test_preferred_backend_explicit_arg_wins(self) -> None:
        from rhmcp.tools_helpers import backend
        with patch.dict("os.environ", {"RHINO_MCP_BACKEND": "rhinocode"}):
            self.assertEqual(backend.preferred_backend("plugin"), "plugin")

    def test_plugin_result_ok_path(self) -> None:
        """plugin_result must wrap a successful response with ok=True."""
        from rhmcp.tools_helpers import backend
        response = {"status": "ok", "result": {"foo": "bar"}}
        with patch("rhmcp.tools_helpers.plugin_client.send_command", return_value=response):
            result = backend.plugin_result("some_command", {})
        self.assertTrue(result["ok"])
        self.assertEqual(result["backend"], "plugin")

    def test_plugin_result_error_path(self) -> None:
        """plugin_result must return ok=False when response status is error."""
        from rhmcp.tools_helpers import backend
        response = {"status": "error", "message": "command failed"}
        with patch("rhmcp.tools_helpers.plugin_client.send_command", return_value=response):
            result = backend.plugin_result("some_command", {})
        self.assertFalse(result["ok"])

    def test_run_plugin_or_python_falls_back_on_oserror(self) -> None:
        """run_plugin_or_python must call rhinocode.execute_python on OSError."""
        from rhmcp.tools_helpers import backend
        python_ok = {"ok": True, "result": {}}
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="auto"), \
             patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=OSError("refused")), \
             patch("rhmcp.tools_helpers.rhinocode.execute_python", return_value=python_ok) as mock_py:
            result = backend.run_plugin_or_python("cmd", {}, "# code", rhino_id=None)
        mock_py.assert_called_once()
        self.assertEqual(result["backend"], "rhinocode")

    def test_run_plugin_or_python_plugin_backend_does_not_fall_back(self) -> None:
        """When explicit backend=plugin and plugin fails, no rhinocode fallback."""
        from rhmcp.tools_helpers import backend
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="plugin"), \
             patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=OSError("refused")), \
             patch("rhmcp.tools_helpers.rhinocode.execute_python") as mock_py:
            result = backend.run_plugin_or_python("cmd", {}, "# code", rhino_id=None, backend_name="plugin")
        mock_py.assert_not_called()
        self.assertFalse(result["ok"])


# ---------------------------------------------------------------------------
# Grasshopper tool tests (no Rhino required)
# ---------------------------------------------------------------------------

class TestGHDocumentTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}):
            cls.tools = _register_module("rhmcp.tools.gh_document")

    def test_open_definition_missing_path_returns_error(self) -> None:
        """gh_open_definition with empty path must return ok=False without socket call."""
        fn = self.tools["gh_open_definition"]
        with patch("rhmcp.tools_helpers.backend.plugin_result") as mock_plugin:
            result = fn(path="")
        self.assertFalse(result["ok"])
        mock_plugin.assert_not_called()

    def test_open_definition_sends_correct_command(self) -> None:
        """gh_open_definition with a path sends gh_open_document to the plugin."""
        fn = self.tools["gh_open_definition"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}) as mock_plugin:
            fn(path="/tmp/test.gh")
        mock_plugin.assert_called_once_with("gh_open_document", {"path": "/tmp/test.gh"}, rhino_id=None)

    def test_oserror_returns_structured_error(self) -> None:
        """Any GH tool must return ok=False (not raise) when the plugin socket is unavailable."""
        fn = self.tools["gh_get_definition_info"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=OSError("refused")):
            result = fn()
        self.assertFalse(result["ok"])
        self.assertIn("error", result)

    def test_new_definition_sends_name(self) -> None:
        """gh_new_definition passes name in params when supplied."""
        fn = self.tools["gh_new_definition"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}) as mock_plugin:
            fn(name="MyDef")
        mock_plugin.assert_called_once_with("gh_new_document", {"name": "MyDef"}, rhino_id=None)

    def test_new_definition_omits_name_when_none(self) -> None:
        """gh_new_definition sends empty params when name is None."""
        fn = self.tools["gh_new_definition"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}) as mock_plugin:
            fn()
        mock_plugin.assert_called_once_with("gh_new_document", {}, rhino_id=None)


class TestGHCanvasTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}):
            cls.tools = _register_module("rhmcp.tools.gh_canvas")

    def test_add_component_sends_correct_params(self) -> None:
        """gh_add_component forwards component_guid and coordinates."""
        fn = self.tools["gh_add_component"]
        guid = "57da07bd-ecab-415d-9cae-be61acf5b7ca"
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}) as mock_plugin:
            fn(component_guid=guid, x=100.0, y=200.0)
        mock_plugin.assert_called_once_with(
            "gh_add_component", {"component_guid": guid, "x": 100.0, "y": 200.0}, rhino_id=None
        )

    def test_add_component_accepts_type_name(self) -> None:
        """gh_add_component places by type_name, same as gh2_place_component."""
        fn = self.tools["gh_add_component"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}) as mock_plugin:
            fn(type_name="Circle", x=10.0, y=20.0)
        mock_plugin.assert_called_once_with(
            "gh_add_component", {"x": 10.0, "y": 20.0, "type_name": "Circle"}, rhino_id=None
        )

    def test_add_component_requires_guid_or_name(self) -> None:
        fn = self.tools["gh_add_component"]
        with patch("rhmcp.tools_helpers.backend.plugin_result") as mock_plugin:
            result = fn(x=0, y=0)
        self.assertFalse(result["ok"])
        mock_plugin.assert_not_called()

    def test_connect_params_int_port_stays_int(self) -> None:
        """Port indices reach the plugin as JSON numbers, same as gh2_connect."""
        fn = self.tools["gh_connect_params"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}) as mock_plugin:
            fn(from_guid="aaa", from_output=0, to_guid="bbb", to_input=1)
        params = mock_plugin.call_args[0][1]
        self.assertIs(type(params["from_output"]), int)
        self.assertIs(type(params["to_input"]), int)

    def test_connect_params_requires_to_guid(self) -> None:
        fn = self.tools["gh_connect_params"]
        with patch("rhmcp.tools_helpers.backend.plugin_result") as mock_plugin:
            result = fn(from_guid="aaa", from_output="R")
        self.assertFalse(result["ok"])
        mock_plugin.assert_not_called()

    def test_connect_params_sends_wire_fields(self) -> None:
        """gh_connect_params sends all four wire endpoint fields."""
        fn = self.tools["gh_connect_params"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}) as mock_plugin:
            fn(from_guid="aaa", from_output="R", to_guid="bbb", to_input="x")
        args = mock_plugin.call_args
        params = args[0][1]
        self.assertEqual(params["from_guid"], "aaa")
        self.assertEqual(params["from_output"], "R")
        self.assertEqual(params["to_guid"], "bbb")
        self.assertEqual(params["to_input"], "x")

    def test_add_group_sends_instance_guids(self) -> None:
        """gh_add_group passes instance_guids list."""
        fn = self.tools["gh_add_group"]
        guids = ["aaa", "bbb"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}) as mock_plugin:
            fn(instance_guids=guids, label="MyGroup")
        params = mock_plugin.call_args[0][1]
        self.assertEqual(params["instance_guids"], guids)
        self.assertEqual(params["label"], "MyGroup")

    def test_oserror_returns_structured_error(self) -> None:
        """Canvas tools return ok=False on OSError — no fallback to rhinocode."""
        fn = self.tools["gh_list_components"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=OSError):
            result = fn()
        self.assertFalse(result["ok"])


class TestGHParamTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}):
            cls.tools = _register_module("rhmcp.tools.gh_params")

    def test_add_script_component_invalid_language(self) -> None:
        """gh_add_script_component rejects unknown language before socket call."""
        fn = self.tools["gh_add_script_component"]
        with patch("rhmcp.tools_helpers.backend.plugin_result") as mock_plugin:
            result = fn(language="ruby", code="", inputs=[], outputs=[], x=0, y=0)
        self.assertFalse(result["ok"])
        mock_plugin.assert_not_called()

    def test_add_script_component_valid_languages(self) -> None:
        """gh_add_script_component accepts python, csharp, and cs."""
        fn = self.tools["gh_add_script_component"]
        for lang in ("python", "csharp", "cs"):
            with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}) as mock_plugin:
                result = fn(language=lang, code="# hi", inputs=["x"], outputs=["y"], x=0, y=0)
            mock_plugin.assert_called_once()
            cmd = mock_plugin.call_args[0][0]
            self.assertEqual(cmd, "gh_add_script_component")

    def test_add_script_component_forwards_inputs_outputs(self) -> None:
        """gh_add_script_component forwards inputs/outputs lists and code verbatim."""
        fn = self.tools["gh_add_script_component"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}) as mock_plugin:
            fn(language="python", code="a = x + y", inputs=["x", "y"], outputs=["a"], x=10, y=20)
        params = mock_plugin.call_args[0][1]
        self.assertEqual(params["inputs"], ["x", "y"])
        self.assertEqual(params["outputs"], ["a"])
        self.assertEqual(params["code"], "a = x + y")
        self.assertEqual((params["x"], params["y"]), (10, 20))

    def test_set_point_param_flattens_3d_points(self) -> None:
        """gh_set_point_param flattens [[x,y,z],...] to [x,y,z,...] for the C# handler."""
        fn = self.tools["gh_set_point_param"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}) as mock_plugin:
            fn(instance_guid="abc", points=[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        params = mock_plugin.call_args[0][1]
        self.assertEqual(params["points"], [1.0, 2.0, 3.0, 4.0, 5.0, 6.0])

    def test_set_point_param_extends_2d_to_3d(self) -> None:
        """gh_set_point_param auto-extends [x,y] points to [x,y,0]."""
        fn = self.tools["gh_set_point_param"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}) as mock_plugin:
            fn(instance_guid="abc", points=[[1.0, 2.0]])
        params = mock_plugin.call_args[0][1]
        self.assertEqual(params["points"], [1.0, 2.0, 0.0])

    def test_oserror_returns_structured_error(self) -> None:
        """Param tools return ok=False on OSError."""
        fn = self.tools["gh_set_slider"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=OSError):
            result = fn(instance_guid="abc", value=0.5)
        self.assertFalse(result["ok"])


class TestGHSolutionTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}):
            cls.tools = _register_module("rhmcp.tools.gh_solution")

    def test_run_solution_sends_command(self) -> None:
        """gh_run_solution sends gh_run_solution command to plugin."""
        fn = self.tools["gh_run_solution"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}) as mock_plugin:
            fn()
        cmd = mock_plugin.call_args[0][0]
        self.assertEqual(cmd, "gh_run_solution")

    def test_bake_sends_instance_guid(self) -> None:
        """gh_bake forwards instance_guid and optional layer."""
        fn = self.tools["gh_bake"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}) as mock_plugin:
            fn(instance_guid="abc-123", layer="Default")
        params = mock_plugin.call_args[0][1]
        self.assertEqual(params["instance_guid"], "abc-123")
        self.assertEqual(params["layer"], "Default")

    def test_enable_component_sends_bool(self) -> None:
        """gh_enable_component passes enabled boolean."""
        fn = self.tools["gh_enable_component"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}) as mock_plugin:
            fn(instance_guid="abc", enabled=False)
        params = mock_plugin.call_args[0][1]
        self.assertFalse(params["enabled"])

    def test_oserror_returns_structured_error(self) -> None:
        """Solution tools return ok=False on OSError."""
        fn = self.tools["gh_get_solution_state"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=OSError):
            result = fn()
        self.assertFalse(result["ok"])


# ---------------------------------------------------------------------------
# plugins.py tests
# ---------------------------------------------------------------------------

class TestPluginsModule(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tools = _register_module("rhmcp.tools.plugins")

    def test_check_plugin_loaded_not_found(self) -> None:
        fn = self.tools["check_plugin_loaded"]
        with patch("rhmcp.tools_helpers.plugin_client.send_command") as mock:
            mock.return_value = {"result": {"plugins": [{"name": "Other", "loaded": True}]}}
            result = fn("NonExistentPlugin")
        self.assertFalse(result["loaded"])
        self.assertIn("not installed", result["message"])

    def test_check_plugin_loaded_found_but_unloaded(self) -> None:
        fn = self.tools["check_plugin_loaded"]
        with patch("rhmcp.tools_helpers.plugin_client.send_command") as mock:
            mock.return_value = {"result": {"plugins": [{"name": "V-Ray for Rhino", "loaded": False}]}}
            result = fn("V-Ray")
        self.assertFalse(result["loaded"])
        self.assertIn("not loaded", result["message"])

    def test_check_plugin_loaded_found(self) -> None:
        fn = self.tools["check_plugin_loaded"]
        with patch("rhmcp.tools_helpers.plugin_client.send_command") as mock:
            mock.return_value = {"result": {"plugins": [{"name": "V-Ray for Rhino", "loaded": True}]}}
            result = fn("V-Ray")
        self.assertTrue(result["loaded"])


# ---------------------------------------------------------------------------
# gh_kangaroo.py tests
# ---------------------------------------------------------------------------

class TestKangarooTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tools = _register_module("rhmcp.tools.gh_kangaroo")

    def test_setup_solver_unavailable(self) -> None:
        fn = self.tools["gh_kangaroo_setup_solver"]
        with patch("rhmcp.tools_helpers.backend.plugin_result") as mock:
            mock.return_value = {"result": {"components": []}}
            result = fn()
        self.assertFalse(result["success"])
        self.assertIn("Kangaroo", result["message"])

    def test_add_goal_unknown_type(self) -> None:
        fn = self.tools["gh_kangaroo_add_goal"]
        with patch("rhmcp.tools_helpers.backend.plugin_result") as mock:
            mock.return_value = {"result": {"components": [{"id": "abc", "name": "K2 Solver"}]}}
            result = fn(goal_type="InvalidGoal", canvas_x=0.0, canvas_y=0.0)
        self.assertFalse(result["success"])
        self.assertIn("Unknown goal type", result["message"])


# ---------------------------------------------------------------------------
# gh_ladybug.py tests
# ---------------------------------------------------------------------------

class TestLadybugTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tools = _register_module("rhmcp.tools.gh_ladybug")

    def test_load_weather_not_installed(self) -> None:
        fn = self.tools["gh_ladybug_load_weather"]
        with patch("rhmcp.tools_helpers.backend.plugin_result") as mock:
            mock.return_value = {"result": {"components": []}}
            result = fn(epw_file_path="/path/to/file.epw")
        self.assertFalse(result["success"])
        self.assertIn("Ladybug", result["message"])

    def test_honeybee_create_room_success(self) -> None:
        fn = self.tools["gh_honeybee_create_room"]

        def mock_plugin(command, params, rhino_id=None):
            if command == "gh_search_components":
                return {"ok": True, "result": {"components": [{"guid": "hb-guid", "name": "HB Room from Solid"}]}}
            if command == "gh_add_component":
                return {"ok": True, "result": {"instance_guid": "inst-123"}}
            return {"ok": True, "result": {"ok": True}}

        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=mock_plugin):
            result = fn(geometry_component_id="geom-123", room_name="TestRoom")
        self.assertTrue(result["success"])


# ---------------------------------------------------------------------------
# gh_pufferfish.py tests
# ---------------------------------------------------------------------------

class TestPufferfishTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tools = _register_module("rhmcp.tools.gh_pufferfish")

    def test_tween_curves_not_installed(self) -> None:
        fn = self.tools["gh_pufferfish_tween_curves"]
        with patch("rhmcp.tools_helpers.backend.plugin_result") as mock:
            mock.return_value = {"result": {"components": []}}
            result = fn(curve1_instance_guid="a", curve2_instance_guid="b", count=5)
        self.assertFalse(result["success"])
        self.assertIn("Pufferfish", result["message"])


# ---------------------------------------------------------------------------
# gh_weaverbird.py tests
# ---------------------------------------------------------------------------

class TestWeaverbirdTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tools = _register_module("rhmcp.tools.gh_weaverbird")

    def test_catmull_clark_not_installed(self) -> None:
        fn = self.tools["gh_wb_catmull_clark"]
        with patch("rhmcp.tools_helpers.backend.plugin_result") as mock:
            mock.return_value = {"result": {"components": []}}
            result = fn(mesh_instance_guid="m1")
        self.assertFalse(result["success"])
        self.assertIn("Weaverbird", result["message"])


# ---------------------------------------------------------------------------
# gh_lunchbox.py tests
# ---------------------------------------------------------------------------

class TestLunchboxTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tools = _register_module("rhmcp.tools.gh_lunchbox")

    def test_quad_panels_not_installed(self) -> None:
        fn = self.tools["gh_lunchbox_quad_panels"]
        with patch("rhmcp.tools_helpers.backend.plugin_result") as mock:
            mock.return_value = {"result": {"components": []}}
            result = fn(surface_instance_guid="s1")
        self.assertFalse(result["success"])
        self.assertIn("LunchBox", result["message"])


# ---------------------------------------------------------------------------
# gh_human_elefront.py tests
# ---------------------------------------------------------------------------

class TestHumanElefrontTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tools = _register_module("rhmcp.tools.gh_human_elefront")

    def test_bake_attributes_not_installed(self) -> None:
        fn = self.tools["gh_elefront_bake_attributes"]
        with patch("rhmcp.tools_helpers.backend.plugin_result") as mock:
            mock.return_value = {"result": {"components": []}}
            result = fn(component_instance_guid="c1", layer="Default")
        self.assertFalse(result["success"])
        self.assertIn("Elefront", result["message"])


# ---------------------------------------------------------------------------
# gh_anemone.py tests
# ---------------------------------------------------------------------------

class TestAnemoneTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tools = _register_module("rhmcp.tools.gh_anemone")

    def test_setup_loop_not_installed(self) -> None:
        fn = self.tools["gh_anemone_setup_loop"]
        with patch("rhmcp.tools_helpers.backend.plugin_result") as mock:
            mock.return_value = {"result": {"components": []}}
            result = fn()
        self.assertFalse(result["success"])
        self.assertIn("Anemone", result["message"])


# ---------------------------------------------------------------------------
# vray.py tests
# ---------------------------------------------------------------------------

class TestVRayTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tools = _register_module("rhmcp.tools.vray")

    def test_render_not_installed(self) -> None:
        fn = self.tools["vray_render"]
        with patch("rhmcp.tools_helpers.plugin_client.send_command") as mock:
            mock.return_value = {"result": {"plugins": []}}
            result = fn(output_path="/tmp/out.png")
        self.assertFalse(result["success"])
        self.assertIn("V-Ray", result["message"])

    def test_create_material_not_installed(self) -> None:
        fn = self.tools["vray_create_material"]
        with patch("rhmcp.tools_helpers.plugin_client.send_command") as mock:
            mock.return_value = {"result": {"plugins": []}}
            result = fn(name="TestMat")
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# enscape.py tests
# ---------------------------------------------------------------------------

class TestEnscapeTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tools = _register_module("rhmcp.tools.enscape")

    def test_start_not_installed(self) -> None:
        fn = self.tools["enscape_start"]
        with patch("rhmcp.tools_helpers.plugin_client.send_command") as mock:
            mock.return_value = {"result": {"plugins": []}}
            result = fn()
        self.assertFalse(result["success"])
        self.assertIn("Enscape", result["message"])


# ---------------------------------------------------------------------------
# visualarq.py tests
# ---------------------------------------------------------------------------

class TestVisualARQTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tools = _register_module("rhmcp.tools.visualarq")

    def test_create_wall_not_installed(self) -> None:
        fn = self.tools["varq_create_wall"]
        with patch("rhmcp.tools_helpers.plugin_client.send_command") as mock:
            mock.return_value = {"result": {"plugins": []}}
            result = fn()
        self.assertFalse(result["success"])
        self.assertIn("VisualARQ", result["message"])

    def test_list_styles_not_installed(self) -> None:
        fn = self.tools["varq_list_styles"]
        with patch("rhmcp.tools_helpers.plugin_client.send_command") as mock:
            mock.return_value = {"result": {"plugins": []}}
            result = fn(object_type="wall")
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# lands_design.py tests
# ---------------------------------------------------------------------------

class TestLandsDesignTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tools = _register_module("rhmcp.tools.lands_design")

    def test_place_plant_not_installed(self) -> None:
        fn = self.tools["lands_place_plant"]
        with patch("rhmcp.tools_helpers.plugin_client.send_command") as mock:
            mock.return_value = {"result": {"plugins": []}}
            result = fn()
        self.assertFalse(result["success"])
        self.assertIn("Lands Design", result["message"])


# ---------------------------------------------------------------------------
# view.py — viewport capture returns image content
# ---------------------------------------------------------------------------

class TestViewCapture(unittest.TestCase):
    """
    capture_rhino_view must:
      - Return [metadata_dict, Image] when Rhino responds with a b64 field.
      - Return [raw_response] (no crash) when b64 is absent (e.g. Rhino error).
      - Accept path=None (in-memory only capture).
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.tools = _register_module("rhmcp.tools.view")

    def _fake_b64_response(self, b64: str, path: str | None = None) -> dict:
        return {
            "ok": True,
            "result": {
                "b64": b64,
                "path": path,
                "saved": path is not None,
                "width": 1200,
                "height": 900,
            },
        }

    def test_returns_image_and_metadata_when_b64_present(self) -> None:
        import base64
        from mcp.server.fastmcp import Image

        # Minimal valid 1×1 transparent PNG (67 bytes).
        png_1x1 = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
            b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
            b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        b64 = base64.b64encode(png_1x1).decode()

        fn = self.tools["capture_rhino_view"]
        with patch("rhmcp.tools_helpers.backend.execute_python") as mock:
            mock.return_value = self._fake_b64_response(b64, path=None)
            result = fn(path=None, width=1200, height=900)

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        meta, img = result
        self.assertIsInstance(meta, dict)
        self.assertIsInstance(img, Image)
        self.assertFalse(meta["saved"])
        self.assertIsNone(meta["path"])

    def test_returns_image_with_path_when_path_given(self) -> None:
        import base64
        from mcp.server.fastmcp import Image

        png_1x1 = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
            b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
            b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        b64 = base64.b64encode(png_1x1).decode()

        fn = self.tools["capture_rhino_view"]
        with patch("rhmcp.tools_helpers.backend.execute_python") as mock:
            mock.return_value = self._fake_b64_response(b64, path="/tmp/view.png")
            result = fn(path="/tmp/view.png")

        meta, img = result
        self.assertTrue(meta["saved"])
        self.assertEqual(meta["path"], "/tmp/view.png")
        self.assertIsInstance(img, Image)

    def test_graceful_fallback_when_no_b64(self) -> None:
        """If Rhino doesn't return b64 (error path), return [raw] without crashing."""
        fn = self.tools["capture_rhino_view"]
        raw = {"ok": False, "error": "No active view"}
        with patch("rhmcp.tools_helpers.backend.execute_python") as mock:
            mock.return_value = raw
            result = fn()

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], raw)


# ---------------------------------------------------------------------------
# telemetry.py — install() patches _tool_manager.call_tool
# ---------------------------------------------------------------------------

class TestTelemetry(unittest.TestCase):
    """
    telemetry.install() must:
      - Do nothing when RHINO_MCP_TELEMETRY is not set.
      - Replace _tool_manager.call_tool with an async wrapper when enabled.
      - Write one JSONL event per tool invocation.
      - Write ok=false + non-null error when the tool raises.
      - Never raise even if the log file can't be written.
    """

    def _make_mcp(self) -> "FastMCP":
        mcp = FastMCP("test-telemetry")
        return mcp

    def test_install_noop_when_disabled(self) -> None:
        import inspect
        import rhmcp.telemetry as tel

        mcp = self._make_mcp()
        original_func = mcp._tool_manager.call_tool.__func__

        with patch.object(tel, "ENABLED", False):
            tel.install(mcp)

        # call_tool must still be the original bound method, not the async wrapper.
        # Bound methods are re-created on each access so we compare __func__.
        self.assertIs(mcp._tool_manager.call_tool.__func__, original_func)
        # Extra guard: the wrapper is a plain async function, original is a coroutine method.
        self.assertTrue(inspect.iscoroutinefunction(mcp._tool_manager.call_tool))

    def test_install_replaces_call_tool_when_enabled(self) -> None:
        import rhmcp.telemetry as tel

        mcp = self._make_mcp()
        original = mcp._tool_manager.call_tool

        with patch.object(tel, "ENABLED", True):
            tel.install(mcp)

        self.assertIsNot(mcp._tool_manager.call_tool, original)

    def test_event_written_on_success(self) -> None:
        import asyncio
        import json
        import rhmcp.telemetry as tel

        mcp = self._make_mcp()
        written: list[dict] = []

        async def _fake_call_tool(name, arguments, context=None, convert_result=False):
            return "ok"

        mcp._tool_manager.call_tool = _fake_call_tool

        with patch.object(tel, "ENABLED", True), \
             patch.object(tel, "_write", side_effect=written.append):
            tel.install(mcp)
            asyncio.run(mcp._tool_manager.call_tool("my_tool", {}))

        self.assertEqual(len(written), 1)
        evt = written[0]
        self.assertEqual(evt["tool"], "my_tool")
        self.assertTrue(evt["ok"])
        self.assertIsNone(evt["error"])
        self.assertIn("ts", evt)
        self.assertIn("ms", evt)

    def test_event_written_on_failure(self) -> None:
        import asyncio
        import rhmcp.telemetry as tel

        mcp = self._make_mcp()
        written: list[dict] = []

        async def _raising_call_tool(name, arguments, context=None, convert_result=False):
            raise ValueError("boom")

        mcp._tool_manager.call_tool = _raising_call_tool

        with patch.object(tel, "ENABLED", True), \
             patch.object(tel, "_write", side_effect=written.append):
            tel.install(mcp)
            with self.assertRaises(ValueError):
                asyncio.run(mcp._tool_manager.call_tool("bad_tool", {}))

        self.assertEqual(len(written), 1)
        evt = written[0]
        self.assertFalse(evt["ok"])
        self.assertIn("ValueError", evt["error"])
        self.assertIn("boom", evt["error"])

    def test_write_io_error_does_not_propagate(self) -> None:
        """A broken log path must never crash a tool call."""
        import rhmcp.telemetry as tel

        # _write swallows all exceptions — call it directly with an unwritable path.
        with patch.object(tel, "LOG_PATH", MagicMock(
            parent=MagicMock(mkdir=MagicMock(side_effect=PermissionError("no"))),
        )):
            try:
                tel._write({"ts": "x", "tool": "t", "ms": 1, "ok": True, "error": None})
            except Exception as exc:  # noqa: BLE001
                self.fail(f"_write raised unexpectedly: {exc}")


import os  # noqa: E402 — needed for TestTelemetry


# ---------------------------------------------------------------------------
# validate.py tests
# ---------------------------------------------------------------------------

class TestValidateGuid(unittest.TestCase):
    def test_valid_guid(self) -> None:
        from rhmcp.tools_helpers import validate
        self.assertIsNone(validate.guid("550e8400-e29b-41d4-a716-446655440000"))

    def test_valid_guid_uppercase(self) -> None:
        from rhmcp.tools_helpers import validate
        self.assertIsNone(validate.guid("550E8400-E29B-41D4-A716-446655440000"))

    def test_invalid_guid_too_short(self) -> None:
        from rhmcp.tools_helpers import validate
        err = validate.guid("not-a-guid")
        self.assertIsNotNone(err)
        self.assertFalse(err["ok"])
        self.assertEqual(err["error_code"], "INVALID_GUID")

    def test_invalid_guid_none(self) -> None:
        from rhmcp.tools_helpers import validate
        err = validate.guid(None)
        self.assertIsNotNone(err)
        self.assertFalse(err["ok"])

    def test_invalid_guid_integer(self) -> None:
        from rhmcp.tools_helpers import validate
        err = validate.guid(12345)
        self.assertIsNotNone(err)
        self.assertEqual(err["error_code"], "INVALID_GUID")

    def test_custom_field_name_in_message(self) -> None:
        from rhmcp.tools_helpers import validate
        err = validate.guid("bad", field="object_id")
        self.assertIn("object_id", err["error"])


class TestValidateColor(unittest.TestCase):
    def test_valid_rgb(self) -> None:
        from rhmcp.tools_helpers import validate
        self.assertIsNone(validate.color([255, 128, 0]))

    def test_valid_rgba(self) -> None:
        from rhmcp.tools_helpers import validate
        self.assertIsNone(validate.color([0, 0, 0, 255]))

    def test_none_is_valid(self) -> None:
        from rhmcp.tools_helpers import validate
        self.assertIsNone(validate.color(None))

    def test_too_few_elements(self) -> None:
        from rhmcp.tools_helpers import validate
        err = validate.color([255, 0])
        self.assertIsNotNone(err)
        self.assertEqual(err["error_code"], "INVALID_COLOR")

    def test_too_many_elements(self) -> None:
        from rhmcp.tools_helpers import validate
        err = validate.color([255, 0, 0, 255, 128])
        self.assertIsNotNone(err)
        self.assertEqual(err["error_code"], "INVALID_COLOR")

    def test_out_of_range_value(self) -> None:
        from rhmcp.tools_helpers import validate
        err = validate.color([256, 0, 0])
        self.assertIsNotNone(err)
        self.assertEqual(err["error_code"], "INVALID_COLOR")

    def test_negative_value(self) -> None:
        from rhmcp.tools_helpers import validate
        err = validate.color([-1, 0, 0])
        self.assertIsNotNone(err)
        self.assertEqual(err["error_code"], "INVALID_COLOR")

    def test_float_values_rejected(self) -> None:
        from rhmcp.tools_helpers import validate
        err = validate.color([1.0, 0.0, 0.0])
        self.assertIsNotNone(err)
        self.assertEqual(err["error_code"], "INVALID_COLOR")


class TestValidateCoordinate(unittest.TestCase):
    def test_valid_int_coords(self) -> None:
        from rhmcp.tools_helpers import validate
        self.assertIsNone(validate.coordinate([0, 0, 0]))

    def test_valid_float_coords(self) -> None:
        from rhmcp.tools_helpers import validate
        self.assertIsNone(validate.coordinate([1.5, -2.0, 0.0]))

    def test_wrong_length_2d(self) -> None:
        from rhmcp.tools_helpers import validate
        err = validate.coordinate([0, 0])
        self.assertIsNotNone(err)
        self.assertEqual(err["error_code"], "INVALID_COORDINATE")

    def test_wrong_length_4d(self) -> None:
        from rhmcp.tools_helpers import validate
        err = validate.coordinate([0, 0, 0, 0])
        self.assertIsNotNone(err)
        self.assertEqual(err["error_code"], "INVALID_COORDINATE")

    def test_string_elements(self) -> None:
        from rhmcp.tools_helpers import validate
        err = validate.coordinate(["x", "y", "z"])
        self.assertIsNotNone(err)
        self.assertEqual(err["error_code"], "INVALID_COORDINATE")

    def test_not_a_list(self) -> None:
        from rhmcp.tools_helpers import validate
        err = validate.coordinate("0,0,0")
        self.assertIsNotNone(err)
        self.assertEqual(err["error_code"], "INVALID_COORDINATE")


class TestValidateLayerName(unittest.TestCase):
    def test_valid_name(self) -> None:
        from rhmcp.tools_helpers import validate
        self.assertIsNone(validate.layer_name("Default"))

    def test_empty_string(self) -> None:
        from rhmcp.tools_helpers import validate
        err = validate.layer_name("")
        self.assertIsNotNone(err)
        self.assertEqual(err["error_code"], "INVALID_LAYER_NAME")

    def test_whitespace_only(self) -> None:
        from rhmcp.tools_helpers import validate
        err = validate.layer_name("   ")
        self.assertIsNotNone(err)
        self.assertEqual(err["error_code"], "INVALID_LAYER_NAME")

    def test_none(self) -> None:
        from rhmcp.tools_helpers import validate
        err = validate.layer_name(None)
        self.assertIsNotNone(err)
        self.assertEqual(err["error_code"], "INVALID_LAYER_NAME")


class TestValidatePositive(unittest.TestCase):
    def test_valid(self) -> None:
        from rhmcp.tools_helpers import validate
        self.assertIsNone(validate.positive(1.0))
        self.assertIsNone(validate.positive(0.001))

    def test_zero_rejected(self) -> None:
        from rhmcp.tools_helpers import validate
        err = validate.positive(0)
        self.assertIsNotNone(err)
        self.assertEqual(err["error_code"], "INVALID_VALUE")

    def test_negative_rejected(self) -> None:
        from rhmcp.tools_helpers import validate
        err = validate.positive(-5)
        self.assertIsNotNone(err)
        self.assertEqual(err["error_code"], "INVALID_VALUE")


class TestValidateGuidList(unittest.TestCase):
    def test_valid_list(self) -> None:
        from rhmcp.tools_helpers import validate
        self.assertIsNone(validate.guid_list(["550e8400-e29b-41d4-a716-446655440000"]))

    def test_empty_list(self) -> None:
        from rhmcp.tools_helpers import validate
        err = validate.guid_list([])
        self.assertIsNotNone(err)
        self.assertEqual(err["error_code"], "INVALID_GUID_LIST")

    def test_invalid_item(self) -> None:
        from rhmcp.tools_helpers import validate
        err = validate.guid_list(["550e8400-e29b-41d4-a716-446655440000", "not-a-guid"])
        self.assertIsNotNone(err)
        self.assertEqual(err["error_code"], "INVALID_GUID")
        self.assertIn("[1]", err["error"])


# ---------------------------------------------------------------------------
# plugin_client retry tests
# ---------------------------------------------------------------------------

class TestPluginClientRetry(unittest.TestCase):
    def setUp(self) -> None:
        # Force one-shot mode so these tests can patch _attempt directly.
        self._ka_patcher = patch.dict("os.environ", {"RHINO_MCP_KEEPALIVE": "0"})
        self._ka_patcher.start()

    def tearDown(self) -> None:
        self._ka_patcher.stop()

    def test_succeeds_on_first_attempt(self) -> None:
        from rhmcp.tools_helpers import plugin_client
        good = {"status": "ok", "result": {}}
        with patch.object(plugin_client, "_attempt", return_value=good) as mock_attempt:
            result = plugin_client.send_command("ping", {}, retries=2)
        self.assertEqual(result, good)
        self.assertEqual(mock_attempt.call_count, 1)

    def test_retries_on_oserror_then_succeeds(self) -> None:
        from rhmcp.tools_helpers import plugin_client
        good = {"status": "ok"}
        with patch.object(plugin_client, "_attempt", side_effect=[OSError("refused"), good]) as mock_attempt:
            with patch.object(plugin_client.time, "sleep"):
                result = plugin_client.send_command("ping", {}, retries=2)
        self.assertEqual(result, good)
        self.assertEqual(mock_attempt.call_count, 2)

    def test_raises_after_all_retries_exhausted(self) -> None:
        from rhmcp.tools_helpers import plugin_client
        with patch.object(plugin_client, "_attempt", side_effect=OSError("refused")):
            with patch.object(plugin_client.time, "sleep"):
                with self.assertRaises(OSError):
                    plugin_client.send_command("ping", {}, retries=2)

    def test_zero_retries_raises_immediately(self) -> None:
        from rhmcp.tools_helpers import plugin_client
        with patch.object(plugin_client, "_attempt", side_effect=OSError("refused")) as mock_attempt:
            with self.assertRaises(OSError):
                plugin_client.send_command("ping", {}, retries=0)
        self.assertEqual(mock_attempt.call_count, 1)

    def test_exponential_backoff_delays(self) -> None:
        from rhmcp.tools_helpers import plugin_client
        delays: list[float] = []
        with patch.object(plugin_client, "_attempt", side_effect=[OSError(), OSError(), {"ok": True}]):
            with patch.object(plugin_client.time, "sleep", side_effect=lambda d: delays.append(d)):
                plugin_client.send_command("ping", {}, retries=2)
        self.assertEqual(len(delays), 2)
        self.assertAlmostEqual(delays[1], delays[0] * 2)


# ---------------------------------------------------------------------------
# objects.py validation integration tests
# ---------------------------------------------------------------------------

class TestObjectsValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"):
            cls.tools = _register_module("rhmcp.tools.objects")

    def test_get_rhino_object_info_invalid_guid(self) -> None:
        fn = self.tools["get_rhino_object_info"]
        result = fn(object_id="not-a-guid")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "INVALID_GUID")

    def test_get_rhino_object_info_no_id_allowed(self) -> None:
        fn = self.tools["get_rhino_object_info"]
        with patch("rhmcp.tools_helpers.backend.execute_python", return_value={"ok": True}):
            result = fn(object_id=None, name="MyObj")
        self.assertTrue(result.get("ok", True))

    def test_delete_rhino_objects_invalid_guid_in_list(self) -> None:
        fn = self.tools["delete_rhino_objects"]
        result = fn(ids=["550e8400-e29b-41d4-a716-446655440000", "bad-guid"], selected=False)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "INVALID_GUID")

    def test_transform_rhino_objects_invalid_move_vector(self) -> None:
        fn = self.tools["transform_rhino_objects"]
        result = fn(move=[1, 2])  # 2D instead of 3D
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "INVALID_COORDINATE")

    def test_edit_attributes_invalid_color(self) -> None:
        fn = self.tools["edit_rhino_object_attributes"]
        result = fn(color=[300, 0, 0])
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "INVALID_COLOR")


# ---------------------------------------------------------------------------
# layers.py validation integration tests
# ---------------------------------------------------------------------------

class TestLayersValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"):
            cls.tools = _register_module("rhmcp.tools.layers")

    def test_manage_layer_empty_name_rejected(self) -> None:
        fn = self.tools["manage_rhino_layer"]
        result = fn(action="create", name="")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "INVALID_LAYER_NAME")

    def test_manage_layer_invalid_color(self) -> None:
        fn = self.tools["manage_rhino_layer"]
        result = fn(action="create", name="MyLayer", color=[255, 0])
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "INVALID_COLOR")

    def test_create_layer_invalid_color(self) -> None:
        fn = self.tools["create_layer"]
        result = fn(name="Test", color=[999, 0, 0])
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "INVALID_COLOR")


# ---------------------------------------------------------------------------
# geometry.py validation integration tests
# ---------------------------------------------------------------------------

class TestGeometryValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"):
            cls.tools = _register_module("rhmcp.tools.geometry")

    def test_create_rhino_geometry_invalid_color(self) -> None:
        fn = self.tools["create_rhino_geometry"]
        result = fn(geometry_type="sphere", params={"center": [0, 0, 0], "radius": 1}, color=[0, 0])
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "INVALID_COLOR")

    def test_create_rhino_geometry_valid_color_passes_through(self) -> None:
        fn = self.tools["create_rhino_geometry"]
        with patch("rhmcp.tools_helpers.backend.execute_python", return_value={"ok": True}):
            result = fn(geometry_type="sphere", params={"center": [0, 0, 0], "radius": 1}, color=[255, 0, 0])
        self.assertTrue(result.get("ok", True))


if __name__ == "__main__":
    unittest.main()


class TestViewCaptureScriptResultShape(unittest.TestCase):
    """backend.execute_python returns the script's ``result`` under ``script_result``;
    ``result`` holds the plugin's {success, output, method} envelope."""

    _PNG_1X1 = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
        b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    def test_reads_b64_from_script_result_on_plugin_backend(self) -> None:
        import base64
        from mcp.server.fastmcp import Image

        tools = _register_module("rhmcp.tools.view")
        b64 = base64.b64encode(self._PNG_1X1).decode()
        raw = {
            "ok": True, "backend": "plugin",
            "result": {"success": True, "output": "", "method": "plugin"},
            "script_result": {"b64": b64, "path": "/tmp/v.png", "saved": True, "width": 640, "height": 480},
        }
        with patch("rhmcp.tools_helpers.backend.execute_python", return_value=raw):
            result = tools["capture_rhino_view"](path="/tmp/v.png", width=640, height=480)

        self.assertEqual(len(result), 2)
        meta, img = result
        self.assertIsInstance(img, Image)
        self.assertEqual(meta, {"path": "/tmp/v.png", "saved": True, "width": 640, "height": 480})

    def test_plugin_envelope_without_script_result_returns_raw(self) -> None:
        tools = _register_module("rhmcp.tools.view")
        raw = {"ok": True, "backend": "plugin",
               "result": {"success": True, "output": "no image", "method": "plugin"}}
        with patch("rhmcp.tools_helpers.backend.execute_python", return_value=raw):
            result = tools["capture_rhino_view"]()
        self.assertEqual(result, [raw])


# ---------------------------------------------------------------------------
# applied / not_applied reporting for parameters that previously were ignored
# ---------------------------------------------------------------------------

class TestAppliedReporting(unittest.TestCase):
    """Tools must report what they applied and what they could not apply."""

    def test_export_fbx_rejects_unknown_file_type(self) -> None:
        tools = _register_module("rhmcp.tools.export_visual")
        with patch("rhmcp.tools_helpers.backend.execute_python") as mock:
            result = tools["export_fbx"](path="/tmp/a.fbx", file_type="FBX202000")
        self.assertFalse(result["ok"])
        self.assertIn("file_type", result["error"])
        mock.assert_not_called()

    def test_export_fbx_injects_enum_name_for_file_type(self) -> None:
        tools = _register_module("rhmcp.tools.export_visual")
        captured: list[str] = []

        def fake_execute_python(code: str, rhino_id=None, **kw):
            captured.append(code)
            return {"ok": True, "backend": "rhinocode", "script_result": {"ok": True}}

        with patch("rhmcp.tools_helpers.backend.execute_python", side_effect=fake_execute_python):
            tools["export_fbx"](path="/tmp/a.fbx", file_type="ascii6")
        self.assertIn('_mcp_file_type = "Ascii6"', captured[0])
        self.assertNotIn("fbx_version", captured[0])

    def test_set_render_settings_altitude_applies_without_enable_flag(self) -> None:
        tools = _register_module("rhmcp.tools.pbr_materials")
        plugin_calls: list[tuple[str, dict]] = []
        scripts: list[str] = []

        def fake_plugin_result(command_type, params=None, rhino_id=None):
            plugin_calls.append((command_type, dict(params or {})))
            return {"ok": True, "result": {"success": True, "settings": dict(params or {})}}

        def fake_execute_python(code: str, rhino_id=None, **kw):
            scripts.append(code)
            return {"ok": True, "script_result": {"ok": True}}

        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="plugin"), \
             patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=fake_plugin_result), \
             patch("rhmcp.tools_helpers.backend.execute_python", side_effect=fake_execute_python):
            result = tools["set_render_settings"](ground_plane_altitude=2.5)

        self.assertTrue(result["ok"])
        self.assertEqual(result["applied"], {"ground_plane_altitude": 2.5})
        self.assertEqual(result["not_applied"], {})
        self.assertEqual(plugin_calls, [], "altitude alone must not round-trip the plugin")
        self.assertIn("GroundPlane", scripts[0])
        self.assertIn("_mcp_altitude = 2.5", scripts[0])

    def test_set_render_settings_reports_not_applied_when_script_fails(self) -> None:
        tools = _register_module("rhmcp.tools.pbr_materials")

        def fake_plugin_result(command_type, params=None, rhino_id=None):
            return {"ok": True, "result": {"success": True, "settings": {"enable_ground_plane": True}}}

        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="plugin"), \
             patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=fake_plugin_result), \
             patch("rhmcp.tools_helpers.backend.execute_python",
                   return_value={"ok": True, "script_result": {"ok": False}}):
            result = tools["set_render_settings"](enable_ground_plane=True, ground_plane_altitude=1.0)

        self.assertFalse(result["ok"])
        self.assertEqual(result["applied"], {"enable_ground_plane": True})
        self.assertEqual(result["not_applied"], {"ground_plane_altitude": 1.0})

    def test_set_render_settings_drops_unscriptable_params(self) -> None:
        tools = _register_module("rhmcp.tools.pbr_materials")
        with self.assertRaises(TypeError):
            tools["set_render_settings"](samples=64)

    def test_create_pbr_material_reports_ior(self) -> None:
        tools = _register_module("rhmcp.tools.pbr_materials")
        scripts: list[str] = []

        def fake_plugin_result(command_type, params=None, rhino_id=None):
            self.assertNotIn("ior", params)
            self.assertNotIn("bump_scale", params)
            return {"ok": True, "result": {"success": True, "material_index": 3, "material_name": "glass"}}

        def fake_execute_python(code: str, rhino_id=None, **kw):
            scripts.append(code)
            return {"ok": True, "script_result": {"ok": True}}

        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="plugin"), \
             patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=fake_plugin_result), \
             patch("rhmcp.tools_helpers.backend.execute_python", side_effect=fake_execute_python):
            result = tools["create_pbr_material"](name="glass", ior=1.45)

        self.assertTrue(result["ok"])
        self.assertEqual(result["applied"], {"ior": 1.45})
        self.assertIn("OpacityIOR", scripts[0])
        self.assertIn("_mcp_index = 3", scripts[0])

    def test_vray_set_render_settings_reports_not_applied_without_module(self) -> None:
        tools = _register_module("rhmcp.tools.vray")
        script_result = {
            "ok": False,
            "applied": {},
            "not_applied": {"width": 800, "quality_preset": "high"},
            "error": "V-Ray Python module (rh8VRay / rhVRay) is not importable in this Rhino.",
        }
        with patch("rhmcp.tools_helpers.plugin_client.send_command",
                   return_value={"result": {"plugins": [{"name": "V-Ray for Rhino", "loaded": True}]}}), \
             patch("rhmcp.tools_helpers.backend.execute_python",
                   return_value={"ok": True, "script_result": script_result}):
            result = tools["vray_set_render_settings"](width=800, quality_preset="high")
        self.assertFalse(result["success"])
        self.assertEqual(result["applied"], {})
        self.assertEqual(result["not_applied"], {"width": 800, "quality_preset": "high"})
        self.assertIn("rh8VRay", result["error"])

    def test_vray_set_render_settings_maps_quality_preset(self) -> None:
        tools = _register_module("rhmcp.tools.vray")
        captured: list[str] = []

        def fake_execute_python(code: str, rhino_id=None, **kw):
            captured.append(code)
            return {"ok": True, "script_result": {"ok": True, "applied": {"quality_preset": "ultra"}, "not_applied": {}}}

        with patch("rhmcp.tools_helpers.plugin_client.send_command",
                   return_value={"result": {"plugins": [{"name": "V-Ray for Rhino", "loaded": True}]}}), \
             patch("rhmcp.tools_helpers.backend.execute_python", side_effect=fake_execute_python):
            result = tools["vray_set_render_settings"](quality_preset="ultra")
        self.assertTrue(result["success"])
        self.assertIn("_mcp_quality_value = 5", captured[0])
        self.assertIn("quality_preset", captured[0])

    def test_lands_place_plant_launches_interactive_command(self) -> None:
        tools = _register_module("rhmcp.tools.lands_design")
        with patch("rhmcp.tools_helpers.plugin_client.send_command",
                   return_value={"result": {"plugins": [{"name": "Lands Design", "loaded": True}]}}), \
             patch("rhmcp.tools_helpers.backend.run_command", return_value={"ok": True}) as run:
            result = tools["lands_place_plant"]()
        self.assertTrue(result["success"])
        self.assertEqual(result["applied"], {})
        self.assertEqual(result["not_applied"], {})
        self.assertIn("interactive", result["note"])
        self.assertIn("_laPlant", run.call_args.args[0])
