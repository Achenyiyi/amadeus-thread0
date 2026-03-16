from __future__ import annotations

from importlib import import_module
from types import ModuleType
from typing import Any


def _public_names(module: ModuleType) -> list[str]:
    exported = getattr(module, "__all__", None)
    if exported is not None:
        return [str(name) for name in exported]
    return sorted(name for name in vars(module) if not name.startswith("_"))


def compat_exports(target_module: str, package: str) -> tuple[list[str], Any, Any]:
    """Build a thin compatibility facade for a moved module."""

    module = import_module(target_module, package)
    exported = _public_names(module)

    def __getattr__(name: str) -> Any:
        if name in exported:
            return getattr(module, name)
        raise AttributeError(f"module {package!r} has no attribute {name!r}")

    def __dir__() -> list[str]:
        return sorted(exported)

    return exported, __getattr__, __dir__
