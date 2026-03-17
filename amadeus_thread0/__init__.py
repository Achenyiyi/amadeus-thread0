from __future__ import annotations

from importlib import import_module
from typing import Any

from .env_bootstrap import load_project_dotenv

load_project_dotenv(override=False)

__all__ = ["agent", "app", "build_graph", "create_agent"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        mod = import_module(".agent", __name__)
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
