from __future__ import annotations

from typing import Any

from ..graph_parts.chinese_semantic_surface import (
    build_runtime_replacement_policy,
    rewrite_semantic_surface_floor,
)
from .artifact_appraisal_bridge import build_artifact_appraisal_readback
from .artifact_behavior_alignment import build_artifact_behavior_alignment_readback
from .artifact_motive_bridge import build_artifact_motive_readback
from .artifact_perception_semantics import build_artifact_semantics_readback
from .multimodal_sources import normalize_multimodal_source


EMBODIED_INTERACTION_PHASE1_READINESS = "embodied_interaction_runtime_phase1_ready"
EMBODIED_INTERACTION_PHASE1_IN_PROGRESS = "embodied_interaction_runtime_phase1_in_progress"
EMBODIED_INTERACTION_PHASE1_NOT_APPLICABLE = "embodied_interaction_runtime_phase1_not_applicable"
EMBODIED_INTERACTION_PHASE2_READINESS = "embodied_interaction_runtime_phase2_ready"
EMBODIED_INTERACTION_PHASE2_IN_PROGRESS = "embodied_interaction_runtime_phase2_in_progress"
EMBODIED_INTERACTION_PHASE3_READINESS = "embodied_interaction_runtime_phase3_ready"
EMBODIED_INTERACTION_PHASE3_IN_PROGRESS = "embodied_interaction_runtime_phase3_in_progress"
EMBODIED_INTERACTION_PHASE4_READINESS = "embodied_interaction_runtime_phase4_ready"
EMBODIED_INTERACTION_PHASE4_IN_PROGRESS = "embodied_interaction_runtime_phase4_in_progress"
EMBODIED_INTERACTION_PHASE5_READINESS = "embodied_interaction_runtime_phase5_ready"
EMBODIED_INTERACTION_PHASE5_IN_PROGRESS = "embodied_interaction_runtime_phase5_in_progress"

AUTHORITY_BOUNDARY = {
    "persona_core_mutation_allowed": False,
    "memory_write_allowed": False,
    "external_mutation_allowed": False,
    "live_microphone_enabled": False,
    "live_camera_enabled": False,
    "background_screen_capture_enabled": False,
    "secret_capture_enabled": False,
    "prompt_sprawl_rewrite_allowed": False,
    "multimodal_model_api_called": False,
}

SOURCE_KIND_BY_MODALITY = {
    "text": "text",
    "image": "image_file",
    "audio": "audio_file",
    "screen": "screen_snapshot_file",
    "browser_capture": "browser_capture_ref",
}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _source_ref(source: dict[str, Any]) -> dict[str, Any]:
    modality = _clean(source.get("modality"))
    return {
        "source_ref_id": _clean(source.get("source_id") or source.get("source_ref_id")),
        "source_kind": SOURCE_KIND_BY_MODALITY.get(modality, modality or "unknown"),
        "modality": modality,
        "source_role": _clean(source.get("source_role")),
        "artifact_ref": _clean(source.get("artifact_ref")),
        "artifact_label": _clean(source.get("artifact_label")),
        "artifact_carrier": _clean(source.get("artifact_carrier")),
        "consent_scope": _clean(source.get("consent_scope")),
        "capture_method": _clean(source.get("capture_method")),
        "payload_digest": _clean(source.get("payload_digest")),
        "status": _clean(source.get("status")),
        "block_reasons": list(source.get("block_reasons") or []),
    }


