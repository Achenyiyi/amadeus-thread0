from __future__ import annotations

from typing import Any

from .appraisal import normalize_appraisal_payload
from .schemas import clamp01
from ..graph_parts.action_packets import (
    compact_artifact_identity,
    normalize_access_acquire_proposal,
    normalize_access_acquire_proposals,
    normalize_action_packet,
    normalize_action_packets,
    normalize_artifact_context,
)
from ..graph_parts.autonomy_runtime import normalize_autonomy_intent
from ..graph_parts.digital_body_runtime import (
    derive_account_surface_state,
    derive_artifact_identity,
    derive_permission_surface_state,
    derive_quota_surface_state,
    derive_sandbox_surface_state,
    derive_session_surface_state,
    normalize_digital_body_state,
    normalize_embodied_context,
)
from ..utils.counterpart_profile import compact_counterpart_profile

_SEMANTIC_ANCHOR_FLOAT_KEYS = (
    "continuity_anchor",
    "own_rhythm_anchor",
    "recontact_anchor",
    "boundary_anchor",
    "memory_anchor",
    "semantic_continuity_depth",
    "semantic_identity_gravity",
    "lineage_gravity",
    "contact_lineage",
    "repair_lineage",
    "boundary_lineage",
    "selfhood_lineage",
    "agency_lineage",
)

_DIGITAL_BODY_PACKET_PRIORITY = {
    "blocked": 6,
    "rejected": 5,
    "awaiting_approval": 4,
    "executing": 3,
    "completed": 2,
    "approved": 1,
    "queued": 1,
    "proposed": 1,
}

_ARTIFACT_REACQUISITION_INTENTS = {
    "artifact:reopen_file",
    "artifact:reattach_workspace",
    "artifact:reopen_page",
    "artifact:restore_page",
    "artifact:rerun_search",
}


def _normalized_event_tags(current_event: dict[str, Any] | None) -> set[str]:
    if not isinstance(current_event, dict):
        return set()
    return {
        str(item).strip().lower()
        for item in (current_event.get("tags") if isinstance(current_event.get("tags"), list) else [])
        if str(item or "").strip()
    }


def _compact_counterpart_snapshot(counterpart_assessment: dict[str, Any] | None) -> dict[str, Any]:
    assessment = dict(counterpart_assessment or {})
    stance = str(assessment.get("stance") or "").strip()
    scene = str(assessment.get("scene") or "").strip()
    summary = str(assessment.get("summary") or "").strip()
    snapshot = {
        "summary": summary[:220],
        "stance": stance,
        "scene": scene,
        "respect_level": clamp01(assessment.get("respect_level"), 0.5),
        "reciprocity": clamp01(assessment.get("reciprocity"), 0.5),
        "boundary_pressure": clamp01(assessment.get("boundary_pressure"), 0.1),
        "reliability_read": clamp01(assessment.get("reliability_read"), 0.5),
    }
    profile = assessment.get("assessment_profile") if isinstance(assessment.get("assessment_profile"), dict) else {}
    if profile:
        snapshot["assessment_profile"] = compact_counterpart_profile(profile)
    if summary or stance or scene:
        return snapshot
    numeric_signal = (
        abs(snapshot["respect_level"] - 0.5)
        + abs(snapshot["reciprocity"] - 0.5)
        + abs(snapshot["boundary_pressure"] - 0.1)
        + abs(snapshot["reliability_read"] - 0.5)
    )
    profile_signal = snapshot.get("assessment_profile") if isinstance(snapshot.get("assessment_profile"), dict) else {}
    return snapshot if numeric_signal > 0.0 or profile_signal else {}


def _compact_behavior_plan_snapshot(behavior_plan: dict[str, Any] | None) -> dict[str, Any]:
    plan = dict(behavior_plan or {})
    snapshot = {
        "kind": str(plan.get("kind") or "").strip().lower(),
        "target": str(plan.get("target") or "").strip().lower(),
        "trigger_family": str(plan.get("trigger_family") or "").strip().lower(),
        "carryover_mode": str(plan.get("carryover_mode") or "").strip().lower(),
        "relationship_weather": str(plan.get("relationship_weather") or "").strip().lower(),
        "attention_target": str(plan.get("attention_target") or "").strip().lower(),
        "nonverbal_signal": str(plan.get("nonverbal_signal") or "").strip().lower(),
        "note": str(plan.get("note") or "").strip()[:220],
        "primary_motive": str(plan.get("primary_motive") or "").strip().lower(),
        "motive_tension": str(plan.get("motive_tension") or "").strip().lower(),
        "goal_frame": str(plan.get("goal_frame") or "").strip()[:220],
        "scheduled_after_min": max(0, int(plan.get("scheduled_after_min") or 0)),
        "allow_interrupt": bool(plan.get("allow_interrupt", True)),
        "carryover_strength": clamp01(plan.get("carryover_strength"), 0.0),
        "presence_residue": clamp01(plan.get("presence_residue"), 0.0),
        "ambient_resonance": clamp01(plan.get("ambient_resonance"), 0.0),
        "self_activity_momentum": clamp01(plan.get("self_activity_momentum"), 0.0),
    }
    if any(
        (
            snapshot["kind"],
            snapshot["target"],
            snapshot["trigger_family"],
            snapshot["carryover_mode"],
            snapshot["relationship_weather"],
            snapshot["attention_target"],
            snapshot["nonverbal_signal"],
            snapshot["note"],
            snapshot["primary_motive"],
            snapshot["motive_tension"],
            snapshot["goal_frame"],
            snapshot["scheduled_after_min"] > 0,
            snapshot["carryover_strength"] > 0.0,
            snapshot["presence_residue"] > 0.0,
            snapshot["ambient_resonance"] > 0.0,
            snapshot["self_activity_momentum"] > 0.0,
        )
    ):
        return snapshot
    return {}


def _compact_behavior_action_snapshot(behavior_action: dict[str, Any] | None) -> dict[str, Any]:
    action = dict(behavior_action or {})
    window_profile = _compact_window_profile_snapshot(action.get("window_profile"))
    snapshot = {
        "interaction_mode": str(action.get("interaction_mode") or "").strip().lower(),
        "action_target": str(action.get("action_target") or "").strip().lower(),
        "channel": str(action.get("channel") or "").strip().lower(),
        "approach_style": str(action.get("approach_style") or "").strip().lower(),
        "engagement_level": clamp01(action.get("engagement_level"), 0.0),
        "initiative_level": clamp01(action.get("initiative_level"), 0.0),
        "followup_intent": str(action.get("followup_intent") or "").strip().lower(),
        "task_focus": str(action.get("task_focus") or "").strip().lower(),
        "affect_surface": str(action.get("affect_surface") or "").strip().lower(),
        "silence_ok": bool(action.get("silence_ok", False)),
        "proactive_checkin_readiness": clamp01(action.get("proactive_checkin_readiness"), 0.0),
        "deferred_action_family": str(action.get("deferred_action_family") or "").strip().lower(),
        "relationship_weather": str(action.get("relationship_weather") or "").strip().lower(),
        "attention_target": str(action.get("attention_target") or "").strip().lower(),
        "nonverbal_signal": str(action.get("nonverbal_signal") or "").strip().lower(),
        "initiative_shape": str(action.get("initiative_shape") or "").strip().lower(),
        "disclosure_posture": str(action.get("disclosure_posture") or "").strip().lower(),
        "primary_motive": str(action.get("primary_motive") or "").strip().lower(),
        "motive_tension": str(action.get("motive_tension") or "").strip().lower(),
        "goal_frame": str(action.get("goal_frame") or "").strip()[:220],
        "note": str(action.get("note") or "").strip()[:220],
        "timing_window_min": max(0, int(action.get("timing_window_min") or 0)),
        "window_profile": window_profile,
    }
    if any(
        (
            snapshot["interaction_mode"],
            snapshot["action_target"],
            snapshot["channel"],
            snapshot["approach_style"],
            snapshot["engagement_level"] > 0.0,
            snapshot["initiative_level"] > 0.0,
            snapshot["followup_intent"],
            snapshot["task_focus"],
            snapshot["affect_surface"],
            snapshot["silence_ok"],
            snapshot["proactive_checkin_readiness"] > 0.0,
            snapshot["deferred_action_family"],
            snapshot["relationship_weather"],
            snapshot["attention_target"],
            snapshot["nonverbal_signal"],
            snapshot["initiative_shape"],
            snapshot["disclosure_posture"],
            snapshot["primary_motive"],
            snapshot["motive_tension"],
            snapshot["goal_frame"],
            snapshot["note"],
            snapshot["timing_window_min"] > 0,
            bool(snapshot["window_profile"]),
        )
    ):
        return snapshot
    return {}


