from __future__ import annotations

from typing import Any

from .schemas import clamp01

VALID_INTERACTION_FRAMES = {
    "natural",
    "casual",
    "relationship",
    "memory_recall",
    "selfhood",
    "structured",
    "companion",
}

VALID_SELFHOOD_SCENES = {
    "",
    "dialogue_equality",
    "relationship_degradation",
    "equality_not_servitude",
    "value_conflict_depth",
    "digital_selfhood",
    "boundary_non_compliance",
    "imperfect_coexistence",
    "own_rhythm_autonomy",
}


def normalize_appraisal_payload(raw: dict[str, Any] | None) -> dict[str, Any]:
    data = dict(raw or {}) if isinstance(raw, dict) else {}
    salience = data.get("salience") if isinstance(data.get("salience"), dict) else {}
    interaction_frame = str(data.get("interaction_frame") or "").strip().lower()
    selfhood_scene = str(data.get("selfhood_scene") or "").strip().lower()
    if interaction_frame not in VALID_INTERACTION_FRAMES:
        interaction_frame = ""
    if selfhood_scene not in VALID_SELFHOOD_SCENES:
        selfhood_scene = ""
    data["interaction_frame"] = interaction_frame
    data["selfhood_scene"] = selfhood_scene
    data["salience"] = {
        "task": clamp01(salience.get("task"), 0.0),
        "relationship": clamp01(salience.get("relationship"), 0.0),
        "memory": clamp01(salience.get("memory"), 0.0),
        "selfhood": clamp01(salience.get("selfhood"), 0.0),
        "companionship": clamp01(salience.get("companionship"), 0.0),
    }
    return data


def derive_response_style_hint(
    *,
    appraisal: dict[str, Any] | None,
    science_mode: bool,
    continuation_mode: bool,
    previous_hint: str = "",
    current_event: dict[str, Any] | None = None,
) -> str:
    event = current_event if isinstance(current_event, dict) else {}
    event_kind = str(event.get("kind") or "").strip().lower()
    prior = str(previous_hint or "").strip().lower()
    app = normalize_appraisal_payload(appraisal)
    signals = app.get("signals") if isinstance(app.get("signals"), dict) else {}
    salience = app.get("salience") if isinstance(app.get("salience"), dict) else {}
    frame = str(app.get("interaction_frame") or "").strip().lower()

    if event_kind in {"gesture_signal", "ambient_shift"}:
        return "companion"
    if science_mode or clamp01(salience.get("task"), 0.0) >= 0.72:
        return "structured"
    if frame in VALID_INTERACTION_FRAMES:
        return frame
    if clamp01(salience.get("selfhood"), 0.0) >= 0.64:
        return "selfhood"
    if bool(signals.get("memory_salient")) or clamp01(salience.get("memory"), 0.0) >= 0.64:
        return "memory_recall"
    if bool(signals.get("repair")) or bool(signals.get("conflict")) or bool(signals.get("withdrawal")):
        return "relationship"
    if clamp01(salience.get("relationship"), 0.0) >= 0.66:
        return "relationship"
    if bool(signals.get("care")) or clamp01(salience.get("companionship"), 0.0) >= 0.60:
        return "companion"
    if continuation_mode and prior:
        return prior
    return prior or "natural"


def build_event_tags(
    *,
    response_style_hint: str,
    science_mode: bool,
    continuation_mode: bool,
    appraisal: dict[str, Any] | None,
    current_event: dict[str, Any] | None = None,
) -> list[str]:
    tags: list[str] = []
    event = current_event if isinstance(current_event, dict) else {}
    event_kind = str(event.get("kind") or "").strip().lower()
    if response_style_hint:
        tags.append(str(response_style_hint).strip())
    if science_mode:
        tags.append("science")
    if continuation_mode:
        tags.append("continuation")
    if event_kind and event_kind != "user_utterance":
        tags.append(event_kind)
    app = normalize_appraisal_payload(appraisal)
    signals = app.get("signals") if isinstance(app.get("signals"), dict) else {}
    salience = app.get("salience") if isinstance(app.get("salience"), dict) else {}
    for key in ("repair", "withdrawal", "care", "conflict", "memory_salient"):
        if bool(signals.get(key)):
            tags.append(key)
    if clamp01(salience.get("selfhood"), 0.0) >= 0.62:
        tags.append("selfhood_salient")
    if clamp01(salience.get("task"), 0.0) >= 0.62:
        tags.append("task_salient")
    if clamp01(salience.get("companionship"), 0.0) >= 0.58:
        tags.append("companionship_salient")
    selfhood_scene = str(app.get("selfhood_scene") or "").strip().lower()
    if selfhood_scene:
        tags.append(selfhood_scene)
    return list(dict.fromkeys([item for item in tags if str(item).strip()]))


def build_event_frame(
    *,
    response_style_hint: str,
    science_mode: bool,
    continuation_mode: bool,
    appraisal: dict[str, Any] | None,
    current_event: dict[str, Any] | None = None,
) -> str:
    event = current_event if isinstance(current_event, dict) else {}
    event_kind = str(event.get("kind") or "").strip().lower()
    app = normalize_appraisal_payload(appraisal)
    selfhood_scene = str(app.get("selfhood_scene") or "").strip().lower()

    if continuation_mode:
        return "continuing an active interaction thread"
    if science_mode or response_style_hint == "structured":
        return "task-focused interaction with live interpersonal carryover"
    if response_style_hint == "selfhood":
        if selfhood_scene:
            return f"selfhood reflection around {selfhood_scene}"
        return "deep selfhood reflection inside an ongoing relationship"
    if response_style_hint == "relationship":
        return "relationship-sensitive exchange with possible long-tail impact"
    if response_style_hint == "memory_recall":
        return "shared-memory recall inside an ongoing relationship"
    if response_style_hint == "companion":
        return "low-pressure companion dialogue"
    if event_kind in {"gesture_signal", "ambient_shift", "scene_observation"}:
        return "nonverbal or ambient perception entering the interaction loop"
    return "ordinary ongoing interaction"
