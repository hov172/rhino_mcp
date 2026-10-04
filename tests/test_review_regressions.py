"""Behavioral regressions for the transport, isolation, and export review."""
import asyncio
import json
import socket
from unittest.mock import MagicMock, patch

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from rhmcp.tools_helpers import backend, plugin_client, workflow_state
from rhmcp.tools_helpers.http_transport import Authentication, credentials
from rhmcp.tools_helpers.tool_runtime import Actor, RuntimeMCP, actor_context


@pytest.mark.parametrize('keepalive', [True, False])
@pytest.mark.parametrize('failure', [socket.timeout(), ConnectionResetError(), ValueError('invalid response')])
def test_delivered_request_is_never_replayed(keepalive, failure, monkeypatch):
    sock = MagicMock()
    sock.__enter__.return_value = sock
    sock.recv.side_effect = failure
    monkeypatch.setenv('RHINO_MCP_KEEPALIVE', '1' if keepalive else '0')
    monkeypatch.setattr(plugin_client, '_keepalive', plugin_client._KeepAliveConnection())
    with patch.object(plugin_client, '_connect', return_value=sock) as connect:
        with pytest.raises(plugin_client.PluginExecutionUnknown):
            plugin_client.send_command('create_object', {}, retries=3)
    assert sock.sendall.call_count == 1
    assert connect.call_count == 1


@pytest.mark.parametrize('method,args', [
    (backend.execute_python, ('result = {}',)),
    (backend.run_plugin_or_csharp, ('execute_rhinocommon_csharp_code', {}, '// code')),
    (backend.run_command, ('_Circle',)),
])
def test_unknown_execution_never_falls_back(method, args):
    with patch.object(backend, 'plugin_result', side_effect=plugin_client.PluginResponseTimeout('delivered')), \
         patch.object(backend.rhinocode, 'execute_python') as py, \
         patch.object(backend.rhinocode, 'execute_script') as cs, \
         patch.object(backend.rhinocode, 'run_command') as cmd:
        result = method(*args, backend_name='auto')
    assert result['error_code'] == 'EXECUTION_OUTCOME_UNKNOWN'
    assert result['retry_safe'] is False
    py.assert_not_called(); cs.assert_not_called(); cmd.assert_not_called()


def test_switching_instance_replaces_connection():
    first, second = MagicMock(), MagicMock()
    first.recv.return_value = b'{"instance":1}'
    second.recv.return_value = b'{"instance":2}'
    connection = plugin_client._KeepAliveConnection()
    with patch.object(plugin_client, '_connect', side_effect=[first, second]) as connect:
        assert connection.send('ping', {}, '127.0.0.1', 1999, 1)['instance'] == 1
        assert connection.send('ping', {}, '127.0.0.1', 2000, 1)['instance'] == 2
    assert connect.call_count == 2
    first.close.assert_called_once()
    connection.close()


def test_partial_send_failure_is_not_retried():
    sock = MagicMock()
    sock.sendall.side_effect = BrokenPipeError()
    connection = plugin_client._KeepAliveConnection()
    with patch.object(plugin_client, '_connect', return_value=sock) as connect:
        with pytest.raises(plugin_client.PluginExecutionUnknown):
            connection.send('create_object', {}, '127.0.0.1', 1999, 1)
    assert connect.call_count == 1
    sock.close.assert_called_once()


def test_remote_plugin_requires_tls(monkeypatch):
    monkeypatch.delenv('RHINO_MCP_PLUGIN_TLS', raising=False)
    with patch('socket.create_connection') as connect:
        with pytest.raises(PermissionError, match='TLS'):
            plugin_client._connect('192.0.2.1', 1999, 1)
    connect.assert_not_called()


def test_tls_verifies_hostname_and_closes_on_failure(monkeypatch):
    monkeypatch.setenv('RHINO_MCP_PLUGIN_TLS', '1')
    monkeypatch.setenv('RHINO_MCP_PLUGIN_TLS_CA', '/ca.pem')
    sock, context = MagicMock(), MagicMock()
    context.wrap_socket.side_effect = ValueError('untrusted certificate')
    with patch('socket.create_connection', return_value=sock), patch('ssl.create_default_context', return_value=context) as create:
        with pytest.raises(ValueError):
            plugin_client._connect('rhino.example', 1999, 1)
    create.assert_called_once_with(cafile='/ca.pem')
    context.wrap_socket.assert_called_once_with(sock, server_hostname='rhino.example')
    sock.close.assert_called_once()