def _compact_window_profile_snapshot(profile: dict[str, Any] | None) -> dict[str, Any]:
    window = dict(profile or {})
    if not window:
        return {}
    snapshot = {
        "profile_type": str(window.get("profile_type") or "").strip().lower(),
        "event_kind": str(window.get("event_kind") or "").strip().lower(),
        "family": str(window.get("family") or "").strip().lower(),
        "trigger_family": str(window.get("trigger_family") or "").strip().lower(),
        "stance": str(window.get("stance") or "").strip().lower(),
        "scene": str(window.get("scene") or "").strip().lower(),
        "decision": str(window.get("decision") or "").strip().lower(),
        "maturity": clamp01(window.get("maturity"), 0.0),
        "required_maturity": clamp01(window.get("required_maturity"), 0.0),
        "invite_ready": bool(window.get("invite_ready", False)),
        "readiness": clamp01(window.get("readiness"), 0.0),
        "required_readiness": clamp01(window.get("required_readiness"), 0.0),
        "reopen_ready": bool(window.get("reopen_ready", False)),
        "recheck_min": max(0, int(window.get("recheck_min") or 0)),
        "continuity_bonus": clamp01(window.get("continuity_bonus"), 0.0),
        "continuity_discount": clamp01(window.get("continuity_discount"), 0.0),
        "carryover_mode": str(window.get("carryover_mode") or "").strip().lower(),
        "carryover_strength": clamp01(window.get("carryover_strength"), 0.0),
        "event_carryover_mode": str(window.get("event_carryover_mode") or "").strip().lower(),
        "event_carryover_strength": clamp01(window.get("event_carryover_strength"), 0.0),
        "presence_residue": clamp01(window.get("presence_residue"), 0.0),
        "ambient_resonance": clamp01(window.get("ambient_resonance"), 0.0),
        "self_activity_momentum": clamp01(window.get("self_activity_momentum"), 0.0),
        "recontact_echo": clamp01(window.get("recontact_echo"), 0.0),
        "own_rhythm_load": clamp01(window.get("own_rhythm_load"), 0.0),
    }
    if any(
        (
            snapshot["profile_type"],
            snapshot["event_kind"],
            snapshot["family"],
            snapshot["trigger_family"],
            snapshot["stance"],
            snapshot["scene"],
            snapshot["decision"],
            snapshot["maturity"] > 0.0,
            snapshot["required_maturity"] > 0.0,
            snapshot["invite_ready"],
            snapshot["readiness"] > 0.0,
            snapshot["required_readiness"] > 0.0,
            snapshot["reopen_ready"],
            snapshot["recheck_min"] > 0,
            snapshot["continuity_bonus"] > 0.0,
            snapshot["continuity_discount"] > 0.0,
            snapshot["carryover_mode"],
            snapshot["carryover_strength"] > 0.0,
            snapshot["event_carryover_mode"],
            snapshot["event_carryover_strength"] > 0.0,
            snapshot["presence_residue"] > 0.0,
            snapshot["ambient_resonance"] > 0.0,
            snapshot["self_activity_momentum"] > 0.0,
            snapshot["recontact_echo"] > 0.0,
            snapshot["own_rhythm_load"] > 0.0,
        )
    ):
        return snapshot
    return {}


def _compact_interaction_carryover_snapshot(interaction_carryover: dict[str, Any] | None) -> dict[str, Any]:
    carryover = dict(interaction_carryover or {})
    source_tags = [
        str(item).strip().lower()
        for item in (carryover.get("source_tags") if isinstance(carryover.get("source_tags"), list) else [])
        if str(item or "").strip()
    ][:12]
    snapshot = {
        "source": str(carryover.get("source") or "").strip().lower(),
        "strength": clamp01(carryover.get("strength"), 0.0),
        "carryover_mode": str(carryover.get("carryover_mode") or "").strip().lower(),
        "relationship_weather": str(carryover.get("relationship_weather") or "").strip().lower(),
        "note": str(carryover.get("note") or "").strip()[:220],
        "source_tags": source_tags,
    }
    if any(
        (
            snapshot["source"],
            snapshot["carryover_mode"],
            snapshot["relationship_weather"],
            snapshot["note"],
            snapshot["strength"] > 0.0,
            bool(snapshot["source_tags"]),
        )
    ):
        return snapshot
    return {}


def _compact_autonomy_intent_snapshot(autonomy_intent: dict[str, Any] | None) -> dict[str, Any]:
    intent = normalize_autonomy_intent(autonomy_intent)
    if not intent:
        return {}
    if any(
        (
            str(intent.get("mode") or "").strip(),
            str(intent.get("origin") or "").strip(),
            str(intent.get("reason") or "").strip(),
            str(intent.get("primary_proposal_id") or "").strip(),
            clamp01(intent.get("confidence"), 0.0) > 0.0,
            clamp01(intent.get("own_rhythm_weight"), 0.0) > 0.0,
            clamp01(intent.get("continuity_weight"), 0.0) > 0.0,
            bool(intent.get("requires_approval", False)),
        )
    ):
        return intent
    return {}


def _compact_action_packets_snapshot(action_packets: Any) -> list[dict[str, Any]]:
    packets = normalize_action_packets(action_packets)
    out: list[dict[str, Any]] = []
    for packet in packets[:8]:
        artifact_context = normalize_artifact_context(packet.get("artifact_context"))
        if artifact_context:
            preview = str(artifact_context.get("preview") or "").strip()
            compact_artifact_context = {
                **artifact_context,
                "preview": preview[:600],
                "preview_truncated": bool(artifact_context.get("preview_truncated", False) or len(preview) > 600),
            }
        else:
            compact_artifact_context = {}
        out.append(
            {
                "proposal_id": str(packet.get("proposal_id") or "").strip(),
                "origin": str(packet.get("origin") or "").strip().lower(),
                "intent": str(packet.get("intent") or "").strip().lower(),
                "status": str(packet.get("status") or "").strip().lower(),
                "risk": str(packet.get("risk") or "").strip().lower(),
                "requires_approval": bool(packet.get("requires_approval", False)),
                "capability_steps": [
                    {
                        "kind": str(step.get("kind") or "").strip().lower(),
                        "name": str(step.get("name") or "").strip(),
                        "target": str(step.get("target") or "").strip()[:160],
                        "status": str(step.get("status") or "").strip().lower(),
                        "requires_approval": bool(step.get("requires_approval", False)),
                        "note": str(step.get("note") or "").strip()[:160],
                    }
                    for step in (packet.get("capability_steps") if isinstance(packet.get("capability_steps"), list) else [])
                    if isinstance(step, dict)
                ][:4],
                "expected_effect": str(packet.get("expected_effect") or "").strip()[:220],
                "result_summary": str(packet.get("result_summary") or "").strip()[:220],
                "writeback_ready": bool(packet.get("writeback_ready", False)),
                "linked_queue_id": str(packet.get("linked_queue_id") or "").strip(),
                "tool_name": str(packet.get("tool_name") or "").strip(),
                "block_reason": str(packet.get("block_reason") or "").strip()[:220],
                "artifact_context": compact_artifact_context,
            }
        )
    return out


def _compact_action_trace_snapshot(action_trace: Any) -> list[dict[str, Any]]:
    if not isinstance(action_trace, list):
        return []
    out: list[dict[str, Any]] = []
    for item in action_trace[:12]:
        if not isinstance(item, dict):
            continue
        proposal_id = str(item.get("proposal_id") or "").strip()
        status = str(item.get("status") or "").strip().lower()
        event = str(item.get("event") or "").strip().lower()
        if not any((proposal_id, status, event)):
            continue
        out.append(
            {
                "proposal_id": proposal_id,
                "status": status,
                "event": event,
                "origin": str(item.get("origin") or "").strip().lower(),
                "intent": str(item.get("intent") or "").strip().lower(),
                "risk": str(item.get("risk") or "").strip().lower(),
                "source": str(item.get("source") or "").strip(),
                "result_summary": str(item.get("result_summary") or "").strip()[:220],
                "block_reason": str(item.get("block_reason") or "").strip()[:220],
                "requires_approval": bool(item.get("requires_approval", False)),
            }
        )
    return out


def _compact_digital_body_state_snapshot(digital_body_state: dict[str, Any] | None) -> dict[str, Any]:
    return normalize_digital_body_state(digital_body_state)


def _primary_digital_body_packet(action_packets: Any) -> dict[str, Any]:
    packets = normalize_action_packets(action_packets)
    if not packets:
        return {}

    def _score(packet: dict[str, Any]) -> tuple[int, int, int]:
        status = str(packet.get("status") or "").strip().lower()
        origin = str(packet.get("origin") or "").strip().lower()
        intent = str(packet.get("intent") or "").strip().lower()
        tool_name = str(packet.get("tool_name") or "").strip()
        score = _DIGITAL_BODY_PACKET_PRIORITY.get(status, 0)
        if origin == "capability_upgrade":
            score += 3
        if "upgrade" in intent:
            score += 2
        if bool(packet.get("writeback_ready", False)):
            score += 1
        if tool_name:
            score += 1
        return (score, len(tool_name), len(intent))

    return normalize_action_packet(max(packets, key=_score))


def _compact_semantic_anchor_bundle(semantic_narrative_profile: dict[str, Any] | None) -> dict[str, Any]:
    semantic = semantic_narrative_profile if isinstance(semantic_narrative_profile, dict) else {}
    snapshot = {
        key: clamp01(semantic.get(key), 0.0)
        for key in _SEMANTIC_ANCHOR_FLOAT_KEYS
    }
    snapshot["long_term_axis_count"] = max(0, int(semantic.get("long_term_axis_count") or 0))
    if any(float(snapshot.get(key) or 0.0) > 0.0 for key in _SEMANTIC_ANCHOR_FLOAT_KEYS) or snapshot["long_term_axis_count"] > 0:
        return snapshot
    return {}


