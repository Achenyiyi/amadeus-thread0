from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from langgraph.types import Command

from ..graph_parts import build_implicit_idle_event_override, build_implicit_idle_state_update
from ..graph_parts.relational_runtime import _prefer_refreshed_relationship_state
from ..memory_store import MemoryStore
from ..utils.cli_views import build_behavior_queue_cli_summary, build_evolution_cli_summary
from .final_state import resolve_behavior_payloads, resolve_behavior_queue


def _coerce_values(snapshot: Any) -> dict[str, Any]:
    values = getattr(snapshot, "values", {}) if snapshot is not None else {}
    return dict(values) if isinstance(values, dict) else {}


def _thread_id_from_config(config: dict[str, Any] | None, fallback: str) -> str:
    configurable = (config or {}).get("configurable") if isinstance(config, dict) else {}
    thread_id = str((configurable or {}).get("thread_id") or fallback).strip()
    return thread_id or fallback


def _message_content(message: Any) -> str:
    return str(getattr(message, "content", "") or "").strip()


def _payload_value(interrupt_payload: Any) -> dict[str, Any]:
    payload = getattr(interrupt_payload, "value", None)
    if payload is None and isinstance(interrupt_payload, dict):
        payload = interrupt_payload.get("value")
    return dict(payload or {}) if isinstance(payload, dict) else {}


@dataclass
class StreamInvocationResult:
    values: dict[str, Any]
    streamed_text: str
    approval_request: ToolApprovalRequest | None = None


@dataclass
class ToolApprovalRequest:
    kind: str
    source: str
    tool_calls: list[dict[str, Any]]
    payload: dict[str, Any]


@dataclass
class EventRoundResult:
    values: dict[str, Any]
    final_text: str


def _approval_request_from_output(output: Any) -> ToolApprovalRequest | None:
    if not isinstance(output, dict):
        return None
    interrupts = output.get("__interrupt__")
    if not isinstance(interrupts, list) or not interrupts:
        return None
    payload = _payload_value(interrupts[0])
    kind = str(payload.get("kind") or "").strip().lower()
    if kind != "tool_approval":
        return None
    tool_calls = payload.get("tool_calls")
    if not isinstance(tool_calls, list):
        tool_calls = []
    normalized_calls = [dict(item) for item in tool_calls if isinstance(item, dict)]
    return ToolApprovalRequest(
        kind=kind,
        source=str(payload.get("source") or "").strip().lower(),
        tool_calls=normalized_calls,
        payload=payload,
    )


