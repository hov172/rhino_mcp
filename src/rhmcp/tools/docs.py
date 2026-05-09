"""
Small built-in Rhino API guidance search.
"""

from __future__ import annotations

import ast
import os
import pkgutil
import re

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers.rhinoscript_docs import RHINOSCRIPT_MODULES, get_function, search_functions

# Human-readable display names for each tool module.
_MODULE_LABELS: dict[str, str] = {
    "advanced_geometry":     "Advanced Geometry",
    "ai_generation":         "AI 3D Generation",
    "analysis":              "Analysis & Measurement",
    "annotations":           "Annotations",
    "asset_libraries":       "Asset Libraries (Poly Haven & Sketchfab)",
    "blocks":                "Blocks (Instance Definitions)",
    "boolean_operations":    "Boolean Operations",
    "curve_operations":      "Curve Operations",
    "docs":                  "Documentation & Search",
    "document":              "Document & File I/O",
    "documents":             "Document Reading (PDF/Image/Spreadsheet)",
    "enscape":               "Enscape Real-Time Rendering",
    "geometry":              "Geometry Creation",
    "gh_anemone":            "Grasshopper — Anemone (Looping)",
    "gh_canvas":             "Grasshopper — Canvas",
    "gh_document":           "Grasshopper — Definition Management",
    "gh_human_elefront":     "Grasshopper — Human & Elefront",
    "gh_kangaroo":           "Grasshopper — Kangaroo Physics",
    "gh_ladybug":            "Grasshopper — Ladybug & Honeybee",
    "gh_lunchbox":           "Grasshopper — LunchBox (Paneling)",
    "gh_params":             "Grasshopper — Parameters",
    "gh_pufferfish":         "Grasshopper — Pufferfish (Morphing)",
    "gh_solution":           "Grasshopper — Solution & Baking",
    "gh_weaverbird":         "Grasshopper — Weaverbird (Subdivision)",
    "groups":                "Groups",
    "lands_design":          "Lands Design (Landscape)",
    "layers":                "Layers",
    "materials":             "Materials",
    "mesh_ops":              "Mesh Operations",
    "objects":               "Object Editing & Selection",
    "pbr_materials":         "PBR Materials & Rendering",
    "plugin_socket":         "Plugin Socket",
    "plugins":               "Plugin Management",
    "python":                "Scripting (Python & C#)",
    "reference_compat":      "Reference-Compatible Aliases",
    "session":               "Session & Commands",
    "surface_ops":           "Surface Operations",
    "transforms":            "Advanced Transforms",
    "undo":                  "Undo / Redo",
    "urban":                 "Urban Design — Core",
    "urban_design_language": "Urban Design — Design Language",
    "urban_pipeline":        "Urban Design — Studio Pipeline",
    "urban_prompt":          "Urban Design — Prompt Parsing",
    "urban_renders":         "Urban Design — Renders",
    "urban_report":          "Urban Design — Reports",
    "userdata":              "User Data (Object & Document)",
    "view":                  "Views & Viewport",
    "visualarq":             "VisualARQ (Architectural BIM)",
    "vray":                  "V-Ray Rendering",
}


