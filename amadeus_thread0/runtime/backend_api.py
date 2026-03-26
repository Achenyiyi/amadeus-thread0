from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..utils.runtime_audit import audit_runtime_layout
from .event_identity import resolve_readback_current_event, resolve_readback_session_context
from .final_state import (
    resolve_agenda_lifecycle_residue,
    resolve_behavior_payloads,
    resolve_counterpart_assessment,
    resolve_interaction_carryover,
)
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
        items.append(dict(item))
        if len(items) >= max_items:
            break
    return items


def _writeback_trace_payload(backend_session: Any, values: dict[str, Any] | None) -> dict[str, Any]:
    data = values if isinstance(values, dict) else {}
    anchor_ts = _writeback_anchor_ts(data)
    store = getattr(backend_session, "memory_store", None)
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
        traces.append(dict(item))
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
    )
    proactive_history = _current_turn_history_slice(
        store,
        "list_proactive_continuity_history",
        anchor_ts=anchor_ts,
        limit=12,
        max_items=6,
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
        internal_state = _internal_state_trace(values)
        writeback_trace = _writeback_trace_payload(self.backend_session, values)
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
            "turn_summary": self.backend_session.build_evolution_summary(state_values=values),
            "writeback_trace": writeback_trace,
            **internal_state,
        }
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
        internal_state = _internal_state_trace(values)
        writeback_trace = _writeback_trace_payload(self.backend_session, values)
        payload = {
            "final_text": final_text,
            "emotion_label": _emotion_label_from_state(values),
            "turn_summary": self.backend_session.build_evolution_summary(state_values=values),
            "behavior_action": behavior_action,
            "behavior_plan": behavior_plan,
            "interaction_carryover": interaction_carryover,
            "counterpart_assessment": counterpart_assessment,
            "agenda_lifecycle_residue": agenda_lifecycle_residue,
            "reconsolidation_snapshot": _dict_or_empty(values.get("reconsolidation_snapshot")),
            "current_event": current_event,
            "session_context": resolve_readback_session_context(values, thread_id=self.thread_id, current_event=current_event),
            "turn_appraisal": _dict_or_empty(values.get("turn_appraisal")),
            "claim_links": _list_or_empty(values.get("claim_links")),
            "sources": _list_or_empty(values.get("evidence_pack")),
            "pending_utterance_fragment": str(values.get("pending_utterance_fragment") or "").strip(),
            "writeback_trace": writeback_trace,
            **internal_state,
        }
        return self._envelope("assistant_turn", payload, meta=meta)


__all__ = ["BackendAPI", "BackendApiEnvelope"]
