from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import uuid
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from amadeus_thread0.evolution_engine.reconsolidation import build_reconsolidation_snapshot
from amadeus_thread0.graph_parts.action_packets import build_tool_action_packet, normalize_action_packet
from amadeus_thread0.graph_parts.memory_evolution import _record_digital_body_consequence
from amadeus_thread0.graph_parts.relational_carryover import _apply_retrieved_behavior_trace_bridge
from amadeus_thread0.graph_parts.skill_runtime import backend_skill_envelope
from amadeus_thread0.memory_store import MemoryStore
from amadeus_thread0.runtime.skill_registry import SkillRegistryManager

REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
TMP_ROOT = PROJECT_ROOT / "evals" / "_tmp" / "skills-ecosystem"
TMP_ROOT.mkdir(parents=True, exist_ok=True)


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _source_ref_body() -> dict[str, Any]:
    return {
        "active_surface": "tooling",
        "perception_channels": ["dialogue", "source_ref"],
        "action_channels": ["language", "structured_action", "tooling"],
        "world_surfaces": ["source_ref", "saved_material"],
        "access_state": {"mode": "tool_enabled", "network_access": "enabled", "filesystem_state": "writable"},
        "resource_state": {
            "artifact_continuity": "attached",
            "active_artifact_kind": "search_result",
            "active_artifact_ref": "https://docs.langchain.com/oss/python/langgraph/persistence",
            "active_artifact_label": "LangGraph Persistence",
            "artifact_carrier": "source_ref",
            "artifact_source_ref_ids": [21, 17],
            "preferred_source_ref_id": 21,
            "preferred_anchor_reason": "primary_more_current",
            "artifact_source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
            "artifact_source_query": "langgraph persistence checkpointer thread",
            "artifact_source_title": "LangGraph Persistence",
            "artifact_source_tool_name": "search_web",
        },
    }


def _workspace_body(workspace_root: Path) -> dict[str, Any]:
    root = str(workspace_root).replace("\\", "/")
    return {
        "active_surface": "tooling",
        "perception_channels": ["dialogue", "filesystem"],
        "action_channels": ["language", "structured_action", "tooling"],
        "world_surfaces": ["filesystem", "sandbox"],
        "access_state": {
            "mode": "tool_enabled",
            "filesystem_state": "writable",
            "sandbox_mode": "restricted",
            "sandbox_state": {
                "availability": "restricted",
                "allowed_roots": [root],
                "execution_policy": "approval_required",
                "runner_kind": "local_restricted_runner",
                "isolation_level": "host_local_restricted",
                "arbitrary_execution": False,
            },
        },
        "resource_state": {
            "artifact_continuity": "attached",
            "active_artifact_kind": "workspace",
            "active_artifact_ref": root,
            "active_artifact_label": workspace_root.name,
            "artifact_carrier": "filesystem",
            "workspace_root": root,
        },
    }


def _skill_markdown(*, skill_id: str, description: str, version: str, triggers: list[str], required_surfaces: list[str], allowed_tools: list[str], sandbox_profiles: list[str]) -> str:
    return "\n".join([
        "---",
        f"name: {skill_id}",
        f"description: {description}",
        f"version: {version}",
        f"skill_id: {skill_id}",
        "kind: executable",
        f"triggers: {json.dumps(triggers)}",
        f"required_surfaces: {json.dumps(required_surfaces)}",
        f"allowed_tools: {json.dumps(allowed_tools)}",
        f"sandbox_profiles: {json.dumps(sandbox_profiles)}",
        "source: official_registry",
        "trust_tier: verified",
        "---",
        "## Use",
        f"- Use {skill_id} when its trigger family is active.",
        "",
    ])


def _build_remote_archive(root: Path, *, skill_id: str, version: str) -> tuple[Path, str]:
    archive_path = root / f"{skill_id}-{version}.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(
            "SKILL.md",
            _skill_markdown(
                skill_id=skill_id,
                description=f"{skill_id} remote package",
                version=version,
                triggers=["anchor", "source_ref", "official"],
                required_surfaces=["source_ref"],
                allowed_tools=["search_web", "inspect_source_ref"],
                sandbox_profiles=[],
            ),
        )
        archive.writestr("scripts/run.py", "print('skill package ready')\n")
    return archive_path, hashlib.sha256(archive_path.read_bytes()).hexdigest()


