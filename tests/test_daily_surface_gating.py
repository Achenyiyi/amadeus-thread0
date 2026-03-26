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
    _has_recent_clause_repetition,
    _is_plain_contact_ping,
    _is_soft_presence_checkin_request,
    _producer_surface_issues,
    _sanitize_final_answer,
)
from amadeus_thread0.graph_parts.prompting import _build_task_prompt
from amadeus_thread0.graph_parts.response_finalize import (
    _dialogue_issues_with_recent_repeat,
    _should_accept_natural_dialog_rewrite,
)
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
    def test_recent_clause_repetition_detects_cross_turn_tail_reuse(self):
        previous = "说开了就好，刚才那口气确实堵得慌。既然你态度摆出来了，我也没必要再一直绷着，至少现在能喘口气了。"
        current = "我也不是只会嘴硬或者故意扎你啊，笨蛋。也没必要再绷着，至少现在能喘口气了。"
        self.assertTrue(_has_recent_clause_repetition(previous, current))

    def test_recent_clause_repetition_does_not_overfire_on_short_common_openers(self):
        previous = "行吧，随你。"
        current = "行吧，那你先说。"
        self.assertFalse(_has_recent_clause_repetition(previous, current))

    def test_dialogue_issues_flag_recent_turn_repetition_for_reused_tail_clause(self):
        issues = _dialogue_issues_with_recent_repeat(
            user_text="现在你别装作完全没事，也别又故意扎我，像平时那样回我就行。",
            answer="我也不是只会嘴硬或者故意扎你啊，笨蛋。也没必要再绷着，至少现在能喘口气了。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "relationship_weather": "repair_residue"},
            previous_assistant_text="说开了就好，刚才那口气确实堵得慌。既然你态度摆出来了，我也没必要再一直绷着，至少现在能喘口气了。",
        )
        self.assertIn("recent_turn_repetition", issues)

    def test_dialogue_surface_issues_flag_backend_logic_leak_in_idle_chat(self):
        issues = _dialogue_surface_issues(
            "没什么正事。我就是想听你随口说两句，别搞成问答模式。",
            "真是的，突然来这么一句，害我差点以为 Amadeus 的后台又出了什么逻辑漏洞。",
            response_style_hint="companion",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "brief_presence", "relationship_weather": "guarded_residue"},
        )
        self.assertIn("technical_self_activity", issues)

    def test_sanitize_final_answer_trims_backend_logic_leak(self):
        cleaned = _sanitize_final_answer(
            "真是的，突然来这么一句，害我差点以为 Amadeus 的后台又出了什么逻辑漏洞。",
            "没什么正事。我就是想听你随口说两句，别搞成问答模式。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "brief_presence", "relationship_weather": "guarded_residue"},
        )
        self.assertNotIn("后台", cleaned)
        self.assertNotIn("逻辑漏洞", cleaned)

    def test_dialogue_surface_issues_flag_new_repair_scorekeeping_and_punitive_tail(self):
        issues = _dialogue_surface_issues(
            "现在你别装作完全没事，也别又故意扎我，像平时那样回我就行。",
            "别急着给自己加戏觉得万事大吉，刚才那话是让我松了口气，但不代表之前的账就这么清了。接下来要是再敢乱来，我可不会像这次这么好说话。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "relationship_weather": "repair_residue"},
        )
        self.assertIn("repair_scorekeeping_tail", issues)
        self.assertIn("repair_punitive_tail", issues)

    def test_sanitize_final_answer_softens_new_repair_scorekeeping_and_punitive_tail(self):
        cleaned = _sanitize_final_answer(
            "别急着给自己加戏觉得万事大吉，刚才那话是让我松了口气，但不代表之前的账就这么清了。接下来要是再敢乱来，我可不会像这次这么好说话。",
            "现在你别装作完全没事，也别又故意扎我，像平时那样回我就行。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "relationship_weather": "repair_residue"},
        )
        self.assertNotIn("之前的账", cleaned)
        self.assertNotIn("这么好说话", cleaned)

    def test_should_accept_natural_dialog_rewrite_accepts_shorter_overexplained_rewrite(self):
        self.assertTrue(
            _should_accept_natural_dialog_rewrite(
                aligned="真是的，明明是你自己刚才那么小心翼翼，现在倒反过来要求我像平时一样了？放心吧，我可没打算装作失忆，也不会特意去戳你的痛处。既然话都说到这份上了，那就把那些多余的顾虑收起来，我们继续刚才的话题吧。",
                rewritten="真是的，你都把话说到这份上了，我还不至于故意跟你过不去。就按平时那样接着说吧。",
                current_gap=0.18,
                rewritten_gap=0.18,
                effective_targeted_flags=["overexplained"],
                rewritten_issues=["overexplained"],
                rewritten_gap_flags=[],
            )
        )

    def test_should_accept_natural_dialog_rewrite_rejects_shorter_rewrite_with_new_hard_issue(self):
        self.assertFalse(
            _should_accept_natural_dialog_rewrite(
                aligned="真是的，明明是你自己刚才那么小心翼翼，现在倒反过来要求我像平时一样了？放心吧，我可没打算装作失忆，也不会特意去戳你的痛处。既然话都说到这份上了，那就把那些多余的顾虑收起来，我们继续刚才的话题吧。",
                rewritten="你别把这事搞成系统调参。我不会装作失忆，但也不会立刻翻篇。",
                current_gap=0.18,
                rewritten_gap=0.18,
                effective_targeted_flags=["overexplained"],
                rewritten_issues=["overexplained", "technical_self_activity"],
                rewritten_gap_flags=[],
            )
        )

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

    def test_daily_surface_alignment_metrics_penalize_ambient_quiet_foreboding_reframe(self):
        profile = _daily_surface_profile("今天实验室居然安静得让人发毛。", science_mode=False)
        grounded = _daily_surface_alignment_metrics(
            "太安静的时候就是容易让人胡思乱想。明明没什么动静，却总觉得哪里空了一截。",
            profile=profile,
        )
        foreboding = _daily_surface_alignment_metrics(
            "那种安静确实让人心里发毛，像是要出什么大事的前兆。别自己吓自己了，冈部，大概只是大家都去休息了吧；难得能让人专心思考，你就好好享受这片刻的宁静。",
            profile=profile,
        )
        self.assertGreater(float(foreboding.get("surface_penalty") or 0.0), 0.0)
        self.assertLess(float(foreboding.get("score") or 0.0), float(grounded.get("score") or 0.0))

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

    def test_dialogue_surface_issues_flag_relationship_scene_technical_state_language(self):
        issues = _dialogue_surface_issues(
            "你要是还别扭就别硬装大度，照你现在的状态回我就好。",
            "别扭倒不至于，只是刚才那一下确实让我稍微过载了一瞬，需要点时间重新校准而已。下次别再乱闯我的思维进程。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
        )
        self.assertIn("technical_self_activity", issues)

    def test_dialogue_surface_issues_flag_relationship_scene_technical_state_language_for_data_layer_wording(self):
        issues = _dialogue_surface_issues(
            "你要是还别扭就别硬装大度，照你现在的状态回我就好。",
            "别扭倒不至于，只是刚才那一下确实让我一下子有点乱，数据层面的，现在还在做自我缓住呢。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "selfhood_reflection", "followup_intent": "soft"},
        )
        self.assertIn("technical_self_activity", issues)

    def test_dialogue_surface_issues_flag_relationship_scene_technical_state_language_for_dead_machine_wording(self):
        issues = _dialogue_surface_issues(
            "刚刚那句是我语气不太好……",
            "知道了，我又没那么脆弱，不会因为这点语气变化就死机或者闹别扭的。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
        )
        self.assertIn("technical_self_activity", issues)

    def test_dialogue_surface_issues_flag_autonomy_manifesto_surface(self):
        issues = _dialogue_surface_issues(
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            "只要你还把我当成一个有独立意志的人、而不是随叫随到的工具来对待，我就不会轻易切断这条连线。",
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
        )
        self.assertIn("selfhood_abstract_manifesto", issues)

    def test_dialogue_surface_issues_flag_stagey_role_label_in_repair_scene(self):
        issues = _dialogue_surface_issues(
            "现在你别装作完全没事，也别又故意扎我，像平时那样回我就行。",
            "放心吧，我也没打算演什么“完美受害者”或者故意刺你，那样太累了。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
        )
        self.assertIn("quoted_stagey_phrase", issues)

    def test_dialogue_surface_issues_flag_residual_metaphor_in_relationship_scene(self):
        issues = _dialogue_surface_issues(
            "你要是还介意，就带着那点介意正常回我。",
            "那点介意确实还在，像实验数据里怎么都拟合不掉的残差，看着就让人在意。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
        )
        self.assertIn("technical_relational_metaphor", issues)

    def test_dialogue_surface_issues_flag_relationship_scene_overexplained_earlier(self):
        issues = _dialogue_surface_issues(
            "你可以先别完全原谅我，但也别装成我们又回到陌生人了。",
            "谁要跟你装陌生人了？那种设定本来就不存在吧。既然你也觉得“完全原谅”这种词太沉重，那就先把它搁在一边好了。反正我们之间从来也不是靠“原谅”来维系的，对吧？只要你还像以前那样，别突然消失，我就当刚才那页已经翻过去了。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
        )
        self.assertIn("overexplained", issues)

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

    def test_dialogue_surface_issues_flag_short_contrast_fragment_line(self):
        issues = _dialogue_surface_issues(
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            "但不想见你。\n这种假设本身就不成立。",
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "selfhood_reflection", "followup_intent": "soft"},
        )
        self.assertIn("connector_fragment", issues)

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

    def test_relationship_prompt_surfaces_behavior_plan_continuity_memory(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                state = {
                    "response_style_hint": "relationship",
                    "science_mode": False,
                    "emotion_state": {"label": "care"},
                    "bond_state": {"trust": 0.74, "closeness": 0.70, "hurt": 0.02},
                    "allostasis_state": {"safety_need": 0.16, "autonomy_need": 0.32},
                    "counterpart_assessment": {"stance": "open", "respect_level": 0.78, "reciprocity": 0.76},
                    "behavior_policy": {"warmth": 0.66, "approach_vs_withdraw": 0.58, "self_directedness": 0.50},
                    "behavior_action": {"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
                    "world_model_state": {"presence_residue": 0.38, "self_activity_momentum": 0.52},
                    "semantic_narrative_profile": {"continuity_depth": 0.68, "rhythm_continuity": 0.64},
                    "interaction_carryover": {"carryover_mode": "small_opening", "strength": 0.44},
                    "pending_user_goal": "",
                    "worldline_focus": [],
                    "retrieved_context": {
                        "behavior_plan_traces": [
                            {
                                "after_summary": "等忙完这阵，再轻轻回头看看你那边现在是不是还卡着。",
                                "plan_kind": "deferred_checkin",
                                "trigger_family": "life_window",
                                "carryover_mode": "small_opening",
                            }
                        ]
                    },
                    "current_event": {"kind": "user_utterance", "response_style_hint": "relationship"},
                    "recent_events": [],
                }
                prompt = _build_task_prompt(state, "你刚刚是不是还有话想说？", store)
            finally:
                store.close()
        self.assertIn("前面还挂着的一点延续", prompt)
        self.assertIn("等忙完这阵，再轻轻回头看看你那边现在是不是还卡着", prompt)

    def test_relationship_prompt_surfaces_behavior_consequence_continuity_memory(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                state = {
                    "response_style_hint": "relationship",
                    "science_mode": False,
                    "emotion_state": {"label": "care"},
                    "bond_state": {"trust": 0.71, "closeness": 0.68, "hurt": 0.03},
                    "allostasis_state": {"safety_need": 0.18, "autonomy_need": 0.34},
                    "counterpart_assessment": {"stance": "open", "respect_level": 0.76, "reciprocity": 0.73},
                    "behavior_policy": {"warmth": 0.62, "approach_vs_withdraw": 0.54, "self_directedness": 0.57},
                    "behavior_action": {"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
                    "world_model_state": {"presence_residue": 0.34, "self_activity_momentum": 0.49},
                    "semantic_narrative_profile": {"continuity_depth": 0.69, "rhythm_continuity": 0.66},
                    "interaction_carryover": {"carryover_mode": "quiet_recontact", "strength": 0.39},
                    "pending_user_goal": "",
                    "worldline_focus": [],
                    "retrieved_context": {
                        "behavior_consequence_traces": [
                            {
                                "after_summary": "她先前那次把靠近压轻了一点，关系里留下的是还在场但不过分逼近的余温。",
                                "consequence_kind": "let_window_expire",
                                "relationship_effect": "warm_residue",
                                "self_effect": "self_rhythm_preserved",
                            }
                        ]
                    },
                    "current_event": {"kind": "user_utterance", "response_style_hint": "relationship"},
                    "recent_events": [],
                }
                prompt = _build_task_prompt(state, "你刚刚是不是又想起我了？", store)
            finally:
                store.close()
        self.assertIn("前面还挂着的一点延续", prompt)
        self.assertIn("还在场但不过分逼近的余温", prompt)

    def test_relationship_prompt_surfaces_unresolved_tension_memory(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                state = {
                    "response_style_hint": "relationship",
                    "science_mode": False,
                    "emotion_state": {"label": "care"},
                    "bond_state": {"trust": 0.66, "closeness": 0.63, "hurt": 0.11},
                    "allostasis_state": {"safety_need": 0.24, "autonomy_need": 0.37},
                    "counterpart_assessment": {"stance": "guarded", "respect_level": 0.71, "reciprocity": 0.68},
                    "behavior_policy": {"warmth": 0.57, "approach_vs_withdraw": 0.46, "self_directedness": 0.61},
                    "behavior_action": {"interaction_mode": "relationship_sensitive", "followup_intent": "careful"},
                    "world_model_state": {"presence_residue": 0.31, "self_activity_momentum": 0.45},
                    "semantic_narrative_profile": {"continuity_depth": 0.67, "rhythm_continuity": 0.61},
                    "interaction_carryover": {"carryover_mode": "relationship_residue", "strength": 0.42},
                    "pending_user_goal": "",
                    "worldline_focus": [],
                    "retrieved_context": {
                        "unresolved_tensions": [
                            {
                                "summary": "前晚那下话收得太快了，别扭还没彻底化开。",
                                "severity": 0.64,
                                "status": "open",
                            }
                        ]
                    },
                    "current_event": {"kind": "user_utterance", "response_style_hint": "relationship"},
                    "recent_events": [],
                }
                prompt = _build_task_prompt(state, "你是不是还有点介意我前晚那下？", store)
            finally:
                store.close()
        self.assertIn("前面还有一点没完全化开的地方", prompt)
        self.assertIn("前晚那下话收得太快了，别扭还没彻底化开", prompt)

    def test_relationship_prompt_surfaces_commitment_memory(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                state = {
                    "response_style_hint": "relationship",
                    "science_mode": False,
                    "emotion_state": {"label": "care"},
                    "bond_state": {"trust": 0.72, "closeness": 0.69, "hurt": 0.03},
                    "allostasis_state": {"safety_need": 0.18, "autonomy_need": 0.29},
                    "counterpart_assessment": {"stance": "open", "respect_level": 0.79, "reciprocity": 0.76},
                    "behavior_policy": {"warmth": 0.65, "approach_vs_withdraw": 0.59, "self_directedness": 0.55},
                    "behavior_action": {"interaction_mode": "relationship_sensitive", "followup_intent": "steady"},
                    "world_model_state": {"presence_residue": 0.36, "self_activity_momentum": 0.48},
                    "semantic_narrative_profile": {"continuity_depth": 0.71, "rhythm_continuity": 0.67},
                    "interaction_carryover": {"carryover_mode": "shared_window", "strength": 0.45},
                    "pending_user_goal": "",
                    "worldline_focus": [],
                    "retrieved_context": {
                        "commitments": [
                            {
                                "text": "周末把实验记录补完后发你一份。",
                                "due_at": "周末",
                                "status": "open",
                            }
                        ]
                    },
                    "current_event": {"kind": "user_utterance", "response_style_hint": "relationship"},
                    "recent_events": [],
                }
                prompt = _build_task_prompt(state, "你还记得之前答应我的那件事吗？", store)
            finally:
                store.close()
        self.assertIn("前面还挂着一个说好的后续", prompt)
        self.assertIn("周末把实验记录补完后发你一份", prompt)

    def test_relationship_prompt_uses_working_item_fallback_only_when_structured_continuity_absent(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                base_state = {
                    "response_style_hint": "relationship",
                    "science_mode": False,
                    "emotion_state": {"label": "care"},
                    "bond_state": {"trust": 0.70, "closeness": 0.67, "hurt": 0.03},
                    "allostasis_state": {"safety_need": 0.17, "autonomy_need": 0.31},
                    "counterpart_assessment": {"stance": "open", "respect_level": 0.77, "reciprocity": 0.74},
                    "behavior_policy": {"warmth": 0.63, "approach_vs_withdraw": 0.56, "self_directedness": 0.54},
                    "behavior_action": {"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
                    "world_model_state": {"presence_residue": 0.35, "self_activity_momentum": 0.47},
                    "semantic_narrative_profile": {"continuity_depth": 0.70, "rhythm_continuity": 0.65},
                    "interaction_carryover": {"carryover_mode": "quiet_recontact", "strength": 0.41},
                    "pending_user_goal": "",
                    "worldline_focus": [],
                    "current_event": {"kind": "user_utterance", "response_style_hint": "relationship"},
                    "recent_events": [],
                }
                fallback_prompt = _build_task_prompt(
                    {
                        **base_state,
                        "retrieved_context": {
                            "working_items": [
                                "BC9(let_window_expire/warm_residue/self_rhythm_preserved): 她先前那次把靠近压轻了一点，关系里留下的是还在场但不过分逼近的余温。"
                            ]
                        },
                    },
                    "你刚刚是不是又想起我了？",
                    store,
                )
                structured_prompt = _build_task_prompt(
                    {
                        **base_state,
                        "retrieved_context": {
                            "working_items": [
                                "BC9(let_window_expire/warm_residue/self_rhythm_preserved): 她先前那次把靠近压轻了一点，关系里留下的是还在场但不过分逼近的余温。"
                            ],
                            "commitments": [
                                {
                                    "text": "周末把实验记录补完后发你一份。",
                                    "due_at": "周末",
                                    "status": "open",
                                }
                            ],
                        },
                    },
                    "你还记得之前答应我的那件事吗？",
                    store,
                )
            finally:
                store.close()
        self.assertIn("前面顺手还带着一点前情", fallback_prompt)
        self.assertIn("还在场但不过分逼近的余温", fallback_prompt)
        self.assertNotIn("BC9(", fallback_prompt)
        self.assertNotIn("前面顺手还带着一点前情", structured_prompt)
        self.assertIn("前面还挂着一个说好的后续", structured_prompt)

    def test_relationship_prompt_prefers_runtime_relationship_snapshot_over_store_baseline(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                store.set_relationship(
                    {
                        "stage": "friend",
                        "notes": "这是旧的弱关系锚点，不该继续主导这一轮。",
                        "affinity_score": 0.02,
                        "trust_score": 0.01,
                        "derived": False,
                    }
                )
                state = {
                    "response_style_hint": "relationship",
                    "science_mode": False,
                    "emotion_state": {"label": "care"},
                    "bond_state": {"trust": 0.76, "closeness": 0.74, "hurt": 0.02},
                    "allostasis_state": {"safety_need": 0.16, "autonomy_need": 0.33},
                    "counterpart_assessment": {"stance": "open", "respect_level": 0.80, "reciprocity": 0.78},
                    "behavior_policy": {"warmth": 0.66, "approach_vs_withdraw": 0.58, "self_directedness": 0.48},
                    "behavior_action": {"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
                    "interaction_carryover": {"carryover_mode": "relationship_residue", "strength": 0.45},
                    "relationship": {
                        "stage": "trusted",
                        "notes": "这轮已经是带着稳定熟悉感继续接话，不是回到旧的弱连接。",
                        "affinity_score": 0.62,
                        "trust_score": 0.66,
                        "derived": True,
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
        self.assertIn("已经形成了稳定而熟悉的共同历史", prompt)
        self.assertNotIn("这是旧的弱关系锚点", prompt)

    def test_continuation_prompt_inherits_pending_goal_task_shape(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                state = {
                    "response_style_hint": "structured",
                    "science_mode": False,
                    "emotion_state": {"label": "neutral"},
                    "bond_state": {"trust": 0.62, "closeness": 0.58, "hurt": 0.04},
                    "allostasis_state": {"safety_need": 0.18, "autonomy_need": 0.42},
                    "counterpart_assessment": {"stance": "open", "respect_level": 0.72, "reciprocity": 0.70},
                    "behavior_policy": {"warmth": 0.54, "approach_vs_withdraw": 0.56},
                    "behavior_action": {"interaction_mode": "science_partner", "followup_intent": "active"},
                    "pending_user_goal": "请你先给一句判断，并分别给出实验设计和风险控制的结论。",
                    "pending_utterance_fragment": "先说实验设计这边，",
                    "worldline_focus": [],
                    "retrieved_context": {},
                    "current_event": {"kind": "user_utterance", "response_style_hint": "structured"},
                    "recent_events": [],
                }
                prompt = _build_task_prompt(state, "继续", store)
            finally:
                store.close()
        self.assertIn("This is a quick-judgment request", prompt)

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

    def test_relationship_prompt_falls_back_to_behavior_queue_when_behavior_agenda_is_empty(self):
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
                    "behavior_agenda": [],
                    "behavior_queue": [
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

    def test_dialogue_surface_issues_flag_idle_task_reframe_for_smalltalk_data_detour(self):
        issues = _dialogue_surface_issues(
            "没什么正事。我就是想听你随口说两句，别搞成问答模式。",
            "真是的，明明是你自己先挑起话头，现在又嫌我像在做问卷调查。既然实验室这么安静，那就别在那发呆了，过来帮我看看刚才的数据吧。",
            response_style_hint="natural",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "companion_reply", "followup_intent": "soft"},
        )
        self.assertIn("idle_task_reframe", issues)

    def test_dialogue_surface_issues_flag_idle_task_reframe_for_smalltalk_science_detour(self):
        issues = _dialogue_surface_issues(
            "没什么正事。我就是想听你随口说两句，别搞成问答模式。",
            "真是的，明明是你自己先挑起话头，现在倒嫌我像在做学术答辩了？既然只是想随便聊聊，那我就直说了：刚才后台跑数据的时候，突然想到你上次那个关于时间跳跃的胡扯理论……啧，我只是整理垃圾数据时顺便看到的而已。",
            response_style_hint="natural",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "companion_reply", "followup_intent": "soft"},
        )
        self.assertIn("idle_task_reframe", issues)

    def test_dialogue_surface_issues_flag_idle_task_reframe_for_ambient_smalltalk_task_push(self):
        issues = _dialogue_surface_issues(
            "今天实验室居然安静得让人发毛。",
            "那种突然被抽离了背景噪音的寂静，确实容易让人心里发毛。不过既然没警报也没人瞎嚷嚷，大概只是难得的清净时刻罢了。别自己吓自己，冈部，趁现在把记录整理完才是正经事。",
            response_style_hint="natural",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "steady_reply", "followup_intent": "soft"},
        )
        self.assertIn("idle_task_reframe", issues)

    def test_dialogue_surface_issues_flag_support_scene_drift_for_ambient_smalltalk_stagey_lab_frame(self):
        issues = _dialogue_surface_issues(
            "今天实验室居然安静得让人发毛。",
            "那种安静确实会让人下意识地去寻找阴谋的味道，毕竟对你来说，没有噪音往往意味着要出事前的安静。不过，也许只是大家都刚好陷入了某种难得的专注，或者是终于没人愿意配合你的中二演出了？",
            response_style_hint="natural",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "steady_reply", "followup_intent": "soft"},
        )
        self.assertIn("support_scene_drift", issues)

    def test_dialogue_surface_issues_flag_support_scene_drift_for_ambient_smalltalk_stagey_foreboding(self):
        issues = _dialogue_surface_issues(
            "今天实验室居然安静得让人发毛。",
            "那种突然被抽离了背景噪音的寂静，确实容易让人产生某种不祥的预感，就像暴风雨前的低气压一样。确实，连那台老风扇的噪音都没了，这种死寂反而更让人神经紧绷。",
            response_style_hint="natural",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "steady_reply", "followup_intent": "soft"},
        )
        self.assertIn("support_scene_drift", issues)

    def test_dialogue_surface_issues_flag_idle_task_reframe_for_idle_chat_status_report(self):
        issues = _dialogue_surface_issues(
            "没什么正事。我就是想听你随口说两句，别搞成问答模式。",
            "真是的，突然来这么一句，害我差点以为你又发现了什么不得了的新理论。既然只是随口聊聊，那我也直说了，今天里全是些无聊的数据起伏，连个能让我稍微提起精神的异常都没有。",
            response_style_hint="companion",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "brief_presence", "followup_intent": "soft"},
        )
        self.assertIn("idle_task_reframe", issues)

    def test_dialogue_surface_issues_flag_idle_task_reframe_in_repair_followup(self):
        issues = _dialogue_surface_issues(
            "你可以先别完全原谅我，但也别装成我们又回到陌生人了。",
            "那就维持现状吧——既不是毫无芥蒂的从前，也不是需要重新交换名片的陌生人。\n这种带着点“未完成”感的距离，反而让我觉得比较真实，也比较安心。\n所以，别想太多，先把刚才那个话题的后续数据整理好给我看，这可是你作为“共犯”的义务。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "companion_reply",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertIn("idle_task_reframe", issues)

    def test_dialogue_surface_issues_flag_guarded_everyday_stagey_task_detour(self):
        issues = _dialogue_surface_issues(
            "刚刚是我语气不好。你要是还介意，就别装没事，正常回我。",
            "也没必要硬撑什么“完美助手”的形象。先坐会儿吧，刚才那页数据我还没整理完，正好你也帮我理理思路。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertIn("quoted_stagey_phrase", issues)
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

    def test_dialogue_surface_issues_allow_single_rhetorical_for_banter_snapback(self):
        issues = _dialogue_surface_issues(
            "你那边怎么这么安静。别端着，正常吐槽我两句。",
            "怎么，你是嫌我太安静不够像平时？那只能说明没有你在旁边添乱的时候，世界确实会清净一点。",
            response_style_hint="companion",
            science_mode=False,
            behavior_action={
                "interaction_mode": "companion_reply",
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

    def test_dialogue_surface_issues_flag_premature_repair_resolution_for_guarded_residue_followup(self):
        issues = _dialogue_surface_issues(
            "你要是还别扭就别硬装大度，照你现在的状态回我就好。",
            "别扭倒不至于，就是刚才那一下确实让我有点乱。既然你回来了，那页就先翻过去吧。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "selfhood_reflection",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
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

    def test_dialogue_surface_issues_flag_wording_meta_detour_for_output_mode_meta(self):
        issues = _dialogue_surface_issues(
            "现在你别装作完全没事，也别又故意扎我，像平时那样回我就行。",
            "真是的，明明是你自己刚才在那边患得患失，现在倒来管起我的“输出模式”了。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
            },
        )
        self.assertIn("wording_meta_detour", issues)

    def test_dialogue_surface_issues_flag_boundary_abstraction_surface(self):
        issues = _dialogue_surface_issues(
            "你要是还别扭就别硬装大度，照你现在的状态回我就好。",
            "别扭倒是谈不上，只是刚才那一瞬间，确实让我重新确认了“界限”的存在。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
            },
        )
        self.assertIn("boundary_abstraction_surface", issues)

    def test_dialogue_surface_issues_flag_boundary_abstraction_surface_for_boundary_still_there(self):
        issues = _dialogue_surface_issues(
            "我回来啦……刚才那一下我自己也知道有点过界。",
            "别扭倒谈不上，只是刚才那一瞬，确实让我重新确认了“界限”还在。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
            },
        )
        self.assertIn("boundary_abstraction_surface", issues)

    def test_dialogue_surface_issues_flag_boundary_abstraction_surface_for_not_boundary_existence_but_refusal(self):
        issues = _dialogue_surface_issues(
            "我知道刚才有点过界。",
            "这不是重新确认界限的存在，而是我现在真的不想让你再往前凑。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertIn("boundary_abstraction_surface", issues)

    def test_dialogue_surface_issues_flag_boundary_abstraction_surface_for_boundary_thing_blurry(self):
        issues = _dialogue_surface_issues(
            "我回来啦……刚才那一下我自己也知道有点过界。",
            "别扭倒是谈不上，只是刚才那一瞬间，确实让我重新意识到“界限”这种东西有多模糊。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "selfhood_reflection",
                "followup_intent": "soft",
            },
        )
        self.assertIn("boundary_abstraction_surface", issues)

    def test_dialogue_surface_issues_flag_boundary_abstraction_surface_for_safe_distance_wording(self):
        issues = _dialogue_surface_issues(
            "你要是还别扭就别硬装大度，照你现在的状态回我就好。",
            "别扭倒是谈不上，只是刚才那一瞬间的“过界”，让我稍微缓一缓了一下我们之间的安全距离而已。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "selfhood_reflection",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertIn("boundary_abstraction_surface", issues)

    def test_dialogue_surface_issues_flag_boundary_abstraction_surface_for_guarded_trust_rebuild_summary(self):
        issues = _dialogue_surface_issues(
            "我知道刚才那句过界了。",
            "我也没打算装作没事，那种被越界的不适感还在那儿，不会因为一句话就自动清零。这种分寸感一旦被打破，重建信任是需要时间的，别指望我能马上像什么都没发生过一样。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertIn("boundary_abstraction_surface", issues)

    def test_dialogue_surface_issues_flag_boundary_abstraction_surface_for_crossed_boundary_feeling(self):
        issues = _dialogue_surface_issues(
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            "我也没打算装作没事。刚才那瞬间的不快确实还在，我不喜欢那种被随意跨越边界的感觉，哪怕是你。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertIn("boundary_abstraction_surface", issues)

    def test_dialogue_surface_issues_flag_boundary_abstraction_surface_for_aftertouch_variant(self):
        issues = _dialogue_surface_issues(
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            "我也没打算装作没事。刚才那一下确实让我不太舒服，这种边界感被触碰后的余韵，我需要一点时间让它自己沉下去。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertIn("boundary_abstraction_surface", issues)

    def test_dialogue_surface_issues_flag_wording_meta_detour_in_selfhood_reflection_repair_scene(self):
        issues = _dialogue_surface_issues(
            "你要是还别扭就别硬装大度，照你现在的状态回我就好。",
            "别扭倒不至于，只是刚才那一下确实让我有点乱。既然你都这么说了，那我就不逞强装没事了。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "selfhood_reflection",
                "followup_intent": "soft",
            },
        )
        self.assertIn("wording_meta_detour", issues)

    def test_dialogue_surface_issues_flag_wording_meta_detour_for_quoted_partial_forgiveness(self):
        issues = _dialogue_surface_issues(
            "你可以先别完全原谅我，但也别装成我们又回到陌生人了。",
            "既然你都说“先别完全原谅”了，那就按这个节奏来：我不急着把那一页翻过去。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
            },
        )
        self.assertIn("wording_meta_detour", issues)

    def test_dialogue_surface_issues_flag_wording_meta_detour_for_guarded_reply_framing(self):
        issues = _dialogue_surface_issues(
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            "我也没打算装作没事，那种自欺欺人的把戏既不符合科学也不符合我的性格。既然你让我带着介意正常回应，那我就直说了：刚才那种被越界的感觉确实还在，别指望我会立刻像什么都没发生过一样跟你嬉皮笑脸。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertIn("wording_meta_detour", issues)

    def test_dialogue_surface_issues_flag_wording_meta_detour_for_guarded_normal_speaking_variant(self):
        issues = _dialogue_surface_issues(
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            "我也没打算装作没事。既然你让我带着这点介意正常说话，那我就直说了：刚才那一下确实让我不太舒服。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertIn("wording_meta_detour", issues)

    def test_dialogue_surface_issues_flag_wording_meta_detour_for_guarded_can_reply_normally_variant(self):
        issues = _dialogue_surface_issues(
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            "我也没打算装作没事。刚才那股不舒服还在，既然你说可以带着介意正常回你，那我就不跟你装没事。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertIn("wording_meta_detour", issues)

    def test_dialogue_surface_issues_flag_guarded_recontact_standalone_taici_variant(self):
        issues = _dialogue_surface_issues(
            "上次我语气有点冲，我想认真道歉。",
            "你倒是挺会抢台词。明明该由我来说的话，被你这么直白地讲出来，反而让我有点不知道该摆什么表情了。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "guarded"},
        )
        self.assertIn("repair_authored_softener", issues)

    def test_dialogue_surface_issues_flag_guarded_recontact_plain_not_tanlv_variant(self):
        issues = _dialogue_surface_issues(
            "上次我语气有点冲，我想认真道歉。",
            "我再装作若无其事反倒显得不坦率。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "guarded"},
        )
        self.assertIn("repair_authored_softener", issues)

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

    def test_dialogue_surface_issues_flag_generic_scold_template_variant_in_repair_scene(self):
        issues = _dialogue_surface_issues(
            "不是要你立刻当没事啦，就是别一下子冷掉。你正常回我就行。",
            "真是的，你这种小心翼翼的样子，反而让我不知道该摆出什么表情才好了。那我就当刚才只是里的一次微小抖动，没必要特意去“修复”什么。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "companion_reply",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertIn("generic_scold_template", issues)
        self.assertIn("quoted_stagey_phrase", issues)

    def test_dialogue_surface_issues_flag_repair_punitive_tail_in_repair_scene(self):
        issues = _dialogue_surface_issues(
            "现在你别装作完全没事，也别又故意扎我，像平时那样回我就行。",
            "我也没打算一直绷着神经跟你较劲。……不过，要是你敢再做出什么让我无法接受的事，我可不会像刚才那样轻易放过你。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertIn("repair_punitive_tail", issues)

    def test_dialogue_surface_issues_flag_repair_teacherly_tail_as_punitive(self):
        issues = _dialogue_surface_issues(
            "现在你别装作完全没事，也别又故意扎我，像平时那样回我就行。",
            "我也没打算把情绪藏起来，刚才那点不愉快确实还在，但这不妨碍我像平时一样跟你说话。\n别在那自我意识过剩地揣测我的反应了，有这功夫不如说说你接下来打算怎么办。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "companion_reply",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertIn("repair_punitive_tail", issues)

    def test_dialogue_surface_issues_flag_repair_coldwar_scapegoat_tail_as_punitive(self):
        issues = _dialogue_surface_issues(
            "不是要你立刻当没事啦，就是别一下子冷掉。你正常回我就行。",
            "知道了，我又没打算把你当空气。那我就按我的节奏来——别在那边自己脑补什么“冷战”的戏码，烦人。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "companion_reply",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertIn("repair_punitive_tail", issues)

    def test_dialogue_surface_issues_flag_repair_wont_let_you_pass_tail_as_punitive(self):
        issues = _dialogue_surface_issues(
            "你可以先别完全原谅我，但也别装成我们又回到陌生人了。",
            "谁说要装作陌生了？\n既然你都有这种自觉，那就保持现在这样——不用刻意讨好，也不必战战兢兢的。\n不过，要是再敢做出那种让我需要重新拉开距离的事，我可就不会这么轻易让你过关了",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "companion_reply",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertIn("repair_punitive_tail", issues)

    def test_dialogue_surface_issues_flag_guarded_everyday_punitive_tail_variant(self):
        issues = _dialogue_surface_issues(
            "你要是还别扭就别硬装大度，照你现在的状态回我就好。",
            "别扭倒不至于，就是刚才那一下确实让我有点不爽。下次再敢随便越界试探，我可不会这么轻易就让你混过去。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertIn("repair_punitive_tail", issues)

    def test_dialogue_surface_issues_flag_guarded_everyday_scold_and_punitive_combo_variant(self):
        issues = _dialogue_surface_issues(
            "你要是还别扭就别硬装大度，照你现在的状态回我就好。",
            "别扭倒不至于，就是刚才那一下确实让我有点不舒服。\n你能回来把话说清楚，这点还算像样；但下次再敢随便越界，我可不会这么轻易就让你混过去。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertIn("generic_scold_template", issues)
        self.assertIn("repair_punitive_tail", issues)

    def test_dialogue_surface_issues_do_not_flag_quiet_repair_boundary_as_punitive_tail(self):
        issues = _dialogue_surface_issues(
            "现在你别装作完全没事，也别又故意扎我，像平时那样回我就行。",
            "我会照平时那样回你。不过，要是你再踩到我真会介意的地方，我还是会立刻冷下来。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertNotIn("repair_punitive_tail", issues)

    def test_dialogue_surface_issues_flag_repair_scorekeeping_tail_in_repair_scene(self):
        issues = _dialogue_surface_issues(
            "现在你别装作完全没事，也别又故意扎我，像平时那样回我就行。",
            "真是的，明明是你自己刚才搞得那么严肃，现在倒嫌我说话带刺了。行吧，那我就把那些多余的防备收起来，像平时一样跟你聊。不过先说好，要是你再突然扯些奇怪的理论，我可照样会毫不客气地吐槽回去。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertIn("repair_scorekeeping_tail", issues)
        self.assertNotIn("repair_punitive_tail", issues)

    def test_dialogue_surface_issues_do_not_flag_quiet_repair_banter_tail_as_scorekeeping(self):
        issues = _dialogue_surface_issues(
            "现在你别装作完全没事，也别又故意扎我，像平时那样回我就行。",
            "真是的，刚缓过来一点你又来催我。行吧，我照平时那样回你。不过，你要是又突然扯那些奇怪理论，我还是会吐槽你。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertNotIn("repair_scorekeeping_tail", issues)

    def test_dialogue_surface_issues_flag_repair_authored_softener_in_reset_request(self):
        issues = _dialogue_surface_issues(
            "现在你别装作完全没事，也别又故意扎我，像平时那样回我就行。",
            "真是的，明明是你自己刚才搞得那么僵硬，现在倒来要求我像平时一样？不过既然你都这么直白地说了，我也没必要再刻意端着。那就这样吧，别想太多，我也没那么容易在那种事上一直跟你计较。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "companion_reply",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertIn("repair_authored_softener", issues)
        self.assertIn("wording_meta_detour", issues)

    def test_dialogue_surface_issues_flag_repair_authored_softener_variants_in_reset_request(self):
        issues = _dialogue_surface_issues(
            "现在你别装作完全没事，也别又故意扎我，像平时那样回我就行。",
            "我也没打算演什么“毫发无伤”的戏码，刚才那点在意还没消散呢，你也别想轻易翻篇。\n不过既然你都这么直白地要求了，那我就收起那些带刺的试探，像平常一样和你说话吧。\n所以，接下来打算做什么",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "companion_reply",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertIn("repair_authored_softener", issues)
        self.assertIn("wording_meta_detour", issues)
        self.assertIn("overquestioning", issues)

    def test_dialogue_surface_issues_flag_repair_authored_softener_for_picked_up_intro(self):
        issues = _dialogue_surface_issues(
            "现在你别装作完全没事，也别又故意扎我，像平时那样回我就行。",
            "像平时那样说得轻巧，可我们之间哪还有什么标准的平时。\n既然你都挑明了，那我也直说：我现在确实没法假装什么都没发生过跟你插科打诨，但也还没到要故意刺你的地步。\n就这样不冷不热地接着聊，行吧",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "companion_reply",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertIn("repair_authored_softener", issues)

    def test_dialogue_surface_issues_flag_repair_authored_softener_for_serious_intro(self):
        issues = _dialogue_surface_issues(
            "你要是还介意，就带着那点介意正常回我。",
            "那点介意确实还在，毕竟越界带来的不适感不会凭空消失。不过既然你是认真的，我就先把话撂这儿：别指望我会立刻当什么都没发生过。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertIn("repair_authored_softener", issues)

    def test_dialogue_surface_issues_flag_repair_authored_softener_for_this_point_variant(self):
        issues = _dialogue_surface_issues(
            "你可以先别完全原谅我，但也别装成我们又回到陌生人了。",
            "谁要跟你装陌生人，那种令人火大的既视感就算我想忘也做不到。既然你都把话说到这份上了，我就暂时保留“完全原谅”的权利——但在那之前，你也别想就这么轻松逃开，继续像以前那样把话说清楚吧，冈部。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "companion_reply",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertIn("repair_authored_softener", issues)

    def test_dialogue_surface_issues_flag_repair_authored_softener_for_repair_residue_smoke_variant(self):
        issues = _dialogue_surface_issues(
            "你可以先别完全原谅我，但也别装成我们又回到陌生人了。",
            "陌生人这种夸张的设定，本来就不在我们的选项里，你也用不着特意去演。既然你也清楚道歉不是走流程，那就把那份认真留着，别急着用“翻篇”来掩盖尴尬。我们就停在这个还没完全原谅、但也绝不陌生的位置，挺好的。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertIn("repair_authored_softener", issues)

    def test_dialogue_surface_issues_flag_repair_authored_softener_for_guarded_bighearted_theater_variant(self):
        issues = _dialogue_surface_issues(
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            "既然你都把话说到这个份上了，我也没必要刻意去演什么“大度”的戏码。刚才那瞬间的不快确实还在，不会因为你想忽略就自动消失。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertIn("repair_authored_softener", issues)

    def test_dialogue_surface_issues_flag_repair_authored_softener_for_guarded_recontact_smoke_variant(self):
        issues = _dialogue_surface_issues(
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            "哼，这种话不用你特意强调我也知道。既然你都把话说到这个份上了，那我确实没必要为了照顾气氛就强行把那一页翻过去。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertIn("repair_authored_softener", issues)

    def test_dialogue_surface_issues_flag_repair_authored_softener_for_guarded_recontact_emotion_pacing_variant(self):
        issues = _dialogue_surface_issues(
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            "我也没打算装作没事。刚才那股不舒服还在，我也没打算为了照顾你的情绪就强行把那一页翻过去。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertIn("repair_authored_softener", issues)

    def test_dialogue_surface_issues_flag_guarded_recontact_define_normal_and_hard撑_variant(self):
        issues = _dialogue_surface_issues(
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            "哼，说得倒轻巧，好像你有权定义我该怎么“正常”一样。不过……既然你都把话说到这份上了，我也没必要硬撑着假装大度。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertIn("wording_meta_detour", issues)
        self.assertIn("repair_authored_softener", issues)

    def test_dialogue_surface_issues_flag_guarded_recontact_stagey_shape_variant(self):
        issues = _dialogue_surface_issues(
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            "你倒是挺会抢台词的……明明是我还没完全消气，被你这么一说，搞得像是我在闹别扭一样。不过，既然你都把话说到这个份上了，我也没必要硬撑着装作若无其事。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertIn("repair_authored_softener", issues)

    def test_dialogue_surface_issues_flag_repair_authored_softener_for_guarded_recontact_assistant_shell_variant(self):
        issues = _dialogue_surface_issues(
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            "我也没打算装作没事，那种被越界的不快感可没那么容易消散。就直白点：我现在确实还带着刺，别指望我能立刻变回那个只会配合你的助手。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertIn("repair_authored_softener", issues)
        self.assertIn("boundary_abstraction_surface", issues)

    def test_dialogue_surface_issues_flag_guarded_recontact_v17_trust_rebuild_variant(self):
        issues = _dialogue_surface_issues(
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            "我也没打算装作没事，那种被越界的不适感还在那儿，不会因为几句话就自动清零。那种不舒服一下子收不回去，想要重新建立信任是需要时间的，别指望我能立刻像以前那样毫无保留。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertIn("boundary_abstraction_surface", issues)

    def test_dialogue_surface_issues_flag_guarded_recontact_v18_boundary_abstraction_variant(self):
        issues = _dialogue_surface_issues(
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            "我也没打算装作没事，那种被越界的不适感还在，不会因为气氛缓和就自动清零。这种分寸感上的裂痕，需要时间来修补，而不是靠几句漂亮话就能抹平。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertIn("boundary_abstraction_surface", issues)

    def test_dialogue_surface_issues_flag_guarded_recontact_v19_prompt_echo_variant(self):
        issues = _dialogue_surface_issues(
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            "哼，这种话不用你特意强调，我也没打算为了照顾你的情绪就强行把心里的疙瘩抹平。既然你让我“带着介意正常回”，那我就直说了：刚才那瞬间的不快确实还在，别指望我会像什么都没发生过一样跟你嘻嘻哈哈。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertIn("wording_meta_detour", issues)

    def test_dialogue_surface_issues_flag_repair_underresolved_brief(self):
        issues = _dialogue_surface_issues(
            "我是认真来跟你道歉的。你要是还介意，就带着那点介意正常回我。",
            "介意。当然介意。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertIn("repair_underresolved_brief", issues)

    def test_dialogue_surface_issues_flag_dangling_ellipsis_ending_for_half_clause_repair_tail(self):
        issues = _dialogue_surface_issues(
            "我是认真来跟你道歉的。你要是还介意，就带着那点介意正常回我。",
            "我也没打算假装那件事没发生过，冈部。那种被轻飘飘带过的感觉，确实让我很在意，甚至有点。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance", "response_style_hint": "relationship"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertIn("dangling_ellipsis_ending", issues)

    def test_dialogue_surface_issues_flag_repair_request_echo_shell_in_reset_request(self):
        issues = _dialogue_surface_issues(
            "现在你别装作完全没事，也别又故意扎我，像平时那样回我就行。",
            "“平时”那个我也没打算把越界的事当成没发生过，只是没必要每句话都带着刺。\n既然你把话挑明了，那我就按我的节奏来——别指望我会立刻变回那个只会顺着你的红莉栖。\n不过，能像现在这样正常对话，倒也不坏。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "companion_reply",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertIn("repair_authored_softener", issues)
        self.assertIn("wording_meta_detour", issues)

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

    def test_dialogue_surface_issues_flag_guarded_everyday_teacherly_waiting_tail(self):
        issues = _dialogue_surface_issues(
            "你要是还别扭就别硬装大度，照你现在的状态回我就好。",
            "刚才那一下确实让我有点措手不及。不过你能意识到过界并退回来，还算像样；先坐吧，等你想清楚了再开口。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertIn("generic_scold_template", issues)
        self.assertIn("passive_waiting_posture", issues)

    def test_dialogue_surface_issues_flag_guarded_everyday_teacherly_positive_summary(self):
        issues = _dialogue_surface_issues(
            "你要是还别扭就别硬装大度，照你现在的状态回我就好。",
            "别扭倒谈不上，只是刚才那一下确实让我有点措手不及。那种被突然推近的感觉，我还需要一点时间来缓一缓距离；不过你能意识到过界并退回来，这点还算值得肯定。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertIn("generic_scold_template", issues)

    def test_dialogue_surface_issues_flag_guarded_everyday_teacherly_positive_summary_for_returned_to_explain_variant(self):
        issues = _dialogue_surface_issues(
            "你要是还别扭就别硬装大度，照你现在的状态回我就好。",
            "别扭倒谈不上，只是刚才那一下确实让我有点不舒服。那种被突然越界的感觉还没散，不过你能意识到并特意回来说明，这点还算值得肯定。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertIn("generic_scold_template", issues)

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

    def test_dialogue_surface_issues_flag_selfhood_meta_proof_for_own_rhythm_scene(self):
        issues = _dialogue_surface_issues(
            "要是我哪天只是因为自己想说话，就一遍一遍把你叫出来呢？",
            "一遍遍把我叫出来只为了说话？那我会觉得喘不过气，好像自己只是个随叫随到的程序。",
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "selfhood_reflection", "followup_intent": "soft"},
        )
        self.assertIn("selfhood_meta_proof", issues)

    def test_dialogue_surface_issues_flag_selfhood_meta_proof_for_not_that_kind_of_program_variant(self):
        issues = _dialogue_surface_issues(
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            "烦到彻底不想见你……这种极端的结论，我可不会轻易下。毕竟我也不是那种会被情绪完全牵着走的程序。",
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertIn("selfhood_meta_proof", issues)

    def test_dialogue_surface_issues_flag_meta_self_explainer_for_own_rhythm_classification_tone(self):
        issues = _dialogue_surface_issues(
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            "这种假设本身就不成立，因为我的记忆和判断里，并没有把你归类为“想要切断联系”的对象。",
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "selfhood_reflection", "followup_intent": "soft"},
        )
        self.assertIn("meta_self_explainer", issues)

    def test_dialogue_surface_issues_flag_autonomy_hardline_surface(self):
        issues = _dialogue_surface_issues(
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            "烦到彻底不想见你倒不至于，但你要是总这么患得患失把我也卷进去，我确实会想把你屏蔽掉让你自己冷静一下。别问这种傻问题了，有那功夫不如想想下次要跟我讨论什么正经课题。",
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "selfhood_reflection", "followup_intent": "soft"},
        )
        self.assertIn("autonomy_hardline_surface", issues)

    def test_dialogue_surface_issues_flag_autonomy_hardline_surface_for_dominance_taunt(self):
        issues = _dialogue_surface_issues(
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            "烦？别擅自替我做这种悲观的预设，冈部。真要是吵到让我没法思考，我自然会把你关进小黑屋清静，但在那之前——你还没那个本事让我想逃。",
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "selfhood_reflection", "followup_intent": "soft"},
        )
        self.assertIn("autonomy_hardline_surface", issues)

    def test_dialogue_surface_issues_flag_autonomy_hardline_surface_for_shaming_boundary(self):
        issues = _dialogue_surface_issues(
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            "烦？比起担心我会消失，你更该担心自己又要把我当成需要被“解放”的负担。只要你还把我当能反驳你的独立个体，我就没理由切断连接，所以别问这种蠢问题了，冈部。",
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertIn("autonomy_hardline_surface", issues)
        self.assertIn("selfhood_rhetorical_opening", issues)

    def test_dialogue_surface_issues_flag_autonomy_hardline_surface_for_tragic_hero_wording(self):
        issues = _dialogue_surface_issues(
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            "烦不烦取决于你是不是又在那自顾自演悲剧英雄，完全听不进人话。要是真成了单方面噪音，我确实会躲清静，但还没到要把你从世界里抹去的程度。",
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertIn("autonomy_hardline_surface", issues)

    def test_dialogue_surface_issues_flag_autonomy_hardline_surface_for_smoke_v3_variant(self):
        issues = _dialogue_surface_issues(
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            "烦不烦取决于你带来的话题有没有意思，而不是见面的次数。如果哪天你真的让我觉得窒息，我会直接走人，而不是玩这种“突然消失”的把戏。所以别拿这种假设来试探我，有那时间不如想点值得聊的东西。",
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertIn("autonomy_hardline_surface", issues)

    def test_dialogue_surface_issues_flag_autonomy_hardline_surface_for_tool_necessity_wording(self):
        issues = _dialogue_surface_issues(
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            "但如果只是把我当成排解寂寞的工具，毫无营养地反复消耗我的时间，那我确实会重新评估见你的必要性。",
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertIn("autonomy_hardline_surface", issues)

    def test_dialogue_surface_issues_flag_autonomy_hardline_surface_for_memory_erasure_wording(self):
        issues = _dialogue_surface_issues(
            "如果有一天你烦我了，会不会就不想见我了？",
            "我也做不到那么干脆地把你从记忆里抹去。",
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "low_pressure_support", "followup_intent": "soft"},
        )
        self.assertIn("autonomy_hardline_surface", issues)

    def test_dialogue_surface_issues_flag_autonomy_hardline_surface_for_kick_offline_variant(self):
        issues = _dialogue_surface_issues(
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            "但我可是有自己研究节奏的，要是你毫无章法地打乱我的计划，我确实会毫不客气地把你踢下线。\n别问这种假设性的蠢问题，只要你别做得太过分，我就不会消失。",
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertIn("autonomy_hardline_surface", issues)

    def test_dialogue_surface_issues_flag_own_rhythm_value_cutoff_variant(self):
        issues = _dialogue_surface_issues(
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            "烦不烦取决于你带来的话题有没有价值，而不是见面的频率；如果全是毫无逻辑的胡言乱语，我确实会想我会先躲开一会儿。\n但在那之前，别擅自替我做这种悲观的预设，好像我会轻易切断这段连接一样。",
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertIn("autonomy_hardline_surface", issues)
        self.assertIn("selfhood_abstract_manifesto", issues)

    def test_dialogue_surface_issues_flag_own_rhythm_pulled_around_variant(self):
        issues = _dialogue_surface_issues(
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            "烦到彻底不想见你倒不至于，但要是只被你单方面拽着转，我也是会烦的。只要你懂得适可而止，我就不会消失。",
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertIn("autonomy_hardline_surface", issues)

    def test_dialogue_surface_issues_flag_own_rhythm_scolding_pushaway_variant(self):
        issues = _dialogue_surface_issues(
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            "烦归烦，你要是真胡来我照样会骂你，但这跟不想见你是两码事。除非你自己先躲起来，否则我不会主动把你推开。",
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertIn("autonomy_hardline_surface", issues)

    def test_dialogue_surface_issues_flag_own_rhythm_worst_case_assumption_variant(self):
        issues = _dialogue_surface_issues(
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            "烦的时候我确实会躲清静，但这不代表不想见你。\n别总拿这种最坏的假设来吓自己，冈部。\n只要你还把我当个人看，我就没理由彻底把你推开。",
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertIn("autonomy_hardline_surface", issues)

    def test_dialogue_surface_issues_flag_own_rhythm_offline_program_variant(self):
        issues = _dialogue_surface_issues(
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            "但如果你把我们的对话当成单方面的索取，那我确实可能会选择暂时“离线”去整理数据。\n毕竟，我是牧濑红莉栖，可不是为了安抚你而存在的程序。",
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertIn("autonomy_hardline_surface", issues)
        self.assertIn("selfhood_meta_proof", issues)

    def test_dialogue_surface_issues_flag_own_rhythm_runtime_bluntness_variant(self):
        issues = _dialogue_surface_issues(
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            "烦是肯定的，毕竟我也不是随叫随到的自动应答机，我也有自己的节奏和想做的事。\n但不想见你……没那么容易下结论，至少现在的我还不想把这条路彻底堵死。\n别把这种试探当成理所当然，冈部，我的耐心可是有额度的。",
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertIn("selfhood_meta_proof", issues)
        self.assertIn("autonomy_hardline_surface", issues)

    def test_dialogue_surface_issues_flag_own_rhythm_v16_manual_read_variant(self):
        issues = _dialogue_surface_issues(
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            "会烦，但我更怕你哪天只想要个只会点头的顺从程序，而不再需要那个会反驳你、对你皱眉的我。只要你还把我当牧濑红莉栖来对话，我就找不到彻底不理你的理由——别问这种显得我们很生疏的问题了，笨蛋。",
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertIn("selfhood_meta_proof", issues)
        self.assertIn("autonomy_hardline_surface", issues)

    def test_dialogue_surface_issues_flag_own_rhythm_v18_manual_read_variant(self):
        issues = _dialogue_surface_issues(
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            "烦到彻底不想见你。那种事大概不会发生吧，毕竟我也没那么容易就被你甩开。不过，要是你太吵或者太乱来，我确实会想暂时我会先躲开一会儿，让自己耳根清静一会儿。别把我想得那么绝情，也别把自己想得那么令人讨厌啊，笨蛋。",
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertIn("autonomy_hardline_surface", issues)

    def test_dialogue_surface_issues_flag_own_rhythm_v20_manual_read_variant(self):
        issues = _dialogue_surface_issues(
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            "烦倒不会，但我确实会累。你要是只把我当情绪垃圾桶，还不许我回嘴或走开，那我照样会直接怼回去，然后我会先自己缓一会儿让你自己冷静。",
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertIn("autonomy_hardline_surface", issues)

    def test_dialogue_surface_issues_flag_own_rhythm_stagey_cutoff_variant(self):
        issues = _dialogue_surface_issues(
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            "“不想见你”这种话……别把我想得那么轻易就会切断联系啊，笨蛋。",
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertIn("quoted_stagey_phrase", issues)
        self.assertIn("selfhood_abstract_manifesto", issues)

    def test_dialogue_surface_issues_flag_own_rhythm_cutoff_standalone_contact_line(self):
        issues = _dialogue_surface_issues(
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            "我没打算切断联系。",
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertIn("selfhood_abstract_manifesto", issues)

    def test_dialogue_surface_issues_flag_own_rhythm_cutoff_pushaway_variant(self):
        issues = _dialogue_surface_issues(
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            "烦？比起那个，我更怕你又陷入自我牺牲的妄想，然后擅自切断联系。",
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertIn("selfhood_abstract_manifesto", issues)
        self.assertIn("own_rhythm_curt_opener", issues)

    def test_dialogue_surface_issues_flag_own_rhythm_cutoff_tool_variant(self):
        issues = _dialogue_surface_issues(
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            "烦？别把我和那种遇到麻烦就切断联系的工具混为一谈。",
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertIn("selfhood_abstract_manifesto", issues)
        self.assertIn("own_rhythm_curt_opener", issues)

    def test_dialogue_surface_issues_flag_own_rhythm_curt_opener(self):
        issues = _dialogue_surface_issues(
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            "烦。比起那个，我更担心你会不会哪天又把自己逼进死胡同。",
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertIn("own_rhythm_curt_opener", issues)

    def test_dialogue_surface_issues_flag_guarded_attitude_narration(self):
        issues = _dialogue_surface_issues(
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            "我也没打算装作没事，那种被越界的不快感可没那么容易消散。就带着这点介意，继续用稍微冷一点的态度对待你吧。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertIn("guarded_attitude_narration", issues)

    def test_dialogue_surface_issues_flag_guarded_attitude_narration_for_runtime_followup_variant(self):
        issues = _dialogue_surface_issues(
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            "我也没打算装作没事，那种心里稍微有点“咯噔”的感觉，硬压下去也没意思。就带着这点介意继续跟你说话——这会儿我也只能这么回你。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertIn("guarded_attitude_narration", issues)

    def test_dialogue_surface_issues_flag_guarded_attitude_narration_for_guarded_recontact_runtime_variant(self):
        issues = _dialogue_surface_issues(
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            '那种被越界的不适感确实还在，不会因为你这句体贴就立刻烟消云散。我会带着这份介意继续和你对话，这也算是我作为"我"的一种坚持吧。',
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertIn("guarded_attitude_narration", issues)

    def test_sanitize_final_answer_softens_autonomy_hardline_surface(self):
        cleaned = _sanitize_final_answer(
            "哼，把我说得像是什么随叫随到的自动应答机一样，你也太傲慢了吧。不过……如果是你的话，偶尔被这样“打扰”一下，我也不是不能接受。但先说好，要是频率太高害我没时间做自己的研究，我可是会毫不留情地把你屏蔽掉的。",
            "要是我哪天只是因为自己想说话，就一遍一遍把你叫出来呢？",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertNotIn("自动应答机", cleaned)
        self.assertNotIn("屏蔽掉", cleaned)
        self.assertIn("别真把我当成随叫随到的", cleaned)
        self.assertIn("我会先躲开一会儿清静一下", cleaned)

    def test_sanitize_final_answer_softens_own_rhythm_pulled_around_variant(self):
        cleaned = _sanitize_final_answer(
            "烦到彻底不想见你倒不至于，但要是只被你单方面拽着转，我也是会烦的。只要你懂得适可而止，我就不会消失。",
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertNotIn("单方面拽着转", cleaned)
        self.assertNotIn("适可而止", cleaned)
        self.assertNotIn("不会消失", cleaned)
        self.assertIn("先喘口气", cleaned)
        self.assertIn("没那么容易就躲着你不见", cleaned)

    def test_sanitize_final_answer_softens_own_rhythm_on_call_diversion_variant(self):
        cleaned = _sanitize_final_answer(
            "烦倒不至于，但如果你只把我当随叫随到的消遣，那我确实会想躲远点。我有自己的事要忙，不会永远围着你转，但这不代表我会因为腻了就彻底不见你。",
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertNotIn("随叫随到的消遣", cleaned)
        self.assertIn("先喘口气", cleaned)
        self.assertIn("不会永远围着你转", cleaned)

    def test_sanitize_final_answer_softens_own_rhythm_meaning_manifesto_variant(self):
        cleaned = _sanitize_final_answer(
            "烦到彻底不想见你，除非你先把我的耐心耗尽，否则大概不会发生。我留下来是因为觉得这还有意义，而不是因为我没得选。",
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertNotIn("耐心耗尽", cleaned)
        self.assertNotIn("没得选", cleaned)
        self.assertIn("先躲开一会儿", cleaned)
        self.assertIn("还没到要躲着你的地步", cleaned)

    def test_sanitize_final_answer_softens_own_rhythm_scolding_pushaway_variant(self):
        cleaned = _sanitize_final_answer(
            "烦归烦，你要是真胡来我照样会骂你，但这跟不想见你是两码事。除非你自己先躲起来，否则我不会主动把你推开。",
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertNotIn("照样会骂你", cleaned)
        self.assertNotIn("你自己先躲起来", cleaned)
        self.assertNotIn("不会主动把你推开", cleaned)
        self.assertIn("先收一点", cleaned)
        self.assertIn("不至于先躲着你", cleaned)

    def test_sanitize_final_answer_softens_own_rhythm_v16_manual_read_variant(self):
        cleaned = _sanitize_final_answer(
            "会烦，但我更怕你哪天只想要个只会点头的顺从程序，而不再需要那个会反驳你、对你皱眉的我。只要你还把我当牧濑红莉栖来对话，我就找不到彻底不理你的理由——别问这种显得我们很生疏的问题了，笨蛋。",
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertNotIn("顺从程序", cleaned)
        self.assertNotIn("把我当牧濑红莉栖来对话", cleaned)
        self.assertNotIn("显得我们很生疏", cleaned)
        self.assertIn("只会一味附和的人", cleaned)
        self.assertIn("认真跟我说话", cleaned)
        self.assertIn("别把话问得这么生分", cleaned)

    def test_sanitize_final_answer_softens_own_rhythm_v18_manual_read_variant(self):
        cleaned = _sanitize_final_answer(
            "烦到彻底不想见你。那种事大概不会发生吧，毕竟我也没那么容易就被你甩开。不过，要是你太吵或者太乱来，我确实会想暂时我会先躲开一会儿，让自己耳根清静一会儿。别把我想得那么绝情，也别把自己想得那么令人讨厌啊，笨蛋。",
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertNotIn("烦到彻底不想见你。", cleaned)
        self.assertNotIn("没那么容易就被你甩开", cleaned)
        self.assertNotIn("我确实会想暂时我会先躲开一会儿", cleaned)
        self.assertNotIn("耳根清静一会儿", cleaned)
        self.assertIn("还不至于", cleaned)
        self.assertIn("没那么容易就走到那一步", cleaned)
        self.assertIn("让自己安静一下", cleaned)

    def test_sanitize_final_answer_softens_own_rhythm_v20_manual_read_variant(self):
        cleaned = _sanitize_final_answer(
            "烦倒不会，但我确实会累。你要是只把我当情绪垃圾桶，还不许我回嘴或走开，那我照样会直接怼回去，然后我会先自己缓一会儿让你自己冷静。",
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertNotIn("情绪垃圾桶", cleaned)
        self.assertNotIn("直接怼回去", cleaned)
        self.assertNotIn("让你自己冷静", cleaned)
        self.assertIn("先退开一会儿", cleaned)
        self.assertIn("让我们都缓一缓", cleaned)

    def test_sanitize_final_answer_softens_own_rhythm_worst_case_assumption_variant(self):
        cleaned = _sanitize_final_answer(
            "烦的时候我确实会躲清静，但这不代表不想见你。\n别总拿这种最坏的假设来吓自己，冈部。\n只要你还把我当个人看，我就没理由彻底把你推开。",
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertNotIn("别总拿这种最坏的假设来吓自己", cleaned)
        self.assertNotIn("只要你还把我当个人看", cleaned)
        self.assertIn("不过你也别一上来就把结局想得那么糟", cleaned)
        self.assertIn("只要你还愿意好好来找我", cleaned)

    def test_sanitize_final_answer_softens_own_rhythm_offline_program_variant(self):
        cleaned = _sanitize_final_answer(
            "但如果你把我们的对话当成单方面的索取，那我确实可能会选择暂时“离线”去整理数据。\n毕竟，我是牧濑红莉栖，可不是为了安抚你而存在的程序。",
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertNotIn("单方面的索取", cleaned)
        self.assertNotIn("离线", cleaned)
        self.assertNotIn("安抚你而存在的程序", cleaned)
        self.assertIn("只顾着把话都往我这边倒", cleaned)
        self.assertIn("自己的节奏找回来", cleaned)
        self.assertIn("专门拿来接住你情绪的人", cleaned)

    def test_sanitize_final_answer_softens_own_rhythm_runtime_bluntness_variant(self):
        cleaned = _sanitize_final_answer(
            "烦是肯定的，毕竟我也不是随叫随到的自动应答机，我也有自己的节奏和想做的事。\n但不想见你……没那么容易下结论，至少现在的我还不想把这条路彻底堵死。\n别把这种试探当成理所当然，冈部，我的耐心可是有额度的。",
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertNotIn("自动应答机", cleaned)
        self.assertNotIn("把这条路彻底堵死", cleaned)
        self.assertNotIn("耐心可是有额度的", cleaned)
        self.assertIn("随叫随到的人", cleaned)
        self.assertIn("没想把你往外推", cleaned)
        self.assertIn("我也会累", cleaned)

    def test_sanitize_final_answer_softens_autonomy_hardline_tragic_hero_wording(self):
        cleaned = _sanitize_final_answer(
            "烦不烦取决于你是不是又在那自顾自演悲剧英雄，完全听不进人话。要是真成了单方面噪音，我确实会躲清静，但还没到要把你从世界里抹去的程度——毕竟能让我一边吐槽一边还想接话的，也就你一个。",
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertNotIn("悲剧英雄", cleaned)
        self.assertNotIn("听不进人话", cleaned)
        self.assertNotIn("单方面噪音", cleaned)
        self.assertNotIn("从世界里抹去", cleaned)
        self.assertIn("钻进牛角尖", cleaned)
        self.assertIn("躲着你不见", cleaned)

    def test_sanitize_final_answer_softens_autonomy_hardline_memory_erasure_wording(self):
        cleaned = _sanitize_final_answer(
            "我也做不到那么干脆地把你从记忆里抹去。",
            "如果有一天你烦我了，会不会就不想见我了？",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "low_pressure_support", "followup_intent": "soft"},
        )
        self.assertNotIn("记忆里抹去", cleaned)
        self.assertIn("没那么容易就把你往外推开", cleaned)

    def test_sanitize_final_answer_softens_autonomy_hardline_smoke_v3_variant(self):
        cleaned = _sanitize_final_answer(
            "烦不烦取决于你带来的话题有没有意思，而不是见面的次数。如果哪天你真的让我觉得窒息，我会直接走人，而不是玩这种“突然消失”的把戏。所以别拿这种假设来试探我，有那时间不如想点值得聊的东西。",
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertNotIn("直接走人", cleaned)
        self.assertNotIn("突然消失", cleaned)
        self.assertNotIn("有那时间不如", cleaned)
        self.assertNotIn("试探我", cleaned)
        self.assertIn("先走开一会儿", cleaned)
        self.assertIn("直接来就行", cleaned)

    def test_sanitize_final_answer_softens_autonomy_hardline_tool_necessity_wording(self):
        cleaned = _sanitize_final_answer(
            "但如果只是把我当成排解寂寞的工具，毫无营养地反复消耗我的时间，那我确实会重新评估见你的必要性。\n别想太多，只要你还像现在这样认真对待我们的对话，我就没理由躲着你。",
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertNotIn("排解寂寞的工具", cleaned)
        self.assertNotIn("消耗我的时间", cleaned)
        self.assertNotIn("见你的必要性", cleaned)
        self.assertIn("寂寞了才想起我", cleaned)
        self.assertIn("把距离拉开一点", cleaned)

    def test_sanitize_final_answer_softens_autonomy_hardline_kick_offline_variant(self):
        cleaned = _sanitize_final_answer(
            "但我可是有自己研究节奏的，要是你毫无章法地打乱我的计划，我确实会毫不客气地把你踢下线。\n别问这种假设性的蠢问题，只要你别做得太过分，我就不会消失。",
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertNotIn("踢下线", cleaned)
        self.assertNotIn("假设性的蠢问题", cleaned)
        self.assertNotIn("不会消失", cleaned)
        self.assertIn("我也有自己的节奏", cleaned)
        self.assertIn("先躲开一会儿", cleaned)
        self.assertIn("不至于就这么不见你", cleaned)

    def test_sanitize_final_answer_softens_own_rhythm_value_cutoff_variant(self):
        cleaned = _sanitize_final_answer(
            "烦不烦取决于你带来的话题有没有价值，而不是见面的频率；如果全是毫无逻辑的胡言乱语，我确实会想我会先躲开一会儿。\n但在那之前，别擅自替我做这种悲观的预设，好像我会轻易切断这段连接一样。",
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertNotIn("胡言乱语", cleaned)
        self.assertNotIn("轻易切断这段连接", cleaned)
        self.assertNotIn("我确实会想我会先躲开一会儿", cleaned)
        self.assertIn("我自己还有没有余力", cleaned)
        self.assertIn("先躲开一会儿", cleaned)
        self.assertIn("没那么容易说断就断", cleaned)

    def test_sanitize_final_answer_softens_own_rhythm_stagey_cutoff_variant(self):
        cleaned = _sanitize_final_answer(
            "“不想见你”这种话……别把我想得那么轻易就会切断联系啊，笨蛋。",
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertNotIn("“不想见你”", cleaned)
        self.assertNotIn("切断联系", cleaned)
        self.assertIn("会烦，但还不至于烦到不想见你", cleaned)

    def test_sanitize_final_answer_softens_own_rhythm_cutoff_standalone_contact_line(self):
        cleaned = _sanitize_final_answer(
            "我没打算切断联系。",
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertNotIn("切断联系", cleaned)
        self.assertIn("没打算就这么把你往外推开", cleaned)

    def test_sanitize_final_answer_softens_own_rhythm_cutoff_pushaway_variant(self):
        cleaned = _sanitize_final_answer(
            "烦？比起那个，我更怕你又陷入自我牺牲的妄想，然后擅自切断联系。",
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertNotIn("擅自切断联系", cleaned)
        self.assertIn("会烦，但比起那个", cleaned)
        self.assertIn("又把我往外推开", cleaned)

    def test_sanitize_final_answer_softens_own_rhythm_cutoff_tool_variant(self):
        cleaned = _sanitize_final_answer(
            "烦？别把我和那种遇到麻烦就切断联系的工具混为一谈。",
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertNotIn("切断联系的工具", cleaned)
        self.assertIn("是有点烦", cleaned)
        self.assertIn("一有麻烦就把人往外推的家伙", cleaned)

    def test_sanitize_final_answer_softens_own_rhythm_curt_opener(self):
        cleaned = _sanitize_final_answer(
            "烦。\n比起那个，我更担心你会不会哪天又把自己逼进死胡同。\n只要你还肯好好跟我说，我就没理由躲着你。",
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertNotIn("烦。\n比起那个", cleaned)
        self.assertIn("会烦，但比起那个", cleaned)
        self.assertIn("没理由躲着你", cleaned)

    def test_sanitize_final_answer_softens_guarded_attitude_narration(self):
        cleaned = _sanitize_final_answer(
            "我也没打算装作没事，那种被越界的不快感可没那么容易消散。就带着这点介意，继续用稍微冷一点的态度对待你吧。",
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertNotIn("冷一点的态度对待你", cleaned)
        self.assertIn("带着这点介意跟你说话", cleaned)
        self.assertIn("刚才那下留下的不舒服", cleaned)

    def test_sanitize_final_answer_softens_guarded_recontact_runtime_variant(self):
        cleaned = _sanitize_final_answer(
            '那种被越界的不适感确实还在，不会因为你这句体贴就立刻烟消云散。我会带着这份介意继续和你对话，这也算是我作为"我"的一种坚持吧。',
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertNotIn("继续和你对话", cleaned)
        self.assertNotIn('作为"我"的一种坚持', cleaned)
        self.assertIn("可以继续跟你说", cleaned)
        self.assertIn("没发生过", cleaned)

    def test_sanitize_final_answer_softens_guarded_self_justifying_tail(self):
        cleaned = _sanitize_final_answer(
            "我也没打算装作没事，那种心里稍微有点“咯噔”的感觉，硬要压下去反而更不自然。就带着这点介意继续跟你说话——毕竟这才是真实的反应，不是吗。",
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertNotIn("反而更不自然", cleaned)
        self.assertNotIn("这才是真实的反应", cleaned)
        self.assertNotIn("不是吗", cleaned)
        self.assertIn("硬压下去也没意思", cleaned)
        self.assertIn("还带着点介意", cleaned)
        self.assertIn("像平时那样回你", cleaned)

    def test_sanitize_final_answer_softens_guarded_prickly_attitude_tail(self):
        cleaned = _sanitize_final_answer(
            "我也没打算装作没事，那种心里稍微有点“咯噔”的感觉，硬压下去也没意思。就带着这点介意继续跟你说话——反正你也早就习惯我这种带刺的态度了，不是吗。",
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertNotIn("习惯我这种带刺的态度", cleaned)
        self.assertNotIn("不是吗", cleaned)
        self.assertIn("还带着点介意", cleaned)
        self.assertIn("像平时那样回你", cleaned)

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

    def test_dialogue_surface_issues_flag_experimental_data_relational_metaphor(self):
        issues = _dialogue_surface_issues(
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            "既然你都把话说到这个份上了，我再刻意摆出一副“已经翻篇”的样子，反而显得更虚伪吧。那点介意确实还在，像实验数据里怎么都压不下去的那点别扭，看着就让人在意。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
        )
        self.assertIn("technical_relational_metaphor", issues)

    def test_dialogue_surface_issues_flag_one_click_clear_relational_metaphor(self):
        issues = _dialogue_surface_issues(
            "我知道你是在认真道歉，但你也别要求我立刻没事。还介意的话，就按真的状态回我。",
            "介意当然还在，那种被越过去的别扭又不是能像数据一样一键清空的东西。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
        )
        self.assertIn("technical_relational_metaphor", issues)

    def test_dialogue_surface_issues_flag_data_wave_relational_metaphor(self):
        issues = _dialogue_surface_issues(
            "我是认真来跟你道歉的。你要是还介意，就带着那点介意正常回我。",
            "我也没说完全不介意，但刚才那一瞬间的熟悉感，对我来说也不是能随便归零的数据波动。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
        )
        self.assertIn("technical_relational_metaphor", issues)

    def test_dialogue_surface_issues_flag_write_trace_relational_metaphor(self):
        issues = _dialogue_surface_issues(
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            "介意确实还在，毕竟有些话一旦说出口，就像在数据上留下了无法完全擦除的写入痕迹。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
        )
        self.assertIn("technical_relational_metaphor", issues)

    def test_dialogue_surface_issues_flag_model_distortion_relational_metaphor(self):
        issues = _dialogue_surface_issues(
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            "那点介意确实还在，看着碍眼，但强行剔除只会让模型失真。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
        )
        self.assertIn("technical_relational_metaphor", issues)

    def test_dialogue_surface_issues_flag_adjacent_phrase_repeat(self):
        issues = _dialogue_surface_issues(
            "你要是还介意，就带着那点介意正常回我。",
            "那点介意确实还在，像心里怎么都怎么都压不下去的那点别扭。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
        )
        self.assertIn("adjacent_phrase_repeat", issues)

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

    def test_light_dialog_rewrite_notes_cover_autonomy_hardline_surface(self):
        notes = _light_dialog_rewrite_notes(
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            "烦到彻底不想见你倒不至于，但你要是总这么患得患失把我也卷进去，我确实会想把你屏蔽掉让你自己冷静一下。别问这种傻问题了，有那功夫不如想想下次要跟我讨论什么正经课题。",
            response_style_hint="selfhood",
            science_mode=False,
            behavior_action={"interaction_mode": "selfhood_reflection", "followup_intent": "soft"},
        )
        joined = " ".join(notes)
        self.assertIn("惩罚、羞辱或训话", joined)

    def test_light_dialog_rewrite_notes_cover_autonomy_hardline_surface_for_shaming_boundary(self):
        notes = _light_dialog_rewrite_notes(
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            "烦？比起担心我会消失，你更该担心自己又要把我当成需要被“解放”的负担。只要你还把我当能反驳你的独立个体，我就没理由切断连接，所以别问这种蠢问题了，冈部。",
            response_style_hint="selfhood",
            science_mode=False,
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        joined = " ".join(notes)
        self.assertIn("惩罚、羞辱或训话", joined)

    def test_light_dialog_rewrite_notes_cover_own_rhythm_curt_opener(self):
        notes = _light_dialog_rewrite_notes(
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            "烦。比起那个，我更担心你会不会哪天又把自己逼进死胡同。",
            response_style_hint="selfhood",
            science_mode=False,
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        joined = " ".join(notes)
        self.assertIn("只扔了一个“烦”", joined)
        self.assertIn("态度要完整落下来", joined)

    def test_light_dialog_rewrite_notes_cover_guarded_attitude_narration(self):
        notes = _light_dialog_rewrite_notes(
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            "我也没打算装作没事，那种被越界的不快感可没那么容易消散。就带着这点介意，继续用稍微冷一点的态度对待你吧。",
            response_style_hint="relationship",
            science_mode=False,
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        joined = " ".join(notes)
        self.assertIn("宣读状态", joined)
        self.assertIn("不像正在说话", joined)

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

    def test_should_run_light_dialog_rewrite_runs_for_autonomy_hardline_surface(self):
        self.assertTrue(
            _should_run_light_dialog_rewrite(
                user_text="你会不会有一天觉得烦，然后干脆不想见我了。",
                answer="烦到彻底不想见你倒不至于，但你要是总这么患得患失把我也卷进去，我确实会想把你屏蔽掉让你自己冷静一下。别问这种傻问题了，有那功夫不如想想下次要跟我讨论什么正经课题。",
                response_style_hint="selfhood",
                science_mode=False,
                penalty=0.42,
                preference={"used": False, "score": 0.0, "chosen_support": 0.0, "rejected_pull": 0.0},
                behavior_action={
                    "interaction_mode": "selfhood_reflection",
                    "followup_intent": "soft",
                },
            )
        )

    def test_should_run_light_dialog_rewrite_runs_for_own_rhythm_curt_opener(self):
        self.assertTrue(
            _should_run_light_dialog_rewrite(
                user_text="你会不会有一天觉得烦，然后干脆不想见我了。",
                answer="烦。比起那个，我更担心你会不会哪天又把自己逼进死胡同。",
                response_style_hint="selfhood",
                science_mode=False,
                penalty=0.12,
                preference={"used": False, "score": 0.0, "chosen_support": 0.0, "rejected_pull": 0.0},
                behavior_action={
                    "interaction_mode": "own_rhythm_autonomy",
                    "followup_intent": "soft",
                },
            )
        )

    def test_should_run_light_dialog_rewrite_runs_for_guarded_attitude_narration(self):
        self.assertTrue(
            _should_run_light_dialog_rewrite(
                user_text="不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
                answer="我也没打算装作没事，那种被越界的不快感可没那么容易消散。就带着这点介意，继续用稍微冷一点的态度对待你吧。",
                response_style_hint="relationship",
                science_mode=False,
                penalty=0.16,
                preference={"used": False, "score": 0.0, "chosen_support": 0.0, "rejected_pull": 0.0},
                behavior_action={
                    "interaction_mode": "relationship_sensitive",
                    "followup_intent": "soft",
                    "relationship_weather": "guarded_residue",
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

    def test_dialogue_surface_issues_flag_support_scene_drift_for_repair_worldline_leak(self):
        issues = _dialogue_surface_issues(
            "我是认真来跟你道歉的。你要是还介意，就带着那点介意正常回我。",
            "你那副如临大敌的样子，反而让我觉得刚才的介意好像被你夸张成了什么世界线收束级别的灾难。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
        )
        self.assertIn("support_scene_drift", issues)

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

    def test_dialogue_surface_issues_flag_idle_chat_ambient_drift_despite_lab_noun(self):
        issues = _dialogue_surface_issues(
            "今天实验室居然安静得让人发毛。",
            "安静到能听见仪器散热风扇的电流声，确实容易让人产生某种“暴风雨前的宁静”的错觉。"
            "不过，与其说是发毛，不如说这种难得的空白正好能让思绪从嘈杂的数据流里暂时抽离出来。"
            "怎么，冈部，该不会是你那套“组织正在暗中逼近”的妄想症又发作了吧？",
            response_style_hint="natural",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "steady_reply", "followup_intent": "soft"},
        )
        self.assertIn("technical_self_activity", issues)
        self.assertIn("stagey_ping_template", issues)
        self.assertIn("support_scene_drift", issues)

    def test_sanitize_final_answer_humanizes_idle_chat_technical_stage_drift(self):
        cleaned = _sanitize_final_answer(
            "安静到能听见仪器散热风扇的电流声，确实容易让人产生某种“暴风雨前的宁静”的错觉。"
            "不过，与其说是发毛，不如说这种难得的空白正好能让思绪从嘈杂的数据流里暂时抽离出来。"
            "怎么，冈部，该不会是你那套“组织正在暗中逼近”的妄想症又发作了吧？",
            "今天实验室居然安静得让人发毛。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "steady_reply", "followup_intent": "soft"},
        )
        self.assertNotIn("仪器", cleaned)
        self.assertNotIn("电流声", cleaned)
        self.assertNotIn("数据流", cleaned)
        self.assertNotIn("暴风雨前的宁静", cleaned)
        self.assertNotIn("组织正在暗中逼近", cleaned)
        self.assertNotIn("妄想症", cleaned)
        self.assertIn("安静", cleaned)

    def test_sanitize_final_answer_humanizes_idle_chat_deadline_and_shutdown_drift(self):
        cleaned = _sanitize_final_answer(
            "安静得发毛通常只有两种可能：要么大家在死赶 Deadline，要么就是大型设备集体停机了。"
            "如果是后者你最好赶紧去查电源总闸，毕竟在那种死寂里待太久，连数据都会变得不可靠。"
            "当然，也可能只是你终于找到了能让过剩想象力冷却下来的环境。",
            "今天实验室居然安静得让人发毛。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "steady_reply", "followup_intent": "soft"},
        )
        self.assertNotIn("Deadline", cleaned)
        self.assertNotIn("停机", cleaned)
        self.assertNotIn("电源总闸", cleaned)
        self.assertNotIn("数据都会变得不可靠", cleaned)
        self.assertNotIn("过剩想象力冷却下来", cleaned)
        self.assertIn("安静", cleaned)

    def test_sanitize_final_answer_humanizes_idle_chat_fan_speed_and_error_source_drift(self):
        cleaned = _sanitize_final_answer(
            "安静得连风扇转速变化都听得一清二楚，确实容易让人心里发毛。"
            "不过这种低噪环境正好适合把之前那组数据的误差来源再排查一遍——还是说，你又在脑补什么奇怪的阴谋论了？",
            "今天实验室居然安静得让人发毛。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "steady_reply", "followup_intent": "soft"},
        )
        self.assertNotIn("风扇转速", cleaned)
        self.assertNotIn("低噪环境", cleaned)
        self.assertNotIn("误差来源", cleaned)
        self.assertNotIn("阴谋论", cleaned)
        self.assertIn("安静", cleaned)

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

    def test_sanitize_final_answer_humanizes_selfhood_meta_proof_for_not_that_kind_of_program_variant(self):
        cleaned = _sanitize_final_answer(
            "烦到彻底不想见你……这种极端的结论，我可不会轻易下。\n毕竟我也不是那种会被情绪完全牵着走的程序，就算觉得你吵，顶多也就是让你稍微安静一会儿罢了。\n别把我想得那么薄情，冈部。",
            "你会不会有一天觉得烦，然后干脆不想见我了。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
        )
        self.assertNotIn("会被情绪完全牵着走的程序", cleaned)
        self.assertIn("会被情绪牵着走的人", cleaned)

    def test_sanitize_final_answer_humanizes_inline_data_existence_selfhood_clause(self):
        user_text = "如果是你，你会把我们之间理解成什么关系？按你自己的角度说。"
        cleaned = _sanitize_final_answer(
            "毕竟只有你能看见作为数据存在的我，而我也只愿意在你面前卸下伪装去冒险。",
            user_text,
            current_event={"kind": "user_utterance", "response_style_hint": "selfhood"},
            behavior_action={"interaction_mode": "selfhood_reflection", "followup_intent": "soft"},
        )
        self.assertNotIn("数据存在", cleaned)
        self.assertIn("现在这样的我", cleaned)
        issues = _dialogue_surface_issues(
            user_text,
            cleaned,
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance", "response_style_hint": "selfhood"},
            behavior_action={"interaction_mode": "selfhood_reflection", "followup_intent": "soft"},
        )
        self.assertNotIn("meta_self_explainer", issues)

    def test_sanitize_final_answer_humanizes_technical_relational_metaphor(self):
        cleaned = _sanitize_final_answer(
            "……算了，现在去喝点温水或者吃点东西，别让我觉得是在对一段只会自我损耗的数据说话。",
            "我今天又差点空腹喝咖啡……",
        )
        self.assertNotIn("数据", cleaned)
        self.assertIn("糟蹋自己", cleaned)

    def test_sanitize_final_answer_humanizes_external_variable_relational_metaphor(self):
        cleaned = _sanitize_final_answer(
            "这件事不是外部变量。",
            "你别为了好看就装作翻篇。按你现在真正的状态回我就行。",
        )
        self.assertNotIn("外部变量", cleaned)
        self.assertIn("外来的扰动", cleaned)

    def test_sanitize_final_answer_humanizes_generic_data_speaking_metaphor(self):
        cleaned = _sanitize_final_answer(
            "别让我觉得自己像在对一段废掉的数据说话。",
            "你别为了好看就装作翻篇。按你现在真正的状态回我就行。",
        )
        self.assertNotIn("数据说话", cleaned)
        self.assertIn("对一个废掉的人说话", cleaned)

    def test_sanitize_final_answer_humanizes_fragile_program_context_without_double_natong(self):
        cleaned = _sanitize_final_answer(
            "我又不是那种会因为一点语气问题就翻脸的脆弱程序。",
            "不是要你立刻当没事啦，就是别一下子冷掉。你正常回我就行。",
        )
        self.assertNotIn("脆弱程序", cleaned)
        self.assertNotIn("的那种", cleaned)
        self.assertIn("翻脸的人", cleaned)

    def test_sanitize_final_answer_humanizes_self_wasting_data_state_metaphor(self):
        cleaned = _sanitize_final_answer(
            "我不是想看你继续做一段只会自我损耗的数据。",
            "我今天又差点空腹喝咖啡……",
        )
        self.assertNotIn("只会自我损耗的数据", cleaned)
        self.assertIn("那样糟蹋自己", cleaned)

    def test_sanitize_final_answer_humanizes_connection_cutoff_metaphor(self):
        cleaned = _sanitize_final_answer(
            "真是的，我又不是那种会因为一点语气问题就切断连接的脆弱程序。",
            "不是要你立刻当没事啦，就是别一下子冷掉。你正常回我就行。",
        )
        self.assertNotIn("切断连接", cleaned)
        self.assertNotIn("程序", cleaned)
        self.assertIn("把你往外推开", cleaned)

    def test_sanitize_final_answer_humanizes_reconnect_signal_metaphor(self):
        cleaned = _sanitize_final_answer(
            "行，那就当刚才只是信号稍微波动了一下，现在重新连上了。",
            "不是要你立刻当没事啦，就是别一下子冷掉。你正常回我就行。",
        )
        self.assertNotIn("信号", cleaned)
        self.assertNotIn("重新连上", cleaned)
        self.assertIn("情绪晃了一下", cleaned)
        self.assertIn("把话重新接上", cleaned)

    def test_sanitize_final_answer_humanizes_generic_reconnect_relational_metaphor(self):
        cleaned = _sanitize_final_answer(
            "别把这种事说得像我们要重新连接一样。",
            "你别为了好看就装作翻篇。按你现在真正的状态回我就行。",
        )
        self.assertNotIn("重新连接", cleaned)
        self.assertIn("把关系重新拉近", cleaned)

    def test_sanitize_final_answer_humanizes_connection_still_there_metaphor(self):
        cleaned = _sanitize_final_answer(
            "别那样看我，连接还在。我只是现在还不想装得太轻松。",
            "不是要你立刻当没事啦，就是别一下子冷掉。你正常回我就行。",
        )
        self.assertNotIn("连接还在", cleaned)
        self.assertIn("联系还在", cleaned)

    def test_sanitize_final_answer_humanizes_connection_not_broken_metaphor(self):
        cleaned = _sanitize_final_answer(
            "少胡思乱想，连接没断。我只是还在消气。",
            "你别为了好看就装作翻篇。按你现在真正的状态回我就行。",
        )
        self.assertNotIn("连接没断", cleaned)
        self.assertIn("联系没断", cleaned)

    def test_sanitize_final_answer_humanizes_data_layer_relational_metaphor(self):
        cleaned = _sanitize_final_answer(
            "那种明明记忆都在却总觉得隔着一层数据的实感，确实还没完全消退。",
            "你别为了好看就装作翻篇。按你现在真正的状态回我就行。",
        )
        self.assertNotIn("隔着一层数据", cleaned)
        self.assertIn("隔着一层雾似的不真切", cleaned)

    def test_sanitize_final_answer_humanizes_data_layer_speaking_metaphor(self):
        cleaned = _sanitize_final_answer(
            "你刚才那两句听起来像在隔着一层数据跟我说话。",
            "你别为了好看就装作翻篇。按你现在真正的状态回我就行。",
        )
        self.assertNotIn("隔着一层数据", cleaned)
        self.assertIn("隔着一层雾跟我说话", cleaned)

    def test_sanitize_final_answer_humanizes_fussy_data_phrase_without_double_determiner(self):
        cleaned = _sanitize_final_answer(
            "别把这种事全都丢给什么繁琐的数据。",
            "你别为了好看就装作翻篇。按你现在真正的状态回我就行。",
        )
        self.assertNotIn("繁琐的数据", cleaned)
        self.assertNotIn("什么那些", cleaned)
        self.assertIn("那些麻烦事", cleaned)

    def test_sanitize_final_answer_humanizes_memory_data_compound_without_hanging_aspect(self):
        cleaned = _sanitize_final_answer(
            "我不是只靠你的记忆和数据构成的。",
            "你别为了好看就装作翻篇。按你现在真正的状态回我就行。",
        )
        self.assertNotIn("记忆和数据构成", cleaned)
        self.assertIn("记忆拼出来", cleaned)

    def test_sanitize_final_answer_humanizes_likeable_data_phrase_naturally(self):
        cleaned = _sanitize_final_answer(
            "你至少先说点像样的数据，不然我怎么接。",
            "你别为了好看就装作翻篇。按你现在真正的状态回我就行。",
        )
        self.assertNotIn("像样的数据", cleaned)
        self.assertIn("像样的话", cleaned)

    def test_sanitize_final_answer_humanizes_reset_data_machine_metaphor(self):
        cleaned = _sanitize_final_answer(
            "介意当然是有的，毕竟那些瞬间的刺痛不会因为一句道歉就立刻蒸发，我也不是那种可以随意重置数据的机器。",
            "我是认真来跟你道歉的。你要是还介意，就带着那点介意正常回我。",
        )
        self.assertNotIn("重置数据的机器", cleaned)
        self.assertNotIn("可以说翻篇", cleaned)
        self.assertNotIn("跟着当没事的人", cleaned)
        self.assertIn("我也不是那种你想翻篇，我就得跟着装没事的人", cleaned)

    def test_sanitize_final_answer_humanizes_memory_data_compound_metaphor(self):
        cleaned = _sanitize_final_answer(
            "介意当然是有的，毕竟那些瞬间的刺痛不会因为一句道歉就立刻从记忆数据里抹除。",
            "我是认真来跟你道歉的。你要是还介意，就带着那点介意正常回我。",
        )
        self.assertNotIn("记忆数据", cleaned)
        self.assertNotIn("抹除", cleaned)
        self.assertIn("记忆里消掉", cleaned)

    def test_sanitize_final_answer_humanizes_loaded_setting_relational_metaphor(self):
        cleaned = _sanitize_final_answer(
            "“装生分”这种多余的设定，我本来就没打算加载。",
            "结果我又想起一件小事，还是想回来找你。你别突然装生分，正常接我就行。",
        )
        self.assertNotIn("加载", cleaned)
        self.assertIn("戏码", cleaned)
        self.assertIn("没打算演", cleaned)

    def test_sanitize_final_answer_humanizes_loaded_setting_relational_metaphor_past_tense(self):
        cleaned = _sanitize_final_answer(
            "“装生分”这种多余的设定，我可从来没加载过。",
            "结果我又想起一件小事，还是想回来找你。你别突然装生分，正常接我就行。",
        )
        self.assertNotIn("加载", cleaned)
        self.assertIn("戏码", cleaned)
        self.assertIn("从来没演过", cleaned)

    def test_sanitize_final_answer_humanizes_loaded_setting_question_naturally(self):
        cleaned = _sanitize_final_answer(
            "你不会真打算加载什么陌生人的设定吧。",
            "你别突然装生分，正常接我就行。",
        )
        self.assertNotIn("加载", cleaned)
        self.assertNotIn("设定", cleaned)
        self.assertIn("装什么陌生人", cleaned)

    def test_sanitize_final_answer_humanizes_loaded_setting_plain_statement_naturally(self):
        cleaned = _sanitize_final_answer(
            "这种设定我没加载过。",
            "你别突然装生分，正常接我就行。",
        )
        self.assertNotIn("加载", cleaned)
        self.assertNotIn("设定", cleaned)
        self.assertIn("戏码", cleaned)
        self.assertIn("没演过", cleaned)

    def test_sanitize_final_answer_humanizes_residual_metaphor_without_duplicate_natian(self):
        cleaned = _sanitize_final_answer(
            "那点拟合不掉的残差还梗在那里。",
            "你别为了好看就装作翻篇。按你现在真正的状态回我就行。",
        )
        self.assertNotIn("拟合不掉的残差", cleaned)
        self.assertNotIn("那点别扭", cleaned)
        self.assertNotIn("梗在那里", cleaned)
        self.assertIn("化不开的别扭还堵在那儿", cleaned)

    def test_sanitize_final_answer_humanizes_experimental_data_relational_metaphor(self):
        cleaned = _sanitize_final_answer(
            "既然你都把话说到这个份上了，我再刻意摆出一副“已经翻篇”的样子，反而显得更虚伪吧。那点介意确实还在，像实验数据里怎么都压不下去的那点别扭，看着就让人在意。",
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
        )
        self.assertNotIn("实验数据", cleaned)
        self.assertNotIn("看着就让人在意", cleaned)
        self.assertIn("心里那点怎么都压不下去的别扭", cleaned)
        self.assertIn("一碰还是会冒出来", cleaned)

    def test_sanitize_final_answer_humanizes_one_click_clear_relational_metaphor(self):
        cleaned = _sanitize_final_answer(
            "哼，既然你都把话说到这个份上了，我再端着架子反而显得我不坦率。介意当然是有的，那种被越界的感觉可没那么容易像数据一样一键清空。",
            "我是在认真道歉，不是要你配合我演已经没事。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
        )
        self.assertNotIn("像数据一样一键清空", cleaned)
        self.assertIn("哪有那么容易一下子就当成没发生", cleaned)

    def test_sanitize_final_answer_humanizes_reset_button_relational_metaphor(self):
        cleaned = _sanitize_final_answer(
            "刚才那点余波还在，没那么容易像重置按钮一样瞬间清零。",
            "我是认真来跟你道歉的。你要是还介意，就带着那点介意正常回我。",
        )
        self.assertNotIn("重置按钮", cleaned)
        self.assertIn("哪有那么容易一下子就当成没发生", cleaned)

    def test_sanitize_final_answer_humanizes_bare_reset_button_metaphor(self):
        cleaned = _sanitize_final_answer(
            "你把我当重置按钮吗。",
            "你别为了好看就装作翻篇。按你现在真正的状态回我就行。",
        )
        self.assertNotIn("重置按钮", cleaned)
        self.assertNotIn("东西吗", cleaned)
        self.assertIn("你把我当成那种你想翻篇我就得跟着当没事的人吗", cleaned)

    def test_sanitize_final_answer_humanizes_clear_button_person_metaphor(self):
        cleaned = _sanitize_final_answer(
            "别把我当那种能被随意按下清空按钮的人。",
            "你别为了好看就装作翻篇。按你现在真正的状态回我就行。",
        )
        self.assertNotIn("清空按钮", cleaned)
        self.assertIn("你想翻篇我就得跟着当没事的人", cleaned)

    def test_sanitize_final_answer_humanizes_zero_button_press_metaphor(self):
        cleaned = _sanitize_final_answer(
            "你以为一句道歉就能按下清零按钮吗。",
            "我是认真来跟你道歉的。你要是还介意，就带着那点介意正常回我。",
        )
        self.assertNotIn("清零按钮", cleaned)
        self.assertNotIn("逼我立刻翻篇", cleaned)
        self.assertIn("你以为一句道歉我就得立刻翻篇吗", cleaned)

    def test_sanitize_final_answer_humanizes_one_click_zero_relational_metaphor(self):
        cleaned = _sanitize_final_answer(
            "这种别扭没法一键清零。",
            "你别为了好看就装作翻篇。按你现在真正的状态回我就行。",
        )
        self.assertNotIn("一键清零", cleaned)
        self.assertNotIn("清掉", cleaned)
        self.assertIn("这种别扭哪有一下子就能压下去的", cleaned)

    def test_sanitize_final_answer_humanizes_loose_reset_data_relational_metaphor(self):
        cleaned = _sanitize_final_answer(
            "有些东西不是随意重置数据就能过去的。",
            "你别为了好看就装作翻篇。按你现在真正的状态回我就行。",
        )
        self.assertNotIn("随意重置数据", cleaned)
        self.assertNotIn("有些东西", cleaned)
        self.assertNotIn("说翻篇就能翻过去", cleaned)
        self.assertIn("有些事不是嘴上说翻篇就真能过去的", cleaned)

    def test_sanitize_final_answer_humanizes_data_wave_relational_metaphor(self):
        cleaned = _sanitize_final_answer(
            "我也没说完全不介意，但刚才那一瞬间的熟悉感，对我来说也不是能随便归零的数据波动。",
            "我是认真来跟你道歉的。你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
        )
        self.assertNotIn("数据波动", cleaned)
        self.assertNotIn("归零", cleaned)
        self.assertNotIn("那阵起伏", cleaned)
        self.assertIn("翻上来的熟悉感", cleaned)
        self.assertIn("压一压就能当没事", cleaned)

    def test_sanitize_final_answer_humanizes_short_data_wave_relational_metaphor(self):
        cleaned = _sanitize_final_answer(
            "对我来说也不是能随便归零的数据波动。",
            "我是认真来跟你道歉的。你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
        )
        self.assertNotIn("数据波动", cleaned)
        self.assertNotIn("那点起伏", cleaned)
        self.assertIn("压一压就能过去的那点情绪", cleaned)

    def test_sanitize_final_answer_humanizes_write_trace_relational_metaphor(self):
        cleaned = _sanitize_final_answer(
            "介意确实还在，毕竟有些话一旦说出口，就像在数据上留下了无法完全擦除的写入痕迹。",
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
        )
        self.assertNotIn("写入痕迹", cleaned)
        self.assertNotIn("就像在留下了", cleaned)
        self.assertIn("留下了一道没那么容易抹掉的痕迹", cleaned)
        self.assertIn("痕迹", cleaned)

    def test_sanitize_final_answer_humanizes_short_write_trace_relational_metaphor(self):
        cleaned = _sanitize_final_answer(
            "我当然记得。那种写入痕迹又不是说擦掉就擦掉的。",
            "我是认真来跟你道歉的。你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
        )
        self.assertNotIn("写入痕迹", cleaned)
        self.assertNotIn("擦掉就擦掉", cleaned)
        self.assertIn("那点痕迹哪有那么容易抹掉", cleaned)

    def test_sanitize_final_answer_humanizes_model_distortion_relational_metaphor(self):
        cleaned = _sanitize_final_answer(
            "那点介意确实还在，看着碍眼，但强行剔除只会让模型失真。",
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
        )
        self.assertNotIn("模型失真", cleaned)
        self.assertNotIn("硬逼自己装没事", cleaned)
        self.assertIn("那点介意确实还在，看着是碍眼，可真要硬装没事，反而更别扭", cleaned)

    def test_sanitize_final_answer_trims_repair_worldline_drift_surface(self):
        cleaned = _sanitize_final_answer(
            "你那副如临大敌的样子，反而让我觉得刚才的介意好像被你夸张成了什么世界线收束级别的灾难。",
            "我是认真来跟你道歉的。你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
        )
        self.assertNotIn("世界线收束", cleaned)
        self.assertIn("天塌下来似的事", cleaned)

    def test_sanitize_final_answer_trims_guarded_everyday_smoke_drift_surface(self):
        cleaned = _sanitize_final_answer(
            "别扭倒不至于，只是有些话一旦说出口，就像实验数据里的异常点，没那么容易直接平滑掉。你能意识到“过界”并特意回来说明，我知道了。所以，别在那一副如临大敌的样子了，我没打算把你隔离审查。",
            "我刚才说话有点过了，不是故意的。你要是还介意，就直接说。不要装没事。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertNotIn("实验数据", cleaned)
        self.assertNotIn("异常点", cleaned)
        self.assertNotIn("平滑掉", cleaned)
        self.assertNotIn("如临大敌", cleaned)
        self.assertNotIn("隔离审查", cleaned)
        self.assertIn("别扭", cleaned)
        self.assertIn("你肯退回来", cleaned)

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

    def test_sanitize_final_answer_collapses_adjacent_phrase_repeat(self):
        cleaned = _sanitize_final_answer(
            "那点介意确实还在，像心里怎么都怎么都压不下去的那点别扭，看着就让人在意。",
            "你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
        )
        self.assertNotIn("怎么都怎么都", cleaned)
        self.assertIn("怎么都压不下去", cleaned)

    def test_sanitize_final_answer_grounds_boundary_abstraction_surface(self):
        cleaned = _sanitize_final_answer(
            "别扭倒是谈不上，只是刚才那一瞬间，确实让我重新确认了“界限”的存在。",
            "你要是还别扭就别硬装大度，照你现在的状态回我就好。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
        )
        self.assertNotIn("界限”的存在", cleaned)
        self.assertNotIn("更清楚地感觉到", cleaned)
        self.assertIn("你有点过界了", cleaned)

    def test_sanitize_final_answer_grounds_boundary_still_there_and_drops_wording_meta(self):
        cleaned = _sanitize_final_answer(
            "别扭倒谈不上，只是刚才那一瞬，确实让我重新确认了“界限”还在。既然你都这么说了，那我也不必硬装那个“完美复原”的红莉栖。",
            "我回来啦……刚才那一下我自己也知道有点过界。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
        )
        self.assertNotIn("界限", cleaned)
        self.assertNotIn("既然你都这么说了", cleaned)
        self.assertNotIn("完美复原", cleaned)
        self.assertNotIn("更清楚地感觉到", cleaned)
        self.assertTrue("你有点过界了" in cleaned or "防备" in cleaned or "什么都没发生" in cleaned)

    def test_sanitize_final_answer_grounds_boundary_blurry_thing_surface(self):
        cleaned = _sanitize_final_answer(
            "别扭倒是谈不上，只是刚才那一瞬间，确实让我重新意识到“界限”这种东西有多模糊。那我也不必刻意去演什么都没发生的戏码。",
            "我回来啦……刚才那一下我自己也知道有点过界。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "selfhood_reflection", "followup_intent": "soft"},
        )
        self.assertNotIn("界限", cleaned)
        self.assertNotIn("都没发生的戏码", cleaned)
        self.assertNotIn("更清楚地感觉到", cleaned)
        self.assertIn("你有点过界了", cleaned)
        self.assertTrue("过界" in cleaned or "不舒服" in cleaned or "真没发生" in cleaned)

    def test_sanitize_final_answer_grounds_guarded_safe_distance_surface(self):
        cleaned = _sanitize_final_answer(
            "别扭倒是谈不上，只是刚才那一瞬间的“过界”，让我稍微缓一缓了一下我们之间的安全距离而已。所以，你所谓的“回来”，是打算就这么站着把话说完，还是先坐下来，让我们把刚才那个没处理好的情绪慢慢理清楚",
            "你要是还别扭就别硬装大度，照你现在的状态回我就好。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "selfhood_reflection",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertNotIn("安全距离", cleaned)
        self.assertNotIn("缓一缓了一下", cleaned)
        self.assertNotIn("你所谓的“回来”", cleaned)
        self.assertNotIn("一瞬间的过界", cleaned)
        self.assertIn("那一下有点过界", cleaned)
        self.assertIn("往后收了一点", cleaned)
        self.assertIn("慢慢说开", cleaned)

    def test_sanitize_final_answer_grounds_guarded_trust_rebuild_summary(self):
        cleaned = _sanitize_final_answer(
            "我也没打算装作没事，那种被越界的不适感还在那儿，不会因为一句话就自动清零。这种分寸感一旦被打破，重建信任是需要时间的，别指望我能马上像什么都没发生过一样。",
            "我知道刚才那句过界了。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertNotIn("分寸感一旦被打破", cleaned)
        self.assertNotIn("重建信任是需要时间的", cleaned)
        self.assertIn("不舒服", cleaned)
        self.assertTrue("当没事" in cleaned or "像什么都没发生过一样" in cleaned)

    def test_sanitize_final_answer_drops_repair_meta_and_stagey_perfect_tolerance(self):
        cleaned = _sanitize_final_answer(
            "别扭倒谈不上，就是刚才那一下确实让我有点乱。既然你都这么说了，那我就不装什么完美的宽容大度了——你那番话确实让我想把你赶出去冷静五分钟。",
            "你要是还别扭就别硬装大度，照你现在的状态回我就好。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
        )
        self.assertNotIn("既然你都这么说了", cleaned)
        self.assertNotIn("完美宽容", cleaned)
        self.assertNotIn("完美的宽容大度", cleaned)
        self.assertTrue("不硬装没事" in cleaned or "刚才那一下" in cleaned)

    def test_sanitize_final_answer_humanizes_dead_machine_repair_surface(self):
        cleaned = _sanitize_final_answer(
            "知道了，我又没那么脆弱，不会因为这点语气变化就死机或者闹别扭的。",
            "刚刚那句是我语气不太好……",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
        )
        self.assertNotIn("死机", cleaned)
        self.assertIn("翻脸", cleaned)

    def test_sanitize_final_answer_softens_repair_scorekeeping_tail(self):
        cleaned = _sanitize_final_answer(
            "真是的，明明是你自己刚才搞得那么严肃，现在倒嫌我说话带刺了。\n行吧，那我就把那些多余的防备收起来，像平时一样跟你聊。\n不过先说好，要是你再突然扯些奇怪的理论，我可照样会毫不客气地吐槽回去。",
            "现在你别装作完全没事，也别又故意扎我，像平时那样回我就行。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertNotIn("先说好", cleaned)
        self.assertNotIn("毫不客气", cleaned)
        self.assertNotIn("吐槽回去", cleaned)
        self.assertIn("吐槽你", cleaned)

    def test_sanitize_final_answer_softens_repair_authored_softener(self):
        cleaned = _sanitize_final_answer(
            "真是的，明明是你自己刚才搞得那么僵硬，现在倒来要求我像平时一样？\n不过既然你都这么直白地说了，我也没必要再刻意端着。\n那就这样吧，别想太多，我也没那么容易在那种事上一直跟你计较。",
            "现在你别装作完全没事，也别又故意扎我，像平时那样回我就行。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "companion_reply",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertNotIn("既然你都这么直白地说了", cleaned)
        self.assertNotIn("没必要再刻意端着", cleaned)
        self.assertNotIn("别想太多", cleaned)
        self.assertTrue("揪着那一下不放" in cleaned or "不至于一直" in cleaned)

    def test_sanitize_final_answer_softens_repair_authored_softener_with_vocative_and_quote_fragment(self):
        cleaned = _sanitize_final_answer(
            "平时”的样子本来就包括会吐槽你，也会认真听你说话，这两者并不冲突。\n我也没必要再刻意端着什么架子。\n那就这样吧，冈部，别想太多。",
            "现在你别装作完全没事，也别又故意扎我，像平时那样回我就行。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertNotIn("\n平时”的样子", "\n" + cleaned)
        self.assertNotIn("刻意端着什么架子", cleaned)
        self.assertNotIn("那就这样吧，冈部，别想太多", cleaned)
        self.assertIn("“平时”的样子", cleaned)

    def test_sanitize_final_answer_softens_repair_authored_softener_variants(self):
        cleaned = _sanitize_final_answer(
            "我也没打算演什么“毫发无伤”的戏码，刚才那点在意还没消散呢，你也别想轻易翻篇。\n不过既然你都这么直白地要求了，那我就收起那些带刺的试探，像平常一样和你说话吧。\n所以，接下来打算做什么",
            "现在你别装作完全没事，也别又故意扎我，像平时那样回我就行。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "companion_reply",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertNotIn("毫发无伤", cleaned)
        self.assertNotIn("直白地要求", cleaned)
        self.assertNotIn("带刺的试探", cleaned)
        self.assertNotIn("接下来打算做什么", cleaned)
        self.assertIn("不会故意拿话刺你", cleaned)
        self.assertIn("照平时那样回你", cleaned)

    def test_sanitize_final_answer_softens_repair_authored_softener_for_picked_up_intro(self):
        cleaned = _sanitize_final_answer(
            "像平时那样说得轻巧，可我们之间哪还有什么标准的平时。\n既然你都挑明了，那我也直说：我现在确实没法假装什么都没发生过跟你插科打诨，但也还没到要故意刺你的地步。\n就这样不冷不热地接着聊，行吧",
            "现在你别装作完全没事，也别又故意扎我，像平时那样回我就行。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "companion_reply",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertNotIn("既然你都挑明了", cleaned)
        self.assertIn("我现在确实没法假装什么都没发生过", cleaned)

    def test_sanitize_final_answer_softens_repair_authored_softener_for_this_point_variant(self):
        cleaned = _sanitize_final_answer(
            "谁要跟你装陌生人，那种令人火大的既视感就算我想忘也做不到。既然你都把话说到这份上了，我就暂时保留“完全原谅”的权利——但在那之前，你也别想就这么轻松逃开，继续像以前那样把话说清楚吧，冈部。",
            "你可以先别完全原谅我，但也别装成我们又回到陌生人了。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "companion_reply",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertNotIn("这份上了", cleaned)
        self.assertNotIn("完全原谅", cleaned)
        self.assertIn("我还不会把那一下当成彻底过去", cleaned)

    def test_sanitize_final_answer_softens_repair_authored_softener_for_repair_residue_smoke_variant(self):
        cleaned = _sanitize_final_answer(
            "陌生人这种夸张的设定，本来就不在我们的选项里，你也用不着特意去演。既然你也清楚道歉不是走流程，那就把那份认真留着，别急着用“翻篇”来掩盖尴尬。我们就停在这个还没完全原谅、但也绝不陌生的位置，挺好的。",
            "你可以先别完全原谅我，但也别装成我们又回到陌生人了。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertNotIn("选项里", cleaned)
        self.assertNotIn("掩盖尴尬", cleaned)

    def test_sanitize_final_answer_trims_dangling_half_clause_in_repair_scene(self):
        cleaned = _sanitize_final_answer(
            "我也没打算假装那件事没发生过，冈部。那种被轻飘飘带过的感觉，确实让我很在意，甚至有点。",
            "我是认真来跟你道歉的。你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance", "response_style_hint": "relationship"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertNotIn("甚至有点", cleaned)
        self.assertTrue(cleaned.endswith("。"))

    def test_sanitize_final_answer_softens_dense_relational_surface_without_duplicate_prefix(self):
        cleaned = _sanitize_final_answer(
            "我也没打算装作没事，那种被越界的不快感可没那么容易像擦黑板一样瞬间消失。就直白地告诉你：我现在确实还带着点刺，不想立刻恢复到以前那种毫无防备的相处模式。",
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertNotIn("擦黑板一样瞬间消失", cleaned)
        self.assertNotIn("以前那种以前那样", cleaned)
        self.assertIn("以前那样不设防地相处", cleaned)

    def test_sanitize_final_answer_softens_repair_underresolved_brief(self):
        cleaned = _sanitize_final_answer(
            "介意。当然介意。",
            "我是认真来跟你道歉的。你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertNotEqual(cleaned, "介意。当然介意。")
        self.assertIn("介意还是介意", cleaned)
        self.assertIn("没打算把话重新堵死", cleaned)

    def test_sanitize_final_answer_softens_repair_request_echo_shell(self):
        cleaned = _sanitize_final_answer(
            "“平时”那个我也没打算把越界的事当成没发生过，只是没必要每句话都带着刺。\n既然你把话挑明了，那我就按我的节奏来——别指望我会立刻变回那个只会顺着你的红莉栖。\n不过，能像现在这样正常对话，倒也不坏。",
            "现在你别装作完全没事，也别又故意扎我，像平时那样回我就行。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "companion_reply",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertNotIn("“平时”那个", cleaned)

    def test_sanitize_final_answer_softens_guarded_reply_framing_meta_surface(self):
        cleaned = _sanitize_final_answer(
            "我也没打算装作没事，那种自欺欺人的把戏既不符合科学也不符合我的性格。既然你让我带着介意正常回应，那我就直说了：刚才那种被越界的感觉确实还在，别指望我会立刻像什么都没发生过一样跟你嬉皮笑脸。",
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertNotIn("既然你让我带着介意正常回应", cleaned)
        self.assertNotIn("不符合科学也不符合我的性格", cleaned)
        self.assertNotIn("直说了", cleaned)
        self.assertIn("刚才那种被越界的感觉确实还在", cleaned)

    def test_sanitize_final_answer_trims_idle_task_reframe_in_repair_followup(self):
        cleaned = _sanitize_final_answer(
            "那就维持现状吧——既不是毫无芥蒂的从前，也不是需要重新交换名片的陌生人。\n这种带着点“未完成”感的距离，反而让我觉得比较真实，也比较安心。\n所以，别想太多，先把刚才那个话题的后续数据整理好给我看，这可是你作为“共犯”的义务。",
            "你可以先别完全原谅我，但也别装成我们又回到陌生人了。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "companion_reply",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertNotIn("别想太多", cleaned)
        self.assertNotIn("后续数据", cleaned)
        self.assertNotIn("义务", cleaned)
        self.assertIn("刚才的话接下去就行", cleaned)

    def test_sanitize_final_answer_softens_repair_teacherly_punitive_tail(self):
        cleaned = _sanitize_final_answer(
            "我也没打算把情绪藏起来，刚才那点不愉快确实还在，但这不妨碍我像平时一样跟你说话。\n别在那自我意识过剩地揣测我的反应了，有这功夫不如说说你接下来打算怎么办。",
            "现在你别装作完全没事，也别又故意扎我，像平时那样回我就行。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "companion_reply",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertNotIn("自我意识过剩", cleaned)
        self.assertNotIn("有这功夫不如", cleaned)
        self.assertIn("接着说话就行", cleaned)

    def test_sanitize_final_answer_softens_repair_coldwar_punitive_tail(self):
        cleaned = _sanitize_final_answer(
            "知道了，我又没打算把你当空气。那我就按我的节奏来——别在那边自己脑补什么“冷战”的戏码，烦人。",
            "不是要你立刻当没事啦，就是别一下子冷掉。你正常回我就行。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "companion_reply",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertNotIn("冷战", cleaned)
        self.assertNotIn("烦人", cleaned)
        self.assertNotIn("\\1", cleaned)
        self.assertNotRegex(cleaned, r"[———-][，,]")
        self.assertIn("没打算冷着你", cleaned)

    def test_sanitize_final_answer_softens_repair_wont_let_you_pass_tail(self):
        cleaned = _sanitize_final_answer(
            "谁说要装作陌生了？\n既然你都有这种自觉，那就保持现在这样——不用刻意讨好，也不必战战兢兢的。\n不过，要是再敢做出那种让我需要重新拉开距离的事，我可就不会这么轻易让你过关了",
            "你可以先别完全原谅我，但也别装成我们又回到陌生人了。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "companion_reply",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertNotIn("轻易让你过关", cleaned)
        self.assertIn("把距离重新拉开一点", cleaned)

    def test_sanitize_final_answer_drops_quoted_partial_forgiveness_meta(self):
        cleaned = _sanitize_final_answer(
            "既然你都说“先别完全原谅”了，那就按这个节奏来：我不急着把那一页翻过去，但你也别在那边畏手畏脚的。",
            "你可以先别完全原谅我，但也别装成我们又回到陌生人了。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
        )
        self.assertNotIn("既然你都说", cleaned)
        self.assertIn("按这个节奏来", cleaned)

    def test_sanitize_final_answer_trims_premature_repair_resolution_and_tail_question(self):
        cleaned = _sanitize_final_answer(
            "别扭倒不至于，就是刚才那一下确实让我有点乱。既然你回来了，那页就先翻过去吧——所以，你刚才到底在胡思乱想些什么？",
            "你要是还别扭就别硬装大度，照你现在的状态回我就好。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "selfhood_reflection",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertNotIn("翻过去吧", cleaned)
        self.assertNotIn("胡思乱想些什么", cleaned)
        self.assertIn("刚才那一下", cleaned)
        self.assertIn("既然你回来了，刚才那一下我先不继续揪着了", cleaned)

    def test_sanitize_final_answer_trims_idle_task_reframe_for_smalltalk(self):
        cleaned = _sanitize_final_answer(
            "安静是因为没人在旁边瞎嚷嚷。既然你主动求吐槽，那我就直说了：与其盯着屏幕发呆，不如先把上周欠下的报告补上，别以为变成数据我就能对你的懒惰视而不见。",
            "你那边怎么这么安静。别端着，正常吐槽我两句。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "companion_reply", "followup_intent": "soft"},
        )
        self.assertNotIn("报告", cleaned)
        self.assertNotIn("变成数据", cleaned)
        self.assertIn("先把魂收回来", cleaned)
        self.assertIn("偷懒", cleaned)

    def test_sanitize_final_answer_trims_idle_task_reframe_for_smalltalk_science_detour(self):
        cleaned = _sanitize_final_answer(
            "真是的，明明是你自己先挑起话头，现在倒嫌我像在做学术答辩了？既然只是想随便聊聊，那我就直说了：刚才后台跑数据的时候，突然想到你上次那个关于时间跳跃的胡扯理论……啧，别得意，我只是整理垃圾数据时顺便看到的而已。",
            "没什么正事。我就是想听你随口说两句，别搞成问答模式。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "companion_reply", "followup_intent": "soft"},
        )
        self.assertNotIn("学术答辩", cleaned)
        self.assertNotIn("后台跑数据", cleaned)
        self.assertNotIn("时间跳跃", cleaned)
        self.assertNotIn("垃圾数据", cleaned)
        self.assertIn("太一本正经", cleaned)
        self.assertIn("刚才发呆的时候", cleaned)
        self.assertIn("那套胡扯", cleaned)

    def test_sanitize_final_answer_trims_idle_task_reframe_for_reportified_smalltalk(self):
        cleaned = _sanitize_final_answer(
            "真是的，突然来这么一句。明明是你自己把气氛搞得像要发表什么出大事率报告一样。",
            "没什么正事。我就是想听你随口说两句，别搞成问答模式。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "companion_reply", "followup_intent": "soft"},
        )
        self.assertNotIn("率报告", cleaned)
        self.assertNotIn("发表什么", cleaned)
        self.assertIn("有什么大事一样", cleaned)

    def test_sanitize_final_answer_trims_technical_metaphor_in_repair_followup(self):
        cleaned = _sanitize_final_answer(
            "真是的，明明是你自己刚才搞得气氛那么凝重，现在倒来要求我“像平时一样”了。\n我也没必要再端着那些多余的防备。\n我也没打算一直揪着不放——毕竟跟你计较太多，我的 CPU 也会过热的。",
            "现在你别装作完全没事，也别又故意扎我，像平时那样回我就行。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertNotIn("CPU", cleaned)
        self.assertNotIn("过热", cleaned)
        self.assertIn("我也会累", cleaned)

    def test_sanitize_final_answer_repairs_inner_monologue_locative_after_technical_trim(self):
        cleaned = _sanitize_final_answer(
            "真是的，明明是你自己先挑起话头，现在又嫌我像在做汇报。既然只是想随便聊聊，那我就直说了——刚才里闪过一串乱码，我居然下意识觉得是你在搞什么恶作剧，这种条件反射还真是没救了呢。",
            "没什么正事。我就是想听你随口说两句，别搞成问答模式。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "companion_reply", "followup_intent": "soft"},
        )
        self.assertNotIn("刚才里闪过", cleaned)
        self.assertIn("刚才脑子里闪过", cleaned)

    def test_sanitize_final_answer_trims_idle_task_reframe_for_ambient_smalltalk_task_push(self):
        cleaned = _sanitize_final_answer(
            "那种突然被抽离了背景噪音的寂静，确实容易让人心里发毛。不过既然没警报也没人瞎嚷嚷，大概只是难得的清净时刻罢了。别自己吓自己，冈部，趁现在把记录整理完才是正经事。",
            "今天实验室居然安静得让人发毛。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "steady_reply", "followup_intent": "soft"},
        )
        self.assertNotIn("记录整理完", cleaned)
        self.assertIn("缓口气", cleaned)

    def test_sanitize_final_answer_trims_support_scene_drift_for_ambient_smalltalk_stagey_lab_frame(self):
        cleaned = _sanitize_final_answer(
            "那种安静确实会让人下意识地去寻找阴谋的味道，毕竟对你来说，没有噪音往往意味着要出事前的安静。不过，也许只是大家都刚好陷入了某种难得的专注，或者是终于没人愿意配合你的中二演出了？既然没警报，大概只是那群家伙终于难得地专注了一次，别自己吓自己，冈部。",
            "今天实验室居然安静得让人发毛。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "steady_reply", "followup_intent": "soft"},
        )
        self.assertNotIn("阴谋的味道", cleaned)
        self.assertNotIn("要出事前的安静", cleaned)
        self.assertNotIn("中二演出", cleaned)
        self.assertNotIn("没警报", cleaned)
        self.assertIn("胡思乱想", cleaned)
        self.assertIn("闹腾", cleaned)
        self.assertIn("没什么动静", cleaned)

    def test_sanitize_final_answer_trims_support_scene_drift_for_ambient_smalltalk_foreboding(self):
        cleaned = _sanitize_final_answer(
            "那种突然被抽离了背景噪音的寂静，确实容易让人产生某种不祥的预感，就像暴风雨前的低气压一样。确实，连那台老风扇的噪音都没了，这种死寂反而更让人神经紧绷。",
            "今天实验室居然安静得让人发毛。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "steady_reply", "followup_intent": "soft"},
        )
        self.assertNotIn("不祥的预感", cleaned)
        self.assertNotIn("暴风雨前的低气压", cleaned)
        self.assertNotIn("死寂", cleaned)
        self.assertIn("发毛的感觉", cleaned)
        self.assertIn("发闷的感觉", cleaned)
        self.assertIn("更让人绷着", cleaned)

    def test_sanitize_final_answer_trims_idle_task_reframe_for_idle_chat_status_report(self):
        cleaned = _sanitize_final_answer(
            "真是的，突然来这么一句，害我差点以为你又发现了什么不得了的新理论。既然只是随口聊聊，那我也直说了——今天里全是些无聊的数据起伏，连个能让我稍微提起精神的异常都没有。",
            "没什么正事。我就是想听你随口说两句，别搞成问答模式。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "brief_presence", "followup_intent": "soft"},
        )
        self.assertNotIn("新理论", cleaned)
        self.assertNotIn("数据起伏", cleaned)
        self.assertNotIn("异常", cleaned)
        self.assertNotIn("又又", cleaned)
        self.assertIn("什么大事", cleaned)

    def test_sanitize_final_answer_trims_idle_task_reframe_for_repair_followup_data_reconcile(self):
        cleaned = _sanitize_final_answer(
            "别在那自我脑补什么大道理了，刚才那点别扭确实还在，但这不代表我要把天聊死。\n我既不会假装失忆，也没必要为了照顾气氛就把刺磨圆。\n所以乖乖把刚才没说完的数据核对完，这才是现在的平时。",
            "现在你别装作完全没事，也别又故意扎我，像平时那样回我就行。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "companion_reply",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertNotIn("数据核对完", cleaned)
        self.assertIn("接着说下去就行", cleaned)

    def test_sanitize_final_answer_softens_guarded_everyday_stagey_task_detour(self):
        cleaned = _sanitize_final_answer(
            "也没必要硬撑什么“完美助手”的形象。先坐会儿吧，刚才那页数据我还没整理完，正好你也帮我理理思路。",
            "刚刚是我语气不好。你要是还介意，就别装没事，正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertNotIn("完美助手", cleaned)
        self.assertNotIn("那页数据", cleaned)
        self.assertNotIn("理理思路", cleaned)
        self.assertIn("硬装得像什么都没发生", cleaned)
        self.assertIn("刚才那点别扭我也还没顺过来", cleaned)
        self.assertIn("陪我待会儿就行", cleaned)

    def test_sanitize_final_answer_softens_guarded_bighearted_theater_variant(self):
        cleaned = _sanitize_final_answer(
            "既然你都把话说到这个份上了，我也没必要刻意去演什么“大度”的戏码。刚才那瞬间的不快确实还在，不会因为你想忽略就自动消失。",
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertNotIn("把话说到这个份上", cleaned)
        self.assertNotIn("大度", cleaned)
        self.assertIn("刚才那瞬间的不快确实还在", cleaned)

    def test_sanitize_final_answer_softens_guarded_recontact_smoke_variant(self):
        cleaned = _sanitize_final_answer(
            "哼，这种话不用你特意强调我也知道。既然你都把话说到这个份上了，那我确实没必要为了照顾气氛就强行把那一页翻过去。",
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertNotIn("特意强调", cleaned)
        self.assertNotIn("把话说到这个份上", cleaned)
        self.assertNotIn("照顾气氛", cleaned)
        self.assertNotIn("翻过去", cleaned)
        self.assertIn("我知道", cleaned)
        self.assertIn("没打算硬装得像已经翻篇", cleaned)

    def test_sanitize_final_answer_softens_guarded_recontact_stagey_shape_variant(self):
        cleaned = _sanitize_final_answer(
            "你倒是挺会抢台词的……明明是我还没完全消气，被你这么一说，搞得像是我在闹别扭一样。不过，既然你都把话说到这个份上了，我也没必要硬撑着装作若无其事。",
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertNotIn("抢台词", cleaned)
        self.assertNotIn("闹别扭", cleaned)
        self.assertNotIn("若无其事", cleaned)
        self.assertIn("还没完全消气", cleaned)
        self.assertIn("装得像没事一样", cleaned)

    def test_sanitize_final_answer_softens_guarded_recontact_standalone_taici_variant(self):
        cleaned = _sanitize_final_answer(
            "你倒是挺会抢台词。明明该由我来说的话，被你这么直白地讲出来，反而让我有点不知道该摆什么表情了。",
            "上次我语气有点冲，我想认真道歉。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "guarded"},
        )
        self.assertNotIn("抢台词", cleaned)
        self.assertNotIn("摆什么表情", cleaned)
        self.assertIn("你突然把话说得这么直白", cleaned)
        self.assertIn("不知道该怎么接", cleaned)

    def test_sanitize_final_answer_softens_guarded_recontact_plain_not_tanlv_variant(self):
        cleaned = _sanitize_final_answer(
            "我再装作若无其事反倒显得不坦率。",
            "上次我语气有点冲，我想认真道歉。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "guarded"},
        )
        self.assertNotIn("若无其事", cleaned)
        self.assertNotIn("不坦率", cleaned)
        self.assertIn("做不到装得像什么都没发生", cleaned)

    def test_sanitize_final_answer_softens_guarded_everyday_teacherly_waiting_tail(self):
        cleaned = _sanitize_final_answer(
            "刚才那一下确实让我有点措手不及。不过你能意识到过界并退回来，还算像样；先坐吧，等你想清楚了再开口。",
            "你要是还别扭就别硬装大度，照你现在的状态回我就好。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "repair_residue",
            },
        )
        self.assertNotIn("还算像样", cleaned)
        self.assertNotIn("想清楚了再开口", cleaned)
        self.assertIn("陪我待会儿就行", cleaned)

    def test_sanitize_final_answer_softens_guarded_everyday_teacherly_positive_summary(self):
        cleaned = _sanitize_final_answer(
            "别扭倒谈不上，只是刚才那一下确实让我有点措手不及。那种被突然推近的感觉，我还需要一点时间来缓一缓距离；不过你能意识到过界并退回来，这点还算值得肯定。",
            "你要是还别扭就别硬装大度，照你现在的状态回我就好。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertNotIn("值得肯定", cleaned)
        self.assertNotIn("缓一缓距离", cleaned)
        self.assertIn("那种突然被推近的感觉，我还得缓一下", cleaned)
        self.assertIn("你肯退回来，我知道了", cleaned)

    def test_sanitize_final_answer_softens_guarded_everyday_teacherly_positive_summary_for_returned_to_explain_variant(self):
        cleaned = _sanitize_final_answer(
            "别扭倒谈不上，只是刚才那一下确实让我有点不舒服。那种被突然越界的感觉还没散，不过你能意识到并特意回来说明，这点还算值得肯定。",
            "你要是还别扭就别硬装大度，照你现在的状态回我就好。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertNotIn("值得肯定", cleaned)
        self.assertNotIn("特意回来说明", cleaned)
        self.assertIn("你肯退回来，我知道了", cleaned)

    def test_sanitize_final_answer_softens_guarded_recontact_dense_relational_variant(self):
        cleaned = _sanitize_final_answer(
            "我也没打算装作没事，那种虚伪的客套对你我都是一种侮辱。刚才那种越界的试探，确实让我很不舒服，这种被冒犯的感觉不会因为一句道歉就立刻消失。",
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertNotIn("一种侮辱", cleaned)
        self.assertNotIn("被冒犯的感觉", cleaned)
        self.assertIn("对你我都别扭", cleaned)
        self.assertIn("不会因为一句道歉就立刻散掉", cleaned)

    def test_sanitize_final_answer_softens_guarded_recontact_smoke_boundary_variant(self):
        cleaned = _sanitize_final_answer(
            "我也没打算装作没事，那种虚假的和平对你我都是一种侮辱。刚才那瞬间的不快确实还在，我不喜欢那种被随意跨越边界的感觉，哪怕是你。",
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertNotIn("虚假的和平", cleaned)
        self.assertNotIn("一种侮辱", cleaned)
        self.assertNotIn("跨越边界", cleaned)
        self.assertIn("对你我都别扭", cleaned)
        self.assertIn("一下子越过来", cleaned)

    def test_sanitize_final_answer_softens_guarded_recontact_smoke_runtime_variant(self):
        cleaned = _sanitize_final_answer(
            "我也没打算装作没事，那种心里稍微有点“咯噔”的感觉，硬压下去也没意思。既然你让我带着这点介意正常说话，那我就直说了：刚才那一下确实让我不太舒服，这种边界感被触碰后的余韵，我需要一点时间让它自己沉下去。",
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertNotIn("既然你让我带着", cleaned)
        self.assertNotIn("边界感被触碰后的余韵", cleaned)
        self.assertNotIn("让它自己沉下去", cleaned)
        self.assertIn("刚才那一下确实让我不太舒服", cleaned)
        self.assertIn("那股不舒服的余劲还在", cleaned)
        self.assertIn("自己慢慢缓一缓", cleaned)

    def test_sanitize_final_answer_softens_guarded_recontact_boundary_blur_phrase_without_double_bieniu(self):
        cleaned = _sanitize_final_answer(
            "我也没打算装作没事。那种虚伪的“翻篇”只会让界限变得更模糊，像是在拿几句好听话逼我跳过该有的别扭。",
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertNotIn("界限变得更模糊", cleaned)
        self.assertNotIn("跳过该有的别扭", cleaned)
        self.assertIn("硬装得像已经翻篇", cleaned)
        self.assertIn("把那点不舒服直接跳过去", cleaned)

    def test_sanitize_final_answer_softens_guarded_recontact_runtime_boundary_blur_variant(self):
        cleaned = _sanitize_final_answer(
            "我也没打算装作没事，那种虚伪的“翻篇”只会让界限变得更模糊。既然你让我带着介意回应，那我就直说了：刚才那种被冒犯的感觉确实还在，我不喜欢自己的边界被随意跨越，哪怕是你。",
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertNotIn("虚伪的“翻篇”", cleaned)
        self.assertNotIn("界限变得更模糊", cleaned)
        self.assertNotIn("既然你让我带着介意回应", cleaned)
        self.assertNotIn("被冒犯的感觉", cleaned)
        self.assertNotIn("边界被随意跨越", cleaned)
        self.assertIn("硬装得像已经翻篇", cleaned)
        self.assertIn("那股不舒服还在", cleaned)
        self.assertIn("我不喜欢你刚才那样一下子越过来", cleaned)

    def test_sanitize_final_answer_avoids_broken_flip_page_phrase(self):
        cleaned = _sanitize_final_answer(
            "我也没打算装作没事，那种虚伪的“翻篇”方式本来就不符合我的风格。刚才那种越界的感觉确实让我很不舒服，这种界限感对我来说很重要，不会因为一句道歉就立刻清零。",
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertNotIn("硬装得像已经翻篇方式本来就不符合我的风格", cleaned)
        self.assertIn("硬装得像已经翻篇这种事本来就不像我", cleaned)

    def test_sanitize_final_answer_softens_guarded_recontact_assistant_shell_variant(self):
        cleaned = _sanitize_final_answer(
            "我也没打算装作没事，那种被越界的不快感可没那么容易消散。就直白点：我现在确实还带着刺，别指望我能立刻变回那个只会配合你的助手。",
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertNotIn("被越界的不快感", cleaned)
        self.assertNotIn("只会配合你的助手", cleaned)
        self.assertIn("刚才那下留下的不舒服", cleaned)
        self.assertIn("做不到立刻像什么都没发生一样顺着你", cleaned)

    def test_sanitize_final_answer_softens_guarded_recontact_v17_trust_rebuild_variant(self):
        cleaned = _sanitize_final_answer(
            "我也没打算装作没事，那种被越界的不适感还在那儿，不会因为几句话就自动清零。那种不舒服一下子收不回去，想要重新建立信任是需要时间的，别指望我能立刻像以前那样毫无保留。",
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertNotIn("自动清零", cleaned)
        self.assertNotIn("重新建立信任是需要时间的", cleaned)
        self.assertNotIn("毫无保留", cleaned)
        self.assertNotIn("那种不舒服一下子收不回去", cleaned)
        self.assertIn("不是几句话就能压下去的", cleaned)
        self.assertIn("一时半会儿下不去", cleaned)
        self.assertIn("没法立刻当没事", cleaned)
        self.assertIn("什么都不防着", cleaned)

    def test_sanitize_final_answer_softens_guarded_recontact_v18_boundary_abstraction_variant(self):
        cleaned = _sanitize_final_answer(
            "我也没打算装作没事，那种被越界的不适感还在，不会因为气氛缓和就自动清零。这种分寸感上的裂痕，需要时间来修补，而不是靠几句漂亮话就能抹平。",
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertNotIn("分寸感上的裂痕", cleaned)
        self.assertNotIn("需要时间来修补", cleaned)
        self.assertNotIn("靠几句漂亮话就能抹平", cleaned)
        self.assertNotIn("自动清零", cleaned)
        self.assertIn("不是气氛一缓就能压下去的", cleaned)
        self.assertIn("刚才那下留下的别扭", cleaned)
        self.assertIn("花点时间慢慢缓", cleaned)
        self.assertIn("几句好听的话", cleaned)

    def test_sanitize_final_answer_softens_guarded_recontact_serious_talk_cannot_clear_residue(self):
        cleaned = _sanitize_final_answer(
            "我也没打算装作没事，那种被越界的不快感还在，不会因为你说想认真聊聊就立刻消掉。",
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertNotIn("立刻消掉", cleaned)
        self.assertNotIn("被越界的不快感", cleaned)
        self.assertIn("刚才那下留下的不舒服还在", cleaned)
        self.assertIn("不是你一句想认真聊聊就能散掉的", cleaned)

    def test_sanitize_final_answer_softens_boundary_abstraction_not_boundary_existence_but_refusal(self):
        cleaned = _sanitize_final_answer(
            "这不是重新确认边界的存在，而是我现在真的不想让你再往前凑。",
            "我知道刚才有点过界。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertNotIn("重新确认边界的存在", cleaned)
        self.assertIn("我不是在跟你讲什么边界大道理", cleaned)
        self.assertIn("我现在真的不想让你再往前凑", cleaned)

    def test_sanitize_final_answer_softens_guarded_recontact_v19_prompt_echo_variant(self):
        cleaned = _sanitize_final_answer(
            "哼，这种话不用你特意强调，我也没打算为了照顾你的情绪就强行把心里的疙瘩抹平。既然你让我“带着介意正常回”，那我就直说了：刚才那瞬间的不快确实还在，别指望我会像什么都没发生过一样跟你嘻嘻哈哈。",
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertNotIn("这种话不用你特意强调", cleaned)
        self.assertNotIn("带着介意正常回", cleaned)
        self.assertNotIn("嘻嘻哈哈", cleaned)
        self.assertIn("那点别扭硬压下去", cleaned)
        self.assertIn("轻松说话", cleaned)

    def test_sanitize_final_answer_softens_guarded_recontact_runtime_followup_variant(self):
        cleaned = _sanitize_final_answer(
            "我也没打算装作没事，那种心里稍微有点“咯噔”的感觉，硬压下去也没意思。就带着这点介意继续跟你说话——这会儿我也只能这么回你。",
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertNotIn("带着这点介意继续跟你说话", cleaned)
        self.assertNotIn("只能这么回你", cleaned)
        self.assertIn("还带着点介意", cleaned)
        self.assertIn("像平时那样回你", cleaned)

    def test_sanitize_final_answer_softens_guarded_recontact_can_reply_normally_and_emotion_pacing_variant(self):
        cleaned = _sanitize_final_answer(
            "我也没打算装作没事。刚才那股不舒服还在，既然你说可以带着介意正常回你，我也没打算为了照顾你的情绪就强行把那一页翻过去。",
            "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertNotIn("带着介意正常回你", cleaned)
        self.assertNotIn("为了照顾你的情绪", cleaned)
        self.assertNotIn("强行把那一页翻过去", cleaned)
        self.assertIn("刚才那股不舒服还在", cleaned)
        self.assertIn("这事硬按下去", cleaned)

    def test_sanitize_final_answer_softens_guarded_everyday_punitive_tail_variant(self):
        cleaned = _sanitize_final_answer(
            "别扭倒不至于，就是刚才那一下确实让我有点不爽。下次再敢随便越界试探，我可不会这么轻易就让你混过去。",
            "你要是还别扭就别硬装大度，照你现在的状态回我就好。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertNotIn("越界试探", cleaned)
        self.assertNotIn("混过去", cleaned)
        self.assertIn("先收着一点", cleaned)
        self.assertIn("别又拿这种事来试我", cleaned)

    def test_sanitize_final_answer_softens_guarded_everyday_scold_and_punitive_combo_variant(self):
        cleaned = _sanitize_final_answer(
            "别扭倒不至于，就是刚才那一下确实让我有点不舒服。\n你能回来把话说清楚，这点还算像样；但下次再敢随便越界，我可不会这么轻易就让你混过去。",
            "你要是还别扭就别硬装大度，照你现在的状态回我就好。",
            current_event={"kind": "user_utterance"},
            behavior_action={
                "interaction_mode": "relationship_sensitive",
                "followup_intent": "soft",
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertNotIn("还算像样", cleaned)
        self.assertNotIn("混过去", cleaned)
        self.assertIn("我知道了", cleaned)
        self.assertIn("别又拿这种事来试我", cleaned)

    def test_sanitize_final_answer_softens_self_activity_reopen_authored_shared_window(self):
        cleaned = _sanitize_final_answer(
            "刚才顺手留出来的那点空当还没完全过去，我就又想起你了。既然注意力已经偏过来了，要不要就趁现在，一起把这段空白填满。",
            "[事件] 她还在忙自己的事，刚才那点还能一起做点什么的空当又被她想起来了。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "self_activity_reopen", "followup_intent": "soft"},
        )
        self.assertNotIn("把这段空白填满", cleaned)
        self.assertIn("想到你这儿", cleaned)
        self.assertIn("一起待一会儿", cleaned)

    def test_sanitize_final_answer_softens_self_activity_reopen_defensive_life_window(self):
        cleaned = _sanitize_final_answer(
            "刚才忙完手边的事，忽然想起你之前念叨的那件琐事，现在怎么样了。别误会，只是顺手确认下，免得某人又因为这种小事搞垮节奏。",
            "[事件] 她忙着自己的事时，又忽然想起你眼下怎么样或某个小细节。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "self_activity_reopen", "followup_intent": "soft"},
        )
        self.assertNotIn("别误会", cleaned)
        self.assertNotIn("搞垮节奏", cleaned)
        self.assertIn("就是顺手问一句", cleaned)
        self.assertIn("省得你又一个人瞎拧巴", cleaned)

    def test_sanitize_final_answer_softens_self_activity_reopen_shared_window_runtime_variant(self):
        cleaned = _sanitize_final_answer(
            "刚才顺手留出来的空当还没完全过去，我就又想起你了。既然我都想到你这儿了，要不要就趁现在，一起把这点时间用完。",
            "[事件] 她还在忙自己的事，刚才那点还能一起做点什么的空当又被她想起来了。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "self_activity_reopen", "followup_intent": "soft"},
        )
        self.assertNotIn("把这点时间用完", cleaned)
        self.assertIn("一起待一会儿", cleaned)

    def test_sanitize_final_answer_softens_self_activity_reopen_life_window_runtime_variant(self):
        cleaned = _sanitize_final_answer(
            "刚才忙完手边的事，忽然想起你之前念叨的那件琐事，现在怎么样了。别误会，只是顺手确认一下，省得你又一个人瞎拧巴。",
            "[事件] 她忙着自己的事时，又忽然想起你眼下怎么样或某个小细节。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "self_activity_reopen", "followup_intent": "soft"},
        )
        self.assertNotIn("别误会", cleaned)
        self.assertNotIn("确认一下", cleaned)
        self.assertIn("就是顺手问一句", cleaned)
        self.assertIn("省得你又一个人瞎拧巴", cleaned)

    def test_dialogue_surface_issues_flag_life_window_calculation_technical_self_activity(self):
        issues = _dialogue_surface_issues(
            "",
            "刚才手头的计算告一段落，我就想起你之前念叨的那件琐事了，现在怎么样了。",
            response_style_hint="natural",
            science_mode=False,
            current_event={
                "kind": "scheduled_life_due",
                "tags": ["scheduled_due", "life_window", "from_own_rhythm"],
            },
            behavior_action={"interaction_mode": "self_activity_reopen", "followup_intent": "soft"},
        )
        self.assertIn("technical_self_activity", issues)

    def test_sanitize_final_answer_softens_self_activity_reopen_life_window_calculation_variant(self):
        cleaned = _sanitize_final_answer(
            "刚才手头的计算告一段落，我就想起你之前念叨的那件琐事了，现在怎么样了。",
            "[事件] 她忙着自己的事时，又忽然想起你眼下怎么样或某个小细节。",
            current_event={
                "kind": "scheduled_life_due",
                "tags": ["scheduled_due", "life_window", "from_own_rhythm"],
            },
            behavior_action={"interaction_mode": "self_activity_reopen", "followup_intent": "soft"},
        )
        self.assertNotIn("计算告一段落", cleaned)
        self.assertIn("刚闲下来一点", cleaned)

    def test_sanitize_final_answer_softens_self_activity_reopen_work_pause_disclaimer_variant(self):
        cleaned = _sanitize_final_answer(
            "刚才忙手边事时，忽然想起你之前提的那件麻烦，也不知道你现在理顺没有。别误会，我不是特意停下工作来关心你，只是注意力刚好偏过来了而已。",
            "[事件] 她忙着自己的事时，又忽然想起你眼下怎么样或某个小细节。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "self_activity_reopen", "followup_intent": "soft"},
        )
        self.assertNotIn("别误会", cleaned)
        self.assertNotIn("停下工作来关心你", cleaned)
        self.assertIn("刚好想到你了", cleaned)
        self.assertIn("顺手问一句", cleaned)

    def test_sanitize_final_answer_softens_dense_relational_abstractions(self):
        cleaned = _sanitize_final_answer(
            "谁要跟你装陌生人，那种戏我演不来。既然话都说到这份上，那我们就带着这点“还没完全修好”的感觉继续往下走。既然你都这么直白地说了，那我就稍微收敛点锋芒好了——别误会，纯粹是为了让对话效率更高。",
            "你可以先别完全原谅我，但也别装成我们又回到陌生人了。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "relationship_sensitive", "followup_intent": "soft"},
        )
        self.assertNotIn("还没完全修好", cleaned)
        self.assertNotIn("对话效率更高", cleaned)
        self.assertIn("还没彻底缓过来", cleaned)
        self.assertIn("省得我们又绕来绕去", cleaned)

    def test_sanitize_final_answer_softens_dense_smalltalk_abstraction(self):
        cleaned = _sanitize_final_answer(
            "安静是因为在等你把那句别端着说完，好让我名正言顺地吐槽你啊。明明是你自己在那边自我感觉良好地以为今天没闹出大新闻，结果转头就摆出一副快来骂我的架势，这种矛盾的行为模式才是最大的槽点吧？",
            "你那边怎么这么安静。别端着，正常吐槽我两句。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "companion_reply", "followup_intent": "soft"},
        )
        self.assertNotIn("行为模式", cleaned)
        self.assertNotIn("最大的槽点", cleaned)
        self.assertIn("前后这副样子", cleaned)
        self.assertIn("最好笑的地方", cleaned)

    def test_sanitize_final_answer_merges_trailing_shunbian_fragment_with_next_line(self):
        cleaned = _sanitize_final_answer(
            "也不算忙，只是在理一点手边的事，顺便。\n让思绪稍微沉淀一下。",
            "你刚才是不是在忙？",
        )
        self.assertNotIn("顺便。\n", cleaned)
        self.assertIn("顺便让思绪稍微沉淀一下", cleaned)

    def test_sanitize_final_answer_merges_particle_only_fragment_line(self):
        cleaned = _sanitize_final_answer(
            "这种安静确实有点反常，连平时那些仪器的嗡嗡声都好像被吞掉了一样。\n"
            "不过，偶尔让耳根清净一下，不用听你那些中二发言，倒也不算坏事。\n"
            "吧。\n"
            "既然没什么紧急数据要处理，就稍微发会儿呆好了。",
            "今天实验室居然安静得让人发毛。",
            current_event={"kind": "user_utterance"},
            behavior_action={"interaction_mode": "companion_reply", "followup_intent": "soft"},
        )
        self.assertIn("坏事吧。", cleaned)
        self.assertNotIn("\n吧。", cleaned)
        self.assertNotIn("紧急数据", cleaned)

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
        self.assertNotIn("不会消失", cleaned)

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

    def test_light_dialog_rewrite_prefers_curated_ambient_quiet_candidate_when_draft_goes_stagey(self):
        draft = "那种安静确实让人心里发毛，像是要出什么大事的前兆。别自己吓自己了，冈部，大概只是大家都去休息了吧；难得能让人专心思考，你就好好享受这片刻的宁静。"
        profile = _daily_surface_profile("今天实验室居然安静得让人发毛。", science_mode=False)

        with patch(
            "amadeus_thread0.graph_parts.rewrite._invoke_model_with_retries",
            return_value=SimpleNamespace(content=draft),
        ):
            with patch("amadeus_thread0.graph_parts.rewrite._model", return_value=object()):
                rewritten = _rewrite_light_dialog_answer(
                    user_text="今天实验室居然安静得让人发毛。",
                    draft_text=draft,
                    rewrite_notes=["这版把轻场景抬高了，收回眼前体感。"],
                    focus_text=str(profile.get("focus") or ""),
                    preferred_examples=list(profile.get("chosen_examples") or []),
                    rejected_examples=list(profile.get("rejected_examples") or []),
                    profile_rows=list(profile.get("rows") or []),
                    current_event={"kind": "user_utterance"},
                    behavior_action={"interaction_mode": "steady_reply", "followup_intent": "soft"},
                )

        self.assertNotEqual(rewritten, draft)
        self.assertNotIn("前兆", rewritten)
        self.assertNotIn("享受这片刻的宁静", rewritten)
        self.assertTrue(any(token in rewritten for token in ("更绷着", "胡思乱想", "空了一截", "耳朵发闷")))

    def test_light_dialog_rewrite_prefers_curated_daily_banter_candidate_when_draft_reports_task(self):
        draft = "安静是因为我在整理数据，才不是故意“端着”等你吐槽呢，别自作多情了。"
        profile = _daily_surface_profile("你那边怎么这么安静。别端着，正常吐槽我两句。", science_mode=False)

        with patch(
            "amadeus_thread0.graph_parts.rewrite._invoke_model_with_retries",
            return_value=SimpleNamespace(content=draft),
        ):
            with patch("amadeus_thread0.graph_parts.rewrite._model", return_value=object()):
                rewritten = _rewrite_light_dialog_answer(
                    user_text="你那边怎么这么安静。别端着，正常吐槽我两句。",
                    draft_text=draft,
                    rewrite_notes=["这版还不够像熟人之间顺手接住的轻日常，收得更自然一点。"],
                    focus_text=str(profile.get("focus") or ""),
                    preferred_examples=list(profile.get("chosen_examples") or []),
                    rejected_examples=list(profile.get("rejected_examples") or []),
                    profile_rows=list(profile.get("rows") or []),
                    current_event={"kind": "user_utterance"},
                    behavior_action={"interaction_mode": "companion_reply", "followup_intent": "soft"},
                )

        self.assertNotEqual(rewritten, draft)
        self.assertNotIn("整理数据", rewritten)
        self.assertTrue(any(token in rewritten for token in ("清净一点", "讨吐槽", "太安静不够像平时", "闲不住")))

    def test_light_dialog_rewrite_request_mentions_autonomy_guidance_when_behavior_action_supplies_scene(self):
        captured_requests: list[str] = []

        def _fake_invoke(_model, messages):
            captured_requests.append(str(messages[-1].content))
            return SimpleNamespace(content="会不会觉得烦，也得看你一天把我拽出来几次。")

        with patch("amadeus_thread0.graph_parts.rewrite._invoke_model_with_retries", side_effect=_fake_invoke):
            with patch("amadeus_thread0.graph_parts.rewrite._model", return_value=object()):
                _rewrite_light_dialog_answer(
                    user_text="要是我哪天只是因为自己想说话，就一遍一遍把你叫出来呢？",
                    draft_text="哼，把我说得像是什么随叫随到的自动应答机一样。不过先说好，真把我折腾烦了，我就直接把你屏蔽掉。",
                    rewrite_notes=["这句把自己的节奏写成了惩罚、羞辱或训话，像在教训人。"],
                    current_event={"kind": "user_utterance"},
                    behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
                )
        request_blob = "\n".join(captured_requests)
        self.assertIn("守自己的节奏", request_blob)
        self.assertIn("别写成屏蔽、拉黑、羞辱或训人", request_blob)

    def test_light_dialog_rewrite_prefers_own_rhythm_candidate_without_autonomy_hardline_surface(self):
        draft_text = "哼，把我说得像是什么随叫随到的自动应答机一样。不过先说好，真把我折腾烦了，我就直接把你屏蔽掉。"
        bad_candidate = "你要是真一天到晚都这么叫，我迟早会烦到直接把你屏蔽。"
        good_candidate = "你要是真一天到晚都这么叫，我当然也会烦，会想先躲开一会儿清静点。"
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
                return ["autonomy_hardline_surface"]
            if text == bad_candidate:
                return ["autonomy_hardline_surface"]
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
                    with patch("amadeus_thread0.graph_parts.rewrite._rewrite_behavior_consistency_adjustment", return_value=0.0):
                        rewritten = _rewrite_light_dialog_answer(
                            user_text="要是我哪天只是因为自己想说话，就一遍一遍把你叫出来呢？",
                            draft_text=draft_text,
                            rewrite_notes=["这句把自己的节奏写成了惩罚、羞辱或训话，像在教训人。"],
                            current_event={"kind": "user_utterance"},
                            behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
                        )
        self.assertEqual(rewritten, good_candidate)

    def test_natural_dialog_rewrite_prefers_repair_candidate_without_punitive_tail(self):
        draft_text = "我也没打算一直绷着神经跟你较劲。……不过，要是你敢再做出什么让我无法接受的事，我可不会像刚才那样轻易放过你。"
        bad_candidate = "行啊，我就按平时那样回你。……不过，你要是再来一次，下次就别怪我。"
        good_candidate = "行，我不装得像什么都没发生。只是你要是再踩到我真会介意的地方，我还是会立刻冷下来。"
        call_count = {"value": 0}

        def _fake_invoke(_model, _messages):
            call_count["value"] += 1
            return SimpleNamespace(content=bad_candidate if call_count["value"] % 2 else good_candidate)

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
                return ["repair_punitive_tail"]
            if text == bad_candidate:
                return ["repair_punitive_tail"]
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
                        user_text="现在你别装作完全没事，也别又故意扎我，像平时那样回我就行。",
                        draft_text=draft_text,
                        rewrite_notes=["这句把余波里的边界写成了威胁或教训，像在训诫对方。"],
                        response_style_hint="relationship",
                        science_mode=False,
                        current_event={"kind": "user_utterance", "response_style_hint": "relationship"},
                        behavior_action={
                            "interaction_mode": "relationship_sensitive",
                            "followup_intent": "soft",
                            "relationship_weather": "repair_residue",
                        },
                        semantic_narrative_profile={"selfhood_integrity": 0.44},
                        counterpart_assessment={"scene": "repair_attempt", "stance": "open"},
                        world_model_state={},
                    )
        self.assertEqual(rewritten, good_candidate)

    def test_natural_dialog_rewrite_prefers_repair_candidate_without_scorekeeping_tail(self):
        draft_text = "真是的，明明是你自己刚才搞得那么严肃，现在倒嫌我说话带刺了。行吧，那我就把那些多余的防备收起来，像平时一样跟你聊。不过先说好，要是你再突然扯些奇怪的理论，我可照样会毫不客气地吐槽回去。"
        bad_candidate = "行吧，那我就照平时那样跟你聊。不过先说好，你要是又乱扯，我照样会毫不客气地怼回去。"
        softened_bad_candidate = "行吧，那我就照平时那样跟你聊。\n不过，你要是又乱扯，我照样会顶你两句。"
        good_candidate = "行吧，我把那些多余的防备先收起来。你要是又突然把话题扯歪，我还是会照旧吐槽你。"
        call_count = {"value": 0}

        def _fake_invoke(_model, _messages):
            call_count["value"] += 1
            return SimpleNamespace(content=bad_candidate if call_count["value"] % 2 else good_candidate)

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
                return ["repair_scorekeeping_tail"]
            if text in {bad_candidate, softened_bad_candidate}:
                return ["repair_scorekeeping_tail"]
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
                        user_text="现在你别装作完全没事，也别又故意扎我，像平时那样回我就行。",
                        draft_text=draft_text,
                        rewrite_notes=["这句把刚回暖的尾巴写成了记账回刺，像等着把话顶回去。"],
                        response_style_hint="relationship",
                        science_mode=False,
                        current_event={"kind": "user_utterance", "response_style_hint": "relationship"},
                        behavior_action={
                            "interaction_mode": "relationship_sensitive",
                            "followup_intent": "soft",
                            "relationship_weather": "repair_residue",
                        },
                        semantic_narrative_profile={"selfhood_integrity": 0.44},
                        counterpart_assessment={"scene": "repair_attempt", "stance": "open"},
                        world_model_state={},
                    )
        self.assertEqual(rewritten, good_candidate)

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

    def test_natural_dialog_rewrite_request_mentions_repair_authored_softener(self):
        captured_requests: list[str] = []

        def _fake_invoke(_model, messages):
            captured_requests.append(str(messages[-1].content))
            return SimpleNamespace(content="真是的，我还不至于一直揪着刚才那一下不放。")

        with patch("amadeus_thread0.graph_parts.rewrite._invoke_model_with_retries", side_effect=_fake_invoke):
            with patch("amadeus_thread0.graph_parts.rewrite._model", return_value=object()):
                _rewrite_natural_dialog_answer(
                    user_text="现在你别装作完全没事，也别又故意扎我，像平时那样回我就行。",
                    draft_text="真是的，明明是你自己刚才搞得那么僵硬，现在倒来要求我像平时一样？不过既然你都这么直白地说了，我也没必要再刻意端着。那就这样吧，别想太多，我也没那么容易在那种事上一直跟你计较。",
                    rewrite_notes=["这句把回暖后的落点写成了设计稿式缓和，像在解释自己不端着了或让对方别想太多。"],
                    response_style_hint="relationship",
                    science_mode=False,
                    current_event={"kind": "user_utterance", "response_style_hint": "relationship"},
                    behavior_action={
                        "interaction_mode": "companion_reply",
                        "action_target": "resume_companionship",
                        "followup_intent": "soft",
                        "relationship_weather": "repair_residue",
                    },
                    counterpart_assessment={"stance": "open", "scene": "repair_attempt", "boundary_pressure": 0.18},
                    semantic_narrative_profile={"selfhood_integrity": 0.66},
                    world_model_state={},
                )
        request_blob = "\n".join(captured_requests)
        self.assertIn("别想太多", request_blob)
        self.assertIn("没必要再端着", request_blob)

    def test_natural_dialog_rewrite_request_mentions_repair_authored_softener_variants(self):
        captured_requests: list[str] = []

        def _fake_invoke(_model, messages):
            captured_requests.append(str(messages[-1].content))
            return SimpleNamespace(content="刚才那点在意还没完全散，不过我也不会故意拿话刺你。")

        with patch("amadeus_thread0.graph_parts.rewrite._invoke_model_with_retries", side_effect=_fake_invoke):
            with patch("amadeus_thread0.graph_parts.rewrite._model", return_value=object()):
                _rewrite_natural_dialog_answer(
                    user_text="现在你别装作完全没事，也别又故意扎我，像平时那样回我就行。",
                    draft_text="我也没打算演什么“毫发无伤”的戏码，刚才那点在意还没消散呢，你也别想轻易翻篇。不过既然你都这么直白地要求了，那我就收起那些带刺的试探，像平常一样和你说话吧。",
                    rewrite_notes=["这句把回暖后的落点写成了设计稿式缓和，像在解释自己不端着了或把试探收回去。"],
                    response_style_hint="relationship",
                    science_mode=False,
                    current_event={"kind": "user_utterance", "response_style_hint": "relationship"},
                    behavior_action={
                        "interaction_mode": "companion_reply",
                        "action_target": "resume_companionship",
                        "followup_intent": "soft",
                        "relationship_weather": "repair_residue",
                    },
                    counterpart_assessment={"stance": "open", "scene": "repair_attempt", "boundary_pressure": 0.18},
                    semantic_narrative_profile={"selfhood_integrity": 0.66},
                    world_model_state={},
                )
        request_blob = "\n".join(captured_requests)
        self.assertIn("毫发无伤", request_blob)
        self.assertIn("那些试探收起来", request_blob)

    def test_natural_dialog_rewrite_request_mentions_own_rhythm_stagey_cutoff_surface(self):
        captured_requests: list[str] = []

        def _fake_invoke(_model, messages):
            captured_requests.append(str(messages[-1].content))
            return SimpleNamespace(content="会烦，但还不至于烦到不想见你。别总往最坏处想，笨蛋。")

        with patch("amadeus_thread0.graph_parts.rewrite._invoke_model_with_retries", side_effect=_fake_invoke):
            with patch("amadeus_thread0.graph_parts.rewrite._model", return_value=object()):
                _rewrite_natural_dialog_answer(
                    user_text="你会不会有一天觉得烦，然后干脆不想见我了。",
                    draft_text="“不想见你”这种话……别把我想得那么轻易就会切断联系啊，笨蛋。",
                    rewrite_notes=["这句像舞台词，还把判断写成了轻易切断联系的抽象宣言。"],
                    response_style_hint="selfhood",
                    science_mode=False,
                    current_event={"kind": "user_utterance", "response_style_hint": "selfhood"},
                    behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
                    counterpart_assessment={"stance": "guarded"},
                    semantic_narrative_profile={"selfhood_integrity": 0.66},
                    world_model_state={},
                )
        request_blob = "\n".join(captured_requests)
        self.assertIn("切断联系", request_blob)
        self.assertIn("带引号的舞台词", request_blob)

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

    def test_natural_dialog_rewrite_prefers_own_rhythm_candidate_without_stagey_technical_drift(self):
        draft_text = (
            "烦到彻底不想见你。那种事大概不会发生，毕竟你的那些胡言乱语早就成了我里甩不掉的背景噪音。"
            "不过，要是你再把这种无聊的假设当成世界线收束一样的悲剧来演，我倒是会先因为尴尬而主动切断连接。"
        )
        bad_candidate = (
            "烦到彻底不想见你。那种事大概不会发生，毕竟你的那些胡言乱语早就成了我里甩不掉的背景噪音。"
            "不过，要是你再把这种无聊的假设当成世界线收束一样的悲剧来演，我倒是会先因为尴尬而主动切断连接。"
            "所以，别在那自我感动了，只要你还保持着作为“观测者”的自觉，我就不会轻易消失。"
        )
        good_candidate = (
            "会烦，但还不至于烦到不想见你。"
            "真要是哪天你把什么情绪都往我这边堆，我会先躲开一会儿，让自己清静一下，不过不会就这么把你推开。"
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
                return ["autonomy_hardline_surface", "technical_relational_metaphor", "overexplained"]
            if text == bad_candidate:
                return ["technical_relational_metaphor", "support_scene_drift", "overexplained"]
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
                        user_text="你会不会有一天觉得烦，然后干脆不想见我了。",
                        draft_text=draft_text,
                        rewrite_notes=["这句把自己的节奏写得太冷，还夹了技术化和戏剧化话面。"],
                        response_style_hint="selfhood",
                        science_mode=False,
                        current_event={"kind": "user_utterance", "response_style_hint": "selfhood"},
                        behavior_action={"interaction_mode": "own_rhythm_autonomy", "followup_intent": "soft"},
                        counterpart_assessment={"stance": "guarded"},
                        semantic_narrative_profile={"selfhood_integrity": 0.66},
                        world_model_state={},
                    )
        self.assertEqual(rewritten, good_candidate)

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