def _candidate_sources(turn: dict[str, Any]) -> list[dict[str, Any]]:
    current_event = _dict_or_empty(turn.get("current_event"))
    perception = _dict_or_empty(current_event.get("perception"))
    event_hints = _dict_or_empty(current_event.get("digital_body_hints"))
    perception_hints = _dict_or_empty(perception.get("digital_body_hints"))
    session_context = _dict_or_empty(turn.get("session_context"))
    session_hints = _dict_or_empty(session_context.get("digital_body_hints"))
    digital_body = _dict_or_empty(turn.get("digital_body"))
    resource_state = _dict_or_empty(digital_body.get("resource_state"))
    embodied = _dict_or_empty(_dict_or_empty(turn.get("interaction_carryover")).get("embodied_context"))

    rows: list[dict[str, Any]] = []
    for holder in (event_hints, perception_hints, session_hints, resource_state, embodied):
        single = holder.get("multimodal_source")
        if isinstance(single, dict):
            rows.append(single)
        for item in _list_or_empty(holder.get("multimodal_sources")):
            if isinstance(item, dict):
                rows.append(item)
    for item in _list_or_empty(current_event.get("perception_sources")):
        if isinstance(item, dict):
            row = dict(item)
            if "source_id" not in row and row.get("source_ref_id"):
                row["source_id"] = row.get("source_ref_id")
            rows.append(row)
    return rows


def normalize_embodied_interaction_sources(turn: dict[str, Any] | None) -> dict[str, Any]:
    data = _dict_or_empty(turn)
    available: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in _candidate_sources(data):
        source = normalize_multimodal_source(raw)
        source_ref = _source_ref(source)
        key = source_ref["source_ref_id"] or source_ref["payload_digest"]
        if not key or key in seen:
            continue
        seen.add(key)
        if source_ref["status"] == "available":
            available.append(source_ref)
        else:
            blocked.append(source_ref)
    return {
        "available_sources": available,
        "blocked_sources": blocked,
        "available_count": len(available),
        "blocked_count": len(blocked),
        "source_ref_ids": [item["source_ref_id"] for item in available if item.get("source_ref_id")],
    }


def _appraisal_evidence(artifact_appraisal: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(item)
        for item in list(artifact_appraisal.get("evidence_items") or [])
        if isinstance(item, dict)
    ]


def _motive_hints(artifact_motive: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(item)
        for item in list(artifact_motive.get("motive_hints") or [])
        if isinstance(item, dict)
    ]


def _has_alignment(artifact_behavior_alignment: dict[str, Any]) -> bool:
    return bool(list(artifact_behavior_alignment.get("alignment_items") or []))


def _current_event_patch(
    turn: dict[str, Any],
    sources: dict[str, Any],
    artifact_semantics: dict[str, Any],
    artifact_appraisal: dict[str, Any],
    artifact_motive: dict[str, Any],
    artifact_behavior_alignment: dict[str, Any],
) -> dict[str, Any]:
    current_event = _dict_or_empty(turn.get("current_event"))
    patch: dict[str, Any] = {"perception_sources": list(sources.get("available_sources") or [])}
    observations = list(artifact_semantics.get("semantic_observations") or [])
    evidence = _appraisal_evidence(artifact_appraisal)
    motive_hints = _motive_hints(artifact_motive)
    has_alignment = _has_alignment(artifact_behavior_alignment)
    if observations or evidence or motive_hints or has_alignment:
        perception = _dict_or_empty(current_event.get("perception"))
        if observations:
            perception["semantic_observations"] = observations
        if evidence:
            perception["appraisal_evidence"] = evidence
        if motive_hints:
            perception["motive_hints"] = motive_hints
        if has_alignment:
            perception["behavior_alignment"] = artifact_behavior_alignment
        patch["perception"] = perception
    return patch


