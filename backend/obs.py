"""Optional observability via agentobs (github.com/arunkonapala/agent-observability).

No-ops unless the package is installed AND AGENTOBS_EXPORTER is set, so the
app runs identically with observability off. Import span helpers from here,
never from agentobs directly.
"""

from contextlib import contextmanager

try:
    from agentobs import (  # noqa: F401
        agent_turn,
        init_tracing,
        llm_call,
        record_llm_usage,
        tool_call,
    )

    ENABLED = True
except ImportError:
    ENABLED = False

    @contextmanager
    def _noop(*args, **kwargs):
        yield None

    agent_turn = tool_call = llm_call = _noop

    def init_tracing(*args, **kwargs):
        pass

    def record_llm_usage(*args, **kwargs):
        pass
