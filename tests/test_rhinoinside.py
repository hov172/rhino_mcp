"""Tests for host_app field in plugin_client.health_check (A2 — RhinoInside support)."""
from __future__ import annotations

import unittest
from unittest.mock import patch


class TestHealthCheckHostApp(unittest.TestCase):
    """health_check() must surface host_app from the ping response."""

    def test_includes_host_app_field_when_present(self) -> None:
        """health_check() return value must include host_app when ping provides it."""
        from rhmcp.tools_helpers import plugin_client

        mock_response = {
            "ok": True,
            "status": "ok",
            "result": {
                "ok": True,
                "version": "0.11.0",
                "rhino": "8.0",
                "host_app": "Revit",
            },
        }
        with patch.object(plugin_client, "send_command", return_value=mock_response):
            result = plugin_client.health_check()

        self.assertTrue(result["ok"])
        self.assertIn("host_app", result)
        self.assertEqual(result["host_app"], "Revit")

    def test_host_app_defaults_to_rhino_when_absent(self) -> None:
        """health_check() must default host_app to 'Rhino' when not in ping response."""
        from rhmcp.tools_helpers import plugin_client

        mock_response = {
            "ok": True,
            "status": "ok",
            "result": {
                "ok": True,
                "version": "0.11.0",
                "rhino": "8.0",
                # host_app intentionally absent
            },
        }
        with patch.object(plugin_client, "send_command", return_value=mock_response):
            result = plugin_client.health_check()

        self.assertTrue(result["ok"])
        self.assertEqual(result.get("host_app"), "Rhino")

    def test_host_app_grasshopper(self) -> None:
        """health_check() must surface host_app=Grasshopper correctly."""
        from rhmcp.tools_helpers import plugin_client

        mock_response = {
            "ok": True,
            "status": "ok",
            "result": {
                "version": "0.11.0",
                "rhino": "8.0",
                "host_app": "Grasshopper",
            },
        }
        with patch.object(plugin_client, "send_command", return_value=mock_response):
            result = plugin_client.health_check()

        self.assertEqual(result.get("host_app"), "Grasshopper")

    def test_failure_path_has_no_host_app(self) -> None:
        """health_check() failure (OSError) must not include host_app."""
        from rhmcp.tools_helpers import plugin_client

        with patch.object(plugin_client, "send_command", side_effect=OSError("Connection refused")):
            result = plugin_client.health_check()

        self.assertFalse(result["ok"])
        self.assertIn("error", result)
        self.assertNotIn("host_app", result)

    def test_unexpected_ping_response_has_no_host_app(self) -> None:
        """health_check() with unexpected (non-ok) response must not include host_app."""
        from rhmcp.tools_helpers import plugin_client

        mock_response = {
            "status": "error",
            "message": "unknown command",
        }
        with patch.object(plugin_client, "send_command", return_value=mock_response):
            result = plugin_client.health_check()

        self.assertFalse(result["ok"])
        self.assertNotIn("host_app", result)

    def test_version_and_rhino_still_present(self) -> None:
        """health_check() success must still include version and rhino fields."""
        from rhmcp.tools_helpers import plugin_client

        mock_response = {
            "ok": True,
            "result": {
                "version": "0.11.0",
                "rhino": "8.14",
                "host_app": "Rhino",
            },
        }
        with patch.object(plugin_client, "send_command", return_value=mock_response):
            result = plugin_client.health_check()

        self.assertTrue(result["ok"])
        self.assertEqual(result["version"], "0.11.0")
        self.assertEqual(result["rhino"], "8.14")
        self.assertEqual(result["host_app"], "Rhino")

    def test_latency_ms_present_on_success(self) -> None:
        """health_check() success must include a non-negative latency_ms."""
        from rhmcp.tools_helpers import plugin_client

        mock_response = {
            "ok": True,
            "result": {"version": "0.11.0", "rhino": "8.0"},
        }
        with patch.object(plugin_client, "send_command", return_value=mock_response):
            result = plugin_client.health_check()

        self.assertIn("latency_ms", result)
        self.assertGreaterEqual(result["latency_ms"], 0)


if __name__ == "__main__":
    unittest.main()