def _turn_appraisal_patch(
    turn: dict[str, Any],
    artifact_semantics: dict[str, Any],
    artifact_appraisal: dict[str, Any],
    artifact_motive: dict[str, Any],
    artifact_behavior_alignment: dict[str, Any],
) -> dict[str, Any]:
    turn_appraisal = _dict_or_empty(turn.get("turn_appraisal"))
    observations = list(artifact_semantics.get("semantic_observations") or [])
    evidence = _appraisal_evidence(artifact_appraisal)
    motive_hints = _motive_hints(artifact_motive)
    has_alignment = _has_alignment(artifact_behavior_alignment)
    if observations:
        turn_appraisal["perception_semantics"] = {
            "status": _clean(artifact_semantics.get("status")) or "empty",
            "semantic_observations": observations,
            "model_api_called": bool(artifact_semantics.get("model_api_called", False)),
            "writeback_ready_count": int(artifact_semantics.get("writeback_ready_count") or 0),
        }
    if evidence:
        perception_semantics = _dict_or_empty(turn_appraisal.get("perception_semantics"))
        perception_semantics.setdefault("status", _clean(artifact_semantics.get("status")) or "empty")
        perception_semantics.setdefault("semantic_observations", observations)
        perception_semantics.setdefault(
            "model_api_called",
            bool(artifact_semantics.get("model_api_called", False)),
        )
        perception_semantics.setdefault(
            "writeback_ready_count",
            int(artifact_semantics.get("writeback_ready_count") or 0),
        )
        perception_semantics["appraisal_evidence"] = evidence
        turn_appraisal["perception_semantics"] = perception_semantics
        turn_appraisal["artifact_evidence"] = evidence
    if motive_hints:
        perception_semantics = _dict_or_empty(turn_appraisal.get("perception_semantics"))
        perception_semantics.setdefault("status", _clean(artifact_semantics.get("status")) or "empty")
        perception_semantics.setdefault("semantic_observations", observations)
        perception_semantics.setdefault(
            "model_api_called",
            bool(artifact_semantics.get("model_api_called", False)),
        )
        perception_semantics.setdefault(
            "writeback_ready_count",
            int(artifact_semantics.get("writeback_ready_count") or 0),
        )
        if evidence:
            perception_semantics.setdefault("appraisal_evidence", evidence)
        perception_semantics["motive_hints"] = motive_hints
        turn_appraisal["perception_semantics"] = perception_semantics
        turn_appraisal["motive_evidence"] = motive_hints
    if has_alignment:
        perception_semantics = _dict_or_empty(turn_appraisal.get("perception_semantics"))
        perception_semantics.setdefault("status", _clean(artifact_semantics.get("status")) or "empty")
        perception_semantics.setdefault("semantic_observations", observations)
        perception_semantics.setdefault(
            "model_api_called",
            bool(artifact_semantics.get("model_api_called", False)),
        )
        perception_semantics.setdefault(
            "writeback_ready_count",
            int(artifact_semantics.get("writeback_ready_count") or 0),
        )
        if evidence:
            perception_semantics.setdefault("appraisal_evidence", evidence)
        if motive_hints:
            perception_semantics.setdefault("motive_hints", motive_hints)
        perception_semantics["behavior_alignment"] = artifact_behavior_alignment
        turn_appraisal["perception_semantics"] = perception_semantics
        turn_appraisal["behavior_alignment_evidence"] = artifact_behavior_alignment
    return turn_appraisal


def _behavior_plan_patch(
    turn: dict[str, Any],
    artifact_motive: dict[str, Any],
    artifact_behavior_alignment: dict[str, Any],
) -> dict[str, Any]:
    behavior_plan = _dict_or_empty(turn.get("behavior_plan"))
    motive_hints = _motive_hints(artifact_motive)
    if motive_hints:
        behavior_plan["artifact_motive_hints"] = motive_hints
    if _has_alignment(artifact_behavior_alignment):
        behavior_plan["artifact_behavior_alignment"] = artifact_behavior_alignment
    return behavior_plan


