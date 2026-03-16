"""Backward-compatible facade over ``amadeus_thread0.runtime.settings``."""

from __future__ import annotations

from ._compat import compat_exports

__all__, __getattr__, __dir__ = compat_exports(".runtime.settings", __package__)

