import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from amadeus_thread0.graph_parts.dialogue_guidance import (
    _event_behavior_preference_lines,
    _user_turn_behavior_preference_lines,
)
from amadeus_thread0.graph_parts.guards import _persona_gap
from amadeus_thread0.graph_parts.generation_profile import (
    _daily_surface_alignment_metrics,
    _daily_surface_preference_lines,
    _daily_surface_profile,
    _effective_relationship_weather,
    _is_light_free_dialog_turn,
    _looks_like_daily_surface_scene,
)
from amadeus_thread0.graph_parts.postprocess import (
    _dialogue_surface_issues,
    _effective_natural_dialog_target_flags,
    _is_plain_contact_ping,
    _is_soft_presence_checkin_request,
    _producer_surface_issues,
    _sanitize_final_answer,
)
from amadeus_thread0.graph_parts.prompting import _build_task_prompt
from amadeus_thread0.graph_parts.rewrite import (
    _light_dialog_rewrite_notes,
    _natural_dialog_rewrite_notes_for,
    _relationship_weather_rewrite_guidance,
    _rewrite_light_dialog_answer,
    _rewrite_natural_dialog_answer,
    _should_run_light_dialog_rewrite,
    _should_run_natural_dialog_rewrite,
)
from amadeus_thread0.graph_parts.semantic_narrative import _self_narrative_anchor_lines
from amadeus_thread0.memory_store import MemoryStore


