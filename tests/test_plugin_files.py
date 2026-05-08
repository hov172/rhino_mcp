from __future__ import annotations

import os
import unittest


REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class PluginFilesTest(unittest.TestCase):
    def test_plugin_project_and_package_files_exist(self) -> None:
        required = [
            "rhino_plugin/RhinoMCPPlugin/RhinoMCPPlugin.csproj",
            "rhino_plugin/RhinoMCPPlugin/Plugin.cs",
            "rhino_plugin/RhinoMCPPlugin/AssemblyInfo.cs",
            "rhino_plugin/RhinoMCPPlugin/Commands.cs",
            "rhino_plugin/RhinoMCPPlugin/RhinoMcpServer.cs",
            "rhino_plugin/RhinoMCPPlugin/CommandDispatcher.cs",
            "rhino_plugin/RhinoMCPPlugin/RhinoHandlers.cs",
            # Grasshopper handler files
            "rhino_plugin/RhinoMCPPlugin/GHDocumentHandlers.cs",
            "rhino_plugin/RhinoMCPPlugin/GHCanvasHandlers.cs",
            "rhino_plugin/RhinoMCPPlugin/GHParamHandlers.cs",
            "rhino_plugin/RhinoMCPPlugin/GHSolutionHandlers.cs",
            # Grasshopper Python tool modules
            "src/rhmcp/tools/gh_document.py",
            "src/rhmcp/tools/gh_canvas.py",
            "src/rhmcp/tools/gh_params.py",
            "src/rhmcp/tools/gh_solution.py",
            # Third-party plugin tool modules
            "src/rhmcp/tools/plugins.py",
            "src/rhmcp/tools/gh_kangaroo.py",
            "src/rhmcp/tools/gh_ladybug.py",
            "src/rhmcp/tools/gh_pufferfish.py",
            "src/rhmcp/tools/gh_weaverbird.py",
            "src/rhmcp/tools/gh_lunchbox.py",
            "src/rhmcp/tools/gh_human_elefront.py",
            "src/rhmcp/tools/gh_anemone.py",
            "src/rhmcp/tools/vray.py",
            "src/rhmcp/tools/enscape.py",
            "src/rhmcp/tools/visualarq.py",
            "src/rhmcp/tools/lands_design.py",
            "rhino_plugin/package/manifest.yml",
            "scripts/build-plugin.sh",
            "scripts/package-plugin.sh",
        ]
        for path in required:
            self.assertTrue(os.path.exists(os.path.join(REPO_DIR, path)), path)


if __name__ == "__main__":
    unittest.main()
