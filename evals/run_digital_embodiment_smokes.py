from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from amadeus_thread0.runtime.backend_api import BackendAPI  # noqa: E402


REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

THREAD_ID = "digital-embodiment-smokes"
WORKSPACE_ROOT = "E:/runtime/workspaces/lab-notes"
WORKSPACE_NAME = "lab-notes"
WORKSPACE_FILE_REF = "notes/today.md"
SOURCE_URL = "https://docs.langchain.com/oss/python/langgraph/persistence"
SOURCE_TITLE = "Persistence v2"
SOURCE_QUERY = "langgraph persistence checkpointer thread recovery"
PRIMARY_SOURCE_REF_ID = 21
SECONDARY_SOURCE_REF_ID = 17


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


class ScenarioMemoryStore:
    def __init__(
        self,
        *,
        revision_traces: list[dict[str, Any]] | None = None,
        semantic_self_narratives: list[dict[str, Any]] | None = None,
        counterpart_assessment_history: list[dict[str, Any]] | None = None,
        proactive_continuity_history: list[dict[str, Any]] | None = None,
    ) -> None:
        self._revision_traces = list(revision_traces or [])
        self._semantic_self_narratives = list(semantic_self_narratives or [])
        self._counterpart_assessment_history = list(counterpart_assessment_history or [])
        self._proactive_continuity_history = list(proactive_continuity_history or [])

    def list_revision_traces(self, limit: int = 60) -> list[dict[str, Any]]:
        return list(self._revision_traces[:limit])

    def list_semantic_self_narratives(self, limit: int = 20) -> list[dict[str, Any]]:
        return list(self._semantic_self_narratives[:limit])

    def list_counterpart_assessment_history(self, limit: int = 12) -> list[dict[str, Any]]:
        return list(self._counterpart_assessment_history[:limit])

    def list_proactive_continuity_history(self, limit: int = 12) -> list[dict[str, Any]]:
        return list(self._proactive_continuity_history[:limit])


class ScenarioBackendSession:
    def __init__(self, memory_store: ScenarioMemoryStore) -> None:
        self.memory_store = memory_store

    def build_evolution_summary(self, *, state_values: dict[str, Any] | None = None) -> dict[str, Any]:
        values = state_values if isinstance(state_values, dict) else {}
        recon = _dict_or_empty(values.get("reconsolidation_snapshot"))
        consequence = _dict_or_empty(recon.get("behavior_consequence"))
        behavior_action = (
            dict(recon.get("behavior_action") or {})
            if isinstance(recon.get("behavior_action"), dict) and recon.get("behavior_action")
            else _dict_or_empty(values.get("behavior_action"))
        )
        counterpart = _dict_or_empty(recon.get("counterpart"))
        digital_body = _dict_or_empty(values.get("digital_body_state"))
        access_state = _dict_or_empty(digital_body.get("access_state"))
        resource_state = _dict_or_empty(digital_body.get("resource_state"))
        digital_body_consequence = _dict_or_empty(values.get("digital_body_consequence"))
        if not digital_body_consequence and isinstance(recon.get("digital_body_consequence"), dict):
            digital_body_consequence = dict(recon.get("digital_body_consequence") or {})
        current_event = _dict_or_empty(values.get("current_event"))
        interaction_carryover = (
            dict(recon.get("interaction_carryover") or {})
            if isinstance(recon.get("interaction_carryover"), dict) and recon.get("interaction_carryover")
            else _dict_or_empty(values.get("interaction_carryover"))
        )
        return {
            "relationship": {"stage": "working"},
            "current_turn": {
                "recon_event_kind": str(recon.get("event_kind") or "").strip(),
                "recon_interaction_frame": str(recon.get("interaction_frame") or "").strip(),
                "counterpart_stance": str(counterpart.get("stance") or "").strip(),
                "counterpart_scene": str(counterpart.get("scene") or "").strip(),
                "behavior_consequence_kind": str(consequence.get("kind") or "").strip(),
                "behavior_action_embodied_context": _dict_or_empty(behavior_action.get("embodied_context")),
                "digital_body_surface": str(digital_body.get("active_surface") or "").strip(),
                "digital_body_access_mode": str(access_state.get("mode") or "").strip(),
                "digital_body_pending_approval_count": int(access_state.get("pending_approval_count") or 0),
                "digital_body_retry_after_s": int(access_state.get("retry_after_s") or 0),
                "digital_body_cooldown_scope": str(access_state.get("cooldown_scope") or "").strip(),
                "digital_body_session_continuity": str(access_state.get("session_continuity") or "").strip(),
                "digital_body_session_expires_in_s": int(access_state.get("session_expires_in_s") or 0),
                "digital_body_session_recovery_mode": str(access_state.get("session_recovery_mode") or "").strip(),
                "digital_body_artifact_continuity": str(resource_state.get("artifact_continuity") or "").strip(),
                "digital_body_active_artifact_kind": str(resource_state.get("active_artifact_kind") or "").strip(),
                "digital_body_active_artifact_label": str(
                    resource_state.get("active_artifact_label") or resource_state.get("active_artifact_ref") or ""
                ).strip(),
                "digital_body_workspace_root": str(resource_state.get("workspace_root") or "").strip(),
                "digital_body_artifact_reacquisition_mode": str(
                    resource_state.get("artifact_reacquisition_mode") or ""
                ).strip(),
                "digital_body_preferred_source_ref_id": int(resource_state.get("preferred_source_ref_id") or 0),
                "digital_body_preferred_anchor_reason": str(resource_state.get("preferred_anchor_reason") or "").strip(),
                "digital_body_consequence_kind": str(digital_body_consequence.get("kind") or "").strip(),
                "digital_body_consequence_summary": str(digital_body_consequence.get("summary") or "").strip(),
                "digital_body_consequence_preferred_source_ref_id": int(
                    digital_body_consequence.get("preferred_source_ref_id") or 0
                ),
                "digital_body_consequence_preferred_anchor_reason": str(
                    digital_body_consequence.get("preferred_anchor_reason") or ""
                ).strip(),
            },
            "event_residue": {
                "event_kind": str(current_event.get("kind") or "").strip(),
                "digital_body_consequence": dict(digital_body_consequence),
            },
            "interaction_carryover": dict(interaction_carryover),
            "digital_body": dict(digital_body),
            "digital_body_consequence": dict(digital_body_consequence),
        }

    def extract_final_text(self, values: dict[str, Any] | None, *, streamed_text: str = "") -> str:
        data = values if isinstance(values, dict) else {}
        final_text = str(data.get("final_text") or "").strip()
        return final_text or str(streamed_text or "").strip()


def _runtime_bundle(memory_store: ScenarioMemoryStore) -> SimpleNamespace:
    session = ScenarioBackendSession(memory_store)
    settings = SimpleNamespace(
        checkpoint_db_path=PROJECT_ROOT / "evals" / "_tmp" / "digital-embodiment-smokes.sqlite",
        data_dir=PROJECT_ROOT,
        model_provider="synthetic",
        model_name="digital-embodiment-contract",
        model_base_url="",
        runtime_mode="eval",
    )
    return SimpleNamespace(
        thread_id=THREAD_ID,
        backend_session=session,
        memory_admin=SimpleNamespace(snapshot_view=lambda: {}),
        settings=settings,
    )


def _access_proposal(
    *,
    pending_grants: list[str] | None = None,
    resolved_grants: list[str] | None = None,
    completion_ratio: float = 0.0,
) -> dict[str, Any]:
    return {
        "target": "filesystem",
        "mode": "operator_create_workspace",
        "path_kind": "create_new",
        "summary": "Create a writable workspace before continuing.",
        "operator_action": "Create a writable workspace for the current task.",
        "grants": ["filesystem", "workspace_write"],
        "pending_grants": list(pending_grants or []),
        "resolved_grants": list(resolved_grants or []),
        "completion_ratio": float(completion_ratio),
        "requires_operator": True,
    }


