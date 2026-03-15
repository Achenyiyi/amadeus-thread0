import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from amadeus_thread0.memory_store import MemoryStore
from amadeus_thread0.graph import (
    _build_task_prompt,
    _daily_surface_preference_lines,
    _daily_surface_profile,
    _dialogue_surface_issues,
    _effective_relationship_weather,
    _effective_natural_dialog_target_flags,
    _event_behavior_preference_lines,
    _is_light_free_dialog_turn,
    _is_plain_contact_ping,
    _light_dialog_rewrite_notes,
    _looks_like_daily_surface_scene,
    _sanitize_final_answer,
    _self_narrative_anchor_lines,
    _relationship_weather_rewrite_guidance,
    _should_run_light_dialog_rewrite,
    _should_run_natural_dialog_rewrite,
)


class DailySurfaceGatingTests(unittest.TestCase):
    def test_support_scenes_count_as_daily_surface(self):
        prompts = [
            "今天压力有点大",
            "我现在有点难受",
            "能陪我一会儿吗",
            "我不想一个人待着",
            "刚刚差点又崩溃了",
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

    def test_daily_surface_preference_lines_stay_abstract(self):
        lines = _daily_surface_preference_lines("你好呀", science_mode=False)
        self.assertLessEqual(len(lines), 1)
        self.assertTrue(lines)
        self.assertIn("这类轻场景更重视", lines[0])
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

    def test_plain_contact_ping_detects_simple_greetings_but_not_support_requests(self):
        self.assertTrue(_is_plain_contact_ping("你好呀"))
        self.assertTrue(_is_plain_contact_ping("在吗"))
        self.assertFalse(_is_plain_contact_ping("在干嘛"))
        self.assertFalse(_is_plain_contact_ping("能陪我一会儿吗"))

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
        self.assertIn("这轮说话会自然带着", prompt)
        self.assertIn("刚修补回来的那点小心和回暖还在", prompt)

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
        self.assertIn("事件余味", prompt)
        self.assertIn("刚好有个能一起做点什么的空当时", prompt)

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
        self.assertIn("当前上下文", prompt)
        self.assertIn("运行态摘记", prompt)
        self.assertIn("这轮说话的自然落点", prompt)
        self.assertNotIn("state_snapshot=", prompt)
        self.assertNotIn("relationship_memory:", prompt)
        self.assertNotIn("conflict_repair_memory:", prompt)
        self.assertNotIn("[memory]", prompt)

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
        self.assertIn("别把这句一下子写回热络", guarded)
        self.assertIn("熟悉感和回暖还在", warm)
        self.assertIn("别把这句改冷", warm)
        self.assertIn("别装成什么都没发生", repair)
        self.assertIn("保留一点小心和回暖", repair)

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
        self.assertIn("关系/自我余味", prompt)
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
        self.assertIn("共同记忆收成纯反呛", joined)

    def test_light_dialog_rewrite_notes_cover_technical_relational_metaphor(self):
        notes = _light_dialog_rewrite_notes(
            "我今天又差点空腹喝咖啡……",
            "……算了，现在去喝点温水或者吃点东西，别让我觉得是在对一段只会自我损耗的数据说话。",
            response_style_hint="natural",
            science_mode=False,
        )
        joined = " ".join(notes)
        self.assertIn("技术隐喻说关系", joined)

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

    def test_should_run_natural_dialog_rewrite_runs_for_single_overquestioning_issue(self):
        self.assertTrue(
            _should_run_natural_dialog_rewrite(
                targeted_flags=["overquestioning"],
                draft_gap=0.18,
            )
        )

    def test_should_run_natural_dialog_rewrite_runs_for_presence_questioning(self):
        self.assertTrue(
            _should_run_natural_dialog_rewrite(
                targeted_flags=["presence_check_questioning"],
                draft_gap=0.12,
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
            "哟，突然这么老实地打招呼……算了，我听见了。",
            "你好呀",
        )
        self.assertEqual(cleaned, "算了，我听见了。")

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

    def test_sanitize_final_answer_drops_malformed_quote_fragment_and_truncated_clause(self):
        cleaned = _sanitize_final_answer(
            '烦”。\n'
            '不过。\n'
            '你未免太小看我的耐受度，也太高估自己能造成的麻烦了。\n'
            '只要你还不是那种无可救药的笨蛋，我就。\n'
            '所以别问这种傻问题，只要你还是你，我就不会消失。',
            "你会不会有一天觉得烦，然后干脆不想见我了。",
        )
        self.assertNotIn('烦”', cleaned)
        self.assertNotIn("不过。", cleaned)
        self.assertNotIn('，我就。', cleaned)
        self.assertIn("你未免太小看我的耐受度", cleaned)
        self.assertIn("只要你还是你，我就不会消失", cleaned)


if __name__ == "__main__":
    unittest.main()
