# Rhino MCP Plug-in

This folder contains the Rhino-side socket server for Rhino 7/8 workflows.

Commands inside Rhino:

- `MCPStart`: starts the socket server on `127.0.0.1:1999`.
- `MCPStop`: stops the socket server.
- `MCPStatus`: prints current server status.

The socket protocol is compatible with the MCP server's `plugin` backend:

```json
{"type": "create_object", "params": {"type": "sphere", "params": {"center": [0,0,0], "radius": 5}}}
```

Python MCP backend setup:

```bash
export RHINO_MCP_BACKEND=plugin
export RHINO_MCP_HOST=127.0.0.1
export RHINO_MCP_PORT=1999
```

Build:

```bash
./scripts/build-plugin.sh
```

Package with Yak:

```bash
./scripts/package-plugin.sh
```
