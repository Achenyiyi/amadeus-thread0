"""Backward-compatible facade over ``amadeus_thread0.utils.tool_registry``."""

from __future__ import annotations

from ._compat import compat_exports

__all__, __getattr__, __dir__ = compat_exports(".utils.tool_registry", __package__)