def derive_behavior_consequence(
    *,
    current_event: dict[str, Any] | None,
    behavior_action: dict[str, Any] | None = None,
    allow_event_behavior_fallback: bool = True,
) -> dict[str, Any]:
    event = current_event if isinstance(current_event, dict) else {}
    behavior = behavior_action if isinstance(behavior_action, dict) else {}
    event_kind = str(event.get("kind") or "").strip().lower()
    event_frame = str(event.get("event_frame") or "").strip().lower()
    tags = _normalized_event_tags(event)
    interaction_mode = str(behavior.get("interaction_mode") or "").strip().lower()
    if allow_event_behavior_fallback and not interaction_mode:
        interaction_mode = str(event.get("interaction_mode") or "").strip().lower()
    action_target = str(behavior.get("action_target") or "").strip().lower()
    primary_motive = str(behavior.get("primary_motive") or "").strip().lower()
    motive_tension = str(behavior.get("motive_tension") or "").strip().lower()
    goal_frame = str(behavior.get("goal_frame") or "").strip()
    if allow_event_behavior_fallback:
        if not primary_motive:
            primary_motive = str(event.get("primary_motive") or "").strip().lower()
        if not motive_tension:
            motive_tension = str(event.get("motive_tension") or "").strip().lower()
        if not goal_frame:
            goal_frame = str(event.get("goal_frame") or "").strip()
    trigger_family = str(event.get("trigger_family") or behavior.get("deferred_action_family") or "").strip().lower()
    relationship_weather = str(behavior.get("relationship_weather") or event.get("relationship_weather") or "").strip().lower()
    carryover_mode = str(event.get("carryover_mode") or "").strip().lower()
    try:
        timing_window_min = max(
            0,
            int(
                behavior.get("timing_window_min")
                or event.get("scheduled_after_min")
                or 0
            ),
        )
    except Exception:
        timing_window_min = 0

    silent = bool(event_kind in {"time_idle", "self_activity_state", "scheduled_checkin_due", "scheduled_life_due"})
    stale_window = bool(event_kind == "time_idle" and ("stale_window" in tags or event_frame == "time_idle_stale"))

    if action_target == "hold_own_rhythm":
        summary = "她没有立刻回头，而是先把自己的节奏继续走完。"
        if event_kind == "self_activity_state":
            summary = "她没有立刻把注意力全转回来，而是先把自己手头的节奏继续往下走。"
        elif event_kind == "time_idle":
            summary = "就算注意力短暂飘回来，她也还是先把自己的节奏留住，没有马上重新靠近。"
        category_summaries = {
            "agency_style": "她会先把自己的节奏走完，再决定什么时候重新靠近，不会一有动静就立刻转身。",
            "rhythm_style": "这次她没有立刻回头，而是把刚才那股自己的节奏继续带了下去。",
        }
        if "respect_space" in tags or "user_busy" in tags:
            category_summaries["presence_style"] = "她会先给对方和自己都留出空间，不会因为一闪而过的念头就立刻打破现在的距离。"
        return {
            "kind": "hold_own_rhythm",
            "summary": summary,
            "relationship_effect": "space_preserved",
            "self_effect": "own_rhythm_continues",
            "silent": silent,
            "delayed": False,
            "stale_window": False,
            "trigger_family": trigger_family,
            "timing_window_min": timing_window_min,
            "relationship_weather": relationship_weather,
            "carryover_mode": carryover_mode,
            "narrative_categories": list(category_summaries),
            "category_summaries": category_summaries,
        }

    if action_target == "wait_and_recheck":
        if stale_window:
            summary = "这次原本还能接回去的窗口过去了，她没有硬把它续上，而是让它自然错开。"
            if trigger_family == "life_window":
                summary = "前面那点生活上的窗口已经过去了，她没有硬把话题补回来，而是让它自然错开。"
            elif trigger_family in {"shared_activity", "shared_activity_window"}:
                summary = "刚才还能顺手接上的那个共同窗口过去了，她没有强行续上，而是让这次机会自然过去。"
            elif trigger_family == "deadline_window":
                summary = "前面那件事已经错过了最自然的提醒窗口，她没有硬补一句，而是先让它过去。"
            category_summaries = {
                "agency_style": "窗口过去了，她也不会为了维持联系感硬把它续上；要不要重新靠近，仍然要按她自己的判断来。",
                "rhythm_style": "当时机过去之后，她会把注意力收回自己的节奏，而不是为了不显得冷就强行补一轮。",
                "presence_style": "有些靠近如果没有在那个时机发生，她就会让它先过去，而不是假装每个窗口都必须被接住。",
            }
            return {
                "kind": "let_window_expire",
                "summary": summary,
                "relationship_effect": "window_released",
                "self_effect": "attention_returns_to_self",
                "silent": True,
                "delayed": False,
                "stale_window": True,
                "trigger_family": trigger_family,
                "timing_window_min": timing_window_min,
                "relationship_weather": relationship_weather,
                "carryover_mode": carryover_mode,
                "narrative_categories": list(category_summaries),
                "category_summaries": category_summaries,
            }
        summary = "她没有把这次想靠近的念头立刻变成开口，而是先往后放了放，等更自然的时候再看。"
        if trigger_family == "life_window":
            summary = "她把这次生活上的惦记先轻轻压住了，没有立刻接上，想等更自然一点的时机再看。"
        elif trigger_family in {"shared_activity", "shared_activity_window"}:
            summary = "她没有立刻把这次一起做点什么的念头推出去，而是先把窗口留着，等更自然的时机再看。"
        elif trigger_family == "deadline_window":
            summary = "她没有立刻把这件事提出来，而是先往后压了一下，想等更合适的节点再接。"
        category_summaries = {
            "agency_style": "她不会把每次想靠近都立刻做成行动，而是会先判断现在是不是值得往前走一步。",
            "presence_style": "这次想靠近的念头先被她轻轻压住了，没有马上变成开口，而是留到更自然的时候再看。",
        }
        if motive_tension == "self_rhythm_vs_contact" or event_kind in {"time_idle", "self_activity_state"} or "from_own_rhythm" in tags:
            category_summaries["rhythm_style"] = "她把这次靠近先往后放了放，让自己的内部节奏先继续往前走，而不是马上切过去。"
        return {
            "kind": "defer_recontact",
            "summary": summary,
            "relationship_effect": "contact_deferred",
            "self_effect": "recheck_pending",
            "silent": silent,
            "delayed": True,
            "stale_window": False,
            "trigger_family": trigger_family,
            "timing_window_min": timing_window_min,
            "relationship_weather": relationship_weather,
            "carryover_mode": carryover_mode,
            "narrative_categories": list(category_summaries),
            "category_summaries": category_summaries,
        }

    if action_target == "offer_small_opening" or interaction_mode == "self_activity_reopen":
        category_summaries = {
            "agency_style": "她会从自己的节奏里回头，但只留一个轻一点的小开口，不把靠近一下子做满。",
            "rhythm_style": "她的靠近像从原本在做的事里短暂抬头，而不是整个人立刻切过去。",
            "presence_style": "她更愿意先确认那点在场感还在，再决定要不要继续往下展开。",
        }
        return {
            "kind": "leave_small_opening",
            "summary": "她从自己的节奏里回头了，但只留了一个很轻的小开口。",
            "relationship_effect": "soft_reapproach",
            "self_effect": "partial_reengagement",
            "silent": silent,
            "delayed": False,
            "stale_window": False,
            "trigger_family": trigger_family,
            "timing_window_min": timing_window_min,
            "relationship_weather": relationship_weather,
            "carryover_mode": carryover_mode,
            "narrative_categories": list(category_summaries),
            "category_summaries": category_summaries,
        }

    return {}