def _write_remote_catalog(path: Path, *, skill_id: str, version: str, package_url: str, package_hash: str) -> None:
    payload = {
        "skills": [{
            "skill_id": skill_id,
            "name": skill_id,
            "description": f"{skill_id} remote package",
            "version": version,
            "kind": "executable",
            "source": "official_registry",
            "trust_tier": "verified",
            "status": "catalog_remote",
            "required_surfaces": ["source_ref"],
            "allowed_tools": ["search_web", "inspect_source_ref"],
            "sandbox_profiles": [],
            "requested_permissions": ["filesystem_read"],
            "hash": package_hash,
            "package_url": package_url,
            "verification_summary": "registry verified",
        }]
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _skill_artifact_context(path: str, label: str) -> dict[str, Any]:
    return {"carrier": "filesystem", "artifact_kind": "directory", "artifact_ref": path, "artifact_label": label, "reacquisition_mode": "inspect_registry_entry", "exists": True}


def _source_artifact_context(body: dict[str, Any]) -> dict[str, Any]:
    resource = _dict(body.get("resource_state"))
    return {
        "carrier": "source_ref",
        "artifact_kind": str(resource.get("active_artifact_kind") or "search_result"),
        "artifact_ref": str(resource.get("active_artifact_ref") or ""),
        "artifact_label": str(resource.get("active_artifact_label") or ""),
        "reacquisition_mode": "inspect_source_ref",
        "source_ref_ids": list(resource.get("artifact_source_ref_ids") or []),
        "preferred_source_ref_id": resource.get("preferred_source_ref_id"),
        "preferred_anchor_reason": str(resource.get("preferred_anchor_reason") or ""),
        "source_url": str(resource.get("artifact_source_url") or ""),
        "source_query": str(resource.get("artifact_source_query") or ""),
        "source_title": str(resource.get("artifact_source_title") or ""),
        "source_tool_name": str(resource.get("artifact_source_tool_name") or ""),
    }


def _packet(*, tool_name: str, proposal_id: str, args: dict[str, Any], status: str, result_summary: str, action: str = "", block_reason: str = "", artifact_context: dict[str, Any] | None = None) -> dict[str, Any]:
    packet = build_tool_action_packet(tool_name=tool_name, proposal_id=proposal_id, args=args, action=action, status=status, result_summary=result_summary, block_reason=block_reason)
    if artifact_context:
        packet["artifact_context"] = dict(artifact_context)
    return normalize_action_packet(packet)


def _intent(packet: dict[str, Any], mode: str) -> dict[str, Any]:
    return {"mode": mode, "origin": str(packet.get("origin") or "motive_goal"), "reason": "skills ecosystem smoke", "primary_proposal_id": str(packet.get("proposal_id") or "")}


def _step(step_id: str, final_text: str, *, current_event: dict[str, Any], digital_body: dict[str, Any], session_skill_state: dict[str, Any], action_packets: list[dict[str, Any]], mode: str, pending_action_proposal: dict[str, Any] | None = None, action_trace: list[dict[str, Any]] | None = None, interaction_carryover: dict[str, Any] | None = None) -> dict[str, Any]:
    trace = list(action_trace or [])
    carryover = dict(interaction_carryover or {})
    snapshot = build_reconsolidation_snapshot(
        current_event=current_event,
        appraisal={"interaction_frame": "task"},
        world_model_state={},
        semantic_narrative_profile={},
        latent_state={"self_coherence": 0.82},
        emotion_state={"label": "focused"},
        bond_state={"trust": 0.62},
        behavior_action={"interaction_mode": "tooling", "primary_motive": "maintain_capability_continuity"},
        interaction_carryover=carryover,
        autonomy_intent=_intent(action_packets[0], mode) if action_packets else {},
        action_packets=action_packets,
        action_trace=trace,
        digital_body_state=digital_body,
        session_skill_state=session_skill_state,
    )
    consequence = _dict(snapshot.get("digital_body_consequence"))
    skills = backend_skill_envelope(session_skill_state, pending_action_proposal=pending_action_proposal)
    return {
        "id": step_id,
        "final_text": final_text,
        "skills": skills,
        "autonomy": {"intent": _intent(action_packets[0], mode) if action_packets else {}, "action_packets": list(action_packets), "pending_approval": dict(skills.get("pending_approval") or {}), "execution_trace": trace, "block_reason": str(consequence.get("block_reason") or "")},
        "digital_body": digital_body,
        "digital_body_consequence": consequence,
        "key_packet_trace": list(action_packets),
        "reconsolidation_snapshot": snapshot,
        "interaction_carryover": carryover,
    }

def _sc_local_skill_discovery_and_progressive_disclosure(run_root: Path) -> dict[str, Any]:
    manager = SkillRegistryManager(base_dir=PROJECT_ROOT, data_dir=run_root / "local-runtime")
    thread_id = "skills-local-source"
    query = "继续沿着 preferred source_ref anchor 看前面那条材料 continuity"
    current_event = {"kind": "user_utterance", "text": query}
    digital_body = _source_ref_body()
    session_state = manager.compute_session_skill_state(thread_id=thread_id, query_text=query, current_event=current_event, digital_body_state=digital_body)
    inspected = manager.inspect("source-ref-anchor-review")
    packet = _packet(tool_name="inspect_source_ref", proposal_id="ap-skill-local-source-1", args={"source_ref_id": 21}, status="completed", result_summary="先按 preferred anchor 检查了保存材料。", artifact_context=_source_artifact_context(digital_body))
    step = _step(
        "inspect_preferred_anchor",
        "本地 authored skill 已经被命中，当前只按需展开了这一条的说明。",
        current_event=current_event,
        digital_body=digital_body,
        session_skill_state=session_state,
        action_packets=[packet],
        mode="tool_completed",
        action_trace=[{"proposal_id": "ap-skill-local-source-1", "event": "tool_completed", "tool_name": "inspect_source_ref", "status": "completed"}],
    )
    return {
        "id": "local_skill_discovery_and_progressive_disclosure",
        "title": "local_skill_discovery_and_progressive_disclosure",
        "focus": "Repo-owned authored skills should be discoverable, matched, and only fully disclosed on demand.",
        "steps": [step],
        "inspection": inspected,
    }


def _sc_remote_install_proposal_approval_install_enable(run_root: Path) -> dict[str, Any]:
    catalog_root = run_root / "remote-install"
    catalog_root.mkdir(parents=True, exist_ok=True)
    catalog_path = catalog_root / "catalog.json"
    skill_id = "official-anchor-assist"
    version = "1.0.0"
    archive_path, digest = _build_remote_archive(catalog_root, skill_id=skill_id, version=version)
    _write_remote_catalog(catalog_path, skill_id=skill_id, version=version, package_url=str(archive_path), package_hash=digest)
    runtime_root = run_root / "remote-install-runtime"
    manager = SkillRegistryManager(base_dir=PROJECT_ROOT, data_dir=runtime_root, registry_url=str(catalog_path), allow_local_remote_source=True)
    thread_id = "skills-remote-install"
    query = "给我装那个官方 source ref anchor skill"
    current_event = {"kind": "user_utterance", "text": query}
    digital_body = {**_source_ref_body(), "resource_state": {**_dict(_source_ref_body().get("resource_state")), "artifact_carrier": "filesystem", "active_artifact_kind": "directory", "active_artifact_ref": "", "active_artifact_label": "skills-registry", "workspace_root": str(runtime_root.resolve()).replace('\\', '/')}}
    preview = manager.preview_operation(operation="install", skill_id=skill_id)
    resolved_args = {"skill_id": preview["skill_id"], "resolved_version": preview["resolved_version"], "source": preview["source"], "hash": preview["hash"], "requested_permissions": list(preview.get("requested_permissions") or []), "sandbox_profiles": list(preview.get("sandbox_profiles") or []), "verification_summary": preview["verification_summary"]}
    pending_proposal = {"proposal_id": "ap-skill-install-1", "tool_name": "install_skill", "tool_args": resolved_args}
    pending_packet = _packet(tool_name="install_skill", proposal_id="ap-skill-install-1", args=resolved_args, action="approve", status="awaiting_approval", result_summary="远程 skill 安装提案已经固定，正在等待审批。")
    pending_step = _step(
        "awaiting_install_approval",
        "远程 install 现在还只是提案，能力还没有真正进入身体面。",
        current_event=current_event,
        digital_body=digital_body,
        session_skill_state=manager.compute_session_skill_state(thread_id=thread_id, query_text=query, current_event=current_event, digital_body_state=digital_body),
        action_packets=[pending_packet],
        mode="approval_pending",
        pending_action_proposal=pending_proposal,
        action_trace=[{"proposal_id": "ap-skill-install-1", "event": "approval_requested", "tool_name": "install_skill", "status": "awaiting_approval"}],
    )
    installed = manager.install(skill_id=preview["skill_id"], resolved_version=preview["resolved_version"], source=preview["source"], hash_value=preview["hash"], requested_permissions=preview["requested_permissions"], sandbox_profiles=preview["sandbox_profiles"], verification_summary=preview["verification_summary"])
    install_body = {**digital_body, "resource_state": {**_dict(digital_body.get("resource_state")), "active_artifact_ref": str(installed.get("installed_path") or ""), "active_artifact_label": f"{skill_id}@{version}"}}
    install_packet = _packet(tool_name="install_skill", proposal_id="ap-skill-install-1", args=resolved_args, action="approve", status="completed", result_summary=f"installed {skill_id}@{version}", artifact_context=_skill_artifact_context(str(installed.get("installed_path") or ""), f"{skill_id}@{version}"))
    install_step = _step(
        "install_completed",
        "安装已经真实落盘，但还没有自动变成当前会话的激活能力。",
        current_event=current_event,
        digital_body=install_body,
        session_skill_state=manager.compute_session_skill_state(thread_id=thread_id, query_text=query, current_event=current_event, digital_body_state=install_body),
        action_packets=[install_packet],
        mode="tool_completed",
        action_trace=[{"proposal_id": "ap-skill-install-1", "event": "approval_resolved", "tool_name": "install_skill", "status": "approved"}, {"proposal_id": "ap-skill-install-1", "event": "tool_completed", "tool_name": "install_skill", "status": "completed"}],
    )
    manager.enable(skill_id=skill_id, thread_id=thread_id)
    enable_event = {"kind": "user_utterance", "text": "启用刚装好的 source ref anchor skill"}
    enable_packet = _packet(tool_name="enable_skill", proposal_id="ap-skill-enable-1", args={"skill_id": skill_id}, action="approve", status="completed", result_summary=f"enabled {skill_id}@{version}", artifact_context=_skill_artifact_context(str(installed.get("installed_path") or ""), f"{skill_id}@{version}"))
    enable_step = _step(
        "enable_completed",
        "这条 remote skill 现在才算真正进入当前 session 的 active layer。",
        current_event=enable_event,
        digital_body=install_body,
        session_skill_state=manager.compute_session_skill_state(thread_id=thread_id, query_text=enable_event["text"], current_event=enable_event, digital_body_state=install_body),
        action_packets=[enable_packet],
        mode="tool_completed",
        action_trace=[{"proposal_id": "ap-skill-enable-1", "event": "tool_completed", "tool_name": "enable_skill", "status": "completed"}],
    )
    return {
        "id": "remote_install_proposal_approval_install_enable",
        "title": "remote_install_proposal_approval_install_enable",
        "focus": "Remote install must stay proposal-gated, then land the same resolved payload, then require explicit enable for session activation.",
        "steps": [pending_step, install_step, enable_step],
        "preview": preview,
        "registry_path": runtime_root / "skills" / "registry.json",
        "lock_path": runtime_root / "skills" / "installed" / skill_id / version / "skill.lock.json",
        "skill_id": skill_id,
    }

def _sc_auto_match_with_manual_disable_and_pin_precedence(run_root: Path) -> dict[str, Any]:
    manager = SkillRegistryManager(base_dir=PROJECT_ROOT, data_dir=run_root / "manual-runtime")
    thread_id = "skills-manual-precedence"
    workspace_root = run_root / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    digital_body = _workspace_body(workspace_root)
    query = "请先跑下 workspace 里的 pytest regression"
    current_event = {"kind": "user_utterance", "text": query}
    auto_state = manager.compute_session_skill_state(thread_id=thread_id, query_text=query, current_event=current_event, digital_body_state=digital_body)
    auto_packet = _packet(tool_name="list_runtime_skills", proposal_id="ap-skill-list-1", args={"query": query}, status="completed", result_summary="自动匹配出了当前最相关的 workspace skill。")
    auto_step = _step("auto_matched", "默认自动匹配会先命中 workspace regression triage 这条 skill。", current_event=current_event, digital_body=digital_body, session_skill_state=auto_state, action_packets=[auto_packet], mode="tool_completed")
    manager.disable(skill_id="workspace-regression-triage", thread_id=thread_id)
    disabled_state = manager.compute_session_skill_state(thread_id=thread_id, query_text=query, current_event=current_event, digital_body_state=digital_body)
    disabled_packet = _packet(tool_name="disable_skill", proposal_id="ap-skill-disable-1", args={"skill_id": "workspace-regression-triage"}, action="approve", status="completed", result_summary="disabled workspace-regression-triage")
    disabled_step = _step("manual_disabled", "手动禁用之后，自动匹配还在，但 active layer 不再把它接进来。", current_event=current_event, digital_body=digital_body, session_skill_state=disabled_state, action_packets=[disabled_packet], mode="tool_completed")
    manager.pin(skill_id="source-ref-anchor-review", thread_id=thread_id)
    pinned_state = manager.compute_session_skill_state(thread_id=thread_id, query_text=query, current_event=current_event, digital_body_state=digital_body)
    pinned_packet = _packet(tool_name="pin_skill", proposal_id="ap-skill-pin-1", args={"skill_id": "source-ref-anchor-review"}, action="approve", status="completed", result_summary="pinned source-ref-anchor-review")
    pinned_step = _step("manual_pin_completed", "手动 pin 会压过普通自动匹配，把指定 skill 放到当前 active layer 的前面。", current_event=current_event, digital_body=digital_body, session_skill_state=pinned_state, action_packets=[pinned_packet], mode="tool_completed")
    return {"id": "auto_match_with_manual_disable_and_pin_precedence", "title": "auto_match_with_manual_disable_and_pin_precedence", "focus": "Auto-match should work by default, manual disable should suppress it, and pin should take active-layer precedence.", "steps": [auto_step, disabled_step, pinned_step]}


def _sc_blocked_or_rejected_skill_mutation_does_not_become_capability(run_root: Path) -> dict[str, Any]:
    catalog_root = run_root / "blocked-mutation"
    catalog_root.mkdir(parents=True, exist_ok=True)
    catalog_path = catalog_root / "catalog.json"
    skill_id = "blocked-anchor-pack"
    archive_path, digest = _build_remote_archive(catalog_root, skill_id=skill_id, version="1.0.0")
    _write_remote_catalog(catalog_path, skill_id=skill_id, version="1.0.0", package_url=str(archive_path), package_hash=digest)
    manager = SkillRegistryManager(base_dir=PROJECT_ROOT, data_dir=run_root / "blocked-runtime", registry_url=str(catalog_path), allow_local_remote_source=True)
    query = "先别装，看看这个 remote skill"
    current_event = {"kind": "user_utterance", "text": query}
    digital_body = _source_ref_body()
    preview = manager.preview_operation(operation="install", skill_id=skill_id)
    blocked_packet = _packet(tool_name="install_skill", proposal_id="ap-skill-blocked-1", args={"skill_id": preview["skill_id"], "resolved_version": preview["resolved_version"], "source": preview["source"], "hash": preview["hash"], "requested_permissions": list(preview.get("requested_permissions") or []), "sandbox_profiles": list(preview.get("sandbox_profiles") or []), "verification_summary": preview["verification_summary"]}, action="approve", status="blocked", result_summary="remote install was blocked before execution", block_reason="operator rejected the capability mutation")
    blocked_step = _step(
        "mutation_blocked",
        "这次 skill 变更没有真正落地，所以不会被写成已经拥有的新能力。",
        current_event=current_event,
        digital_body=digital_body,
        session_skill_state=manager.compute_session_skill_state(thread_id="skills-blocked", query_text=query, current_event=current_event, digital_body_state=digital_body),
        action_packets=[blocked_packet],
        mode="blocked",
        action_trace=[{"proposal_id": "ap-skill-blocked-1", "event": "skill_mutation_blocked", "tool_name": "install_skill", "status": "blocked"}],
    )
    return {"id": "blocked_or_rejected_skill_mutation_does_not_become_capability", "title": "blocked_or_rejected_skill_mutation_does_not_become_capability", "focus": "Blocked or rejected skill mutations must remain blocked intentions, not acquired capability facts.", "steps": [blocked_step], "installed_after": manager.installed_skills(), "runtime_after": manager.list_runtime(thread_id="skills-blocked"), "skill_id": skill_id}


def _sc_completed_skill_usage_resurfaces_in_followup_continuity(run_root: Path) -> dict[str, Any]:
    manager = SkillRegistryManager(base_dir=PROJECT_ROOT, data_dir=run_root / "followup-runtime")
    thread_id = "skills-followup"
    manager.pin(skill_id="source-ref-anchor-review", thread_id=thread_id)
    digital_body = _source_ref_body()
    query = "继续用 source_ref anchor 那条技能把资料线索接起来"
    current_event = {"kind": "user_utterance", "text": query}
    session_state = manager.compute_session_skill_state(thread_id=thread_id, query_text=query, current_event=current_event, digital_body_state=digital_body)
    usage_packet = _packet(tool_name="search_web", proposal_id="ap-skill-usage-1", args={"query": "langgraph persistence checkpointer"}, status="completed", result_summary="顺着 source_ref continuity 重新补了一轮相关材料。", artifact_context=_source_artifact_context(digital_body))
    usage_step = _step("usage_completed", "这条 skill 这次已经真正参与过动作了，后面要能沿着它留下的连续性继续。", current_event=current_event, digital_body=digital_body, session_skill_state=session_state, action_packets=[usage_packet], mode="tool_completed", action_trace=[{"proposal_id": "ap-skill-usage-1", "event": "tool_completed", "tool_name": "search_web", "status": "completed"}])
    with TemporaryDirectory() as td:
        store = MemoryStore(Path(td) / "memory.json")
        try:
            _record_digital_body_consequence(store, digital_body_state=digital_body, reconsolidation_snapshot=usage_step["reconsolidation_snapshot"], source="skills-smoke", confidence=0.88)
            retrieved = {"digital_body_consequence_traces": store.list_revision_traces(limit=8)}
        finally:
            store.close()
    followup_event, followup_carryover = _apply_retrieved_behavior_trace_bridge(retrieved=retrieved, current_event={"kind": "user_utterance", "text": "那就顺着刚才那条 skill 的线索继续"}, interaction_carryover={})
    followup_packet = _packet(tool_name="inspect_source_ref", proposal_id="ap-skill-followup-1", args={"source_ref_id": 21}, status="completed", result_summary="继续沿着刚才那条 skill 带出来的 anchor 检查材料。", artifact_context=_source_artifact_context(digital_body))
    followup_step = _step(
        "followup_continuity",
        "后续回合确实顺着那次 skill 使用留下的连续性继续了，而不是把它丢成一次性说明。",
        current_event=followup_event,
        digital_body=digital_body,
        session_skill_state=session_state,
        action_packets=[followup_packet],
        mode="continue",
        interaction_carryover=followup_carryover,
        action_trace=[{"proposal_id": "ap-skill-usage-1", "event": "digital_body_trace_resurfaced", "tool_name": "search_web", "status": "completed"}, {"proposal_id": "ap-skill-followup-1", "event": "tool_completed", "tool_name": "inspect_source_ref", "status": "completed"}],
    )
    return {"id": "completed_skill_usage_resurfaces_in_followup_continuity", "title": "completed_skill_usage_resurfaces_in_followup_continuity", "focus": "Completed skill usage should write truthful embodied residue that resurfaces in later continuity.", "steps": [usage_step, followup_step]}


def _scenario_specs(run_root: Path) -> list[dict[str, Any]]:
    return [
        _sc_local_skill_discovery_and_progressive_disclosure(run_root),
        _sc_remote_install_proposal_approval_install_enable(run_root),
        _sc_auto_match_with_manual_disable_and_pin_precedence(run_root),
        _sc_blocked_or_rejected_skill_mutation_does_not_become_capability(run_root),
        _sc_completed_skill_usage_resurfaces_in_followup_continuity(run_root),
    ]


def _check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}