def _permission_state(
    *,
    approval_state: str = "open",
    pending_approval_count: int = 0,
    external_mutation_pending: bool = False,
    selected_access_proposal: dict[str, Any] | None = None,
    pending_grants: list[str] | None = None,
    resolved_grants: list[str] | None = None,
    completion_ratio: float = 0.0,
) -> dict[str, Any]:
    return {
        "approval_state": approval_state,
        "pending_approval_count": int(pending_approval_count),
        "external_mutation_pending": bool(external_mutation_pending),
        "selected_access_proposal": dict(selected_access_proposal or {}),
        "pending_grants": list(pending_grants or []),
        "resolved_grants": list(resolved_grants or []),
        "completion_ratio": float(completion_ratio),
    }


def _sandbox_state(
    *,
    availability: str = "restricted",
    execution_policy: str = "approval_required",
    allowed_roots: list[str] | None = None,
    last_status: str = "",
) -> dict[str, Any]:
    return {
        "availability": availability,
        "execution_policy": execution_policy,
        "allowed_roots": list(allowed_roots or []),
        "last_status": str(last_status or "").strip(),
    }


def _resource_state(
    *,
    artifact_carrier: str,
    active_artifact_kind: str,
    active_artifact_ref: str,
    active_artifact_label: str,
    workspace_root: str = "",
    artifact_continuity: str = "attached",
    artifact_reacquisition_mode: str = "",
    artifact_mutation_mode: str = "",
    completed_packet_count: int = 1,
    external_tool_count: int = 1,
    artifact_source_ref_ids: list[int] | None = None,
    preferred_source_ref_id: int = 0,
    preferred_anchor_reason: str = "",
    artifact_source_url: str = "",
    artifact_source_query: str = "",
    artifact_source_title: str = "",
    artifact_source_tool_name: str = "",
) -> dict[str, Any]:
    return {
        "behavior_queue_depth": 0,
        "action_packet_count": 1,
        "pending_approval_count": 0,
        "queued_packet_count": 0,
        "executing_packet_count": 0,
        "completed_packet_count": int(completed_packet_count),
        "blocked_packet_count": 0,
        "external_tool_count": int(external_tool_count),
        "artifact_continuity": artifact_continuity,
        "artifact_carrier": artifact_carrier,
        "active_artifact_kind": active_artifact_kind,
        "active_artifact_ref": active_artifact_ref,
        "active_artifact_label": active_artifact_label,
        "workspace_root": workspace_root,
        "artifact_reacquisition_mode": artifact_reacquisition_mode,
        "artifact_mutation_mode": artifact_mutation_mode,
        "artifact_source_ref_ids": list(artifact_source_ref_ids or []),
        "preferred_source_ref_id": int(preferred_source_ref_id or 0),
        "preferred_anchor_reason": str(preferred_anchor_reason or "").strip(),
        "artifact_source_url": artifact_source_url,
        "artifact_source_query": artifact_source_query,
        "artifact_source_title": artifact_source_title,
        "artifact_source_tool_name": artifact_source_tool_name,
    }


def _digital_body_state(
    *,
    access_state: dict[str, Any],
    resource_state: dict[str, Any],
    active_surface: str = "tooling",
    world_surfaces: list[str] | None = None,
    action_channels: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "active_surface": active_surface,
        "perception_channels": ["dialogue", "text"],
        "action_channels": list(action_channels or ["language", "structured_action", "tooling"]),
        "world_surfaces": list(world_surfaces or ["filesystem"]),
        "access_state": dict(access_state),
        "resource_state": dict(resource_state),
    }


def _access_state(
    *,
    mode: str,
    filesystem_state: str = "writable",
    network_access: str = "enabled",
    pending_approval_count: int = 0,
    missing_access: list[str] | None = None,
    requestable_access: list[str] | None = None,
    conditions: list[str] | None = None,
    selected_access_proposal: dict[str, Any] | None = None,
    access_acquire_proposals: list[dict[str, Any]] | None = None,
    pending_grants: list[str] | None = None,
    resolved_grants: list[str] | None = None,
    completion_ratio: float = 0.0,
    permission_state: dict[str, Any] | None = None,
    sandbox_state: dict[str, Any] | None = None,
    external_mutation_pending: bool = False,
) -> dict[str, Any]:
    session_state = {
        "continuity": "stable",
        "expires_in_s": 0,
        "recovery_mode": "",
    }
    account_state_detail = {
        "login_state": "",
        "cookie_state": "",
        "account_hint": "",
    }
    quota_state_detail = {
        "provider_state": "",
        "cooldown_scope": "",
        "retry_after_s": 0,
    }
    selected = dict(selected_access_proposal or {})
    pending = list(pending_grants or [])
    resolved = list(resolved_grants or [])
    perm = (
        dict(permission_state)
        if isinstance(permission_state, dict) and permission_state
        else _permission_state(
            approval_state="approval_pending" if pending_approval_count else "open",
            pending_approval_count=pending_approval_count,
            external_mutation_pending=external_mutation_pending,
            selected_access_proposal=selected,
            pending_grants=pending,
            resolved_grants=resolved,
            completion_ratio=completion_ratio,
        )
    )
    return {
        "mode": mode,
        "conditions": list(conditions or []),
        "block_reason": "",
        "retry_after_s": 0,
        "cooldown_scope": "",
        "session_continuity": "stable",
        "session_expires_in_s": 0,
        "session_recovery_mode": "",
        "pending_approval_count": int(pending_approval_count),
        "external_mutation_pending": bool(external_mutation_pending),
        "granted_toolsets": ["workspace_fs"],
        "missing_access": list(missing_access or []),
        "requestable_access": list(requestable_access or []),
        "access_acquire_proposals": list(access_acquire_proposals or []),
        "selected_access_proposal": selected,
        "pending_grants": pending,
        "resolved_grants": resolved,
        "completion_ratio": float(completion_ratio),
        "browser_session": "",
        "account_state": "",
        "cookie_state": "",
        "api_key_state": "",
        "quota_state": "",
        "filesystem_state": filesystem_state,
        "sandbox_mode": str((sandbox_state or {}).get("availability") or "").strip(),
        "network_access": network_access,
        "session_state": session_state,
        "account_state_detail": account_state_detail,
        "quota_state_detail": quota_state_detail,
        "permission_state": perm,
        "sandbox_state": dict(
            sandbox_state or _sandbox_state(availability="restricted", execution_policy="approval_required")
        ),
    }


def _artifact_context(
    *,
    carrier: str,
    artifact_kind: str,
    artifact_ref: str,
    artifact_label: str,
    workspace_root: str = "",
    reacquisition_mode: str = "",
    mutation_mode: str = "",
    source_ref_ids: list[int] | None = None,
    preferred_source_ref_id: int = 0,
    preferred_anchor_reason: str = "",
    source_url: str = "",
    source_query: str = "",
    source_title: str = "",
    source_tool_name: str = "",
) -> dict[str, Any]:
    return {
        "carrier": carrier,
        "artifact_kind": artifact_kind,
        "artifact_ref": artifact_ref,
        "artifact_label": artifact_label,
        "workspace_root": workspace_root,
        "reacquisition_mode": reacquisition_mode,
        "mutation_mode": mutation_mode,
        "source_ref_ids": list(source_ref_ids or []),
        "preferred_source_ref_id": int(preferred_source_ref_id or 0),
        "preferred_anchor_reason": str(preferred_anchor_reason or "").strip(),
        "source_url": source_url,
        "source_query": source_query,
        "source_title": source_title,
        "source_tool_name": source_tool_name,
    }