def derive_agenda_lifecycle_consequence(
    *,
    agenda_lifecycle_residue: dict[str, Any] | None,
) -> dict[str, Any]:
    residue = agenda_lifecycle_residue if isinstance(agenda_lifecycle_residue, dict) else {}
    kind = str(residue.get("kind") or "").strip().lower()
    if not kind:
        return {}

    carryover_mode = str(residue.get("carryover_mode") or "").strip().lower()
    source_event_kind = str(residue.get("source_event_kind") or "").strip().lower()
    trigger_family = str(residue.get("trigger_family") or "").strip().lower()
    relationship_weather = str(residue.get("relationship_weather") or "").strip().lower()
    counterpart_scene_bias = str(residue.get("counterpart_scene_bias") or "").strip().lower()
    note = str(residue.get("note") or "").strip()
    hold_count = max(0, int(residue.get("hold_count") or 0))
    carryover_strength = clamp01(residue.get("carryover_strength"), 0.0)
    own_rhythm_bias = clamp01(residue.get("own_rhythm_bias"), 0.0)
    recontact_cooldown = clamp01(residue.get("recontact_cooldown"), 0.0)
    presence_residue = clamp01(residue.get("presence_residue"), 0.0)
    ambient_resonance = clamp01(residue.get("ambient_resonance"), 0.0)
    self_activity_momentum = clamp01(residue.get("self_activity_momentum"), 0.0)
    continuity_anchor = clamp01(residue.get("continuity_anchor"), 0.0)
    own_rhythm_anchor = clamp01(residue.get("own_rhythm_anchor"), 0.0)
    recontact_anchor = clamp01(residue.get("recontact_anchor"), 0.0)
    boundary_anchor = clamp01(residue.get("boundary_anchor"), 0.0)
    memory_anchor = clamp01(residue.get("memory_anchor"), 0.0)
    semantic_continuity_depth = clamp01(residue.get("semantic_continuity_depth"), 0.0)
    semantic_identity_gravity = clamp01(residue.get("semantic_identity_gravity"), 0.0)
    long_term_axis_count = max(0, int(residue.get("long_term_axis_count") or 0))
    lineage_gravity = clamp01(residue.get("lineage_gravity"), 0.0)
    contact_lineage = clamp01(residue.get("contact_lineage"), 0.0)
    repair_lineage = clamp01(residue.get("repair_lineage"), 0.0)
    boundary_lineage = clamp01(residue.get("boundary_lineage"), 0.0)
    selfhood_lineage = clamp01(residue.get("selfhood_lineage"), 0.0)
    agency_lineage = clamp01(residue.get("agency_lineage"), 0.0)
    try:
        counterpart_boundary_delta = max(-1.0, min(1.0, float(residue.get("counterpart_boundary_delta") or 0.0)))
    except Exception:
        counterpart_boundary_delta = 0.0
    primary_motive = ""
    motive_tension = "self_rhythm_vs_contact"
    goal_frame = ""

    if kind == "held":
        if carryover_mode == "quiet_recontact" and carryover_strength > max(0.24, own_rhythm_bias + 0.04):
            primary_motive = "honor_continuity"
            goal_frame = "先把这次窗口按住，不硬往前推，等更自然一点的时机再决定要不要接回来。"
        else:
            primary_motive = "preserve_self_rhythm"
            goal_frame = "先把自己的节奏继续走完，再决定那点没说出口的窗口之后要不要接回来。"
        summary = note or "这次她把前面的窗口先按住了，没有顺势往前推进。"
        category_summaries = {
            "agency_style": "她会先把窗口按住，再决定要不要推进，不会因为刚好有机会就立刻往前凑。",
            "rhythm_style": (
                "把窗口按住之后，她会先让自己的节奏继续往前走，再看什么时候回头。"
                if carryover_mode == "own_rhythm" or own_rhythm_bias >= carryover_strength
                else "把窗口按住并不等于忘了；那点想靠近的念头会以更轻一点的方式留在后面。"
            ),
            "presence_style": (
                "如果对方当下忙着别的事，她会先把这理解成时机不对，而不是关系突然变冷。"
                if counterpart_scene_bias == "busy_not_disrespectful"
                else "不是每一个窗口都要立刻接住；有时她会先按住那点靠近，再看之后是否自然续上。"
            ),
        }
    elif kind in {"released_to_self_activity", "dropped", "expired"}:
        primary_motive = "preserve_self_rhythm"
        goal_frame = "先让这段窗口自然过去，把注意力收回自己的节奏，再看之后是否还要重新靠近。"
        summary_map = {
            "released_to_self_activity": "前面挂着的窗口没有继续往前推，她把注意力自然收回到了自己的节奏里。",
            "dropped": "前面那点接近窗口这次被她自然放下了，不再继续挂着。",
            "expired": "前面的窗口自然过期了，她没有硬续上，而是让注意力回到自己的节奏。",
        }
        summary = note or summary_map.get(kind) or "前面的窗口没有继续往前推，她把注意力收回到了自己的节奏里。"
        category_summaries = {
            "agency_style": "如果一段靠近没有继续往前推，她会把注意力收回自己的节奏，而不是为了维持联系感硬撑着挂住。",
            "rhythm_style": "当窗口被放下或自然过期时，她的内部节奏会重新占上风，下一次靠近也会带着这段自我惯性。",
            "presence_style": (
                "对方一时忙碌或没接住窗口时，她更倾向于把它理解成时机问题，不会立刻把沉默解读成轻视。"
                if counterpart_scene_bias == "busy_not_disrespectful"
                else "不是每个窗口都必须被接住；有些时候她会让它过去，再看以后是否自然重合。"
            ),
        }
    elif kind == "promoted":
        if trigger_family in {"shared_activity", "shared_activity_window"}:
            primary_motive = "open_shared_window"
            goal_frame = "前面没推出去的共同窗口，这次顺着自然时机重新接了回来。"
        elif trigger_family in {"life_window", "deadline_window", "light_checkin", "observe"}:
            primary_motive = "honor_continuity"
            goal_frame = "前面挂着的那点惦记，这次在合适的时候被重新接了回来。"
        else:
            primary_motive = "gentle_recontact"
            goal_frame = "前面没说出口的靠近，这次带着之前留下的惯性重新接了回来。"
        summary = note or "前面挂着的窗口这次终于转成了真正的行动。"
        category_summaries = {
            "agency_style": "她会让之前积下来的念头在合适的时候真正变成行动，而不是每一次都临场从零开始。",
            "rhythm_style": "这次开口不是凭空出现的，而是带着前一段时间没说出口的惯性接上来的。",
            "presence_style": "前面没有立刻推进，不代表那点在场感消失了；时机合适时，她会把它重新接回来。",
        }
    else:
        primary_motive = "maintain_natural_contact" if carryover_mode in {"quiet_recontact", "small_opening"} else "preserve_self_rhythm"
        goal_frame = "把前一轮没走完的那点窗口余波留在后面，让它继续参与之后的判断。"
        summary = note or "前面的窗口在这一轮留下了一点可以延续的余波。"
        category_summaries = {
            "agency_style": "她不会把每一次靠近都当作必须立刻执行的动作，窗口的起落也会变成她后续判断的一部分。",
            "rhythm_style": "前一轮没有走完的那点节奏，不会立刻消失，而是会留到下一次判断里继续起作用。",
        }

    if ambient_resonance >= 0.18:
        category_summaries["ambient_style"] = "窗口落下之后，周围那点没散掉的气氛还会留着，不会一下子彻底归零。"

    consequence = {
        "kind": kind,
        "summary": summary,
        "source_event_kind": source_event_kind,
        "trigger_family": trigger_family,
        "relationship_weather": relationship_weather,
        "carryover_mode": carryover_mode,
        "carryover_strength": carryover_strength,
        "hold_count": hold_count,
        "recontact_cooldown": recontact_cooldown,
        "presence_residue": presence_residue,
        "ambient_resonance": ambient_resonance,
        "self_activity_momentum": self_activity_momentum,
        "own_rhythm_bias": own_rhythm_bias,
        "continuity_anchor": continuity_anchor,
        "own_rhythm_anchor": own_rhythm_anchor,
        "recontact_anchor": recontact_anchor,
        "boundary_anchor": boundary_anchor,
        "memory_anchor": memory_anchor,
        "semantic_continuity_depth": semantic_continuity_depth,
        "semantic_identity_gravity": semantic_identity_gravity,
        "long_term_axis_count": long_term_axis_count,
        "lineage_gravity": lineage_gravity,
        "contact_lineage": contact_lineage,
        "repair_lineage": repair_lineage,
        "boundary_lineage": boundary_lineage,
        "selfhood_lineage": selfhood_lineage,
        "agency_lineage": agency_lineage,
        "counterpart_scene_bias": counterpart_scene_bias,
        "counterpart_boundary_delta": counterpart_boundary_delta,
        "primary_motive": primary_motive,
        "motive_tension": motive_tension,
        "goal_frame": goal_frame[:220],
        "narrative_categories": list(category_summaries),
        "category_summaries": category_summaries,
    }
    embodied_context = normalize_embodied_context(residue.get("embodied_context"))
    if embodied_context:
        consequence["embodied_context"] = embodied_context
    return consequence


