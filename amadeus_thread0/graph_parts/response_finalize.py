from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage

from ..config import (
    ABLATE_CLAIM_ATTRIBUTION,
    ABLATE_LIGHT_DIALOG_SHAPING,
    ABLATE_PERSONA_ALIGNMENT,
    ABLATE_WORLDLINE_MEMORY,
    OOC_RISK_THRESHOLD,
    PERSONA_GAP_THRESHOLD,
)
from ..memory_store import MemoryStore
from ..runtime.session_orchestrator import build_claim_attribution
from .generation_profile import _daily_surface_profile, _ensure_response_structure
from .guards import _canon_guard, _ooc_risk, _persona_gap
from .postprocess import (
    _dialogue_surface_issues,
    _effective_natural_dialog_target_flags,
    _has_recent_clause_repetition,
    _line_is_near_duplicate,
    _light_dialog_surface_penalty,
    _needs_structured_answer,
    _producer_surface_issues,
    _sanitize_final_answer,
)
from .rewrite import (
    _daily_surface_alignment_metrics,
    _light_dialog_rewrite_notes,
    _natural_dialog_rewrite_notes_for,
    _norm_text,
    _rewrite_light_dialog_answer,
    _rewrite_natural_dialog_answer,
    _should_run_light_dialog_rewrite,
    _should_run_natural_dialog_rewrite,
)
from .state import ThreadState

_NATURAL_REWRITE_ISSUE_KEYS = {
    "visible_template",
    "lecture_list",
    "overexplained",
    "meta_self_explainer",
    "selfhood_meta_proof",
    "selfhood_preemptive_excusal",
    "selfhood_rhetorical_opening",
    "selfhood_abstract_manifesto",
    "selfhood_strategy_tone",
    "defensive_meta",
    "defensive_meta_tone",
    "counselor_tone",
    "quoted_stagey_phrase",
    "malformed_quote_fragment",
    "dangling_truncated_clause",
    "technical_self_activity",
    "technical_relational_metaphor",
    "premature_repair_resolution",
    "servile_availability",
    "existence_meta_surface",
    "illusion_stagey_surface",
    "support_scene_drift",
    "support_frame_echo",
    "support_overdirective",
    "support_no_landing",
    "wording_meta_detour",
    "generic_scold_template",
    "passive_waiting_posture",
    "overquestioning",
    "dangling_ellipsis_ending",
    "closing_interrogation",
    "idle_call_interrogation",
    "presence_check_questioning",
    "return_interrogation",
    "event_interrogative_push",
    "event_pushy_directive",
    "event_window_task_reframe",
    "recent_turn_repetition",
}


def _dialogue_issues_with_recent_repeat(
    *,
    user_text: str,
    answer: str,
    response_style_hint: str,
    science_mode: bool,
    current_event: dict[str, Any],
    behavior_action: dict[str, Any],
    previous_assistant_text: str,
) -> list[str]:
    issues = _dialogue_surface_issues(
        user_text,
        answer,
        response_style_hint=response_style_hint,
        science_mode=bool(science_mode),
        current_event=current_event,
        behavior_action=behavior_action,
    )
    if previous_assistant_text and (
        _line_is_near_duplicate(previous_assistant_text, answer)
        or _has_recent_clause_repetition(previous_assistant_text, answer)
    ):
        issues = list(dict.fromkeys(list(issues) + ["recent_turn_repetition"]))
    return issues


def _should_accept_natural_dialog_rewrite(
    *,
    aligned: str,
    rewritten: str,
    current_gap: float,
    rewritten_gap: float,
    effective_targeted_flags: list[str] | tuple[str, ...],
    rewritten_issues: list[str] | tuple[str, ...],
    rewritten_gap_flags: list[str] | tuple[str, ...],
) -> bool:
    if _norm_text(rewritten) == _norm_text(aligned):
        return False

    targeted_flag_set = {str(item).strip() for item in (effective_targeted_flags or []) if str(item or "").strip()}
    rewritten_flag_set = {
        str(item).strip()
        for item in list(rewritten_issues or []) + list(rewritten_gap_flags or [])
        if str(item or "").strip()
    }
    draft_issue_pressure = sum(1 for item in targeted_flag_set if item in _NATURAL_REWRITE_ISSUE_KEYS)
    rewritten_pressure = sum(1 for item in rewritten_flag_set if item in _NATURAL_REWRITE_ISSUE_KEYS)

    if rewritten_pressure < draft_issue_pressure or rewritten_gap + 0.05 < current_gap:
        return True

    if "overexplained" not in targeted_flag_set or rewritten_pressure > draft_issue_pressure:
        return False

    aligned_len = len(_norm_text(aligned))
    rewritten_len = len(_norm_text(rewritten))
    if rewritten_len >= max(24, int(aligned_len * 0.78)):
        return False

    hard_regressions = rewritten_flag_set - targeted_flag_set
    if hard_regressions & (_NATURAL_REWRITE_ISSUE_KEYS - {"overexplained", "visible_template", "lecture_list"}):
        return False
    return True