def _evaluate(result: dict[str, Any]) -> dict[str, Any]:
    scenario_id = str(result.get("id") or "")
    steps = _list(result.get("steps"))
    if scenario_id == "local_skill_discovery_and_progressive_disclosure":
        step = _dict(steps[-1])
        skills = _dict(step.get("skills"))
        active = _list(skills.get("active"))
        installed = _list(skills.get("installed"))
        inspected = _dict(result.get("inspection"))
        checks = [
            _check("repo_owned_skill_discovered", any(_dict(item).get("skill_id") == "source-ref-anchor-review" for item in installed), json.dumps(installed, ensure_ascii=False)),
            _check("catalog_stays_compact", all("skill_excerpt" not in _dict(item) for item in installed), json.dumps(installed, ensure_ascii=False)),
            _check("active_discloses_excerpt", bool(_dict(active[0]).get("skill_excerpt")) if active else False, json.dumps(active, ensure_ascii=False)),
            _check("inspect_loads_full_skill_md", "Inspect the preferred saved source first." in str(inspected.get("skill_excerpt") or ""), json.dumps(inspected, ensure_ascii=False)),
        ]
    elif scenario_id == "remote_install_proposal_approval_install_enable":
        pending = _dict(steps[0])
        installed = _dict(steps[1])
        enabled = _dict(steps[2])
        preview = _dict(result.get("preview"))
        pending_payload = _dict(_dict(pending.get("skills")).get("pending_approval"))
        install_packet = _dict((_list(_dict(installed.get("autonomy")).get("action_packets")) or [{}])[0])
        registry_path = Path(str(result.get("registry_path") or ""))
        lock_path = Path(str(result.get("lock_path") or ""))
        registry_payload = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else {}
        lock_payload = json.loads(lock_path.read_text(encoding="utf-8")) if lock_path.exists() else {}
        checks = [
            _check("pending_proposal_keeps_resolved_payload", pending_payload.get("resolved_version") == preview.get("resolved_version") and pending_payload.get("hash") == preview.get("hash"), json.dumps(pending_payload, ensure_ascii=False)),
            _check("install_reuses_same_payload", _dict(install_packet.get("tool_args")).get("skill_id") == preview.get("skill_id") and _dict(install_packet.get("tool_args")).get("resolved_version") == preview.get("resolved_version") and _dict(install_packet.get("tool_args")).get("source") == preview.get("source") and _dict(install_packet.get("tool_args")).get("hash") == preview.get("hash") and list(_dict(install_packet.get("tool_args")).get("requested_permissions") or []) == list(preview.get("requested_permissions") or []) and list(_dict(install_packet.get("tool_args")).get("sandbox_profiles") or []) == list(preview.get("sandbox_profiles") or []) and _dict(install_packet.get("tool_args")).get("verification_summary") == preview.get("verification_summary"), json.dumps(install_packet, ensure_ascii=False)),
            _check("registry_and_lock_truth_match", bool(registry_payload) and bool(lock_payload) and registry_payload["skills"][0]["version"] == lock_payload["version"] and registry_payload["skills"][0]["hash"] == lock_payload["hash"], json.dumps({"registry": registry_payload, "lock": lock_payload}, ensure_ascii=False)),
            _check("enable_makes_skill_active", _dict((_list(_dict(enabled.get("skills")).get("active")) or [{}])[0]).get("skill_id") == result.get("skill_id") and _dict(enabled.get("digital_body_consequence")).get("kind") == "skill_activation_changed", json.dumps(enabled, ensure_ascii=False)),
        ]
    elif scenario_id == "auto_match_with_manual_disable_and_pin_precedence":
        auto_state = _dict(_dict(steps[0]).get("skills"))
        disabled_state = _dict(_dict(steps[1]).get("skills"))
        pinned_state = _dict(_dict(steps[2]).get("skills"))
        checks = [
            _check("auto_match_hits_workspace_skill", _dict((_list(auto_state.get("active")) or [{}])[0]).get("skill_id") == "workspace-regression-triage", json.dumps(auto_state, ensure_ascii=False)),
            _check("manual_disable_beats_auto_match", any(_dict(item).get("skill_id") == "workspace-regression-triage" for item in _list(disabled_state.get("matched"))) and not any(_dict(item).get("skill_id") == "workspace-regression-triage" for item in _list(disabled_state.get("active"))), json.dumps(disabled_state, ensure_ascii=False)),
            _check("pin_takes_precedence", _dict((_list(pinned_state.get("active")) or [{}])[0]).get("skill_id") == "source-ref-anchor-review" and "source-ref-anchor-review" in _dict(pinned_state.get("manual_overrides")).get("pinned", []), json.dumps(pinned_state, ensure_ascii=False)),
            _check("final_state_is_activation_change", _dict(_dict(steps[2]).get("digital_body_consequence")).get("kind") == "skill_activation_changed", json.dumps(_dict(steps[2]), ensure_ascii=False)),
        ]
    elif scenario_id == "blocked_or_rejected_skill_mutation_does_not_become_capability":
        consequence = _dict(_dict(steps[-1]).get("digital_body_consequence"))
        installed_after = _list(result.get("installed_after"))
        runtime_after = _dict(result.get("runtime_after"))
        checks = [
            _check("blocked_mutation_stays_blocked", consequence.get("kind") == "skill_mutation_blocked", json.dumps(consequence, ensure_ascii=False)),
            _check("blocked_mutation_not_installed", not any(_dict(item).get("skill_id") == result.get("skill_id") for item in installed_after), json.dumps(installed_after, ensure_ascii=False)),
            _check("blocked_mutation_not_active", not any(_dict(item).get("skill_id") == result.get("skill_id") for item in _list(runtime_after.get("active"))), json.dumps(runtime_after, ensure_ascii=False)),
            _check("skill_effect_status_not_completed", _dict((consequence.get("skill_effects") or [{}])[0]).get("status") == "blocked", json.dumps(consequence, ensure_ascii=False)),
        ]
    else:
        usage = _dict(steps[0])
        followup = _dict(steps[-1])
        consequence = _dict(usage.get("digital_body_consequence"))
        carryover = _dict(followup.get("interaction_carryover"))
        embodied = _dict(carryover.get("embodied_context"))
        checks = [
            _check("usage_records_skill_effect", consequence.get("kind") == "skill_usage_completed" and _dict((consequence.get("skill_effects") or [{}])[0]).get("skill_id") == "source-ref-anchor-review", json.dumps(consequence, ensure_ascii=False)),
            _check("followup_carryover_keeps_skill_tags", "skill:source-ref-anchor-review" in _list(carryover.get("source_tags")) and "skillop:use" in _list(carryover.get("source_tags")), json.dumps(carryover, ensure_ascii=False)),
            _check("followup_embodied_context_keeps_skill_effects", embodied.get("kind") == "skill_usage_completed" and _dict((embodied.get("skill_effects") or [{}])[0]).get("skill_id") == "source-ref-anchor-review", json.dumps(embodied, ensure_ascii=False)),
            _check("followup_continues_from_same_surface", _dict(_dict(followup.get("digital_body")).get("resource_state")).get("artifact_carrier") == "source_ref", json.dumps(_dict(followup.get("digital_body")), ensure_ascii=False)),
        ]
    return {"passed": all(item["passed"] for item in checks), "checks": checks}


