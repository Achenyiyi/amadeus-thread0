from __future__ import annotations

import importlib

import pytest


_FACADE_CASES = [
    ("amadeus_thread0.settings", "amadeus_thread0.runtime.settings"),
    ("amadeus_thread0.modeling", "amadeus_thread0.runtime.modeling"),
    ("amadeus_thread0.session_orchestrator", "amadeus_thread0.runtime.session_orchestrator"),
    ("amadeus_thread0.tts_io", "amadeus_thread0.runtime.tts_io"),
    ("amadeus_thread0.cli_views", "amadeus_thread0.utils.cli_views"),
    ("amadeus_thread0.runtime_audit", "amadeus_thread0.utils.runtime_audit"),
    ("amadeus_thread0.tool_registry", "amadeus_thread0.utils.tool_registry"),
    ("amadeus_thread0.perception_events", "amadeus_thread0.utils.perception_events"),
    ("amadeus_thread0.tools", "amadeus_thread0.utils.tools"),
]


def _public_names(module) -> list[str]:
    exported = getattr(module, "__all__", None)
    if exported is not None:
        return [str(name) for name in exported]
    return [name for name in vars(module) if not name.startswith("_")]


@pytest.mark.parametrize(("facade_name", "target_name"), _FACADE_CASES)
def test_package_facade_exports_target_public_symbols(facade_name: str, target_name: str) -> None:
    facade = importlib.import_module(facade_name)
    target = importlib.import_module(target_name)
    public_names = _public_names(target)
    assert public_names, f"{target_name} should expose at least one public symbol"

    sample = public_names[: min(5, len(public_names))]
    for symbol in sample:
        assert getattr(facade, symbol) is getattr(target, symbol)
        assert symbol in dir(facade)
