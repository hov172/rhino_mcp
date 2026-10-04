"""Process-local workflow state isolated by authenticated actor, project and Rhino."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import threading


@dataclass
class WorkflowState:
    current_typology: str | None = None
    current_massing_layer: str | None = None
    current_slider_guids: dict = field(default_factory=dict)
    current_metrics_guid: str | None = None
    current_bake_guid: str | None = None
    current_params: dict = field(default_factory=dict)
    current_site_width: float | None = None
    current_site_depth: float | None = None
    current_metrics_cache: dict | None = None
    current_solar: dict | None = None
    current_design_language: dict | None = None
    current_renders: dict = field(default_factory=dict)
    report_history: list = field(default_factory=list)
    pipeline_history: list = field(default_factory=list)
    current_run: dict | None = None


_default = WorkflowState()
_scope: ContextVar[tuple[str, str, str]] = ContextVar('workflow_scope', default=('local', 'default', 'default'))
_states: dict[tuple[str, str, str], WorkflowState] = {('local', 'default', 'default'): _default}
_lock = threading.Lock()


def current() -> WorkflowState:
    key = _scope.get()
    with _lock:
        if key not in _states:
            if len(_states) >= 256:
                raise RuntimeError('Workflow capacity reached; restart the server to release inactive projects.')
            _states[key] = WorkflowState()
        return _states[key]


def rhino_id() -> str | None:
    value = _scope.get()[2]
    return None if value == 'default' else value


def storage_namespace() -> str:
    import hashlib
    return hashlib.sha256(repr(_scope.get()).encode()).hexdigest()[:24]


@contextmanager
def scope(actor: str, project: str, rhino: str):
    token = _scope.set((actor, project, rhino))
    try:
        yield current()
    finally:
        _scope.reset(token)


def reset_all() -> None:
    """For isolated tests; production reset tools only clear their current scope."""
    global _default
    with _lock:
        _default = WorkflowState()
        _states.clear()
        _states[('local', 'default', 'default')] = _default
