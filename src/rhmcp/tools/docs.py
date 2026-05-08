"""
Small built-in Rhino API guidance search.
"""

from __future__ import annotations

import os
import re

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers.rhinoscript_docs import RHINOSCRIPT_MODULES, get_function, search_functions


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
