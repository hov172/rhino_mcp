"""Keep workflow state and generated artifacts isolated between tests."""
import pytest


@pytest.fixture(autouse=True)
def isolate_workflows(tmp_path, monkeypatch):
    from rhmcp.tools_helpers.workflow_state import reset_all
    reset_all()
    monkeypatch.setenv('RHINO_MCP_REPORT_DIR', str(tmp_path / 'reports'))
    yield
    reset_all()