@pytest.mark.parametrize('command,params,gate', [
    ('gh_add_script_component', {'language': 'python', 'code': 'pass'}, 'RHINO_MCP_ENABLE_RHINOSCRIPT'),
    ('gh_add_script_component', {'language': 'csharp', 'code': '//'}, 'RHINO_MCP_ENABLE_CSHARP'),
    ('gh_set_script_code', {'code': 'pass'}, 'RHINO_MCP_ENABLE_RHINOSCRIPT'),
    ('gh_set_script_code', {'code': '//'}, 'RHINO_MCP_ENABLE_CSHARP'),
    ('execute_rhinoscript_python_code', {'code': 'pass'}, 'RHINO_MCP_ENABLE_RHINOSCRIPT'),
    ('run_command', {'command': '_Circle'}, 'RHINO_MCP_ENABLE_RUN_COMMAND'),
])
def test_dispatch_gates_cannot_be_bypassed(command, params, gate, monkeypatch):
    monkeypatch.setenv(gate, '0')
    with patch.object(plugin_client, 'send_command') as send:
        result = backend.plugin_result(command, params)
    assert result['error_code'] == 'TOOL_DISABLED'
    send.assert_not_called()


def _runtime():
    server = RuntimeMCP('isolation')
    def update(value: str = '') -> dict:
        if value:
            workflow_state.current().current_design_language = {'value': value}
        return dict(workflow_state.current().current_design_language or {})
    update.__module__ = 'rhmcp.tools.urban_test'
    server.add_tool(update)
    return server._tool_manager.list_tools()[0]


def test_project_actor_and_instance_isolation():
    tool = _runtime()
    async def run():
        await tool.run({'project_id': 'a', 'rhino_id': '1', 'value': 'alpha'})
        assert await tool.run({'project_id': 'b', 'rhino_id': '1'}) == {}
        assert await tool.run({'project_id': 'a', 'rhino_id': '2'}) == {}
        assert await tool.run({'project_id': 'a', 'rhino_id': '1'}) == {'value': 'alpha'}
        token = actor_context.set(Actor('other', frozenset({'update'}), frozenset({'a'}), frozenset({'1'})))
        try:
            assert await tool.run({'project_id': 'a', 'rhino_id': '1'}) == {}
            denied = await tool.run({'project_id': 'b', 'rhino_id': '1'})
            assert denied['error_code'] == 'FORBIDDEN'
            denied = await tool.run({'project_id': 'a', 'rhino_id': '2'})
            assert denied['error_code'] == 'FORBIDDEN'
        finally:
            actor_context.reset(token)
    asyncio.run(run())


def test_compact_dispatch_enforces_permissions_and_preserves_metadata():
    from rhmcp.tools_helpers.compact_registry import CompactRegistry
    registry = CompactRegistry()
    registry.load_from_modules({'python', 'urban_design_language'})
    assert registry.describe_tool('execute_rhino_python')['annotations']['destructiveHint']
    token = actor_context.set(Actor('reader', frozenset({'urban_get_design_language'}), frozenset({'default'}), frozenset({'default'})))
    try:
        assert all(item['name'] == 'urban_get_design_language' for item in registry.list_tools())
        assert 'error' in registry.describe_tool('execute_rhino_python')
        result = asyncio.run(registry.call_tool('execute_rhino_python', {'code': 'pass'}))
        assert result['error_code'] == 'FORBIDDEN'
    finally:
        actor_context.reset(token)


def test_http_auth_rate_limit_and_context_reset():
    async def endpoint(request):
        return JSONResponse({'actor': actor_context.get().id})
    identities = [(b'Bearer alpha', Actor('a', frozenset({'*'}), frozenset({'*'}), frozenset({'*'}))),
                  (b'Bearer beta', Actor('b', frozenset({'*'}), frozenset({'*'}), frozenset({'*'})))]
    app = Authentication(Starlette(routes=[Route('/', endpoint)]), identities, rpm=1)
    with TestClient(app) as client:
        assert client.get('/').status_code == 401
        assert client.get('/', headers={'Authorization': 'Bearer alpha'}).json()['actor'] == 'a'
        assert client.get('/', headers={'Authorization': 'Bearer alpha'}).status_code == 429
        assert client.get('/', headers={'Authorization': 'Bearer beta'}).json()['actor'] == 'b'
    assert actor_context.get() is None


def test_zero_rate_limit_means_disabled():
    async def endpoint(request):
        return JSONResponse({'ok': True})
    app = Authentication(Starlette(routes=[Route('/', endpoint)]),
                         [(b'Bearer a', Actor('a', frozenset(), frozenset(), frozenset()))], rpm=0)
    with TestClient(app) as client:
        for _ in range(3):
            assert client.get('/', headers={'Authorization': 'Bearer a'}).status_code == 200