def _digital_body_patch(turn: dict[str, Any], sources: dict[str, Any]) -> dict[str, Any]:
    digital_body = _dict_or_empty(turn.get("digital_body"))
    resource_state = _dict_or_empty(digital_body.get("resource_state"))
    refs = list(sources.get("source_ref_ids") or [])
    if refs:
        resource_state["multimodal_source_refs"] = refs
        first = (sources.get("available_sources") or [{}])[0]
        resource_state.setdefault("artifact_carrier", first.get("artifact_carrier") or "multimodal_source")
        resource_state.setdefault("active_artifact_kind", first.get("modality") or "")
        resource_state.setdefault("active_artifact_ref", first.get("artifact_ref") or "")
        resource_state.setdefault("active_artifact_label", first.get("artifact_label") or "")
        resource_state.setdefault("artifact_continuity", "attached")
    digital_body["resource_state"] = resource_state
    return digital_body


def _carryover_patch(
    turn: dict[str, Any],
    sources: dict[str, Any],
    artifact_semantics: dict[str, Any],
    artifact_appraisal: dict[str, Any],
    artifact_motive: dict[str, Any],
    artifact_behavior_alignment: dict[str, Any],
) -> dict[str, Any]:
    carryover = _dict_or_empty(turn.get("interaction_carryover"))
    embodied = _dict_or_empty(carryover.get("embodied_context"))
    available = list(sources.get("available_sources") or [])
    if available:
        embodied["multimodal_sources"] = available
        embodied.setdefault("kind", "multimodal_observation")
        embodied.setdefault("artifact_continuity", "attached")
        embodied.setdefault("artifact_carrier", available[0].get("artifact_carrier") or "multimodal_source")
    observations = list(artifact_semantics.get("semantic_observations") or [])
    if observations:
        embodied["artifact_semantic_observations"] = observations
        embodied.setdefault("kind", "artifact_semantic_observation")
        embodied.setdefault("artifact_continuity", "attached")
    evidence = _appraisal_evidence(artifact_appraisal)
    if evidence:
        embodied["artifact_appraisal_evidence"] = evidence
        embodied.setdefault("kind", "artifact_appraisal_evidence")
        embodied.setdefault("artifact_continuity", "attached")
    motive_hints = _motive_hints(artifact_motive)
    if motive_hints:
        embodied["artifact_motive_hints"] = motive_hints
        embodied.setdefault("kind", "artifact_motive_hints")
        embodied.setdefault("artifact_continuity", "attached")
    if _has_alignment(artifact_behavior_alignment):
        embodied["artifact_behavior_alignment"] = artifact_behavior_alignment
        embodied.setdefault("kind", "artifact_behavior_alignment")
        embodied.setdefault("artifact_continuity", "attached")
    carryover["embodied_context"] = embodied
    return carryover


def _semantic_runtime_floor(turn: dict[str, Any]) -> dict[str, Any]:
    final_text = _clean(turn.get("final_text"))
    runtime_policy = build_runtime_replacement_policy(final_text)
    result = rewrite_semantic_surface_floor(final_text)
    runtime_text = _clean(runtime_policy.get("runtime_final_text")) or _clean(result.get("safe_surface_floor")) or final_text
    tts_text = runtime_text
    return {
        "status": _clean(result.get("status")) or "no_semantic_residue",
        "families": list(result.get("families") or []),
        "applied_floor": bool(result.get("applied_floor", False)),
        "original_text": final_text,
        "runtime_final_text": runtime_text,
        "runtime_policy": runtime_policy,
        "tts_text": tts_text,
        "text_tts_drift": tts_text != runtime_text,
        "replacement_plan": _dict_or_empty(result.get("replacement_plan")),
    }


