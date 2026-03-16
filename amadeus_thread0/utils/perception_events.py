from __future__ import annotations

import json
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVENT_SEED_BANK_PATH = PROJECT_ROOT / "evals" / "perception_event_seed_bank.json"

_SENSE_SHORTCUTS: dict[str, dict[str, Any]] = {
    "wave": {"seed_id": "user_wave_ping"},
    "busy": {"seed_id": "user_busy_window_tangle"},
    "coffee": {"seed_id": "desk_cold_coffee"},
    "fish": {"seed_id": "fish_keychain_glimpse"},
    "night": {"seed_id": "late_night_screen_glow"},
    "self_focus": {"seed_id": "self_lab_focus_window"},
    "self_break": {"seed_id": "self_break_small_opening"},
    "checkin": {"seed_id": "scheduled_checkin_due_light"},
    "deadline": {"seed_id": "scheduled_deadline_article_due"},
    "shared": {"seed_id": "scheduled_watch_window"},
    "idle_work": {"seed_id": "time_idle_work_checkin"},
    "idle_space": {"seed_id": "time_idle_respect_space"},
    "scene": {
        "kind": "scene_observation",
        "source": "vision",
        "event_frame": "custom_scene_observation",
        "response_style_hint": "companion",
        "tags": ["vision", "user_scene"],
        "require_text": True,
    },
    "gesture": {
        "kind": "gesture_signal",
        "source": "vision",
        "event_frame": "custom_gesture_signal",
        "response_style_hint": "companion",
        "tags": ["vision", "gesture", "presence_ping"],
        "require_text": True,
    },
    "ambient": {
        "kind": "ambient_shift",
        "source": "ambient",
        "event_frame": "custom_ambient_shift",
        "response_style_hint": "companion",
        "tags": ["ambient"],
        "require_text": True,
    },
}


def _clean_text(value: Any) -> str:
    return str(value or "").encode("utf-8", "ignore").decode("utf-8").strip()


def _normalize_ref(value: Any) -> str:
    text = _clean_text(value).lower()
    text = text.replace("-", "_").replace(" ", "_")
    return text


@lru_cache(maxsize=1)
def load_event_seed_bank() -> dict[str, dict[str, Any]]:
    try:
        raw = json.loads(EVENT_SEED_BANK_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    seeds = raw.get("seeds") if isinstance(raw, dict) else []
    bank: dict[str, dict[str, Any]] = {}
    if not isinstance(seeds, list):
        return bank
    for item in seeds:
        if not isinstance(item, dict):
            continue
        seed_id = str(item.get("id") or "").strip()
        if seed_id:
            bank[seed_id] = dict(item)
    return bank


def list_event_seed_rows() -> list[str]:
    bank = load_event_seed_bank()
    rows: list[str] = []
    for seed_id in sorted(bank):
        item = bank[seed_id]
        kind = str(item.get("kind") or "").strip() or "unknown"
        source = str(item.get("source") or "").strip() or "unknown"
        status = str(item.get("status") or "").strip() or "unknown"
        tags = item.get("tags") if isinstance(item.get("tags"), list) else []
        rows.append(
            f"- {seed_id} [{kind}/{source}/{status}]"
            + (f" tags={tags[:4]}" if tags else "")
        )
    return rows


def list_sense_rows() -> list[str]:
    rows: list[str] = []
    for ref in sorted(_SENSE_SHORTCUTS):
        spec = _SENSE_SHORTCUTS[ref]
        if spec.get("seed_id"):
            rows.append(f"- {ref} -> {spec['seed_id']}")
        else:
            rows.append(
                f"- {ref} -> {spec['kind']}"
                + (" (requires note)" if spec.get("require_text") else "")
            )
    return rows


def _resolve_seed_ref(seed_ref: str) -> tuple[str, dict[str, Any]] | None:
    bank = load_event_seed_bank()
    if seed_ref in bank:
        return seed_ref, dict(bank[seed_ref])
    normalized = _normalize_ref(seed_ref)
    for seed_id, item in bank.items():
        if _normalize_ref(seed_id) == normalized:
            return seed_id, dict(item)
    return None


def build_seed_event(seed_ref: str, *, note_override: str = "", now_ts: int | None = None) -> tuple[str, dict[str, Any]] | None:
    resolved = _resolve_seed_ref(seed_ref)
    if resolved is None:
        return None
    seed_id, seed = resolved
    event = seed.get("event") if isinstance(seed.get("event"), dict) else {}
    if not event:
        return None
    payload_event = dict(event)
    if _clean_text(note_override):
        note = _clean_text(note_override)
        payload_event["text"] = note
        payload_event["effective_text"] = note
        payload_event["semantic_goal"] = note[:220]
    payload_event.setdefault("created_at", int(now_ts or time.time()))
    return seed_id, payload_event


def build_custom_event(
    *,
    kind: str,
    text: str,
    source: str,
    tags: list[str] | None = None,
    event_frame: str = "",
    response_style_hint: str = "companion",
    now_ts: int | None = None,
) -> dict[str, Any]:
    clean_text = _clean_text(text)
    if not clean_text:
        raise ValueError("custom event text is required")
    out = {
        "kind": _clean_text(kind) or "external_event",
        "source": _clean_text(source) or "external",
        "text": clean_text,
        "effective_text": clean_text,
        "semantic_goal": clean_text[:220],
        "response_style_hint": _clean_text(response_style_hint) or "companion",
        "event_frame": _clean_text(event_frame) or "custom_event",
        "tags": [_clean_text(item) for item in (tags or []) if _clean_text(item)],
        "created_at": int(now_ts or time.time()),
    }
    return out


def build_sense_event(sense_ref: str, *, note_override: str = "", now_ts: int | None = None) -> tuple[str, dict[str, Any]]:
    normalized = _normalize_ref(sense_ref)
    spec = _SENSE_SHORTCUTS.get(normalized)
    if spec is None:
        built = build_seed_event(sense_ref, note_override=note_override, now_ts=now_ts)
        if built is not None:
            return built
        raise ValueError(f"unknown sense ref: {sense_ref}")

    seed_id = str(spec.get("seed_id") or "").strip()
    if seed_id:
        built = build_seed_event(seed_id, note_override=note_override, now_ts=now_ts)
        if built is None:
            raise ValueError(f"seed not available for sense ref: {sense_ref}")
        return normalized, built[1]

    require_text = bool(spec.get("require_text"))
    text = _clean_text(note_override)
    if require_text and not text:
        raise ValueError(f"sense ref '{sense_ref}' requires a note after '|', e.g. /sense {sense_ref} | ...")
    return normalized, build_custom_event(
        kind=_clean_text(spec.get("kind") or "external_event"),
        text=text,
        source=_clean_text(spec.get("source") or "external"),
        tags=[_clean_text(item) for item in (spec.get("tags") or []) if _clean_text(item)],
        event_frame=_clean_text(spec.get("event_frame") or "custom_event"),
        response_style_hint=_clean_text(spec.get("response_style_hint") or "companion"),
        now_ts=now_ts,
    )