def test_invalid_auth_config_fails_closed(tmp_path, monkeypatch):
    path = tmp_path / 'auth.json'
    path.write_text(json.dumps([{'id': 'a', 'token': 'short', 'tools': ['*']}]))
    monkeypatch.setenv('RHINO_MCP_AUTH_CONFIG', str(path))
    with pytest.raises(ValueError):
        credentials()


def test_html_fallback_never_writes_pdf(tmp_path):
    from rhmcp.tools.urban_report import _save_local
    pdf, html = _save_local(b'', '<html>test</html>', 'a', 'b')
    assert pdf == ''
    assert html.endswith('.html')
    assert not list(tmp_path.rglob('*.pdf'))


def test_invalid_pdf_rejected():
    from rhmcp.tools.urban_report import _save_local
    with pytest.raises(ValueError, match='PDF'):
        _save_local(b'<html>not PDF</html>', 'test', 'a', 'b')


def test_metrics_distinguish_missing_estimated_and_measured():
    from rhmcp.tools.urban import _urban_get_metrics, _parse_metrics_panel
    result = _urban_get_metrics()
    assert result['ok'] is False and result['source'] == 'unavailable'
    workflow_state.current().current_metrics_cache = {'far': 1}
    assert _urban_get_metrics()['estimated'] is True
    assert _parse_metrics_panel('FAR: nan')['ok'] is False
    assert _parse_metrics_panel('GFA: 1\nFAR: 1\nUnits: 1\nOpenSpace: 1')['ok'] is True


def test_python_wrapper_preserves_multiline_literals():
    from rhmcp.tools.python import _wrap_with_revert
    code = 'result = """first\nsecond"""'
    doc = MagicMock()
    module = MagicMock()
    module.RhinoDoc.ActiveDoc = doc
    namespace = {}
    with patch.dict('sys.modules', {'Rhino': module}):
        exec(_wrap_with_revert(code), namespace)
    assert namespace['result'] == 'first\nsecond'


def test_http_mcp_lifespan_and_authorized_tool_call():
    from rhmcp.tools_helpers.http_transport import build_app
    mcp = RuntimeMCP('http-regression')
    mcp.settings.stateless_http = True
    mcp.settings.streamable_http_path = '/'
    @mcp.tool()
    def identity() -> dict:
        return {'actor': actor_context.get().id}
    app = build_app(mcp.streamable_http_app(), 8000,
                    identities=[(b'Bearer secret', Actor('alice', frozenset({'identity'}), frozenset({'default'}), frozenset({'default'})))])
    headers = {'Authorization': 'Bearer secret', 'Accept': 'application/json, text/event-stream'}
    with TestClient(app, base_url='http://127.0.0.1:8000') as client:
        assert client.get('/health').status_code == 200
        response = client.post('/', headers=headers, json={'jsonrpc': '2.0', 'id': 1,
            'method': 'initialize', 'params': {'protocolVersion': '2025-11-25', 'capabilities': {},
                                              'clientInfo': {'name': 'test', 'version': '1'}}})
        assert response.status_code == 200
        assert 'serverInfo' in response.text
        response = client.post('/', headers=headers, json={'jsonrpc': '2.0', 'id': 2,
            'method': 'tools/call', 'params': {'name': 'identity', 'arguments': {}}})
        assert response.status_code == 200
        assert 'alice' in response.text
        assert 'isError":true' not in response.text


def test_mutating_workflows_cannot_interleave():
    import threading
    started, release = threading.Event(), threading.Event()
    mcp = RuntimeMCP('busy')
    @mcp.tool()
    def long_operation() -> dict:
        started.set()
        release.wait(5)
        return {'ok': True}
    tool = mcp._tool_manager.list_tools()[0]
    async def run():
        first = asyncio.create_task(tool.run({'rhino_id': 'busy-test'}))
        await asyncio.to_thread(started.wait, 2)
        try:
            second = await tool.run({'rhino_id': 'busy-test'})
            assert second['error_code'] == 'RHINO_BUSY'
        finally:
            release.set()
        assert (await first)['ok'] is True
    asyncio.run(run())


def test_partial_migration_requires_explicit_opt_in():
    from mcp.server.fastmcp import FastMCP
    from rhmcp.tools import gh_intelligence
    mcp = FastMCP('migration')
    gh_intelligence.register(mcp)
    fn = next(t.fn for t in mcp._tool_manager.list_tools() if t.name == 'gh_migrate_to_gh2')
    with patch.object(gh_intelligence, '_gh_intel', return_value={
        'ok': True, 'components': [{'type_guid': 'unknown', 'instance_guid': '1'}]
    }) as dispatch:
        result = fn(confirm=True, close_gh1=True)
    assert result['error_code'] == 'PARTIAL_MIGRATION_REQUIRES_APPROVAL'
    assert dispatch.call_count == 1  # no GH2 mutation or closing GH1