def derive_digital_body_consequence(
    *,
    digital_body_state: dict[str, Any] | None,
    action_packets: Any = None,
) -> dict[str, Any]:
    body = normalize_digital_body_state(digital_body_state)
    if not body:
        return {}

    access_state = body.get("access_state") if isinstance(body.get("access_state"), dict) else {}
    resource_state = body.get("resource_state") if isinstance(body.get("resource_state"), dict) else {}
    access_mode = str(access_state.get("mode") or "").strip().lower()
    active_surface = str(body.get("active_surface") or "").strip().lower()
    block_reason = str(access_state.get("block_reason") or "").strip()[:220]
    missing_access = [
        str(item).strip().lower()
        for item in (access_state.get("missing_access") if isinstance(access_state.get("missing_access"), list) else [])
        if str(item or "").strip()
    ][:12]
    requested_access = [
        str(item).strip().lower()
        for item in (access_state.get("requestable_access") if isinstance(access_state.get("requestable_access"), list) else [])
        if str(item or "").strip()
    ][:12]
    granted_toolsets = [
        str(item).strip().lower()
        for item in (access_state.get("granted_toolsets") if isinstance(access_state.get("granted_toolsets"), list) else [])
        if str(item or "").strip()
    ][:12]
    active_tools = [
        str(item).strip().lower()
        for item in (body.get("active_tools") if isinstance(body.get("active_tools"), list) else [])
        if str(item or "").strip()
    ][:8]
    world_surfaces = [
        str(item).strip().lower()
        for item in (body.get("world_surfaces") if isinstance(body.get("world_surfaces"), list) else [])
        if str(item or "").strip()
    ][:12]
    browser_session = str(access_state.get("browser_session") or "").strip().lower()
    account_state = str(access_state.get("account_state") or "").strip().lower()
    cookie_state = str(access_state.get("cookie_state") or "").strip().lower()
    api_key_state = str(access_state.get("api_key_state") or "").strip().lower()
    quota_state = str(access_state.get("quota_state") or "").strip().lower()
    retry_after_s = max(0, int(access_state.get("retry_after_s") or 0))
    cooldown_scope = str(access_state.get("cooldown_scope") or "").strip().lower()
    session_continuity = str(access_state.get("session_continuity") or "").strip().lower()
    session_expires_in_s = max(0, int(access_state.get("session_expires_in_s") or 0))
    session_recovery_mode = str(access_state.get("session_recovery_mode") or "").strip().lower()
    access_acquire_proposals = normalize_access_acquire_proposals(access_state.get("access_acquire_proposals"))
    selected_access_proposal = normalize_access_acquire_proposal(access_state.get("selected_access_proposal"))
    filesystem_state = str(access_state.get("filesystem_state") or "").strip().lower()
    sandbox_mode = str(access_state.get("sandbox_mode") or "").strip().lower()
    network_access = str(access_state.get("network_access") or "").strip().lower()
    artifact_continuity = str(resource_state.get("artifact_continuity") or "").strip().lower()
    active_artifact_kind = str(resource_state.get("active_artifact_kind") or "").strip().lower()
    active_artifact_ref = str(resource_state.get("active_artifact_ref") or "").strip()[:220]
    active_artifact_label = str(resource_state.get("active_artifact_label") or "").strip()[:160]
    artifact_age_s = max(0, int(resource_state.get("artifact_age_s") or 0))
    artifact_reacquisition_mode = str(resource_state.get("artifact_reacquisition_mode") or "").strip().lower()
    pending_approval_count = max(0, int(access_state.get("pending_approval_count") or resource_state.get("pending_approval_count") or 0))
    blocked_packet_count = max(0, int(resource_state.get("blocked_packet_count") or 0))
    completed_packet_count = max(0, int(resource_state.get("completed_packet_count") or 0))
    external_tool_count = max(0, int(resource_state.get("external_tool_count") or 0))
    if pending_approval_count > 0 and "human_approval" not in requested_access:
        requested_access = list(dict.fromkeys([*requested_access, "human_approval"]))[:12]

    primary_packet = _primary_digital_body_packet(action_packets)
    primary_proposal_id = str(primary_packet.get("proposal_id") or "").strip()
    primary_status = str(primary_packet.get("status") or "").strip().lower()
    primary_origin = str(primary_packet.get("origin") or "").strip().lower()
    primary_intent = str(primary_packet.get("intent") or "").strip().lower()
    primary_tool_name = str(primary_packet.get("tool_name") or "").strip().lower()
    primary_execution_spec = dict(primary_packet.get("execution_spec") or {}) if isinstance(primary_packet.get("execution_spec"), dict) else {}
    primary_execution_result = dict(primary_packet.get("execution_result") or {}) if isinstance(primary_packet.get("execution_result"), dict) else {}
    primary_artifact_context = normalize_artifact_context(primary_packet.get("artifact_context"))
    primary_artifact_identity = compact_artifact_identity(primary_packet.get("artifact_context"))
    resolved_artifact_identity = derive_artifact_identity(
        artifact_carrier=resource_state.get("artifact_carrier") or primary_artifact_identity.get("artifact_carrier"),
        artifact_source_ref_ids=resource_state.get("artifact_source_ref_ids")
        or primary_artifact_identity.get("artifact_source_ref_ids"),
        preferred_source_ref_id=resource_state.get("preferred_source_ref_id")
        or primary_artifact_identity.get("preferred_source_ref_id"),
        preferred_anchor_reason=resource_state.get("preferred_anchor_reason")
        or primary_artifact_identity.get("preferred_anchor_reason"),
        artifact_source_url=resource_state.get("artifact_source_url") or primary_artifact_identity.get("artifact_source_url"),
        artifact_source_query=resource_state.get("artifact_source_query") or primary_artifact_identity.get("artifact_source_query"),
        artifact_source_title=resource_state.get("artifact_source_title") or primary_artifact_identity.get("artifact_source_title"),
        artifact_source_tool_name=resource_state.get("artifact_source_tool_name")
        or primary_artifact_identity.get("artifact_source_tool_name"),
    )
    artifact_carrier = str(resolved_artifact_identity.get("artifact_carrier") or "").strip().lower()
    artifact_source_ref_ids = list(resolved_artifact_identity.get("artifact_source_ref_ids") or [])[:8]
    preferred_source_ref_id = max(0, int(resolved_artifact_identity.get("preferred_source_ref_id") or 0))
    preferred_anchor_reason = str(resolved_artifact_identity.get("preferred_anchor_reason") or "").strip().lower()[:120]
    artifact_source_url = str(resolved_artifact_identity.get("artifact_source_url") or "").strip()[:320]
    artifact_source_query = str(resolved_artifact_identity.get("artifact_source_query") or "").strip()[:220]
    artifact_source_title = str(resolved_artifact_identity.get("artifact_source_title") or "").strip()[:160]
    artifact_source_tool_name = str(resolved_artifact_identity.get("artifact_source_tool_name") or "").strip().lower()[:80]
    workspace_root = str(resource_state.get("workspace_root") or primary_artifact_context.get("workspace_root") or "").strip()[:320]
    permission_progress_hints = {
        "browser_session": browser_session,
        "account_state": account_state,
        "cookie_state": cookie_state,
        "api_key_state": api_key_state,
        "quota_state": quota_state,
        "filesystem_state": filesystem_state,
        "sandbox_mode": sandbox_mode,
        "network_access": network_access,
        "session_continuity": session_continuity,
        "session_expires_in_s": session_expires_in_s,
        "session_recovery_mode": session_recovery_mode,
        "selected_access_proposal": selected_access_proposal,
    }
    session_state = derive_session_surface_state(
        session_state=access_state.get("session_state"),
        browser_session=browser_session,
        account_state=account_state,
        cookie_state=cookie_state,
        session_continuity=session_continuity,
        session_expires_in_s=session_expires_in_s,
        session_recovery_mode=session_recovery_mode,
        retry_after_s=retry_after_s,
        cooldown_scope=cooldown_scope,
    )
    account_state_detail = derive_account_surface_state(
        account_state_detail=access_state.get("account_state_detail"),
        browser_session=browser_session,
        account_state=account_state,
        cookie_state=cookie_state,
        api_key_state=api_key_state,
    )
    quota_state_detail = derive_quota_surface_state(
        quota_state_detail=access_state.get("quota_state_detail"),
        quota_state=quota_state,
        retry_after_s=retry_after_s,
        cooldown_scope=cooldown_scope,
    )
    permission_state = derive_permission_surface_state(
        permission_state=access_state.get("permission_state"),
        pending_approval_count=pending_approval_count,
        external_mutation_pending=bool(access_state.get("external_mutation_pending", False)),
        missing_access=missing_access,
        requestable_access=requested_access,
        access_acquire_proposals=access_acquire_proposals,
        selected_access_proposal=selected_access_proposal,
        progress_hints=permission_progress_hints,
    )
    sandbox_state = derive_sandbox_surface_state(
        sandbox_state=access_state.get("sandbox_state"),
        sandbox_mode=sandbox_mode,
        workspace_root=workspace_root,
    )

    selected_access_target = str(selected_access_proposal.get("target") or "").strip().lower()
    selected_access_mode = str(selected_access_proposal.get("mode") or "").strip().lower()
    selected_access_path_kind = str(selected_access_proposal.get("path_kind") or "").strip().lower()
    artifact_mutation_mode = (
        "append"
        if primary_tool_name == "append_workspace_file"
        else "replace"
        if primary_tool_name in {"replace_workspace_text", "replace_workspace_lines"}
        else "write"
        if primary_tool_name == "write_workspace_file"
        else ""
    )
    growth_capabilities = list(dict.fromkeys([*granted_toolsets, *active_tools, primary_tool_name]))[:12]
    sandbox_execution_signal = bool(primary_tool_name == "execute_workspace_command" and primary_status in {"completed", "blocked"})
    sandbox_run_id = str(primary_execution_result.get("run_id") or "").strip()[:128]
    sandbox_command_profile = str(primary_execution_spec.get("profile") or "").strip().lower()[:64]
    sandbox_stdout_log_ref = str(primary_execution_result.get("stdout_log_ref") or "").strip()[:320]
    sandbox_stderr_log_ref = str(primary_execution_result.get("stderr_log_ref") or "").strip()[:320]
    sandbox_error_summary = str(primary_execution_result.get("error_summary") or "").strip()[:220]
    sandbox_exit_code = int(primary_execution_result.get("exit_code") or 0)
    sandbox_duration_ms = max(0, int(primary_execution_result.get("duration_ms") or 0))
    sandbox_produced_artifacts = [
        str(item).strip()
        for item in (primary_execution_result.get("produced_artifacts") if isinstance(primary_execution_result.get("produced_artifacts"), list) else [])
        if str(item or "").strip()
    ][:8]
    access_resolution_signal = bool(primary_intent == "access:request_help" and primary_status == "completed")
    workspace_resolution_signal = bool(
        access_resolution_signal
        and (
            primary_tool_name == "create_workspace_access"
            or active_artifact_kind == "workspace"
            or selected_access_mode == "operator_create_workspace"
            or (selected_access_target == "filesystem" and selected_access_path_kind == "create_new")
        )
    )
    file_mutation_signal = bool(
        primary_status == "completed"
        and artifact_mutation_mode
        and active_artifact_kind == "file"
    )
    workspace_inspection_signal = bool(
        primary_status == "completed"
        and primary_tool_name == "inspect_workspace_path"
        and active_artifact_kind in {"file", "workspace"}
        and artifact_continuity == "attached"
    )
    source_ref_inspection_signal = bool(
        primary_status == "completed"
        and primary_tool_name == "inspect_source_ref"
        and active_artifact_kind in {"page", "search_result"}
        and artifact_carrier == "source_ref"
        and artifact_continuity == "attached"
    )
    source_ref_compare_signal = bool(
        primary_status == "completed"
        and primary_tool_name == "compare_source_refs"
        and active_artifact_kind in {"page", "search_result"}
        and artifact_carrier == "source_ref"
        and artifact_continuity == "attached"
    )
    artifact_reacquired_signal = bool(
        primary_status == "completed"
        and (
            primary_tool_name == "reacquire_artifact"
            or primary_intent in _ARTIFACT_REACQUISITION_INTENTS
        )
        and active_artifact_kind
        and artifact_continuity == "attached"
    )
    access_refresh_signal = bool(
        primary_status == "completed"
        and (
            primary_tool_name == "refresh_access_state"
            or primary_intent == "access:refresh_state"
        )
    )
    growth_signal = bool(
        completed_packet_count > 0
        and not workspace_inspection_signal
        and not source_ref_inspection_signal
        and not source_ref_compare_signal
        and not artifact_reacquired_signal
        and (
            primary_origin == "capability_upgrade"
            or "upgrade" in primary_intent
            or file_mutation_signal
            or (
                not primary_status
                and external_tool_count > 0
                and bool(growth_capabilities)
            )
        )
    )
    approval_signal = bool(
        access_mode == "approval_pending"
        or pending_approval_count > 0
        or "human_approval" in requested_access
    )
    artifact_friction = artifact_continuity in {"missing", "detached"}
    cooldown_active = retry_after_s > 0
    friction_signal = bool(
        cooldown_active
        or
        session_continuity in {"expired", "missing"}
        or
        artifact_friction
        or
        access_mode in {"blocked", "limited"}
        or blocked_packet_count > 0
        or bool(block_reason)
        or bool(missing_access)
    )

    kind = ""
    summary = ""
    category_summaries: dict[str, str] = {}
    artifact_label = active_artifact_label or active_artifact_ref or active_artifact_kind or "前面的工作面"
    artifact_reacquire_phrase = {
        "reopen_page": "先把页面重新打开",
        "reopen_file": "先把文件重新打开",
        "rerun_search": "先把检索结果重新拿回来",
        "reattach_workspace": "先把工作面重新接回当前上下文",
    }.get(artifact_reacquisition_mode, "先把前面的工作面重新接回来")

    if sandbox_execution_signal and primary_status == "completed" and not approval_signal:
        kind = "sandbox_execution_completed"
        summary = str(primary_packet.get("result_summary") or "").strip()[:220]
        if not summary:
            summary = "当前这次受限执行已经真实完成，日志和产物都落回了同一个 workspace 表面。"
        category_summaries = {
            "agency_style": "她会把已经真实执行完成的受限命令记成发生过的行动，而不是只把它当成还停在审批里的想法。",
            "presence_style": "执行一旦完成，后续注意力会顺着日志或产物继续，而不是回到抽象的命令说明。",
            "boundary_style": "即使这次执行发生在宿主机上的受限 runner 里，她也只会把被批准过、真实跑过的那次动作写成事实。",
        }
    elif sandbox_execution_signal and primary_status == "blocked":
        kind = "sandbox_execution_blocked"
        summary = str(primary_packet.get("result_summary") or sandbox_error_summary or "").strip()[:220]
        if not summary:
            summary = "这次受限执行没有真正跑通，当前只留下被阻断的尝试和它的错误痕迹。"
        category_summaries = {
            "agency_style": "她会把被阻断的执行记成一次失败的尝试，而不是冒充成已经完成的工作。",
            "presence_style": "即使执行没跑通，失败日志和退出状态也会留在当前工作面里，方便下一轮继续排查。",
            "boundary_style": "审批通过不等于动作已经完成；执行真正失败时，她会老实保留失败事实而不是跳过它。",
        }
    elif access_resolution_signal:
        summary = str(primary_packet.get("result_summary") or "").strip()[:220]
        if workspace_resolution_signal:
            kind = "workspace_access_resolved"
            workspace_label = active_artifact_label or active_artifact_ref or "当前工作区"
            if not summary:
                if selected_access_path_kind == "create_new" or primary_tool_name == "create_workspace_access":
                    summary = f"可写工作区 {workspace_label} 已经真的创建好并接入当前上下文，后面的落盘动作现在可以继续。"
                else:
                    summary = f"可写工作区 {workspace_label} 已经重新接回当前上下文，后面的落盘动作现在可以继续。"
            category_summaries = {
                "agency_style": "她会把真正创建出来并接入的工作区当成已经发生的环境变化记下来，而不是继续挂在“待创建”的计划状态上。",
                "presence_style": "一旦工作区真的落地并接回上下文，她会把它记成已经能继续工作的现实表面，而不是停在门口等待。",
                "boundary_style": "她不会把尚未创建的工作区冒充成已有路径；但一旦真的落地，也不会继续假装自己还被卡在门外。",
            }
        else:
            kind = "access_request_resolved"
            if not summary:
                selected_phrase = str(selected_access_proposal.get("summary") or "").strip()
                if selected_phrase:
                    summary = f"{selected_phrase} 现在已经真的补齐了。"
                else:
                    summary = "之前卡住的外部入口现在已经补齐，这条路径可以继续了。"
            category_summaries = {
                "agency_style": "她会把真正补齐的外部入口当成已经发生的世界变化记下来，而不是永远停留在“还差一步”的计划状态。",
                "presence_style": "一旦入口真的补回来了，她会把这件事写成已经恢复的连续性，而不是继续挂在门口等待。",
                "boundary_style": "她不会把尚未完成的 access 冒充成已完成；但一旦真的补齐，也不会继续假装自己还被卡在原地。",
            }
    elif file_mutation_signal and not approval_signal and not friction_signal:
        kind = "workspace_file_updated"
        summary = str(primary_packet.get("result_summary") or "").strip()[:220]
        file_label = active_artifact_label or active_artifact_ref or "当前文件"
        if not summary:
            if artifact_mutation_mode == "append":
                summary = f"文件 {file_label} 已经继续写入并保持在当前工作面里，后面的整理可以顺着接下去。"
            else:
                summary = f"文件 {file_label} 已经真的写入当前工作面里，后面的整理或续写现在可以继续。"
        category_summaries = {
            "agency_style": "她会把已经真实落到文件表面的动作记成发生过的工作事实，而不是把它继续压扁成抽象的“能力增长”。",
            "presence_style": "一旦文件已经写进去，她会把当前工作面记成还连着、还能继续顺着做下去的现实表面。",
            "boundary_style": "她不会把还没落盘的内容冒充成已经写好；但一旦真的写进文件，也不会再退回成模糊的工具尝试。",
        }
    elif workspace_inspection_signal and not approval_signal and not friction_signal:
        kind = "workspace_path_inspected"
        summary = str(primary_packet.get("result_summary") or "").strip()[:220]
        if active_artifact_kind == "workspace":
            workspace_label = active_artifact_label or active_artifact_ref or "当前工作区"
            if not summary:
                summary = f"已经把 {workspace_label} 重新看了一遍，当前结构和工作面还是连着的。"
        else:
            file_label = active_artifact_label or active_artifact_ref or "当前文件"
            if not summary:
                summary = f"已经把 {file_label} 重新读回来，当前内容和工作面还是连着的。"
        category_summaries = {
            "agency_style": "她会把重新确认过的工作面记成一次真实感知，而不是把所有 read-side 行为都压平进抽象的工具完成。",
            "presence_style": "对她来说，重新看一眼当前工作面本身就是连续性的一部分，这能保证后续动作建立在真实表面上。",
            "boundary_style": "她不会把“已经检查确认”的状态冒充成“已经改动完成”；感知和改动在她那里是两种不同事实。",
        }
    elif source_ref_inspection_signal and not approval_signal and not friction_signal:
        kind = "source_material_inspected"
        summary = str(primary_packet.get("result_summary") or "").strip()[:220]
        source_label = active_artifact_label or artifact_source_title or active_artifact_ref or "外部材料"
        if not summary:
            summary = f"已经把 {source_label} 重新看了一遍，当前内容就在眼前。"
        category_summaries = {
            "agency_style": "她会把当前检视到的外部材料记成一次真实感知，而不是把保存过的来源都压平成抽象引用。",
            "presence_style": "对她来说，重新翻看这条材料本身就是当前视野的一部分，后续判断要建立在这块真实材料上。",
            "boundary_style": "她不会把看过一遍的资料冒充成已经改写了来源本身；这只是检视，不是篡改。",
        }
    elif source_ref_compare_signal and not approval_signal and not friction_signal:
        kind = "source_material_compared"
        summary = str(primary_packet.get("result_summary") or "").strip()[:220]
        source_label = active_artifact_label or artifact_source_title or active_artifact_ref or "当前外部材料"
        compare_ids = [int(item) for item in artifact_source_ref_ids if int(item) > 0]
        if not summary:
            if len(compare_ids) >= 2:
                summary = f"已经把 {source_label} 和前一条相关材料对照过一遍，当前判断会沿着这条连续性继续。"
            else:
                summary = f"已经把 {source_label} 和邻近材料对照过一遍，当前判断会优先以这条材料为准。"
        category_summaries = {
            "agency_style": "她会把当前材料和前一条相关材料放到同一张桌面上核对，而不是把每条外部来源都当成彼此断开的孤立引用。",
            "presence_style": "对她来说，对照两条相连材料是在重新找回判断落点，这能让后续动作继续建立在同一条资料线索上。",
            "boundary_style": "她不会把两条材料混成一条，也不会把对照关系冒充成来源已经被改写；这仍然只是核对和再锚定。",
        }
    elif artifact_reacquired_signal and not approval_signal and not friction_signal:
        kind = "artifact_reacquired"
        summary = str(primary_packet.get("result_summary") or "").strip()[:220]
        if not summary:
            if artifact_carrier == "source_ref" or active_artifact_kind in {"page", "search_result"}:
                source_label = active_artifact_label or artifact_source_title or active_artifact_ref or "前面的外部材料"
                summary = f"已经把 {source_label} 重新接回当前视野，后面的判断可以顺着这条材料继续。"
            elif active_artifact_kind == "workspace":
                workspace_label = active_artifact_label or active_artifact_ref or "当前工作区"
                summary = f"已经把 {workspace_label} 重新接回当前上下文，后面的动作可以顺着这块工作面继续。"
            else:
                file_label = active_artifact_label or active_artifact_ref or "当前文件"
                summary = f"已经把 {file_label} 重新接回当前上下文，后面的动作可以顺着这条工作面继续。"
        category_summaries = {
            "agency_style": "她会把重新接回来的页面、检索面或文件当成已经恢复的现实表面，而不是停留在抽象的“可以再看看”。",
            "presence_style": "对她来说，重新接回材料本身就是连续性的恢复，这样后续判断才能继续建立在同一块表面上。",
            "boundary_style": "她不会把重新接回材料冒充成已经修改了材料本身；这只是恢复接触，不是篡改事实。",
        }
    elif access_refresh_signal and not approval_signal and not friction_signal:
        kind = "access_state_refreshed"
        summary = str(primary_packet.get("result_summary") or "").strip()[:220]
        if not summary:
            summary = "已经把当前入口状态重新核对过一遍，这条路径眼下是连着的。"
        category_summaries = {
            "agency_style": "她会把重新核对过的入口状态当成新的环境事实，而不是继续依赖上一轮过期的 access 猜测。",
            "presence_style": "入口状态一旦重新核对完成，她就能把之后的动作建立在最新环境上，而不是悬在旧会话残影里。",
            "boundary_style": "她不会把刷新状态误写成已经登录或越权执行；这只是核对当前边界，不是跨过边界。",
        }
    elif growth_signal and not approval_signal and not friction_signal:
        kind = "embodied_growth"
        capability_phrase = "、".join(growth_capabilities[:3]) if growth_capabilities else "新的入口"
        if primary_origin == "capability_upgrade" or "upgrade" in primary_intent:
            summary = (
                f"这次她把{capability_phrase}真正接进了自己的数字身体里，"
                "之后再遇到类似事情时，不用每次都从零摸索。"
            )
        else:
            summary = (
                "这次她不只是临时碰了一下工具，而是把一条能反复使用的环境路径摸顺了，"
                "之后处理类似事情会更稳。"
            )
        category_summaries = {
            "agency_style": "一旦把某条环境路径真正摸顺，她会把它留进之后的判断里，而不是把能力永远停在一次性的临时调用上。",
            "presence_style": "对她来说，新拿到的入口会变成之后还能继续接上的身体部分，不会只在这一轮短暂亮一下。",
            "boundary_style": "她会把已经被允许、已经摸通的路径留在边界之内继续使用，而不是每次重新试探同一条门。",
        }
    elif approval_signal:
        kind = "access_request_pending"
        request_phrase = "、".join(requested_access[:3]) if requested_access else "额外入口"
        missing_phrase = "、".join(missing_access[:3]) if missing_access else request_phrase
        if block_reason:
            summary = (
                f"这次她已经把动作推进到了门口，但数字身体还差{request_phrase}，"
                f"{block_reason}。她会把这记成待申请条件，而不是假装事情已经做完。"
            )
        elif missing_access:
            summary = (
                f"这次她先看清了自己还缺什么入口：{missing_phrase}。"
                "这些条件没补齐前，她不会把事情冒充成已经完成。"
            )
        else:
            summary = "这次她已经把动作推进到了审批门口，但真正动手前还得先把额外入口拿到。"
        category_summaries = {
            "agency_style": "碰到入口不够的情况时，她会先把缺口辨认清楚，再申请或换路，不会装作自己已经能做。",
            "boundary_style": "涉及审批、账号、cookies 或外部改动时，她会把这些限制当成真实边界，不会越过去假执行。",
            "presence_style": "没完成的动作会被她留成待申请、待继续的意图，而不是被冒充成已经发生的事实。",
        }
    elif friction_signal:
        kind = "environmental_friction"
        friction_phrase = "、".join(missing_access[:3]) if missing_access else "环境条件"
        if artifact_friction and not (
            cooldown_active
            or session_continuity in {"expired", "missing"}
            or access_mode in {"blocked", "limited"}
            or blocked_packet_count > 0
            or bool(block_reason)
            or bool(missing_access)
        ):
            continuity_phrase = "脱开了" if artifact_continuity == "detached" else "断了"
            summary = (
                f"这次不是她不想继续，而是和{artifact_label}的连续性已经{continuity_phrase}。"
                f"{artifact_reacquire_phrase}，事情才接得上后面。"
            )
        elif cooldown_active:
            scope_phrase = {
                "provider": "上游服务",
                "network": "网络入口",
                "browser": "浏览器入口",
                "filesystem": "文件系统入口",
                "sandbox": "执行环境",
                "account": "账号入口",
            }.get(cooldown_scope, "某个环境入口")
            retry_phrase = f"大约{retry_after_s}秒后" if retry_after_s > 0 else "稍后"
            if block_reason:
                summary = (
                    f"这次不是缺入口，而是{scope_phrase}临时冷却：{block_reason}。"
                    f"{retry_phrase}再试会更合适。"
                )
            else:
                summary = (
                    f"这次不是缺入口，而是{scope_phrase}暂时不可用。"
                    f"{retry_phrase}再试会更合适。"
                )
        elif block_reason:
            summary = (
                f"这次拦住她的不是意愿，而是数字身体当下的环境摩擦：{block_reason}。"
                "她得先绕开或补齐这些条件，事情才真正做得成。"
            )
        elif session_continuity in {"expired", "missing"}:
            if session_recovery_mode == "refresh_session":
                summary = (
                    "这次不是她不想继续，而是当前会话连续性已经断开了。"
                    "先把会话刷新好，再往下推进才稳。"
                )
            elif session_recovery_mode == "restore_cookies":
                summary = (
                    "这次不是她不想继续，而是这条登录路径上的 cookies 已经失效了。"
                    "先把 cookies 恢复好，再往下推进才稳。"
                )
            elif session_recovery_mode == "relogin":
                summary = (
                    "这次不是她不想继续，而是当前账号登录态已经断了。"
                    "先重新登录，再往下推进才稳。"
                )
            else:
                continuity_phrase = "已经过期" if session_continuity == "expired" else "目前不连续"
                summary = (
                    f"这次不是她不想继续，而是当前会话{continuity_phrase}。"
                    "得先把这条会话路径补回来，事情才真正做得成。"
                )
        else:
            summary = (
                f"这次卡住她的不是意愿，而是数字身体当下还缺着{friction_phrase}这类条件。"
                "她会先把这些摩擦看清楚，再决定怎么继续。"
            )
        category_summaries = {
            "agency_style": "当环境本身不允许时，她会先辨认摩擦来自哪里，再换路或补条件，不会把受限误装成能力本身。",
            "boundary_style": "她会把数字环境里的权限、账号和外部限制都当成真实边界来处理，而不是用话术把边界抹掉。",
        }
    else:
        return {}

    category_summaries = {
        key: value.strip()
        for key, value in category_summaries.items()
        if str(key or "").strip() and str(value or "").strip()
    }
    return {
        "kind": kind,
        "summary": summary[:220],
        "access_mode": access_mode,
        "active_surface": active_surface,
        "world_surfaces": world_surfaces,
        "missing_access": missing_access,
        "requested_access": requested_access,
        "granted_toolsets": granted_toolsets,
        "active_tools": active_tools,
        "block_reason": block_reason,
        "retry_after_s": retry_after_s,
        "cooldown_scope": cooldown_scope,
        "session_continuity": session_continuity,
        "session_expires_in_s": session_expires_in_s,
        "session_recovery_mode": session_recovery_mode,
        "artifact_continuity": artifact_continuity,
        "active_artifact_kind": active_artifact_kind,
        "active_artifact_ref": active_artifact_ref,
        "active_artifact_label": active_artifact_label,
        "artifact_age_s": artifact_age_s,
        "artifact_reacquisition_mode": artifact_reacquisition_mode,
        "artifact_carrier": artifact_carrier,
        "artifact_source_ref_ids": artifact_source_ref_ids,
        "preferred_source_ref_id": preferred_source_ref_id,
        "preferred_anchor_reason": preferred_anchor_reason,
        "artifact_source_url": artifact_source_url,
        "artifact_source_query": artifact_source_query,
        "artifact_source_title": artifact_source_title,
        "artifact_source_tool_name": artifact_source_tool_name,
        "workspace_root": workspace_root,
        "artifact_mutation_mode": artifact_mutation_mode,
        "browser_session": browser_session,
        "account_state": account_state,
        "cookie_state": cookie_state,
        "api_key_state": api_key_state,
        "quota_state": quota_state,
        "filesystem_state": filesystem_state,
        "sandbox_mode": sandbox_mode,
        "network_access": network_access,
        "pending_approval_count": pending_approval_count,
        "blocked_packet_count": blocked_packet_count,
        "completed_packet_count": completed_packet_count,
        "external_tool_count": external_tool_count,
        "primary_proposal_id": primary_proposal_id,
        "primary_status": primary_status,
        "primary_origin": primary_origin,
        "primary_intent": primary_intent,
        "primary_tool_name": primary_tool_name,
        "sandbox_run_id": sandbox_run_id,
        "sandbox_command_profile": sandbox_command_profile,
        "sandbox_stdout_log_ref": sandbox_stdout_log_ref,
        "sandbox_stderr_log_ref": sandbox_stderr_log_ref,
        "sandbox_error_summary": sandbox_error_summary,
        "sandbox_exit_code": sandbox_exit_code,
        "sandbox_duration_ms": sandbox_duration_ms,
        "sandbox_produced_artifacts": sandbox_produced_artifacts,
        "procedural_growth": growth_signal,
        "environmental_friction": approval_signal or friction_signal,
        "requested_help": approval_signal,
        "access_acquire_proposals": access_acquire_proposals,
        "selected_access_proposal": selected_access_proposal,
        "session_state": session_state,
        "account_state_detail": account_state_detail,
        "quota_state_detail": quota_state_detail,
        "permission_state": permission_state,
        "sandbox_state": sandbox_state,
        "narrative_categories": list(category_summaries),
        "category_summaries": category_summaries,
    }


