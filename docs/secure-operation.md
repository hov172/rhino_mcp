# Operating rhino-mcp 0.17.1

For package builds and installation, see the [upgrade guide](upgrade-0.17.1.md). The security behavior introduced in 0.17.0 remains in effect. See the [validation record](../release/validation-0.17.1.md) for the checks performed; a local read-only check does not validate remote TLS or mutation recovery.

## Execution and recovery

A TCP request is retried only when connection establishment fails, before sending
starts. A timeout, partial write, disconnected peer, or invalid response after that
point returns `EXECUTION_OUTCOME_UNKNOWN` with `retry_safe: false`. Inspect the
Rhino document before manually retrying. Neither another socket attempt nor the
CLI fallback repeats that request. The old `RHINO_MCP_RUNPYTHON_FALLBACK` switch is
no longer used: absence of a CLI result is also an ambiguous execution outcome.

Connections are replaced when the requested Rhino destination changes. Every
underlying registered tool accepts `rhino_id`; internal calls inherit that target, including
calls that directly use the socket client. HTTP callers cannot override their
authorized destination with raw host/port arguments.

Plugin mutations have an isolated Rhino undo record. A reported failure restores
that record; a marker prevents an empty failed operation from undoing the user's
preceding edit. Python CLI execution also owns an undo record. This recovers
changes Rhino records for undo, including object modifications and deletions.
It cannot reverse filesystem writes, network effects, unsupported third-party
state, or code that deliberately changes undo history. Finish an active Rhino
command before invoking tools; inability to create a record is an error.

## Execution controls

`RHINO_MCP_ENABLE_RHINOSCRIPT`, `RHINO_MCP_ENABLE_CSHARP`, and
`RHINO_MCP_ENABLE_RUN_COMMAND` accept `0`, `false`, or `no` to disable a capability.
Set them in **both the MCP process and Rhino's environment**. They are enforced at
Python socket dispatch, CLI execution, and C# command dispatch. Grasshopper script
creation checks the chosen language; replacing an existing script requires both
script capabilities because its language is not supplied by that operation.

Compatibility defaults remain enabled for trusted local workstation use.
Disabling Python also disables built-in operations implemented through Python.
These switches are not a sandbox: opening a third-party definition, loading a
plugin, or granting arbitrary commands can also execute code. Restrict HTTP tool
grants to reviewed operations. Run separate OS accounts/processes when filesystem
and credential isolation is needed.

## TLS

Local stdio and loopback HTTP remain available. Non-loopback HTTP now requires:

```sh
export RHINO_MCP_HTTP_TLS_CERT=/secure/http-server.pem
export RHINO_MCP_HTTP_TLS_KEY=/secure/http-server-key.pem
export RHINO_MCP_HTTP_ALLOWED_HOSTS='rhino.example.internal:*'
rhino-mcp --transport http --host 0.0.0.0 --port 8000
```

Connect to `https://<certificate-hostname>:8000/` using a client that trusts the
issuing CA. Use a certificate whose SAN covers the hostname clients actually use.
Set `RHINO_MCP_HTTP_ALLOWED_HOSTS` to the certificate hostname with `:*` for
any port. For browser clients, also set `RHINO_MCP_HTTP_ALLOWED_ORIGINS` to their
exact origins. DNS rebinding protection remains enabled. The token is required on MCP requests. `/health` is a liveness endpoint.

For a remote Rhino plugin, set these in **Rhino's environment**, then restart its
MCP listener:

```sh
RHINO_MCP_BIND_HOST=0.0.0.0
RHINO_MCP_PLUGIN_SECRET=<shared-secret>
RHINO_MCP_PLUGIN_TLS_CERT=/secure/rhino-server.pfx
RHINO_MCP_PLUGIN_TLS_PASSWORD=<pfx-password>
```

Set these on the **Python MCP server**:

```sh
RHINO_MCP_HOST=rhino.example.internal
RHINO_MCP_ALLOW_REMOTE=1
RHINO_MCP_PLUGIN_SECRET=<same-shared-secret>
RHINO_MCP_PLUGIN_TLS=1
RHINO_MCP_PLUGIN_TLS_CA=/secure/issuing-ca.pem
```

The PFX must contain the private key. Python validates both the CA chain and server
hostname. The CA setting is optional when the issuer is already trusted by the OS.
TLS cannot be disabled for non-loopback plugin connections. The plugin supports
TLS 1.2/1.3, caps concurrent clients at 32, and bounds handshake/request-read time.

