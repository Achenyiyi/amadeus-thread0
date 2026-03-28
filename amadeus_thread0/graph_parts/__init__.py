"""LangGraph-aligned graph components for Amadeus-K."""

from .implicit_idle import build_implicit_idle_event_override, build_implicit_idle_state_update
from .state import ThreadState

__all__ = [
    "ThreadState",
    "build_graph",
    "build_implicit_idle_event_override",
    "build_implicit_idle_state_update",
    "reset_runtime_caches",
]


def __getattr__(name: str):
    if name in {"build_graph", "reset_runtime_caches"}:
        from .graph_builder import build_graph, reset_runtime_caches

        mapping = {
            "build_graph": build_graph,
            "reset_runtime_caches": reset_runtime_caches,
        }
        return mapping[name]
    raise AttributeError(name)
