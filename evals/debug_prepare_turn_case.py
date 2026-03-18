from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from langchain_core.messages import HumanMessage

from amadeus_thread0.memory_store import MemoryStore
import amadeus_thread0.graph_parts.prepare_turn_context as ptc


def _append(log_path: Path, label: str, start_ts: float) -> None:
    elapsed = time.time() - start_ts
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{time.time():.3f}\t{elapsed:.3f}\t{label}\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True, help="User text to run through prepare_turn_context")
    parser.add_argument(
        "--log",
        default="",
        help="Optional log path; defaults to evals/reports/debug-prepare-turn-<timestamp>.log",
    )
    args = parser.parse_args()

    ts = time.strftime("%Y%m%d-%H%M%S")
    log_path = Path(args.log).expanduser() if str(args.log or "").strip() else (
        Path(__file__).resolve().parents[1] / "evals" / "reports" / f"debug-prepare-turn-{ts}.log"
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("", encoding="utf-8")

    start_ts = time.time()
    state = {
        "messages": [HumanMessage(content=str(args.text or "").strip())],
    }

    with tempfile.TemporaryDirectory() as td:
        store = MemoryStore(Path(td) / "memories.sqlite")
        _append(log_path, "store_ready", start_ts)

        profile, _ = ptc._active_counterpart_profile(state, store, with_trace=True)
        _append(log_path, "active_counterpart_profile", start_ts)
        persona_core, _ = ptc._active_persona_core(state, with_trace=True)
        _append(log_path, "active_persona_core", start_ts)

        msgs = ptc._messages(state)
        _append(log_path, "messages_loaded", start_ts)

        counterpart_name = str(
            profile.get("short_name") or profile.get("nickname") or profile.get("name") or ptc.CANON_COUNTERPART_NAME
        )
        event_override = ptc._normalize_event_override(
            ptc._sanitize_obj(state.get("event_override")),
            counterpart_name=counterpart_name,
        )
        _append(log_path, "event_override_normalized", start_ts)

        prior_current_event = ptc._sanitize_obj(state.get("current_event")) if isinstance(state.get("current_event"), dict) else {}
        prior_behavior_action = ptc._sanitize_obj(state.get("behavior_action")) if isinstance(state.get("behavior_action"), dict) else {}
        prior_behavior_plan = ptc._sanitize_obj(state.get("behavior_plan")) if isinstance(state.get("behavior_plan"), dict) else {}
        prior_behavior_agenda = ptc._sanitize_obj(state.get("behavior_agenda")) if isinstance(state.get("behavior_agenda"), list) else []
        agenda_lifecycle_residue: dict[str, object] = {}
        if not prior_behavior_agenda and isinstance(state.get("behavior_queue"), list):
            prior_behavior_agenda = ptc._sanitize_obj(state.get("behavior_queue"))
        _append(log_path, "prior_runtime_loaded", start_ts)

        user_text = ptc._last_user_text(msgs)
        previous_user_text = ptc._previous_user_text(msgs)
        prev_assistant = ptc._last_ai_text(msgs)
        _append(log_path, "message_views_ready", start_ts)

        pending = ptc.derive_pending_fragment(
            user_text=user_text,
            previous_excerpt=prev_assistant[:180],
            pending_fragment=ptc._clean_utf8_text(str(state.get("pending_utterance_fragment") or "")),
        )
        _append(log_path, "pending_ready", start_ts)
        pending_user_goal = ptc.derive_pending_user_goal(
            user_text=user_text,
            previous_user_text=previous_user_text,
            pending_user_goal=ptc._clean_utf8_text(str(state.get("pending_user_goal") or "")),
            pending_fragment=pending,
        )
        _append(log_path, "pending_user_goal_ready", start_ts)

        continuation_mode = ptc.has_active_continuation(user_text=user_text, pending_fragment=pending)
        continuation_seed = ptc.continuation_seed_text(
            pending_user_goal=pending_user_goal,
            pending_fragment=pending,
        )
        effective_user_text = continuation_seed if continuation_mode and continuation_seed else user_text
        _append(log_path, "continuation_ready", start_ts)

        ptc._compact_thread_if_needed(msgs, store)
        _append(log_path, "compact_thread_done", start_ts)

        science_mode = (
            ptc._science_mode_from_context(
                effective_user_text or user_text,
                previous_user_text=previous_user_text,
                pending_user_goal=pending_user_goal,
                previous_assistant_text=prev_assistant,
            )
            if (effective_user_text or user_text)
            else bool(state.get("science_mode", False))
        )
        _append(log_path, "science_mode_ready", start_ts)

        response_style_hint = ptc._response_style_hint(
            effective_user_text or user_text,
            science_mode=science_mode,
            continuation_mode=continuation_mode,
            previous_hint=str(state.get("response_style_hint") or ""),
            current_event=event_override if isinstance(event_override, dict) and event_override else None,
        )
        _append(log_path, "response_style_hint_ready", start_ts)

        external_probe_mode = ptc._is_external_probe_context(
            persona_core=persona_core,
            counterpart_profile=profile,
        )
        _append(log_path, "external_probe_mode_ready", start_ts)

        retrieved = ptc._empty_retrieved_context(store) if external_probe_mode else ptc._retrieve_context(
            effective_user_text or user_text,
            store,
        )
        _append(log_path, "retrieved_ready", start_ts)

        retrieved_relationship = (
            retrieved.get("relationship") if isinstance(retrieved.get("relationship"), dict) else store.get_relationship()
        )
        relationship = ptc._relationship_runtime_snapshot(
            relationship=ptc._prefer_relationship_state(
                state.get("relationship") if isinstance(state.get("relationship"), dict) else None,
                retrieved_relationship,
            ),
            bond_state=state.get("bond_state") if isinstance(state.get("bond_state"), dict) else None,
            world_model_state=state.get("world_model_state") if isinstance(state.get("world_model_state"), dict) else None,
            counterpart_assessment=state.get("counterpart_assessment")
            if isinstance(state.get("counterpart_assessment"), dict)
            else None,
            semantic_narrative_profile=state.get("semantic_narrative_profile")
            if isinstance(state.get("semantic_narrative_profile"), dict)
            else None,
        )
        _append(log_path, "relationship_ready", start_ts)

        canon_recontact_baseline = ptc._canon_okabe_recontact_baseline(
            state=state,
            persona_core=persona_core,
            counterpart_profile=profile,
            relationship=relationship,
            retrieved=retrieved if isinstance(retrieved, dict) else {},
            external_probe_mode=external_probe_mode,
            now_ts=int(time.time()),
        )
        _append(log_path, "canon_baseline_ready", start_ts)

        worldline_focus = [] if external_probe_mode else ptc._worldline_focus(store)
        _append(log_path, "worldline_focus_ready", start_ts)

        seed_emotion_state = ptc._prefer_explicit_state_dict(
            state,
            "emotion_state",
            canon_recontact_baseline.get("emotion_state") if isinstance(canon_recontact_baseline, dict) else None,
        )
        seed_bond_state = ptc._prefer_explicit_state_dict(
            state,
            "bond_state",
            canon_recontact_baseline.get("bond_state") if isinstance(canon_recontact_baseline, dict) else None,
        )
        seed_allostasis_state = ptc._prefer_explicit_state_dict(
            state,
            "allostasis_state",
            canon_recontact_baseline.get("allostasis_state") if isinstance(canon_recontact_baseline, dict) else None,
        )
        seed_counterpart_assessment = ptc._prefer_explicit_state_dict(
            state,
            "counterpart_assessment",
            canon_recontact_baseline.get("counterpart_assessment")
            if isinstance(canon_recontact_baseline, dict)
            else None,
        )
        seed_world_model_state = ptc._prefer_explicit_state_dict(
            state,
            "world_model_state",
            canon_recontact_baseline.get("world_model_state") if isinstance(canon_recontact_baseline, dict) else None,
        )
        seed_world_model_state, seed_counterpart_assessment = ptc._apply_agenda_lifecycle_residue_to_runtime_state(
            agenda_lifecycle_residue=agenda_lifecycle_residue,
            world_model_state=seed_world_model_state,
            counterpart_assessment=seed_counterpart_assessment,
        )
        _append(log_path, "seed_states_ready", start_ts)

        appraisal_event_context = ptc._appraisal_event_context(
            user_text=user_text,
            effective_text=effective_user_text or user_text,
            response_style_hint=response_style_hint,
            science_mode=science_mode,
            continuation_mode=continuation_mode,
            counterpart_name=counterpart_name,
            pending_user_goal=pending_user_goal,
            event_override=event_override,
        )
        _append(log_path, "appraisal_event_context_ready", start_ts)

        semantic_narrative_profile_for_appraisal = ptc._semantic_narrative_profile(
            retrieved.get("semantic_self_narratives")
            if isinstance(retrieved.get("semantic_self_narratives"), list)
            else [],
            user_text=effective_user_text or user_text,
            current_event=appraisal_event_context,
        )
        _append(log_path, "semantic_profile_ready", start_ts)

        prior_semantic_narrative_profile = (
            state.get("semantic_narrative_profile")
            if isinstance(state.get("semantic_narrative_profile"), dict)
            else semantic_narrative_profile_for_appraisal
        )
        appraisal_interaction_carryover = ptc._recent_interaction_carryover(
            prior_current_event=prior_current_event if isinstance(prior_current_event, dict) else {},
            prior_behavior_action=prior_behavior_action if isinstance(prior_behavior_action, dict) else {},
            prior_agenda_lifecycle_residue=state.get("agenda_lifecycle_residue")
            if isinstance(state.get("agenda_lifecycle_residue"), dict)
            else {},
            prior_counterpart_assessment=state.get("counterpart_assessment")
            if isinstance(state.get("counterpart_assessment"), dict)
            else {},
            recent_events=state.get("recent_events"),
            current_event=appraisal_event_context,
            response_style_hint=response_style_hint,
            world_model_state=seed_world_model_state,
            semantic_narrative_profile=prior_semantic_narrative_profile
            if isinstance(prior_semantic_narrative_profile, dict)
            else {},
        )
        _append(log_path, "recent_interaction_carryover_ready", start_ts)

        if not appraisal_interaction_carryover:
            appraisal_interaction_carryover = ptc._seeded_interaction_carryover_from_state(
                state=state,
                prior_current_event=prior_current_event if isinstance(prior_current_event, dict) else {},
                prior_behavior_action=prior_behavior_action if isinstance(prior_behavior_action, dict) else {},
                seed_world_model_state=seed_world_model_state,
                semantic_narrative_profile=prior_semantic_narrative_profile
                if isinstance(prior_semantic_narrative_profile, dict)
                else {},
                counterpart_assessment=seed_counterpart_assessment,
                current_event=appraisal_event_context,
                response_style_hint=response_style_hint,
            )
        _append(log_path, "seeded_interaction_carryover_ready", start_ts)

        _ = ptc._invoke_turn_appraisal(
            msgs=msgs,
            user_text=effective_user_text or user_text,
            response_style_hint=response_style_hint,
            science_mode=science_mode,
            prev_emotion_state=seed_emotion_state,
            prev_bond_state=seed_bond_state,
            prev_allostasis_state=seed_allostasis_state,
            relationship=relationship,
            worldline_focus=worldline_focus,
            retrieved=retrieved,
            persona_core=persona_core,
            counterpart_profile=profile,
            current_event=appraisal_event_context,
            semantic_narrative_profile=semantic_narrative_profile_for_appraisal,
            interaction_carryover=appraisal_interaction_carryover,
        )
        _append(log_path, "appraisal_ready", start_ts)

        store.close()
        _append(log_path, "done", start_ts)

    print(log_path)


if __name__ == "__main__":
    main()