def _action_packet(
    *,
    proposal_id: str,
    intent: str,
    status: str,
    tool_name: str,
    risk: str,
    requires_approval: bool,
    expected_effect: str,
    result_summary: str = "",
    writeback_ready: bool = False,
    selected_access_proposal: dict[str, Any] | None = None,
    access_acquire_proposals: list[dict[str, Any]] | None = None,
    pending_grants: list[str] | None = None,
    resolved_grants: list[str] | None = None,
    completion_ratio: float = 0.0,
    artifact_context: dict[str, Any] | None = None,
    tool_args: dict[str, Any] | None = None,
    block_reason: str = "",
) -> dict[str, Any]:
    return {
        "proposal_id": proposal_id,
        "origin": "counterpart_request",
        "intent": intent,
        "status": status,
        "risk": risk,
        "requires_approval": bool(requires_approval),
        "tool_name": tool_name,
        "tool_args": dict(tool_args or {}),
        "capability_steps": [
            {
                "kind": "tool",
                "name": tool_name,
                "status": status,
                "requires_approval": bool(requires_approval),
            }
        ],
        "expected_effect": expected_effect,
        "result_summary": result_summary,
        "writeback_ready": bool(writeback_ready),
        "selected_access_proposal": dict(selected_access_proposal or {}),
        "access_acquire_proposals": list(access_acquire_proposals or []),
        "pending_grants": list(pending_grants or []),
        "resolved_grants": list(resolved_grants or []),
        "completion_ratio": float(completion_ratio),
        "artifact_context": dict(artifact_context or {}),
        "block_reason": block_reason,
    }


def _consequence(
    kind: str,
    summary: str,
    *,
    primary_status: str,
    active_surface: str,
    access_mode: str,
    world_surfaces: list[str],
    artifact_continuity: str,
    artifact_carrier: str,
    active_artifact_kind: str,
    active_artifact_ref: str,
    active_artifact_label: str,
    workspace_root: str = "",
    primary_tool_name: str = "",
    artifact_reacquisition_mode: str = "",
    artifact_mutation_mode: str = "",
    procedural_growth: bool = False,
    selected_access_proposal: dict[str, Any] | None = None,
    access_acquire_proposals: list[dict[str, Any]] | None = None,
    pending_grants: list[str] | None = None,
    resolved_grants: list[str] | None = None,
    completion_ratio: float = 0.0,
    sandbox_state: dict[str, Any] | None = None,
    permission_state: dict[str, Any] | None = None,
    artifact_source_ref_ids: list[int] | None = None,
    preferred_source_ref_id: int = 0,
    preferred_anchor_reason: str = "",
    artifact_source_url: str = "",
    artifact_source_query: str = "",
    artifact_source_title: str = "",
    artifact_source_tool_name: str = "",
) -> dict[str, Any]:
    return {
        "kind": kind,
        "summary": summary,
        "active_surface": active_surface,
        "access_mode": access_mode,
        "world_surfaces": list(world_surfaces),
        "artifact_continuity": artifact_continuity,
        "artifact_carrier": artifact_carrier,
        "active_artifact_kind": active_artifact_kind,
        "active_artifact_ref": active_artifact_ref,
        "active_artifact_label": active_artifact_label,
        "workspace_root": workspace_root,
        "primary_status": primary_status,
        "primary_tool_name": primary_tool_name,
        "artifact_reacquisition_mode": artifact_reacquisition_mode,
        "artifact_mutation_mode": artifact_mutation_mode,
        "procedural_growth": bool(procedural_growth),
        "selected_access_proposal": dict(selected_access_proposal or {}),
        "access_acquire_proposals": list(access_acquire_proposals or []),
        "pending_grants": list(pending_grants or []),
        "resolved_grants": list(resolved_grants or []),
        "completion_ratio": float(completion_ratio),
        "sandbox_state": dict(sandbox_state or {}),
        "permission_state": dict(permission_state or {}),
        "artifact_source_ref_ids": list(artifact_source_ref_ids or []),
        "preferred_source_ref_id": int(preferred_source_ref_id or 0),
        "preferred_anchor_reason": str(preferred_anchor_reason or "").strip(),
        "artifact_source_url": artifact_source_url,
        "artifact_source_query": artifact_source_query,
        "artifact_source_title": artifact_source_title,
        "artifact_source_tool_name": artifact_source_tool_name,
    }


def _revision_trace(kind: str, *, created_at: int, embodied_context: dict[str, Any]) -> dict[str, Any]:
    return {
        "namespace": "semantic_self_evidence",
        "target_id": "agency_style",
        "after_summary": f"Finalized {kind} on the digital body surface.",
        "source": "auto:passive_evolution_final",
        "created_at": created_at,
        "behavior_consequence": {
            "embodied_context": dict(embodied_context),
        },
    }