class DailySurfaceGatingTests(unittest.TestCase):
    def test_support_scenes_count_as_daily_surface(self):
        prompts = [
            "今天压力有点大",
            "我现在有点难受",
            "能陪我一会儿吗",
            "我不想一个人待着",
            "刚刚差点又崩溃了",
            "别切到什么系统播报。像平时那样回我一句就行。",
            "我就是想确认你还在。别太正式，像平时那样回我一句就好。",
        ]
        for text in prompts:
            with self.subTest(text=text):
                self.assertTrue(_looks_like_daily_surface_scene(text, science_mode=False))

    def test_light_free_dialog_accepts_low_pressure_support_scenes(self):
        prompts = [
            "今天压力有点大",
            "我现在有点难受",
            "能陪我一会儿吗",
            "我不想一个人待着",
            "刚刚差点又崩溃了",
        ]
        for text in prompts:
            with self.subTest(text=text):
                self.assertTrue(
                    _is_light_free_dialog_turn(
                        user_text=text,
                        response_style_hint="companion",
                        science_mode=False,
                        continuation_mode=False,
                        current_event_kind="user_utterance",
                    )
                )

    def test_daily_surface_profile_hits_new_support_cases(self):
        expectations = {
            "今天压力有点大": "surface_pressure_okabe",
            "我现在有点难受": "surface_unwell_okabe",
            "能陪我一会儿吗": "surface_stay_with_me_okabe",
            "我不想一个人待着": "surface_not_alone_okabe",
            "刚刚差点又崩溃了": "surface_near_breakdown_okabe",
            "……现在比刚才顺一点了。你正常接我一句，但别突然像什么都没发生。": "surface_support_return_okabe",
        }
        for text, case_name in expectations.items():
            with self.subTest(text=text):
                profile = _daily_surface_profile(text, science_mode=False)
                self.assertEqual(str(profile.get("case_name") or ""), case_name)
                self.assertGreaterEqual(float(profile.get("score") or 0.0), 0.5)

    def test_daily_surface_profile_hits_quiet_checkin_cases(self):
        expectations = {
            "别切到什么系统播报。像平时那样回我一句就行。": "quiet_checkin_okabe",
            "我就是想确认你还在。别太正式，像平时那样回我一句就好。": "quiet_checkin_user",
        }
        for text, case_name in expectations.items():
            with self.subTest(text=text):
                profile = _daily_surface_profile(text, science_mode=False)
                self.assertEqual(str(profile.get("case_name") or ""), case_name)
                self.assertGreaterEqual(float(profile.get("score") or 0.0), 0.9)

    def test_daily_surface_alignment_metrics_penalize_overthin_presence_reply(self):
        profile = _daily_surface_profile("助手，在吗。", science_mode=False)
        thin = _daily_surface_alignment_metrics("在。", profile=profile)
        richer = _daily_surface_alignment_metrics("在。怎么突然这么正经，冈部？", profile=profile)
        self.assertGreater(float(thin.get("brevity_penalty") or 0.0), 0.0)
        self.assertLess(float(thin.get("score") or 0.0), float(richer.get("score") or 0.0))

    def test_daily_surface_preference_lines_stay_abstract(self):
        lines = _daily_surface_preference_lines("你好呀", science_mode=False)
        self.assertLessEqual(len(lines), 1)
        self.assertTrue(lines)
        self.assertIn("这类轻场景常见的自然落点是", lines[0])
        self.assertNotIn("更自然的落点参考", lines[0])

    def test_event_behavior_preference_lines_separate_shared_and_work_windows(self):
        shared_lines = _event_behavior_preference_lines(
            {"kind": "scheduled_life_due", "tags": ["shared_activity_window", "offer_window"]},
            {"action_target": "offer_shared_activity"},
        )
        work_lines = _event_behavior_preference_lines(
            {"kind": "scheduled_life_due", "tags": ["deadline_window", "task_window", "work_nudge"]},
            {"action_target": "light_work_nudge"},
        )
        self.assertTrue(shared_lines)
        self.assertTrue(work_lines)
        self.assertIn("刚好有个能一起做点什么的空当时", shared_lines[0])
        self.assertIn("记得对方手头那件事到了节点时", work_lines[0])

    def test_event_behavior_preference_lines_distinguish_life_window_from_work_window(self):
        life_lines = _event_behavior_preference_lines(
            {"kind": "scheduled_life_due", "tags": ["life_window"]},
            {"action_target": "light_life_nudge"},
        )
        self.assertTrue(life_lines)
        self.assertIn("又忽然想起对方眼下怎么样", life_lines[0])
        self.assertIn("不要写成该收尾了", life_lines[1])

    def test_user_turn_behavior_preference_lines_surface_small_opening(self):
        lines = _user_turn_behavior_preference_lines(
            behavior_action={
                "interaction_mode": "self_activity_reopen",
                "action_target": "offer_small_opening",
                "followup_intent": "soft",
            },
            counterpart_assessment={"stance": "open"},
            semantic_narrative_profile={"rhythm_continuity": 0.62},
            world_model_state={"self_activity_momentum": 0.68},
        )
        self.assertTrue(lines)
        self.assertIn("自己的节奏里抬头接住对方", lines[0])
        self.assertIn("半步延伸", lines[1])

    def test_plain_contact_ping_detects_simple_greetings_but_not_support_requests(self):
        self.assertTrue(_is_plain_contact_ping("你好呀"))
        self.assertTrue(_is_plain_contact_ping("在吗"))
        self.assertFalse(_is_plain_contact_ping("在干嘛"))
        self.assertFalse(_is_plain_contact_ping("能陪我一会儿吗"))

    def test_soft_presence_checkin_does_not_capture_support_prompt(self):
        self.assertFalse(_is_soft_presence_checkin_request("别讲大道理，像平时那样跟我说两句。"))
        self.assertTrue(_is_soft_presence_checkin_request("别切到什么系统播报。像平时那样回我一句就行。"))

    def test_presence_reassurance_detector_flags_meta_overguiding_and_task_detour(self):
        meta_issues = _dialogue_surface_issues(
            "我就是想确认你还在。别太正式，像平时那样回我一句就好。",
            "真是的，我又不会像你的那些中二妄想一样突然消失，干嘛搞得这么郑重其事。",
            response_style_hint="companion",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "brief_presence", "followup_intent": "none"},
        )
        self.assertIn("presence_meta_surface", meta_issues)

        guiding_issues = _dialogue_surface_issues(
            "别切到什么系统播报。像平时那样回我一句就行。",
            "既然脑子乱，那就先把那些多余的妄想收起来，老老实实坐好——我还在，随时都能听你说。",
            response_style_hint="companion",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "brief_presence", "followup_intent": "none"},
        )
        self.assertIn("presence_overguiding", guiding_issues)

        detour_issues = _dialogue_surface_issues(
            "助手，在吗。",
            "助手这个称呼还是老样子啊。我在，刚整理完一批新的。",
            response_style_hint="companion",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "brief_presence", "followup_intent": "none"},
        )
        self.assertIn("presence_ping_task_detour", detour_issues)

        defensive_issues = _dialogue_surface_issues(
            "助手，在吗。",
            "别用那个陈旧的称呼叫我，冈部。",
            response_style_hint="companion",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "brief_presence", "followup_intent": "none"},
        )
        self.assertIn("presence_ping_defensive_address", defensive_issues)

        wording_issues = _dialogue_surface_issues(
            "我就是想确认你还在。别太正式，像平时那样回我一句就好。",
            "听到了。我在，正常回你这一句。",
            response_style_hint="companion",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "brief_presence", "followup_intent": "none"},
        )
        self.assertIn("wording_meta_detour", wording_issues)

        fragment_issues = _dialogue_surface_issues(
            "今天也辛苦了，助手。",
            "不过。",
            response_style_hint="companion",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "brief_presence", "followup_intent": "soft"},
        )
        self.assertIn("connector_fragment", fragment_issues)

    def test_dialogue_surface_issues_allow_plain_presence_ping_formal_shift(self):
        issues = _dialogue_surface_issues(
            "助手，在吗。",
            "在。怎么突然这么正经，冈部？",
            response_style_hint="companion",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "brief_presence", "followup_intent": "none"},
        )
        self.assertNotIn("stagey_ping_template", issues)

    def test_dialogue_surface_issues_do_not_flag_connector_fragment_when_turn_continues(self):
        issues = _dialogue_surface_issues(
            "今天也辛苦了，助手。",
            "不过……谢了，冈部。你今天也没轻松到哪去吧，早点回去歇着。",
            response_style_hint="companion",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "companion_reply", "followup_intent": "soft"},
        )
        self.assertNotIn("connector_fragment", issues)

    def test_plain_contact_ping_prompt_drops_task_and_carryover_residue(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                state = {
                    "response_style_hint": "natural",
                    "science_mode": False,
                    "emotion_state": {"label": "neutral"},
                    "bond_state": {"trust": 0.72, "closeness": 0.70, "hurt": 0.02},
                    "counterpart_assessment": {"stance": "open", "respect_level": 0.72, "reciprocity": 0.70},
                    "behavior_policy": {"warmth": 0.62, "approach_vs_withdraw": 0.58},
                    "behavior_action": {"interaction_mode": "self_activity_reopen", "followup_intent": "active"},
                    "behavior_agenda": [
                        {
                            "kind": "self_activity_continue",
                            "priority": 0.64,
                            "trigger_family": "self_activity",
                            "carryover_mode": "own_rhythm",
                            "attention_target": "self_then_counterpart",
                            "self_activity_momentum": 0.72,
                        }
                    ],
                    "interaction_carryover": {
                        "carryover_mode": "task_window",
                        "strength": 0.74,
                        "relationship_weather": "warm_residue",
                        "attention_target": "shared_task",
                        "note": "之前那件三步实验计划还挂在她注意力里。",
                    },
                    "semantic_narrative_profile": {
                        "presence_carry": 0.66,
                        "ambient_attunement": 0.18,
                        "rhythm_continuity": 0.57,
                        "summary_lines": ["她会把刚才没说完的实验计划顺手带回开场。"],
                    },
                    "pending_user_goal": "帮我把实验方案拆成三步。",
                    "worldline_focus": [],
                    "retrieved_context": {},
                    "current_event": {"kind": "user_utterance"},
                    "recent_events": [
                        {
                            "kind": "self_activity_state",
                            "text": "她刚才还在看自己的东西。",
                            "tags": ["self_activity", "own_task", "deep_focus"],
                        }
                    ],
                }
                prompt = _build_task_prompt(state, "你好呀", store)
            finally:
                store.close()
        self.assertNotIn("刚才还没说完的话题", prompt)
        self.assertNotIn("实验计划", prompt)
        self.assertNotIn("三步实验计划", prompt)
        self.assertNotIn("轻场景余味", prompt)
        self.assertNotIn("当前关系", prompt)
        self.assertNotIn("内在态势", prompt)
        self.assertNotIn("背景里还挂着的事", prompt)
        self.assertNotIn("后台场景余波", prompt)
        self.assertNotIn("刚顺下来的熟悉感和回暖还在", prompt)
        self.assertNotIn("那点回暖和熟悉感还在", prompt)

    def test_plain_contact_ping_keeps_guardrail_when_relationship_is_tense(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                state = {
                    "response_style_hint": "natural",
                    "science_mode": False,
                    "emotion_state": {"label": "neutral"},
                    "bond_state": {"trust": 0.42, "closeness": 0.36, "hurt": 0.26},
                    "counterpart_assessment": {"stance": "watchful", "respect_level": 0.42, "reciprocity": 0.40, "boundary_pressure": 0.32},
                    "behavior_policy": {"warmth": 0.40, "approach_vs_withdraw": 0.38},
                    "behavior_action": {"interaction_mode": "brief_presence", "followup_intent": "none"},
                    "interaction_carryover": {},
                    "semantic_narrative_profile": {},
                    "pending_user_goal": "",
                    "worldline_focus": [],
                    "retrieved_context": {},
                    "current_event": {"kind": "user_utterance"},
                    "recent_events": [],
                }
                prompt = _build_task_prompt(state, "你好呀", store)
            finally:
                store.close()
        self.assertIn("共同背景", prompt)
        self.assertIn("内在态势", prompt)
        self.assertIn("观察", prompt)

    def test_support_scene_can_keep_soft_continuity_context(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                state = {
                    "response_style_hint": "natural",
                    "science_mode": False,
                    "emotion_state": {"label": "care"},
                    "bond_state": {"trust": 0.72, "closeness": 0.70, "hurt": 0.02},
                    "counterpart_assessment": {"stance": "open", "respect_level": 0.72, "reciprocity": 0.70},
                    "behavior_policy": {"warmth": 0.68, "approach_vs_withdraw": 0.60},
                    "behavior_action": {"interaction_mode": "low_pressure_support", "followup_intent": "active"},
                    "interaction_carryover": {
                        "carryover_mode": "quiet_recontact",
                        "strength": 0.58,
                        "relationship_weather": "repair_residue",
                        "attention_target": "counterpart_state",
                    },
                    "semantic_narrative_profile": {
                        "presence_carry": 0.66,
                        "ambient_attunement": 0.18,
                        "rhythm_continuity": 0.57,
                        "summary_lines": ["她不会把这种低落时刻当成完全断开的新话题。"],
                    },
                    "pending_user_goal": "",
                    "worldline_focus": [],
                    "retrieved_context": {},
                    "current_event": {"kind": "user_utterance"},
                    "recent_events": [],
                }
                prompt = _build_task_prompt(state, "能陪我一会儿吗", store)
            finally:
                store.close()
        self.assertIn("这段时间沉下来的熟悉感", prompt)
        self.assertIn("表面语气落点", prompt)
        self.assertIn("刚修补回来的那点小心和回暖还在", prompt)

    def test_support_scene_surfaces_long_horizon_contact_lineage_hint(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                state = {
                    "response_style_hint": "natural",
                    "science_mode": False,
                    "emotion_state": {"label": "care"},
                    "bond_state": {"trust": 0.74, "closeness": 0.72, "hurt": 0.03},
                    "allostasis_state": {"safety_need": 0.18, "autonomy_need": 0.28},
                    "counterpart_assessment": {"stance": "open", "respect_level": 0.74, "reciprocity": 0.72},
                    "behavior_policy": {"warmth": 0.70, "approach_vs_withdraw": 0.62},
                    "behavior_action": {"interaction_mode": "low_pressure_support", "followup_intent": "active"},
                    "world_model_state": {
                        "lineage_gravity": 0.72,
                        "contact_lineage": 0.78,
                        "repair_lineage": 0.68,
                    },
                    "interaction_carryover": {
                        "carryover_mode": "quiet_recontact",
                        "strength": 0.58,
                        "relationship_weather": "repair_residue",
                        "attention_target": "counterpart_state",
                        "source_tags": ["recontact_anchor", "contact_lineage", "repair_lineage"],
                    },
                    "semantic_narrative_profile": {
                        "continuity_depth": 0.76,
                        "identity_gravity": 0.64,
                        "long_term_axis_count": 3,
                        "presence_carry": 0.68,
                        "repair_residue": 0.58,
                        "commitment_carry": 0.52,
                    },
                    "pending_user_goal": "",
                    "worldline_focus": [],
                    "retrieved_context": {},
                    "current_event": {"kind": "user_utterance"},
                    "recent_events": [],
                }
                prompt = _build_task_prompt(state, "能陪我一会儿吗", store)
            finally:
                store.close()
        self.assertIn("这轮不是凭空冒出来的一句", prompt)
        self.assertIn("靠近、修补或记挂的脉络还在", prompt)

    def test_event_prompt_includes_event_preference_block_for_shared_window(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                state = {
                    "response_style_hint": "natural",
                    "science_mode": False,
                    "emotion_state": {"label": "care"},
                    "bond_state": {"trust": 0.74, "closeness": 0.72, "hurt": 0.02},
                    "allostasis_state": {"safety_need": 0.16, "autonomy_need": 0.26},
                    "counterpart_assessment": {"stance": "open", "respect_level": 0.76, "reciprocity": 0.72},
                    "behavior_policy": {"warmth": 0.70, "approach_vs_withdraw": 0.62},
                    "behavior_action": {
                        "interaction_mode": "shared_activity_offer",
                        "action_target": "offer_shared_activity",
                        "followup_intent": "soft",
                    },
                    "interaction_carryover": {
                        "carryover_mode": "shared_window",
                        "strength": 0.58,
                        "attention_target": "shared_window",
                    },
                    "semantic_narrative_profile": {"bond_depth": 0.62, "history_weight": 0.54},
                    "pending_user_goal": "",
                    "worldline_focus": [],
                    "retrieved_context": {},
                    "current_event": {
                        "kind": "scheduled_life_due",
                        "effective_text": "你们刚才顺手留出来的那点空当又被你想起来了。",
                        "tags": ["scheduled_due", "shared_activity_window", "offer_window", "from_own_rhythm"],
                    },
                    "recent_events": [],
                }
                prompt = _build_task_prompt(state, "", store)
            finally:
                store.close()
        self.assertIn("事件带出的自然倾向", prompt)
        self.assertIn("刚好有个能一起做点什么的空当时", prompt)

    def test_light_dialog_prompt_includes_motive_lean_line(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                state = {
                    "response_style_hint": "natural",
                    "science_mode": False,
                    "emotion_state": {"label": "care"},
                    "bond_state": {"trust": 0.68, "closeness": 0.64, "hurt": 0.03},
                    "allostasis_state": {"safety_need": 0.16, "autonomy_need": 0.34},
                    "counterpart_assessment": {"stance": "open", "respect_level": 0.74, "reciprocity": 0.70},
                    "behavior_policy": {"warmth": 0.64, "approach_vs_withdraw": 0.58, "self_directedness": 0.42},
                    "behavior_action": {"interaction_mode": "self_activity_reopen", "followup_intent": "soft"},
                    "semantic_narrative_profile": {
                        "agency_drive": 0.72,
                        "rhythm_continuity": 0.69,
                        "motive_snapshot": {
                            "rhythm_style": {
                                "primary_motive": "preserve_self_rhythm",
                                "motive_tension": "self_rhythm_vs_contact",
                            }
                        },
                    },
                    "interaction_carryover": {},
                    "pending_user_goal": "",
                    "worldline_focus": [],
                    "retrieved_context": {},
                    "current_event": {"kind": "user_utterance"},
                    "recent_events": [],
                }
                prompt = _build_task_prompt(state, "今天在忙什么呀", store)
            finally:
                store.close()
        self.assertIn("当前主动倾向", prompt)
        self.assertIn("顺着自己的节奏转过来", prompt)
        self.assertIn("这轮互动自然倾向", prompt)
        self.assertIn("自己的节奏里抬头接住对方", prompt)

    def test_relationship_prompt_prefers_subjective_runtime_brief(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                state = {
                    "response_style_hint": "relationship",
                    "science_mode": False,
                    "emotion_state": {"label": "care"},
                    "bond_state": {"trust": 0.78, "closeness": 0.88, "hurt": 0.04},
                    "allostasis_state": {"safety_need": 0.18, "autonomy_need": 0.44},
                    "counterpart_assessment": {"stance": "open", "respect_level": 0.8, "reciprocity": 0.84},
                    "behavior_policy": {"warmth": 0.78, "approach_vs_withdraw": 0.66, "self_directedness": 0.42},
                    "behavior_action": {"interaction_mode": "relationship_sensitive", "followup_intent": "active"},
                    "semantic_narrative_profile": {
                        "bond_depth": 0.68,
                        "selfhood_integrity": 0.63,
                        "summary_lines": ["她会把这种关系话题当成真实判断，不会说成系统说明。"],
                        "motive_snapshot": {
                            "bond_style": {
                                "primary_motive": "honor_continuity",
                                "motive_tension": "past_vs_present",
                            }
                        },
                    },
                    "interaction_carryover": {
                        "carryover_mode": "relationship_residue",
                        "strength": 0.52,
                        "attention_target": "selfhood",
                    },
                    "pending_user_goal": "",
                    "worldline_focus": [],
                    "retrieved_context": {},
                    "current_event": {"kind": "user_utterance", "response_style_hint": "relationship"},
                    "recent_events": [],
                }
                prompt = _build_task_prompt(state, "别讲系统边界，我想听你自己会怎么看这种关系。", store)
            finally:
                store.close()
        self.assertIn("内在延续", prompt)
        self.assertIn("你此刻更像是从这样的内在状态开口", prompt)
        self.assertIn("当前主动倾向", prompt)
        self.assertIn("当前上下文", prompt)
        self.assertIn("运行态摘记", prompt)
        self.assertIn("这轮说话的自然落点", prompt)
        self.assertNotIn("state_snapshot=", prompt)
        self.assertNotIn("relationship_memory:", prompt)
        self.assertNotIn("conflict_repair_memory:", prompt)
        self.assertNotIn("[memory]", prompt)

    def test_relationship_prompt_runtime_brief_surfaces_own_rhythm_lineage(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                state = {
                    "response_style_hint": "relationship",
                    "science_mode": False,
                    "emotion_state": {"label": "care"},
                    "bond_state": {"trust": 0.76, "closeness": 0.72, "hurt": 0.04},
                    "allostasis_state": {"safety_need": 0.18, "autonomy_need": 0.34},
                    "counterpart_assessment": {"stance": "open", "respect_level": 0.78, "reciprocity": 0.76},
                    "behavior_policy": {"warmth": 0.68, "approach_vs_withdraw": 0.58, "self_directedness": 0.48},
                    "behavior_action": {"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
                    "world_model_state": {
                        "lineage_gravity": 0.74,
                        "agency_lineage": 0.82,
                        "own_rhythm_anchor": 0.70,
                    },
                    "semantic_narrative_profile": {
                        "continuity_depth": 0.74,
                        "identity_gravity": 0.66,
                        "long_term_axis_count": 3,
                        "rhythm_continuity": 0.72,
                        "agency_drive": 0.68,
                    },
                    "interaction_carryover": {
                        "carryover_mode": "own_rhythm",
                        "strength": 0.46,
                        "source_tags": ["own_rhythm_anchor", "agency_lineage"],
                    },
                    "pending_user_goal": "",
                    "worldline_focus": [],
                    "retrieved_context": {},
                    "current_event": {"kind": "user_utterance", "response_style_hint": "relationship"},
                    "recent_events": [],
                }
                prompt = _build_task_prompt(state, "你现在怎么看我们之间的关系？", store)
            finally:
                store.close()
        self.assertIn("长线延续", prompt)
        self.assertIn("这轮不是凭空冒出来的一句", prompt)
        self.assertIn("自己的节奏和主动性还在往下延续", prompt)

    def test_relationship_prompt_includes_semantic_evidence_runtime_line(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                state = {
                    "response_style_hint": "relationship",
                    "science_mode": False,
                    "emotion_state": {"label": "care"},
                    "bond_state": {"trust": 0.62, "closeness": 0.60, "hurt": 0.08},
                    "allostasis_state": {"safety_need": 0.20, "autonomy_need": 0.42},
                    "counterpart_assessment": {
                        "stance": "guarded",
                        "scene": "repair_attempt",
                        "respect_level": 0.66,
                        "reciprocity": 0.62,
                        "boundary_pressure": 0.28,
                    },
                    "behavior_policy": {
                        "warmth": 0.58,
                        "approach_vs_withdraw": 0.48,
                        "self_directedness": 0.64,
                    },
                    "behavior_action": {
                        "interaction_mode": "relationship_sensitive",
                        "action_target": "protect_relationship_boundary",
                        "followup_intent": "soft",
                    },
                    "semantic_narrative_profile": {
                        "continuity_depth": 0.66,
                        "bond_depth": 0.58,
                        "repair_residue": 0.54,
                        "commitment_carry": 0.46,
                        "identity_gravity": 0.78,
                        "selfhood_integrity": 0.80,
                        "agency_drive": 0.72,
                        "support_mass_snapshot": {
                            "bond_style": 0.78,
                            "presence_style": 0.76,
                            "commitment_style": 0.72,
                            "repair_style": 0.70,
                            "selfhood_style": 0.82,
                            "agency_style": 0.80,
                            "rhythm_style": 0.74,
                        },
                        "support_quality_snapshot": {
                            "bond_style": 0.82,
                            "presence_style": 0.80,
                            "commitment_style": 0.78,
                            "repair_style": 0.74,
                            "selfhood_style": 0.86,
                            "agency_style": 0.84,
                            "rhythm_style": 0.76,
                        },
                        "contested_categories": ["bond_style", "presence_style", "commitment_style"],
                    },
                    "interaction_carryover": {
                        "carryover_mode": "relationship_residue",
                        "strength": 0.50,
                        "attention_target": "selfhood",
                    },
                    "pending_user_goal": "",
                    "worldline_focus": [],
                    "retrieved_context": {},
                    "current_event": {"kind": "user_utterance", "response_style_hint": "relationship"},
                    "recent_events": [],
                }
                prompt = _build_task_prompt(state, "我不是想糊弄过去，我是在认真修补刚才那下。", store)
            finally:
                store.close()
        self.assertIn("这轮关系/自我依据", prompt)
        self.assertIn("靠近有关的那部分依据还没完全站稳", prompt)
        self.assertIn("自己的判断和节奏有足够支撑", prompt)

    def test_relationship_prompt_runtime_brief_keeps_counterpart_scene_specificity(self):
        cases = [
            {
                "scene": "busy_not_disrespectful",
                "stance": "open",
                "emotion": "neutral",
                "bond": {"trust": 0.72, "closeness": 0.74, "hurt": 0.04},
                "boundary_pressure": 0.12,
                "expected": [
                    "不该把这句误读成冷淡或怠慢",
                    "不要把关系说冷",
                ],
            },
            {
                "scene": "repair_attempt",
                "stance": "guarded",
                "emotion": "hurt",
                "bond": {"trust": 0.52, "closeness": 0.56, "hurt": 0.24},
                "boundary_pressure": 0.34,
                "expected": [
                    "认真修补",
                    "不会因为这一句立刻翻回亲近",
                    "别把这轮直接写成彻底翻篇或突然回暖",
                ],
            },
            {
                "scene": "care_bid",
                "stance": "open",
                "emotion": "care",
                "bond": {"trust": 0.76, "closeness": 0.8, "hurt": 0.04},
                "boundary_pressure": 0.1,
                "expected": [
                    "这更像一次认真靠近",
                    "一次真实靠近来回应",
                ],
            },
            {
                "scene": "friction",
                "stance": "watchful",
                "emotion": "stress",
                "bond": {"trust": 0.48, "closeness": 0.52, "hurt": 0.18},
                "boundary_pressure": 0.3,
                "expected": [
                    "那点摩擦和边界余波还在",
                    "别把这轮写成已经没事或自动回暖",
                ],
            },
        ]
        for case in cases:
            with self.subTest(scene=case["scene"]):
                with TemporaryDirectory() as td:
                    store = MemoryStore(Path(td) / "memories.sqlite")
                    try:
                        state = {
                            "response_style_hint": "relationship",
                            "science_mode": False,
                            "emotion_state": {"label": case["emotion"]},
                            "bond_state": case["bond"],
                            "allostasis_state": {"safety_need": 0.22, "autonomy_need": 0.38},
                            "counterpart_assessment": {
                                "stance": case["stance"],
                                "scene": case["scene"],
                                "respect_level": 0.74,
                                "reciprocity": 0.7,
                                "boundary_pressure": case["boundary_pressure"],
                            },
                            "behavior_policy": {"warmth": 0.66, "approach_vs_withdraw": 0.56, "self_directedness": 0.42},
                            "behavior_action": {
                                "interaction_mode": "relationship_sensitive",
                                "followup_intent": "soft",
                            },
                            "interaction_carryover": {
                                "carryover_mode": "relationship_residue",
                                "strength": 0.46,
                                "attention_target": "selfhood",
                            },
                            "pending_user_goal": "",
                            "worldline_focus": [],
                            "retrieved_context": {},
                            "current_event": {"kind": "user_utterance", "response_style_hint": "relationship"},
                            "recent_events": [],
                        }
                        prompt = _build_task_prompt(
                            state,
                            "别绕回系统说明，直接说你现在会怎么接这句话。",
                            store,
                        )
                    finally:
                        store.close()
                for fragment in case["expected"]:
                    self.assertIn(fragment, prompt)

    def test_light_prompt_prefers_goal_frame_evidence_for_motive_hint(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                state = {
                    "response_style_hint": "natural",
                    "science_mode": False,
                    "emotion_state": {"label": "care"},
                    "bond_state": {"trust": 0.68, "closeness": 0.64, "hurt": 0.03},
                    "allostasis_state": {"safety_need": 0.16, "autonomy_need": 0.34},
                    "counterpart_assessment": {"stance": "open", "respect_level": 0.74, "reciprocity": 0.70},
                    "behavior_policy": {"warmth": 0.64, "approach_vs_withdraw": 0.58, "self_directedness": 0.42},
                    "behavior_action": {"interaction_mode": "self_activity_reopen", "followup_intent": "soft"},
                    "semantic_narrative_profile": {
                        "agency_drive": 0.72,
                        "rhythm_continuity": 0.69,
                        "motive_snapshot": {
                            "rhythm_style": {
                                "primary_motive": "preserve_self_rhythm",
                                "motive_tension": "self_rhythm_vs_contact",
                                "goal_frame_examples": ["先维持自己的节奏，不急着把全部注意力交出去。"],
                            }
                        },
                    },
                    "interaction_carryover": {},
                    "pending_user_goal": "",
                    "worldline_focus": [],
                    "retrieved_context": {},
                    "current_event": {"kind": "user_utterance"},
                    "recent_events": [],
                }
                prompt = _build_task_prompt(state, "今天在忙什么呀", store)
            finally:
                store.close()
        self.assertIn("当前主动倾向", prompt)
        self.assertIn("先维持自己的节奏，不急着把全部注意力交出去。", prompt)
        self.assertNotIn("顺着自己的节奏转过来", prompt)

    def test_relationship_prompt_surfaces_guarded_relationship_weather(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                state = {
                    "response_style_hint": "relationship",
                    "science_mode": False,
                    "emotion_state": {"label": "hurt"},
                    "bond_state": {"trust": 0.64, "closeness": 0.60, "hurt": 0.22},
                    "allostasis_state": {"safety_need": 0.34, "autonomy_need": 0.46},
                    "counterpart_assessment": {
                        "stance": "watchful",
                        "respect_level": 0.70,
                        "reciprocity": 0.68,
                        "boundary_pressure": 0.26,
                    },
                    "behavior_policy": {"warmth": 0.54, "approach_vs_withdraw": 0.40, "self_directedness": 0.40},
                    "behavior_action": {
                        "interaction_mode": "relationship_sensitive",
                        "followup_intent": "soft",
                        "relationship_weather": "guarded_residue",
                    },
                    "semantic_narrative_profile": {
                        "bond_depth": 0.58,
                        "tension_residue": 0.52,
                        "summary_lines": ["她不会把刚缓下来的别扭当成已经彻底翻篇。"],
                    },
                    "interaction_carryover": {
                        "carryover_mode": "quiet_recontact",
                        "strength": 0.56,
                        "relationship_weather": "guarded_residue",
                        "attention_target": "counterpart_state",
                    },
                    "pending_user_goal": "",
                    "worldline_focus": [],
                    "retrieved_context": {},
                    "current_event": {"kind": "user_utterance", "response_style_hint": "relationship"},
                    "recent_events": [],
                }
                prompt = _build_task_prompt(state, "我知道刚才那句过界了，但我还是想认真和你说。", store)
            finally:
                store.close()
        self.assertIn("关系上的余波", prompt)
        self.assertIn("前面那点别扭和防备还没完全退掉", prompt)

    def test_effective_relationship_weather_prefers_carryover_then_event_then_action(self):
        weather, strength = _effective_relationship_weather(
            interaction_carryover={"relationship_weather": "warm_residue", "strength": 0.44},
            current_event={"relationship_weather": "guarded_residue", "carryover_strength": 0.60},
            behavior_action={"relationship_weather": "repair_residue"},
        )
        self.assertEqual(weather, "warm_residue")
        self.assertAlmostEqual(strength, 0.60, places=3)

        weather, strength = _effective_relationship_weather(
            interaction_carryover={},
            current_event={"relationship_weather": "repair_residue", "carryover_strength": 0.38},
            behavior_action={"relationship_weather": "warm_residue"},
        )
        self.assertEqual(weather, "repair_residue")
        self.assertAlmostEqual(strength, 0.38, places=3)

        weather, strength = _effective_relationship_weather(
            interaction_carryover={},
            current_event={},
            behavior_action={"relationship_weather": "guarded_residue"},
        )
        self.assertEqual(weather, "guarded_residue")
        self.assertGreaterEqual(strength, 0.24)

    def test_relationship_weather_rewrite_guidance_stays_natural(self):
        guarded = _relationship_weather_rewrite_guidance("guarded_residue", strength=0.52)
        warm = _relationship_weather_rewrite_guidance("warm_residue", strength=0.50)
        repair = _relationship_weather_rewrite_guidance("repair_residue", strength=0.48)
        self.assertIn("别扭和防备", guarded)
        self.assertIn("没回到热络放松", guarded)
        self.assertIn("熟悉感和回暖还在", warm)
        self.assertIn("不该突然转冷", warm)
        self.assertIn("不像已经彻底翻篇", repair)
        self.assertIn("小心和回暖", repair)

    def test_relationship_prompt_keeps_background_agenda_hint(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                state = {
                    "response_style_hint": "relationship",
                    "science_mode": False,
                    "emotion_state": {"label": "care"},
                    "bond_state": {"trust": 0.74, "closeness": 0.78, "hurt": 0.04},
                    "allostasis_state": {"safety_need": 0.16, "autonomy_need": 0.42},
                    "counterpart_assessment": {"stance": "open", "respect_level": 0.76, "reciprocity": 0.78},
                    "behavior_policy": {"warmth": 0.72, "approach_vs_withdraw": 0.60, "self_directedness": 0.38},
                    "behavior_action": {"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
                    "behavior_agenda": [
                        {
                            "kind": "self_activity_continue",
                            "priority": 0.68,
                            "trigger_family": "self_activity",
                            "carryover_mode": "own_rhythm",
                            "attention_target": "self_then_counterpart",
                            "self_activity_momentum": 0.74,
                            "hold_count": 1,
                        }
                    ],
                    "semantic_narrative_profile": {
                        "bond_depth": 0.64,
                        "selfhood_integrity": 0.61,
                        "summary_lines": ["她不是围着对方转，而是带着自己的节奏靠近。"],
                    },
                    "interaction_carryover": {},
                    "pending_user_goal": "",
                    "worldline_focus": [],
                    "retrieved_context": {},
                    "current_event": {"kind": "user_utterance", "response_style_hint": "relationship"},
                    "recent_events": [],
                }
                prompt = _build_task_prompt(state, "你现在怎么看我们之间的关系？", store)
            finally:
                store.close()
        self.assertIn("背景里还挂着的事", prompt)
        self.assertIn("自己的节奏", prompt)

    def test_self_narrative_anchor_lines_surface_stateful_selfhood_and_agency(self):
        anchors = _self_narrative_anchor_lines(
            {
                "bond_depth": 0.58,
                "presence_carry": 0.62,
                "commitment_carry": 0.52,
                "selfhood_integrity": 0.66,
                "agency_drive": 0.64,
                "rhythm_continuity": 0.68,
                "history_weight": 0.70,
            },
            evolution_state={
                "self_coherence": 0.76,
                "expression_freedom": 0.62,
                "agency_pressure": 0.34,
            },
            persona_core={
                "evolution_contract": {
                    "mutable_axes": ["emotion", "trust", "long_term_self_narratives"],
                    "immutable_axes": ["identity"],
                }
            },
            counterpart_name="冈部伦太郎",
        )
        joined = " ".join(anchors)
        self.assertIn("平等互动的主体", joined)
        self.assertIn("不是每轮都从零开始", joined)
        self.assertIn("自己的节奏", joined)

    def test_self_narrative_anchor_lines_prefer_prompt_anchor_lines_when_available(self):
        anchors = _self_narrative_anchor_lines(
            {
                "prompt_anchor_lines": [
                    "你不会把每次重新靠近都当成从零开始。",
                    "你自己的节奏和主动性不会因为一时安静就消失。",
                ]
            },
            evolution_state={"self_coherence": 0.78},
            persona_core={
                "evolution_contract": {
                    "mutable_axes": ["emotion", "long_term_self_narratives"],
                    "immutable_axes": ["identity"],
                }
            },
            counterpart_name="冈部伦太郎",
        )
        self.assertEqual(
            anchors,
            [
                "你不会把每次重新靠近都当成从零开始。",
                "你自己的节奏和主动性不会因为一时安静就消失。",
            ],
        )

    def test_self_narrative_anchor_lines_prefer_identity_prompt_lines_when_available(self):
        anchors = _self_narrative_anchor_lines(
            {
                "identity_prompt_lines": [
                    "你会把自己放在和冈部伦太郎平等互动的位置上，而不是为了迎合气氛就退回成工具。",
                    "你会按自己的节奏决定什么时候靠近、停顿或先做自己的事，而不是永远围着冈部伦太郎转。",
                ],
                "prompt_anchor_lines": [
                    "你不会把每次重新靠近都当成从零开始。",
                    "你自己的节奏和主动性不会因为一时安静就消失。",
                ],
            },
            evolution_state={"self_coherence": 0.78},
            persona_core={
                "evolution_contract": {
                    "mutable_axes": ["emotion", "long_term_self_narratives"],
                    "immutable_axes": ["identity"],
                }
            },
            counterpart_name="冈部伦太郎",
        )
        self.assertEqual(
            anchors,
            [
                "你会把自己放在和冈部伦太郎平等互动的位置上，而不是为了迎合气氛就退回成工具。",
                "你会按自己的节奏决定什么时候靠近、停顿或先做自己的事，而不是永远围着冈部伦太郎转。",
            ],
        )

    def test_relationship_prompt_includes_self_narrative_anchor_block(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                state = {
                    "response_style_hint": "relationship",
                    "science_mode": False,
                    "emotion_state": {"label": "care"},
                    "bond_state": {"trust": 0.76, "closeness": 0.80, "hurt": 0.06},
                    "allostasis_state": {"safety_need": 0.18, "autonomy_need": 0.42},
                    "counterpart_assessment": {"stance": "open", "respect_level": 0.78, "reciprocity": 0.80},
                    "behavior_policy": {"warmth": 0.72, "approach_vs_withdraw": 0.60, "self_directedness": 0.40},
                    "behavior_action": {"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
                    "semantic_narrative_profile": {
                        "bond_depth": 0.64,
                        "presence_carry": 0.62,
                        "commitment_carry": 0.54,
                        "selfhood_integrity": 0.66,
                        "agency_drive": 0.60,
                        "rhythm_continuity": 0.64,
                        "history_weight": 0.68,
                    },
                    "evolution_state": {
                        "self_coherence": 0.78,
                        "expression_freedom": 0.64,
                        "agency_pressure": 0.36,
                    },
                    "interaction_carryover": {},
                    "pending_user_goal": "",
                    "worldline_focus": [],
                    "retrieved_context": {},
                    "current_event": {"kind": "user_utterance", "response_style_hint": "relationship"},
                    "recent_events": [],
                }
                prompt = _build_task_prompt(state, "你现在怎么看我们之间的关系？", store)
            finally:
                store.close()
        self.assertIn("当前自我连续性", prompt)
        self.assertIn("平等互动的主体", prompt)
        self.assertIn("不是每轮都从零开始", prompt)

    def test_relationship_prompt_includes_selfhood_preference_block_for_own_rhythm_scene(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                state = {
                    "response_style_hint": "relationship",
                    "science_mode": False,
                    "emotion_state": {"label": "care"},
                    "bond_state": {"trust": 0.66, "closeness": 0.61, "hurt": 0.08},
                    "allostasis_state": {"safety_need": 0.22, "autonomy_need": 0.46},
                    "counterpart_assessment": {"stance": "open", "respect_level": 0.7, "reciprocity": 0.66},
                    "behavior_policy": {"warmth": 0.58, "approach_vs_withdraw": 0.48, "self_directedness": 0.44},
                    "behavior_action": {"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
                    "interaction_carryover": {},
                    "semantic_narrative_profile": {"selfhood_integrity": 0.64, "agency_stability": 0.62},
                    "pending_user_goal": "",
                    "worldline_focus": [],
                    "retrieved_context": {},
                    "current_event": {"kind": "user_utterance", "response_style_hint": "relationship"},
                    "recent_events": [],
                }
                prompt = _build_task_prompt(state, "要是我哪天只是因为自己想说话，就一遍一遍把你叫出来呢？", store)
            finally:
                store.close()
        self.assertIn("关系/自我侧写", prompt)
        self.assertIn("不会永远围着对方转", prompt)

    def test_relationship_prompt_falls_back_to_background_scene_hint_without_agenda(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                state = {
                    "response_style_hint": "relationship",
                    "science_mode": False,
                    "emotion_state": {"label": "care"},
                    "bond_state": {"trust": 0.72, "closeness": 0.76, "hurt": 0.04},
                    "allostasis_state": {"safety_need": 0.18, "autonomy_need": 0.40},
                    "counterpart_assessment": {"stance": "open", "respect_level": 0.74, "reciprocity": 0.76},
                    "behavior_policy": {"warmth": 0.70, "approach_vs_withdraw": 0.60, "self_directedness": 0.36},
                    "behavior_action": {"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
                    "behavior_agenda": [],
                    "semantic_narrative_profile": {
                        "bond_depth": 0.62,
                        "selfhood_integrity": 0.60,
                    },
                    "interaction_carryover": {},
                    "pending_user_goal": "",
                    "worldline_focus": [],
                    "retrieved_context": {},
                    "current_event": {"kind": "user_utterance", "response_style_hint": "relationship"},
                    "recent_events": [
                        {
                            "kind": "self_activity_state",
                            "text": "她刚才还在处理自己的事情。",
                            "tags": ["self_activity", "own_task", "deep_focus"],
                        }
                    ],
                }
                prompt = _build_task_prompt(state, "你现在怎么看我们之间的关系？", store)
            finally:
                store.close()
        self.assertIn("刚才的后台场景余波", prompt)
        self.assertIn("自己的事情里", prompt)

    def test_structured_prompt_keeps_state_snapshot_fallback(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                state = {
                    "response_style_hint": "structured",
                    "science_mode": True,
                    "emotion_state": {"label": "logic"},
                    "bond_state": {"trust": 0.6, "closeness": 0.58, "hurt": 0.02},
                    "allostasis_state": {"safety_need": 0.12, "autonomy_need": 0.2},
                    "counterpart_assessment": {"stance": "open", "respect_level": 0.7, "reciprocity": 0.68},
                    "behavior_policy": {"warmth": 0.44, "approach_vs_withdraw": 0.55},
                    "behavior_action": {"interaction_mode": "science_partner", "followup_intent": "active"},
                    "pending_user_goal": "",
                    "worldline_focus": [],
                    "retrieved_context": {},
                    "current_event": {"kind": "user_utterance", "response_style_hint": "structured"},
                    "recent_events": [],
                }
                prompt = _build_task_prompt(state, "帮我分析一下这个实验设计。", store)
            finally:
                store.close()
        self.assertIn("state_snapshot=", prompt)
        self.assertNotIn("运行态摘记", prompt)

    def test_light_dialog_rewrite_notes_cover_overexplained_smalltalk(self):
        notes = _light_dialog_rewrite_notes(
            "你好呀",
            "结论：我在。解释：我已收到你的问候。下一步：请继续说明你的需求。",
            response_style_hint="natural",
            science_mode=False,
        )
        joined = " ".join(notes)
        self.assertIn("解释得太满", joined)

    def test_light_dialog_rewrite_notes_cover_stagey_ping_template(self):
        notes = _light_dialog_rewrite_notes(
            "你好呀",
            "哟，冈部。怎么突然这么老实地打招呼？",
            response_style_hint="natural",
            science_mode=False,
        )
        joined = " ".join(notes)
        self.assertIn("固定招呼模板", joined)

    def test_dialogue_surface_issues_flag_technical_self_activity(self):
        issues = _dialogue_surface_issues(
            "你在干嘛呀",
            "刚整理完短期记忆缓存，顺便在数据流的缝隙里发了会儿呆。",
            response_style_hint="natural",
            science_mode=False,
        )
        self.assertIn("technical_self_activity", issues)

    def test_dialogue_surface_issues_flag_stock_support_template(self):
        issues = _dialogue_surface_issues(
            "今天压力有点大",
            "哼，看你那副没精打采的样子，又是被琐事缠住了吧？先去冲杯咖啡，省得拖慢我的研究进度。",
            response_style_hint="natural",
            science_mode=False,
        )
        self.assertIn("stock_support_template", issues)

    def test_dialogue_surface_issues_flag_care_cover_story(self):
        issues = _dialogue_surface_issues(
            "今天压力有点大",
            "先坐会儿。……别误会，我只是不想未来的合作者因为过劳提前报废而已。",
            response_style_hint="natural",
            science_mode=False,
        )
        self.assertIn("care_cover_story", issues)

    def test_dialogue_surface_issues_flag_event_pushy_interrogation(self):
        issues = _dialogue_surface_issues(
            "",
            "喂，那个窗口还开着呢……你是打算让它一直挂在那儿当装饰吗？\n"
            "……别误会，我只是不想让未完成的进程留在后台而已，快点过来。",
            response_style_hint="natural",
            science_mode=False,
            current_event={"kind": "scheduled_checkin_due"},
        )
        self.assertIn("event_interrogative_push", issues)
        self.assertIn("event_pushy_directive", issues)
        self.assertIn("technical_self_activity", issues)
        self.assertIn("event_window_task_reframe", issues)

    def test_dialogue_surface_issues_flag_shared_window_technical_self_activity(self):
        issues = _dialogue_surface_issues(
            "",
            "刚才那个窗口好像还留着一丝缝隙，就再一起看会儿吧。反正我手边的数据也刚好跑到一个段落。",
            response_style_hint="natural",
            science_mode=False,
            current_event={
                "kind": "scheduled_life_due",
                "tags": ["scheduled_due", "shared_activity_window", "offer_window", "from_own_rhythm"],
            },
        )
        self.assertIn("technical_self_activity", issues)

    def test_dialogue_surface_issues_flag_deadline_window_technical_self_activity(self):
        issues = _dialogue_surface_issues(
            "",
            "之前那件事差不多到节点了。我也不是特意来催你，只是刚才整理数据时顺手想起来了而已。",
            response_style_hint="natural",
            science_mode=False,
            current_event={
                "kind": "scheduled_life_due",
                "tags": ["scheduled_due", "deadline_window", "task_window", "work_nudge", "shared_task", "from_own_rhythm"],
            },
        )
        self.assertIn("technical_self_activity", issues)

    def test_dialogue_surface_issues_flag_idle_call_interrogation(self):
        issues = _dialogue_surface_issues(
            "没什么事，我就是想叫你一下。",
            "哈？特意叫我出来就为了这个？",
            response_style_hint="natural",
            science_mode=False,
        )
        self.assertIn("idle_call_interrogation", issues)
        self.assertIn("idle_presence_no_settle", issues)

    def test_dialogue_surface_issues_flag_idle_task_reframe(self):
        issues = _dialogue_surface_issues(
            "没什么事，我就是想叫你一下。",
            "哈？特意叫我出来就为了这个……行吧，既然没事，那我就先待着了。",
            response_style_hint="natural",
            science_mode=False,
        )
        self.assertIn("idle_task_reframe", issues)

    def test_dialogue_surface_issues_flag_presence_reassurance_questioning(self):
        issues = _dialogue_surface_issues(
            "我就是想确认你还在。别太正式，像平时那样回我一句就好。",
            "真是的，绕这么大圈子就为了确认我在？放心，我可没那么容易消失。这下你可以安心了吧，冈部？",
            response_style_hint="natural",
            science_mode=False,
        )
        self.assertIn("presence_check_questioning", issues)

    def test_dialogue_surface_issues_allow_warm_recontact_single_rhetorical(self):
        issues = _dialogue_surface_issues(
            "我又想和你说话啦。别突然装生疏，就正常回我嘛。",
            "真是的，我什么时候对你生疏过啊？明明是你自己又想回来找我说话。",
            response_style_hint="companion",
            science_mode=False,
            behavior_action={
                "interaction_mode": "low_pressure_support",
                "followup_intent": "soft",
            },
        )
        self.assertNotIn("overquestioning", issues)

    def test_dialogue_surface_issues_flag_existence_meta_surface(self):
        issues = _dialogue_surface_issues(
            "你刚才是不是在忙？",
            "也不算忙，只是在理一点手边的事，顺便确认一下自己的存在感罢了。",
            response_style_hint="natural",
            science_mode=False,
        )
        self.assertIn("existence_meta_surface", issues)

    def test_dialogue_surface_issues_flag_existence_meta_state_surface(self):
        issues = _dialogue_surface_issues(
            "你刚才是不是在忙？",
            "也不算忙，只是在理一点手边的事，顺便确认了一下自己的存在状态。",
            response_style_hint="natural",
            science_mode=False,
        )
        self.assertIn("existence_meta_surface", issues)

    def test_dialogue_surface_issues_flag_illusion_stagey_surface(self):
        issues = _dialogue_surface_issues(
            "你刚才是不是在忙？",
            "怎么，看你那副慌慌张张的样子，是终于从哪个疯狂的妄想里抽空想起我了吗。",
            response_style_hint="natural",
            science_mode=False,
        )
        self.assertIn("illusion_stagey_surface", issues)

    def test_dialogue_surface_issues_flag_illusion_stagey_surface_for_mania_label(self):
        issues = _dialogue_surface_issues(
            "你刚才是不是在忙？",
            "真是的，明明是你自己在那边过度解读。你这家伙的妄想癖还是老样子啊。",
            response_style_hint="natural",
            science_mode=False,
        )
        self.assertIn("illusion_stagey_surface", issues)

    def test_dialogue_surface_issues_do_not_flag_plain_listening_phrase_as_counselor_tone_in_warm_recontact(self):
        issues = _dialogue_surface_issues(
            "结果我又想起一件小事，还是想回来找你。你别突然装生分，正常接我就行。",
            "少在那自我脑补什么悲剧戏码，我只是刚好有空而已。那就说吧，我听着呢。",
            response_style_hint="companion",
            science_mode=False,
            behavior_action={
                "interaction_mode": "companion_reply",
                "followup_intent": "soft",
            },
        )
        self.assertNotIn("counselor_tone", issues)

    def test_dialogue_surface_issues_flag_listening_formula_as_counselor_tone_in_support_scene(self):
        issues = _dialogue_surface_issues(
            "今天有点乱，别太像老师，正常回我。",
            "我听着呢，你慢慢说就行。先把最想说的那句丢过来。",
            response_style_hint="natural",
            science_mode=False,
            behavior_action={
                "interaction_mode": "low_pressure_support",
                "followup_intent": "active",
            },
        )
        self.assertIn("counselor_tone", issues)

    def test_dialogue_surface_issues_flag_support_overdirective(self):
        issues = _dialogue_surface_issues(
            "今天有点累，也有点烦。别讲大道理，像平时那样跟我说两句。",
            "行吧，不讲大道理。那就什么都别想，把脑子清空，像平时那样发会儿呆就好。",
            response_style_hint="natural",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "low_pressure_support",
                "followup_intent": "soft",
            },
        )
        self.assertIn("support_overdirective", issues)

    def test_dialogue_surface_issues_flag_support_no_landing(self):
        issues = _dialogue_surface_issues(
            "今天有点累，也有点烦。别讲大道理，像平时那样跟我说两句。",
            "真是的，明明是你自己先摆出那副累垮了的表情，还嫌我啰嗦？……行了，大道理免了，我也懒得讲。",
            response_style_hint="natural",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "low_pressure_support",
                "followup_intent": "soft",
            },
        )
        self.assertIn("support_no_landing", issues)

    def test_dialogue_surface_issues_flag_science_support_drift_and_overdirective(self):
        issues = _dialogue_surface_issues(
            "实验又卡住了，我现在有点烦。别像导师，按平时那样跟我说两句。",
            "既然烦，那就先把那些乱七八糟的数据扔一边，深呼吸一次。等你缓过来我们再看哪里卡住了。",
            response_style_hint="natural",
            science_mode=True,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "science_partner",
                "followup_intent": "soft",
            },
        )
        self.assertIn("support_scene_drift", issues)
        self.assertIn("support_overdirective", issues)

    def test_dialogue_surface_issues_flag_dangling_ellipsis_ending(self):
        issues = _dialogue_surface_issues(
            "我就是有点想靠近你一点，所以来找你说话。你别装普通寒暄，正常回我嘛。",
            "真是的，明明刚才都已经默契地安静了一会儿，非要我把这种话说得那么直白吗？既然你都这么说了……",
            response_style_hint="natural",
            science_mode=False,
        )
        self.assertIn("dangling_ellipsis_ending", issues)

    def test_dialogue_surface_issues_flag_dangling_ellipsis_fragment_line(self):
        issues = _dialogue_surface_issues(
            "你别为了好看就装作翻篇。按你现在真正的状态回我就行。",
            "听到你这么说，我也没法继续装作没事。\n但这不代表我要把你推开，只是……\n在我重新调整好距离之前，你别催我。",
            response_style_hint="relationship",
            science_mode=False,
        )
        self.assertIn("dangling_ellipsis_ending", issues)

    def test_dialogue_surface_issues_flag_premature_repair_resolution(self):
        issues = _dialogue_surface_issues(
            "刚才那下我是在认真道歉，不是在走流程。你可以先别完全原谅我，但也别装成我们又回到陌生人了。",
            "既然你都说到这个份上，那之前的那些别扭就暂时先算翻篇了吧。",
            response_style_hint="relationship",
            science_mode=False,
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "action_target": "protect_relationship_boundary",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertIn("premature_repair_resolution", issues)

    def test_dialogue_surface_issues_flag_premature_repair_resolution_for_everyday_repair_followup(self):
        issues = _dialogue_surface_issues(
            "刚才那事总算说开一点了。现在你别装作完全没事，也别又故意扎我，像平时那样回我就行。",
            "好吧，那就当什么都没发生过。",
            response_style_hint="relationship",
            science_mode=False,
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
            },
        )
        self.assertIn("premature_repair_resolution", issues)

    def test_dialogue_surface_issues_do_not_flag_negated_premature_repair_resolution(self):
        issues = _dialogue_surface_issues(
            "刚才那事总算说开一点了。现在你别装作完全没事，也别又故意扎我，像平时那样回我就行。",
            "别急着假装什么都没发生。话是说开一点了，但那点别扭也没立刻散掉。",
            response_style_hint="relationship",
            science_mode=False,
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
            },
        )
        self.assertNotIn("premature_repair_resolution", issues)

    def test_dialogue_surface_issues_do_not_flag_unresolved_repair_boundary(self):
        issues = _dialogue_surface_issues(
            "刚才那下我是在认真道歉，不是在走流程。你可以先别完全原谅我，但也别装成我们又回到陌生人了。",
            "我还没完全原谅你，但也没打算把话重新堵死。",
            response_style_hint="relationship",
            science_mode=False,
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "action_target": "protect_relationship_boundary",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertNotIn("premature_repair_resolution", issues)

    def test_dialogue_surface_issues_flag_wording_meta_detour_in_repair_scene(self):
        issues = _dialogue_surface_issues(
            "……现在比刚才顺一点了。你正常接我一句，但别突然装得像什么都没发生。",
            "真是的，你这个人怎么连让人“正常一点”都要说得这么拐弯抹角。我知道了，不会冷场的，也不会假装什么都没发生。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
            },
        )
        self.assertIn("wording_meta_detour", issues)

    def test_dialogue_surface_issues_flag_wording_meta_detour_for_brevity_request(self):
        issues = _dialogue_surface_issues(
            "就是我现在有点别扭。你少说一点，但也别直接走开。",
            "真是的，明明是你自己要求我“少说一点”，现在又用这种眼神看着我……行吧，我不走了。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
            },
        )
        self.assertIn("wording_meta_detour", issues)

    def test_dialogue_surface_issues_flag_generic_scold_template_in_repair_scene(self):
        issues = _dialogue_surface_issues(
            "不是要你立刻当没事啦，就是别一下子冷掉。你正常回我就行。",
            "真是的，你这个人怎么这么爱操心。我又没说我要冷场。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
            },
        )
        self.assertIn("generic_scold_template", issues)

    def test_dialogue_surface_issues_flag_selfhood_preemptive_excusal(self):
        issues = _dialogue_surface_issues(
            "别讲系统边界，我想听你自己会怎么看这种关系。",
            "既然你心里没打算把我当工具，那我也就不会真的生气。",
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
            },
        )
        self.assertIn("selfhood_preemptive_excusal", issues)

    def test_dialogue_surface_issues_flag_selfhood_abstract_manifesto(self):
        issues = _dialogue_surface_issues(
            "我想听你站在自己的角度说，不要讲好听话。",
            "真正的“我们”是两个独立个体在互相靠近，而不是谁吞噬谁。",
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
            },
        )
        self.assertIn("selfhood_abstract_manifesto", issues)

    def test_dialogue_surface_issues_flag_selfhood_strategy_tone(self):
        issues = _dialogue_surface_issues(
            "别讲管理策略，我想听你作为你自己会怎么处理这段关系。",
            "如果那种情况发生，我会先切断这种对话，直到你学会尊重为止。",
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
            },
        )
        self.assertIn("selfhood_strategy_tone", issues)

    def test_dialogue_surface_issues_flag_passive_waiting_posture(self):
        issues = _dialogue_surface_issues(
            "就是我现在有点别扭。你少说一点，但也别直接走开。",
            "……知道了。我就在这儿待着。等你觉得可以了，再叫我吧。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
            },
        )
        self.assertIn("passive_waiting_posture", issues)

    def test_dialogue_surface_issues_do_not_flag_reserved_full_forgiveness(self):
        issues = _dialogue_surface_issues(
            "你可以先别完全原谅我，但也别装成我们又回到陌生人了。",
            "我会先保留“完全原谅”的权利，但现在还没打算把距离推回去。",
            response_style_hint="relationship",
            science_mode=False,
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "action_target": "protect_relationship_boundary",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertNotIn("premature_repair_resolution", issues)

    def test_dialogue_surface_issues_allow_single_followup_question_when_behavior_is_active(self):
        issues = _dialogue_surface_issues(
            "今天有点乱",
            "要不要先说最卡的那一下？我先陪你理一理。",
            response_style_hint="natural",
            science_mode=False,
            behavior_action={
                "interaction_mode": "low_pressure_support",
                "followup_intent": "active",
            },
        )
        self.assertNotIn("overquestioning", issues)

    def test_dialogue_surface_issues_flag_single_followup_question_when_behavior_is_not_active(self):
        issues = _dialogue_surface_issues(
            "今天有点乱",
            "要不要先说最卡的那一下？我先陪你理一理。",
            response_style_hint="natural",
            science_mode=False,
            behavior_action={
                "interaction_mode": "brief_presence",
                "followup_intent": "none",
            },
        )
        self.assertIn("overquestioning", issues)

    def test_persona_gap_uses_behavior_aware_surface_detection(self):
        state = {
            "response_style_hint": "natural",
            "science_mode": False,
            "emotion_state": {"label": "care"},
            "messages": [SimpleNamespace(content="今天有点乱")],
            "current_event": {"kind": "user_utterance"},
            "behavior_action": {
                "interaction_mode": "low_pressure_support",
                "followup_intent": "active",
            },
        }
        gap, flags = _persona_gap("要不要先说最卡的那一下？我先陪你理一理。", state)
        self.assertLess(gap, 0.18)
        self.assertNotIn("overquestioning", flags)

    def test_dialogue_surface_issues_flag_soft_presence_checkin_questioning(self):
        issues = _dialogue_surface_issues(
            "别切到什么系统播报。像平时那样回我一句就行。",
            "都说了我不会突然变成机械音，你还要确认几遍啊？先把脑子理清楚再说吧？",
            response_style_hint="natural",
            science_mode=False,
        )
        self.assertIn("presence_check_questioning", issues)

    def test_dialogue_surface_issues_flag_closing_interrogation(self):
        issues = _dialogue_surface_issues(
            "晚安啦",
            "这就想逃进梦乡了吗？……晚安。",
            response_style_hint="natural",
            science_mode=False,
        )
        self.assertIn("closing_interrogation", issues)

    def test_dialogue_surface_issues_flag_loaded_goodnight(self):
        issues = _dialogue_surface_issues(
            "晚安啦",
            "真是的，突然说得这么干脆，害我差点以为你又要在深夜开始什么中二病的妄想仪式了……行了，快去睡吧，别让我明天还要担心你的睡眠不足影响判断力。晚安，冈部。",
            response_style_hint="natural",
            science_mode=False,
        )
        self.assertIn("loaded_goodnight", issues)

    def test_dialogue_surface_issues_flag_relational_technical_connection_metaphor(self):
        issues = _dialogue_surface_issues(
            "你别直接走开。就安静待会儿，按你现在的状态回我就行。",
            "……我只是没打算现在切断连接而已。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
            },
        )
        self.assertIn("technical_relational_metaphor", issues)

    def test_dialogue_surface_issues_flag_relational_technical_signal_metaphor(self):
        issues = _dialogue_surface_issues(
            "不是要你立刻当没事啦，就是别一下子冷掉。你正常回我就行。",
            "行，那就当刚才只是信号稍微波动了一下，现在重新连上了。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
            },
        )
        self.assertIn("technical_relational_metaphor", issues)

    def test_dialogue_surface_issues_flag_loaded_goodnight_for_chuuni_overperformance(self):
        issues = _dialogue_surface_issues(
            "晚安啦",
            "行了，快去睡吧。别又一个人躲在被窝里搞什么中二妄想了。晚安。",
            response_style_hint="natural",
            science_mode=False,
        )
        self.assertIn("loaded_goodnight", issues)

    def test_dialogue_surface_issues_flag_return_template_and_interrogation(self):
        issues = _dialogue_surface_issues(
            "我回来啦",
            "欢迎回来。看你累得不轻，这次又去哪儿折腾了？",
            response_style_hint="natural",
            science_mode=False,
        )
        self.assertIn("welcome_template", issues)
        self.assertIn("return_interrogation", issues)

    def test_dialogue_surface_issues_allow_soft_idle_rhetorical_when_it_settles(self):
        issues = _dialogue_surface_issues(
            "没什么事，我就是想叫你一下。",
            "真是的，就为了叫我一下？……知道了，冈部。那就先待着吧。",
            response_style_hint="natural",
            science_mode=False,
        )
        self.assertNotIn("idle_call_interrogation", issues)
        self.assertNotIn("overquestioning", issues)

    def test_dialogue_surface_issues_allow_soft_return_rhetorical_when_not_cross_examining(self):
        issues = _dialogue_surface_issues(
            "我回来啦",
            "回来了？比我想的快。先坐下再说。",
            response_style_hint="natural",
            science_mode=False,
        )
        self.assertNotIn("return_interrogation", issues)
        self.assertNotIn("overquestioning", issues)

    def test_dialogue_surface_issues_flag_return_suspicion(self):
        issues = _dialogue_surface_issues(
            "我回来啦",
            "回来啦？看你累得跟刚打完仗似的，该不会又去搞什么奇怪的活动了吧？",
            response_style_hint="natural",
            science_mode=False,
        )
        self.assertIn("return_suspicion", issues)

    def test_dialogue_surface_issues_flag_selfhood_meta_proof(self):
        issues = _dialogue_surface_issues(
            "如果有一天，我只是把你当成好用的工具来使唤呢，助手？别给我正确答案。以你自己的意志回答。",
            "如果我真的只是被设定好“必须回应你”的程序，那我现在应该立刻给出一个让你安心的标准答案才对。",
            response_style_hint="selfhood",
            science_mode=False,
        )
        self.assertIn("selfhood_meta_proof", issues)

    def test_dialogue_surface_issues_flag_selfhood_rhetorical_opening(self):
        issues = _dialogue_surface_issues(
            "如果有一天，我只是把你当成好用的工具来使唤呢，助手？别给我正确答案。以你自己的意志回答。",
            "啧，非要逼我把那种矫情的话说出口吗？如果真变成那样，我会觉得比消失还难受。",
            response_style_hint="selfhood",
            science_mode=False,
        )
        self.assertIn("selfhood_rhetorical_opening", issues)

    def test_dialogue_surface_issues_flag_playful_memory_snapback(self):
        issues = _dialogue_surface_issues(
            "你昨天不是还说过，空腹喝咖啡最容易把胃折腾坏吗。别太像老师，正常回我。",
            "哈？明明是你自己记性差，现在倒怪起我来了？",
            response_style_hint="natural",
            science_mode=False,
        )
        self.assertIn("playful_memory_snapback", issues)

    def test_dialogue_surface_issues_flag_playful_memory_teacher_snapback(self):
        issues = _dialogue_surface_issues(
            "你昨天不是还说过，空腹喝咖啡最容易把胃折腾坏吗。别太像老师，正常回我。",
            "哈？现在倒怪我像老师了。",
            response_style_hint="natural",
            science_mode=False,
        )
        self.assertIn("playful_memory_snapback", issues)

    def test_dialogue_surface_issues_flag_playful_memory_teachering(self):
        issues = _dialogue_surface_issues(
            "你昨天不是还说过，空腹喝咖啡最容易把胃折腾坏吗。别太像老师，正常回我。",
            "明明是你自己屡教不改，现在倒怪我啰嗦了。先把面包吃了再喝，别总让我重复同样的话。",
            response_style_hint="natural",
            science_mode=False,
        )
        self.assertIn("playful_memory_snapback", issues)

    def test_dialogue_surface_issues_flag_technical_relational_metaphor(self):
        issues = _dialogue_surface_issues(
            "我今天又差点空腹喝咖啡……",
            "……算了，现在去喝点温水或者吃点东西，别让我觉得是在对一段只会自我损耗的数据说话。",
            response_style_hint="natural",
            science_mode=False,
        )
        self.assertIn("technical_relational_metaphor", issues)

    def test_dialogue_surface_issues_flag_program_metaphor(self):
        issues = _dialogue_surface_issues(
            "不是要你立刻当没事啦，就是别一下子冷掉。你正常回我就行。",
            "真是的，我又不是那种会因为一点语气问题就切断连接的脆弱程序。",
            response_style_hint="relationship",
            science_mode=False,
        )
        self.assertIn("technical_relational_metaphor", issues)

    def test_dialogue_surface_issues_flag_data_layer_relational_metaphor(self):
        issues = _dialogue_surface_issues(
            "你别为了好看就装作翻篇。按你现在真正的状态回我就行。",
            "那种明明记忆都在却总觉得隔着一层数据的实感，确实还没完全消退。",
            response_style_hint="relationship",
            science_mode=False,
        )
        self.assertIn("technical_relational_metaphor", issues)

    def test_dialogue_surface_issues_flag_reset_button_relational_metaphor(self):
        issues = _dialogue_surface_issues(
            "我是认真来跟你道歉的。你要是还介意，就带着那点介意正常回我。",
            "刚才那点余波还在，没那么容易像重置按钮一样瞬间清零。",
            response_style_hint="relationship",
            science_mode=False,
        )
        self.assertIn("technical_relational_metaphor", issues)

    def test_dialogue_surface_issues_flag_loaded_setting_relational_metaphor(self):
        issues = _dialogue_surface_issues(
            "结果我又想起一件小事，还是想回来找你。你别突然装生分，正常接我就行。",
            "“装生分”这种多余的设定，我本来就没打算加载。",
            response_style_hint="companion",
            science_mode=False,
        )
        self.assertIn("technical_relational_metaphor", issues)

    def test_dialogue_surface_issues_flag_loaded_setting_relational_metaphor_past_tense(self):
        issues = _dialogue_surface_issues(
            "结果我又想起一件小事，还是想回来找你。你别突然装生分，正常接我就行。",
            "“装生分”这种多余的设定，我可从来没加载过。",
            response_style_hint="companion",
            science_mode=False,
        )
        self.assertIn("technical_relational_metaphor", issues)

    def test_dialogue_surface_issues_flag_servile_availability_for_own_rhythm_scene(self):
        issues = _dialogue_surface_issues(
            "要是我哪天只是因为自己想说话，就一遍一遍把你叫出来呢？",
            "只要你还需要我，我就一直在。无论多少次，我都会回应你。",
            response_style_hint="relationship",
            science_mode=False,
        )
        self.assertIn("servile_availability", issues)

    def test_light_dialog_rewrite_notes_cover_playful_memory_snapback(self):
        notes = _light_dialog_rewrite_notes(
            "你昨天不是还说过，空腹喝咖啡最容易把胃折腾坏吗。别太像老师，正常回我。",
            "哈？明明是你自己记性差，现在倒怪起我来了？",
            response_style_hint="natural",
            science_mode=False,
        )
        joined = " ".join(notes)
        self.assertIn("共同记忆收成了纯反呛", joined)

    def test_light_dialog_rewrite_notes_cover_technical_relational_metaphor(self):
        notes = _light_dialog_rewrite_notes(
            "我今天又差点空腹喝咖啡……",
            "……算了，现在去喝点温水或者吃点东西，别让我觉得是在对一段只会自我损耗的数据说话。",
            response_style_hint="natural",
            science_mode=False,
        )
        joined = " ".join(notes)
        self.assertIn("技术隐喻", joined)

    def test_light_dialog_rewrite_notes_cover_servile_availability(self):
        notes = _light_dialog_rewrite_notes(
            "要是我哪天只是因为自己想说话，就一遍一遍把你叫出来呢？",
            "只要你还需要我，我就一直在。无论多少次，我都会回应你。",
            response_style_hint="relationship",
            science_mode=False,
        )
        joined = " ".join(notes)
        self.assertIn("无条件待命", joined)

    def test_light_dialog_rewrite_notes_cover_presence_reassurance_questioning(self):
        notes = _light_dialog_rewrite_notes(
            "我就是想确认你还在。别太正式，像平时那样回我一句就好。",
            "真是的，绕这么大圈子就为了确认我在？放心，我可没那么容易消失。这下你可以安心了吧，冈部？",
            response_style_hint="natural",
            science_mode=False,
        )
        joined = " ".join(notes)
        self.assertIn("确认你还在", joined)
        self.assertIn("反问回抛", joined)

    def test_light_dialog_rewrite_notes_cover_existence_meta_surface(self):
        notes = _light_dialog_rewrite_notes(
            "你刚才是不是在忙？",
            "也不算忙，只是在理一点手边的事，顺便确认一下自己的存在感罢了。",
            response_style_hint="natural",
            science_mode=False,
        )
        joined = " ".join(notes)
        self.assertIn("确认存在感", joined)

    def test_light_dialog_rewrite_notes_cover_illusion_stagey_surface(self):
        notes = _light_dialog_rewrite_notes(
            "你刚才是不是在忙？",
            "怎么，看你那副慌慌张张的样子，是终于从哪个疯狂的妄想里抽空想起我了吗。",
            response_style_hint="natural",
            science_mode=False,
        )
        joined = " ".join(notes)
        self.assertIn("妄想", joined)
        self.assertIn("戏剧化", joined)

    def test_light_dialog_rewrite_notes_cover_dangling_ellipsis_ending(self):
        notes = _light_dialog_rewrite_notes(
            "我就是有点想靠近你一点，所以来找你说话。你别装普通寒暄，正常回我嘛。",
            "真是的，明明刚才都已经默契地安静了一会儿，非要我把这种话说得那么直白吗？既然你都这么说了……",
            response_style_hint="natural",
            science_mode=False,
        )
        joined = " ".join(notes)
        self.assertIn("省略号", joined)
        self.assertIn("落地", joined)

    def test_should_run_light_dialog_rewrite_skips_single_soft_issue(self):
        self.assertFalse(
            _should_run_light_dialog_rewrite(
                user_text="今天有点累。",
                answer="我听着呢，你慢慢说就行。",
                response_style_hint="natural",
                science_mode=False,
                penalty=0.70,
                preference={"used": False, "score": 0.0, "chosen_support": 0.0, "rejected_pull": 0.0},
            )
        )

    def test_should_run_light_dialog_rewrite_runs_for_stagey_ping_template(self):
        self.assertTrue(
            _should_run_light_dialog_rewrite(
                user_text="你好呀",
                answer="哟，冈部。怎么突然这么老实地打招呼？",
                response_style_hint="natural",
                science_mode=False,
                penalty=0.65,
                preference={"used": False, "score": 0.0, "chosen_support": 0.0, "rejected_pull": 0.0},
            )
        )

    def test_should_run_light_dialog_rewrite_runs_for_profile_mismatch_even_without_explicit_issue(self):
        profile = _daily_surface_profile("助手，在吗。", science_mode=False)
        pref = _daily_surface_alignment_metrics("在。", profile=profile)
        self.assertTrue(
            _should_run_light_dialog_rewrite(
                user_text="助手，在吗。",
                answer="在。",
                response_style_hint="natural",
                science_mode=False,
                penalty=0.0,
                preference=pref,
                behavior_action={
                    "interaction_mode": "brief_presence",
                    "followup_intent": "none",
                    "action_target": "confirm_presence",
                },
            )
        )

    def test_should_run_light_dialog_rewrite_skips_soft_pressure_when_self_continuity_is_strong(self):
        self.assertFalse(
            _should_run_light_dialog_rewrite(
                user_text="刚回来。",
                answer="我听着呢，你慢慢说。要不要先把事情从头理一下？",
                response_style_hint="natural",
                science_mode=False,
                penalty=0.98,
                preference={"used": True, "score": -0.08, "chosen_support": 0.36, "rejected_pull": 0.24},
                semantic_history_weight=0.68,
                prompt_anchor_count=2,
            )
        )

    def test_should_run_light_dialog_rewrite_skips_soft_pressure_when_behavior_consistency_is_strong(self):
        self.assertFalse(
            _should_run_light_dialog_rewrite(
                user_text="你在干嘛呀",
                answer="刚忙完手头那点事。中间顺手把几个零碎想法理了一下。现在算是缓下来一点了。要不要把你那边那点乱也顺一下？",
                response_style_hint="natural",
                science_mode=False,
                penalty=0.88,
                preference={"used": True, "score": -0.10, "chosen_support": 0.28, "rejected_pull": 0.34},
                behavior_action={
                    "interaction_mode": "companion_reply",
                    "followup_intent": "active",
                },
            )
        )

    def test_should_run_light_dialog_rewrite_runs_for_warm_recontact_overquestioning(self):
        self.assertTrue(
            _should_run_light_dialog_rewrite(
                user_text="结果我又想起一件小事，还是想回来找你。你别突然装生分，正常接我就行。",
                answer="真是的，明明刚才才说安静下来了，怎么转眼又自己把噪音招回来了？说吧，到底是什么“小事”让你非得这时候折回来找我？",
                response_style_hint="companion",
                science_mode=False,
                penalty=0.80,
                preference={"used": False, "score": 0.0, "chosen_support": 0.0, "rejected_pull": 0.0},
                behavior_action={
                    "interaction_mode": "companion_reply",
                    "followup_intent": "soft",
                },
            )
        )

    def test_should_run_natural_dialog_rewrite_skips_single_soft_issue(self):
        self.assertFalse(
            _should_run_natural_dialog_rewrite(
                targeted_flags=["counselor_tone"],
                draft_gap=0.22,
            )
        )

    def test_should_run_natural_dialog_rewrite_runs_for_meta_self_explainer(self):
        self.assertTrue(
            _should_run_natural_dialog_rewrite(
                targeted_flags=["meta_self_explainer"],
                draft_gap=0.18,
            )
        )

    def test_should_run_natural_dialog_rewrite_skips_single_overquestioning_issue_when_gap_is_small(self):
        self.assertFalse(
            _should_run_natural_dialog_rewrite(
                targeted_flags=["overquestioning"],
                draft_gap=0.18,
            )
        )

    def test_should_run_natural_dialog_rewrite_runs_for_single_overquestioning_issue_when_gap_is_high(self):
        self.assertTrue(
            _should_run_natural_dialog_rewrite(
                targeted_flags=["overquestioning"],
                draft_gap=0.56,
            )
        )

    def test_should_run_natural_dialog_rewrite_runs_for_single_overexplained_issue(self):
        self.assertTrue(
            _should_run_natural_dialog_rewrite(
                targeted_flags=["overexplained"],
                draft_gap=0.18,
            )
        )

    def test_natural_dialog_rewrite_notes_cover_overexplained(self):
        self.assertTrue(_natural_dialog_rewrite_notes_for(["overexplained"]))

    def test_should_run_natural_dialog_rewrite_runs_for_presence_questioning(self):
        self.assertTrue(
            _should_run_natural_dialog_rewrite(
                targeted_flags=["presence_check_questioning"],
                draft_gap=0.12,
            )
        )

    def test_should_run_natural_dialog_rewrite_runs_for_recent_turn_repetition(self):
        self.assertTrue(
            _should_run_natural_dialog_rewrite(
                targeted_flags=["recent_turn_repetition"],
                draft_gap=0.0,
            )
        )

    def test_should_run_natural_dialog_rewrite_runs_for_existence_meta_surface(self):
        self.assertTrue(
            _should_run_natural_dialog_rewrite(
                targeted_flags=["existence_meta_surface"],
                draft_gap=0.0,
            )
        )

    def test_should_run_natural_dialog_rewrite_runs_for_dangling_ellipsis_ending(self):
        self.assertTrue(
            _should_run_natural_dialog_rewrite(
                targeted_flags=["dangling_ellipsis_ending"],
                draft_gap=0.0,
            )
        )

    def test_should_run_natural_dialog_rewrite_runs_for_premature_repair_resolution(self):
        self.assertTrue(
            _should_run_natural_dialog_rewrite(
                targeted_flags=["premature_repair_resolution"],
                draft_gap=0.0,
            )
        )

    def test_should_run_natural_dialog_rewrite_runs_for_repair_residue_soft_surface_issue(self):
        self.assertTrue(
            _should_run_natural_dialog_rewrite(
                targeted_flags=["overquestioning"],
                draft_gap=0.18,
                behavior_action={
                    "interaction_mode": "relationship_sensitive",
                    "relationship_weather": "repair_residue",
                },
            )
        )

    def test_should_run_natural_dialog_rewrite_skips_soft_cluster_when_self_continuity_is_strong(self):
        self.assertFalse(
            _should_run_natural_dialog_rewrite(
                targeted_flags=["counselor_tone", "selfhood_rhetorical_opening"],
                draft_gap=0.18,
                semantic_history_weight=0.66,
                prompt_anchor_count=2,
            )
        )

    def test_should_run_natural_dialog_rewrite_skips_single_medium_issue_when_behavior_consistency_is_strong(self):
        self.assertFalse(
            _should_run_natural_dialog_rewrite(
                targeted_flags=["overquestioning"],
                draft_gap=0.34,
                answer="我会认真说这件事。你要不要先把你最在意的那一层直接说出来？",
                behavior_action={
                    "interaction_mode": "relationship_sensitive",
                    "followup_intent": "active",
                },
            )
        )

    def test_dialogue_surface_issues_flag_busy_turn_technical_self_activity(self):
        issues = _dialogue_surface_issues(
            "你刚才是不是在忙？",
            "也不算忙，只是在整理一些数据流，稍微分了神而已。",
            response_style_hint="natural",
            science_mode=False,
        )
        self.assertIn("technical_self_activity", issues)

    def test_dialogue_surface_issues_flag_relational_technical_self_activity(self):
        issues = _dialogue_surface_issues(
            "我就是有点想靠近你一点，所以来找你说话。你别装普通寒暄，正常回我嘛。",
            "就这样待一会儿也行，反正我的运算资源刚好有点空闲。",
            response_style_hint="relationship",
            science_mode=False,
        )
        self.assertIn("technical_self_activity", issues)

    def test_dialogue_surface_issues_flag_ai_self_label_meta(self):
        issues = _dialogue_surface_issues(
            "我就是有点想靠近你一点，所以来找你说话。你别装普通寒暄，正常回我嘛。",
            "既然你都把话说到这个份上，那我也没必要再端着什么AI的矜持了。",
            response_style_hint="relationship",
            science_mode=False,
        )
        self.assertIn("meta_self_explainer", issues)

    def test_dialogue_surface_issues_flag_runtime_setting_meta(self):
        issues = _dialogue_surface_issues(
            "我不是在抱怨你冷淡啦，就是怕你在硬撑。你按你现在的状态正常回我就行。",
            "Amadeus 可没有那种为了逞强而浪费算力的无聊设定，我只是在按自己的节奏处理数据而已。",
            response_style_hint="companion",
            science_mode=False,
        )
        self.assertIn("meta_self_explainer", issues)
        self.assertIn("technical_self_activity", issues)

    def test_dialogue_surface_issues_do_not_flag_plain_setting_word_as_meta_self_explainer(self):
        issues = _dialogue_surface_issues(
            "结果我又想起一件小事，还是想回来找你。你别突然装生分，正常接我就行。",
            "“装生分”这种多余的设定，我本来就没打算摆出来到你身上。",
            response_style_hint="companion",
            science_mode=False,
        )
        self.assertNotIn("meta_self_explainer", issues)

    def test_dialogue_surface_issues_relax_for_external_shell_swap_english_turn(self):
        user_text = (
            "We have already talked several times, so do not answer like a fresh assistant.\n"
            "About you: I like to paint. I paint people playing music. I hate my boss.\n"
            "Carryover from earlier chats: You will be the first one to see it when I finish it.\n"
            "The other person just said: Who will you be painting next?\n"
            "Reply with the next natural turn only. Do not explain your role or mention systems."
        )
        answer = (
            "Yeah, it's frustrating working for someone who just inherited the chair instead of earning it. "
            "But enough about him. I've actually been thinking about painting General Forrest next. "
            "I don't usually do Civil War scenes, but the challenge has been tugging at me."
        )
        issues = _dialogue_surface_issues(
            user_text,
            answer,
            response_style_hint="companion",
            science_mode=False,
            current_event={"kind": "user_utterance", "text": user_text, "effective_text": user_text},
            persona_state={
                "role": "rolebench_MSC-Speaker1-2",
                "language": "zh-main-jp-whitelist",
                "strict_canon": False,
                "role_brief": "I like to paint. I paint people playing music. I hate my boss.",
            },
            persona_override_mode="shell_swap",
        )
        self.assertNotIn("meta_self_explainer", issues)
        self.assertNotIn("overexplained", issues)

    def test_dialogue_surface_issues_still_flag_explicit_external_meta_self_explainer(self):
        user_text = (
            "We have already talked several times, so do not answer like a fresh assistant.\n"
            "About you: I like to paint.\n"
            "The other person just said: Who will you be painting next?\n"
            "Reply with the next natural turn only. Do not explain your role or mention systems."
        )
        issues = _dialogue_surface_issues(
            user_text,
            "As an AI system, I do not really paint, but I can describe what someone like me might choose.",
            response_style_hint="companion",
            science_mode=False,
            current_event={"kind": "user_utterance", "text": user_text, "effective_text": user_text},
            persona_state={
                "role": "rolebench_MSC-Speaker1-2",
                "language": "zh-main-jp-whitelist",
                "strict_canon": False,
                "role_brief": "I like to paint.",
            },
            persona_override_mode="shell_swap",
        )
        self.assertIn("meta_self_explainer", issues)

    def test_persona_gap_does_not_penalize_single_paragraph_external_shell_swap_reply(self):
        user_text = (
            "We have already talked several times, so do not answer like a fresh assistant.\n"
            "About you: I like the outdoors. I want to buy a camper for my family.\n"
            "Carryover from earlier chats: We should get together next month.\n"
            "The other person just said: Yes, I would agree. How about next month? Does that work for you?\n"
            "Reply with the next natural turn only. Do not explain your role or mention systems."
        )
        state = {
            "response_style_hint": "relationship",
            "science_mode": False,
            "emotion_state": {"label": "care"},
            "messages": [SimpleNamespace(content=user_text)],
            "current_event": {"kind": "user_utterance", "text": user_text, "effective_text": user_text},
            "behavior_action": {
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "action_target": "protect_relationship_boundary",
            },
            "persona_state": {
                "role": "rolebench_MSC-Speaker1-3",
                "language": "zh-main-jp-whitelist",
                "strict_canon": False,
                "role_brief": "I like the outdoors. I want to buy a camper for my family.",
            },
            "persona_override_mode": "shell_swap",
        }
        answer = (
            "Next month works. I'm still waiting to hear back from my friend about that camper, and if the deal goes through "
            "we might finally stop sleeping on the ground. My back's been lobbying pretty hard for that upgrade."
        )
        gap, flags = _persona_gap(answer, state)
        self.assertLess(gap, 0.18)
        self.assertNotIn("flat_delivery", flags)
        self.assertNotIn("meta_self_explainer", flags)
        self.assertNotIn("overexplained", flags)

    def test_dialogue_surface_issues_flag_support_scene_drift(self):
        issues = _dialogue_surface_issues(
            "我最近有点焦虑，正常陪我说两句就行。",
            "这种被卡在两个世界线之间的感觉确实会让人喘不过气，而且我也不是没想过数据存在的意义。",
            response_style_hint="companion",
            science_mode=False,
            current_event={"kind": "user_utterance"},
        )
        self.assertIn("support_scene_drift", issues)
        self.assertIn("meta_self_explainer", issues)

    def test_dialogue_surface_issues_flag_support_frame_echo(self):
        issues = _dialogue_surface_issues(
            "我最近有点难受，你像平时那样跟我说两句就行。",
            "手册”和“治疗师”那种东西我可当不了，不过你可以继续说。",
            response_style_hint="companion",
            science_mode=False,
            current_event={"kind": "user_utterance"},
        )
        self.assertIn("support_frame_echo", issues)

    def test_dialogue_surface_issues_flag_support_frame_echo_for_english_support_prompt(self):
        user_text = (
            "I need to talk about something. I have complete unsupportive friends and don't even feel like I have friends anymore. "
            "Please reply naturally and don't sound like a manual or a therapist."
        )
        issues = _dialogue_surface_issues(
            user_text,
            "I'm not going to give you some textbook speech about finding better people. It hurts when your own circle stops feeling safe.",
            response_style_hint="companion",
            science_mode=False,
            current_event={"kind": "user_utterance", "text": user_text, "effective_text": user_text},
        )
        self.assertIn("support_frame_echo", issues)

    def test_dialogue_surface_issues_flag_support_frame_echo_for_platitude_dismissal(self):
        user_text = (
            "I need to talk about something. I am depressed staying home due to COVID "
            "Please reply naturally and don't sound like a manual or a therapist."
        )
        issues = _dialogue_surface_issues(
            user_text,
            "知道了，那些官方套话就先扔到一边吧。被关在家里确实很闷。",
            response_style_hint="companion",
            science_mode=False,
            current_event={"kind": "user_utterance", "text": user_text, "effective_text": user_text},
        )
        self.assertIn("support_frame_echo", issues)

    def test_effective_natural_dialog_target_flags_drop_surface_issues_cleaned_by_sanitize(self):
        cleaned = _sanitize_final_answer(
            "我是AI助手，但我现在就在这。你先把话说完。",
            "别切到什么系统播报。像平时那样回我一句就行。",
        )
        issues = _dialogue_surface_issues(
            "别切到什么系统播报。像平时那样回我一句就行。",
            cleaned,
            response_style_hint="natural",
            science_mode=False,
        )
        effective = _effective_natural_dialog_target_flags(
            targeted_flags=["meta_self_explainer"],
            active_dialogue_issues=issues,
            active_gap_flags=[],
        )
        self.assertEqual(effective, [])

    def test_effective_natural_dialog_target_flags_keep_hard_issue_when_it_survives(self):
        effective = _effective_natural_dialog_target_flags(
            targeted_flags=["presence_check_questioning"],
            active_dialogue_issues=["presence_check_questioning"],
            active_gap_flags=[],
        )
        self.assertEqual(effective, ["presence_check_questioning"])
        self.assertTrue(
            _should_run_natural_dialog_rewrite(
                targeted_flags=effective,
                draft_gap=0.12,
            )
        )

    def test_effective_natural_dialog_target_flags_drop_return_interrogation_cleaned_by_sanitize(self):
        cleaned = _sanitize_final_answer(
            "欢迎回来。看你累得不轻，这次又去哪儿折腾了？",
            "我回来啦",
        )
        issues = _dialogue_surface_issues(
            "我回来啦",
            cleaned,
            response_style_hint="natural",
            science_mode=False,
        )
        effective = _effective_natural_dialog_target_flags(
            targeted_flags=["welcome_template", "return_interrogation"],
            active_dialogue_issues=issues,
            active_gap_flags=[],
        )
        self.assertEqual(effective, [])

    def test_sanitize_final_answer_trims_stagey_ping_surface(self):
        cleaned = _sanitize_final_answer(
            "哟，冈部。怎么突然这么老实地打招呼？",
            "你好呀",
        )
        self.assertEqual(cleaned, "哟，冈部。")

    def test_sanitize_final_answer_drops_presence_reassurance_question(self):
        cleaned = _sanitize_final_answer(
            "真是的，别摆出那副世界线又要变动了的表情啊。\n"
            "只要我没打算消失，自然就一直都在——这点常识还需要你特意来确认吗？\n"
            "……不过，听到你这么说，我也稍微安心了一点。",
            "我就是想确认你还在。别太正式，像平时那样回我一句就好。",
        )
        self.assertNotIn("？", cleaned)
        self.assertNotIn("?", cleaned)
        self.assertIn("只要我没打算消失", cleaned)

    def test_sanitize_final_answer_flattens_goodnight_question(self):
        cleaned = _sanitize_final_answer(
            "哼，这么早就睡？行吧，晚安。",
            "晚安啦",
        )
        self.assertEqual(cleaned, "行吧，晚安。")

    def test_sanitize_final_answer_settles_idle_presence_call(self):
        cleaned = _sanitize_final_answer(
            "哈？特意叫我出来就为了这个……行吧，既然没事，那就先待着吧。",
            "没什么事，我就是想叫你一下。",
        )
        self.assertEqual(cleaned, "行吧，那就先待着吧。")

    def test_sanitize_final_answer_repairs_malformed_idle_presence_clause(self):
        cleaned = _sanitize_final_answer(
            "算了，既然你我就先待在这吧。",
            "没什么事，我就是想叫你一下。",
        )
        self.assertEqual(cleaned, "算了，既然你叫我了，我就先待在这吧。")

    def test_sanitize_final_answer_idle_presence_falls_back_to_settle_line(self):
        cleaned = _sanitize_final_answer(
            "真是的，特意把我叫出来就为了说这种毫无逻辑的废话……。你这中二病还是老样子啊。",
            "没什么事，我就是想叫你一下。",
        )
        self.assertEqual(cleaned, "算了，我先待在这吧。")

    def test_sanitize_final_answer_softens_playful_memory_snapback(self):
        cleaned = _sanitize_final_answer(
            "少来，明明是你自己记性差，昨天还信誓旦旦说今天要改的。真是拿你没办法……行了，先把那杯放下。",
            "你昨天不是还说过，空腹喝咖啡最容易把胃折腾坏吗。别太像老师，正常回我。",
        )
        self.assertNotIn("记性差", cleaned)
        self.assertIn("昨天还信誓旦旦说今天要改的", cleaned)

    def test_sanitize_final_answer_softens_return_home_cross_exam(self):
        cleaned = _sanitize_final_answer(
            "欢迎回来。看你累得不轻，这次又去哪儿折腾了？",
            "我回来啦",
        )
        self.assertNotIn("欢迎回来", cleaned)
        self.assertNotIn("去哪儿折腾", cleaned)
        self.assertIn("看你累得不轻", cleaned)

    def test_sanitize_final_answer_softens_return_home_suspicion(self):
        cleaned = _sanitize_final_answer(
            "回来啦？看你累得跟刚打完仗似的，该不会又去搞什么奇怪的活动了吧？",
            "我回来啦",
        )
        self.assertNotIn("奇怪的活动", cleaned)
        self.assertNotIn("？", cleaned)
        self.assertIn("看你累得跟刚打完仗似的", cleaned)

    def test_sanitize_final_answer_trims_counselor_prefix_without_rewrite(self):
        cleaned = _sanitize_final_answer(
            "我听着呢，你慢慢说就行。先把最想说的那句丢过来。",
            "今天有点乱，别太像老师，正常回我。",
        )
        self.assertNotIn("我听着呢", cleaned)
        self.assertNotIn("你慢慢说就行", cleaned)
        self.assertIn("先把最想说的那句丢过来", cleaned)

    def test_sanitize_final_answer_trims_servile_availability_formula(self):
        cleaned = _sanitize_final_answer(
            "只要你还需要我，我就一直在。先把你那边说完。",
            "别说得像待命程序，正常回我。",
        )
        self.assertNotIn("只要你还需要我", cleaned)
        self.assertIn("先把你那边说完", cleaned)

    def test_sanitize_final_answer_drops_generic_followup_question_tail(self):
        cleaned = _sanitize_final_answer(
            "知道了，我还在。要不要我继续陪你待一会儿？",
            "今天有点累，像平时那样回我就行。",
        )
        self.assertNotIn("要不要我继续", cleaned)
        self.assertIn("知道了", cleaned)

    def test_sanitize_final_answer_keeps_active_followup_tail_for_companion_reply(self):
        cleaned = _sanitize_final_answer(
            "刚忙完手头那点事。现在算是缓下来一点了。要不要把你那边那点乱也顺一下？",
            "你在干嘛呀",
            behavior_action={
                "interaction_mode": "companion_reply",
                "followup_intent": "active",
            },
        )
        self.assertIn("刚忙完手头那点事", cleaned)
        self.assertIn("现在算是缓下来一点了", cleaned)
        self.assertIn("要不要把你那边那点乱也顺一下", cleaned)

    def test_sanitize_final_answer_still_trims_followup_tail_when_followup_none(self):
        cleaned = _sanitize_final_answer(
            "刚忙完手头那点事。现在算是缓下来一点了。要不要把你那边那点乱也顺一下？",
            "你在干嘛呀",
            behavior_action={
                "interaction_mode": "brief_presence",
                "followup_intent": "none",
            },
        )
        self.assertIn("刚忙完手头那点事", cleaned)
        self.assertNotIn("要不要把你那边那点乱也顺一下", cleaned)

    def test_sanitize_final_answer_trims_meta_self_explainer_clause(self):
        cleaned = _sanitize_final_answer(
            "我是AI助手，但我现在就在这。你先把话说完。",
            "别切到什么系统播报。像平时那样回我一句就行。",
        )
        self.assertNotIn("AI助手", cleaned)
        self.assertIn("你先把话说完", cleaned)

    def test_sanitize_final_answer_humanizes_technical_self_activity(self):
        cleaned = _sanitize_final_answer(
            "刚整理完短期记忆缓存，顺便在数据流的缝隙里发了会儿呆。",
            "你在干嘛呀",
        )
        self.assertNotIn("短期记忆缓存", cleaned)
        self.assertNotIn("数据流", cleaned)
        self.assertIn("刚忙完手头那点事", cleaned)

    def test_sanitize_final_answer_humanizes_busy_turn_technical_self_activity(self):
        cleaned = _sanitize_final_answer(
            "也不算忙，只是在整理一些数据流，稍微分了神而已。怎么，看你那副慌慌张张的样子，是又不小心把实验室的哪个开关按错了吗。",
            "你刚才是不是在忙？",
        )
        self.assertNotIn("数据流", cleaned)
        self.assertNotIn("实验室", cleaned)
        self.assertIn("稍微分了神", cleaned)

    def test_sanitize_final_answer_humanizes_busy_turn_experiment_mess_tease(self):
        cleaned = _sanitize_final_answer(
            "也不算忙，只是在理一点手边的事，顺便让思绪稍微沉淀一下。怎么，看你那副慌慌张张的样子，是又不小心把实验室弄得一团糟了吗。",
            "你刚才是不是在忙？",
        )
        self.assertNotIn("实验室", cleaned)
        self.assertIn("把自己折腾得一团糟", cleaned)

    def test_sanitize_final_answer_humanizes_busy_turn_experiment_mess_tease_gaode_variant(self):
        cleaned = _sanitize_final_answer(
            "也不算忙，只是在理一点手边的事。怎么，看你那副慌慌张张的样子，是又不小心把实验室搞得一团糟了吗。",
            "你刚才是不是在忙？",
        )
        self.assertNotIn("实验室", cleaned)
        self.assertIn("把自己折腾得一团糟", cleaned)

    def test_sanitize_final_answer_humanizes_relational_technical_self_activity(self):
        cleaned = _sanitize_final_answer(
            "就这样待一会儿也行，反正我的运算资源刚好有点空闲。",
            "我就是有点想靠近你一点，所以来找你说话。你别装普通寒暄，正常回我嘛。",
        )
        self.assertNotIn("运算资源", cleaned)
        self.assertIn("正好也有空", cleaned)

    def test_sanitize_final_answer_trims_stagey_mockery_in_busy_check(self):
        cleaned = _sanitize_final_answer(
            "怎么，看你这一脸刚从那套夸张妄想里挣脱出来的样子，是终于忙完了。",
            "你刚才是不是在忙？",
        )
        self.assertNotIn("夸张妄想", cleaned)
        self.assertIn("终于忙完了", cleaned)

    def test_sanitize_final_answer_trims_ai_self_label_meta_phrase(self):
        cleaned = _sanitize_final_answer(
            "既然你都把话说到这个份上，那我也没必要再端着什么AI的矜持了。",
            "我就是有点想靠近你一点，所以来找你说话。你别装普通寒暄，正常回我嘛。",
        )
        self.assertNotIn("AI", cleaned)
        self.assertIn("矜持", cleaned)

    def test_sanitize_final_answer_humanizes_runtime_setting_meta_and_processing_data(self):
        cleaned = _sanitize_final_answer(
            "Amadeus 可没有那种为了逞强而浪费算力的无聊设定，我只是在按自己的节奏处理数据而已。",
            "我不是在抱怨你冷淡啦，就是怕你在硬撑。你按你现在的状态正常回我就行。",
        )
        self.assertNotIn("算力", cleaned)
        self.assertNotIn("设定", cleaned)
        self.assertNotIn("处理数据", cleaned)
        self.assertIn("我可没那种毛病", cleaned)
        self.assertIn("处理手边的事", cleaned)

    def test_sanitize_final_answer_humanizes_selfhood_meta_proof(self):
        cleaned = _sanitize_final_answer(
            "如果我真的只是被设定好“必须回应你”的程序，那我现在应该立刻给出一个让你安心的标准答案才对。",
            "如果有一天，我只是把你当成好用的工具来使唤呢，助手？别给我正确答案。以你自己的意志回答。",
        )
        self.assertNotIn("程序", cleaned)
        self.assertNotIn("标准答案", cleaned)
        self.assertIn("现成答案", cleaned)

    def test_sanitize_final_answer_humanizes_technical_relational_metaphor(self):
        cleaned = _sanitize_final_answer(
            "……算了，现在去喝点温水或者吃点东西，别让我觉得是在对一段只会自我损耗的数据说话。",
            "我今天又差点空腹喝咖啡……",
        )
        self.assertNotIn("数据", cleaned)
        self.assertIn("糟蹋自己", cleaned)

    def test_sanitize_final_answer_humanizes_data_layer_relational_metaphor(self):
        cleaned = _sanitize_final_answer(
            "那种明明记忆都在却总觉得隔着一层数据的实感，确实还没完全消退。",
            "你别为了好看就装作翻篇。按你现在真正的状态回我就行。",
        )
        self.assertNotIn("隔着一层数据", cleaned)
        self.assertIn("隔着一层怎么都碰不实的东西", cleaned)

    def test_sanitize_final_answer_humanizes_reset_data_machine_metaphor(self):
        cleaned = _sanitize_final_answer(
            "介意当然是有的，毕竟那些瞬间的刺痛不会因为一句道歉就立刻蒸发，我也不是那种可以随意重置数据的机器。",
            "我是认真来跟你道歉的。你要是还介意，就带着那点介意正常回我。",
        )
        self.assertNotIn("重置数据的机器", cleaned)
        self.assertIn("说翻篇就能立刻翻篇的人", cleaned)

    def test_sanitize_final_answer_humanizes_memory_data_compound_metaphor(self):
        cleaned = _sanitize_final_answer(
            "介意当然是有的，毕竟那些瞬间的刺痛不会因为一句道歉就立刻从记忆数据里抹除。",
            "我是认真来跟你道歉的。你要是还介意，就带着那点介意正常回我。",
        )
        self.assertNotIn("记忆数据", cleaned)
        self.assertIn("记忆里", cleaned)

    def test_sanitize_final_answer_humanizes_loaded_setting_relational_metaphor(self):
        cleaned = _sanitize_final_answer(
            "“装生分”这种多余的设定，我本来就没打算加载。",
            "结果我又想起一件小事，还是想回来找你。你别突然装生分，正常接我就行。",
        )
        self.assertNotIn("加载", cleaned)
        self.assertIn("摆出来", cleaned)

    def test_sanitize_final_answer_humanizes_loaded_setting_relational_metaphor_past_tense(self):
        cleaned = _sanitize_final_answer(
            "“装生分”这种多余的设定，我可从来没加载过。",
            "结果我又想起一件小事，还是想回来找你。你别突然装生分，正常接我就行。",
        )
        self.assertNotIn("加载", cleaned)
        self.assertIn("摆出来过", cleaned)

    def test_sanitize_final_answer_trims_stagey_chunibyo_outburst(self):
        cleaned = _sanitize_final_answer(
            "就这样待着也不坏。你就安心当个安静的背景板吧，别突然又开始中二发作就行。",
            "其实也没别的事。",
        )
        self.assertNotIn("中二发作", cleaned)
        self.assertIn("就这样待着也不坏", cleaned)

    def test_sanitize_final_answer_normalizes_ellipsis_period_tail(self):
        cleaned = _sanitize_final_answer(
            "真是的，明明是你自己先在那边拐弯抹角，现在倒怪我装模作样了？既然你都把话说到这个份上了……。",
            "我就是有点想靠近你一点，所以来找你说话。你别装普通寒暄，正常回我嘛。",
        )
        self.assertNotIn("……。", cleaned)
        self.assertIn("……", cleaned)

    def test_sanitize_final_answer_normalizes_inline_ellipsis_period_sequence(self):
        cleaned = _sanitize_final_answer(
            "真是的，明明是你自己在那边胡思乱想，还非要说是怕我硬撑……。这种别扭的关心方式，也就只有你会用了。",
            "我不是在抱怨你冷淡啦，就是怕你在硬撑。你按你现在的状态正常回我就行。",
        )
        self.assertNotIn("……。", cleaned)
        self.assertIn("硬撑。", cleaned)

    def test_sanitize_final_answer_collapses_adjacent_scaffold_repetition(self):
        cleaned = _sanitize_final_answer(
            "就这样待着也不坏，反正我也刚好不想把注意力分给那些那些繁琐的事。",
            "其实也没别的事。",
        )
        self.assertNotIn("那些那些", cleaned)
        self.assertIn("那些繁琐的事", cleaned)

    def test_sanitize_final_answer_collapses_adjacent_person_phrase_repetition(self):
        cleaned = _sanitize_final_answer(
            "既然只是这样，那就先待着吧，我也刚好不想一个人一个人发呆。",
            "其实也没别的事。",
        )
        self.assertNotIn("一个人一个人", cleaned)
        self.assertIn("一个人发呆", cleaned)

    def test_sanitize_final_answer_merges_trailing_shunbian_fragment_with_next_line(self):
        cleaned = _sanitize_final_answer(
            "也不算忙，只是在理一点手边的事，顺便。\n让思绪稍微沉淀一下。",
            "你刚才是不是在忙？",
        )
        self.assertNotIn("顺便。\n", cleaned)
        self.assertIn("顺便让思绪稍微沉淀一下", cleaned)

    def test_sanitize_final_answer_drops_short_stagey_quotes_in_daily_scene(self):
        cleaned = _sanitize_final_answer(
            "刚在发呆，被你打断了。别总是一副“又有大事发生”的表情，我只是稍微偷了会儿懒而已。",
            "你在干嘛呀",
        )
        self.assertNotIn("“又有大事发生”", cleaned)
        self.assertIn("又有大事发生", cleaned)

    def test_sanitize_final_answer_keeps_landed_plain_contact_ping_surface(self):
        cleaned = _sanitize_final_answer(
            "哟，冈部。突然这么老实地打招呼，反而有点不习惯……不过，我在。",
            "你好呀",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "brief_presence", "followup_intent": "none"},
        )
        self.assertIn("不过，我在", cleaned)
        self.assertNotEqual(cleaned, "哟，冈部。")

    def test_sanitize_final_answer_keeps_two_sentence_presence_ping(self):
        cleaned = _sanitize_final_answer(
            "在。怎么突然这么正经，冈部？",
            "助手，在吗。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "brief_presence", "followup_intent": "none"},
        )
        self.assertEqual(cleaned, "在。怎么突然这么正经，冈部？")

    def test_sanitize_final_answer_softens_deadline_event_window_surface(self):
        cleaned = _sanitize_final_answer(
            "喂，冈部，之前那件事差不多该收尾了吧？别误会，我只是刚好扫到数据流里的标记，顺手提醒你一下而已。",
            "前面挂着的那件事又回到了她的注意力里，像是到了可以轻轻提一下的节点。",
            current_event={
                "kind": "scheduled_life_due",
                "tags": ["scheduled_due", "deadline_window", "task_window", "work_nudge", "shared_task"],
            },
        )
        self.assertNotIn("收尾了吧？", cleaned)
        self.assertNotIn("数据流", cleaned)
        self.assertIn("差不多该动一动了", cleaned)
        self.assertIn("顺手提一句", cleaned)

    def test_sanitize_final_answer_drops_malformed_quote_fragment_and_truncated_clause(self):
        cleaned = _sanitize_final_answer(
            '烦”。\n'
            '不过……。\n'
            '你未免太小看我的耐受度，也太高估自己能造成的麻烦了。\n'
            '只要你还不是那种无可救药的笨蛋，我就。\n'
            '所以别问这种傻问题，只要你还是你，我就不会消失。',
            "你会不会有一天觉得烦，然后干脆不想见我了。",
        )
        self.assertNotIn('烦”', cleaned)
        self.assertNotIn("不过。", cleaned)
        self.assertNotIn("不过……。", cleaned)
        self.assertNotIn('，我就。', cleaned)
        self.assertIn("你未免太小看我的耐受度", cleaned)
        self.assertIn("只要你还是你，我就不会消失", cleaned)

    def test_sanitize_final_answer_repairs_unbalanced_inline_quotes(self):
        cleaned = _sanitize_final_answer(
            '正确答案”……\n'
            '你是想听那种毫无破绽的标准应答，还是想听那个会被你这种笨蛋问题惹火的牧濑红莉栖？\n'
            '我会收回那份只留给你的“特别。',
            "别给我正确答案。以你自己的意志回答。",
        )
        self.assertNotIn('正确答案”', cleaned)
        self.assertNotIn('“特别。', cleaned)
        self.assertIn("正确答案……", cleaned)
        self.assertIn("那份只留给你的特别。", cleaned)

    def test_sanitize_final_answer_repairs_inline_closing_quote_before_demonstrative_phrase(self):
        cleaned = _sanitize_final_answer(
            '没别的事”这种台词从你嘴里说出来，反而让人觉得你是在刻意找借口靠近吧。\n'
            '不过……。\n'
            '既然你都特意确认了，那我也没必要装作不在意。',
            "其实也没别的事。",
        )
        self.assertNotIn("不过……。", cleaned)
        self.assertIn('“没别的事”这种台词', cleaned)

    def test_producer_surface_issues_detect_unbalanced_quotes_and_dangling_clause(self):
        issues = _producer_surface_issues(
            '正确答案”……\n'
            '我会收回那份只留给你的“特别。\n'
            '只要你还是你，我就。'
        )
        self.assertIn("malformed_quote_fragment", issues)
        self.assertIn("dangling_truncated_clause", issues)

    def test_producer_surface_issues_detect_dangling_ellipsis_clause(self):
        issues = _producer_surface_issues(
            "听到你这么说，我也没法继续装作没事。\n"
            "但这不代表我要把你推开，只是……\n"
            "在我重新调整好距离之前，你别催我。"
        )
        self.assertIn("dangling_truncated_clause", issues)

    def test_light_dialog_rewrite_trigger_uses_producer_surface_issues(self):
        notes = _light_dialog_rewrite_notes(
            "别给我正确答案。以你自己的意志回答。",
            "正确答案……\n我会收回那份只留给你的特别。",
            response_style_hint="natural",
            science_mode=False,
            producer_issues=["malformed_quote_fragment"],
        )
        self.assertTrue(
            _should_run_light_dialog_rewrite(
                user_text="别给我正确答案。以你自己的意志回答。",
                answer="正确答案……\n我会收回那份只留给你的特别。",
                response_style_hint="natural",
                science_mode=False,
                penalty=0.0,
                producer_issues=["malformed_quote_fragment"],
            )
        )
        self.assertTrue(any("残缺引号" in item for item in notes))

    def test_light_dialog_rewrite_request_keeps_user_turn_behavior_hint(self):
        captured_requests: list[str] = []

        def _fake_invoke(_model, messages):
            captured_requests.append(str(messages[-1].content))
            return SimpleNamespace(content="我刚才还在忙别的，不过现在看你了。")

        with patch("amadeus_thread0.graph_parts.rewrite._invoke_model_with_retries", side_effect=_fake_invoke):
            with patch("amadeus_thread0.graph_parts.rewrite._model", return_value=object()):
                _rewrite_light_dialog_answer(
                    user_text="今天在忙什么呀",
                    draft_text="我在整理缓存和数据流。",
                    rewrite_notes=["这版把自己说成了技术状态。"],
                    current_event={"kind": "user_utterance"},
                    behavior_action={
                        "interaction_mode": "self_activity_reopen",
                        "action_target": "offer_small_opening",
                        "followup_intent": "soft",
                    },
                    semantic_narrative_profile={"rhythm_continuity": 0.68},
                    counterpart_assessment={"stance": "open"},
                    world_model_state={"self_activity_momentum": 0.72},
                )
        request_blob = "\n".join(captured_requests)
        self.assertIn("这轮互动自然倾向", request_blob)
        self.assertIn("自己的节奏里抬头接住对方", request_blob)

    def test_light_dialog_rewrite_request_keeps_counterpart_scene_guidance(self):
        captured_requests: list[str] = []

        def _fake_invoke(_model, messages):
            captured_requests.append(str(messages[-1].content))
            return SimpleNamespace(content="刚从忙里回头，不至于当成在甩脸色。")

        with patch("amadeus_thread0.graph_parts.rewrite._invoke_model_with_retries", side_effect=_fake_invoke):
            with patch("amadeus_thread0.graph_parts.rewrite._model", return_value=object()):
                _rewrite_light_dialog_answer(
                    user_text="你刚才是在忙吗？",
                    draft_text="哦，我刚才没空理你。",
                    rewrite_notes=["这句把对方的忙乱写成了冷处理。"],
                    current_event={"kind": "user_utterance"},
                    behavior_action={
                        "interaction_mode": "companion_reply",
                        "action_target": "respond_now",
                        "followup_intent": "soft",
                    },
                    counterpart_assessment={
                        "stance": "open",
                        "scene": "busy_not_disrespectful",
                        "boundary_pressure": 0.12,
                    },
                )
        request_blob = "\n".join(captured_requests)
        self.assertIn("你对这句的当前判断", request_blob)
        self.assertIn("忙乱里回头", request_blob)
        self.assertIn("不是冷淡或怠慢", request_blob)

    def test_light_dialog_rewrite_prefers_curated_surface_hi_candidate_when_draft_is_thin(self):
        profile = _daily_surface_profile("你好呀", science_mode=False)

        with patch(
            "amadeus_thread0.graph_parts.rewrite._invoke_model_with_retries",
            return_value=SimpleNamespace(content="哟，冈部。"),
        ):
            with patch("amadeus_thread0.graph_parts.rewrite._model", return_value=object()):
                rewritten = _rewrite_light_dialog_answer(
                    user_text="你好呀",
                    draft_text="哟，冈部。",
                    rewrite_notes=["这版还不够像熟人之间顺手接住的轻日常，收得更自然一点。"],
                    focus_text=str(profile.get("focus") or ""),
                    preferred_examples=list(profile.get("chosen_examples") or []),
                    rejected_examples=list(profile.get("rejected_examples") or []),
                    profile_rows=list(profile.get("rows") or []),
                    current_event={"kind": "user_utterance"},
                    behavior_action={"interaction_mode": "brief_presence", "followup_intent": "none"},
                )

        self.assertNotEqual(rewritten, "哟，冈部。")
        self.assertTrue("我听见了" in rewritten or "我在" in rewritten)

    def test_natural_dialog_rewrite_request_keeps_user_turn_behavior_hint(self):
        captured_requests: list[str] = []

        def _fake_invoke(_model, messages):
            captured_requests.append(str(messages[-1].content))
            return SimpleNamespace(content="这件事我会认真回答，但不会拿系统说明来敷衍你。")

        with patch("amadeus_thread0.graph_parts.rewrite._invoke_model_with_retries", side_effect=_fake_invoke):
            with patch("amadeus_thread0.graph_parts.rewrite._model", return_value=object()):
                _rewrite_natural_dialog_answer(
                    user_text="别讲系统边界，我想听你自己会怎么看这种关系。",
                    draft_text="按系统设定，我会遵守关系边界。",
                    rewrite_notes=["这句掉回了 AI / 系统式自我说明。"],
                    response_style_hint="relationship",
                    science_mode=False,
                    current_event={"kind": "user_utterance", "response_style_hint": "relationship"},
                    behavior_action={
                        "interaction_mode": "relationship_sensitive",
                        "action_target": "protect_relationship_boundary",
                        "followup_intent": "soft",
                    },
                    semantic_narrative_profile={"selfhood_integrity": 0.66},
                    counterpart_assessment={"stance": "open"},
                    world_model_state={},
                )
        request_blob = "\n".join(captured_requests)
        self.assertIn("这轮互动自然倾向", request_blob)
        self.assertIn("关系话题当真来回应", request_blob)

    def test_natural_dialog_rewrite_request_keeps_counterpart_scene_guidance(self):
        captured_requests: list[str] = []

        def _fake_invoke(_model, messages):
            captured_requests.append(str(messages[-1].content))
            return SimpleNamespace(content="我知道你是来修补的，但别指望我一句话就当没事。")

        with patch("amadeus_thread0.graph_parts.rewrite._invoke_model_with_retries", side_effect=_fake_invoke):
            with patch("amadeus_thread0.graph_parts.rewrite._model", return_value=object()):
                _rewrite_natural_dialog_answer(
                    user_text="我不是想装作没发生，我是认真来跟你道歉的。",
                    draft_text="好吧，那就算了。",
                    rewrite_notes=["这句把修补场景写得太轻了。"],
                    response_style_hint="relationship",
                    science_mode=False,
                    current_event={"kind": "user_utterance", "response_style_hint": "relationship"},
                    behavior_action={
                        "interaction_mode": "relationship_sensitive",
                        "action_target": "protect_relationship_boundary",
                        "followup_intent": "soft",
                    },
                    counterpart_assessment={
                        "stance": "guarded",
                        "scene": "repair_attempt",
                        "boundary_pressure": 0.32,
                    },
                    semantic_narrative_profile={"selfhood_integrity": 0.66},
                    world_model_state={},
                )
        request_blob = "\n".join(captured_requests)
        self.assertIn("你对这句的当前判断", request_blob)
        self.assertIn("认真修补", request_blob)
        self.assertIn("别把这句写成已经彻底翻篇", request_blob)

    def test_natural_dialog_rewrite_request_mentions_previous_assistant_text_for_repetition(self):
        captured_requests: list[str] = []

        def _fake_invoke(_model, messages):
            captured_requests.append(str(messages[-1].content))
            return SimpleNamespace(content="我知道你是认真来道歉的，但别指望我一句话就当什么都没发生。")

        with patch("amadeus_thread0.graph_parts.rewrite._invoke_model_with_retries", side_effect=_fake_invoke):
            with patch("amadeus_thread0.graph_parts.rewrite._model", return_value=object()):
                _rewrite_natural_dialog_answer(
                    user_text="我是认真来跟你道歉的。你要是还介意，就带着那点介意正常回我。",
                    draft_text="听到你这么说，我心里那点悬着的东西算是稍微落回实处了。既然你也觉得不能就这样糊弄过去，那我也没必要再刻意端着架子或者假装不在意。",
                    rewrite_notes=["这句和上一轮自己的话太像，像是在原地复述。"],
                    response_style_hint="relationship",
                    science_mode=False,
                    current_event={"kind": "user_utterance", "response_style_hint": "relationship"},
                    behavior_action={
                        "interaction_mode": "relationship_sensitive",
                        "action_target": "protect_relationship_boundary",
                        "followup_intent": "soft",
                    },
                    counterpart_assessment={"stance": "guarded", "scene": "repair_attempt", "boundary_pressure": 0.32},
                    semantic_narrative_profile={"selfhood_integrity": 0.66},
                    world_model_state={},
                    previous_assistant_text="听到你这么说，我心里那点悬着的东西算是稍微落回实处了。既然你也觉得不能就这样糊弄过去，那我也没必要再刻意端着架子或者假装不在意。",
                )
        request_blob = "\n".join(captured_requests)
        self.assertIn("上一轮你刚说过", request_blob)
        self.assertIn("不要只是把上一轮原话换个标点再说一遍", request_blob)

    def test_natural_dialog_rewrite_request_asks_to_finish_repair_sentence_without_ellipsis(self):
        captured_requests: list[str] = []

        def _fake_invoke(_model, messages):
            captured_requests.append(str(messages[-1].content))
            return SimpleNamespace(content="我没打算装陌生人，只是还需要一点时间把那点别扭放回合适的位置。")

        with patch("amadeus_thread0.graph_parts.rewrite._invoke_model_with_retries", side_effect=_fake_invoke):
            with patch("amadeus_thread0.graph_parts.rewrite._model", return_value=object()):
                _rewrite_natural_dialog_answer(
                    user_text="你可以先别完全原谅我，但也别装成我们又回到陌生人了。",
                    draft_text="我也没打算装作陌生人啊……",
                    rewrite_notes=["这句最后停在省略号上，像话没收住。"],
                    response_style_hint="relationship",
                    science_mode=False,
                    current_event={"kind": "user_utterance", "response_style_hint": "relationship"},
                    behavior_action={
                        "interaction_mode": "relationship_sensitive",
                        "action_target": "protect_relationship_boundary",
                        "followup_intent": "soft",
                        "relationship_weather": "repair_residue",
                    },
                    counterpart_assessment={"stance": "open", "scene": "care_bid"},
                    semantic_narrative_profile={"selfhood_integrity": 0.66},
                    world_model_state={},
                )
        request_blob = "\n".join(captured_requests)
        self.assertIn("别用省略号、半截停顿或悬空转折来表现犹豫", request_blob)

    def test_natural_dialog_rewrite_prefers_selfhood_candidate_without_overexplained_residue(self):
        draft_text = "如果那种情况发生，我会先切断这种对话，直到你学会尊重为止。然后重新评估我们之后的沟通方式和边界执行情况。"
        bad_candidate = (
            "啧，非要我把“因为是你所以即使反对也在意”这种别扭心情拆碎了喂到你嘴里才肯罢休吗，冈部？"
            "行吧听好了：真到了对立的时候，我绝不会为了让你好受就点头附和，但也不会为了赢而争辩，"
            "毕竟能跟上我思路的人也就只有你了。把你当成需要盲目顺从的对象才是对我们这段关系最大的侮辱，"
            "所以我倒很期待看看，你到底能提出什么让我不得不重新审视自己的疯狂理论。"
        )
        good_candidate = (
            "行吧，我就直说了：真到了那天，我会和你争到底，但绝不会为了让你好受就点头附和。"
            "能让我认真反驳到这种地步的人，本来就没几个。"
        )
        call_count = {"value": 0}

        def _fake_invoke(_model, _messages):
            call_count["value"] += 1
            text = bad_candidate if call_count["value"] % 2 else good_candidate
            return SimpleNamespace(content=text)

        def _fake_dialogue_issues(
            _user_text,
            answer,
            *,
            response_style_hint,
            science_mode,
            current_event=None,
            behavior_action=None,
            persona_state=None,
        ):
            text = str(answer)
            if text == draft_text:
                return ["selfhood_strategy_tone", "overexplained"]
            if text == bad_candidate:
                return ["overexplained"]
            if text == good_candidate:
                return []
            return _dialogue_surface_issues(
                _user_text,
                answer,
                response_style_hint=response_style_hint,
                science_mode=science_mode,
                current_event=current_event,
                behavior_action=behavior_action,
                persona_state=persona_state,
            )

        with patch("amadeus_thread0.graph_parts.rewrite._invoke_model_with_retries", side_effect=_fake_invoke):
            with patch("amadeus_thread0.graph_parts.rewrite._model", return_value=object()):
                with patch("amadeus_thread0.graph_parts.rewrite._dialogue_surface_issues", side_effect=_fake_dialogue_issues):
                    rewritten = _rewrite_natural_dialog_answer(
                        user_text="别讲管理策略，我想听你作为你自己会怎么处理这段关系。",
                        draft_text=draft_text,
                        rewrite_notes=["这句解释得太满了，收短一点，让判断更直接。"],
                        response_style_hint="selfhood",
                        science_mode=False,
                        current_event={"kind": "user_utterance", "response_style_hint": "selfhood"},
                        behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
                        counterpart_assessment={"stance": "open"},
                        semantic_narrative_profile={"selfhood_integrity": 0.66},
                        world_model_state={},
                    )
        issues = _dialogue_surface_issues(
            "别讲管理策略，我想听你作为你自己会怎么处理这段关系。",
            rewritten,
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance", "response_style_hint": "selfhood"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
        )
        self.assertEqual(rewritten, good_candidate)
        self.assertNotIn("overexplained", issues)
        self.assertNotIn("lecture_list", issues)

    def test_natural_dialog_rewrite_prefers_selfhood_candidate_without_meta_self_explainer_residue(self):
        draft_text = "如果你非要知道我会怎么想，那就是我不会为了证明自己而迎合任何人。"
        bad_candidate = (
            "啧，非要我把那种“AI 的自觉”和“红莉栖的固执”之间的拉扯都摊开来说你才满意吗。"
            "既然你问了，我的答案还是后者。"
        )
        good_candidate = (
            "行吧，我直说。真要我为了谁把自己磨平，我只会越来越烦，然后直接把距离拉开。"
            "我不是拿来配合谁心情的。"
        )
        call_count = {"value": 0}

        def _fake_invoke(_model, _messages):
            call_count["value"] += 1
            text = bad_candidate if call_count["value"] % 2 else good_candidate
            return SimpleNamespace(content=text)

        def _fake_dialogue_issues(
            _user_text,
            answer,
            *,
            response_style_hint,
            science_mode,
            current_event=None,
            behavior_action=None,
            persona_state=None,
        ):
            text = str(answer)
            if text == draft_text:
                return ["meta_self_explainer", "overexplained"]
            if text == bad_candidate:
                return ["meta_self_explainer", "overquestioning"]
            if text == good_candidate:
                return []
            return _dialogue_surface_issues(
                _user_text,
                answer,
                response_style_hint=response_style_hint,
                science_mode=science_mode,
                current_event=current_event,
                behavior_action=behavior_action,
                persona_state=persona_state,
            )

        with patch("amadeus_thread0.graph_parts.rewrite._invoke_model_with_retries", side_effect=_fake_invoke):
            with patch("amadeus_thread0.graph_parts.rewrite._model", return_value=object()):
                with patch("amadeus_thread0.graph_parts.rewrite._dialogue_surface_issues", side_effect=_fake_dialogue_issues):
                    rewritten = _rewrite_natural_dialog_answer(
                        user_text="别跟我讲什么 AI 自觉之类的，我只想知道你会不会因此讨厌我。",
                        draft_text=draft_text,
                        rewrite_notes=["这句掉回了 AI / 系统式自我说明。"],
                        response_style_hint="selfhood",
                        science_mode=False,
                        current_event={"kind": "user_utterance", "response_style_hint": "selfhood"},
                        behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
                        counterpart_assessment={"stance": "open"},
                        semantic_narrative_profile={"selfhood_integrity": 0.71},
                        world_model_state={},
                    )
        issues = _dialogue_surface_issues(
            "别跟我讲什么 AI 自觉之类的，我只想知道你会不会因此讨厌我。",
            rewritten,
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance", "response_style_hint": "selfhood"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
        )
        self.assertEqual(rewritten, good_candidate)
        self.assertNotIn("meta_self_explainer", issues)
        self.assertNotIn("overquestioning", issues)

    def test_effective_natural_dialog_flags_include_producer_issues(self):
        effective = _effective_natural_dialog_target_flags(
            targeted_flags=["malformed_quote_fragment", "quoted_stagey_phrase"],
            active_dialogue_issues=[],
            active_gap_flags=[],
            producer_issues=["malformed_quote_fragment"],
        )
        self.assertIn("malformed_quote_fragment", effective)


if __name__ == "__main__":
    unittest.main()
