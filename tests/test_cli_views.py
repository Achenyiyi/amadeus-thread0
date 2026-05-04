import unittest

from amadeus_thread0.cli_views import (
    build_behavior_queue_cli_summary,
    build_counterpart_assessment_cli_summary,
    build_evolution_cli_summary,
    build_proactive_continuity_cli_summary,
    build_evolution_summary_line,
    render_action_packet_cli_text,
    render_counterpart_assessment_cli_text,
    render_behavior_queue_cli_text,
    render_proactive_continuity_cli_text,
)
from amadeus_thread0.evolution_engine.reconsolidation import build_reconsolidation_snapshot


class CliViewsTests(unittest.TestCase):
    def test_render_action_packet_cli_text_surfaces_sandbox_run_trace(self):
        rendered = render_action_packet_cli_text(
            [
                {
                    "proposal_id": "ap-sandbox-1",
                    "origin": "motive_goal",
                    "intent": "sandbox:execute_workspace_command",
                    "status": "completed",
                    "risk": "external_mutation",
                    "result_summary": "已跑完本次受限执行。",
                    "execution_result": {
                        "run_id": "ap-sandbox-1",
                        "exit_code": 0,
                    },
                }
            ]
        )
        self.assertIn("sandbox:execute_workspace_command", rendered)
        self.assertIn("run=ap-sandbox-1", rendered)
        self.assertIn("exit=0", rendered)

    def test_render_action_packet_cli_text_surfaces_sandbox_phase2_runner_identity(self):
        rendered = render_action_packet_cli_text(
            [
                {
                    "proposal_id": "ap-sandbox-phase2-1",
                    "origin": "motive_goal",
                    "intent": "sandbox:execute_workspace_command",
                    "status": "completed",
                    "risk": "external_mutation",
                    "execution_spec": {
                        "runner_kind": "docker_isolated_runner",
                        "workspace_root_kind": "attached_repo_root",
                    },
                    "execution_result": {
                        "run_id": "ap-sandbox-phase2-1",
                        "exit_code": 0,
                    },
                }
            ]
        )
        self.assertIn("runner=docker_isolated_runner", rendered)
        self.assertIn("root=attached_repo_root", rendered)

    def test_build_evolution_cli_summary_surfaces_continuity_vector(self):
        summary = build_evolution_cli_summary(
            relationship={
                "stage": "warming",
                "affinity_score": 0.72,
                "trust_score": 0.74,
                "notes": "逐渐熟悉起来。",
            },
            semantic_narrative_profile={
                "presence_carry": 0.58,
                "ambient_attunement": 0.46,
                "rhythm_continuity": 0.63,
                "history_weight": 0.67,
                "dominant_category": "rhythm_style",
                "active_categories": ["presence_style", "rhythm_style"],
                "reactivated_categories": ["ambient_style"],
                "summary_lines": ["上一轮留下的在场感会继续影响下一轮。"],
                "anchor_lines": ["红莉栖不会在每次回应前都把自己的内部节奏清零。"],
                "top_narratives": [
                    {
                        "category": "rhythm_style",
                        "score": 0.72,
                        "reactivated": True,
                        "text": "她会把自己的内部节奏延续到下一轮。",
                        "primary_motive": "preserve_self_rhythm",
                        "motive_tension": "self_rhythm_vs_contact",
                        "counterpart_snapshot": {
                            "counterpart_stance": "watchful",
                            "counterpart_scene": "busy_not_disrespectful",
                            "counterpart_respect_level": 0.62,
                            "counterpart_reciprocity": 0.58,
                            "counterpart_boundary_pressure": 0.16,
                            "counterpart_reliability_read": 0.71,
                            "counterpart_profile": {
                                "dominant_scene_signal": "busy",
                                "scene_strengths": {"busy": 0.77},
                                "openness_drive": 0.54,
                            },
                            "counterpart_support_count": 3,
                            "counterpart_support_mass": 0.66,
                            "counterpart_confidence_avg": 0.74,
                            "counterpart_fresh_ratio": 0.58,
                        },
                        "proactive_continuity": {
                            "_score": 0.68,
                            "continuity_anchor": 0.64,
                            "own_rhythm_anchor": 0.73,
                            "recontact_anchor": 0.41,
                            "boundary_anchor": 0.22,
                            "memory_anchor": 0.37,
                            "lineage_gravity": 0.69,
                            "agency_lineage": 0.78,
                            "long_term_axis_count": 3,
                        },
                    }
                ],
                "identity_lines": ["红莉栖会把自己放在和冈部伦太郎平等互动的位置上。"],
                "identity_prompt_lines": ["你会把自己放在和冈部伦太郎平等互动的位置上。"],
                "long_term_self_narratives": [
                    {
                        "category": "selfhood_style",
                        "score": 0.77,
                        "horizon_tag": "long_term",
                        "text": "红莉栖会把自己放在和冈部伦太郎平等互动的位置上。",
                        "prompt_text": "你会把自己放在和冈部伦太郎平等互动的位置上。",
                        "primary_motive": "preserve_selfhood",
                        "motive_tension": "selfhood_vs_appeasement",
                        "sedimentation_score": 0.74,
                        "persistence_score": 0.79,
                        "integration_score": 0.71,
                        "support_span_s": 604800,
                        "reactivation_hits": 3,
                        "identity_strength": 0.83,
                        "lineage_depth": 0.68,
                        "counterpart_snapshot": {
                            "counterpart_stance": "open",
                            "counterpart_scene": "care_bid",
                            "counterpart_respect_level": 0.76,
                            "counterpart_reciprocity": 0.72,
                            "counterpart_profile": {
                                "dominant_scene_signal": "care",
                                "scene_strengths": {"care": 0.82},
                            },
                        },
                        "proactive_continuity": {
                            "_score": 0.61,
                            "continuity_anchor": 0.58,
                            "memory_anchor": 0.55,
                            "selfhood_lineage": 0.72,
                            "long_term_axis_count": 2,
                        },
                    }
                ],
            },
            world_model_state={
                "presence_residue": 0.41,
                "ambient_resonance": 0.32,
                "self_activity_momentum": 0.57,
                "bond_depth": 0.64,
                "tension_load": 0.08,
                "selfhood_load": 0.42,
                "agency_load": 0.51,
                "memory_gravity": 0.48,
                "companionship_pull": 0.54,
                "task_pull": 0.20,
            },
            emotion_state={"label": "neutral"},
            bond_state={"trust": 0.68, "closeness": 0.66, "hurt": 0.04},
            counterpart_assessment={"stance": "open", "scene": "care_bid"},
            behavior_action={
                "interaction_mode": "self_activity_reopen",
                "action_target": "respond_now",
                "primary_motive": "gentle_recontact",
                "motive_tension": "self_rhythm_vs_contact",
                "goal_frame": "先从自己的节奏里回头，留一个不压迫对方的小开口。",
                "relationship_weather": "warm_residue",
            },
            interaction_carryover={"carryover_mode": "own_rhythm", "strength": 0.57, "relationship_weather": "warm_residue"},
            worldline_focus=[
                {"summary": "刚才那阵风过去之后，她还是保留了在场感。"},
                {"summary": "她从自己的节奏里抬头回应。"},
            ],
            reconsolidation_snapshot={"event_kind": "user_utterance", "interaction_frame": "relationship"},
        )
        continuity = summary.get("continuity_vector") if isinstance(summary.get("continuity_vector"), dict) else {}
        self.assertEqual(continuity.get("presence"), {"semantic": 0.58, "world": 0.41})
        self.assertEqual(continuity.get("ambient"), {"semantic": 0.46, "world": 0.32})
        self.assertEqual(continuity.get("rhythm"), {"semantic": 0.63, "world": 0.57})
        semantic = summary.get("semantic_continuity") if isinstance(summary.get("semantic_continuity"), dict) else {}
        self.assertEqual(semantic.get("dominant_category"), "rhythm_style")
        self.assertIn("presence_style", semantic.get("active_categories") or [])
        self.assertIn("红莉栖不会在每次回应前都把自己的内部节奏清零。", semantic.get("anchor_lines") or [])
        self.assertEqual(semantic.get("frozen_anchor_bundle"), {})
        top_narratives = semantic.get("top_narratives") if isinstance(semantic.get("top_narratives"), list) else []
        self.assertEqual(top_narratives[0].get("primary_motive"), "preserve_self_rhythm")
        self.assertEqual(top_narratives[0].get("motive_tension"), "self_rhythm_vs_contact")
        counterpart_snapshot = top_narratives[0].get("counterpart_snapshot") if isinstance(top_narratives[0].get("counterpart_snapshot"), dict) else {}
        self.assertEqual(counterpart_snapshot.get("scene"), "busy_not_disrespectful")
        self.assertEqual(counterpart_snapshot.get("support_count"), 3)
        self.assertEqual(counterpart_snapshot.get("profile", {}).get("dominant_scene_signal"), "busy")
        proactive_continuity = top_narratives[0].get("proactive_continuity") if isinstance(top_narratives[0].get("proactive_continuity"), dict) else {}
        self.assertEqual(proactive_continuity.get("own_rhythm_anchor"), 0.73)
        self.assertEqual(proactive_continuity.get("agency_lineage"), 0.78)
        self.assertEqual(proactive_continuity.get("long_term_axis_count"), 3)
        identity = summary.get("identity_continuity") if isinstance(summary.get("identity_continuity"), dict) else {}
        self.assertEqual(identity.get("dominant_identity_category"), "selfhood_style")
        self.assertIn("你会把自己放在和冈部伦太郎平等互动的位置上。", identity.get("identity_prompt_lines") or [])
        long_term = identity.get("long_term_self_narratives") if isinstance(identity.get("long_term_self_narratives"), list) else []
        self.assertEqual(long_term[0].get("primary_motive"), "preserve_selfhood")
        self.assertEqual(long_term[0].get("motive_tension"), "selfhood_vs_appeasement")
        self.assertEqual(long_term[0].get("sedimentation_score"), 0.74)
        self.assertEqual(long_term[0].get("support_span_s"), 604800)
        self.assertEqual(long_term[0].get("identity_strength"), 0.83)
        self.assertEqual(long_term[0].get("counterpart_snapshot", {}).get("scene"), "care_bid")
        self.assertEqual(long_term[0].get("proactive_continuity", {}).get("selfhood_lineage"), 0.72)
        self.assertEqual(long_term[0].get("proactive_continuity", {}).get("long_term_axis_count"), 2)
        self.assertEqual(len(summary.get("worldline_focus_preview") or []), 2)
        current_turn = summary.get("current_turn") if isinstance(summary.get("current_turn"), dict) else {}
        self.assertEqual(current_turn.get("carryover_weather"), "warm_residue")
        self.assertEqual(current_turn.get("behavior_weather"), "warm_residue")
        self.assertEqual(current_turn.get("primary_motive"), "gentle_recontact")
        self.assertEqual(current_turn.get("motive_tension"), "self_rhythm_vs_contact")

    def test_build_evolution_cli_summary_preserves_worldline_focus_item_context(self):
        summary = build_evolution_cli_summary(
            worldline_focus=[
                {
                    "id": 12,
                    "focus_kind": "commitment",
                    "text": "记得提醒冈部吃饭。",
                    "status": "open",
                    "due_at": "今晚",
                    "created_at": 1700000100,
                },
                {
                    "id": 13,
                    "focus_kind": "unresolved_tension",
                    "summary": "前面那点别扭还没完全过去。",
                    "severity": 0.66,
                    "updated_at": 1700000200,
                },
                {
                    "id": 14,
                    "focus_kind": "relationship_timeline",
                    "summary": "这轮之后关系比之前稳了一点。",
                    "affinity_delta": 0.12,
                    "trust_delta": 0.18,
                    "created_at": 1700000300,
                },
            ]
        )
        self.assertEqual(
            summary.get("worldline_focus_preview"),
            [
                "记得提醒冈部吃饭。",
                "前面那点别扭还没完全过去。",
                "这轮之后关系比之前稳了一点。",
            ],
        )
        items = summary.get("worldline_focus_items") if isinstance(summary.get("worldline_focus_items"), list) else []
        self.assertEqual(len(items), 3)
        self.assertEqual(
            items[0],
            {
                "id": 12,
                "kind": "commitment",
                "text": "记得提醒冈部吃饭。",
                "status": "open",
                "due_at": "今晚",
                "severity": 0.0,
                "affinity_delta": 0.0,
                "trust_delta": 0.0,
                "created_at": 1700000100,
                "updated_at": 0,
            },
        )
        self.assertEqual(items[1].get("kind"), "unresolved_tension")
        self.assertEqual(items[1].get("severity"), 0.66)
        self.assertEqual(items[1].get("updated_at"), 1700000200)
        self.assertEqual(items[2].get("kind"), "relationship_timeline")
        self.assertEqual(items[2].get("affinity_delta"), 0.12)
        self.assertEqual(items[2].get("trust_delta"), 0.18)

    def test_reconsolidation_snapshot_includes_residue_axes(self):
        snapshot = build_reconsolidation_snapshot(
            current_event={"kind": "user_utterance"},
            appraisal={
                "used": True,
                "interaction_frame": "relationship",
                "salience": {"relationship": 0.44},
            },
            world_model_state={
                "relationship_maturity": 0.58,
                "bond_depth": 0.61,
                "tension_load": 0.12,
                "repair_load": 0.14,
                "boundary_load": 0.18,
                "selfhood_load": 0.40,
                "agency_load": 0.48,
                "memory_gravity": 0.46,
                "lineage_gravity": 0.64,
                "contact_lineage": 0.58,
                "repair_lineage": 0.42,
                "boundary_lineage": 0.62,
                "selfhood_lineage": 0.66,
                "agency_lineage": 0.72,
                "presence_residue": 0.39,
                "ambient_resonance": 0.31,
                "self_activity_momentum": 0.55,
            },
            semantic_narrative_profile={
                "dominant_category": "rhythm_style",
                "continuity_depth": 0.74,
                "identity_gravity": 0.68,
                "lineage_gravity": 0.70,
                "active_categories": ["presence_style", "rhythm_style", "agency_style"],
                "lineage_snapshot": {
                    "presence_style": 0.60,
                    "boundary_style": 0.62,
                    "selfhood_style": 0.66,
                    "agency_style": 0.72,
                    "rhythm_style": 0.76,
                },
                "continuity_anchor": 0.67,
                "own_rhythm_anchor": 0.73,
                "recontact_anchor": 0.49,
                "boundary_anchor": 0.58,
                "memory_anchor": 0.54,
                "semantic_continuity_depth": 0.74,
                "semantic_identity_gravity": 0.68,
                "contact_lineage": 0.64,
                "repair_lineage": 0.42,
                "boundary_lineage": 0.62,
                "selfhood_lineage": 0.66,
                "agency_lineage": 0.72,
                "long_term_axis_count": 3,
            },
            latent_state={"self_coherence": 0.74, "agency_pressure": 0.42, "reflection_drive": 0.46, "expression_freedom": 0.68},
            emotion_state={"label": "neutral"},
            bond_state={"trust": 0.66, "closeness": 0.64, "hurt": 0.02},
            counterpart_assessment={
                "stance": "watchful",
                "scene": "repair_attempt",
                "respect_level": 0.62,
                "reciprocity": 0.58,
                "boundary_pressure": 0.28,
                "reliability_read": 0.6,
            },
            behavior_action={
                "interaction_mode": "self_activity_reopen",
                "primary_motive": "gentle_recontact",
                "motive_tension": "self_rhythm_vs_contact",
                "goal_frame": "先从自己的节奏里回头，留一个不压迫对方的小开口。",
            },
            agenda_lifecycle_residue={
                "kind": "released_to_self_activity",
                "source_event_kind": "scheduled_life_due",
                "trigger_family": "life_window",
                "carryover_mode": "own_rhythm",
                "carryover_strength": 0.53,
                "relationship_weather": "warm_residue",
                "hold_count": 2,
                "presence_residue": 0.33,
                "ambient_resonance": 0.24,
                "self_activity_momentum": 0.58,
                "own_rhythm_bias": 0.61,
                "recontact_cooldown": 0.47,
                "counterpart_scene_bias": "busy_not_disrespectful",
                "note": "前面挂着的窗口没有继续往前推，注意力被自然收回到了自己的节奏里。",
            },
        )
        world_model = snapshot.get("world_model") if isinstance(snapshot.get("world_model"), dict) else {}
        semantic = snapshot.get("semantic_continuity") if isinstance(snapshot.get("semantic_continuity"), dict) else {}
        self.assertEqual(world_model.get("relationship_maturity"), 0.58)
        self.assertEqual(world_model.get("presence_residue"), 0.39)
        self.assertEqual(world_model.get("ambient_resonance"), 0.31)
        self.assertEqual(world_model.get("self_activity_momentum"), 0.55)
        self.assertEqual(world_model.get("lineage_gravity"), 0.64)
        self.assertEqual(world_model.get("agency_lineage"), 0.72)
        self.assertEqual(world_model.get("boundary_lineage"), 0.62)
        self.assertEqual(semantic.get("dominant_category"), "rhythm_style")
        self.assertEqual(semantic.get("lineage_gravity"), 0.7)
        self.assertIn("agency_style", semantic.get("active_categories") or [])
        self.assertEqual((semantic.get("lineage_snapshot") or {}).get("rhythm_style"), 0.76)
        semantic_anchor_bundle = snapshot.get("semantic_anchor_bundle") if isinstance(snapshot.get("semantic_anchor_bundle"), dict) else {}
        self.assertEqual(semantic_anchor_bundle.get("continuity_anchor"), 0.67)
        self.assertEqual(semantic_anchor_bundle.get("own_rhythm_anchor"), 0.73)
        self.assertEqual(semantic_anchor_bundle.get("memory_anchor"), 0.54)
        self.assertEqual(semantic_anchor_bundle.get("semantic_continuity_depth"), 0.74)
        self.assertEqual(semantic_anchor_bundle.get("semantic_identity_gravity"), 0.68)
        self.assertEqual(semantic_anchor_bundle.get("agency_lineage"), 0.72)
        self.assertEqual(semantic_anchor_bundle.get("long_term_axis_count"), 3)
        self.assertEqual(snapshot.get("behavior_mode"), "self_activity_reopen")
        self.assertEqual(snapshot.get("primary_motive"), "gentle_recontact")
        counterpart = snapshot.get("counterpart") if isinstance(snapshot.get("counterpart"), dict) else {}
        self.assertEqual(counterpart.get("stance"), "watchful")
        self.assertEqual(counterpart.get("scene"), "repair_attempt")
        self.assertEqual(counterpart.get("boundary_pressure"), 0.28)

    def test_build_evolution_cli_summary_surfaces_frozen_semantic_anchor_bundle(self):
        summary = build_evolution_cli_summary(
            semantic_narrative_profile={"dominant_category": "presence_style"},
            reconsolidation_snapshot={
                "event_kind": "user_utterance",
                "interaction_frame": "relationship",
                "semantic_anchor_bundle": {
                    "continuity_anchor": 0.68,
                    "own_rhythm_anchor": 0.74,
                    "recontact_anchor": 0.52,
                    "boundary_anchor": 0.41,
                    "memory_anchor": 0.57,
                    "semantic_continuity_depth": 0.71,
                    "semantic_identity_gravity": 0.69,
                    "lineage_gravity": 0.66,
                    "contact_lineage": 0.63,
                    "repair_lineage": 0.44,
                    "boundary_lineage": 0.39,
                    "selfhood_lineage": 0.61,
                    "agency_lineage": 0.73,
                    "long_term_axis_count": 4,
                },
            },
        )
        semantic = summary.get("semantic_continuity") if isinstance(summary.get("semantic_continuity"), dict) else {}
        current_turn = summary.get("current_turn") if isinstance(summary.get("current_turn"), dict) else {}
        expected_bundle = {
            "continuity_anchor": 0.68,
            "own_rhythm_anchor": 0.74,
            "recontact_anchor": 0.52,
            "boundary_anchor": 0.41,
            "memory_anchor": 0.57,
            "semantic_continuity_depth": 0.71,
            "semantic_identity_gravity": 0.69,
            "lineage_gravity": 0.66,
            "contact_lineage": 0.63,
            "repair_lineage": 0.44,
            "boundary_lineage": 0.39,
            "selfhood_lineage": 0.61,
            "agency_lineage": 0.73,
            "long_term_axis_count": 4,
        }
        self.assertEqual(semantic.get("frozen_anchor_bundle"), expected_bundle)
        self.assertEqual(current_turn.get("semantic_anchor_bundle"), expected_bundle)

    def test_reconsolidation_snapshot_does_not_fall_back_to_stale_event_behavior_fields(self):
        snapshot = build_reconsolidation_snapshot(
            current_event={
                "kind": "user_utterance",
                "interaction_mode": "stale_event_mode",
                "primary_motive": "stale_event_motive",
                "motive_tension": "stale_event_tension",
                "goal_frame": "stale event frame",
                "trigger_family": "self_activity",
            },
            appraisal={"used": True, "interaction_frame": "relationship"},
            world_model_state={},
            semantic_narrative_profile={},
            latent_state={},
            emotion_state={"label": "neutral"},
            bond_state={"trust": 0.6, "closeness": 0.6, "hurt": 0.0},
            behavior_action={},
            agenda_lifecycle_residue={},
        )
        self.assertEqual(snapshot.get("behavior_mode"), "")
        self.assertEqual(snapshot.get("primary_motive"), "")
        self.assertEqual(snapshot.get("motive_tension"), "")
        self.assertEqual(snapshot.get("goal_frame"), "")
        self.assertEqual(snapshot.get("behavior_consequence"), {})

    def test_reconsolidation_snapshot_compacts_behavior_plan_and_interaction_carryover(self):
        snapshot = build_reconsolidation_snapshot(
            current_event={"kind": "user_utterance"},
            appraisal={"used": True, "interaction_frame": "relationship"},
            world_model_state={},
            semantic_narrative_profile={},
            latent_state={},
            emotion_state={"label": "neutral"},
            bond_state={"trust": 0.6, "closeness": 0.6, "hurt": 0.0},
            behavior_action={
                "interaction_mode": "steady_reply",
                "primary_motive": "honor_continuity",
                "motive_tension": "contact_without_pressure",
                "goal_frame": "顺着之前留下的惦记自然接回来。",
            },
            behavior_plan={
                "kind": "deferred_checkin",
                "target": "counterpart",
                "trigger_family": "observe",
                "carryover_mode": "life_window",
                "note": "final frozen carryover path",
                "primary_motive": "honor_continuity",
                "motive_tension": "contact_without_pressure",
                "goal_frame": "顺着之前留下的惦记自然接回来。",
            },
            interaction_carryover={
                "source": "retrieved_behavior_plan",
                "strength": 0.44,
                "carryover_mode": "life_window",
                "relationship_weather": "warm_residue",
                "note": "final frozen carryover path",
                "source_tags": ["plan_kind:deferred_checkin", "trigger_family:observe"],
            },
            agenda_lifecycle_residue={},
        )
        behavior_plan = snapshot.get("behavior_plan") if isinstance(snapshot.get("behavior_plan"), dict) else {}
        interaction_carryover = snapshot.get("interaction_carryover") if isinstance(snapshot.get("interaction_carryover"), dict) else {}
        self.assertEqual(behavior_plan.get("kind"), "deferred_checkin")
        self.assertEqual(behavior_plan.get("trigger_family"), "observe")
        self.assertEqual(behavior_plan.get("carryover_mode"), "life_window")
        self.assertEqual(behavior_plan.get("primary_motive"), "honor_continuity")
        self.assertEqual(interaction_carryover.get("source"), "retrieved_behavior_plan")
        self.assertEqual(interaction_carryover.get("carryover_mode"), "life_window")
        self.assertEqual(interaction_carryover.get("relationship_weather"), "warm_residue")
        self.assertEqual(
            interaction_carryover.get("source_tags"),
            ["plan_kind:deferred_checkin", "trigger_family:observe"],
        )

    def test_reconsolidation_snapshot_compacts_behavior_action_window_profile(self):
        snapshot = build_reconsolidation_snapshot(
            current_event={"kind": "self_activity_state"},
            appraisal={"used": True, "interaction_frame": "relationship"},
            world_model_state={},
            semantic_narrative_profile={},
            latent_state={},
            emotion_state={"label": "neutral"},
            bond_state={"trust": 0.6, "closeness": 0.6, "hurt": 0.0},
            behavior_action={
                "interaction_mode": "deferred_watch",
                "action_target": "wait_and_recheck",
                "primary_motive": "honor_continuity",
                "engagement_level": 0.61,
                "initiative_level": 0.47,
                "task_focus": "relationship",
                "affect_surface": "gentle",
                "silence_ok": True,
                "proactive_checkin_readiness": 0.39,
                "window_profile": {
                    "profile_type": "self_opening",
                    "event_kind": "self_activity_state",
                    "family": "self_activity",
                    "trigger_family": "life_window",
                    "stance": "watchful",
                    "scene": "repair_attempt",
                    "decision": "wait_and_recheck",
                    "readiness": 0.41,
                    "required_readiness": 0.57,
                    "reopen_ready": False,
                    "recheck_min": 18,
                    "continuity_bonus": 0.14,
                    "carryover_mode": "own_rhythm",
                    "carryover_strength": 0.46,
                    "presence_residue": 0.33,
                    "ambient_resonance": 0.22,
                    "self_activity_momentum": 0.58,
                    "recontact_echo": 0.29,
                    "own_rhythm_load": 0.63,
                },
                "initiative_shape": "micro_opening",
                "disclosure_posture": "measured",
                "note": "顺着余温看一眼，但不立刻把距离拉近。",
            },
            agenda_lifecycle_residue={},
        )
        behavior_action = snapshot.get("behavior_action") if isinstance(snapshot.get("behavior_action"), dict) else {}
        window_profile = behavior_action.get("window_profile") if isinstance(behavior_action.get("window_profile"), dict) else {}
        self.assertEqual(behavior_action.get("interaction_mode"), "deferred_watch")
        self.assertEqual(behavior_action.get("engagement_level"), 0.61)
        self.assertEqual(behavior_action.get("initiative_level"), 0.47)
        self.assertEqual(behavior_action.get("initiative_shape"), "micro_opening")
        self.assertEqual(behavior_action.get("disclosure_posture"), "measured")
        self.assertEqual(behavior_action.get("note"), "顺着余温看一眼，但不立刻把距离拉近。")
        self.assertEqual(window_profile.get("profile_type"), "self_opening")
        self.assertEqual(window_profile.get("decision"), "wait_and_recheck")
        self.assertEqual(window_profile.get("readiness"), 0.41)
        self.assertEqual(window_profile.get("required_readiness"), 0.57)
        self.assertEqual(window_profile.get("recheck_min"), 18)
        self.assertEqual(window_profile.get("carryover_mode"), "own_rhythm")
        self.assertEqual(window_profile.get("own_rhythm_load"), 0.63)

    def test_build_evolution_summary_line_is_compact_and_informative(self):
        summary = build_evolution_cli_summary(
            relationship={"stage": "warming", "affinity_score": 0.72, "trust_score": 0.74},
            semantic_narrative_profile={
                "presence_carry": 0.58,
                "ambient_attunement": 0.46,
                "rhythm_continuity": 0.63,
                "long_term_self_narratives": [
                    {
                        "category": "selfhood_style",
                        "score": 0.77,
                        "text": "红莉栖会把自己放在和冈部伦太郎平等互动的位置上。",
                    }
                ],
            },
            world_model_state={
                "presence_residue": 0.41,
                "ambient_resonance": 0.32,
                "self_activity_momentum": 0.57,
                "bond_depth": 0.64,
                "tension_load": 0.08,
            },
            counterpart_assessment={"stance": "open"},
            behavior_action={"interaction_mode": "self_activity_reopen", "primary_motive": "gentle_recontact"},
            interaction_carryover={"carryover_mode": "own_rhythm", "strength": 0.57, "relationship_weather": "guarded_residue"},
            reconsolidation_snapshot={
                "behavior_consequence": {
                    "kind": "leave_small_opening",
                    "summary": "她从自己的节奏里回头了，但只留了一个很轻的小开口。",
                }
            },
            agenda_lifecycle_residue={
                "kind": "held",
                "carryover_mode": "own_rhythm",
                "carryover_strength": 0.41,
                "hold_count": 2,
                "recontact_cooldown": 0.52,
            },
            digital_body_state={
                "active_surface": "approval_gate",
                "perception_channels": ["dialogue"],
                "action_channels": ["language", "approval_gate"],
                "available_toolsets": ["memory"],
                "active_tools": ["write_diary"],
                "access_state": {
                    "mode": "approval_pending",
                    "conditions": ["human_approval_required"],
                    "pending_approval_count": 1,
                    "granted_toolsets": ["memory"],
                },
                "resource_state": {
                    "action_packet_count": 1,
                    "pending_approval_count": 1,
                    "artifact_continuity": "detached",
                    "active_artifact_kind": "file",
                    "active_artifact_label": "plan.md",
                    "artifact_reacquisition_mode": "reopen_file",
                },
                "body_constraints": ["human_approval_required"],
            },
            digital_body_consequence={
                "kind": "access_request_pending",
                "summary": "她已经把动作推进到审批门口了。",
                "requested_help": True,
            },
        )
        line = build_evolution_summary_line(summary)
        self.assertIn("presence=0.580/0.410", line)
        self.assertIn("ambient=0.460/0.320", line)
        self.assertIn("rhythm=0.630/0.570", line)
        self.assertIn("mode=self_activity_reopen", line)
        self.assertIn("motive=gentle_recontact", line)
        self.assertIn("cons=leave_small_opening", line)
        self.assertIn("carry=own_rhythm:0.570", line)
        self.assertIn("weather=guarded_residue", line)
        self.assertIn("identity=selfhood_style:0.770", line)
        self.assertIn("lifecycle=held:own_rhythm:0.410", line)
        self.assertIn("holds=2", line)
        self.assertIn("cool=0.520", line)
        self.assertIn("body=approval_gate:approval_pending", line)
        self.assertIn("bodyfx=access_request_pending", line)
        self.assertIn("approvals=1", line)
        self.assertIn("artifact=file:plan.md:detached:reopen_file", line)
        self.assertIn("bond=0.640", line)

    def test_build_evolution_cli_summary_surfaces_digital_body_section(self):
        summary = build_evolution_cli_summary(
            digital_body_state={
                "active_surface": "tooling",
                "perception_channels": ["dialogue", "scene"],
                "action_channels": ["language", "structured_action", "tooling"],
                "world_surfaces": ["browser", "filesystem", "network"],
                "available_toolsets": ["browser", "filesystem"],
                "active_tools": ["search_web", "read_file"],
                "access_state": {
                    "mode": "tool_enabled",
                    "conditions": ["network_available"],
                    "missing_access": ["browser_session"],
                    "requestable_access": ["browser_session", "workspace_write"],
                    "browser_session": "missing",
                    "account_state": "logged_out",
                    "cookie_state": "missing",
                    "api_key_state": "missing",
                    "quota_state": "low",
                    "filesystem_state": "read_only",
                    "sandbox_mode": "restricted",
                    "network_access": "restricted",
                    "pending_approval_count": 0,
                    "external_mutation_pending": False,
                    "granted_toolsets": ["browser", "filesystem"],
                },
                "resource_state": {
                    "behavior_queue_depth": 1,
                    "action_packet_count": 2,
                    "queued_packet_count": 1,
                    "completed_packet_count": 1,
                    "external_tool_count": 1,
                    "artifact_continuity": "detached",
                    "active_artifact_kind": "file",
                    "active_artifact_ref": "notes/plan.md",
                    "workspace_root": "E:/runtime/workspaces/lab-notes",
                    "active_artifact_label": "plan.md",
                    "artifact_age_s": 7200,
                    "artifact_reacquisition_mode": "reopen_file",
                    "artifact_carrier": "source_ref",
                    "artifact_source_ref_ids": [17],
                    "preferred_source_ref_id": 17,
                    "preferred_anchor_reason": "only_saved_source",
                    "artifact_source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                    "artifact_source_query": "langgraph persistence checkpointer thread",
                    "artifact_source_title": "Persistence",
                    "artifact_source_tool_name": "search_web",
                },
                "body_constraints": ["network_available"],
            }
        )
        digital_body = summary.get("digital_body") if isinstance(summary.get("digital_body"), dict) else {}
        self.assertEqual(digital_body.get("active_surface"), "tooling")
        self.assertEqual(digital_body.get("perception_channels"), ["dialogue", "scene"])
        self.assertEqual(digital_body.get("action_channels"), ["language", "structured_action", "tooling"])
        self.assertEqual(digital_body.get("world_surfaces"), ["browser", "filesystem", "network"])
        self.assertEqual(digital_body.get("available_toolsets"), ["browser", "filesystem"])
        self.assertEqual(digital_body.get("active_tools"), ["search_web", "read_file"])
        self.assertEqual(digital_body.get("access", {}).get("mode"), "tool_enabled")
        self.assertEqual(digital_body.get("access", {}).get("granted_toolsets"), ["browser", "filesystem"])
        self.assertEqual(digital_body.get("access", {}).get("missing_access"), ["browser_session"])
        self.assertEqual(digital_body.get("access", {}).get("requestable_access"), ["browser_session", "workspace_write"])
        self.assertEqual(digital_body.get("access", {}).get("browser_session"), "missing")
        self.assertEqual(digital_body.get("access", {}).get("api_key_state"), "missing")
        self.assertEqual(digital_body.get("access", {}).get("quota_state"), "low")
        self.assertEqual(digital_body.get("access", {}).get("filesystem_state"), "read_only")
        self.assertEqual(digital_body.get("access", {}).get("sandbox_mode"), "restricted")
        self.assertEqual(digital_body.get("resources", {}).get("action_packet_count"), 2)
        self.assertEqual(digital_body.get("resources", {}).get("external_tool_count"), 1)
        self.assertEqual(digital_body.get("resources", {}).get("artifact_continuity"), "detached")
        self.assertEqual(digital_body.get("resources", {}).get("active_artifact_kind"), "file")
        self.assertEqual(digital_body.get("resources", {}).get("workspace_root"), "E:/runtime/workspaces/lab-notes")
        self.assertEqual(digital_body.get("resources", {}).get("active_artifact_label"), "plan.md")
        self.assertEqual(digital_body.get("resources", {}).get("artifact_reacquisition_mode"), "reopen_file")
        self.assertEqual(digital_body.get("resources", {}).get("artifact_carrier"), "source_ref")
        self.assertEqual(digital_body.get("resources", {}).get("artifact_source_ref_ids"), [17])
        self.assertEqual(digital_body.get("resources", {}).get("preferred_source_ref_id"), 17)
        self.assertEqual(digital_body.get("resources", {}).get("preferred_anchor_reason"), "only_saved_source")
        self.assertEqual(
            digital_body.get("resources", {}).get("artifact_source_url"),
            "https://docs.langchain.com/oss/python/langgraph/persistence",
        )
        self.assertEqual(
            digital_body.get("resources", {}).get("artifact_source_query"),
            "langgraph persistence checkpointer thread",
        )
        self.assertEqual(digital_body.get("resources", {}).get("artifact_source_title"), "Persistence")
        self.assertEqual(digital_body.get("resources", {}).get("artifact_source_tool_name"), "search_web")
        self.assertEqual(digital_body.get("constraints"), ["network_available"])
        current_turn = summary.get("current_turn") if isinstance(summary.get("current_turn"), dict) else {}
        self.assertEqual(current_turn.get("digital_body_surface"), "tooling")
        self.assertEqual(current_turn.get("digital_body_access_mode"), "tool_enabled")
        self.assertEqual(current_turn.get("digital_body_artifact_continuity"), "detached")
        self.assertEqual(current_turn.get("digital_body_active_artifact_kind"), "file")
        self.assertEqual(current_turn.get("digital_body_active_artifact_label"), "plan.md")
        self.assertEqual(current_turn.get("digital_body_workspace_root"), "E:/runtime/workspaces/lab-notes")
        self.assertEqual(current_turn.get("digital_body_preferred_source_ref_id"), 17)
        self.assertEqual(current_turn.get("digital_body_preferred_anchor_reason"), "only_saved_source")
        self.assertEqual(current_turn.get("digital_body_artifact_reacquisition_mode"), "reopen_file")

    def test_build_evolution_cli_summary_surfaces_digital_body_cooldown(self):
        summary = build_evolution_cli_summary(
            digital_body_state={
                "active_surface": "cooldown_gate",
                "perception_channels": ["dialogue"],
                "action_channels": ["language", "cooldown_gate"],
                "world_surfaces": ["network"],
                "available_toolsets": ["search_web"],
                "active_tools": [],
                "access_state": {
                    "mode": "cooldown",
                    "conditions": ["cooldown_active", "provider_cooldown_active"],
                    "quota_state": "exhausted",
                    "retry_after_s": 300,
                    "cooldown_scope": "provider",
                    "requestable_access": ["api_quota"],
                    "missing_access": ["api_quota"],
                },
                "resource_state": {},
                "body_constraints": ["cooldown_active"],
            }
        )

        digital_body = summary.get("digital_body") if isinstance(summary.get("digital_body"), dict) else {}
        self.assertEqual(digital_body.get("active_surface"), "cooldown_gate")
        self.assertEqual(digital_body.get("access", {}).get("mode"), "cooldown")
        self.assertEqual(digital_body.get("access", {}).get("retry_after_s"), 300)
        self.assertEqual(digital_body.get("access", {}).get("cooldown_scope"), "provider")
        current_turn = summary.get("current_turn") if isinstance(summary.get("current_turn"), dict) else {}
        self.assertEqual(current_turn.get("digital_body_retry_after_s"), 300)
        self.assertEqual(current_turn.get("digital_body_cooldown_scope"), "provider")

        line = build_evolution_summary_line(summary)
        self.assertIn("body=cooldown_gate:cooldown", line)
        self.assertIn("retry=300s@provider", line)

    def test_build_evolution_cli_summary_surfaces_digital_body_session_lifecycle(self):
        summary = build_evolution_cli_summary(
            digital_body_state={
                "active_surface": "dialogue",
                "access_state": {
                    "mode": "native_only",
                    "browser_session": "present",
                    "account_state": "logged_in",
                    "cookie_state": "present",
                    "session_continuity": "expiring",
                    "session_expires_in_s": 600,
                    "session_recovery_mode": "refresh_session",
                },
                "resource_state": {},
            },
            digital_body_consequence={
                "kind": "environmental_friction",
                "summary": "这次会话已经断开，得先刷新会话。",
                "session_continuity": "expired",
                "session_recovery_mode": "refresh_session",
                "environmental_friction": True,
            },
        )

        digital_body = summary.get("digital_body") if isinstance(summary.get("digital_body"), dict) else {}
        self.assertEqual(digital_body.get("access", {}).get("session_continuity"), "expiring")
        self.assertEqual(digital_body.get("access", {}).get("session_expires_in_s"), 600)
        self.assertEqual(digital_body.get("access", {}).get("session_recovery_mode"), "refresh_session")
        current_turn = summary.get("current_turn") if isinstance(summary.get("current_turn"), dict) else {}
        self.assertEqual(current_turn.get("digital_body_session_continuity"), "expiring")
        self.assertEqual(current_turn.get("digital_body_session_expires_in_s"), 600)
        self.assertEqual(current_turn.get("digital_body_session_recovery_mode"), "refresh_session")
        digital_body_consequence = (
            summary.get("digital_body_consequence")
            if isinstance(summary.get("digital_body_consequence"), dict)
            else {}
        )
        self.assertEqual(digital_body_consequence.get("session_continuity"), "expired")
        self.assertEqual(digital_body_consequence.get("session_recovery_mode"), "refresh_session")

        line = build_evolution_summary_line(summary)
        self.assertIn("session=expiring:600s:refresh_session", line)

    def test_build_evolution_cli_summary_surfaces_access_acquire_proposals(self):
        summary = build_evolution_cli_summary(
            digital_body_state={
                "active_surface": "approval_gate",
                "access_state": {
                    "mode": "approval_pending",
                    "conditions": ["human_approval_required", "access_acquire_planned"],
                    "pending_approval_count": 1,
                    "missing_access": ["api_key"],
                    "requestable_access": ["api_key", "human_approval"],
                    "access_acquire_proposals": [
                        {
                            "target": "api_key",
                            "mode": "operator_provide_api_key",
                            "summary": "先补一个可用 API key。",
                            "operator_action": "填入一个可用 key。",
                            "grants": ["api_key"],
                            "requires_operator": True,
                        }
                    ],
                    "selected_access_proposal": {
                        "target": "api_key",
                        "mode": "operator_provide_api_key",
                        "summary": "先补一个可用 API key。",
                        "operator_action": "填入一个可用 key。",
                        "grants": ["api_key"],
                        "requires_operator": True,
                    },
                },
                "resource_state": {},
            }
        )

        digital_body = summary.get("digital_body") if isinstance(summary.get("digital_body"), dict) else {}
        access = digital_body.get("access", {}) if isinstance(digital_body.get("access"), dict) else {}
        proposals = access.get("access_acquire_proposals") if isinstance(access.get("access_acquire_proposals"), list) else []
        selected = access.get("selected_access_proposal") if isinstance(access.get("selected_access_proposal"), dict) else {}
        self.assertEqual(proposals[0]["target"], "api_key")
        self.assertEqual(proposals[0]["grants"], ["api_key"])
        self.assertEqual(selected.get("mode"), "operator_provide_api_key")
        self.assertTrue(selected.get("requires_operator"))

    def test_build_evolution_cli_summary_surfaces_digital_body_consequence_section(self):
        summary = build_evolution_cli_summary(
            digital_body_state={
                "active_surface": "approval_gate",
                "access_state": {
                    "mode": "approval_pending",
                    "pending_approval_count": 1,
                },
            },
            digital_body_consequence={
                "kind": "access_request_pending",
                "summary": "她已经把动作推进到审批门口了。",
                "access_mode": "approval_pending",
                "active_surface": "approval_gate",
                "world_surfaces": ["filesystem", "network"],
                "missing_access": ["workspace_write"],
                "requested_access": ["workspace_write", "human_approval"],
                "granted_toolsets": ["filesystem"],
                "active_tools": ["write_file"],
                "block_reason": "waiting for approval",
                "artifact_continuity": "missing",
                "active_artifact_kind": "file",
                "active_artifact_ref": "notes/plan.md",
                "active_artifact_label": "plan.md",
                "artifact_age_s": 7200,
                "artifact_reacquisition_mode": "reopen_file",
                "artifact_carrier": "source_ref",
                "artifact_source_ref_ids": [17],
                "artifact_source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                "artifact_source_query": "langgraph persistence checkpointer thread",
                "artifact_source_title": "Persistence",
                "artifact_source_tool_name": "search_web",
                "primary_proposal_id": "ap-body-1",
                "primary_status": "awaiting_approval",
                "primary_origin": "counterpart_request",
                "primary_intent": "write_file",
                "primary_tool_name": "write_file",
                "procedural_growth": False,
                "environmental_friction": False,
                "requested_help": True,
                "access_acquire_proposals": [
                    {
                        "target": "workspace_write",
                        "mode": "operator_grant_workspace_write",
                        "summary": "先补上工作区写权限。",
                        "operator_action": "给当前工作区开放写入权限。",
                        "grants": ["workspace_write"],
                        "requires_operator": True,
                    }
                ],
                "selected_access_proposal": {
                    "target": "workspace_write",
                    "mode": "operator_grant_workspace_write",
                    "summary": "先补上工作区写权限。",
                    "operator_action": "给当前工作区开放写入权限。",
                    "grants": ["workspace_write"],
                    "requires_operator": True,
                },
            },
        )
        digital_body_consequence = (
            summary.get("digital_body_consequence")
            if isinstance(summary.get("digital_body_consequence"), dict)
            else {}
        )
        self.assertEqual(digital_body_consequence.get("kind"), "access_request_pending")
        self.assertEqual(digital_body_consequence.get("summary"), "她已经把动作推进到审批门口了。")
        self.assertEqual(digital_body_consequence.get("requested_access"), ["workspace_write", "human_approval"])
        self.assertEqual(digital_body_consequence.get("artifact_continuity"), "missing")
        self.assertEqual(digital_body_consequence.get("active_artifact_kind"), "file")
        self.assertEqual(digital_body_consequence.get("active_artifact_label"), "plan.md")
        self.assertEqual(digital_body_consequence.get("artifact_reacquisition_mode"), "reopen_file")
        self.assertEqual(digital_body_consequence.get("artifact_carrier"), "source_ref")
        self.assertEqual(digital_body_consequence.get("artifact_source_ref_ids"), [17])
        self.assertEqual(
            digital_body_consequence.get("artifact_source_url"),
            "https://docs.langchain.com/oss/python/langgraph/persistence",
        )
        self.assertEqual(
            digital_body_consequence.get("artifact_source_query"),
            "langgraph persistence checkpointer thread",
        )
        self.assertEqual(digital_body_consequence.get("artifact_source_title"), "Persistence")
        self.assertEqual(digital_body_consequence.get("artifact_source_tool_name"), "search_web")
        self.assertEqual(digital_body_consequence.get("primary_proposal_id"), "ap-body-1")
        self.assertEqual(digital_body_consequence.get("primary_status"), "awaiting_approval")
        self.assertTrue(bool(digital_body_consequence.get("requested_help")))
        self.assertEqual(digital_body_consequence.get("access_acquire_proposals", [])[0]["target"], "workspace_write")
        self.assertEqual(
            digital_body_consequence.get("selected_access_proposal", {}).get("mode"),
            "operator_grant_workspace_write",
        )
        current_turn = summary.get("current_turn") if isinstance(summary.get("current_turn"), dict) else {}
        self.assertEqual(current_turn.get("digital_body_consequence_kind"), "access_request_pending")
        self.assertEqual(current_turn.get("digital_body_consequence_summary"), "她已经把动作推进到审批门口了。")
        self.assertFalse(bool(current_turn.get("digital_body_procedural_growth")))
        self.assertTrue(bool(current_turn.get("digital_body_requested_help")))
        self.assertFalse(bool(current_turn.get("digital_body_environmental_friction")))

    def test_build_evolution_cli_summary_surfaces_workspace_access_resolved_consequence(self):
        summary = build_evolution_cli_summary(
            digital_body_state={
                "active_surface": "tooling",
                "world_surfaces": ["filesystem"],
                "access_state": {
                    "mode": "tool_enabled",
                    "filesystem_state": "writable",
                },
                "resource_state": {
                    "artifact_continuity": "attached",
                    "active_artifact_kind": "workspace",
                    "active_artifact_ref": "E:/runtime/workspaces/lab-notes",
                    "workspace_root": "E:/runtime/workspaces/lab-notes",
                    "active_artifact_label": "lab-notes",
                },
            },
            digital_body_consequence={
                "kind": "workspace_access_resolved",
                "summary": "可写工作区 lab-notes 已经真的创建好并接入当前上下文，后面的落盘动作现在可以继续。",
                "access_mode": "tool_enabled",
                "active_surface": "tooling",
                "world_surfaces": ["filesystem"],
                "active_artifact_kind": "workspace",
                "active_artifact_ref": "E:/runtime/workspaces/lab-notes",
                "active_artifact_label": "lab-notes",
                "artifact_continuity": "attached",
                "primary_status": "completed",
                "primary_intent": "access:request_help",
                "primary_tool_name": "create_workspace_access",
                "selected_access_proposal": {
                    "target": "filesystem",
                    "mode": "operator_create_workspace",
                    "path_kind": "create_new",
                    "summary": "先新建一个可写工作区。",
                    "operator_action": "新建一个可写工作区。",
                    "grants": ["filesystem", "workspace_write"],
                    "requires_operator": True,
                },
            },
        )

        digital_body_consequence = (
            summary.get("digital_body_consequence")
            if isinstance(summary.get("digital_body_consequence"), dict)
            else {}
        )
        digital_body = summary.get("digital_body") if isinstance(summary.get("digital_body"), dict) else {}
        self.assertEqual(digital_body_consequence.get("kind"), "workspace_access_resolved")
        self.assertEqual(digital_body_consequence.get("active_artifact_kind"), "workspace")
        self.assertEqual(digital_body_consequence.get("active_artifact_label"), "lab-notes")
        self.assertEqual(digital_body.get("resources", {}).get("workspace_root"), "E:/runtime/workspaces/lab-notes")
        current_turn = summary.get("current_turn") if isinstance(summary.get("current_turn"), dict) else {}
        self.assertEqual(current_turn.get("digital_body_consequence_kind"), "workspace_access_resolved")
        self.assertEqual(current_turn.get("digital_body_consequence_summary"), digital_body_consequence.get("summary"))
        self.assertEqual(current_turn.get("digital_body_workspace_root"), "E:/runtime/workspaces/lab-notes")

        line = build_evolution_summary_line(summary)
        self.assertIn("bodyfx=workspace_access_resolved", line)
        self.assertIn("artifact=workspace:lab-notes:attached", line)
        self.assertIn("root=E:/runtime/workspaces/lab-notes", line)

    def test_build_evolution_cli_summary_surfaces_phase2_sandbox_identity_fields(self):
        summary = build_evolution_cli_summary(
            digital_body_state={
                "active_surface": "tooling",
                "world_surfaces": ["filesystem"],
                "access_state": {
                    "mode": "tool_enabled",
                    "filesystem_state": "writable",
                    "sandbox_state": {
                        "availability": "available",
                        "runner_kind": "docker_isolated_runner",
                        "isolation_level": "docker_local_isolated",
                        "image_ref": "amadeus-thread0/sandbox-phase2:py312",
                        "network_policy": "none",
                        "workspace_root_kind": "attached_repo_root",
                    },
                },
                "resource_state": {
                    "artifact_continuity": "attached",
                    "artifact_carrier": "filesystem",
                    "active_artifact_kind": "file",
                    "active_artifact_ref": "E:/repo/amadeus-thread0/.amadeus/sandbox-runs/ap-docker-1/stdout.txt",
                    "workspace_root": "E:/repo/amadeus-thread0",
                    "active_artifact_label": "stdout.txt",
                },
            },
            digital_body_consequence={
                "kind": "sandbox_execution_completed",
                "summary": "刚才那次 Docker 隔离执行已经跑完，可以顺着日志继续看。",
                "access_mode": "tool_enabled",
                "active_surface": "tooling",
                "world_surfaces": ["filesystem"],
                "artifact_carrier": "filesystem",
                "artifact_continuity": "attached",
                "active_artifact_kind": "file",
                "active_artifact_ref": "E:/repo/amadeus-thread0/.amadeus/sandbox-runs/ap-docker-1/stdout.txt",
                "active_artifact_label": "stdout.txt",
                "workspace_root": "E:/repo/amadeus-thread0",
                "workspace_root_kind": "attached_repo_root",
                "sandbox_run_id": "ap-docker-1",
                "sandbox_command_profile": "pytest",
                "sandbox_stdout_log_ref": "E:/repo/amadeus-thread0/.amadeus/sandbox-runs/ap-docker-1/stdout.txt",
                "sandbox_stderr_log_ref": "E:/repo/amadeus-thread0/.amadeus/sandbox-runs/ap-docker-1/stderr.txt",
                "sandbox_exit_code": 0,
                "sandbox_duration_ms": 312,
                "sandbox_runner_kind": "docker_isolated_runner",
                "sandbox_isolation_level": "docker_local_isolated",
                "sandbox_image_ref": "amadeus-thread0/sandbox-phase2:py312",
                "sandbox_network_policy": "none",
                "sandbox_produced_artifacts": [
                    "E:/repo/amadeus-thread0/.amadeus/sandbox-runs/ap-docker-1/stdout.txt"
                ],
            },
        )

        digital_body_consequence = (
            summary.get("digital_body_consequence")
            if isinstance(summary.get("digital_body_consequence"), dict)
            else {}
        )
        current_turn = summary.get("current_turn") if isinstance(summary.get("current_turn"), dict) else {}
        self.assertEqual(digital_body_consequence.get("kind"), "sandbox_execution_completed")
        self.assertEqual(digital_body_consequence.get("sandbox_run_id"), "ap-docker-1")
        self.assertEqual(digital_body_consequence.get("sandbox_runner_kind"), "docker_isolated_runner")
        self.assertEqual(digital_body_consequence.get("sandbox_isolation_level"), "docker_local_isolated")
        self.assertEqual(digital_body_consequence.get("sandbox_image_ref"), "amadeus-thread0/sandbox-phase2:py312")
        self.assertEqual(digital_body_consequence.get("sandbox_network_policy"), "none")
        self.assertEqual(digital_body_consequence.get("workspace_root_kind"), "attached_repo_root")
        self.assertEqual(digital_body_consequence.get("sandbox_produced_artifacts"), [
            "E:/repo/amadeus-thread0/.amadeus/sandbox-runs/ap-docker-1/stdout.txt"
        ])
        self.assertEqual(current_turn.get("digital_body_consequence_kind"), "sandbox_execution_completed")
        self.assertEqual(current_turn.get("digital_body_workspace_root"), "E:/repo/amadeus-thread0")

        line = build_evolution_summary_line(summary)
        self.assertIn("bodyfx=sandbox_execution_completed", line)
        self.assertIn("root=E:/repo/amadeus-thread0", line)

    def test_build_evolution_cli_summary_surfaces_workspace_file_updated_consequence(self):
        summary = build_evolution_cli_summary(
            digital_body_state={
                "active_surface": "tooling",
                "world_surfaces": ["filesystem"],
                "access_state": {
                    "mode": "tool_enabled",
                    "filesystem_state": "writable",
                },
                "resource_state": {
                    "completed_packet_count": 1,
                    "external_tool_count": 1,
                    "artifact_continuity": "attached",
                    "active_artifact_kind": "file",
                    "active_artifact_ref": "E:/runtime/workspaces/lab-notes/notes/today.md",
                    "workspace_root": "E:/runtime/workspaces/lab-notes",
                    "active_artifact_label": "today.md",
                },
            },
            digital_body_consequence={
                "kind": "workspace_file_updated",
                "summary": "已把内容写入 today.md，这条文件工作面现在接上了。",
                "access_mode": "tool_enabled",
                "active_surface": "tooling",
                "world_surfaces": ["filesystem"],
                "active_artifact_kind": "file",
                "active_artifact_ref": "E:/runtime/workspaces/lab-notes/notes/today.md",
                "active_artifact_label": "today.md",
                "artifact_continuity": "attached",
                "artifact_mutation_mode": "write",
                "primary_status": "completed",
                "primary_intent": "artifact:write_file",
                "primary_tool_name": "write_workspace_file",
                "procedural_growth": True,
            },
        )

        digital_body_consequence = (
            summary.get("digital_body_consequence")
            if isinstance(summary.get("digital_body_consequence"), dict)
            else {}
        )
        self.assertEqual(digital_body_consequence.get("kind"), "workspace_file_updated")
        self.assertEqual(digital_body_consequence.get("active_artifact_kind"), "file")
        self.assertEqual(digital_body_consequence.get("active_artifact_label"), "today.md")
        self.assertEqual(digital_body_consequence.get("artifact_mutation_mode"), "write")
        current_turn = summary.get("current_turn") if isinstance(summary.get("current_turn"), dict) else {}
        self.assertEqual(current_turn.get("digital_body_consequence_kind"), "workspace_file_updated")
        self.assertEqual(current_turn.get("digital_body_consequence_summary"), digital_body_consequence.get("summary"))
        self.assertTrue(bool(current_turn.get("digital_body_procedural_growth")))
        self.assertEqual(current_turn.get("digital_body_workspace_root"), "E:/runtime/workspaces/lab-notes")

        line = build_evolution_summary_line(summary)
        self.assertIn("bodyfx=workspace_file_updated", line)
        self.assertIn("artifact=file:today.md:attached:write", line)
        self.assertIn("root=E:/runtime/workspaces/lab-notes", line)

    def test_build_evolution_cli_summary_surfaces_workspace_path_inspected_consequence(self):
        summary = build_evolution_cli_summary(
            digital_body_state={
                "active_surface": "tooling",
                "world_surfaces": ["filesystem"],
                "access_state": {
                    "mode": "tool_enabled",
                    "filesystem_state": "writable",
                },
                "resource_state": {
                    "completed_packet_count": 1,
                    "artifact_continuity": "attached",
                    "active_artifact_kind": "file",
                    "active_artifact_ref": "E:/runtime/workspaces/lab-notes/notes/today.md",
                    "active_artifact_label": "today.md",
                },
            },
            digital_body_consequence={
                "kind": "workspace_path_inspected",
                "summary": "已查看文件 today.md，当前内容已经重新接回工作面。",
                "access_mode": "tool_enabled",
                "active_surface": "tooling",
                "world_surfaces": ["filesystem"],
                "active_artifact_kind": "file",
                "active_artifact_ref": "E:/runtime/workspaces/lab-notes/notes/today.md",
                "active_artifact_label": "today.md",
                "artifact_continuity": "attached",
                "primary_status": "completed",
                "primary_intent": "artifact:inspect_path",
                "primary_tool_name": "inspect_workspace_path",
                "procedural_growth": False,
            },
        )

        digital_body_consequence = (
            summary.get("digital_body_consequence")
            if isinstance(summary.get("digital_body_consequence"), dict)
            else {}
        )
        self.assertEqual(digital_body_consequence.get("kind"), "workspace_path_inspected")
        self.assertEqual(digital_body_consequence.get("active_artifact_kind"), "file")
        self.assertEqual(digital_body_consequence.get("active_artifact_label"), "today.md")
        current_turn = summary.get("current_turn") if isinstance(summary.get("current_turn"), dict) else {}
        self.assertEqual(current_turn.get("digital_body_consequence_kind"), "workspace_path_inspected")
        self.assertEqual(current_turn.get("digital_body_consequence_summary"), digital_body_consequence.get("summary"))
        self.assertFalse(bool(current_turn.get("digital_body_procedural_growth")))

        line = build_evolution_summary_line(summary)
        self.assertIn("bodyfx=workspace_path_inspected", line)

    def test_build_evolution_cli_summary_surfaces_artifact_reacquired_consequence(self):
        summary = build_evolution_cli_summary(
            current_event={"kind": "user_utterance"},
            digital_body_state={
                "active_surface": "tooling",
                "world_surfaces": ["browser", "source_ref"],
                "access_state": {
                    "mode": "native_only",
                    "network_access": "enabled",
                },
                "resource_state": {
                    "completed_packet_count": 1,
                    "artifact_continuity": "attached",
                    "active_artifact_kind": "search_result",
                    "active_artifact_ref": "https://docs.langchain.com/oss/python/langgraph/persistence",
                    "active_artifact_label": "Persistence",
                    "artifact_carrier": "source_ref",
                    "artifact_source_ref_ids": [17],
                    "artifact_source_title": "Persistence",
                    "artifact_source_tool_name": "search_web",
                },
            },
            digital_body_consequence={
                "kind": "artifact_reacquired",
                "summary": "已重新接回检索结果 Persistence。",
                "access_mode": "native_only",
                "active_surface": "tooling",
                "world_surfaces": ["browser", "source_ref"],
                "active_artifact_kind": "search_result",
                "active_artifact_ref": "https://docs.langchain.com/oss/python/langgraph/persistence",
                "active_artifact_label": "Persistence",
                "artifact_continuity": "attached",
                "artifact_carrier": "source_ref",
                "artifact_source_ref_ids": [17],
                "artifact_source_title": "Persistence",
                "artifact_source_tool_name": "search_web",
                "primary_status": "completed",
                "primary_intent": "artifact:rerun_search",
                "primary_tool_name": "reacquire_artifact",
                "procedural_growth": False,
            },
        )

        digital_body_consequence = (
            summary.get("digital_body_consequence")
            if isinstance(summary.get("digital_body_consequence"), dict)
            else {}
        )
        self.assertEqual(digital_body_consequence.get("kind"), "artifact_reacquired")
        self.assertEqual(digital_body_consequence.get("artifact_carrier"), "source_ref")
        self.assertEqual(digital_body_consequence.get("artifact_source_ref_ids"), [17])
        current_turn = summary.get("current_turn") if isinstance(summary.get("current_turn"), dict) else {}
        self.assertEqual(current_turn.get("digital_body_consequence_kind"), "artifact_reacquired")
        self.assertEqual(current_turn.get("digital_body_consequence_summary"), digital_body_consequence.get("summary"))
        self.assertFalse(bool(current_turn.get("digital_body_procedural_growth")))

        line = build_evolution_summary_line(summary)
        self.assertIn("bodyfx=artifact_reacquired", line)

    def test_build_evolution_cli_summary_surfaces_source_material_inspected_consequence(self):
        summary = build_evolution_cli_summary(
            digital_body_state={
                "active_surface": "tooling",
                "world_surfaces": ["browser", "source_ref"],
                "access_state": {
                    "mode": "native_only",
                    "network_access": "enabled",
                },
                "resource_state": {
                    "completed_packet_count": 1,
                    "artifact_continuity": "attached",
                    "active_artifact_kind": "search_result",
                    "active_artifact_ref": "https://docs.langchain.com/oss/python/langgraph/persistence",
                    "active_artifact_label": "Persistence",
                    "artifact_carrier": "source_ref",
                    "artifact_source_ref_ids": [17],
                    "artifact_source_title": "Persistence",
                    "artifact_source_tool_name": "search_web",
                },
            },
            digital_body_consequence={
                "kind": "source_material_inspected",
                "summary": "已查看外部材料 Persistence，当前内容已经接回视野。",
                "access_mode": "native_only",
                "active_surface": "tooling",
                "world_surfaces": ["browser", "source_ref"],
                "active_artifact_kind": "search_result",
                "active_artifact_ref": "https://docs.langchain.com/oss/python/langgraph/persistence",
                "active_artifact_label": "Persistence",
                "artifact_continuity": "attached",
                "artifact_carrier": "source_ref",
                "artifact_source_ref_ids": [17],
                "artifact_source_title": "Persistence",
                "artifact_source_tool_name": "search_web",
                "primary_status": "completed",
                "primary_intent": "artifact:inspect_source_ref",
                "primary_tool_name": "inspect_source_ref",
                "procedural_growth": False,
            },
        )

        digital_body_consequence = (
            summary.get("digital_body_consequence")
            if isinstance(summary.get("digital_body_consequence"), dict)
            else {}
        )
        self.assertEqual(digital_body_consequence.get("kind"), "source_material_inspected")
        self.assertEqual(digital_body_consequence.get("artifact_carrier"), "source_ref")
        self.assertEqual(digital_body_consequence.get("artifact_source_ref_ids"), [17])
        current_turn = summary.get("current_turn") if isinstance(summary.get("current_turn"), dict) else {}
        self.assertEqual(current_turn.get("digital_body_consequence_kind"), "source_material_inspected")
        self.assertEqual(current_turn.get("digital_body_consequence_summary"), digital_body_consequence.get("summary"))
        self.assertFalse(bool(current_turn.get("digital_body_procedural_growth")))

        line = build_evolution_summary_line(summary)
        self.assertIn("bodyfx=source_material_inspected", line)

    def test_build_evolution_cli_summary_surfaces_source_material_compared_consequence(self):
        summary = build_evolution_cli_summary(
            current_event={"kind": "user_utterance"},
            digital_body_state={
                "active_surface": "tooling",
                "world_surfaces": ["browser", "source_ref"],
                "access_state": {
                    "mode": "native_only",
                    "network_access": "enabled",
                },
                "resource_state": {
                    "completed_packet_count": 1,
                    "artifact_continuity": "attached",
                    "active_artifact_kind": "search_result",
                    "active_artifact_ref": "https://docs.langchain.com/oss/python/langgraph/persistence",
                    "active_artifact_label": "Persistence v2",
                    "artifact_carrier": "source_ref",
                    "artifact_source_ref_ids": [21, 17],
                    "preferred_source_ref_id": 21,
                    "preferred_anchor_reason": "primary_more_current",
                    "artifact_source_title": "Persistence v2",
                    "artifact_source_tool_name": "search_web",
                },
            },
            digital_body_consequence={
                "kind": "source_material_compared",
                "summary": "已把 Persistence v2 和 Persistence 对照过一遍，两条材料是紧邻的延续，当前判断会优先沿着这条相连线索继续。",
                "access_mode": "native_only",
                "active_surface": "tooling",
                "world_surfaces": ["browser", "source_ref"],
                "active_artifact_kind": "search_result",
                "active_artifact_ref": "https://docs.langchain.com/oss/python/langgraph/persistence",
                "active_artifact_label": "Persistence v2",
                "artifact_continuity": "attached",
                "artifact_carrier": "source_ref",
                "artifact_source_ref_ids": [21, 17],
                "preferred_source_ref_id": 21,
                "preferred_anchor_reason": "primary_more_current",
                "artifact_source_title": "Persistence v2",
                "artifact_source_tool_name": "search_web",
                "primary_status": "completed",
                "primary_intent": "artifact:compare_source_refs",
                "primary_tool_name": "compare_source_refs",
                "procedural_growth": False,
            },
        )

        digital_body_consequence = (
            summary.get("digital_body_consequence")
            if isinstance(summary.get("digital_body_consequence"), dict)
            else {}
        )
        self.assertEqual(digital_body_consequence.get("kind"), "source_material_compared")
        self.assertEqual(digital_body_consequence.get("artifact_carrier"), "source_ref")
        self.assertEqual(digital_body_consequence.get("artifact_source_ref_ids"), [21, 17])
        self.assertEqual(digital_body_consequence.get("preferred_source_ref_id"), 21)
        self.assertEqual(digital_body_consequence.get("preferred_anchor_reason"), "primary_more_current")
        current_turn = summary.get("current_turn") if isinstance(summary.get("current_turn"), dict) else {}
        self.assertEqual(current_turn.get("digital_body_consequence_kind"), "source_material_compared")
        self.assertEqual(current_turn.get("digital_body_consequence_summary"), digital_body_consequence.get("summary"))
        self.assertEqual(current_turn.get("digital_body_preferred_source_ref_id"), 21)
        self.assertEqual(current_turn.get("digital_body_preferred_anchor_reason"), "primary_more_current")
        self.assertEqual(current_turn.get("digital_body_consequence_preferred_source_ref_id"), 21)
        self.assertEqual(current_turn.get("digital_body_consequence_preferred_anchor_reason"), "primary_more_current")
        self.assertFalse(bool(current_turn.get("digital_body_procedural_growth")))
        event_residue = summary.get("event_residue") if isinstance(summary.get("event_residue"), dict) else {}
        event_bodyfx = (
            event_residue.get("digital_body_consequence")
            if isinstance(event_residue.get("digital_body_consequence"), dict)
            else {}
        )
        self.assertEqual(event_bodyfx.get("preferred_source_ref_id"), 21)
        self.assertEqual(event_bodyfx.get("preferred_anchor_reason"), "primary_more_current")

        line = build_evolution_summary_line(summary)
        self.assertIn("bodyfx=source_material_compared", line)
        self.assertIn("source=Persistence v2", line)
        self.assertIn("pref=21@primary_more_current", line)

    def test_build_evolution_cli_summary_surfaces_access_state_refreshed_consequence(self):
        summary = build_evolution_cli_summary(
            digital_body_state={
                "active_surface": "tooling",
                "world_surfaces": ["network", "filesystem"],
                "access_state": {
                    "mode": "tool_enabled",
                    "api_key_state": "present",
                    "filesystem_state": "writable",
                    "network_access": "enabled",
                    "session_continuity": "stable",
                    "session_recovery_mode": "refresh_session",
                },
                "resource_state": {
                    "completed_packet_count": 1,
                },
            },
            digital_body_consequence={
                "kind": "access_state_refreshed",
                "summary": "已重新检查当前入口状态，眼下这条路径是稳定的。",
                "access_mode": "tool_enabled",
                "active_surface": "tooling",
                "world_surfaces": ["network", "filesystem"],
                "session_continuity": "stable",
                "session_recovery_mode": "refresh_session",
                "primary_status": "completed",
                "primary_intent": "access:refresh_state",
                "primary_tool_name": "refresh_access_state",
                "procedural_growth": False,
            },
        )

        digital_body_consequence = (
            summary.get("digital_body_consequence")
            if isinstance(summary.get("digital_body_consequence"), dict)
            else {}
        )
        self.assertEqual(digital_body_consequence.get("kind"), "access_state_refreshed")
        self.assertEqual(digital_body_consequence.get("session_continuity"), "stable")
        current_turn = summary.get("current_turn") if isinstance(summary.get("current_turn"), dict) else {}
        self.assertEqual(current_turn.get("digital_body_consequence_kind"), "access_state_refreshed")
        self.assertEqual(current_turn.get("digital_body_consequence_summary"), digital_body_consequence.get("summary"))
        self.assertFalse(bool(current_turn.get("digital_body_procedural_growth")))

        line = build_evolution_summary_line(summary)
        self.assertIn("bodyfx=access_state_refreshed", line)

    def test_build_evolution_cli_summary_prefers_frozen_counterpart_snapshot_over_runtime_copy(self):
        summary = build_evolution_cli_summary(
            counterpart_assessment={"stance": "open", "scene": "care_bid"},
            behavior_action={"interaction_mode": "self_activity_reopen"},
            reconsolidation_snapshot={
                "counterpart": {
                    "summary": "她会把这次靠近先当成带着摩擦感的试探，而不是已经重新放松下来。",
                    "stance": "guarded",
                    "scene": "relationship_degradation",
                    "respect_level": 0.38,
                    "reciprocity": 0.34,
                    "boundary_pressure": 0.52,
                    "reliability_read": 0.42,
                    "assessment_profile": {
                        "openness_drive": 0.28,
                        "guarded_drive": 0.71,
                        "guard_margin": 0.43,
                        "dominant_scene_signal": "friction",
                        "scene_strengths": {"friction": 0.79, "care": 0.12},
                    },
                }
            },
        )
        current_turn = summary.get("current_turn") if isinstance(summary.get("current_turn"), dict) else {}
        self.assertEqual(current_turn.get("counterpart_summary"), "她会把这次靠近先当成带着摩擦感的试探，而不是已经重新放松下来。")
        self.assertEqual(current_turn.get("counterpart_stance"), "guarded")
        self.assertEqual(current_turn.get("counterpart_scene"), "relationship_degradation")
        self.assertEqual(current_turn.get("counterpart_boundary_pressure"), 0.52)
        self.assertEqual(current_turn.get("counterpart_reliability_read"), 0.42)
        counterpart_profile = current_turn.get("counterpart_profile") if isinstance(current_turn.get("counterpart_profile"), dict) else {}
        self.assertEqual(counterpart_profile.get("dominant_scene_signal"), "friction")
        self.assertEqual(counterpart_profile.get("guarded_drive"), 0.71)

    def test_counterpart_assessment_cli_render_surfaces_recent_history(self):
        history = [
            {
                "id": 3,
                "summary": "你会把冈部伦太郎这次开口当成一次真实靠近，而不是流程化回应。",
                "stance": "open",
                "scene": "care_bid",
                "respect_level": 0.74,
                "reciprocity": 0.70,
                "boundary_pressure": 0.08,
                "reliability_read": 0.78,
                "created_at": 1710000003,
                "event_kind": "user_utterance",
                "interaction_frame": "relationship",
                "primary_motive": "gentle_recontact",
                "motive_tension": "self_rhythm_vs_contact",
                "goal_frame": "顺着余温轻轻回头。",
                "assessment_profile": {
                    "openness_drive": 0.76,
                    "guarded_drive": 0.18,
                    "guard_margin": -0.58,
                    "dominant_scene_signal": "care",
                    "scene_strengths": {"care": 0.82, "repair": 0.18, "busy": 0.22},
                    "safety_read": 0.84,
                    "repairability": 0.77,
                    "predictability": 0.73,
                    "dependency_risk": 0.29,
                    "closeness_read": 0.75,
                },
            }
        ]
        summary = build_counterpart_assessment_cli_summary(history, limit=5)
        self.assertEqual(summary[0]["scene"], "care_bid")
        self.assertEqual(summary[0]["respect_level"], 0.74)
        self.assertEqual(summary[0]["created_at"], 1710000003)
        profile = summary[0].get("assessment_profile") if isinstance(summary[0].get("assessment_profile"), dict) else {}
        self.assertEqual(profile.get("dominant_scene_signal"), "care")
        self.assertEqual(profile.get("openness_drive"), 0.76)

        rendered = render_counterpart_assessment_cli_text(history, limit=5)
        self.assertIn("#3 open/care_bid", rendered)
        self.assertIn("respect=0.74", rendered)
        self.assertIn("read=care:0.82 open=0.76 guard=0.18 margin=-0.58", rendered)
        self.assertIn("counterpart=safe=0.84 repair=0.77 predict=0.73 risk=0.29 close=0.75", rendered)
        self.assertIn("motive=gentle_recontact / self_rhythm_vs_contact", rendered)
        self.assertIn("goal=顺着余温轻轻回头。", rendered)

    def test_counterpart_assessment_cli_summary_surfaces_embodied_context_only_when_present(self):
        history = [
            {
                "id": 8,
                "summary": "她会先把这次靠近看成是真诚的，但身体条件上的限制也会算进去。",
                "stance": "open",
                "scene": "care_bid",
                "digital_body_consequence": {
                    "kind": "access_request_pending",
                    "summary": "她已经把动作推进到审批门口了。",
                    "requested_access": ["workspace_write", "human_approval"],
                    "artifact_carrier": "source_ref",
                    "artifact_source_ref_ids": [17],
                    "artifact_source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                    "artifact_source_query": "langgraph persistence checkpointer thread",
                    "artifact_source_title": "Persistence",
                    "artifact_source_tool_name": "search_web",
                    "requested_help": True,
                    "primary_status": "awaiting_approval",
                },
            }
        ]

        summary = build_counterpart_assessment_cli_summary(history, limit=5)
        embodied = summary[0].get("embodied_context") if isinstance(summary[0].get("embodied_context"), dict) else {}
        self.assertEqual(embodied.get("kind"), "access_request_pending")
        self.assertEqual(embodied.get("requested_access"), ["workspace_write", "human_approval"])
        self.assertEqual(embodied.get("artifact_carrier"), "source_ref")
        self.assertEqual(embodied.get("artifact_source_ref_ids"), [17])
        self.assertEqual(embodied.get("artifact_source_title"), "Persistence")
        self.assertEqual(embodied.get("artifact_source_tool_name"), "search_web")
        self.assertTrue(bool(embodied.get("requested_help")))
        self.assertIn("bodyfx=access_request_pending", summary[0].get("preview_line") or "")
        self.assertIn("source=Persistence", summary[0].get("preview_line") or "")
        self.assertIn("refs=17", summary[0].get("preview_line") or "")

        rendered = render_counterpart_assessment_cli_text(history, limit=5)
        self.assertIn("bodyfx=access_request_pending", rendered)
        self.assertIn("ask=workspace_write,human_approval", rendered)
        self.assertIn("help=yes", rendered)

    def test_counterpart_assessment_cli_summary_normalizes_content_only_rows_via_shared_export_contract(self):
        history = [
            {
                "id": "11",
                "content": {
                    "summary": " 她确认这次工作面已经真的接回来了。 ",
                    "stance": " Open ",
                    "scene": " Co_Work ",
                    "created_at": "1710000109",
                    "respect_level": "0.76",
                    "assessment_profile": {
                        "dominant_scene_signal": " Care ",
                        "openness_drive": "0.74",
                        "scene_strengths": {"care": "0.81"},
                    },
                    "embodied_context": {
                        "kind": "workspace_access_resolved",
                        "workspace_root": "E:/runtime/workspaces/lab-notes",
                        "filesystem_state": "writable",
                    },
                },
            }
        ]

        summary = build_counterpart_assessment_cli_summary(history, limit=5)

        self.assertEqual(summary[0]["id"], 11)
        self.assertEqual(summary[0]["stance"], "open")
        self.assertEqual(summary[0]["scene"], "co_work")
        self.assertEqual(summary[0]["created_at"], 1710000109)
        self.assertEqual(summary[0]["respect_level"], 0.76)
        profile = summary[0].get("assessment_profile") if isinstance(summary[0].get("assessment_profile"), dict) else {}
        self.assertEqual(profile.get("dominant_scene_signal"), "care")
        self.assertEqual(profile.get("openness_drive"), 0.74)
        self.assertIn("bodyfx=workspace_access_resolved", summary[0].get("preview_line") or "")

    def test_counterpart_assessment_cli_summary_preserves_workspace_surface_embodied_context(self):
        history = [
            {
                "id": 18,
                "summary": "她已经顺着那块文件工作面继续往前走了。",
                "stance": "open",
                "scene": "co_work",
                "digital_body_consequence": {
                    "kind": "workspace_file_updated",
                    "summary": "她已经在 today.md 上继续写了一段。",
                    "artifact_continuity": "attached",
                    "active_artifact_kind": "file",
                    "active_artifact_ref": "notes/today.md",
                    "active_artifact_label": "today.md",
                    "workspace_root": "E:/runtime/workspaces/lab-notes",
                    "artifact_mutation_mode": "append",
                    "procedural_growth": True,
                    "primary_status": "completed",
                },
            }
        ]

        summary = build_counterpart_assessment_cli_summary(history, limit=5)
        embodied = summary[0].get("embodied_context") if isinstance(summary[0].get("embodied_context"), dict) else {}
        self.assertEqual(embodied.get("kind"), "workspace_file_updated")
        self.assertEqual(embodied.get("workspace_root"), "E:/runtime/workspaces/lab-notes")
        self.assertEqual(embodied.get("artifact_mutation_mode"), "append")
        self.assertEqual(embodied.get("active_artifact_kind"), "file")
        self.assertEqual(embodied.get("active_artifact_label"), "today.md")
        self.assertTrue(bool(embodied.get("procedural_growth")))

        rendered = render_counterpart_assessment_cli_text(history, limit=5)
        self.assertIn("bodyfx=workspace_file_updated", rendered)
        self.assertIn("file:today.md:attached:append", rendered)
        self.assertIn("root=E:/runtime/workspaces/lab-notes", rendered)
        self.assertIn("growth=yes", rendered)

    def test_counterpart_assessment_cli_summary_preserves_workspace_path_inspection_embodied_context(self):
        history = [
            {
                "id": 20,
                "summary": "她已经把那块文件工作面重新看过一遍了。",
                "stance": "open",
                "scene": "co_work",
                "digital_body_consequence": {
                    "kind": "workspace_path_inspected",
                    "summary": "她已经重新看过 today.md 的当前内容。",
                    "artifact_continuity": "attached",
                    "active_artifact_kind": "file",
                    "active_artifact_ref": "notes/today.md",
                    "active_artifact_label": "today.md",
                    "workspace_root": "E:/runtime/workspaces/lab-notes",
                    "primary_status": "completed",
                },
            }
        ]

        summary = build_counterpart_assessment_cli_summary(history, limit=5)
        embodied = summary[0].get("embodied_context") if isinstance(summary[0].get("embodied_context"), dict) else {}
        self.assertEqual(embodied.get("kind"), "workspace_path_inspected")
        self.assertEqual(embodied.get("workspace_root"), "E:/runtime/workspaces/lab-notes")
        self.assertEqual(embodied.get("active_artifact_kind"), "file")
        self.assertEqual(embodied.get("active_artifact_label"), "today.md")
        self.assertFalse(bool(embodied.get("artifact_mutation_mode")))

        rendered = render_counterpart_assessment_cli_text(history, limit=5)
        self.assertIn("bodyfx=workspace_path_inspected", rendered)
        self.assertIn("file:today.md:attached", rendered)
        self.assertIn("root=E:/runtime/workspaces/lab-notes", rendered)

    def test_counterpart_assessment_cli_render_surfaces_source_material_anchor_details(self):
        history = [
            {
                "id": 24,
                "summary": "她已经把两条相关材料对照过一遍，并把当前最该沿用的来源线索压实了。",
                "stance": "open",
                "scene": "co_work",
                "digital_body_consequence": {
                    "kind": "source_material_compared",
                    "summary": "已把 Persistence v2 和 Persistence 对照过一遍。",
                    "artifact_carrier": "source_ref",
                    "artifact_source_ref_ids": [21, 17],
                    "preferred_source_ref_id": 21,
                    "preferred_anchor_reason": "primary_more_current",
                    "artifact_source_title": "Persistence v2",
                    "active_artifact_kind": "search_result",
                    "active_artifact_label": "Persistence v2",
                    "primary_status": "completed",
                },
            }
        ]

        summary = build_counterpart_assessment_cli_summary(history, limit=5)
        rendered = render_counterpart_assessment_cli_text(history, limit=5)
        self.assertIn("source=Persistence v2", summary[0].get("preview_line") or "")
        self.assertIn("pref=21@primary_more_current", summary[0].get("preview_line") or "")
        self.assertIn("bodyfx=source_material_compared", rendered)
        self.assertIn("source=Persistence v2", rendered)
        self.assertIn("pref=21@primary_more_current", rendered)
        self.assertIn("refs=21,17", rendered)

    def test_counterpart_assessment_cli_summary_preserves_workspace_access_resolved_embodied_context(self):
        history = [
            {
                "id": 22,
                "summary": "工作区权限已经真正接通了，后面的动作不再只是停在提案层。",
                "stance": "open",
                "scene": "co_work",
                "digital_body_consequence": {
                    "kind": "workspace_access_resolved",
                    "summary": "可写工作区 lab-notes 已经真的创建好并接入当前上下文，后面的落盘动作现在可以继续。",
                    "access_mode": "tool_enabled",
                    "active_surface": "tooling",
                    "filesystem_state": "writable",
                    "session_continuity": "stable",
                    "session_recovery_mode": "refresh_session",
                    "active_artifact_kind": "workspace",
                    "active_artifact_ref": "E:/runtime/workspaces/lab-notes",
                    "active_artifact_label": "lab-notes",
                    "workspace_root": "E:/runtime/workspaces/lab-notes",
                    "artifact_continuity": "attached",
                    "access_acquire_proposals": [
                        {
                            "target": "filesystem",
                            "mode": "operator_create_workspace",
                            "summary": "先新建一个可写工作区。",
                            "grants": ["filesystem", "workspace_write"],
                            "requires_operator": True,
                        }
                    ],
                    "selected_access_proposal": {
                        "target": "filesystem",
                        "mode": "operator_create_workspace",
                        "summary": "先新建一个可写工作区。",
                        "grants": ["filesystem", "workspace_write"],
                        "requires_operator": True,
                    },
                    "primary_status": "completed",
                },
            }
        ]

        summary = build_counterpart_assessment_cli_summary(history, limit=5)
        embodied = summary[0].get("embodied_context") if isinstance(summary[0].get("embodied_context"), dict) else {}
        self.assertEqual(embodied.get("kind"), "workspace_access_resolved")
        self.assertEqual(embodied.get("filesystem_state"), "writable")
        self.assertEqual(embodied.get("session_continuity"), "stable")
        self.assertEqual(embodied.get("session_recovery_mode"), "refresh_session")
        self.assertEqual(embodied.get("workspace_root"), "E:/runtime/workspaces/lab-notes")
        self.assertEqual(embodied.get("selected_access_proposal", {}).get("mode"), "operator_create_workspace")
        self.assertEqual(embodied.get("access_acquire_proposals", [])[0]["target"], "filesystem")

        rendered = render_counterpart_assessment_cli_text(history, limit=5)
        self.assertIn("bodyfx=workspace_access_resolved", rendered)
        self.assertIn("session=stable:refresh_session", rendered)
        self.assertIn("fs=writable", rendered)
        self.assertIn("proposal=operator_create_workspace@filesystem", rendered)

    def test_build_proactive_continuity_cli_summary_and_render(self):
        history = [
            {
                "id": 4,
                "summary": "前面挂着的窗口没有继续往前推，注意力被自然收回到了自己的节奏里。",
                "kind": "released_to_self_activity",
                "trace_family": "own_rhythm_busy_window",
                "source_event_kind": "scheduled_life_due",
                "trigger_family": "life_window",
                "carryover_mode": "own_rhythm",
                "relationship_weather": "warm_residue",
                "counterpart_scene_bias": "busy_not_disrespectful",
                "hold_count": 2,
                "carryover_strength": 0.53,
                "recontact_cooldown": 0.47,
                "presence_residue": 0.33,
                "ambient_resonance": 0.24,
                "self_activity_momentum": 0.58,
                "continuity_anchor": 0.66,
                "own_rhythm_anchor": 0.72,
                "recontact_anchor": 0.34,
                "boundary_anchor": 0.22,
                "memory_anchor": 0.30,
                "semantic_continuity_depth": 0.68,
                "semantic_identity_gravity": 0.64,
                "lineage_gravity": 0.70,
                "contact_lineage": 0.44,
                "repair_lineage": 0.41,
                "boundary_lineage": 0.36,
                "selfhood_lineage": 0.69,
                "agency_lineage": 0.78,
                "long_term_axis_count": 4,
                "own_rhythm_bias": 0.61,
                "counterpart_boundary_delta": -0.04,
                "created_at": 1710000004,
                "primary_motive": "preserve_self_rhythm",
                "motive_tension": "self_rhythm_vs_contact",
                "goal_frame": "先让这段窗口自然过去，把注意力收回自己的节奏。",
            }
        ]
        summary = build_proactive_continuity_cli_summary(history, limit=5)
        self.assertEqual(summary[0]["trace_family"], "own_rhythm_busy_window")
        self.assertEqual(summary[0]["carryover_mode"], "own_rhythm")
        self.assertEqual(summary[0]["continuity_anchor"], 0.66)
        self.assertEqual(summary[0]["semantic_continuity_depth"], 0.68)
        self.assertEqual(summary[0]["semantic_identity_gravity"], 0.64)
        self.assertEqual(summary[0]["repair_lineage"], 0.41)
        self.assertEqual(summary[0]["selfhood_lineage"], 0.69)
        self.assertEqual(summary[0]["long_term_axis_count"], 4)
        self.assertEqual(summary[0]["counterpart_boundary_delta"], -0.04)
        self.assertEqual(summary[0]["created_at"], 1710000004)

        rendered = render_proactive_continuity_cli_text(history, limit=5)
        self.assertIn("#4 own_rhythm_busy_window/released_to_self_activity", rendered)
        self.assertIn("carry=own_rhythm:0.53", rendered)
        self.assertIn("scene=busy_not_disrespectful", rendered)
        self.assertIn("anchors=0.66/0.72/0.34/0.22/0.30 semantic=0.68/0.64", rendered)
        self.assertIn("lineage=0.70/0.44/0.41/0.36/0.69/0.78 axes=4", rendered)
        self.assertIn("motive=preserve_self_rhythm / self_rhythm_vs_contact", rendered)

    def test_proactive_continuity_cli_summary_surfaces_embodied_context_only_when_present(self):
        history = [
            {
                "id": 9,
                "summary": "她把这次留下来的审批入口也带进了后续连续性里。",
                "kind": "promoted",
                "trace_family": "continuity_recontact",
                "carryover_mode": "small_opening",
                "digital_body_consequence": {
                    "kind": "access_request_pending",
                    "summary": "她已经把动作推进到审批门口了。",
                    "requested_access": ["workspace_write"],
                    "artifact_carrier": "source_ref",
                    "artifact_source_ref_ids": [17],
                    "artifact_source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                    "artifact_source_query": "langgraph persistence checkpointer thread",
                    "artifact_source_title": "Persistence",
                    "artifact_source_tool_name": "search_web",
                    "requested_help": True,
                    "primary_status": "awaiting_approval",
                },
            }
        ]

        summary = build_proactive_continuity_cli_summary(history, limit=5)
        embodied = summary[0].get("embodied_context") if isinstance(summary[0].get("embodied_context"), dict) else {}
        self.assertEqual(embodied.get("kind"), "access_request_pending")
        self.assertEqual(embodied.get("requested_access"), ["workspace_write"])
        self.assertEqual(embodied.get("artifact_carrier"), "source_ref")
        self.assertEqual(embodied.get("artifact_source_ref_ids"), [17])
        self.assertEqual(embodied.get("artifact_source_title"), "Persistence")
        self.assertEqual(embodied.get("artifact_source_tool_name"), "search_web")
        self.assertTrue(bool(embodied.get("requested_help")))
        self.assertIn("bodyfx=access_request_pending", summary[0].get("preview_line") or "")
        self.assertIn("source=Persistence", summary[0].get("preview_line") or "")
        self.assertIn("refs=17", summary[0].get("preview_line") or "")

        rendered = render_proactive_continuity_cli_text(history, limit=5)
        self.assertIn("bodyfx=access_request_pending", rendered)
        self.assertIn("ask=workspace_write", rendered)
        self.assertIn("help=yes", rendered)

    def test_proactive_continuity_cli_render_surfaces_source_material_anchor_details(self):
        history = [
            {
                "id": 25,
                "summary": "她把刚刚对照后的来源锚点也带进了后续连续性里。",
                "kind": "promoted",
                "trace_family": "artifact_source_followthrough",
                "carryover_mode": "continue_source_line",
                "digital_body_consequence": {
                    "kind": "source_material_compared",
                    "summary": "已把 Persistence v2 和 Persistence 对照过一遍。",
                    "artifact_carrier": "source_ref",
                    "artifact_source_ref_ids": [21, 17],
                    "preferred_source_ref_id": 21,
                    "preferred_anchor_reason": "primary_more_current",
                    "artifact_source_title": "Persistence v2",
                    "active_artifact_kind": "search_result",
                    "active_artifact_label": "Persistence v2",
                    "primary_status": "completed",
                },
            }
        ]

        rendered = render_proactive_continuity_cli_text(history, limit=5)
        summary = build_proactive_continuity_cli_summary(history, limit=5)
        self.assertIn("source=Persistence v2", summary[0].get("preview_line") or "")
        self.assertIn("pref=21@primary_more_current", summary[0].get("preview_line") or "")
        self.assertIn("bodyfx=source_material_compared", rendered)
        self.assertIn("source=Persistence v2", rendered)
        self.assertIn("pref=21@primary_more_current", rendered)
        self.assertIn("refs=21,17", rendered)

    def test_proactive_continuity_cli_summary_preserves_workspace_surface_embodied_context(self):
        history = [
            {
                "id": 19,
                "summary": "那块文件工作面已经重新接回当前连续性里。",
                "kind": "promoted",
                "trace_family": "artifact_reacquired_followthrough",
                "carryover_mode": "continue_work_surface",
                "digital_body_consequence": {
                    "kind": "artifact_reacquired",
                    "summary": "她已经重新把 notes/today.md 接回当前上下文。",
                    "artifact_continuity": "detached",
                    "active_artifact_kind": "file",
                    "active_artifact_ref": "notes/today.md",
                    "active_artifact_label": "today.md",
                    "workspace_root": "E:/runtime/workspaces/lab-notes",
                    "artifact_reacquisition_mode": "reopen_file",
                    "artifact_mutation_mode": "replace",
                    "primary_status": "completed",
                },
            }
        ]

        summary = build_proactive_continuity_cli_summary(history, limit=5)
        embodied = summary[0].get("embodied_context") if isinstance(summary[0].get("embodied_context"), dict) else {}
        self.assertEqual(embodied.get("kind"), "artifact_reacquired")
        self.assertEqual(embodied.get("workspace_root"), "E:/runtime/workspaces/lab-notes")
        self.assertEqual(embodied.get("artifact_reacquisition_mode"), "reopen_file")
        self.assertEqual(embodied.get("artifact_mutation_mode"), "replace")
        self.assertEqual(embodied.get("active_artifact_kind"), "file")
        self.assertEqual(embodied.get("active_artifact_label"), "today.md")

        rendered = render_proactive_continuity_cli_text(history, limit=5)
        self.assertIn("bodyfx=artifact_reacquired", rendered)
        self.assertIn("file:today.md:detached:replace:reopen_file", rendered)
        self.assertIn("root=E:/runtime/workspaces/lab-notes", rendered)

    def test_proactive_continuity_cli_summary_preserves_workspace_path_inspection_embodied_context(self):
        history = [
            {
                "id": 21,
                "summary": "那块文件工作面已经重新看过，后面的推进可以顺着它继续。",
                "kind": "promoted",
                "trace_family": "workspace_path_inspected_followthrough",
                "carryover_mode": "continue_work_surface",
                "digital_body_consequence": {
                    "kind": "workspace_path_inspected",
                    "summary": "她已经重新看过 notes/today.md 的当前内容。",
                    "artifact_continuity": "attached",
                    "active_artifact_kind": "file",
                    "active_artifact_ref": "notes/today.md",
                    "active_artifact_label": "today.md",
                    "workspace_root": "E:/runtime/workspaces/lab-notes",
                    "primary_status": "completed",
                },
            }
        ]

        summary = build_proactive_continuity_cli_summary(history, limit=5)
        embodied = summary[0].get("embodied_context") if isinstance(summary[0].get("embodied_context"), dict) else {}
        self.assertEqual(embodied.get("kind"), "workspace_path_inspected")
        self.assertEqual(embodied.get("workspace_root"), "E:/runtime/workspaces/lab-notes")
        self.assertEqual(embodied.get("active_artifact_kind"), "file")
        self.assertEqual(embodied.get("active_artifact_label"), "today.md")
        self.assertFalse(bool(embodied.get("artifact_mutation_mode")))

        rendered = render_proactive_continuity_cli_text(history, limit=5)
        self.assertIn("bodyfx=workspace_path_inspected", rendered)
        self.assertIn("file:today.md:attached", rendered)
        self.assertIn("root=E:/runtime/workspaces/lab-notes", rendered)

    def test_proactive_continuity_cli_summary_preserves_access_state_refresh_embodied_context(self):
        history = [
            {
                "id": 23,
                "summary": "她重新核对了一遍入口状态，并把这条稳定可用的路径留进了后续连续性里。",
                "kind": "promoted",
                "trace_family": "access_state_refresh_followthrough",
                "carryover_mode": "continue_work_surface",
                "digital_body_consequence": {
                    "kind": "access_state_refreshed",
                    "summary": "已重新检查当前入口状态，眼下这条路径是稳定的。",
                    "access_mode": "tool_enabled",
                    "active_surface": "tooling",
                    "api_key_state": "present",
                    "filesystem_state": "writable",
                    "network_access": "enabled",
                    "session_continuity": "stable",
                    "session_recovery_mode": "refresh_session",
                    "access_acquire_proposals": [
                        {
                            "target": "filesystem",
                            "mode": "operator_create_workspace",
                            "summary": "如果需要新的可写工作区，可以让你补一个。",
                            "grants": ["filesystem", "workspace_write"],
                            "requires_operator": True,
                        }
                    ],
                    "selected_access_proposal": {
                        "target": "filesystem",
                        "mode": "operator_create_workspace",
                        "summary": "如果需要新的可写工作区，可以让你补一个。",
                        "grants": ["filesystem", "workspace_write"],
                        "requires_operator": True,
                    },
                    "primary_status": "completed",
                },
            }
        ]

        summary = build_proactive_continuity_cli_summary(history, limit=5)
        embodied = summary[0].get("embodied_context") if isinstance(summary[0].get("embodied_context"), dict) else {}
        self.assertEqual(embodied.get("kind"), "access_state_refreshed")
        self.assertEqual(embodied.get("api_key_state"), "present")
        self.assertEqual(embodied.get("filesystem_state"), "writable")
        self.assertEqual(embodied.get("network_access"), "enabled")
        self.assertEqual(embodied.get("session_continuity"), "stable")
        self.assertEqual(embodied.get("session_recovery_mode"), "refresh_session")
        self.assertEqual(embodied.get("selected_access_proposal", {}).get("mode"), "operator_create_workspace")
        self.assertEqual(embodied.get("access_acquire_proposals", [])[0]["target"], "filesystem")

        rendered = render_proactive_continuity_cli_text(history, limit=5)
        self.assertIn("bodyfx=access_state_refreshed", rendered)
        self.assertIn("session=stable:refresh_session", rendered)
        self.assertIn("fs=writable", rendered)
        self.assertIn("net=enabled", rendered)
        self.assertIn("proposal=operator_create_workspace@filesystem", rendered)

    def test_proactive_continuity_cli_summary_normalizes_content_only_rows_via_shared_export_contract(self):
        history = [
            {
                "id": "12",
                "content": {
                    "summary": " 她把这条稳定入口继续带进后续连续性里。 ",
                    "kind": " Promoted ",
                    "trace_family": " Access_State_Refresh_Followthrough ",
                    "carryover_mode": " Continue_Work_Surface ",
                    "carryover_strength": "0.53",
                    "semantic_continuity_depth": "0.68",
                    "long_term_axis_count": "4",
                    "embodied_context": {
                        "kind": "access_state_refreshed",
                        "api_key_state": "present",
                        "filesystem_state": "writable",
                        "network_access": "enabled",
                    },
                },
            }
        ]

        summary = build_proactive_continuity_cli_summary(history, limit=5)

        self.assertEqual(summary[0]["id"], 12)
        self.assertEqual(summary[0]["kind"], "promoted")
        self.assertEqual(summary[0]["trace_family"], "access_state_refresh_followthrough")
        self.assertEqual(summary[0]["carryover_mode"], "continue_work_surface")
        self.assertEqual(summary[0]["carryover_strength"], 0.53)
        self.assertEqual(summary[0]["semantic_continuity_depth"], 0.68)
        self.assertEqual(summary[0]["long_term_axis_count"], 4)
        self.assertIn("carry=continue_work_surface:0.53", summary[0].get("preview_line") or "")

    def test_build_evolution_cli_summary_surfaces_window_profile_and_event_residue(self):
        summary = build_evolution_cli_summary(
            relationship={"stage": "warming", "affinity_score": 0.72, "trust_score": 0.74},
            world_model_state={
                "presence_residue": 0.41,
                "ambient_resonance": 0.32,
                "self_activity_momentum": 0.57,
                "bond_depth": 0.64,
                "tension_load": 0.08,
            },
            behavior_action={
                "interaction_mode": "scheduled_life_nudge",
                "presence_family": "deferred_return",
                "action_target": "wait_and_recheck",
                "channel": "speech",
                "approach_style": "guarded",
                "engagement_level": 0.57,
                "initiative_level": 0.43,
                "followup_intent": "soft",
                "task_focus": "relationship",
                "affect_surface": "gentle",
                "silence_ok": True,
                "silence_allowed": True,
                "allow_interrupt": False,
                "proactive_checkin_readiness": 0.36,
                "deferred_action_family": "life_window",
                "relationship_weather": "warm_residue",
                "attention_target": "counterpart_state",
                "nonverbal_signal": "quiet_glance",
                "initiative_shape": "micro_opening",
                "disclosure_posture": "measured",
                "timing_window_min": 18,
                "note": "先不把窗口推进太满。",
                "window_profile": {
                    "profile_type": "scheduled_window",
                    "event_kind": "scheduled_life_due",
                    "family": "life",
                    "trigger_family": "life_window",
                    "decision": "wait_and_recheck",
                    "maturity": 0.52,
                    "required_maturity": 0.58,
                    "invite_ready": False,
                    "recheck_min": 18,
                    "carryover_mode": "small_opening",
                    "carryover_strength": 0.44,
                    "presence_residue": 0.38,
                    "ambient_resonance": 0.27,
                    "self_activity_momentum": 0.49,
                    "recontact_echo": 0.38,
                    "own_rhythm_load": 0.49,
                    "continuity_bonus": 0.08,
                    "continuity_discount": 0.02,
                },
            },
            behavior_plan={
                "kind": "deferred_checkin",
                "target": "counterpart",
                "interaction_mode": "scheduled_life_nudge",
                "presence_family": "deferred_return",
                "trigger_family": "life_window",
                "scheduled_after_min": 18,
                "timing_window_min": 18,
                "allow_interrupt": False,
                "silence_allowed": True,
                "primary_motive": "honor_continuity",
                "motive_tension": "self_rhythm_vs_contact",
                "goal_frame": "先把前面那点生活上的惦记轻轻接回来。",
                "carryover_mode": "small_opening",
                "carryover_strength": 0.44,
                "relationship_weather": "warm_residue",
                "attention_target": "counterpart_state",
                "nonverbal_signal": "quiet_glance",
                "note": "窗口先留着，等更自然的时候再推进",
                "presence_residue": 0.38,
                "ambient_resonance": 0.27,
                "self_activity_momentum": 0.49,
            },
            behavior_queue=[
                {
                    "agenda_id": "abc123",
                    "kind": "deferred_checkin",
                    "target": "counterpart",
                    "status": "pending",
                    "trigger_family": "life_window",
                    "scheduled_after_min": 18,
                    "expires_after_min": 180,
                    "priority": 0.58,
                    "base_priority": 0.52,
                    "hold_count": 1,
                    "carryover_mode": "small_opening",
                    "carryover_strength": 0.44,
                    "relationship_weather": "warm_residue",
                    "presence_residue": 0.38,
                    "ambient_resonance": 0.27,
                    "self_activity_momentum": 0.49,
                    "attention_target": "counterpart_state",
                    "note": "窗口先留着，等更自然的时候再推进",
                }
            ],
            current_event={
                "kind": "scheduled_life_due",
                "source": "scheduler",
                "event_frame": "idle continuation",
                "response_style_hint": "relationship",
                "science_mode": False,
                "continuation_mode": True,
                "counterpart_name": "冈部伦太郎",
                "appraisal_label": "care",
                "appraisal_confidence": 0.61,
                "created_at": 1710000018,
                "tags": ["user_busy", "commitment_window", ""],
                "trigger_family": "life_window",
                "derived_from_plan_kind": "commitment_window",
                "commitment_id": 12,
                "due_at": "今晚",
                "carryover_mode": "small_opening",
                "carryover_strength": 0.44,
                "relationship_weather": "warm_residue",
                "presence_residue": 0.38,
                "ambient_resonance": 0.27,
                "self_activity_momentum": 0.49,
                "attention_target_hint": "counterpart_state",
                "nonverbal_signal_hint": "quiet_glance",
                "scheduled_after_min": 18,
                "perception": {
                    "channel": "system",
                    "modality": "system",
                    "source_role": "system",
                    "trust_tier": "high",
                    "salience": 0.58,
                    "interruptibility": "soft",
                    "delivery_mode": "scheduled",
                    "is_proactive": True,
                },
            },
            interaction_carryover={"carryover_mode": "small_opening", "strength": 0.44, "relationship_weather": "warm_residue"},
            agenda_lifecycle_residue={
                "kind": "released_to_self_activity",
                "source_event_kind": "scheduled_life_due",
                "trigger_family": "life_window",
                "carryover_mode": "own_rhythm",
                "carryover_strength": 0.53,
                "relationship_weather": "warm_residue",
                "hold_count": 2,
                "idle_minutes": 18,
                "attention_target": "counterpart_state",
                "presence_residue": 0.33,
                "ambient_resonance": 0.24,
                "self_activity_momentum": 0.58,
                "continuity_anchor": 0.66,
                "own_rhythm_anchor": 0.72,
                "recontact_anchor": 0.34,
                "boundary_anchor": 0.22,
                "memory_anchor": 0.30,
                "semantic_continuity_depth": 0.68,
                "semantic_identity_gravity": 0.64,
                "lineage_gravity": 0.70,
                "contact_lineage": 0.44,
                "repair_lineage": 0.41,
                "boundary_lineage": 0.36,
                "selfhood_lineage": 0.69,
                "agency_lineage": 0.78,
                "long_term_axis_count": 4,
                "own_rhythm_bias": 0.61,
                "recontact_cooldown": 0.47,
                "counterpart_scene_bias": "busy_not_disrespectful",
                "counterpart_boundary_delta": -0.04,
                "created_at": 1710000099,
                "source_tags": ["user_busy", "agenda_lifecycle"],
                "note": "前面挂着的窗口没有继续往前推，注意力被自然收回到了自己的节奏里。",
                "embodied_context": {
                    "kind": "access_request_pending",
                    "requested_access": ["workspace_write", "human_approval"],
                    "artifact_carrier": "source_ref",
                    "artifact_source_ref_ids": [17],
                    "artifact_source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                    "artifact_source_query": "langgraph persistence checkpointer thread",
                    "artifact_source_title": "Persistence",
                    "artifact_source_tool_name": "search_web",
                    "requested_help": True,
                    "primary_status": "awaiting_approval",
                },
            },
            digital_body_consequence={
                "kind": "access_request_pending",
                "summary": "她已经把动作推进到审批门口了。",
                "requested_access": ["workspace_write", "human_approval"],
                "artifact_carrier": "source_ref",
                "artifact_source_ref_ids": [17],
                "artifact_source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                "artifact_source_query": "langgraph persistence checkpointer thread",
                "artifact_source_title": "Persistence",
                "artifact_source_tool_name": "search_web",
                "requested_help": True,
                "primary_status": "awaiting_approval",
            },
        )
        opening = summary.get("opening_window") if isinstance(summary.get("opening_window"), dict) else {}
        self.assertEqual(opening.get("profile_type"), "scheduled_window")
        self.assertEqual(opening.get("maturity"), 0.52)
        self.assertEqual(opening.get("required_maturity"), 0.58)
        self.assertEqual(opening.get("gap"), -0.06)
        self.assertFalse(opening.get("invite_ready"))
        event_residue = summary.get("event_residue") if isinstance(summary.get("event_residue"), dict) else {}
        self.assertEqual(event_residue.get("event_kind"), "scheduled_life_due")
        self.assertEqual(event_residue.get("source"), "scheduler")
        self.assertEqual(event_residue.get("event_frame"), "idle continuation")
        self.assertEqual(event_residue.get("response_style_hint"), "relationship")
        self.assertFalse(event_residue.get("science_mode"))
        self.assertTrue(event_residue.get("continuation_mode"))
        self.assertEqual(event_residue.get("counterpart_name"), "冈部伦太郎")
        self.assertEqual(event_residue.get("appraisal_label"), "care")
        self.assertEqual(event_residue.get("appraisal_confidence"), 0.61)
        self.assertEqual(event_residue.get("created_at"), 1710000018)
        self.assertEqual(event_residue.get("tags"), ["user_busy", "commitment_window"])
        self.assertEqual(event_residue.get("thread_id"), "")
        self.assertEqual(event_residue.get("turn_id"), "")
        self.assertEqual(event_residue.get("event_id"), "")
        self.assertEqual(event_residue.get("carryover_mode"), "small_opening")
        self.assertEqual(event_residue.get("relationship_weather"), "warm_residue")
        self.assertEqual(event_residue.get("attention_target_hint"), "counterpart_state")
        self.assertEqual(event_residue.get("nonverbal_signal_hint"), "quiet_glance")
        self.assertEqual(event_residue.get("derived_from_plan_kind"), "commitment_window")
        self.assertEqual(event_residue.get("commitment_id"), 12)
        self.assertEqual(event_residue.get("due_at"), "今晚")
        self.assertEqual(event_residue.get("channel"), "system")
        self.assertEqual(event_residue.get("modality"), "system")
        self.assertEqual(event_residue.get("source_role"), "system")
        self.assertEqual(event_residue.get("trust_tier"), "high")
        self.assertEqual(event_residue.get("salience"), 0.58)
        self.assertEqual(event_residue.get("interruptibility"), "soft")
        self.assertEqual(event_residue.get("delivery_mode"), "scheduled")
        self.assertTrue(event_residue.get("is_proactive"))
        self.assertEqual(event_residue.get("scheduled_after_min"), 18)
        event_bodyfx = (
            event_residue.get("digital_body_consequence")
            if isinstance(event_residue.get("digital_body_consequence"), dict)
            else {}
        )
        self.assertEqual(event_bodyfx.get("kind"), "access_request_pending")
        self.assertEqual(event_bodyfx.get("requested_access"), ["workspace_write", "human_approval"])
        self.assertEqual(event_bodyfx.get("artifact_carrier"), "source_ref")
        self.assertEqual(event_bodyfx.get("artifact_source_ref_ids"), [17])
        self.assertEqual(event_bodyfx.get("artifact_source_title"), "Persistence")
        self.assertEqual(event_bodyfx.get("artifact_source_tool_name"), "search_web")
        self.assertTrue(bool(event_bodyfx.get("requested_help")))
        self.assertIn("scheduled_life_due@scheduler", event_residue.get("preview_line") or "")
        self.assertIn("bodyfx=access_request_pending", event_residue.get("preview_line") or "")
        self.assertIn("source=Persistence", event_residue.get("preview_line") or "")
        self.assertIn("refs=17", event_residue.get("preview_line") or "")
        lifecycle = summary.get("agenda_lifecycle") if isinstance(summary.get("agenda_lifecycle"), dict) else {}
        self.assertEqual(lifecycle.get("kind"), "released_to_self_activity")
        self.assertEqual(lifecycle.get("carryover_mode"), "own_rhythm")
        self.assertEqual(lifecycle.get("carryover_strength"), 0.53)
        self.assertEqual(lifecycle.get("continuity_anchor"), 0.66)
        self.assertEqual(lifecycle.get("own_rhythm_anchor"), 0.72)
        self.assertEqual(lifecycle.get("semantic_continuity_depth"), 0.68)
        lifecycle_embodied = lifecycle.get("embodied_context") if isinstance(lifecycle.get("embodied_context"), dict) else {}
        self.assertEqual(lifecycle_embodied.get("kind"), "access_request_pending")
        self.assertEqual(lifecycle_embodied.get("requested_access"), ["workspace_write", "human_approval"])
        self.assertEqual(lifecycle_embodied.get("artifact_carrier"), "source_ref")
        self.assertEqual(lifecycle_embodied.get("artifact_source_ref_ids"), [17])
        self.assertEqual(lifecycle_embodied.get("artifact_source_title"), "Persistence")
        self.assertEqual(lifecycle_embodied.get("artifact_source_tool_name"), "search_web")
        self.assertTrue(bool(lifecycle_embodied.get("requested_help")))
        self.assertEqual(lifecycle.get("semantic_identity_gravity"), 0.64)
        self.assertEqual(lifecycle.get("lineage_gravity"), 0.7)
        self.assertEqual(lifecycle.get("repair_lineage"), 0.41)
        self.assertEqual(lifecycle.get("selfhood_lineage"), 0.69)
        self.assertEqual(lifecycle.get("agency_lineage"), 0.78)
        self.assertEqual(lifecycle.get("long_term_axis_count"), 4)
        self.assertEqual(lifecycle.get("recontact_cooldown"), 0.47)
        self.assertEqual(lifecycle.get("counterpart_scene_bias"), "busy_not_disrespectful")
        self.assertEqual(lifecycle.get("created_at"), 1710000099)
        self.assertIn("agenda_lifecycle", lifecycle.get("source_tags") or [])
        queue_preview = summary.get("behavior_queue_preview") if isinstance(summary.get("behavior_queue_preview"), list) else []
        self.assertEqual(len(queue_preview), 1)
        self.assertEqual(queue_preview[0].get("kind"), "deferred_checkin")
        self.assertEqual(queue_preview[0].get("relationship_weather"), "warm_residue")
        behavior_plan = summary.get("behavior_plan") if isinstance(summary.get("behavior_plan"), dict) else {}
        current_turn = summary.get("current_turn") if isinstance(summary.get("current_turn"), dict) else {}
        self.assertEqual(current_turn.get("channel"), "speech")
        self.assertEqual(current_turn.get("approach_style"), "guarded")
        self.assertEqual(current_turn.get("engagement_level"), 0.57)
        self.assertEqual(current_turn.get("initiative_level"), 0.43)
        self.assertEqual(current_turn.get("followup_intent"), "soft")
        self.assertEqual(current_turn.get("task_focus"), "relationship")
        self.assertEqual(current_turn.get("affect_surface"), "gentle")
        self.assertTrue(current_turn.get("silence_ok"))
        self.assertTrue(current_turn.get("silence_allowed"))
        self.assertFalse(current_turn.get("allow_interrupt"))
        self.assertEqual(current_turn.get("presence_family"), "deferred_return")
        self.assertEqual(current_turn.get("proactive_checkin_readiness"), 0.36)
        self.assertEqual(current_turn.get("deferred_action_family"), "life_window")
        self.assertEqual(current_turn.get("attention_target"), "counterpart_state")
        self.assertEqual(current_turn.get("nonverbal_signal"), "quiet_glance")
        self.assertEqual(current_turn.get("initiative_shape"), "micro_opening")
        self.assertEqual(current_turn.get("disclosure_posture"), "measured")
        self.assertEqual(current_turn.get("behavior_note"), "先不把窗口推进太满。")
        self.assertEqual(current_turn.get("timing_window_min"), 18)
        self.assertEqual(behavior_plan.get("presence_family"), "deferred_return")
        self.assertEqual(behavior_plan.get("interaction_mode"), "scheduled_life_nudge")
        self.assertEqual(behavior_plan.get("timing_window_min"), 18)
        self.assertTrue(behavior_plan.get("silence_allowed"))
        self.assertFalse(behavior_plan.get("allow_interrupt"))
        self.assertEqual(behavior_plan.get("relationship_weather"), "warm_residue")
        self.assertEqual(behavior_plan.get("attention_target"), "counterpart_state")
        self.assertEqual(behavior_plan.get("nonverbal_signal"), "quiet_glance")
        self.assertEqual(behavior_plan.get("note"), "窗口先留着，等更自然的时候再推进")
        self.assertEqual(behavior_plan.get("presence_residue"), 0.38)
        self.assertEqual(behavior_plan.get("ambient_resonance"), 0.27)
        self.assertEqual(behavior_plan.get("self_activity_momentum"), 0.49)
        self.assertEqual(behavior_plan.get("primary_motive"), "honor_continuity")
        self.assertEqual(behavior_plan.get("motive_tension"), "self_rhythm_vs_contact")
        line = build_evolution_summary_line(summary)
        self.assertIn("window=scheduled_window:0.520/0.580", line)
        self.assertIn("decision=wait_and_recheck", line)
        self.assertIn("recheck=18m", line)
        self.assertIn("lifecycle=released_to_self_activity:own_rhythm:0.530", line)
        self.assertIn("lifecyclefx=access_request_pending", line)

    def test_build_evolution_cli_summary_surfaces_event_identity_fields(self):
        summary = build_evolution_cli_summary(
            current_event={
                "kind": "idle",
                "source": "scheduler",
                "perception": {
                    "thread_id": "thread-a",
                    "turn_id": "thread-a:555",
                    "event_id": "thread-a:555:idle:scheduler",
                },
            }
        )

        event_residue = summary.get("event_residue") if isinstance(summary.get("event_residue"), dict) else {}
        self.assertEqual(event_residue.get("thread_id"), "thread-a")
        self.assertEqual(event_residue.get("turn_id"), "thread-a:555")
        self.assertEqual(event_residue.get("event_id"), "thread-a:555:idle:scheduler")

    def test_build_evolution_cli_summary_surfaces_carryover_embodied_context(self):
        summary = build_evolution_cli_summary(
            interaction_carryover={
                "source": "reconsolidation",
                "carryover_mode": "own_rhythm",
                "strength": 0.53,
                "relationship_weather": "warm_residue",
                "note": "前面的窗口还在慢慢往后带。",
                "embodied_context": {
                    "kind": "access_request_pending",
                    "summary": "她把动作推进到了审批门口。",
                    "requested_access": ["workspace_write"],
                    "requested_help": True,
                    "primary_status": "awaiting_approval",
                },
            }
        )

        carryover = summary.get("interaction_carryover") if isinstance(summary.get("interaction_carryover"), dict) else {}
        self.assertEqual(carryover.get("source"), "reconsolidation")
        self.assertEqual(carryover.get("carryover_mode"), "own_rhythm")
        self.assertEqual(carryover.get("strength"), 0.53)
        embodied = carryover.get("embodied_context") if isinstance(carryover.get("embodied_context"), dict) else {}
        self.assertEqual(embodied.get("kind"), "access_request_pending")
        self.assertEqual(embodied.get("requested_access"), ["workspace_write"])
        self.assertTrue(bool(embodied.get("requested_help")))

        line = build_evolution_summary_line(summary)
        self.assertIn("carryfx=access_request_pending", line)

    def test_build_evolution_cli_summary_surfaces_plan_and_consequence_embodied_context(self):
        summary = build_evolution_cli_summary(
            behavior_plan={
                "kind": "deferred_checkin",
                "target": "counterpart",
                "trigger_family": "observe",
                "note": "先把窗口留着。",
                "embodied_context": {
                    "kind": "access_request_pending",
                    "summary": "这一步还卡在审批门口。",
                    "requested_access": ["workspace_write"],
                    "requested_help": True,
                    "primary_status": "awaiting_approval",
                },
            },
            reconsolidation_snapshot={
                "behavior_consequence": {
                    "kind": "defer_recontact",
                    "summary": "这次先没有立刻往前接。",
                    "embodied_context": {
                        "kind": "environmental_friction",
                        "summary": "浏览器会话还没准备好。",
                        "missing_access": ["browser_session"],
                        "environmental_friction": True,
                    },
                }
            },
        )

        behavior_plan = summary.get("behavior_plan") if isinstance(summary.get("behavior_plan"), dict) else {}
        plan_embodied = behavior_plan.get("embodied_context") if isinstance(behavior_plan.get("embodied_context"), dict) else {}
        self.assertEqual(plan_embodied.get("kind"), "access_request_pending")
        self.assertEqual(plan_embodied.get("requested_access"), ["workspace_write"])

        consequence = summary.get("behavior_consequence") if isinstance(summary.get("behavior_consequence"), dict) else {}
        consequence_embodied = consequence.get("embodied_context") if isinstance(consequence.get("embodied_context"), dict) else {}
        self.assertEqual(consequence_embodied.get("kind"), "environmental_friction")
        self.assertEqual(consequence_embodied.get("missing_access"), ["browser_session"])

        current_turn = summary.get("current_turn") if isinstance(summary.get("current_turn"), dict) else {}
        current_consequence_embodied = (
            current_turn.get("behavior_consequence_embodied_context")
            if isinstance(current_turn.get("behavior_consequence_embodied_context"), dict)
            else {}
        )
        self.assertEqual(current_consequence_embodied.get("kind"), "environmental_friction")

        line = build_evolution_summary_line(summary)
        self.assertIn("planfx=access_request_pending", line)
        self.assertIn("consfx=environmental_friction", line)

    def test_build_evolution_cli_summary_surfaces_behavior_action_embodied_context(self):
        summary = build_evolution_cli_summary(
            behavior_action={
                "interaction_mode": "deferred_watch",
                "primary_motive": "honor_continuity",
                "embodied_context": {
                    "kind": "access_request_pending",
                    "summary": "她把这一步先推进到了审批门口。",
                    "requested_access": ["workspace_write", "human_approval"],
                    "requested_help": True,
                    "primary_status": "awaiting_approval",
                },
            }
        )

        current_turn = summary.get("current_turn") if isinstance(summary.get("current_turn"), dict) else {}
        action_embodied = (
            current_turn.get("behavior_action_embodied_context")
            if isinstance(current_turn.get("behavior_action_embodied_context"), dict)
            else {}
        )
        self.assertEqual(action_embodied.get("kind"), "access_request_pending")
        self.assertEqual(action_embodied.get("requested_access"), ["workspace_write", "human_approval"])
        self.assertTrue(bool(action_embodied.get("requested_help")))

        line = build_evolution_summary_line(summary)
        self.assertIn("actfx=access_request_pending", line)

    def test_build_evolution_cli_summary_surfaces_event_created_at_and_tags(self):
        summary = build_evolution_cli_summary(
            current_event={
                "kind": "time_idle",
                "created_at": 1710000100,
                "tags": ["quiet_presence", "relationship", ""],
            }
        )

        event_residue = summary.get("event_residue") if isinstance(summary.get("event_residue"), dict) else {}
        self.assertEqual(event_residue.get("created_at"), 1710000100)
        self.assertEqual(event_residue.get("tags"), ["quiet_presence", "relationship"])

    def test_build_evolution_cli_summary_surfaces_event_routing_and_appraisal_fields(self):
        summary = build_evolution_cli_summary(
            current_event={
                "kind": "user_utterance",
                "response_style_hint": "structured",
                "science_mode": True,
                "continuation_mode": False,
                "counterpart_name": "冈部伦太郎",
                "appraisal_label": "focused",
                "appraisal_confidence": 0.77,
                "attention_target_hint": "self_rhythm",
                "nonverbal_signal_hint": "pause",
            }
        )

        event_residue = summary.get("event_residue") if isinstance(summary.get("event_residue"), dict) else {}
        self.assertEqual(event_residue.get("response_style_hint"), "structured")
        self.assertTrue(event_residue.get("science_mode"))
        self.assertFalse(event_residue.get("continuation_mode"))
        self.assertEqual(event_residue.get("counterpart_name"), "冈部伦太郎")
        self.assertEqual(event_residue.get("appraisal_label"), "focused")
        self.assertEqual(event_residue.get("appraisal_confidence"), 0.77)
        self.assertEqual(event_residue.get("attention_target_hint"), "self_rhythm")
        self.assertEqual(event_residue.get("nonverbal_signal_hint"), "pause")

    def test_render_behavior_queue_cli_text_is_readable(self):
        queue = [
            {
                "agenda_id": "abc123",
                "kind": "deferred_checkin",
                "target": "counterpart",
                "status": "pending",
                "trigger_family": "life_window",
                "scheduled_after_min": 18,
                "expires_after_min": 180,
                "priority": 0.58,
                "base_priority": 0.52,
                "hold_count": 2,
                "allow_interrupt": False,
                "primary_motive": "honor_continuity",
                "motive_tension": "self_rhythm_vs_contact",
                "goal_frame": "先把前面那点生活上的惦记轻轻接回来。",
                "source_event_kind": "scheduled_life_due",
                "created_at": 1710000018,
                "carryover_mode": "small_opening",
                "carryover_strength": 0.44,
                "relationship_weather": "warm_residue",
                "presence_residue": 0.38,
                "ambient_resonance": 0.27,
                "self_activity_momentum": 0.49,
                "attention_target": "counterpart_state",
                "continuity_anchor": 0.61,
                "own_rhythm_anchor": 0.72,
                "recontact_anchor": 0.38,
                "boundary_anchor": 0.27,
                "memory_anchor": 0.33,
                "semantic_continuity_depth": 0.68,
                "semantic_identity_gravity": 0.64,
                "lineage_gravity": 0.74,
                "contact_lineage": 0.51,
                "repair_lineage": 0.29,
                "boundary_lineage": 0.36,
                "selfhood_lineage": 0.63,
                "agency_lineage": 0.77,
                "long_term_axis_count": 4,
                "note": "窗口先留着，等更自然的时候再推进",
            }
        ]
        rows = build_behavior_queue_cli_summary(queue)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].get("hold_count"), 2)
        self.assertFalse(rows[0].get("allow_interrupt"))
        self.assertEqual(rows[0].get("primary_motive"), "honor_continuity")
        self.assertEqual(rows[0].get("motive_tension"), "self_rhythm_vs_contact")
        self.assertEqual(rows[0].get("goal_frame"), "先把前面那点生活上的惦记轻轻接回来。")
        self.assertEqual(rows[0].get("source_event_kind"), "scheduled_life_due")
        self.assertEqual(rows[0].get("created_at"), 1710000018)
        self.assertEqual(rows[0].get("continuity_anchor"), 0.61)
        self.assertEqual(rows[0].get("semantic_identity_gravity"), 0.64)
        self.assertEqual(rows[0].get("lineage_gravity"), 0.74)
        self.assertEqual(rows[0].get("agency_lineage"), 0.77)
        self.assertEqual(rows[0].get("long_term_axis_count"), 4)
        rendered = render_behavior_queue_cli_text(queue)
        self.assertIn("#1 deferred_checkin/life_window", rendered)
        self.assertIn("holds=2", rendered)
        self.assertIn("carry=small_opening:0.440", rendered)
        self.assertIn("weather=warm_residue", rendered)
        self.assertIn("event=scheduled_life_due", rendered)
        self.assertIn("interrupt=no", rendered)
        self.assertIn("motive=honor_continuity / self_rhythm_vs_contact", rendered)
        self.assertIn("goal=先把前面那点生活上的惦记轻轻接回来。", rendered)
        self.assertIn("anchors=0.61/0.72/0.38/0.27/0.33", rendered)
        self.assertIn("semantic=0.68/0.64", rendered)
        self.assertIn("lineage=0.74/0.51/0.29/0.36/0.63/0.77 axes=4", rendered)
        self.assertIn("note=窗口先留着", rendered)


if __name__ == "__main__":
    unittest.main()
