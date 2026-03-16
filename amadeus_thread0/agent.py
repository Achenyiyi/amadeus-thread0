from __future__ import annotations

from .graph_parts import build_graph


def create_agent():
    return build_graph()


agent = create_agent()
app = agent

__all__ = ["agent", "app", "build_graph", "create_agent"]