def build_embodied_interaction_readback(turn: dict[str, Any] | None) -> dict[str, Any]:
    data = _dict_or_empty(turn)
    sources = normalize_embodied_interaction_sources(data)
    artifact_semantics = build_artifact_semantics_readback(_candidate_sources(data))
    artifact_appraisal = build_artifact_appraisal_readback(artifact_semantics)
    artifact_motive = build_artifact_motive_readback(artifact_appraisal)
    artifact_behavior_alignment = build_artifact_behavior_alignment_readback(
        artifact_motive,
        data.get("behavior_action"),
        data.get("behavior_plan"),
    )
    semantic = _semantic_runtime_floor(data)
    available = int(sources.get("available_count") or 0)
    blocked = int(sources.get("blocked_count") or 0)
    semantic_applied = bool(semantic.get("applied_floor", False))
    artifact_semantics_ready = _clean(artifact_semantics.get("status")) == "ready"
    artifact_appraisal_ready = _clean(artifact_appraisal.get("status")) == "ready"
    artifact_motive_ready = _clean(artifact_motive.get("status")) == "ready"
    artifact_behavior_alignment_ready = _clean(artifact_behavior_alignment.get("status")) == "ready"
    if artifact_behavior_alignment_ready:
        overall = "passed"
        readiness = EMBODIED_INTERACTION_PHASE5_READINESS
    elif artifact_motive_ready:
        overall = "passed"
        readiness = EMBODIED_INTERACTION_PHASE4_READINESS
    elif artifact_appraisal_ready:
        overall = "passed"
        readiness = EMBODIED_INTERACTION_PHASE3_READINESS
    elif artifact_semantics_ready:
        overall = "passed"
        readiness = EMBODIED_INTERACTION_PHASE2_READINESS
    elif available > 0 and blocked == 0:
        overall = "passed"
        readiness = EMBODIED_INTERACTION_PHASE1_READINESS
    elif available > 0 and blocked > 0:
        overall = "in_progress"
        readiness = EMBODIED_INTERACTION_PHASE1_IN_PROGRESS
    elif blocked > 0:
        overall = "in_progress"
        readiness = EMBODIED_INTERACTION_PHASE1_IN_PROGRESS
    elif semantic_applied:
        overall = "passed"
        readiness = EMBODIED_INTERACTION_PHASE1_READINESS
    else:
        overall = "not_applicable"
        readiness = EMBODIED_INTERACTION_PHASE1_NOT_APPLICABLE

    runtime_text = _clean(semantic.get("runtime_final_text")) or _clean(data.get("final_text"))
    reconsolidation_snapshot = _dict_or_empty(data.get("reconsolidation_snapshot"))
    if runtime_text:
        reconsolidation_snapshot["final_text"] = runtime_text

    return {
        "phase": "Embodied Interaction Runtime Phase 4",
        "schema": "embodied_interaction.runtime.v1",
        "overall_status": overall,
        "readiness_status": readiness,
        "final_text": runtime_text,
        "current_event": _current_event_patch(
            data,
            sources,
            artifact_semantics,
            artifact_appraisal,
            artifact_motive,
            artifact_behavior_alignment,
        ),
        "turn_appraisal": _turn_appraisal_patch(
            data,
            artifact_semantics,
            artifact_appraisal,
            artifact_motive,
            artifact_behavior_alignment,
        ),
        "behavior_plan": _behavior_plan_patch(data, artifact_motive, artifact_behavior_alignment),
        "digital_body": _digital_body_patch(data, sources),
        "interaction_carryover": _carryover_patch(
            data,
            sources,
            artifact_semantics,
            artifact_appraisal,
            artifact_motive,
            artifact_behavior_alignment,
        ),
        "reconsolidation_snapshot": reconsolidation_snapshot,
        "source_status": sources,
        "artifact_semantics": artifact_semantics,
        "artifact_appraisal": artifact_appraisal,
        "artifact_motive": artifact_motive,
        "artifact_behavior_alignment": artifact_behavior_alignment,
        "chinese_semantic_surface": semantic,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "failure_reasons": [
            f"blocked_source:{item.get('source_ref_id')}" for item in sources.get("blocked_sources") or []
        ],
    }


