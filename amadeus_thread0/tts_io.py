"""Backward-compatible facade over ``amadeus_thread0.runtime.tts_io``."""

from __future__ import annotations

from ._compat import compat_exports

__all__, __getattr__, __dir__ = compat_exports(".runtime.tts_io", __package__)