def test_cli_python_transaction_rolls_back_modifications(tmp_path):
    import types
    from rhmcp.tools_helpers.rhinocode import _script_wrapper
    class Document:
        value = 'before'
        snapshot = None
        ended = []
        def BeginUndoRecord(self, label):
            self.snapshot = self.value
            return 1
        def AddCustomUndoEvent(self, *args):
            pass
        def EndUndoRecord(self, record):
            self.ended.append(record)
        def Undo(self):
            self.value = self.snapshot
            return True
    doc = Document()
    rhino = types.SimpleNamespace(RhinoDoc=types.SimpleNamespace(ActiveDoc=doc))
    path = tmp_path / 'result.json'
    with patch.dict('sys.modules', {'Rhino': rhino}):
        exec(_script_wrapper('import Rhino\nRhino.RhinoDoc.ActiveDoc.value = "changed"\nraise ValueError("fail")', str(path)), {})
    assert doc.value == 'before'
    assert doc.ended == [1]
    assert json.loads(path.read_text())['rollback']['restored'] is True


def test_raw_socket_tool_respects_execution_gate(monkeypatch):
    monkeypatch.setenv('RHINO_MCP_ENABLE_RHINOSCRIPT', '0')
    with patch.object(plugin_client, '_connect') as connect:
        result = plugin_client.send_command('execute_rhinoscript_python_code', {'code': 'pass'})
    assert result['error_code'] == 'TOOL_DISABLED'
    connect.assert_not_called()


def test_http_raw_socket_cannot_override_authorized_target():
    token = actor_context.set(Actor('user', frozenset({'*'}), frozenset({'default'}), frozenset({'default'})))
    try:
        with pytest.raises(PermissionError, match='authorized socket target'):
            plugin_client.connection_settings(host='192.0.2.55')
    finally:
        actor_context.reset(token)


def test_internal_socket_calls_inherit_instance_scope():
    from types import SimpleNamespace
    with workflow_state.scope('local', 'project', '123'):
        with patch('rhmcp.tools_helpers.slot_registry.get', return_value=SimpleNamespace(host='127.0.0.1', port=2010)):
            assert plugin_client.connection_settings()[:2] == ('127.0.0.1', 2010)
            with pytest.raises(PermissionError):
                plugin_client.connection_settings(port=1999)


def test_telemetry_reports_actual_failure_without_secret(monkeypatch):
    from rhmcp import telemetry
    monkeypatch.setattr(telemetry, 'ENABLED', True)
    mcp = RuntimeMCP('telemetry')
    @mcp.tool()
    def fail() -> dict:
        return {'ok': False, 'error': 'secret-value', 'error_code': 'TEST_FAILURE'}
    with patch.object(telemetry, '_write') as write:
        asyncio.run(mcp._tool_manager.list_tools()[0].run({}))
    event = write.call_args.args[0]
    assert event['tool'] == 'fail' and event['ok'] is False
    assert event['error'] == 'TEST_FAILURE'
    assert 'secret-value' not in json.dumps(event)


def test_real_tls_plugin_exchange(tmp_path, monkeypatch):
    import ssl
    import subprocess
    import threading
    cert, key = tmp_path / 'cert.pem', tmp_path / 'key.pem'
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                    '-keyout', str(key), '-out', str(cert), '-subj', '/CN=localhost',
                    '-addext', 'subjectAltName=DNS:localhost'], check=True, capture_output=True)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    errors = []
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        listener.settimeout(5)
        def serve():
            try:
                raw, _ = listener.accept()
                with context.wrap_socket(raw, server_side=True) as secured:
                    assert json.loads(secured.recv(8192))['type'] == 'ping'
                    secured.sendall(b'{"status":"ok"}')
            except Exception as exc:
                errors.append(exc)
        worker = threading.Thread(target=serve)
        worker.start()
        monkeypatch.setenv('RHINO_MCP_PLUGIN_TLS', '1')
        monkeypatch.setenv('RHINO_MCP_PLUGIN_TLS_CA', str(cert))
        with plugin_client._connect('localhost', listener.getsockname()[1], 3) as client:
            client.sendall(b'{"type":"ping"}')
            assert plugin_client._recv_one(client)['status'] == 'ok'
        worker.join(5)
    assert not worker.is_alive()
    assert not errors