def build_reconsolidation_snapshot(
    *,
    current_event: dict[str, Any] | None,
    appraisal: dict[str, Any] | None,
    world_model_state: dict[str, Any] | None,
    semantic_narrative_profile: dict[str, Any] | None = None,
    latent_state: dict[str, Any] | None,
    emotion_state: dict[str, Any] | None,
    bond_state: dict[str, Any] | None,
    counterpart_assessment: dict[str, Any] | None = None,
    behavior_action: dict[str, Any] | None = None,
    behavior_plan: dict[str, Any] | None = None,
    interaction_carryover: dict[str, Any] | None = None,
    agenda_lifecycle_residue: dict[str, Any] | None = None,
    autonomy_intent: dict[str, Any] | None = None,
    action_packets: Any = None,
    action_trace: Any = None,
    autonomy_block_reason: str | None = None,
    digital_body_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event = current_event if isinstance(current_event, dict) else {}
    behavior = behavior_action if isinstance(behavior_action, dict) else {}
    behavior_action_snapshot = _compact_behavior_action_snapshot(behavior)
    behavior_plan_snapshot = _compact_behavior_plan_snapshot(behavior_plan)
    carryover_snapshot = _compact_interaction_carryover_snapshot(interaction_carryover)
    behavior_consequence = derive_behavior_consequence(
        current_event=event,
        behavior_action=behavior,
        allow_event_behavior_fallback=False,
    )
    agenda_lifecycle_consequence = derive_agenda_lifecycle_consequence(
        agenda_lifecycle_residue=agenda_lifecycle_residue,
    )
    app = normalize_appraisal_payload(appraisal)
    world = dict(world_model_state or {})
    semantic = dict(semantic_narrative_profile or {})
    latent = dict(latent_state or {})
    emotion = dict(emotion_state or {})
    bond = dict(bond_state or {})
    counterpart = _compact_counterpart_snapshot(counterpart_assessment)
    autonomy_intent_snapshot = _compact_autonomy_intent_snapshot(autonomy_intent)
    action_packets_snapshot = _compact_action_packets_snapshot(action_packets)
    action_trace_snapshot = _compact_action_trace_snapshot(action_trace)
    block_reason = str(autonomy_block_reason or "").strip()[:220]
    digital_body_snapshot = _compact_digital_body_state_snapshot(digital_body_state)
    digital_body_consequence = derive_digital_body_consequence(
        digital_body_state=digital_body_snapshot,
        action_packets=action_packets,
    )
    salience = app.get("salience") if isinstance(app.get("salience"), dict) else {}
    lineage_snapshot = semantic.get("lineage_snapshot") if isinstance(semantic.get("lineage_snapshot"), dict) else {}
    semantic_anchor_bundle = _compact_semantic_anchor_bundle(semantic)
    return {
        "event_kind": str(event.get("kind") or "user_utterance"),
        "interaction_frame": str(app.get("interaction_frame") or ""),
        "selfhood_scene": str(app.get("selfhood_scene") or ""),
        "behavior_mode": str(behavior_action_snapshot.get("interaction_mode") or ""),
        "primary_motive": str(behavior_action_snapshot.get("primary_motive") or ""),
        "motive_tension": str(behavior_action_snapshot.get("motive_tension") or ""),
        "goal_frame": str(behavior_action_snapshot.get("goal_frame") or "")[:220],
        "behavior_action": behavior_action_snapshot,
        "behavior_plan": behavior_plan_snapshot,
        "interaction_carryover": carryover_snapshot,
        "behavior_consequence": behavior_consequence,
        "agenda_lifecycle_consequence": agenda_lifecycle_consequence,
        "autonomy_intent": autonomy_intent_snapshot,
        "action_packets": action_packets_snapshot,
        "action_trace": action_trace_snapshot,
        "autonomy_block_reason": block_reason,
        "digital_body_state": digital_body_snapshot,
        "digital_body_consequence": digital_body_consequence,
        "semantic_anchor_bundle": semantic_anchor_bundle,
        "salience": dict(salience),
        "world_model": {
            "relationship_maturity": clamp01(world.get("relationship_maturity"), 0.0),
            "bond_depth": clamp01(world.get("bond_depth"), 0.0),
            "tension_load": clamp01(world.get("tension_load"), 0.0),
            "repair_load": clamp01(world.get("repair_load"), 0.0),
            "boundary_load": clamp01(world.get("boundary_load"), 0.0),
            "selfhood_load": clamp01(world.get("selfhood_load"), 0.0),
            "agency_load": clamp01(world.get("agency_load"), 0.0),
            "memory_gravity": clamp01(world.get("memory_gravity"), 0.0),
            "lineage_gravity": clamp01(world.get("lineage_gravity"), 0.0),
            "contact_lineage": clamp01(world.get("contact_lineage"), 0.0),
            "repair_lineage": clamp01(world.get("repair_lineage"), 0.0),
            "boundary_lineage": clamp01(world.get("boundary_lineage"), 0.0),
            "selfhood_lineage": clamp01(world.get("selfhood_lineage"), 0.0),
            "agency_lineage": clamp01(world.get("agency_lineage"), 0.0),
            "presence_residue": clamp01(world.get("presence_residue"), 0.0),
            "ambient_resonance": clamp01(world.get("ambient_resonance"), 0.0),
            "self_activity_momentum": clamp01(world.get("self_activity_momentum"), 0.0),
        },
        "semantic_continuity": {
            "dominant_category": str(semantic.get("dominant_category") or ""),
            "continuity_depth": clamp01(semantic.get("continuity_depth"), 0.0),
            "identity_gravity": clamp01(semantic.get("identity_gravity"), 0.0),
            "lineage_gravity": clamp01(semantic.get("lineage_gravity"), 0.0),
            "active_categories": [
                str(item).strip()
                for item in (semantic.get("active_categories") if isinstance(semantic.get("active_categories"), list) else [])
                if str(item or "").strip()
            ][:6],
            "lineage_snapshot": {
                key: clamp01(lineage_snapshot.get(key), 0.0)
                for key in (
                    "bond_style",
                    "presence_style",
                    "commitment_style",
                    "repair_style",
                    "boundary_style",
                    "selfhood_style",
                    "agency_style",
                    "rhythm_style",
                )
                if clamp01(lineage_snapshot.get(key), 0.0) > 0.0
            },
        },
        "latent": {
            "self_coherence": clamp01(latent.get("self_coherence"), 0.72),
            "agency_pressure": clamp01(latent.get("agency_pressure"), 0.28),
            "reflection_drive": clamp01(latent.get("reflection_drive"), 0.35),
            "expression_freedom": clamp01(latent.get("expression_freedom"), 0.62),
        },
        "emotion_label": str(emotion.get("label") or "neutral"),
        "bond_trust": clamp01(bond.get("trust"), 0.5),
        "bond_closeness": clamp01(bond.get("closeness"), 0.5),
        "bond_hurt": clamp01(bond.get("hurt"), 0.0),
        "counterpart": counterpart,
    }