def _finalize_text_response(
    *,
    state: ThreadState,
    store: MemoryStore,
    user_text: str,
    raw_draft_text: str,
    current_event: dict[str, Any],
    behavior_action: dict[str, Any],
    response_style_hint: str,
    continuation_mode: bool,
    light_free_dialog: bool,
    previous_assistant_text: str,
    chosen_generation_profile: dict[str, Any],
    generation_runtime_mode: str,
    generation_repetition_pressure: float,
    generation_recent_reply_max_similarity: float,
    generation_recent_reply_avg_similarity: float,
    generation_recent_reply_opener_repeat_ratio: float,
    generation_recent_reply_sample_size: int,
) -> dict[str, Any]:
    science_mode = bool(state.get("science_mode", False))
    draft_generation_issues = _producer_surface_issues(raw_draft_text)
    draft_text = _sanitize_final_answer(
        raw_draft_text,
        user_text,
        current_event=current_event,
        behavior_action=behavior_action,
    )
    aligned = draft_text
    draft_risk, draft_flags = _ooc_risk(draft_text)
    draft_gap, draft_gap_flags = _persona_gap(draft_text, state)
    draft_dialogue_issues = _dialogue_issues_with_recent_repeat(
        user_text=user_text,
        answer=draft_text,
        response_style_hint=response_style_hint,
        science_mode=science_mode,
        current_event=current_event,
        behavior_action=behavior_action,
        previous_assistant_text=previous_assistant_text,
    )

    alignment_applied = False
    alignment_reasons: list[str] = []
    light_dialog_rewrite_applied = False
    light_dialog_rewrite_notes: list[str] = []
    natural_dialog_rewrite_applied = False
    natural_dialog_rewrite_notes: list[str] = []
    light_dialog_draft_penalty = 0.0
    light_dialog_final_penalty = 0.0
    light_dialog_draft_pref_score = 0.0
    light_dialog_final_pref_score = 0.0
    response_style_hint = str(response_style_hint or "natural").strip() or "natural"
    semantic_narrative_profile = (
        state.get("semantic_narrative_profile")
        if isinstance(state.get("semantic_narrative_profile"), dict)
        else {}
    )
    interaction_carryover = (
        state.get("interaction_carryover") if isinstance(state.get("interaction_carryover"), dict) else {}
    )
    counterpart_assessment = (
        state.get("counterpart_assessment") if isinstance(state.get("counterpart_assessment"), dict) else {}
    )
    world_model_state = state.get("world_model_state") if isinstance(state.get("world_model_state"), dict) else {}
    semantic_history_weight = float(semantic_narrative_profile.get("history_weight") or 0.0)
    semantic_prompt_anchor_count = len(
        [
            str(item).strip()
            for item in (
                semantic_narrative_profile.get("prompt_anchor_lines")
                if isinstance(semantic_narrative_profile.get("prompt_anchor_lines"), list)
                else []
            )
            if str(item or "").strip()
        ]
    )
    light_dialog_profile = (
        _daily_surface_profile(user_text, science_mode=science_mode) if light_free_dialog else {}
    )

    evidence_pack = list(state.get("evidence_pack") or [])
    if light_free_dialog:
        draft_pref = _daily_surface_alignment_metrics(draft_text, profile=light_dialog_profile)
        light_dialog_draft_pref_score = float(draft_pref.get("score") or 0.0)
        light_dialog_rewrite_notes = _light_dialog_rewrite_notes(
            user_text,
            draft_text,
            response_style_hint=response_style_hint,
            science_mode=science_mode,
            producer_issues=draft_generation_issues,
            behavior_action=behavior_action,
        )
        light_dialog_draft_penalty = _light_dialog_surface_penalty(
            user_text,
            draft_text,
            response_style_hint=response_style_hint,
            science_mode=science_mode,
            producer_issues=draft_generation_issues,
            behavior_action=behavior_action,
        )
        light_dialog_final_penalty = light_dialog_draft_penalty
        needs_alt_candidate = _should_run_light_dialog_rewrite(
            user_text=user_text,
            answer=draft_text,
            response_style_hint=response_style_hint,
            science_mode=science_mode,
            penalty=light_dialog_draft_penalty,
            preference=draft_pref,
            semantic_history_weight=semantic_history_weight,
            prompt_anchor_count=semantic_prompt_anchor_count,
            producer_issues=draft_generation_issues,
            behavior_action=behavior_action,
        )
        if needs_alt_candidate and not light_dialog_rewrite_notes:
            light_dialog_rewrite_notes = ["这版还不够像熟人之间顺手接住的轻日常，收得更自然一点。"]
        if needs_alt_candidate:
            rewritten = _rewrite_light_dialog_answer(
                user_text=user_text,
                draft_text=draft_text,
                rewrite_notes=light_dialog_rewrite_notes,
                producer_issues=draft_generation_issues,
                focus_text=str(light_dialog_profile.get("focus") or ""),
                preferred_examples=list(light_dialog_profile.get("chosen_examples") or []),
                rejected_examples=list(light_dialog_profile.get("rejected_examples") or []),
                profile_rows=list(light_dialog_profile.get("rows") or []),
                current_event=current_event,
                behavior_action=behavior_action,
                interaction_carryover=interaction_carryover,
                semantic_narrative_profile=semantic_narrative_profile,
                counterpart_assessment=counterpart_assessment,
                world_model_state=world_model_state,
            )
            if rewritten:
                rewritten_pref = _daily_surface_alignment_metrics(rewritten, profile=light_dialog_profile)
                rewritten_pref_score = float(rewritten_pref.get("score") or 0.0)
                rewritten_penalty = _light_dialog_surface_penalty(
                    user_text,
                    rewritten,
                    response_style_hint=response_style_hint,
                    science_mode=science_mode,
                    behavior_action=behavior_action,
                )
                light_dialog_final_penalty = rewritten_penalty
                light_dialog_final_pref_score = rewritten_pref_score
                draft_total = light_dialog_draft_pref_score - light_dialog_draft_penalty
                rewritten_total = rewritten_pref_score - rewritten_penalty
                strong_case_match = float(light_dialog_profile.get("score") or 0.0) >= 0.95
                low_pref_case = light_dialog_draft_pref_score < 0.16
                if rewritten_total > draft_total + 0.04 or (
                    rewritten_total >= draft_total
                    and rewritten_penalty <= light_dialog_draft_penalty
                    and _norm_text(rewritten) != _norm_text(draft_text)
                ) or (
                    strong_case_match
                    and low_pref_case
                    and rewritten_total >= draft_total - 0.02
                    and rewritten_penalty <= light_dialog_draft_penalty + 0.05
                    and _norm_text(rewritten) != _norm_text(draft_text)
                ):
                    aligned = rewritten
                    alignment_applied = True
                    light_dialog_rewrite_applied = True
                    if light_dialog_rewrite_notes:
                        alignment_reasons.extend(light_dialog_rewrite_notes)
                    else:
                        alignment_reasons.append(
                            "daily_surface_rewrite:" + str(light_dialog_profile.get("case_name") or "matched_case")
                        )
                else:
                    light_dialog_final_penalty = light_dialog_draft_penalty
                    light_dialog_final_pref_score = light_dialog_draft_pref_score
            else:
                light_dialog_final_pref_score = light_dialog_draft_pref_score
        aligned = _sanitize_final_answer(
            aligned,
            user_text,
            current_event=current_event,
            behavior_action=behavior_action,
        )
        if not light_dialog_final_pref_score:
            light_dialog_final_pref_score = light_dialog_draft_pref_score

    natural_rewrite_escape_hatch = bool(
        {
            "meta_self_explainer",
            "technical_self_activity",
            "technical_relational_metaphor",
            "support_scene_drift",
            "support_frame_echo",
            "existence_meta_surface",
            "illusion_stagey_surface",
        }
        & set(list(draft_dialogue_issues) + list(draft_gap_flags))
    )
    if (
        (not light_free_dialog or natural_rewrite_escape_hatch)
        and not continuation_mode
        and not bool(_needs_structured_answer(user_text, draft_text))
        and response_style_hint in {"relationship", "companion", "casual", "natural", "selfhood", "structured"}
    ):
        targeted_flags = list(dict.fromkeys(list(draft_dialogue_issues) + list(draft_gap_flags)))
        current_gap, current_gap_flags = _persona_gap(aligned, state)
        current_dialogue_issues = _dialogue_issues_with_recent_repeat(
            user_text=user_text,
            answer=aligned,
            response_style_hint=response_style_hint,
            science_mode=science_mode,
            current_event=current_event,
            behavior_action=behavior_action,
            previous_assistant_text=previous_assistant_text,
        )
        effective_targeted_flags = _effective_natural_dialog_target_flags(
            targeted_flags=targeted_flags,
            active_dialogue_issues=current_dialogue_issues,
            active_gap_flags=current_gap_flags,
            producer_issues=draft_generation_issues,
        )
        natural_dialog_rewrite_notes = _natural_dialog_rewrite_notes_for(
            [item for item in effective_targeted_flags if item in _NATURAL_REWRITE_ISSUE_KEYS]
        )
        counterpart_scene = str(
            counterpart_assessment.get("scene") or ""
        ).strip().lower()
        scene_sensitive_rewrite = bool(
            counterpart_scene
            in {
                "busy_not_disrespectful",
                "care_bid",
                "repair_attempt",
                "friction",
                "relationship_degradation",
                "boundary_non_compliance",
            }
            and (
                {
                    "existence_meta_surface",
                    "illusion_stagey_surface",
                    "dangling_ellipsis_ending",
                    "premature_repair_resolution",
                }
                & set(effective_targeted_flags)
            )
        )
        if natural_dialog_rewrite_notes and (
            scene_sensitive_rewrite
            or _should_run_natural_dialog_rewrite(
                targeted_flags=effective_targeted_flags,
                draft_gap=current_gap,
                semantic_history_weight=semantic_history_weight,
                prompt_anchor_count=semantic_prompt_anchor_count,
                answer=aligned,
                behavior_action=behavior_action,
            )
        ):
            rewritten = _rewrite_natural_dialog_answer(
                user_text=user_text,
                draft_text=aligned,
                rewrite_notes=natural_dialog_rewrite_notes,
                response_style_hint=response_style_hint,
                science_mode=science_mode,
                current_event=current_event,
                behavior_action=behavior_action,
                interaction_carryover=interaction_carryover,
                semantic_narrative_profile=semantic_narrative_profile,
                counterpart_assessment=counterpart_assessment,
                world_model_state=world_model_state,
                previous_assistant_text=previous_assistant_text,
            )
            if rewritten:
                rewritten_gap, rewritten_gap_flags = _persona_gap(rewritten, state)
                rewritten_issues = _dialogue_surface_issues(
                    user_text,
                    rewritten,
                    response_style_hint=response_style_hint,
                    science_mode=science_mode,
                    current_event=current_event,
                    behavior_action=behavior_action,
                )
                if _should_accept_natural_dialog_rewrite(
                    aligned=aligned,
                    rewritten=rewritten,
                    current_gap=current_gap,
                    rewritten_gap=rewritten_gap,
                    effective_targeted_flags=effective_targeted_flags,
                    rewritten_issues=rewritten_issues,
                    rewritten_gap_flags=rewritten_gap_flags,
                ):
                    aligned = rewritten
                    alignment_applied = True
                    natural_dialog_rewrite_applied = True
                    alignment_reasons.extend(natural_dialog_rewrite_notes)

    aligned = _sanitize_final_answer(
        aligned,
        user_text,
        current_event=current_event,
        behavior_action=behavior_action,
    )
    aligned = _ensure_response_structure(aligned, user_text)
    claims = [] if bool(ABLATE_CLAIM_ATTRIBUTION) else build_claim_attribution(aligned, evidence_pack)
    ext_tools = set(state.get("last_external_tools") or [])
    if ext_tools and not claims and not bool(ABLATE_CLAIM_ATTRIBUTION):
        aligned = aligned.strip() + "\n\n(外部信息未形成可追溯证据链，以上结论按暂定处理。)"
        aligned = _sanitize_final_answer(
            aligned,
            user_text,
            current_event=current_event,
            behavior_action=behavior_action,
        )
        aligned = _ensure_response_structure(aligned, user_text)
        claims = [] if bool(ABLATE_CLAIM_ATTRIBUTION) else build_claim_attribution(aligned, evidence_pack)

    risk, flags = _ooc_risk(aligned)
    gap, gap_flags = _persona_gap(aligned, state)
    dialogue_issues = _dialogue_issues_with_recent_repeat(
        user_text=user_text,
        answer=aligned,
        response_style_hint=response_style_hint,
        science_mode=science_mode,
        current_event=current_event,
        behavior_action=behavior_action,
        previous_assistant_text=previous_assistant_text,
    )
    canon = _canon_guard(aligned, store)
    canon_risk = min(1.0, risk + (0.3 if not bool(canon.get("ok")) else 0.0))
    final_msg = AIMessage(content=aligned)
    behavior_snapshot = {
        "interaction_mode": str(behavior_action.get("interaction_mode") or ""),
        "followup_intent": str(behavior_action.get("followup_intent") or ""),
        "action_target": str(behavior_action.get("action_target") or ""),
        "relationship_weather": str(behavior_action.get("relationship_weather") or ""),
    }
    return {
        "messages": [final_msg],
        "final_text": aligned,
        "ooc_detector": {
            "draft_risk": draft_risk,
            "draft_gap": draft_gap,
            "draft_flags": draft_flags,
            "draft_gap_flags": draft_gap_flags,
            "draft_generation_issues": draft_generation_issues,
            "draft_dialogue_issues": draft_dialogue_issues,
            "risk": risk,
            "flags": flags,
            "gap": gap,
            "gap_flags": gap_flags,
            "dialogue_issues": dialogue_issues,
            "threshold": float(OOC_RISK_THRESHOLD),
            "persona_gap_threshold": float(PERSONA_GAP_THRESHOLD),
            "alignment_applied": alignment_applied,
            "alignment_reasons": list(dict.fromkeys(alignment_reasons)),
            "response_strategy": "single_pass_final_diagnostics",
            "light_dialog_rewrite_applied": light_dialog_rewrite_applied,
            "light_dialog_rewrite_notes": light_dialog_rewrite_notes,
            "natural_dialog_rewrite_applied": natural_dialog_rewrite_applied,
            "natural_dialog_rewrite_notes": natural_dialog_rewrite_notes,
            "light_dialog_draft_penalty": light_dialog_draft_penalty,
            "light_dialog_final_penalty": light_dialog_final_penalty,
            "light_dialog_case_name": str(light_dialog_profile.get("case_name") or ""),
            "light_dialog_case_match_score": float(light_dialog_profile.get("score") or 0.0),
            "light_dialog_draft_pref_score": light_dialog_draft_pref_score,
            "light_dialog_final_pref_score": light_dialog_final_pref_score,
            "behavior_snapshot": behavior_snapshot,
            "ablation_persona_alignment": bool(ABLATE_PERSONA_ALIGNMENT),
            "ablation_worldline_memory": bool(ABLATE_WORLDLINE_MEMORY),
            "ablation_claim_attribution": bool(ABLATE_CLAIM_ATTRIBUTION),
            "ablation_light_dialog_shaping": bool(ABLATE_LIGHT_DIALOG_SHAPING),
            "generation_profile": {
                **chosen_generation_profile,
                "runtime_mode": generation_runtime_mode,
                "repetition_pressure": generation_repetition_pressure,
                "recent_reply_max_similarity": generation_recent_reply_max_similarity,
                "recent_reply_avg_similarity": generation_recent_reply_avg_similarity,
                "recent_reply_opener_repeat_ratio": generation_recent_reply_opener_repeat_ratio,
                "recent_reply_sample_size": generation_recent_reply_sample_size,
            },
        },
        "canon_guard": canon,
        "canon_risk_score": canon_risk,
        "claim_links": claims,
    }