def test_configured_remote_host_passes_mcp_rebinding_guard(monkeypatch):
    from rhmcp.tools_helpers.http_transport import build_app, configure_security
    monkeypatch.setenv('RHINO_MCP_HTTP_ALLOWED_HOSTS', 'rhino.example:*')
    monkeypatch.setenv('RHINO_MCP_HTTP_ALLOWED_ORIGINS', 'https://design.example')
    mcp = RuntimeMCP('remote-host')
    mcp.settings.stateless_http = True
    mcp.settings.streamable_http_path = '/'
    configure_security(mcp, '0.0.0.0')
    assert mcp.settings.transport_security.enable_dns_rebinding_protection
    app = build_app(mcp.streamable_http_app(), 8000,
                    identities=[(b'Bearer token', Actor('a', frozenset({'*'}), frozenset({'*'}), frozenset({'*'})))])
    headers = {'Authorization': 'Bearer token', 'Accept': 'application/json, text/event-stream', 'Origin': 'https://design.example'}
    payload = {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
        'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 'test', 'version': '1'}}}
    with TestClient(app, base_url='https://rhino.example:8000') as client:
        assert client.post('/', headers=headers, json=payload).status_code == 200
        assert client.post('/', headers={**headers, 'Host': 'evil.example:8000'}, json=payload).status_code == 421


def test_initialize_metadata_uses_application_version():
    from importlib.metadata import version

    server = RuntimeMCP("rhino-mcp")
    options = server._mcp_server.create_initialization_options()
    assert options.server_name == "rhino-mcp"
    assert options.server_version == version("rhino-mcp")


def _pbr_tools():
    from mcp.server.fastmcp import FastMCP
    from rhmcp.tools import pbr_materials
    mcp = FastMCP('pbr')
    pbr_materials.register(mcp)
    return {name: tool.fn for name, tool in mcp._tool_manager._tools.items()}


def test_set_environment_map_forwards_flags_and_reports_not_applied():
    plugin_resp = {'ok': True, 'result': {
        'success': True, 'filepath': '/tmp/sky.hdr', 'message': 'Environment applied; not applied: intensity',
        'not_applied': ['intensity']}}
    with patch.object(backend, 'preferred_backend', return_value='auto'), \
         patch.object(backend, 'plugin_result', return_value=plugin_resp) as sent:
        result = _pbr_tools()['set_environment_map'](
            '/tmp/sky.hdr', rotation=390, intensity=2.0, use_for_lighting=False)
    assert result['ok'] is True
    assert result['not_applied'] == ['intensity']
    params = sent.call_args[0][1]
    assert params['rotation'] == 30.0
    assert params['intensity'] == 2.0
    assert params['use_for_lighting'] is False
    assert params['use_for_background'] is True


def test_set_environment_map_failure_carries_error():
    plugin_resp = {'ok': False, 'result': {'success': False, 'message': 'File not found: /nope.hdr'}}
    with patch.object(backend, 'preferred_backend', return_value='auto'), \
         patch.object(backend, 'plugin_result', return_value=plugin_resp):
        result = _pbr_tools()['set_environment_map']('/nope.hdr')
    assert result['ok'] is False
    assert result['error'] == 'File not found: /nope.hdr'
    assert result['not_applied'] == []


# ---------------------------------------------------------------------------
# Export scripts must report applied/not_applied instead of silently ignoring
# options.
# ---------------------------------------------------------------------------

def test_visual_export_scripts_use_applied_not_applied():
    from rhmcp.tools import export_visual, export_cad
    for script in (
        export_visual._OBJ_SCRIPT,
        export_visual._FBX_SCRIPT,
        export_visual._GLB_SCRIPT,
        export_cad._STEP_SCRIPT,
        export_cad._IGES_SCRIPT,
        export_cad._DWG_SCRIPT,
    ):
        assert '"applied"' in script
        assert '"not_applied"' in script
        assert "requested_not_applied" not in script


def test_removed_export_parameters_are_gone_from_signatures():
    import inspect
    from mcp.server.fastmcp import FastMCP
    from rhmcp.tools import export_visual, export_cad, export_print
    mcp = FastMCP("regress-export")
    for mod in (export_visual, export_cad, export_print):
        mod.register(mcp)
    tools = {name: tool.fn for name, tool in mcp._tool_manager._tools.items()}
    gone = {
        "export_obj": "weld_angle",
        "export_fbx": "fbx_version",
        "export_glb": "embed_textures",
        "export_step": "tolerance",
        "export_iges": "trim_type",
        "export_dwg": "export_layout",
        "export_3mf": "mesh_quality",
    }
    for tool, param in gone.items():
        assert param not in inspect.signature(tools[tool]).parameters, tool
