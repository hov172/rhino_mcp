"""Authorization and workflow context shared by compact and direct tool dispatch."""
from __future__ import annotations

import asyncio
from contextvars import ContextVar
from dataclasses import dataclass
import functools
import inspect
from importlib.metadata import version
import re
import threading
import time
from typing import get_type_hints

from mcp.server.fastmcp import FastMCP
from rhmcp.tools_helpers import workflow_state


@dataclass(frozen=True)
class Actor:
    id: str
    tools: frozenset[str]
    projects: frozenset[str]
    rhino_ids: frozenset[str]


actor_context: ContextVar[Actor | None] = ContextVar('actor', default=None)
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()
_DISCOVERY = {'list_rhino_tools', 'describe_rhino_tool', 'call_rhino_tool'}


def permitted(name: str) -> bool:
    actor = actor_context.get()
    return actor is None or '*' in actor.tools or name in actor.tools


def _allowed(value: str, allowed: frozenset[str]) -> bool:
    return '*' in allowed or value in allowed


def _default(allowed: frozenset[str]) -> str:
    return next(iter(allowed)) if len(allowed) == 1 and '*' not in allowed else 'default'


def _instance_lock_key(target: str) -> str:
    import os
    host = os.environ.get("RHINO_MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("RHINO_MCP_PORT", "1999"))
    if target != "default" or os.environ.get("RHINO_MCP_USE_SLOT_REGISTRY") == "1":
        from rhmcp.tools_helpers.slot_registry import get
        try:
            slot = get(None if target == "default" else target)
            host, port = slot.host, slot.port
        except RuntimeError:
            if target != "default":
                return "unavailable:" + target
    host = "127.0.0.1" if host == "localhost" else host
    return f"{host}:{port}"


class RuntimeMCP(FastMCP):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # FastMCP does not expose a version argument. Without this, its underlying
        # server advertises the MCP SDK version in the initialize response.
        self._mcp_server.version = version("rhino-mcp")

    async def list_tools(self):
        return [tool for tool in await super().list_tools()
                if tool.name in _DISCOVERY or permitted(tool.name)]

    def add_tool(self, fn, **kwargs):
        name = kwargs.get('name') or fn.__name__
        if name in _DISCOVERY:
            return super().add_tool(fn, **kwargs)
        signature = inspect.signature(fn)
        # Resolve future annotations before wrapping a function from another module.
        hints = get_type_hints(fn)
        params = [p.replace(annotation=hints.get(p.name, p.annotation)) for p in signature.parameters.values()]
        if 'project_id' not in signature.parameters:
            params.append(inspect.Parameter('project_id', inspect.Parameter.KEYWORD_ONLY, default='default', annotation=str))
        if 'rhino_id' not in signature.parameters:
            params.append(inspect.Parameter('rhino_id', inspect.Parameter.KEYWORD_ONLY, default=None, annotation=str | None))
        annotations = kwargs.get('annotations')
        readonly = bool(annotations and annotations.readOnlyHint)

        @functools.wraps(fn)
        async def execute(**arguments):
            actor = actor_context.get()
            if not permitted(name):
                return {'ok': False, 'error': 'Tool is not authorized for this identity.', 'error_code': 'FORBIDDEN'}
            project = arguments.get('project_id', 'default')
            target = arguments.get('rhino_id') or 'default'
            if actor:
                if project == 'default':
                    project = _default(actor.projects)
                if target == 'default':
                    target = _default(actor.rhino_ids)
                if not _allowed(project, actor.projects) or not _allowed(target, actor.rhino_ids):
                    return {'ok': False, 'error': 'Project or Rhino instance is not authorized.', 'error_code': 'FORBIDDEN'}
            if not isinstance(project, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', project):
                return {'ok': False, 'error': 'Invalid project_id.', 'error_code': 'INVALID_VALUE'}
            if 'rhino_id' in arguments or 'rhino_id' in signature.parameters:
                arguments['rhino_id'] = None if target == 'default' else target
            if 'project_id' not in signature.parameters:
                arguments.pop('project_id', None)
            if 'rhino_id' not in signature.parameters:
                arguments.pop('rhino_id', None)

            def run():
                # One mutating workflow at a time per Rhino instance. This also
                # prevents interleaving multi-step changes across projects/users.
                lock = None
                if not readonly:
                    lock_key = _instance_lock_key(target)
                    with _locks_guard:
                        if lock_key not in _locks and len(_locks) >= 256:
                            return {'ok': False, 'error': 'Instance capacity reached.', 'error_code': 'CAPACITY_EXCEEDED'}
                        lock = _locks.setdefault(lock_key, threading.Lock())
                    if not lock.acquire(blocking=False):
                        return {'ok': False, 'error': 'Another operation is running on this Rhino instance.', 'error_code': 'RHINO_BUSY'}
                try:
                    with workflow_state.scope(actor.id if actor else 'local', project, target):
                        result = fn(**arguments)
                        if inspect.isawaitable(result):
                            return asyncio.run(result)
                        return result
                finally:
                    if lock is not None:
                        lock.release()
            # Sync Rhino/HTTP calls must not block the MCP event loop.
            return await asyncio.to_thread(run)

        @functools.wraps(fn)
        async def invoke(**arguments):
            from rhmcp import telemetry
            started = time.monotonic()
            result, error = None, None
            try:
                result = await execute(**arguments)
                return result
            except Exception as exc:
                error = type(exc).__name__
                raise
            finally:
                if telemetry.ENABLED:
                    actor = actor_context.get()
                    telemetry.record(name, time.monotonic() - started, result, error,
                                     actor.id if actor else "local", arguments.get("project_id", "default"))

        invoke.__signature__ = signature.replace(parameters=params, return_annotation=hints.get('return', signature.return_annotation))
        invoke.__annotations__ = {p.name: p.annotation for p in params}
        invoke.__annotations__['return'] = hints.get('return', signature.return_annotation)
        return super().add_tool(invoke, **kwargs)
