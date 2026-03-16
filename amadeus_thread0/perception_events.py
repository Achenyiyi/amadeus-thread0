"""Backward-compatible facade over ``amadeus_thread0.utils.perception_events``."""

from __future__ import annotations

from ._compat import compat_exports

__all__, __getattr__, __dir__ = compat_exports(".utils.perception_events", __package__)

