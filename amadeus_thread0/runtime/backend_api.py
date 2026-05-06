from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ..graph_parts.digital_body_runtime import derive_digital_body_state
from ..graph_parts.procedural_planning import normalize_procedural_planning
from ..graph_parts.skill_runtime import backend_skill_envelope
from ..utils.memory_history_export import normalize_memory_history_export
from ..utils.relational_history_export import (
    normalize_counterpart_assessment_export,
    normalize_proactive_continuity_export,
)
from ..utils.revision_trace_export import normalize_revision_trace_export
from ..utils.runtime_audit import audit_runtime_layout
from ..utils.source_material_export import normalize_claim_link_exports, normalize_source_material_exports
from ..utils.turn_summary_export import (
    summarize_procedural_growth,
    summarize_procedural_outcome,
    summarize_procedural_recovery,
)
from .access_negotiation import attach_assist_request_to_pending_approval, resolve_access_negotiation_context
from .event_identity import resolve_readback_current_event, resolve_readback_session_context
from .final_state import (
    resolve_agenda_lifecycle_residue,
    resolve_action_packets,
    resolve_action_trace,
    resolve_autonomy_block_reason,
    resolve_autonomy_intent,
    resolve_behavior_payloads,
    resolve_counterpart_assessment,
    resolve_digital_body_consequence,
    resolve_digital_body_state,
    resolve_interaction_carryover,
    resolve_pending_action_proposal,
)
from .embodied_interaction_runtime import apply_embodied_interaction_readback_to_payload
from .living_loop_realism import build_backend_payload_realism_readback
from .post_baseline_closure import evaluate_post_baseline_status
from .runtime_productization import build_runtime_productization_readback
from .thread_runtime import list_threads


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _emotion_label_from_state(values: dict[str, Any] | None, *, default: str = "neutral") -> str:
    data = values if isinstance(values, dict) else {}
    emotion_state = data.get("emotion_state") if isinstance(data.get("emotion_state"), dict) else {}
    label = str((emotion_state or {}).get("label") or "").strip()
    return label or str(default or "neutral")