@dataclass
class BackendSession:
    graph: Any
    memory_store: MemoryStore
    thread_id: str
    user_id: str | None = None

    def config(self, *, checkpoint_id: str | None = None) -> dict[str, Any]:
        configurable: dict[str, Any] = {"thread_id": self.thread_id}
        if str(self.user_id or "").strip():
            configurable["user_id"] = self.user_id
        if str(checkpoint_id or "").strip():
            configurable["checkpoint_id"] = str(checkpoint_id).strip()
        return {"configurable": configurable}

    def build_run_config(self, pending_checkpoint_id: str | None) -> tuple[dict[str, Any], str | None]:
        if str(pending_checkpoint_id or "").strip():
            return self.config(checkpoint_id=str(pending_checkpoint_id).strip()), None
        return self.config(), pending_checkpoint_id

    def get_state_values(self, *, config: dict[str, Any] | None = None) -> dict[str, Any]:
        cfg = config or self.config()
        thread_id = _thread_id_from_config(cfg, self.thread_id)
        return _coerce_values(self.graph.get_state({"configurable": {"thread_id": thread_id}}))

    def emotion_label(self, *, config: dict[str, Any] | None = None, default: str = "neutral") -> str:
        vals = self.get_state_values(config=config)
        emotion_state = vals.get("emotion_state") if isinstance(vals.get("emotion_state"), dict) else {}
        label = str((emotion_state or {}).get("label") or "").strip()
        return label or str(default or "neutral")

    def apply_implicit_idle_maturation(
        self,
        *,
        run_config: dict[str, Any],
        last_conversation_touch_ts: int | None,
        trigger_minutes: int,
        now_ts: int | None = None,
    ) -> bool:
        if int(trigger_minutes or 0) <= 0 or last_conversation_touch_ts is None:
            return False
        clock_now = int(now_ts or 0) or 0
        if clock_now <= 0:
            import time as _time

            clock_now = int(_time.time())
        elapsed_seconds = max(0, clock_now - int(last_conversation_touch_ts))
        elapsed_minutes = elapsed_seconds // 60
        if elapsed_minutes < int(trigger_minutes):
            return False

        cfg = {"configurable": {"thread_id": _thread_id_from_config(run_config, self.thread_id)}}
        current_values = self.get_state_values(config=cfg)
        if not isinstance(current_values, dict):
            return False
        prepared = build_implicit_idle_state_update(
            current_values,
            idle_minutes=int(elapsed_minutes),
            created_at=clock_now,
        )
        self.graph.update_state(cfg, prepared, as_node="prepare_turn")
        return True

    def build_idle_event_payload(
        self,
        *,
        run_config: dict[str, Any],
        idle_minutes: int,
        note: str = "",
        created_at: int | None = None,
        extra_tags: list[str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        cfg = {"configurable": {"thread_id": _thread_id_from_config(run_config, self.thread_id)}}
        current_values = self.get_state_values(config=cfg)
        event_override = build_implicit_idle_event_override(
            current_values if isinstance(current_values, dict) else {},
            idle_minutes=int(idle_minutes),
            note=str(note or "").strip(),
            created_at=created_at,
            extra_tags=extra_tags or [],
        )
        return {"event_override": event_override}

    def invoke_stream(
        self,
        payload: Any,
        *,
        config: dict[str, Any] | None = None,
        on_text: Callable[[str], None] | None = None,
    ) -> StreamInvocationResult:
        cfg = config or self.config()
        last_values: dict[str, Any] | None = None
        buf = ""
        for mode, chunk in self.graph.stream(payload, config=cfg, stream_mode=["messages", "values"]):
            if mode == "values":
                last_values = dict(chunk) if isinstance(chunk, dict) else {}
                continue
            if mode != "messages":
                continue
            msg, meta = chunk
            if (meta or {}).get("langgraph_node") != "call_model":
                continue
            if not type(msg).__name__.endswith("Chunk"):
                continue
            text = getattr(msg, "content", "") or ""
            if not text:
                continue
            buf += str(text)
            if callable(on_text):
                on_text(str(text))
        values = last_values or {}
        return StreamInvocationResult(
            values=values,
            streamed_text=buf,
            approval_request=_approval_request_from_output(values),
        )

    def resume_stream(
        self,
        decisions: list[dict[str, Any]],
        *,
        config: dict[str, Any] | None = None,
        on_text: Callable[[str], None] | None = None,
    ) -> StreamInvocationResult:
        return self.invoke_stream(
            Command(resume={"decisions": decisions}),
            config=config,
            on_text=on_text,
        )

    def extract_final_text(
        self,
        values: dict[str, Any] | None,
        *,
        streamed_text: str = "",
    ) -> str:
        data = values if isinstance(values, dict) else {}
        msgs = data.get("messages")
        if isinstance(msgs, list) and msgs:
            return _message_content(msgs[-1])
        return str(streamed_text or "").strip()

    def invoke_event_round(
        self,
        *,
        run_config: dict[str, Any],
        event_payload: dict[str, Any],
        auto_resume_memory_approval: Callable[[dict[str, Any]], bool] | None = None,
        reject_reason: str = "event_round_no_manual_tooling",
    ) -> EventRoundResult:
        before_values = self.get_state_values(config=run_config)
        before_messages = before_values.get("messages") if isinstance(before_values.get("messages"), list) else []
        before_len = len(before_messages)

        out = self.graph.invoke(event_payload, config=run_config)
        approval_request = _approval_request_from_output(out)
        while approval_request is not None:
            if callable(auto_resume_memory_approval) and auto_resume_memory_approval(approval_request.payload):
                decisions = [{"action": "approve"} for _ in approval_request.tool_calls]
            else:
                decisions = [{"action": "reject", "reason": reject_reason} for _ in approval_request.tool_calls]
            out = self.graph.invoke(
                Command(resume={"decisions": decisions}),
                config={"configurable": {"thread_id": run_config["configurable"]["thread_id"]}},
            )
            approval_request = _approval_request_from_output(out)

        after_values = self.get_state_values(config=run_config)
        after_messages = after_values.get("messages") if isinstance(after_values.get("messages"), list) else []
        final_text = ""
        if len(after_messages) > before_len and after_messages:
            final_text = _message_content(after_messages[-1])
        return EventRoundResult(values=after_values, final_text=final_text)

    def build_evolution_summary(self, *, state_values: dict[str, Any] | None = None) -> dict[str, Any]:
        vals = state_values if isinstance(state_values, dict) else self.get_state_values()
        behavior_action, behavior_plan = resolve_behavior_payloads(
            behavior_action=vals.get("behavior_action") if isinstance(vals.get("behavior_action"), dict) else {},
            behavior_plan=vals.get("behavior_plan") if isinstance(vals.get("behavior_plan"), dict) else {},
            current_event=vals.get("current_event") if isinstance(vals.get("current_event"), dict) else {},
            world_model_state=vals.get("world_model_state") if isinstance(vals.get("world_model_state"), dict) else {},
        )
        behavior_queue = resolve_behavior_queue(
            behavior_queue=vals.get("behavior_queue"),
            behavior_agenda=vals.get("behavior_agenda"),
        )
        return build_evolution_cli_summary(
            relationship=self.memory_store.get_relationship(),
            semantic_narrative_profile=vals.get("semantic_narrative_profile")
            if isinstance(vals.get("semantic_narrative_profile"), dict)
            else {},
            world_model_state=vals.get("world_model_state") if isinstance(vals.get("world_model_state"), dict) else {},
            emotion_state=vals.get("emotion_state") if isinstance(vals.get("emotion_state"), dict) else {},
            bond_state=vals.get("bond_state") if isinstance(vals.get("bond_state"), dict) else {},
            counterpart_assessment=vals.get("counterpart_assessment")
            if isinstance(vals.get("counterpart_assessment"), dict)
            else {},
            behavior_action=behavior_action,
            behavior_plan=behavior_plan,
            behavior_queue=behavior_queue,
            interaction_carryover=vals.get("interaction_carryover")
            if isinstance(vals.get("interaction_carryover"), dict)
            else {},
            current_event=vals.get("current_event") if isinstance(vals.get("current_event"), dict) else {},
            worldline_focus=vals.get("worldline_focus") if isinstance(vals.get("worldline_focus"), list) else [],
            reconsolidation_snapshot=vals.get("reconsolidation_snapshot")
            if isinstance(vals.get("reconsolidation_snapshot"), dict)
            else {},
            agenda_lifecycle_residue=vals.get("agenda_lifecycle_residue")
            if isinstance(vals.get("agenda_lifecycle_residue"), dict)
            else {},
        )

    def worldline_view(self) -> dict[str, Any]:
        snap = self.memory_store.snapshot()
        vals = self.get_state_values()
        return {
            "worldline_summary": self.build_evolution_summary(state_values=vals),
            "worldline_events": snap.get("worldline_events", []),
            "commitments": snap.get("commitments", []),
            "conflict_repair": snap.get("conflict_repair", []),
            "unresolved_tensions": snap.get("unresolved_tensions", []),
            "semantic_self_narratives": snap.get("semantic_self_narratives", []),
            "revision_traces": snap.get("revision_traces", []),
        }

    def bond_view(self) -> dict[str, Any]:
        vals = self.get_state_values()
        runtime_relationship = vals.get("relationship") if isinstance(vals.get("relationship"), dict) else {}
        persisted_relationship = self.memory_store.get_relationship()
        relationship_state = _prefer_refreshed_relationship_state(runtime_relationship, persisted_relationship)
        return {
            "relationship_state": relationship_state,
            "bond_state": vals.get("bond_state") if isinstance(vals.get("bond_state"), dict) else {},
            "relationship_timeline": list(reversed(self.memory_store.list_relationship_timeline(limit=30))),
            "conflict_repair": list(reversed(self.memory_store.list_conflict_repairs(limit=30))),
        }

    def sources_view(self) -> dict[str, Any]:
        vals = self.get_state_values()
        return {
            "sources": list(reversed(self.memory_store.list_source_refs(limit=30))),
            "claim_links": vals.get("claim_links") if isinstance(vals.get("claim_links"), list) else [],
        }

    def persona_view(self) -> dict[str, Any]:
        vals = self.get_state_values()
        queue_vals = resolve_behavior_queue(
            behavior_queue=vals.get("behavior_queue"),
            behavior_agenda=vals.get("behavior_agenda"),
        )
        behavior_action, behavior_plan = resolve_behavior_payloads(
            behavior_action=vals.get("behavior_action") if isinstance(vals.get("behavior_action"), dict) else {},
            behavior_plan=vals.get("behavior_plan") if isinstance(vals.get("behavior_plan"), dict) else {},
            current_event=vals.get("current_event") if isinstance(vals.get("current_event"), dict) else {},
            world_model_state=vals.get("world_model_state") if isinstance(vals.get("world_model_state"), dict) else {},
        )
        return {
            "evolution_summary": self.build_evolution_summary(state_values=vals),
            "persona_state": vals.get("persona_state") if isinstance(vals.get("persona_state"), dict) else {},
            "emotion_state": vals.get("emotion_state") if isinstance(vals.get("emotion_state"), dict) else {},
            "bond_state": vals.get("bond_state") if isinstance(vals.get("bond_state"), dict) else {},
            "allostasis_state": vals.get("allostasis_state") if isinstance(vals.get("allostasis_state"), dict) else {},
            "counterpart_assessment": vals.get("counterpart_assessment")
            if isinstance(vals.get("counterpart_assessment"), dict)
            else {},
            "semantic_narrative_profile": vals.get("semantic_narrative_profile")
            if isinstance(vals.get("semantic_narrative_profile"), dict)
            else {},
            "world_model_state": vals.get("world_model_state") if isinstance(vals.get("world_model_state"), dict) else {},
            "evolution_state": vals.get("evolution_state") if isinstance(vals.get("evolution_state"), dict) else {},
            "reconsolidation_snapshot": vals.get("reconsolidation_snapshot")
            if isinstance(vals.get("reconsolidation_snapshot"), dict)
            else {},
            "turn_appraisal": vals.get("turn_appraisal") if isinstance(vals.get("turn_appraisal"), dict) else {},
            "behavior_policy": vals.get("behavior_policy") if isinstance(vals.get("behavior_policy"), dict) else {},
            "behavior_action": behavior_action,
            "interaction_carryover": vals.get("interaction_carryover")
            if isinstance(vals.get("interaction_carryover"), dict)
            else {},
            "agenda_lifecycle_residue": vals.get("agenda_lifecycle_residue")
            if isinstance(vals.get("agenda_lifecycle_residue"), dict)
            else {},
            "behavior_plan": behavior_plan,
            "behavior_queue": queue_vals,
            "behavior_queue_summary": build_behavior_queue_cli_summary(queue_vals, limit=3),
            "science_mode": bool(vals.get("science_mode", False)),
            "tsundere_intensity": vals.get("tsundere_intensity", 0.5),
            "ooc_detector": vals.get("ooc_detector") if isinstance(vals.get("ooc_detector"), dict) else {},
            "canon_guard": vals.get("canon_guard") if isinstance(vals.get("canon_guard"), dict) else {},
        }

    def appraisal_view(self) -> dict[str, Any]:
        vals = self.get_state_values()
        return vals.get("turn_appraisal") if isinstance(vals.get("turn_appraisal"), dict) else {}

    def current_checkpoint_view(self, *, config: dict[str, Any] | None = None) -> dict[str, Any]:
        cfg = config or self.config()
        thread_id = _thread_id_from_config(cfg, self.thread_id)
        snapshot = self.graph.get_state({"configurable": {"thread_id": thread_id}})
        snapshot_cfg = getattr(snapshot, "config", {}) if snapshot is not None else {}
        checkpoint_id = None
        if isinstance(snapshot_cfg, dict):
            checkpoint_id = (snapshot_cfg.get("configurable") or {}).get("checkpoint_id")
        return {"thread_id": thread_id, "checkpoint_id": checkpoint_id}

    def checkpoint_history_view(
        self,
        *,
        limit: int = 10,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cfg = config or self.config()
        thread_id = _thread_id_from_config(cfg, self.thread_id)
        try:
            capped_limit = max(1, int(limit))
        except Exception:
            capped_limit = 10
        history_rows = list(self.graph.get_state_history({"configurable": {"thread_id": thread_id}}))
        rows: list[dict[str, Any]] = []
        for snapshot in history_rows[:capped_limit]:
            snapshot_cfg = getattr(snapshot, "config", {}) if snapshot is not None else {}
            checkpoint_id = None
            if isinstance(snapshot_cfg, dict):
                checkpoint_id = (snapshot_cfg.get("configurable") or {}).get("checkpoint_id")
            rows.append(
                {
                    "checkpoint_id": checkpoint_id,
                    "next": list(getattr(snapshot, "next", []) or []),
                }
            )
        return {
            "thread_id": thread_id,
            "limit": capped_limit,
            "total": len(history_rows),
            "rows": rows,
        }

    def behavior_queue_view(self, *, config: dict[str, Any] | None = None) -> dict[str, Any]:
        vals = self.get_state_values(config=config)
        queue = resolve_behavior_queue(
            behavior_queue=vals.get("behavior_queue"),
            behavior_agenda=vals.get("behavior_agenda"),
        )
        return {
            "behavior_queue": queue,
            "behavior_queue_summary": build_behavior_queue_cli_summary(queue, limit=3),
        }


__all__ = [
    "BackendSession",
    "EventRoundResult",
    "StreamInvocationResult",
    "ToolApprovalRequest",
]