def _run_single_scenario(spec: dict[str, Any]) -> dict[str, Any]:
    result = {key: spec[key] for key in ("id", "title", "focus")}
    result["steps"] = list(spec.get("steps") or [])
    result["duration_s"] = 0.0
    final_step = _dict(result["steps"][-1]) if result["steps"] else {}
    result["final_text"] = str(final_step.get("final_text") or "")
    result["skills"] = _dict(final_step.get("skills"))
    result["autonomy"] = _dict(final_step.get("autonomy"))
    result["digital_body"] = _dict(final_step.get("digital_body"))
    result["digital_body_consequence"] = _dict(final_step.get("digital_body_consequence"))
    result["key_packet_trace"] = _list(final_step.get("key_packet_trace"))
    for key in ("inspection", "preview", "registry_path", "lock_path", "skill_id", "installed_after", "runtime_after"):
        if key in spec:
            value = spec[key]
            result[key] = str(value) if isinstance(value, Path) else value
    result["evaluation"] = _evaluate(result)
    return result


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [f"# Skills Ecosystem Smokes ({report['run_id']})", "", f"Generated at: {report['generated_at']}", f"Overall Status: `{report['overall_status']}`", f"Passed: `{report['passed']}`", f"Failed: `{report['failed']}`", "", "## Scenario Summary", "", "| Scenario | Status | Duration (s) |", "| --- | --- | ---: |"]
    for result in report.get("results") or []:
        status = "passed" if _dict(result.get("evaluation")).get("passed") else "failed"
        lines.append(f"| `{result.get('id', '')}` | `{status}` | {float(result.get('duration_s') or 0.0):.3f} |")
    for result in report.get("results") or []:
        lines.extend(["", f"## {result.get('title', result.get('id', 'scenario'))}", "", f"- Focus: {result.get('focus', '')}", f"- Status: `{'passed' if _dict(result.get('evaluation')).get('passed') else 'failed'}`", f"- Final Text: `{str(result.get('final_text') or '').strip()}`", f"- Skills: `{json.dumps(_dict(result.get('skills')), ensure_ascii=False)}`", f"- Autonomy: `{json.dumps(_dict(result.get('autonomy')), ensure_ascii=False)}`", f"- Digital Body: `{json.dumps(_dict(result.get('digital_body')), ensure_ascii=False)}`", f"- Digital Body Consequence: `{json.dumps(_dict(result.get('digital_body_consequence')), ensure_ascii=False)}`", f"- Key Packet Trace: `{json.dumps(_list(result.get('key_packet_trace')), ensure_ascii=False)}`", "- Checks:"])
        for check in _dict(result.get("evaluation")).get("checks") or []:
            lines.append(f"  - `{'pass' if check.get('passed') else 'fail'}` {check.get('name', '')}: {check.get('detail', '')}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run skills ecosystem smoke scenarios.")
    parser.add_argument("--run-tag", default="")
    parser.add_argument("--scenario", action="append", default=[])
    args = parser.parse_args()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    run_root = TMP_ROOT / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    requested = {str(item or "").strip() for item in _list(args.scenario) if str(item or "").strip()}
    specs = _scenario_specs(run_root)
    if requested:
        specs = [spec for spec in specs if str(spec.get("id") or "") in requested]
        if not specs:
            available = ", ".join(sorted(str(spec.get("id") or "") for spec in _scenario_specs(run_root)))
            raise SystemExit(f"No skills smoke scenarios matched {sorted(requested)!r}. Available: {available}")
    results = [_run_single_scenario(spec) for spec in specs]
    passed = len([row for row in results if _dict(row.get("evaluation")).get("passed")])
    failed = len(results) - passed
    report = {"run_id": run_id, "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "overall_status": "passed" if failed == 0 else "failed", "passed": passed, "failed": failed, "results": results, "scenario_artifact_references": [{"id": str(result.get("id") or ""), "title": str(result.get("title") or ""), "status": "passed" if _dict(result.get("evaluation")).get("passed") else "failed"} for result in results]}
    json_path = REPORT_DIR / f"skills-ecosystem-smokes-{run_id}.json"
    md_path = REPORT_DIR / f"skills-ecosystem-smokes-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(f"[skills-ecosystem-smokes] json={json_path}")
    print(f"[skills-ecosystem-smokes] md={md_path}")
    print(f"[skills-ecosystem-smokes] overall_status={report['overall_status']}")


if __name__ == "__main__":
    main()