def _resolved_behavior_payloads(values: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    data = values if isinstance(values, dict) else {}
    return resolve_behavior_payloads(
        behavior_action=_dict_or_empty(data.get("behavior_action")),
        behavior_plan=_dict_or_empty(data.get("behavior_plan")),
        reconsolidation_snapshot=_dict_or_empty(data.get("reconsolidation_snapshot")),
        current_event=_dict_or_empty(data.get("current_event")),
        world_model_state=_dict_or_empty(data.get("world_model_state")),
    )


def _resolved_interaction_carryover(values: dict[str, Any] | None) -> dict[str, Any]:
    data = values if isinstance(values, dict) else {}
    return resolve_interaction_carryover(
        interaction_carryover=_dict_or_empty(data.get("interaction_carryover")),
        reconsolidation_snapshot=_dict_or_empty(data.get("reconsolidation_snapshot")),
    )


def _resolved_counterpart_assessment(values: dict[str, Any] | None) -> dict[str, Any]:
    data = values if isinstance(values, dict) else {}
    return resolve_counterpart_assessment(
        counterpart_assessment=_dict_or_empty(data.get("counterpart_assessment")),
        reconsolidation_snapshot=_dict_or_empty(data.get("reconsolidation_snapshot")),
    )


def _resolved_agenda_lifecycle_residue(values: dict[str, Any] | None) -> dict[str, Any]:
    data = values if isinstance(values, dict) else {}
    return resolve_agenda_lifecycle_residue(
        agenda_lifecycle_residue=_dict_or_empty(data.get("agenda_lifecycle_residue")),
        reconsolidation_snapshot=_dict_or_empty(data.get("reconsolidation_snapshot")),
    )


def _resolved_autonomy(values: dict[str, Any] | None) -> dict[str, Any]:
    data = values if isinstance(values, dict) else {}
    reconsolidation_snapshot = _dict_or_empty(data.get("reconsolidation_snapshot"))
    digital_body = resolve_digital_body_state(
        digital_body_state=_dict_or_empty(data.get("digital_body_state")),
        reconsolidation_snapshot=reconsolidation_snapshot,
    )
    action_packets = resolve_action_packets(
        action_packets=data.get("action_packets"),
        reconsolidation_snapshot=reconsolidation_snapshot,
    )
    pending_approval = resolve_pending_action_proposal(
        pending_action_proposal=_dict_or_empty(data.get("pending_action_proposal")),
        action_packets=action_packets,
        reconsolidation_snapshot=reconsolidation_snapshot,
    )
    negotiation = resolve_access_negotiation_context(
        data,
        pending_action_proposal=pending_approval,
        action_packets=action_packets,
        reconsolidation_snapshot=reconsolidation_snapshot,
        digital_body_state=digital_body,
    )
    action_trace = resolve_action_trace(
        action_trace=data.get("action_trace"),
        reconsolidation_snapshot=reconsolidation_snapshot,
    )
    procedural_planning = normalize_procedural_planning(data.get("procedural_planning"))
    if not procedural_planning:
        for item in action_trace:
            if not isinstance(item, dict):
                continue
            procedural_planning = normalize_procedural_planning(item.get("procedural_planning"))
            if procedural_planning:
                break
    return {
        "intent": resolve_autonomy_intent(
            autonomy_intent=_dict_or_empty(data.get("autonomy_intent")),
            reconsolidation_snapshot=reconsolidation_snapshot,
            action_packets=action_packets,
            current_event=_dict_or_empty(data.get("current_event")),
            autonomy_block_reason=str(data.get("autonomy_block_reason") or ""),
        ),
        "action_packets": action_packets,
        "pending_approval": attach_assist_request_to_pending_approval(
            pending_approval,
            assist_request=negotiation.get("assist_request") if isinstance(negotiation, dict) else None,
            source_packet=negotiation.get("packet") if isinstance(negotiation, dict) else None,
        ),
        "execution_trace": action_trace,
        "block_reason": resolve_autonomy_block_reason(
            autonomy_block_reason=str(data.get("autonomy_block_reason") or ""),
            action_packets=action_packets,
            reconsolidation_snapshot=reconsolidation_snapshot,
        ),
        "procedural_planning": procedural_planning,
    }


def _resolved_digital_body(values: dict[str, Any] | None) -> dict[str, Any]:
    data = values if isinstance(values, dict) else {}
    body = resolve_digital_body_state(
        digital_body_state=_dict_or_empty(data.get("digital_body_state")),
        reconsolidation_snapshot=_dict_or_empty(data.get("reconsolidation_snapshot")),
    )
    if body:
        return body
    return derive_digital_body_state(
        current_event=_dict_or_empty(data.get("current_event")),
        behavior_queue=data.get("behavior_queue") if isinstance(data.get("behavior_queue"), list) else data.get("behavior_agenda"),
        action_packets=data.get("action_packets"),
        interaction_carryover=_dict_or_empty(data.get("interaction_carryover")),
        toolset_unlocks=_dict_or_empty(data.get("toolset_unlocks")),
        autonomy_block_reason=str(data.get("autonomy_block_reason") or ""),
        session_context=_dict_or_empty(data.get("session_context")),
        last_external_tools=data.get("last_external_tools"),
    )


def _resolved_digital_body_consequence(
    values: dict[str, Any] | None,
    *,
    digital_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = values if isinstance(values, dict) else {}
    reconsolidation_snapshot = _dict_or_empty(data.get("reconsolidation_snapshot"))
    resolved_body = digital_body if isinstance(digital_body, dict) and digital_body else _resolved_digital_body(data)
    action_packets = resolve_action_packets(
        action_packets=data.get("action_packets"),
        reconsolidation_snapshot=reconsolidation_snapshot,
    )
    return resolve_digital_body_consequence(
        digital_body_consequence=_dict_or_empty(data.get("digital_body_consequence")),
        digital_body_state=resolved_body,
        action_packets=action_packets,
        reconsolidation_snapshot=reconsolidation_snapshot,
        session_skill_state=_dict_or_empty(data.get("session_skill_state")),
    )


def _internal_state_trace(values: dict[str, Any] | None) -> dict[str, Any]:
    data = values if isinstance(values, dict) else {}
    return {
        "emotion_state": _dict_or_empty(data.get("emotion_state")),
        "bond_state": _dict_or_empty(data.get("bond_state")),
        "allostasis_state": _dict_or_empty(data.get("allostasis_state")),
        "semantic_narrative_profile": _dict_or_empty(data.get("semantic_narrative_profile")),
        "world_model_state": _dict_or_empty(data.get("world_model_state")),
        "evolution_state": _dict_or_empty(data.get("evolution_state")),
    }


def _summary_state_values(
    values: dict[str, Any] | None,
    *,
    behavior_action: dict[str, Any],
    behavior_plan: dict[str, Any],
    interaction_carryover: dict[str, Any],
    counterpart_assessment: dict[str, Any],
    agenda_lifecycle_residue: dict[str, Any],
    autonomy: dict[str, Any],
    digital_body: dict[str, Any],
    digital_body_consequence: dict[str, Any],
) -> dict[str, Any]:
    summary_values = dict(values) if isinstance(values, dict) else {}
    summary_values.update(
        {
            "behavior_action": dict(behavior_action or {}),
            "behavior_plan": dict(behavior_plan or {}),
            "interaction_carryover": dict(interaction_carryover or {}),
            "counterpart_assessment": dict(counterpart_assessment or {}),
            "agenda_lifecycle_residue": dict(agenda_lifecycle_residue or {}),
            "digital_body_state": dict(digital_body or {}),
            "digital_body_consequence": dict(digital_body_consequence or {}),
            "autonomy_intent": dict((autonomy or {}).get("intent") or {}),
            "pending_action_proposal": dict((autonomy or {}).get("pending_approval") or {}),
            "action_trace": list((autonomy or {}).get("execution_trace") or []),
            "autonomy_block_reason": str((autonomy or {}).get("block_reason") or ""),
            "procedural_planning": dict((autonomy or {}).get("procedural_planning") or {}),
        }
    )
    if "action_packets" not in summary_values and isinstance((autonomy or {}).get("action_packets"), list):
        summary_values["action_packets"] = list((autonomy or {}).get("action_packets") or [])
    return summary_values


def _summary_with_procedural_readback(summary: Any, *, digital_body_consequence: Any) -> dict[str, Any]:
    enriched = dict(summary) if isinstance(summary, dict) else {}
    outcome = summarize_procedural_outcome(digital_body_consequence)
    recovery = summarize_procedural_recovery(digital_body_consequence)
    if not bool(outcome.get("procedural_outcome", False)) and not bool(recovery.get("procedural_recovery", False)):
        return enriched
    current_turn = dict(enriched.get("current_turn") or {}) if isinstance(enriched.get("current_turn"), dict) else {}
    if bool(outcome.get("procedural_outcome", False)):
        enriched["procedural_outcome"] = outcome
        outcomes = outcome.get("outcomes") if isinstance(outcome.get("outcomes"), list) else []
        latest = outcomes[-1] if outcomes and isinstance(outcomes[-1], dict) else {}
        if latest:
            current_turn["procedural_outcome"] = {
                "outcome_id": str(latest.get("outcome_id") or "").strip(),
                "outcome_kind": str(latest.get("outcome_kind") or "").strip(),
                "source_trace_id": str(latest.get("source_trace_id") or "").strip(),
                "source_run_id": str(latest.get("source_run_id") or "").strip(),
                "planning_bias_kind": str(latest.get("planning_bias_kind") or "").strip(),
                "confidence_delta": float(latest.get("confidence_delta") or 0.0),
                "reuse_allowed": bool(latest.get("reuse_allowed", False)),
                "boundary_reinforced": bool(latest.get("boundary_reinforced", False)),
            }
    if bool(recovery.get("procedural_recovery", False)):
        enriched["procedural_recovery"] = recovery
        recoveries = recovery.get("recoveries") if isinstance(recovery.get("recoveries"), list) else []
        latest_recovery = recoveries[-1] if recoveries and isinstance(recoveries[-1], dict) else {}
        if latest_recovery:
            current_turn["procedural_recovery"] = {
                "recovery_id": str(latest_recovery.get("recovery_id") or "").strip(),
                "recovery_kind": str(latest_recovery.get("recovery_kind") or "").strip(),
                "source_outcome_id": str(latest_recovery.get("source_outcome_id") or "").strip(),
                "source_trace_id": str(latest_recovery.get("source_trace_id") or "").strip(),
                "source_run_id": str(latest_recovery.get("source_run_id") or "").strip(),
                "safe_to_reuse": bool(latest_recovery.get("safe_to_reuse", False)),
                "requires_approval": bool(latest_recovery.get("requires_approval", False)),
                "allowed_bias_kind": str(latest_recovery.get("allowed_bias_kind") or "").strip(),
            }
    enriched["current_turn"] = current_turn
    return enriched


def _default_preserved_baselines_status() -> dict[str, Any]:
    return {"overall_status": "passed", "readiness_status": "preserved_baselines_ready"}


def _default_post_unlock_roadmap_status() -> dict[str, Any]:
    return {"overall_status": "passed", "readiness_status": "post_unlock_roadmap_ready"}


def _record_field(record: dict[str, Any] | None, key: str, default: Any = "") -> Any:
    item = record if isinstance(record, dict) else {}
    if key in item:
        return item.get(key, default)
    content = item.get("content") if isinstance(item.get("content"), dict) else {}
    return content.get(key, default)


def _recent_record_ts(record: dict[str, Any] | None) -> int:
    item = record if isinstance(record, dict) else {}
    for key in ("updated_at", "created_at", "timestamp", "retrieved_at"):
        try:
            value = int(item.get(key) or 0)
        except Exception:
            value = 0
        if value > 0:
            return value
    return 0


def _writeback_anchor_ts(values: dict[str, Any] | None) -> int:
    data = values if isinstance(values, dict) else {}
    session_context = _dict_or_empty(data.get("session_context"))
    try:
        turn_started_at = int(session_context.get("turn_started_at") or 0)
    except Exception:
        turn_started_at = 0
    if turn_started_at > 0:
        return turn_started_at
    current_event = _dict_or_empty(data.get("current_event"))
    try:
        return int(current_event.get("created_at") or 0)
    except Exception:
        return 0


def _current_turn_history_slice(
    store: Any,
    method_name: str,
    *,
    anchor_ts: int,
    limit: int,
    max_items: int,
    normalizer: Callable[[Any], dict[str, Any]] = normalize_memory_history_export,
) -> list[dict[str, Any]]:
    if store is None or not hasattr(store, method_name):
        return []
    items: list[dict[str, Any]] = []
    for item in list(getattr(store, method_name)(limit=limit) or []):
        if not isinstance(item, dict):
            continue
        item_ts = _recent_record_ts(item)
        if anchor_ts > 0:
            if item_ts <= 0:
                continue
            if item_ts < anchor_ts:
                continue
        normalized = normalizer(item)
        if not normalized:
            continue
        items.append(normalized)
        if len(items) >= max_items:
            break
    return items


def _writeback_trace_payload(backend_session: Any, values: dict[str, Any] | None) -> dict[str, Any]:
    data = values if isinstance(values, dict) else {}
    anchor_ts = _writeback_anchor_ts(data)
    store = getattr(backend_session, "memory_store", None)
    explicit_trace = _dict_or_empty(data.get("writeback_trace"))
    if explicit_trace and store is None:
        trace = dict(explicit_trace)
        trace.setdefault("turn_started_at", anchor_ts)
        return trace
    if store is None or not all(hasattr(store, attr) for attr in ("list_revision_traces", "list_semantic_self_narratives")):
        return {
            "turn_started_at": anchor_ts,
            "semantic_self_narratives": [],
            "revision_traces": [],
            "counterpart_assessment_history": [],
            "proactive_continuity_history": [],
        }

    final_source = "auto:passive_evolution_final"
    traces: list[dict[str, Any]] = []
    for item in list(getattr(store, "list_revision_traces")(limit=60) or []):
        if not isinstance(item, dict):
            continue
        item_source = str(_record_field(item, "source", "") or "").strip()
        if item_source != final_source:
            continue
        item_ts = _recent_record_ts(item)
        if anchor_ts > 0 and item_ts <= 0:
            continue
        if anchor_ts > 0 and item_ts < anchor_ts:
            continue
        traces.append(normalize_revision_trace_export(item))
        if len(traces) >= 12:
            break

    touched_categories = {
        str(_record_field(item, "target_id", "") or "").strip()
        for item in traces
        if str(_record_field(item, "namespace", "") or "").strip() == "semantic_self_evidence"
        and str(_record_field(item, "target_id", "") or "").strip()
    }
    touched_narrative_ids = {
        str(_record_field(item, "target_id", "") or "").strip()
        for item in traces
        if str(_record_field(item, "namespace", "") or "").strip() == "semantic_self_narratives"
        and str(_record_field(item, "target_id", "") or "").strip()
    }

    narratives: list[dict[str, Any]] = []
    for item in list(getattr(store, "list_semantic_self_narratives")(limit=20) or []):
        if not isinstance(item, dict):
            continue
        item_ts = _recent_record_ts(item)
        category = str(_record_field(item, "category", "") or "").strip()
        item_id = str(item.get("id") or "").strip()
        if anchor_ts > 0 and item_ts > 0 and item_ts >= anchor_ts:
            narratives.append(dict(item))
        elif category and category in touched_categories:
            narratives.append(dict(item))
        elif item_id and item_id in touched_narrative_ids:
            narratives.append(dict(item))
        if len(narratives) >= 8:
            break

    counterpart_history = _current_turn_history_slice(
        store,
        "list_counterpart_assessment_history",
        anchor_ts=anchor_ts,
        limit=12,
        max_items=6,
        normalizer=normalize_counterpart_assessment_export,
    )
    proactive_history = _current_turn_history_slice(
        store,
        "list_proactive_continuity_history",
        anchor_ts=anchor_ts,
        limit=12,
        max_items=6,
        normalizer=normalize_proactive_continuity_export,
    )

    return {
        "turn_started_at": anchor_ts,
        "semantic_self_narratives": narratives,
        "revision_traces": traces,
        "counterpart_assessment_history": counterpart_history,
        "proactive_continuity_history": proactive_history,
    }

@dataclass(frozen=True)
class BackendApiEnvelope:
    kind: str
    thread_id: str
    payload: dict[str, Any]
    generated_at: int = field(default_factory=lambda: int(time.time()))
    schema_version: str = "backend.v1"
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": int(self.generated_at),
            "kind": self.kind,
            "thread_id": self.thread_id,
            "payload": dict(self.payload),
            "meta": dict(self.meta),
        }


@dataclass
class BackendAPI:
    runtime_bundle: Any
    base_data_dir: Path
    cwd: Path | None = None

    @property
    def thread_id(self) -> str:
        return str(getattr(self.runtime_bundle, "thread_id", "") or "")

    @property
    def backend_session(self) -> Any:
        return getattr(self.runtime_bundle, "backend_session")

    @property
    def memory_admin(self) -> Any:
        return getattr(self.runtime_bundle, "memory_admin")

    @property
    def settings(self) -> Any:
        return getattr(self.runtime_bundle, "settings")

    def _envelope(
        self,
        kind: str,
        payload: dict[str, Any],
        *,
        meta: dict[str, Any] | None = None,
    ) -> BackendApiEnvelope:
        return BackendApiEnvelope(
            kind=kind,
            thread_id=self.thread_id,
            payload=dict(payload),
            meta=dict(meta or {}),
        )

    def memory_snapshot(self) -> BackendApiEnvelope:
        return self._envelope("memory_snapshot", self.memory_admin.snapshot_view())

    def worldline(self) -> BackendApiEnvelope:
        return self._envelope("worldline_view", self.backend_session.worldline_view())

    def bond(self) -> BackendApiEnvelope:
        return self._envelope("bond_view", self.backend_session.bond_view())

    def sources(self) -> BackendApiEnvelope:
        return self._envelope("sources_view", self.backend_session.sources_view())

    def persona(self) -> BackendApiEnvelope:
        return self._envelope("persona_view", self.backend_session.persona_view())

    def appraisal(self) -> BackendApiEnvelope:
        return self._envelope("appraisal_view", {"turn_appraisal": self.backend_session.appraisal_view()})

    def behavior_queue(self, *, config: dict[str, Any] | None = None) -> BackendApiEnvelope:
        return self._envelope("behavior_queue_view", self.backend_session.behavior_queue_view(config=config))

    def runtime_productization(self) -> BackendApiEnvelope:
        return self._envelope(
            "runtime_productization",
            self._runtime_productization_payload(current_turn={}),
        )

    def checkpoint_history(
        self,
        *,
        limit: int = 10,
        config: dict[str, Any] | None = None,
    ) -> BackendApiEnvelope:
        return self._envelope(
            "checkpoint_history",
            self.backend_session.checkpoint_history_view(limit=limit, config=config),
        )

    def current_checkpoint(self, *, config: dict[str, Any] | None = None) -> BackendApiEnvelope:
        return self._envelope("current_checkpoint", self.backend_session.current_checkpoint_view(config=config))

    def thread_inventory(self) -> BackendApiEnvelope:
        inventory = list_threads(
            base_data_dir=self.base_data_dir,
            checkpoint_db_path=self.settings.checkpoint_db_path,
        )
        return self._envelope(
            "thread_inventory",
            {
                "checkpoint_thread_ids": inventory.checkpoint_thread_ids,
                "worldline_dir_ids": inventory.worldline_dir_ids,
                "current_thread_id": self.thread_id,
            },
        )

    def runtime_layout(self) -> BackendApiEnvelope:
        repo_runtime = audit_runtime_layout(self.base_data_dir)
        current_runtime = None
        try:
            if Path(self.settings.data_dir).resolve() != Path(self.base_data_dir).resolve():
                current_runtime = audit_runtime_layout(self.settings.data_dir)
        except Exception:
            current_runtime = None
        return self._envelope(
            "runtime_layout",
            {
                "repo_runtime": repo_runtime,
                "current_runtime": current_runtime,
            },
        )

    def environment_summary(
        self,
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> BackendApiEnvelope:
        current_env = dict(env or os.environ)
        current_cwd = Path(cwd or self.cwd or Path.cwd())
        base_url = str(self.settings.model_base_url) if str(self.settings.model_base_url).strip() else "(default)"
        payload = {
            "cwd": str(current_cwd),
            "model_provider": str(self.settings.model_provider),
            "model_name": str(self.settings.model_name),
            "model_base_url": base_url,
            "runtime_mode": str(self.settings.runtime_mode),
            "eval_mode": str(current_env.get("AMADEUS_EVAL_MODE", "0")),
            "user_facing_mode": str(current_env.get("AMADEUS_USER_FACING_MODE", "1")),
            "cli_show_turn_summary": str(current_env.get("AMADEUS_CLI_SHOW_TURN_SUMMARY", "0")),
            "tts_enabled": str(current_env.get("AMADEUS_TTS_ENABLED")),
            "tts_backend": str(current_env.get("AMADEUS_TTS_BACKEND")),
            "tts_ref_audio": str(current_env.get("AMADEUS_TTS_REF_AUDIO")),
            "tts_model": str(current_env.get("AMADEUS_TTS_DASHSCOPE_MODEL")),
            "dashscope_api_key_set": bool(str(current_env.get("DASHSCOPE_API_KEY") or "").strip()),
        }
        return self._envelope("environment_summary", payload)

    def _runtime_productization_payload(self, *, current_turn: dict[str, Any] | None = None) -> dict[str, Any]:
        return build_runtime_productization_readback(
            post_baseline_status=evaluate_post_baseline_status(
                post_unlock_roadmap=_default_post_unlock_roadmap_status()
            ),
            preserved_baselines=_default_preserved_baselines_status(),
            post_unlock_roadmap=_default_post_unlock_roadmap_status(),
            current_turn=current_turn,
        )

    def build_event_round_response(
        self,
        *,
        state_values: dict[str, Any] | None,
        final_text: str,
        meta: dict[str, Any] | None = None,
    ) -> BackendApiEnvelope:
        values = state_values if isinstance(state_values, dict) else {}
        raw_session_context = _dict_or_empty(values.get("session_context"))
        current_event = resolve_readback_current_event(values, thread_id=self.thread_id, session_context=raw_session_context)
        behavior_action, behavior_plan = _resolved_behavior_payloads(values)
        interaction_carryover = _resolved_interaction_carryover(values)
        counterpart_assessment = _resolved_counterpart_assessment(values)
        agenda_lifecycle_residue = _resolved_agenda_lifecycle_residue(values)
        autonomy = _resolved_autonomy(values)
        skills = backend_skill_envelope(
            values.get("session_skill_state"),
            pending_action_proposal=_dict_or_empty(values.get("pending_action_proposal")),
        )
        digital_body = _resolved_digital_body(values)
        digital_body_consequence = _resolved_digital_body_consequence(values, digital_body=digital_body)
        internal_state = _internal_state_trace(values)
        writeback_trace = _writeback_trace_payload(self.backend_session, values)
        summary_values = _summary_state_values(
            values,
            behavior_action=behavior_action,
            behavior_plan=behavior_plan,
            interaction_carryover=interaction_carryover,
            counterpart_assessment=counterpart_assessment,
            agenda_lifecycle_residue=agenda_lifecycle_residue,
            autonomy=autonomy,
            digital_body=digital_body,
            digital_body_consequence=digital_body_consequence,
        )
        turn_summary = _summary_with_procedural_readback(
            self.backend_session.build_evolution_summary(state_values=summary_values),
            digital_body_consequence=digital_body_consequence,
        )
        current_turn = turn_summary.get("current_turn") if isinstance(turn_summary.get("current_turn"), dict) else {}
        operator_readback = self._runtime_productization_payload(current_turn=current_turn)
        payload = {
            "final_text": str(final_text or "").strip(),
            "emotion_label": _emotion_label_from_state(values),
            "behavior_action": behavior_action,
            "behavior_plan": behavior_plan,
            "interaction_carryover": interaction_carryover,
            "counterpart_assessment": counterpart_assessment,
            "agenda_lifecycle_residue": agenda_lifecycle_residue,
            "reconsolidation_snapshot": _dict_or_empty(values.get("reconsolidation_snapshot")),
            "current_event": current_event,
            "session_context": resolve_readback_session_context(values, thread_id=self.thread_id, current_event=current_event),
            "turn_appraisal": _dict_or_empty(values.get("turn_appraisal")),
            "turn_summary": turn_summary,
            "autonomy": autonomy,
            "skills": skills,
            "digital_body": digital_body,
            "digital_body_consequence": digital_body_consequence,
            "procedural_growth": summarize_procedural_growth(digital_body_consequence),
            "procedural_outcome": summarize_procedural_outcome(digital_body_consequence),
            "procedural_recovery": summarize_procedural_recovery(digital_body_consequence),
            "operator_readback": operator_readback,
            "writeback_trace": writeback_trace,
            **internal_state,
        }
        payload = apply_embodied_interaction_readback_to_payload(payload)
        payload["living_loop_realism"] = build_backend_payload_realism_readback(payload)
        return self._envelope("event_round", payload, meta=meta)

    def build_turn_response(
        self,
        *,
        state_values: dict[str, Any] | None,
        streamed_text: str = "",
        meta: dict[str, Any] | None = None,
    ) -> BackendApiEnvelope:
        values = state_values if isinstance(state_values, dict) else {}
        final_text = self.backend_session.extract_final_text(values, streamed_text=streamed_text)
        raw_session_context = _dict_or_empty(values.get("session_context"))
        current_event = resolve_readback_current_event(values, thread_id=self.thread_id, session_context=raw_session_context)
        behavior_action, behavior_plan = _resolved_behavior_payloads(values)
        interaction_carryover = _resolved_interaction_carryover(values)
        counterpart_assessment = _resolved_counterpart_assessment(values)
        agenda_lifecycle_residue = _resolved_agenda_lifecycle_residue(values)
        autonomy = _resolved_autonomy(values)
        skills = backend_skill_envelope(
            values.get("session_skill_state"),
            pending_action_proposal=_dict_or_empty(values.get("pending_action_proposal")),
        )
        digital_body = _resolved_digital_body(values)
        digital_body_consequence = _resolved_digital_body_consequence(values, digital_body=digital_body)
        internal_state = _internal_state_trace(values)
        writeback_trace = _writeback_trace_payload(self.backend_session, values)
        sources = normalize_source_material_exports(values.get("evidence_pack"))
        summary_values = _summary_state_values(
            values,
            behavior_action=behavior_action,
            behavior_plan=behavior_plan,
            interaction_carryover=interaction_carryover,
            counterpart_assessment=counterpart_assessment,
            agenda_lifecycle_residue=agenda_lifecycle_residue,
            autonomy=autonomy,
            digital_body=digital_body,
            digital_body_consequence=digital_body_consequence,
        )
        turn_summary = _summary_with_procedural_readback(
            self.backend_session.build_evolution_summary(state_values=summary_values),
            digital_body_consequence=digital_body_consequence,
        )
        current_turn = turn_summary.get("current_turn") if isinstance(turn_summary.get("current_turn"), dict) else {}
        operator_readback = self._runtime_productization_payload(current_turn=current_turn)
        payload = {
            "final_text": final_text,
            "emotion_label": _emotion_label_from_state(values),
            "turn_summary": turn_summary,
            "behavior_action": behavior_action,
            "behavior_plan": behavior_plan,
            "interaction_carryover": interaction_carryover,
            "counterpart_assessment": counterpart_assessment,
            "agenda_lifecycle_residue": agenda_lifecycle_residue,
            "reconsolidation_snapshot": _dict_or_empty(values.get("reconsolidation_snapshot")),
            "current_event": current_event,
            "session_context": resolve_readback_session_context(values, thread_id=self.thread_id, current_event=current_event),
            "turn_appraisal": _dict_or_empty(values.get("turn_appraisal")),
            "claim_links": normalize_claim_link_exports(values.get("claim_links"), source_rows=sources),
            "sources": sources,
            "pending_utterance_fragment": str(values.get("pending_utterance_fragment") or "").strip(),
            "autonomy": autonomy,
            "skills": skills,
            "digital_body": digital_body,
            "digital_body_consequence": digital_body_consequence,
            "procedural_growth": summarize_procedural_growth(digital_body_consequence),
            "procedural_outcome": summarize_procedural_outcome(digital_body_consequence),
            "procedural_recovery": summarize_procedural_recovery(digital_body_consequence),
            "operator_readback": operator_readback,
            "writeback_trace": writeback_trace,
            **internal_state,
        }
        payload = apply_embodied_interaction_readback_to_payload(payload)
        payload["living_loop_realism"] = build_backend_payload_realism_readback(payload)
        return self._envelope("assistant_turn", payload, meta=meta)


__all__ = ["BackendAPI", "BackendApiEnvelope"]
