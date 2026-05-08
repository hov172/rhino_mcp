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
            params = json.loads(line.split(" = ", 1)[1])
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
            params = json.loads(code.split("\n", 1)[0].split(" = ", 1)[1])
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
            params = json.loads(code.split("\n", 1)[0].split(" = ", 1)[1])
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
            params = json.loads(code.split("\n", 1)[0].split(" = ", 1)[1])
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
            params = json.loads(code.split("\n", 1)[0].split(" = ", 1)[1])
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
            params = json.loads(code.split("\n", 1)[0].split(" = ", 1)[1])
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
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"):
            result = fn(id="some-guid-1234")
        self.assertFalse(result["ok"])
        self.assertIn("material_index", result["error"])
        self.assertIn("material_name", result["error"])

    def test_set_object_material_with_index_proceeds(self) -> None:
        """Providing material_index must not trigger the no-identifier error."""
        fn = self.tools["set_object_material"]
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"), \
             patch("rhmcp.tools_helpers.backend.execute_python", return_value={"ok": True, "result": {}}):
            result = fn(id="some-guid-1234", material_index=0)
        self.assertNotEqual(result.get("ok"), False, "Should not get validation error")

    def test_set_object_material_with_name_proceeds(self) -> None:
        """Providing material_name must not trigger the no-identifier error."""
        fn = self.tools["set_object_material"]
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"), \
             patch("rhmcp.tools_helpers.backend.execute_python", return_value={"ok": True, "result": {}}):
            result = fn(id="some-guid-1234", material_name="Wood")
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

    def test_manage_rhino_layer_invalid_action_reaches_execute_python(self) -> None:
        """
        manage_rhino_layer with an unrecognised action forwards the payload to
        execute_python (where the rhinoscript raises ValueError).  The tool
        itself must NOT raise — it should return whatever execute_python returns.
        """
        fn = self.tools["manage_rhino_layer"]
        # Simulate execute_python returning an error dict (as rhinocode would
        # if the script raised a ValueError).
        error_response = {"ok": False, "backend": "rhinocode", "error": "Unsupported layer action: fly"}
        with patch("rhmcp.tools_helpers.backend.preferred_backend", return_value="rhinocode"), \
             patch("rhmcp.tools_helpers.backend.execute_python", return_value=error_response) as mock_exec:
            result = fn(action="fly", name="Phantom")
        mock_exec.assert_called_once()
        # The tool should propagate the error dict from execute_python.
        self.assertFalse(result["ok"])

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
        mock_plugin.assert_called_once_with("gh_open_document", {"path": "/tmp/test.gh"})

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
        mock_plugin.assert_called_once_with("gh_new_document", {"name": "MyDef"})

    def test_new_definition_omits_name_when_none(self) -> None:
        """gh_new_definition sends empty params when name is None."""
        fn = self.tools["gh_new_definition"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}) as mock_plugin:
            fn()
        mock_plugin.assert_called_once_with("gh_new_document", {})


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
            "gh_add_component", {"component_guid": guid, "x": 100.0, "y": 200.0}
        )

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
        with patch("rhmcp.tools_helpers.backend.plugin_result") as mock:
            mock.return_value = {"result": {"components": [{"id": "hb-guid", "name": "HB Room from Solid"}], "instance_guid": "inst-123"}}
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


if __name__ == "__main__":
    unittest.main()
