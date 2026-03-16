"""Backward-compatible facade over ``amadeus_thread0.utils.runtime_audit``."""

from __future__ import annotations

from ._compat import compat_exports

__all__, __getattr__, __dir__ = compat_exports(".utils.runtime_audit", __package__)

