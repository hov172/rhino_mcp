"""Authenticated HTTP transport with bounded per-identity rate limiting."""
from __future__ import annotations

from collections import deque
import json
import os
from pathlib import Path
import secrets
import sys
import time

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from rhmcp.tools_helpers.tool_runtime import Actor, actor_context


def credentials() -> list[tuple[bytes, Actor]]:
    path = os.environ.get('RHINO_MCP_AUTH_CONFIG')
    if path:
        data = json.loads(Path(path).read_text())
        if not isinstance(data, list) or not data:
            raise ValueError('RHINO_MCP_AUTH_CONFIG must contain a non-empty array of identities.')
        result = []
        ids, tokens = set(), set()
        for item in data:
            identity, token = item['id'], item['token']
            if not isinstance(identity, str) or not identity or identity == 'local':
                raise ValueError('Each HTTP identity needs a unique non-local id.')
            if not isinstance(token, str) or len(token) < 32 or identity in ids or token in tokens:
                raise ValueError('Identity IDs and tokens must be unique; tokens require at least 32 characters.')
            grants = []
            for field in ('tools', 'projects', 'rhino_ids'):
                values = item.get(field)
                if not isinstance(values, list) or not values or not all(isinstance(v, str) and v for v in values):
                    raise ValueError(f'Identity {identity}: {field} must be a non-empty string array.')
                grants.append(frozenset(values))
            result.append((f'Bearer {token}'.encode(), Actor(identity, *grants)))
            ids.add(identity)
            tokens.add(token)
        return result
    token = os.environ.get('RHINO_MCP_AUTH_TOKEN') or secrets.token_hex(32)
    if len(token) < 32:
        raise ValueError('RHINO_MCP_AUTH_TOKEN requires at least 32 characters.')
    if not os.environ.get('RHINO_MCP_AUTH_TOKEN'):
        print(f'Rhino MCP auth token: {token}', file=sys.stderr)
    return [(f'Bearer {token}'.encode(), Actor('owner', frozenset({'*'}), frozenset({'*'}), frozenset({'*'})))]


class Authentication:
    def __init__(self, app, identities, rpm=120):
        if rpm < 0:
            raise ValueError('RHINO_MCP_RATE_LIMIT_RPM must be non-negative.')
        self.app, self.identities, self.rpm = app, identities, rpm
        self.windows = {}

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['path'] == '/health' or scope['method'] == 'OPTIONS':
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        supplied = headers.get(b'authorization', b'')
        actor = None
        for expected, identity in self.identities:
            if secrets.compare_digest(supplied, expected):
                actor = identity
        if actor is None:
            return await JSONResponse({'error': 'Unauthorized'}, status_code=401)(scope, receive, send)
        if self.rpm:
            now = time.monotonic()
            hits = self.windows.setdefault(actor.id, deque())
            while hits and hits[0] <= now - 60:
                hits.popleft()
            if len(hits) >= self.rpm:
                return await JSONResponse({'error': 'Rate limit exceeded'}, status_code=429,
                                          headers={'Retry-After': '60'})(scope, receive, send)
            hits.append(now)
        token = actor_context.set(actor)
        try:
            await self.app(scope, receive, send)
        finally:
            actor_context.reset(token)


def configure_security(mcp, host: str) -> None:
    """Keep rebinding protection enabled while admitting configured TLS names."""
    from mcp.server.transport_security import TransportSecuritySettings
    settings = mcp.settings.transport_security or TransportSecuritySettings()
    settings.enable_dns_rebinding_protection = True
    extra_hosts = [value.strip() for value in os.environ.get("RHINO_MCP_HTTP_ALLOWED_HOSTS", "").split(",") if value.strip()]
    if host not in ("0.0.0.0", "::"):
        extra_hosts.append(f"[{host}]:*" if ":" in host else f"{host}:*")
    if "*" in extra_hosts:
        raise ValueError("HTTP allowed hosts must name hosts explicitly, not '*'.")
    settings.allowed_hosts = list(dict.fromkeys([*settings.allowed_hosts, *extra_hosts]))
    origins = [value.strip() for value in os.environ.get("RHINO_MCP_HTTP_ALLOWED_ORIGINS", "").split(",") if value.strip()]
    if "*" in origins:
        raise ValueError("HTTP origins must be explicit, not '*'.")
    settings.allowed_origins = list(dict.fromkeys([*settings.allowed_origins,
        "https://localhost:*", "https://127.0.0.1:*", "https://[::1]:*", *origins]))
    mcp.settings.transport_security = settings


def build_app(mcp_app, port: int, identities=None, rpm=None):
    async def health(request):
        return JSONResponse({'status': 'ok'})

    app = Starlette(routes=[Route('/health', health), Mount('/', app=mcp_app)],
                    lifespan=lambda app: mcp_app.router.lifespan_context(mcp_app))
    authenticated = Authentication(app, identities if identities is not None else credentials(),
                                  int(os.environ.get('RHINO_MCP_RATE_LIMIT_RPM', '120')) if rpm is None else rpm)
    extra_origins = [value.strip() for value in os.environ.get('RHINO_MCP_HTTP_ALLOWED_ORIGINS', '').split(',') if value.strip()]
    return CORSMiddleware(authenticated,
                          allow_origins=['http://localhost', 'http://127.0.0.1',
                                         f'http://localhost:{port}', f'http://127.0.0.1:{port}',
                                         f'https://localhost:{port}', f'https://127.0.0.1:{port}', *extra_origins],
                          allow_methods=['GET', 'POST', 'DELETE', 'OPTIONS'],
                          allow_headers=['Authorization', 'Content-Type', 'MCP-Protocol-Version', 'Mcp-Session-Id'],
                          expose_headers=['Mcp-Session-Id'])