def _count_mcp_tools(module_name: str, tools_dir: str) -> list[str]:
    """Return names of @mcp.tool-decorated functions in a module file."""
    path = os.path.join(tools_dir, module_name + ".py")
    try:
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
    except (OSError, SyntaxError):
        return []
    names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for dec in node.decorator_list:
            # matches @mcp.tool(...) or @mcp.tool
            is_mcp_tool = (
                (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr == "tool")
                or (isinstance(dec, ast.Attribute) and dec.attr == "tool")
            )
            if is_mcp_tool:
                names.append(node.name)
                break
    return names


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Search Rhino MCP Docs", readOnlyHint=True))
    def search_rhino_docs(query: str, limit: int = 8) -> dict[str, object]:
        """
        Search bundled Rhino scripting guidance and API notes.

        This is a compact local reference for common modeling operations. For
        exhaustive docs, use McNeel's RhinoCommon and RhinoScriptSyntax API
        references.
        """
        data_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "rhino_notes.md")
        with open(data_path, encoding="utf-8") as fh:
            text = fh.read()
        chunks = [chunk.strip() for chunk in re.split(r"\n(?=## )", text) if chunk.strip()]
        terms = [term.lower() for term in re.findall(r"\w+", query)]
        scored: list[tuple[int, str]] = []
        for chunk in chunks:
            haystack = chunk.lower()
            score = sum(haystack.count(term) for term in terms)
            if score:
                scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        return {
            "query": query,
            "results": [{"score": score, "text": chunk} for score, chunk in scored[:limit]],
        }

    @mcp.tool(annotations=ToolAnnotations(title="Search RhinoScript Functions", readOnlyHint=True))
    def search_rhinoscript_functions(query: str, limit: int = 10) -> list[dict[str, object]]:
        """
        Search common RhinoScriptSyntax functions by name, signature, or description.
        """
        return search_functions(query, limit)

    @mcp.tool(annotations=ToolAnnotations(title="Get RhinoScript Docs", readOnlyHint=True))
    def get_rhinoscript_docs(topic: str, include_examples: bool = True, max_functions: int = 5) -> dict[str, object]:
        """
        Return documentation for functions relevant to a modeling topic.
        """
        functions = search_functions(topic, max_functions)
        return {
            "success": bool(functions),
            "topic": topic,
            "functions_found": len(functions),
            "documentation": functions,
            "include_examples": include_examples,
            "usage_reminder": "Import with: import rhinoscriptsyntax as rs",
        }

    @mcp.tool(annotations=ToolAnnotations(title="List RhinoScript Modules", readOnlyHint=True))
    def list_rhinoscript_modules() -> dict[str, object]:
        """
        List bundled RhinoScriptSyntax modules and function counts.
        """
        modules = [
            {
                "module": module["ModuleName"],
                "function_count": len(module["functions"]),
                "example_functions": [func["Name"] for func in module["functions"][:5]],
            }
            for module in RHINOSCRIPT_MODULES
        ]
        return {
            "total_modules": len(modules),
            "total_functions": sum(int(module["function_count"]) for module in modules),
            "modules": modules,
        }

    @mcp.tool(annotations=ToolAnnotations(title="Get RhinoScript Module Functions", readOnlyHint=True))
    def get_module_functions(module_name: str) -> dict[str, object]:
        """
        Get functions in a bundled RhinoScriptSyntax module.
        """
        for module in RHINOSCRIPT_MODULES:
            if module["ModuleName"].lower() == module_name.lower():
                return {"module": module["ModuleName"], "function_count": len(module["functions"]), "functions": module["functions"]}
        return {"error": "Module not found", "available_modules": [module["ModuleName"] for module in RHINOSCRIPT_MODULES]}

    @mcp.tool(annotations=ToolAnnotations(title="Get RhinoScript Function", readOnlyHint=True))
    def get_rhinoscript_function(function_name: str) -> dict[str, object]:
        """
        Get one bundled RhinoScriptSyntax function entry.
        """
        found = get_function(function_name)
        return found or {"error": "Function not found", "function_name": function_name}

    @mcp.tool(annotations=ToolAnnotations(title="List Tool Categories", readOnlyHint=True))
    def list_tool_categories(include_tool_names: bool = False) -> dict[str, object]:
        """
        Return all tool categories with their tool counts.

        Use this before a complex task to discover which categories are
        available and how many tools each contains, without loading every
        tool description into context.

        ``include_tool_names=True`` adds the individual tool names to each
        category entry — useful when you need to find a specific tool.
        """
        import rhmcp.tools as _pkg

        tools_dir = _pkg.__path__[0]
        categories: list[dict[str, object]] = []
        total = 0

        for info in pkgutil.iter_modules([tools_dir]):
            tool_names = _count_mcp_tools(info.name, tools_dir)
            if not tool_names:
                continue
            label = _MODULE_LABELS.get(info.name, info.name.replace("_", " ").title())
            entry: dict[str, object] = {
                "category": label,
                "module": info.name,
                "count": len(tool_names),
            }
            if include_tool_names:
                entry["tools"] = tool_names
            categories.append(entry)
            total += len(tool_names)

        categories.sort(key=lambda c: c["category"])  # type: ignore[arg-type]
        return {
            "total_tools": total,
            "total_categories": len(categories),
            "tip": "Call list_tool_categories(include_tool_names=True) to see tool names per category.",
            "categories": categories,
        }