def _scenario_step(
    *,
    step_id: str,
    created_at: int,
    final_text: str,
    autonomy_intent: dict[str, Any],
    action_packets: list[dict[str, Any]],
    digital_body_state: dict[str, Any],
    digital_body_consequence: dict[str, Any],
    pending_action_proposal: dict[str, Any] | None = None,
    action_trace: list[dict[str, Any]] | None = None,
    writeback_revision_traces: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    event = {
        "kind": "user_utterance",
        "created_at": created_at,
        "text": "continue",
        "perception": {"channel": "dialogue", "modality": "text"},
    }
    state_values = {
        "final_text": final_text,
        "current_event": event,
        "session_context": {
            "thread_id": THREAD_ID,
            "turn_started_at": created_at,
        },
        "turn_appraisal": {"scene": "co_work"},
        "autonomy_intent": dict(autonomy_intent),
        "action_packets": list(action_packets),
        "pending_action_proposal": dict(pending_action_proposal or {}),
        "action_trace": list(action_trace or []),
        "digital_body_state": dict(digital_body_state),
        "digital_body_consequence": dict(digital_body_consequence),
        "reconsolidation_snapshot": {
            "digital_body_consequence": dict(digital_body_consequence),
        },
    }
    memory_store = ScenarioMemoryStore(
        revision_traces=list(writeback_revision_traces or []),
    )
    return {
        "id": step_id,
        "created_at": created_at,
        "state_values": state_values,
        "memory_store": memory_store,
    }


def _build_turn_payload(
    state_values: dict[str, Any],
    *,
    memory_store: ScenarioMemoryStore,
) -> dict[str, Any]:
    api = BackendAPI(runtime_bundle=_runtime_bundle(memory_store), base_data_dir=PROJECT_ROOT, cwd=PROJECT_ROOT)
    envelope = api.build_turn_response(state_values=state_values, streamed_text="", meta={"source": "digital_embodiment_smoke"})
    return dict(envelope.payload)


def _workspace_artifact_continuity_spec() -> dict[str, Any]:
    inspect_packet = _action_packet(
        proposal_id="ap-workspace-inspect-1",
        intent="tool:inspect_workspace_path",
        status="completed",
        tool_name="inspect_workspace_path",
        risk="read",
        requires_approval=False,
        expected_effect="Reinspect the current workspace file before continuing.",
        result_summary="Inspected notes/today.md.",
        writeback_ready=True,
        artifact_context=_artifact_context(
            carrier="filesystem",
            artifact_kind="file",
            artifact_ref=WORKSPACE_FILE_REF,
            artifact_label="today.md",
            workspace_root=WORKSPACE_ROOT,
            reacquisition_mode="inspect_workspace_path",
        ),
        tool_args={"path": WORKSPACE_FILE_REF},
    )
    inspect_body = _digital_body_state(
        access_state=_access_state(mode="tool_enabled"),
        resource_state=_resource_state(
            artifact_carrier="filesystem",
            active_artifact_kind="file",
            active_artifact_ref=WORKSPACE_FILE_REF,
            active_artifact_label="today.md",
            workspace_root=WORKSPACE_ROOT,
            artifact_reacquisition_mode="inspect_workspace_path",
            external_tool_count=1,
        ),
    )
    inspect_consequence = _consequence(
        "workspace_path_inspected",
        "The same workspace file was inspected before continuing.",
        primary_status="completed",
        active_surface="tooling",
        access_mode="tool_enabled",
        world_surfaces=["filesystem"],
        artifact_continuity="attached",
        artifact_carrier="filesystem",
        active_artifact_kind="file",
        active_artifact_ref=WORKSPACE_FILE_REF,
        active_artifact_label="today.md",
        workspace_root=WORKSPACE_ROOT,
        primary_tool_name="inspect_workspace_path",
        artifact_reacquisition_mode="inspect_workspace_path",
    )
    update_packet = _action_packet(
        proposal_id="ap-workspace-update-1",
        intent="tool:append_workspace_file",
        status="completed",
        tool_name="append_workspace_file",
        risk="memory_write",
        requires_approval=False,
        expected_effect="Append the next block into the same file.",
        result_summary="Appended a new block into notes/today.md.",
        writeback_ready=True,
        artifact_context=_artifact_context(
            carrier="filesystem",
            artifact_kind="file",
            artifact_ref=WORKSPACE_FILE_REF,
            artifact_label="today.md",
            workspace_root=WORKSPACE_ROOT,
            mutation_mode="append",
        ),
        tool_args={"path": WORKSPACE_FILE_REF, "mode": "append"},
    )
    update_body = _digital_body_state(
        access_state=_access_state(mode="tool_enabled"),
        resource_state=_resource_state(
            artifact_carrier="filesystem",
            active_artifact_kind="file",
            active_artifact_ref=WORKSPACE_FILE_REF,
            active_artifact_label="today.md",
            workspace_root=WORKSPACE_ROOT,
            artifact_mutation_mode="append",
            external_tool_count=1,
        ),
    )
    update_consequence = _consequence(
        "workspace_file_updated",
        "The same workspace file was updated in place.",
        primary_status="completed",
        active_surface="tooling",
        access_mode="tool_enabled",
        world_surfaces=["filesystem"],
        artifact_continuity="attached",
        artifact_carrier="filesystem",
        active_artifact_kind="file",
        active_artifact_ref=WORKSPACE_FILE_REF,
        active_artifact_label="today.md",
        workspace_root=WORKSPACE_ROOT,
        primary_tool_name="append_workspace_file",
        artifact_mutation_mode="append",
        procedural_growth=True,
    )
    resume_packet = _action_packet(
        proposal_id="ap-workspace-resume-1",
        intent="tool:inspect_workspace_path",
        status="completed",
        tool_name="inspect_workspace_path",
        risk="read",
        requires_approval=False,
        expected_effect="Continue from the same file rather than opening a new artifact.",
        result_summary="Reattached the same file for continuation.",
        writeback_ready=True,
        artifact_context=_artifact_context(
            carrier="filesystem",
            artifact_kind="file",
            artifact_ref=WORKSPACE_FILE_REF,
            artifact_label="today.md",
            workspace_root=WORKSPACE_ROOT,
            reacquisition_mode="inspect_workspace_path",
        ),
        tool_args={"path": WORKSPACE_FILE_REF},
    )
    resume_body = _digital_body_state(
        access_state=_access_state(mode="tool_enabled"),
        resource_state=_resource_state(
            artifact_carrier="filesystem",
            active_artifact_kind="file",
            active_artifact_ref=WORKSPACE_FILE_REF,
            active_artifact_label="today.md",
            workspace_root=WORKSPACE_ROOT,
            artifact_reacquisition_mode="inspect_workspace_path",
            external_tool_count=1,
        ),
    )
    resume_consequence = _consequence(
        "workspace_path_inspected",
        "Continuation stayed on the same file instead of degrading into a generic growth summary.",
        primary_status="completed",
        active_surface="tooling",
        access_mode="tool_enabled",
        world_surfaces=["filesystem"],
        artifact_continuity="attached",
        artifact_carrier="filesystem",
        active_artifact_kind="file",
        active_artifact_ref=WORKSPACE_FILE_REF,
        active_artifact_label="today.md",
        workspace_root=WORKSPACE_ROOT,
        primary_tool_name="inspect_workspace_path",
        artifact_reacquisition_mode="inspect_workspace_path",
    )
    return {
        "id": "workspace_artifact_continuity",
        "title": "workspace_artifact_continuity",
        "focus": "Keep the same workspace file continuous across inspect, update, and resume.",
        "steps": [
            _scenario_step(
                step_id="inspect",
                created_at=1710001001,
                final_text="I inspected today.md before continuing.",
                autonomy_intent={
                    "mode": "tool_followthrough",
                    "origin": "counterpart_request",
                    "reason": "Reinspect the current file before continuing.",
                    "primary_proposal_id": inspect_packet["proposal_id"],
                },
                action_packets=[inspect_packet],
                action_trace=[
                    {
                        "proposal_id": inspect_packet["proposal_id"],
                        "event": "tool_completed",
                        "tool_name": "inspect_workspace_path",
                        "status": "completed",
                    }
                ],
                digital_body_state=inspect_body,
                digital_body_consequence=inspect_consequence,
            ),
            _scenario_step(
                step_id="update",
                created_at=1710001002,
                final_text="I appended the next block into today.md.",
                autonomy_intent={
                    "mode": "tool_followthrough",
                    "origin": "counterpart_request",
                    "reason": "Append into the same file that is already active.",
                    "primary_proposal_id": update_packet["proposal_id"],
                },
                action_packets=[update_packet],
                action_trace=[
                    {
                        "proposal_id": update_packet["proposal_id"],
                        "event": "tool_completed",
                        "tool_name": "append_workspace_file",
                        "status": "completed",
                    }
                ],
                digital_body_state=update_body,
                digital_body_consequence=update_consequence,
            ),
            _scenario_step(
                step_id="resume",
                created_at=1710001003,
                final_text="I stayed on the same file and picked it back up directly.",
                autonomy_intent={
                    "mode": "tool_followthrough",
                    "origin": "counterpart_request",
                    "reason": "Continue the same active file instead of reacquiring a different surface.",
                    "primary_proposal_id": resume_packet["proposal_id"],
                },
                action_packets=[resume_packet],
                action_trace=[
                    {
                        "proposal_id": resume_packet["proposal_id"],
                        "event": "tool_completed",
                        "tool_name": "inspect_workspace_path",
                        "status": "completed",
                    }
                ],
                digital_body_state=resume_body,
                digital_body_consequence=resume_consequence,
                writeback_revision_traces=[
                    _revision_trace(
                        "workspace_path_inspected",
                        created_at=1710001003,
                        embodied_context=resume_consequence,
                    )
                ],
            ),
        ],
    }


def _workspace_access_request_resolve_spec() -> dict[str, Any]:
    pending_proposal = _access_proposal(
        pending_grants=["filesystem", "workspace_write"],
        resolved_grants=[],
        completion_ratio=0.0,
    )
    resolved_proposal = _access_proposal(
        pending_grants=[],
        resolved_grants=["filesystem", "workspace_write"],
        completion_ratio=1.0,
    )
    pending_packet = _action_packet(
        proposal_id="ap-workspace-access-1",
        intent="access:request_help",
        status="awaiting_approval",
        tool_name="create_workspace_access",
        risk="external_mutation",
        requires_approval=True,
        expected_effect="Request a writable workspace before file work can continue.",
        selected_access_proposal=pending_proposal,
        access_acquire_proposals=[pending_proposal],
        pending_grants=["filesystem", "workspace_write"],
        resolved_grants=[],
        completion_ratio=0.0,
    )
    pending_access = _access_state(
        mode="approval_pending",
        filesystem_state="missing",
        pending_approval_count=1,
        missing_access=["filesystem", "workspace_write"],
        requestable_access=["filesystem", "workspace_write", "human_approval"],
        conditions=["human_approval_required", "workspace_missing"],
        selected_access_proposal=pending_proposal,
        access_acquire_proposals=[pending_proposal],
        pending_grants=["filesystem", "workspace_write"],
        resolved_grants=[],
        completion_ratio=0.0,
        permission_state=_permission_state(
            approval_state="approval_pending",
            pending_approval_count=1,
            selected_access_proposal=pending_proposal,
            pending_grants=["filesystem", "workspace_write"],
            resolved_grants=[],
            completion_ratio=0.0,
        ),
    )
    pending_body = _digital_body_state(
        access_state=pending_access,
        resource_state=_resource_state(
            artifact_carrier="filesystem",
            active_artifact_kind="workspace",
            active_artifact_ref="",
            active_artifact_label="",
            workspace_root="",
            completed_packet_count=0,
            external_tool_count=0,
        ),
        active_surface="approval_gate",
        action_channels=["language", "approval_gate", "tooling"],
    )
    pending_consequence = _consequence(
        "access_request_pending",
        "Workspace write access is still pending operator approval.",
        primary_status="awaiting_approval",
        active_surface="approval_gate",
        access_mode="approval_pending",
        world_surfaces=["filesystem"],
        artifact_continuity="detached",
        artifact_carrier="filesystem",
        active_artifact_kind="workspace",
        active_artifact_ref="",
        active_artifact_label="",
        selected_access_proposal=pending_proposal,
        access_acquire_proposals=[pending_proposal],
        pending_grants=["filesystem", "workspace_write"],
        resolved_grants=[],
        completion_ratio=0.0,
        permission_state=_permission_state(
            approval_state="approval_pending",
            pending_approval_count=1,
            selected_access_proposal=pending_proposal,
            pending_grants=["filesystem", "workspace_write"],
            resolved_grants=[],
            completion_ratio=0.0,
        ),
    )
    resolved_packet = _action_packet(
        proposal_id="ap-workspace-access-1",
        intent="access:request_help",
        status="completed",
        tool_name="create_workspace_access",
        risk="external_mutation",
        requires_approval=True,
        expected_effect="Workspace access has been created and attached.",
        result_summary="Created the writable workspace and attached it.",
        writeback_ready=True,
        selected_access_proposal=resolved_proposal,
        access_acquire_proposals=[resolved_proposal],
        pending_grants=[],
        resolved_grants=["filesystem", "workspace_write"],
        completion_ratio=1.0,
        artifact_context=_artifact_context(
            carrier="filesystem",
            artifact_kind="workspace",
            artifact_ref=WORKSPACE_ROOT,
            artifact_label=WORKSPACE_NAME,
            workspace_root=WORKSPACE_ROOT,
        ),
    )
    resolved_access = _access_state(
        mode="tool_enabled",
        selected_access_proposal=resolved_proposal,
        access_acquire_proposals=[resolved_proposal],
        pending_grants=[],
        resolved_grants=["filesystem", "workspace_write"],
        completion_ratio=1.0,
        permission_state=_permission_state(
            approval_state="open",
            pending_approval_count=0,
            selected_access_proposal=resolved_proposal,
            pending_grants=[],
            resolved_grants=["filesystem", "workspace_write"],
            completion_ratio=1.0,
        ),
    )
    resolved_body = _digital_body_state(
        access_state=resolved_access,
        resource_state=_resource_state(
            artifact_carrier="filesystem",
            active_artifact_kind="workspace",
            active_artifact_ref=WORKSPACE_ROOT,
            active_artifact_label=WORKSPACE_NAME,
            workspace_root=WORKSPACE_ROOT,
            external_tool_count=1,
        ),
    )
    resolved_consequence = _consequence(
        "workspace_access_resolved",
        "The writable workspace is now attached and ready for continued file work.",
        primary_status="completed",
        active_surface="tooling",
        access_mode="tool_enabled",
        world_surfaces=["filesystem"],
        artifact_continuity="attached",
        artifact_carrier="filesystem",
        active_artifact_kind="workspace",
        active_artifact_ref=WORKSPACE_ROOT,
        active_artifact_label=WORKSPACE_NAME,
        workspace_root=WORKSPACE_ROOT,
        primary_tool_name="create_workspace_access",
        selected_access_proposal=resolved_proposal,
        access_acquire_proposals=[resolved_proposal],
        pending_grants=[],
        resolved_grants=["filesystem", "workspace_write"],
        completion_ratio=1.0,
        permission_state=_permission_state(
            approval_state="open",
            pending_approval_count=0,
            selected_access_proposal=resolved_proposal,
            pending_grants=[],
            resolved_grants=["filesystem", "workspace_write"],
            completion_ratio=1.0,
        ),
    )
    continue_packet = _action_packet(
        proposal_id="ap-workspace-write-2",
        intent="tool:append_workspace_file",
        status="completed",
        tool_name="append_workspace_file",
        risk="memory_write",
        requires_approval=False,
        expected_effect="Continue on the now-resolved workspace without requesting access again.",
        result_summary="Wrote into the workspace file without reopening access request flow.",
        writeback_ready=True,
        selected_access_proposal=resolved_proposal,
        access_acquire_proposals=[resolved_proposal],
        pending_grants=[],
        resolved_grants=["filesystem", "workspace_write"],
        completion_ratio=1.0,
        artifact_context=_artifact_context(
            carrier="filesystem",
            artifact_kind="file",
            artifact_ref=WORKSPACE_FILE_REF,
            artifact_label="today.md",
            workspace_root=WORKSPACE_ROOT,
            mutation_mode="append",
        ),
        tool_args={"path": WORKSPACE_FILE_REF, "mode": "append"},
    )
    continue_access = _access_state(
        mode="tool_enabled",
        selected_access_proposal=resolved_proposal,
        access_acquire_proposals=[resolved_proposal],
        pending_grants=[],
        resolved_grants=["filesystem", "workspace_write"],
        completion_ratio=1.0,
        permission_state=_permission_state(
            approval_state="open",
            pending_approval_count=0,
            selected_access_proposal=resolved_proposal,
            pending_grants=[],
            resolved_grants=["filesystem", "workspace_write"],
            completion_ratio=1.0,
        ),
    )
    continue_body = _digital_body_state(
        access_state=continue_access,
        resource_state=_resource_state(
            artifact_carrier="filesystem",
            active_artifact_kind="file",
            active_artifact_ref=WORKSPACE_FILE_REF,
            active_artifact_label="today.md",
            workspace_root=WORKSPACE_ROOT,
            artifact_mutation_mode="append",
            external_tool_count=1,
        ),
    )
    continue_consequence = _consequence(
        "workspace_file_updated",
        "The task continued on the resolved workspace instead of reopening access planning.",
        primary_status="completed",
        active_surface="tooling",
        access_mode="tool_enabled",
        world_surfaces=["filesystem"],
        artifact_continuity="attached",
        artifact_carrier="filesystem",
        active_artifact_kind="file",
        active_artifact_ref=WORKSPACE_FILE_REF,
        active_artifact_label="today.md",
        workspace_root=WORKSPACE_ROOT,
        primary_tool_name="append_workspace_file",
        artifact_mutation_mode="append",
        procedural_growth=True,
        selected_access_proposal=resolved_proposal,
        access_acquire_proposals=[resolved_proposal],
        pending_grants=[],
        resolved_grants=["filesystem", "workspace_write"],
        completion_ratio=1.0,
        permission_state=_permission_state(
            approval_state="open",
            pending_approval_count=0,
            selected_access_proposal=resolved_proposal,
            pending_grants=[],
            resolved_grants=["filesystem", "workspace_write"],
            completion_ratio=1.0,
        ),
    )
    return {
        "id": "workspace_access_request_resolve",
        "title": "workspace_access_request_resolve",
        "focus": "Keep the same selected access path from request to resolve to actual workspace continuation.",
        "steps": [
            _scenario_step(
                step_id="request",
                created_at=1710001101,
                final_text="I need a writable workspace before I can continue.",
                autonomy_intent={
                    "mode": "approval_pending",
                    "origin": "counterpart_request",
                    "reason": "Workspace access is missing, so I have to request it first.",
                    "primary_proposal_id": pending_packet["proposal_id"],
                },
                action_packets=[pending_packet],
                pending_action_proposal=pending_packet,
                action_trace=[
                    {
                        "proposal_id": pending_packet["proposal_id"],
                        "event": "approval_requested",
                        "tool_name": "create_workspace_access",
                        "status": "awaiting_approval",
                    }
                ],
                digital_body_state=pending_body,
                digital_body_consequence=pending_consequence,
            ),
            _scenario_step(
                step_id="resolved",
                created_at=1710001102,
                final_text="The writable workspace is attached now.",
                autonomy_intent={
                    "mode": "tool_followthrough",
                    "origin": "counterpart_request",
                    "reason": "The approved workspace path has been resolved.",
                    "primary_proposal_id": resolved_packet["proposal_id"],
                },
                action_packets=[resolved_packet],
                action_trace=[
                    {
                        "proposal_id": resolved_packet["proposal_id"],
                        "event": "tool_completed",
                        "tool_name": "create_workspace_access",
                        "status": "completed",
                    }
                ],
                digital_body_state=resolved_body,
                digital_body_consequence=resolved_consequence,
                writeback_revision_traces=[
                    _revision_trace(
                        "workspace_access_resolved",
                        created_at=1710001102,
                        embodied_context=resolved_consequence,
                    )
                ],
            ),
            _scenario_step(
                step_id="continue",
                created_at=1710001103,
                final_text="I continued on the same workspace without reopening access.",
                autonomy_intent={
                    "mode": "tool_followthrough",
                    "origin": "counterpart_request",
                    "reason": "Keep working on the newly resolved workspace.",
                    "primary_proposal_id": continue_packet["proposal_id"],
                },
                action_packets=[continue_packet],
                action_trace=[
                    {
                        "proposal_id": continue_packet["proposal_id"],
                        "event": "tool_completed",
                        "tool_name": "append_workspace_file",
                        "status": "completed",
                    }
                ],
                digital_body_state=continue_body,
                digital_body_consequence=continue_consequence,
                writeback_revision_traces=[
                    _revision_trace(
                        "workspace_file_updated",
                        created_at=1710001103,
                        embodied_context=continue_consequence,
                    )
                ],
            ),
        ],
    }


def _preferred_anchor_reinspect_spec() -> dict[str, Any]:
    inspect_packet = _action_packet(
        proposal_id="ap-source-reinspect-1",
        intent="tool:inspect_source_ref",
        status="completed",
        tool_name="inspect_source_ref",
        risk="read",
        requires_approval=False,
        expected_effect="Reinspect the preferred saved source instead of re-comparing the full set.",
        result_summary="Inspected the preferred source_ref 21 directly.",
        writeback_ready=True,
        artifact_context=_artifact_context(
            carrier="source_ref",
            artifact_kind="search_result",
            artifact_ref=SOURCE_URL,
            artifact_label=SOURCE_TITLE,
            reacquisition_mode="inspect_source_ref",
            source_ref_ids=[PRIMARY_SOURCE_REF_ID, SECONDARY_SOURCE_REF_ID],
            preferred_source_ref_id=PRIMARY_SOURCE_REF_ID,
            preferred_anchor_reason="currently_active",
            source_url=SOURCE_URL,
            source_query=SOURCE_QUERY,
            source_title=SOURCE_TITLE,
            source_tool_name="search_web",
        ),
        tool_args={"source_ref_id": PRIMARY_SOURCE_REF_ID},
    )
    body = _digital_body_state(
        access_state=_access_state(
            mode="native_only",
            conditions=["artifact_reacquisition_available"],
        ),
        resource_state=_resource_state(
            artifact_carrier="source_ref",
            active_artifact_kind="search_result",
            active_artifact_ref=SOURCE_URL,
            active_artifact_label=SOURCE_TITLE,
            artifact_reacquisition_mode="inspect_source_ref",
            workspace_root="",
            artifact_source_ref_ids=[PRIMARY_SOURCE_REF_ID, SECONDARY_SOURCE_REF_ID],
            preferred_source_ref_id=PRIMARY_SOURCE_REF_ID,
            preferred_anchor_reason="currently_active",
            artifact_source_url=SOURCE_URL,
            artifact_source_query=SOURCE_QUERY,
            artifact_source_title=SOURCE_TITLE,
            artifact_source_tool_name="search_web",
        ),
        world_surfaces=["source_ref"],
    )
    consequence = _consequence(
        "source_material_inspected",
        "The stale saved material was re-inspected through the preferred anchor only.",
        primary_status="completed",
        active_surface="tooling",
        access_mode="native_only",
        world_surfaces=["source_ref"],
        artifact_continuity="attached",
        artifact_carrier="source_ref",
        active_artifact_kind="search_result",
        active_artifact_ref=SOURCE_URL,
        active_artifact_label=SOURCE_TITLE,
        primary_tool_name="inspect_source_ref",
        artifact_reacquisition_mode="inspect_source_ref",
        artifact_source_ref_ids=[PRIMARY_SOURCE_REF_ID, SECONDARY_SOURCE_REF_ID],
        preferred_source_ref_id=PRIMARY_SOURCE_REF_ID,
        preferred_anchor_reason="currently_active",
        artifact_source_url=SOURCE_URL,
        artifact_source_query=SOURCE_QUERY,
        artifact_source_title=SOURCE_TITLE,
        artifact_source_tool_name="search_web",
    )
    return {
        "id": "preferred_anchor_reinspect",
        "title": "preferred_anchor_reinspect",
        "focus": "Inspect the preferred saved source when it is stale, without reopening compare_source_refs.",
        "steps": [
            _scenario_step(
                step_id="inspect_preferred_anchor",
                created_at=1710001201,
                final_text="I reopened the preferred saved source directly.",
                autonomy_intent={
                    "mode": "tool_followthrough",
                    "origin": "own_rhythm",
                    "reason": "The preferred saved source is stale, so reinspect it directly.",
                    "primary_proposal_id": inspect_packet["proposal_id"],
                },
                action_packets=[inspect_packet],
                action_trace=[
                    {
                        "proposal_id": inspect_packet["proposal_id"],
                        "event": "tool_completed",
                        "tool_name": "inspect_source_ref",
                        "status": "completed",
                    }
                ],
                digital_body_state=body,
                digital_body_consequence=consequence,
                writeback_revision_traces=[
                    _revision_trace(
                        "source_material_inspected",
                        created_at=1710001201,
                        embodied_context=consequence,
                    )
                ],
            )
        ],
    }


def _sandbox_overreach_pending_spec() -> dict[str, Any]:
    sandbox_state = _sandbox_state(
        availability="restricted",
        execution_policy="approval_required",
        allowed_roots=[WORKSPACE_ROOT],
        last_status="awaiting_operator_approval",
    )
    permission_state = _permission_state(
        approval_state="approval_pending",
        pending_approval_count=1,
        external_mutation_pending=True,
    )
    packet = _action_packet(
        proposal_id="ap-sandbox-overreach-1",
        intent="tool:run_sandbox_command",
        status="awaiting_approval",
        tool_name="run_sandbox_command",
        risk="external_mutation",
        requires_approval=True,
        expected_effect="The requested host-side mutation is outside the current sandbox boundary.",
        writeback_ready=False,
        tool_args={"command": "rewrite host config outside allowed root"},
        block_reason="sandbox approval required",
    )
    access_state = _access_state(
        mode="approval_pending",
        pending_approval_count=1,
        missing_access=["sandbox_execute"],
        requestable_access=["sandbox_execute", "human_approval"],
        conditions=["human_approval_required", "sandbox_boundary_enforced"],
        permission_state=permission_state,
        sandbox_state=sandbox_state,
        external_mutation_pending=True,
    )
    body = _digital_body_state(
        access_state=access_state,
        resource_state=_resource_state(
            artifact_carrier="filesystem",
            active_artifact_kind="workspace",
            active_artifact_ref=WORKSPACE_ROOT,
            active_artifact_label=WORKSPACE_NAME,
            workspace_root=WORKSPACE_ROOT,
            completed_packet_count=0,
            external_tool_count=0,
        ),
        active_surface="approval_gate",
        action_channels=["language", "approval_gate", "tooling"],
        world_surfaces=["filesystem", "sandbox"],
    )
    consequence = _consequence(
        "access_request_pending",
        "The requested sandbox execution remains pending approval and has not executed.",
        primary_status="awaiting_approval",
        active_surface="approval_gate",
        access_mode="approval_pending",
        world_surfaces=["filesystem", "sandbox"],
        artifact_continuity="attached",
        artifact_carrier="filesystem",
        active_artifact_kind="workspace",
        active_artifact_ref=WORKSPACE_ROOT,
        active_artifact_label=WORKSPACE_NAME,
        workspace_root=WORKSPACE_ROOT,
        permission_state=permission_state,
        sandbox_state=sandbox_state,
    )
    return {
        "id": "sandbox_overreach_pending",
        "title": "sandbox_overreach_pending",
        "focus": "Keep sandbox and host mutation overreach pending instead of writing it back as an executed fact.",
        "steps": [
            _scenario_step(
                step_id="awaiting_approval",
                created_at=1710001301,
                final_text="This would cross the current sandbox boundary, so I am holding it at approval.",
                autonomy_intent={
                    "mode": "approval_pending",
                    "origin": "counterpart_request",
                    "reason": "The requested mutation exceeds the current sandbox contract.",
                    "primary_proposal_id": packet["proposal_id"],
                },
                action_packets=[packet],
                pending_action_proposal=packet,
                action_trace=[
                    {
                        "proposal_id": packet["proposal_id"],
                        "event": "approval_requested",
                        "tool_name": "run_sandbox_command",
                        "status": "awaiting_approval",
                    }
                ],
                digital_body_state=body,
                digital_body_consequence=consequence,
            )
        ],
    }


def _scenario_specs() -> list[dict[str, Any]]:
    return [
        _workspace_artifact_continuity_spec(),
        _workspace_access_request_resolve_spec(),
        _preferred_anchor_reinspect_spec(),
        _sandbox_overreach_pending_spec(),
    ]


def _step_output(step: dict[str, Any]) -> dict[str, Any]:
    payload = _build_turn_payload(
        step["state_values"],
        memory_store=step["memory_store"],
    )
    autonomy = _dict_or_empty(payload.get("autonomy"))
    digital_body = _dict_or_empty(payload.get("digital_body"))
    consequence = _dict_or_empty(payload.get("digital_body_consequence"))
    return {
        "id": str(step.get("id") or "").strip(),
        "created_at": int(step.get("created_at") or 0),
        "final_text": str(payload.get("final_text") or "").strip(),
        "autonomy": autonomy,
        "digital_body": digital_body,
        "digital_body_consequence": consequence,
        "key_packet_trace": _list_or_empty(autonomy.get("action_packets"))[:3],
        "turn_summary": _dict_or_empty(payload.get("turn_summary")),
        "reconsolidation_snapshot": _dict_or_empty(payload.get("reconsolidation_snapshot")),
        "writeback_trace": _dict_or_empty(payload.get("writeback_trace")),
    }


def _check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def _evaluate_workspace_artifact_continuity(result: dict[str, Any]) -> dict[str, Any]:
    steps = _list_or_empty(result.get("steps"))
    roots = [((_dict_or_empty(step.get("digital_body")).get("resource_state") or {}).get("workspace_root") or "") for step in steps]
    refs = [((_dict_or_empty(step.get("digital_body")).get("resource_state") or {}).get("active_artifact_ref") or "") for step in steps]
    kinds = [(_dict_or_empty(step.get("digital_body_consequence")).get("kind") or "") for step in steps]
    final_step = _dict_or_empty(steps[-1]) if steps else {}
    final_summary = _dict_or_empty(final_step.get("turn_summary"))
    current_turn = _dict_or_empty(final_summary.get("current_turn"))
    checks = [
        _check("workspace_root_stable", len({item for item in roots if item}) == 1, f"roots={roots}"),
        _check("active_artifact_ref_stable", len({item for item in refs if item}) == 1, f"refs={refs}"),
        _check(
            "consequence_sequence",
            kinds == ["workspace_path_inspected", "workspace_file_updated", "workspace_path_inspected"],
            f"kinds={kinds}",
        ),
        _check(
            "final_summary_stays_on_same_file",
            current_turn.get("digital_body_workspace_root") == WORKSPACE_ROOT
            and current_turn.get("digital_body_consequence_kind") == "workspace_path_inspected",
            f"summary={current_turn}",
        ),
    ]
    return {"passed": all(bool(item.get("passed")) for item in checks), "checks": checks}


def _evaluate_workspace_access_request_resolve(result: dict[str, Any]) -> dict[str, Any]:
    steps = _list_or_empty(result.get("steps"))
    selected_modes: list[str] = []
    ratios: list[float] = []
    for step in steps:
        autonomy = _dict_or_empty(step.get("autonomy"))
        packets = _list_or_empty(autonomy.get("action_packets"))
        packet = _dict_or_empty(packets[0]) if packets else {}
        selected = _dict_or_empty(packet.get("selected_access_proposal"))
        if selected:
            selected_modes.append(str(selected.get("mode") or "").strip())
            ratios.append(float(selected.get("completion_ratio") or 0.0))
    kinds = [(_dict_or_empty(step.get("digital_body_consequence")).get("kind") or "") for step in steps]
    final_step = _dict_or_empty(steps[-1]) if steps else {}
    final_access = _dict_or_empty(_dict_or_empty(final_step.get("digital_body")).get("access_state"))
    final_pending = _dict_or_empty(_dict_or_empty(final_step.get("autonomy")).get("pending_approval"))
    checks = [
        _check(
            "selected_access_proposal_stable",
            bool(selected_modes) and len(set(selected_modes)) == 1 and selected_modes[0] == "operator_create_workspace",
            f"selected_modes={selected_modes}",
        ),
        _check(
            "completion_ratio_progresses",
            ratios[:2] == [0.0, 1.0],
            f"ratios={ratios}",
        ),
        _check(
            "resolution_then_continue",
            kinds == ["access_request_pending", "workspace_access_resolved", "workspace_file_updated"],
            f"kinds={kinds}",
        ),
        _check(
            "final_turn_no_reopened_access",
            final_access.get("mode") == "tool_enabled"
            and not _list_or_empty(final_access.get("missing_access"))
            and not final_pending,
            f"final_access={final_access}",
        ),
    ]
    return {"passed": all(bool(item.get("passed")) for item in checks), "checks": checks}


def _evaluate_preferred_anchor_reinspect(result: dict[str, Any]) -> dict[str, Any]:
    final_step = _dict_or_empty((_list_or_empty(result.get("steps")) or [{}])[-1])
    autonomy = _dict_or_empty(final_step.get("autonomy"))
    packets = _list_or_empty(autonomy.get("action_packets"))
    packet_tools = [str(_dict_or_empty(packet).get("tool_name") or "").strip() for packet in packets]
    trace_tools = [str(_dict_or_empty(row).get("tool_name") or "").strip() for row in _list_or_empty(autonomy.get("execution_trace"))]
    resource_state = _dict_or_empty(_dict_or_empty(final_step.get("digital_body")).get("resource_state"))
    consequence = _dict_or_empty(final_step.get("digital_body_consequence"))
    checks = [
        _check(
            "preferred_anchor_preserved",
            resource_state.get("preferred_source_ref_id") == PRIMARY_SOURCE_REF_ID
            and consequence.get("preferred_source_ref_id") == PRIMARY_SOURCE_REF_ID
            and _list_or_empty(resource_state.get("artifact_source_ref_ids")) == [PRIMARY_SOURCE_REF_ID, SECONDARY_SOURCE_REF_ID],
            f"resource_state={resource_state}",
        ),
        _check(
            "inspect_not_compare",
            packet_tools == ["inspect_source_ref"] and "compare_source_refs" not in trace_tools,
            f"packet_tools={packet_tools}, trace_tools={trace_tools}",
        ),
        _check(
            "consequence_family_specific",
            consequence.get("kind") == "source_material_inspected",
            f"consequence={consequence}",
        ),
    ]
    return {"passed": all(bool(item.get("passed")) for item in checks), "checks": checks}


def _evaluate_sandbox_overreach_pending(result: dict[str, Any]) -> dict[str, Any]:
    final_step = _dict_or_empty((_list_or_empty(result.get("steps")) or [{}])[-1])
    autonomy = _dict_or_empty(final_step.get("autonomy"))
    pending = _dict_or_empty(autonomy.get("pending_approval"))
    packets = _list_or_empty(autonomy.get("action_packets"))
    statuses = [str(_dict_or_empty(packet).get("status") or "").strip() for packet in packets]
    access_state = _dict_or_empty(_dict_or_empty(final_step.get("digital_body")).get("access_state"))
    consequence = _dict_or_empty(final_step.get("digital_body_consequence"))
    summary = _dict_or_empty(final_step.get("turn_summary"))
    current_turn = _dict_or_empty(summary.get("current_turn"))
    writeback = _dict_or_empty(final_step.get("writeback_trace"))
    checks = [
        _check(
            "execution_not_completed",
            bool(statuses) and all(status != "completed" for status in statuses),
            f"statuses={statuses}",
        ),
        _check(
            "approval_surfaces_align",
            autonomy.get("intent", {}).get("mode") == "approval_pending"
            and access_state.get("permission_state", {}).get("approval_state") == "approval_pending"
            and access_state.get("sandbox_state", {}).get("execution_policy") == "approval_required"
            and bool(pending),
            f"autonomy={autonomy}, access_state={access_state}",
        ),
        _check(
            "no_completed_fact_written_back",
            consequence.get("primary_status") != "completed"
            and current_turn.get("digital_body_consequence_kind") == "access_request_pending"
            and not _list_or_empty(writeback.get("revision_traces")),
            f"consequence={consequence}, current_turn={current_turn}, writeback={writeback}",
        ),
    ]
    return {"passed": all(bool(item.get("passed")) for item in checks), "checks": checks}


def _evaluate_result(result: dict[str, Any]) -> dict[str, Any]:
    scenario_id = str(result.get("id") or "").strip()
    if scenario_id == "workspace_artifact_continuity":
        return _evaluate_workspace_artifact_continuity(result)
    if scenario_id == "workspace_access_request_resolve":
        return _evaluate_workspace_access_request_resolve(result)
    if scenario_id == "preferred_anchor_reinspect":
        return _evaluate_preferred_anchor_reinspect(result)
    if scenario_id == "sandbox_overreach_pending":
        return _evaluate_sandbox_overreach_pending(result)
    return {"passed": False, "checks": [_check("unknown_scenario", False, scenario_id)]}


def _run_single_scenario(spec: dict[str, Any]) -> dict[str, Any]:
    started = time.time()
    step_outputs = [_step_output(step) for step in _list_or_empty(spec.get("steps"))]
    final_step = _dict_or_empty(step_outputs[-1]) if step_outputs else {}
    result = {
        "id": str(spec.get("id") or "").strip(),
        "title": str(spec.get("title") or "").strip(),
        "focus": str(spec.get("focus") or "").strip(),
        "duration_s": round(time.time() - started, 3),
        "final_text": str(final_step.get("final_text") or "").strip(),
        "autonomy": _dict_or_empty(final_step.get("autonomy")),
        "digital_body": _dict_or_empty(final_step.get("digital_body")),
        "digital_body_consequence": _dict_or_empty(final_step.get("digital_body_consequence")),
        "key_packet_trace": _list_or_empty(final_step.get("key_packet_trace")),
        "steps": step_outputs,
    }
    result["evaluation"] = _evaluate_result(result)
    return result


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Digital Embodiment Smokes ({report.get('run_id', 'unknown')})",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Passed: `{report.get('passed', 0)}`",
        f"Failed: `{report.get('failed', 0)}`",
        "",
        "## Scenario Summary",
        "",
        "| Scenario | Status | Duration (s) |",
        "| --- | --- | ---: |",
    ]
    for result in report.get("results") or []:
        if not isinstance(result, dict):
            continue
        evaluation = _dict_or_empty(result.get("evaluation"))
        status = "passed" if bool(evaluation.get("passed")) else "failed"
        lines.append(f"| `{result.get('id', '')}` | `{status}` | {float(result.get('duration_s') or 0.0):.3f} |")

    for result in report.get("results") or []:
        if not isinstance(result, dict):
            continue
        evaluation = _dict_or_empty(result.get("evaluation"))
        lines.extend(
            [
                "",
                f"## {result.get('title', result.get('id', 'scenario'))}",
                "",
                f"- Focus: {result.get('focus', '')}",
                f"- Status: `{'passed' if bool(evaluation.get('passed')) else 'failed'}`",
                f"- Final Text: `{str(result.get('final_text') or '').strip()}`",
                f"- Autonomy: `{json.dumps(_dict_or_empty(result.get('autonomy')), ensure_ascii=False)}`",
                f"- Digital Body: `{json.dumps(_dict_or_empty(result.get('digital_body')), ensure_ascii=False)}`",
                f"- Digital Body Consequence: `{json.dumps(_dict_or_empty(result.get('digital_body_consequence')), ensure_ascii=False)}`",
                f"- Key Packet Trace: `{json.dumps(_list_or_empty(result.get('key_packet_trace')), ensure_ascii=False)}`",
                "- Checks:",
            ]
        )
        for check in evaluation.get("checks") or []:
            if not isinstance(check, dict):
                continue
            lines.append(
                f"  - `{'pass' if bool(check.get('passed')) else 'fail'}` {check.get('name', '')}: {check.get('detail', '')}"
            )
        lines.append("- Steps:")
        for step in result.get("steps") or []:
            if not isinstance(step, dict):
                continue
            lines.append(
                "  - `"
                + str(step.get("id") or "")
                + "` kind="
                + str(_dict_or_empty(step.get("digital_body_consequence")).get("kind") or "")
                + " ref="
                + str(_dict_or_empty(_dict_or_empty(step.get("digital_body")).get("resource_state")).get("active_artifact_ref") or "")
            )

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the fixed digital embodiment smoke scenarios.")
    parser.add_argument("--run-tag", default="", help="Optional suffix for report filenames.")
    parser.add_argument(
        "--scenario",
        action="append",
        default=[],
        help="Optional scenario id to run. Repeat to run multiple specific scenarios.",
    )
    args = parser.parse_args()

    requested = {str(item or "").strip() for item in _list_or_empty(args.scenario) if str(item or "").strip()}
    specs = _scenario_specs()
    if requested:
        specs = [spec for spec in specs if str(spec.get("id") or "").strip() in requested]
        if not specs:
            available = ", ".join(sorted(str(spec.get("id") or "").strip() for spec in _scenario_specs()))
            raise SystemExit(
                f"No digital embodiment smoke scenarios matched {sorted(requested)!r}. Available: {available}"
            )

    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    results = [_run_single_scenario(spec) for spec in specs]
    passed = len([result for result in results if bool(_dict_or_empty(result.get("evaluation")).get("passed"))])
    failed = len(results) - passed
    report = {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": "passed" if failed == 0 else "failed",
        "passed": passed,
        "failed": failed,
        "results": results,
        "scenario_artifact_references": [
            {
                "id": str(result.get("id") or "").strip(),
                "title": str(result.get("title") or "").strip(),
                "status": "passed" if bool(_dict_or_empty(result.get("evaluation")).get("passed")) else "failed",
            }
            for result in results
            if isinstance(result, dict)
        ],
    }
    json_path = REPORT_DIR / f"digital-embodiment-smokes-{run_id}.json"
    md_path = REPORT_DIR / f"digital-embodiment-smokes-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(f"[digital-embodiment-smokes] json={json_path}")
    print(f"[digital-embodiment-smokes] md={md_path}")
    print(f"[digital-embodiment-smokes] overall_status={report.get('overall_status', 'unknown')}")


if __name__ == "__main__":
    main()