For Docker, mount certificates read-only and pass the HTTP and plugin TLS
variables. The plugin certificate must cover `host.docker.internal` if that is the
configured target. The container health check uses the configured HTTP CA/cert.
Do not reuse old plaintext Docker commands without supplying this configuration.

## HTTP identities and grants

A legacy `RHINO_MCP_AUTH_TOKEN` grants owner access; use at least 32 characters.
Without a configured token, a random owner token is printed to stderr at startup.
For separate identities, set `RHINO_MCP_AUTH_CONFIG` to a protected local JSON file:

```json
[
  {
    "id": "designer-a",
    "token": "replace-with-a-unique-random-token-of-at-least-32-characters",
    "tools": ["urban_get_metrics", "urban_get_design_language", "urban_set_design_language"],
    "projects": ["courtyard-study"],
    "rhino_ids": ["12345"]
  }
]
```

All three grant lists are required. `*` explicitly grants all values in that list.
Use tool names from discovery; unknown names grant no capability. Tokens and IDs
must be unique. Invalid configuration stops startup. Restart after rotating keys.
The same enforcement applies in compact and direct mode, before the tool runs.
Compact discovery filters tools and preserves category and safety annotations.

Every underlying tool accepts `project_id` (default `default`) and `rhino_id`. A sole project
or instance grant becomes the identity's default; otherwise pass an explicitly
granted value. Workflow state is keyed by identity, project, and instance. Local
stdio uses the `local` identity. Reports use separate hashed storage namespaces
and unique artifact names. State is in-memory and resets on process restart; at
256 scopes, new scopes fail instead of evicting another project's state.

Only one mutating tool/workflow runs per instance within a server process;
concurrent mutations return `RHINO_BUSY`. Status/read tools remain responsive.
This is not cross-process scheduling. Different projects sharing one Rhino
instance still share its active document. Assign distinct instances and appropriate
tool grants when separating users' geometry; project state isolation alone does
not create separate Rhino documents.

Rate limiting is per authenticated identity (120 requests/minute by default).
`RHINO_MCP_RATE_LIMIT_RPM=0` disables it; negative values are rejected. Invalid
credentials cannot create rate-limit entries. OPTIONS and health are exempt.

## Definitions and external dependencies

Urban workflows require the files in `grasshopper/urban` on the Rhino host.
Set `RHINO_MCP_GH_DIR` in the MCP process to their path **as seen by Rhino**,
especially when Python runs in Docker or on another machine. Install the
required Grasshopper plugins and weather files on that host. Tool registration
does not install or validate third-party dependencies.

## Results and exports

- Metrics report `source: grasshopper`, `source: heuristic` with `estimated: true`,
  or `ok: false` / `METRICS_UNAVAILABLE`. Missing data is not a measured zero.
- Solar analysis fails if required outputs are absent or non-finite.
- Reports identify estimates and omit unavailable metric numbers.
- PDF bytes must start with `%PDF-`. If PDF generation is unavailable, export
  produces HTML, leaves `pdf_url` empty, and returns the actual `format` and a
  warning. `format=html` never calls the PDF service. Pipeline URLs use the actual
  artifact, and failed steps produce `partial: true` / `ok: false`.
- GH1-to-GH2 migration rejects unmapped components before changing GH2 unless
  `allow_partial=true`. A partial migration never automatically closes GH1.
  `complete` describes mapped graph coverage; `semantic_equivalence_verified`
  remains false. Custom component behavior and data are not proven equivalent.

## Development verification

CI runs the full non-integration Python suite on 3.10, 3.11, and 3.12. Regression
coverage includes dropped responses, destination changes, dispatch gates, TLS
validation configuration, HTTP MCP lifespan, grants, state isolation, concurrency,
PDF validation, missing metrics, partial migration, and Python undo behavior.

`dotnet build rhino_plugin/RhinoMCPPlugin/RhinoMCPPlugin.csproj` builds without
installing into Rhino. Explicitly pass `-p:InstallPluginAfterBuild=true` for the
legacy macOS post-build copy. Live Rhino validation is separate from mocked tests:
use a scratch document and test deletion/modification rollback, third-party tools,
TLS listener startup, and actual multi-instance routing before deployment.