def apply_embodied_interaction_readback_to_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    data = _dict_or_empty(payload)
    readback = build_embodied_interaction_readback(data)
    data["embodied_interaction"] = readback
    if readback.get("final_text"):
        data["final_text"] = str(readback.get("final_text") or "")
    if isinstance(readback.get("current_event"), dict):
        current_event = _dict_or_empty(data.get("current_event"))
        event_patch = _dict_or_empty(readback.get("current_event"))
        perception = _dict_or_empty(current_event.get("perception"))
        perception_patch = _dict_or_empty(event_patch.pop("perception", {}))
        if perception_patch:
            perception.update(perception_patch)
            current_event["perception"] = perception
        current_event.update(event_patch)
        data["current_event"] = current_event
    if isinstance(readback.get("turn_appraisal"), dict):
        turn_appraisal = _dict_or_empty(data.get("turn_appraisal"))
        turn_appraisal.update(readback["turn_appraisal"])
        data["turn_appraisal"] = turn_appraisal
    if isinstance(readback.get("behavior_plan"), dict):
        behavior_plan = _dict_or_empty(data.get("behavior_plan"))
        behavior_plan.update(readback["behavior_plan"])
        data["behavior_plan"] = behavior_plan
    if isinstance(readback.get("digital_body"), dict):
        data["digital_body"] = dict(readback["digital_body"])
    if isinstance(readback.get("interaction_carryover"), dict):
        data["interaction_carryover"] = dict(readback["interaction_carryover"])
    if isinstance(readback.get("reconsolidation_snapshot"), dict):
        data["reconsolidation_snapshot"] = dict(readback["reconsolidation_snapshot"])
    return data


def compact_embodied_interaction_line(readback: dict[str, Any] | None) -> str:
    data = _dict_or_empty(readback)
    if not data:
        return ""
    source_status = _dict_or_empty(data.get("source_status"))
    semantic = _dict_or_empty(data.get("chinese_semantic_surface"))
    boundary = _dict_or_empty(data.get("authority_boundary"))
    live_capture = any(
        bool(boundary.get(key, False))
        for key in ("live_microphone_enabled", "live_camera_enabled", "background_screen_capture_enabled")
    )
    parts = [
        f"embodied_interaction={_clean(data.get('readiness_status')) or 'unknown'}",
        f"sources={int(source_status.get('available_count') or 0)}",
        f"blocked={int(source_status.get('blocked_count') or 0)}",
        f"artifact_semantics={int(_dict_or_empty(data.get('artifact_semantics')).get('observation_count') or 0)}",
        f"artifact_appraisal={int(_dict_or_empty(data.get('artifact_appraisal')).get('evidence_count') or 0)}",
        f"artifact_motive={int(_dict_or_empty(data.get('artifact_motive')).get('hint_count') or 0)}",
        f"artifact_behavior_alignment={int(_dict_or_empty(data.get('artifact_behavior_alignment')).get('alignment_count') or 0)}",
        f"semantic_floor={_clean(semantic.get('status')) or 'unknown'}",
        f"live_capture={str(live_capture).lower()}",
    ]
    return " | ".join(parts)


__all__ = [
    "AUTHORITY_BOUNDARY",
    "EMBODIED_INTERACTION_PHASE1_IN_PROGRESS",
    "EMBODIED_INTERACTION_PHASE1_NOT_APPLICABLE",
    "EMBODIED_INTERACTION_PHASE1_READINESS",
    "EMBODIED_INTERACTION_PHASE2_IN_PROGRESS",
    "EMBODIED_INTERACTION_PHASE2_READINESS",
    "EMBODIED_INTERACTION_PHASE3_IN_PROGRESS",
    "EMBODIED_INTERACTION_PHASE3_READINESS",
    "EMBODIED_INTERACTION_PHASE4_IN_PROGRESS",
    "EMBODIED_INTERACTION_PHASE4_READINESS",
    "EMBODIED_INTERACTION_PHASE5_IN_PROGRESS",
    "EMBODIED_INTERACTION_PHASE5_READINESS",
    "apply_embodied_interaction_readback_to_payload",
    "build_embodied_interaction_readback",
    "compact_embodied_interaction_line",
    "normalize_embodied_interaction_sources",
]
