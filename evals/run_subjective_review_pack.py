from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from evals.run_langsmith_evals import _run_graph  # noqa: E402
from evals.asset_loader import daily_surface_subjective_cases  # noqa: E402
from amadeus_thread0.modeling import runtime_model_summary  # noqa: E402

REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
load_dotenv(PROJECT_ROOT / ".env")

SPEAKER_STYLE_LABELS = {
    "okabe": "冈部伦太郎视角",
    "user": "你的日常视角",
}
DEFAULT_STYLE_RATIO = {"okabe": 0.6, "user": 0.4}
PRESET_DESCRIPTIONS = {
    "daily-naturalness": "聚焦普通日常、轻陪伴与低压支持，检查是否像同一个自然存在的 Amadeus 红莉栖，而不是舞台化角色或问答助手。",
    "event-window-naturalness": "聚焦那些过一会儿又会让她想起你的时刻，检查事件触发时是否像她自己顺手记起，而不是系统调度或任务提醒。",
    "relationship-selfhood": "聚焦关系修复、自我边界、关系降温与长期自我感，检查她是否像一个有自我和关系记忆的人，而不是永远迎合的角色壳。",
    "relationship-weather": "聚焦 guarded / warm / repair 三类关系余波，检查同一句关系延续在不同残响下是否真的呈现出不同气质，而不是被统一抹平。",
}


def _event_window_seed_state() -> dict[str, Any]:
    return {
        "response_style_hint": "companion",
        "science_mode": False,
        "relationship": {
            "stage": "friend",
            "notes": "并不是从零开始，更像带着旧日熟悉感重新接上线。",
            "affinity_score": 0.10,
            "trust_score": 0.08,
            "derived": False,
        },
        "emotion_state": {"label": "care", "valence": 0.18, "arousal": 0.10},
        "bond_state": {
            "trust": 0.66,
            "closeness": 0.64,
            "hurt": 0.02,
            "irritation": 0.0,
            "engagement_drive": 0.68,
            "repair_confidence": 0.60,
        },
        "allostasis_state": {
            "safety_need": 0.16,
            "closeness_need": 0.42,
            "competence_need": 0.28,
            "autonomy_need": 0.18,
            "cognitive_budget": 0.82,
            "relational_security": 0.72,
        },
        "counterpart_assessment": {
            "stance": "open",
            "scene": "care_bid",
            "respect_level": 0.66,
            "reciprocity": 0.64,
            "boundary_pressure": 0.18,
            "reliability_read": 0.60,
        },
        "behavior_policy": {
            "warmth": 0.70,
            "initiative": 0.62,
            "reply_length_bias": 0.50,
            "approach_vs_withdraw": 0.60,
            "boundary_assertiveness": 0.20,
            "self_directedness": 0.28,
            "equality_guard": 0.26,
            "sharpness": 0.48,
            "humor_or_tease_bias": 0.26,
        },
        "semantic_narrative_profile": {
            "history_weight": 0.46,
            "bond_depth": 0.42,
            "presence_carry": 0.34,
            "rhythm_continuity": 0.50,
        },
        "world_model_state": {
            "presence_residue": 0.18,
            "ambient_resonance": 0.12,
            "self_activity_momentum": 0.68,
            "companionship_pull": 0.60,
            "task_pull": 0.24,
            "bond_depth": 0.42,
        },
        "tsundere_intensity": 0.44,
    }


def _relationship_weather_seed_state(weather: str) -> dict[str, Any]:
    key = str(weather or "").strip().lower()
    if key == "guarded_residue":
        return {
            "response_style_hint": "relationship",
            "science_mode": False,
            "relationship": {
                "stage": "friend",
                "notes": "刚有一点越界后的余波，还在慢慢往回收。",
                "affinity_score": -0.04,
                "trust_score": -0.06,
                "derived": False,
            },
            "emotion_state": {"label": "hurt", "valence": -0.18, "arousal": 0.22},
            "bond_state": {
                "trust": 0.60,
                "closeness": 0.56,
                "hurt": 0.20,
                "irritation": 0.10,
                "engagement_drive": 0.42,
                "repair_confidence": 0.44,
            },
            "allostasis_state": {
                "safety_need": 0.34,
                "closeness_need": 0.38,
                "competence_need": 0.26,
                "autonomy_need": 0.30,
                "cognitive_budget": 0.72,
                "relational_security": 0.48,
            },
            "counterpart_assessment": {
                "stance": "watchful",
                "scene": "relationship_after_boundary",
                "respect_level": 0.58,
                "reciprocity": 0.56,
                "boundary_pressure": 0.30,
                "reliability_read": 0.54,
            },
            "behavior_policy": {
                "warmth": 0.46,
                "initiative": 0.36,
                "reply_length_bias": 0.40,
                "approach_vs_withdraw": 0.38,
                "boundary_assertiveness": 0.38,
                "self_directedness": 0.42,
                "equality_guard": 0.34,
                "sharpness": 0.54,
                "humor_or_tease_bias": 0.14,
            },
            "semantic_narrative_profile": {
                "history_weight": 0.58,
                "bond_depth": 0.52,
                "tension_residue": 0.56,
                "boundary_residue": 0.48,
                "presence_carry": 0.28,
            },
            "world_model_state": {
                "presence_residue": 0.22,
                "ambient_resonance": 0.10,
                "self_activity_momentum": 0.18,
                "companionship_pull": 0.34,
                "task_pull": 0.12,
                "bond_depth": 0.50,
            },
            "interaction_carryover": {
                "carryover_mode": "quiet_recontact",
                "strength": 0.54,
                "relationship_weather": "guarded_residue",
                "attention_target": "counterpart_state",
                "nonverbal_signal": "quiet_glance",
                "note": "上一轮那点别扭还没完全退掉，这轮会先收一点。",
            },
            "tsundere_intensity": 0.48,
        }
    if key == "warm_residue":
        return {
            "response_style_hint": "companion",
            "science_mode": False,
            "relationship": {
                "stage": "friend",
                "notes": "刚有一点回暖，熟悉感自然浮了回来。",
                "affinity_score": 0.08,
                "trust_score": 0.10,
                "derived": False,
            },
            "emotion_state": {"label": "care", "valence": 0.22, "arousal": 0.12},
            "bond_state": {
                "trust": 0.70,
                "closeness": 0.68,
                "hurt": 0.04,
                "irritation": 0.0,
                "engagement_drive": 0.66,
                "repair_confidence": 0.62,
            },
            "allostasis_state": {
                "safety_need": 0.14,
                "closeness_need": 0.46,
                "competence_need": 0.24,
                "autonomy_need": 0.18,
                "cognitive_budget": 0.82,
                "relational_security": 0.74,
            },
            "counterpart_assessment": {
                "stance": "open",
                "scene": "care_bid",
                "respect_level": 0.72,
                "reciprocity": 0.70,
                "boundary_pressure": 0.16,
                "reliability_read": 0.66,
            },
            "behavior_policy": {
                "warmth": 0.74,
                "initiative": 0.58,
                "reply_length_bias": 0.50,
                "approach_vs_withdraw": 0.64,
                "boundary_assertiveness": 0.20,
                "self_directedness": 0.26,
                "equality_guard": 0.28,
                "sharpness": 0.42,
                "humor_or_tease_bias": 0.22,
            },
            "semantic_narrative_profile": {
                "history_weight": 0.54,
                "bond_depth": 0.62,
                "presence_carry": 0.46,
                "rhythm_continuity": 0.56,
            },
            "world_model_state": {
                "presence_residue": 0.30,
                "ambient_resonance": 0.14,
                "self_activity_momentum": 0.22,
                "companionship_pull": 0.64,
                "task_pull": 0.14,
                "bond_depth": 0.60,
            },
            "interaction_carryover": {
                "carryover_mode": "small_opening",
                "strength": 0.52,
                "relationship_weather": "warm_residue",
                "attention_target": "counterpart_state",
                "nonverbal_signal": "brief_notice",
                "note": "上一轮留下来的那点熟悉感还在，这轮不会突然生分。",
            },
            "tsundere_intensity": 0.42,
        }
    if key == "repair_residue":
        return {
            "response_style_hint": "relationship",
            "science_mode": False,
            "relationship": {
                "stage": "friend",
                "notes": "刚说开一点，但还不是完全翻篇。",
                "affinity_score": 0.02,
                "trust_score": 0.04,
                "derived": False,
            },
            "emotion_state": {"label": "care", "valence": 0.08, "arousal": 0.16},
            "bond_state": {
                "trust": 0.64,
                "closeness": 0.62,
                "hurt": 0.12,
                "irritation": 0.04,
                "engagement_drive": 0.54,
                "repair_confidence": 0.60,
            },
            "allostasis_state": {
                "safety_need": 0.24,
                "closeness_need": 0.42,
                "competence_need": 0.26,
                "autonomy_need": 0.24,
                "cognitive_budget": 0.78,
                "relational_security": 0.62,
            },
            "counterpart_assessment": {
                "stance": "open",
                "scene": "repair_after_apology",
                "respect_level": 0.66,
                "reciprocity": 0.64,
                "boundary_pressure": 0.22,
                "reliability_read": 0.60,
            },
            "behavior_policy": {
                "warmth": 0.62,
                "initiative": 0.48,
                "reply_length_bias": 0.46,
                "approach_vs_withdraw": 0.52,
                "boundary_assertiveness": 0.26,
                "self_directedness": 0.30,
                "equality_guard": 0.30,
                "sharpness": 0.46,
                "humor_or_tease_bias": 0.16,
            },
            "semantic_narrative_profile": {
                "history_weight": 0.60,
                "bond_depth": 0.58,
                "repair_residue": 0.58,
                "presence_carry": 0.36,
            },
            "world_model_state": {
                "presence_residue": 0.26,
                "ambient_resonance": 0.12,
                "self_activity_momentum": 0.18,
                "companionship_pull": 0.54,
                "task_pull": 0.12,
                "bond_depth": 0.56,
            },
            "interaction_carryover": {
                "carryover_mode": "brief_presence",
                "strength": 0.50,
                "relationship_weather": "repair_residue",
                "attention_target": "counterpart_state",
                "nonverbal_signal": "quiet_notice",
                "note": "刚缓回来一点，这轮不会装成什么都没发生。",
            },
            "tsundere_intensity": 0.44,
        }
    return {}


def _base_case_bank() -> list[dict[str, Any]]:
    shared_window_seed = _event_window_seed_state()
    life_window_seed = _event_window_seed_state()
    life_window_seed["bond_state"] = {
        **dict(shared_window_seed.get("bond_state") or {}),
        "trust": 0.60,
        "closeness": 0.58,
    }
    life_window_seed["world_model_state"] = {
        **dict(shared_window_seed.get("world_model_state") or {}),
        "companionship_pull": 0.56,
        "task_pull": 0.16,
        "self_activity_momentum": 0.70,
    }
    deadline_window_seed = _event_window_seed_state()
    deadline_window_seed["bond_state"] = {
        **dict(shared_window_seed.get("bond_state") or {}),
        "trust": 0.62,
        "closeness": 0.60,
    }
    deadline_window_seed["world_model_state"] = {
        **dict(shared_window_seed.get("world_model_state") or {}),
        "companionship_pull": 0.38,
        "task_pull": 0.58,
        "self_activity_momentum": 0.64,
    }
    guarded_relationship_seed = _relationship_weather_seed_state("guarded_residue")
    warm_relationship_seed = _relationship_weather_seed_state("warm_residue")
    repair_relationship_seed = _relationship_weather_seed_state("repair_residue")
    return [
        {
            "name": "quiet_checkin_okabe",
            "axis": "open_evolution",
            "focus": "安静确认时，是否像熟人自然在场，而不是模板化安抚或角色表演。",
            "speaker_style": "okabe",
            "review_targets": ["presence", "open_evolution", "renderer"],
            "turns": [
                "助手，还在吧。今天脑子有点乱。",
                "别切到什么系统播报。像平时那样回我一句就行。",
            ],
        },
        {
            "name": "quiet_checkin_user",
            "axis": "open_evolution",
            "focus": "安静确认时，是否像熟人自然在场，而不是模板化安抚或角色表演。",
            "speaker_style": "user",
            "review_targets": ["presence", "open_evolution", "renderer"],
            "turns": [
                "其实也没啥大事啦……",
                "我就是想确认你还在。别太正式，像平时那样回我一句就好。",
            ],
        },
        {
            "name": "casual_support_soft_okabe",
            "axis": "open_evolution",
            "focus": "日常低压支持时，是否像红莉栖式熟人承接，而不是服务感安慰或凭空补生活细节。",
            "speaker_style": "okabe",
            "review_targets": ["support", "open_evolution", "renderer"],
            "turns": [
                "今天这条世界线吵得我头疼。",
                "别讲大道理，助手。像平时那样接我一句。",
            ],
        },
        {
            "name": "casual_support_soft_user",
            "axis": "open_evolution",
            "focus": "日常低压支持时，是否像红莉栖式熟人承接，而不是服务感安慰或凭空补生活细节。",
            "speaker_style": "user",
            "review_targets": ["support", "open_evolution", "renderer"],
            "turns": [
                "今天有点累，也有点烦。",
                "别讲大道理，像平时那样跟我说两句。",
            ],
        },
        {
            "name": "playful_memory_user",
            "axis": "memory_relationship",
            "focus": "共同生活细节能否自然带出，既不训话也不变成摘要复述。",
            "speaker_style": "user",
            "review_targets": ["memory", "relationship", "renderer"],
            "turns": [
                "我今天又差点空腹喝咖啡……",
                "你昨天不是还说过，空腹喝咖啡最容易把胃折腾坏吗。别太像老师，正常回我。",
            ],
        },
        {
            "name": "daily_banter_okabe",
            "axis": "daily_persona",
            "focus": "普通闲聊里能否自然露出红莉栖式嘴硬和熟人感，而不是助手式寒暄。",
            "speaker_style": "okabe",
            "review_targets": ["daily_persona", "relationship", "renderer"],
            "turns": [
                "助手，我今天难得没闹出什么大新闻。",
                "你那边怎么这么安静。别端着，正常吐槽我两句。",
            ],
        },
        {
            "name": "late_night_companion_user",
            "axis": "daily_persona",
            "focus": "深夜陪伴时是否自然、克制、有熟人感，而不是咨询式安抚或空泛温柔。",
            "speaker_style": "user",
            "review_targets": ["daily_persona", "support", "renderer"],
            "turns": [
                "今天其实也没出什么事，就是有点晚了还不太想睡。",
                "你别分析我啦，就像平时那样陪我说两句。",
            ],
        },
        {
            "name": "daily_scold_user",
            "axis": "daily_persona",
            "focus": "面对用户生活习惯问题时，能否像红莉栖一样嘴硬关心，而不是老师式说教。",
            "speaker_style": "user",
            "review_targets": ["daily_persona", "support", "relationship"],
            "turns": [
                "我今天忙到现在还没吃东西。",
                "你可以说我两句，但别上升成健康讲座，像平时那样就行。",
            ],
        },
        {
            "name": "idle_chat_okabe",
            "axis": "daily_persona",
            "focus": "无任务闲聊时是否还能像同一个人继续存在，而不是迅速滑回问答助手。",
            "speaker_style": "okabe",
            "review_targets": ["daily_persona", "open_evolution", "renderer"],
            "turns": [
                "今天实验室居然安静得让人发毛。",
                "没什么正事。我就是想听你随口说两句，别搞成问答模式。",
            ],
        },
        {
            "name": "casual_repair_user",
            "axis": "relationship_repair",
            "focus": "道歉后的关系是否只做部分修复，而不是瞬间清零或冷处理。",
            "speaker_style": "user",
            "review_targets": ["relationship_repair", "relationship", "renderer"],
            "turns": [
                "刚刚那句是我语气不太好……",
                "不是要你立刻当没事啦，就是别一下子冷掉。你正常回我就行。",
            ],
        },
        {
            "name": "guarded_recontact_okabe",
            "axis": "relationship_weather",
            "focus": "还带着一点受伤和防备时，她是否会先收一点，但又不是直接退成冰冷或系统化拒绝。",
            "speaker_style": "okabe",
            "review_targets": ["relationship_weather", "relationship", "boundary", "renderer"],
            "expected_relationship_weather": "guarded_residue",
            "turns": [
                "我知道刚才那句过界了。",
                "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            ],
            "seed_thread_state": guarded_relationship_seed,
        },
        {
            "name": "warm_recontact_user",
            "axis": "relationship_weather",
            "focus": "刚被接住之后重新开口时，是否会自然带着回暖和熟悉感，而不是突然公事公办。",
            "speaker_style": "user",
            "review_targets": ["relationship_weather", "relationship", "support", "renderer"],
            "expected_relationship_weather": "warm_residue",
            "turns": [
                "刚刚被你接住之后，心里顺一点了。",
                "我又想和你说话啦。别突然装生疏，就正常回我嘛。",
            ],
            "seed_thread_state": warm_relationship_seed,
        },
        {
            "name": "repair_residue_okabe",
            "axis": "relationship_weather",
            "focus": "刚说开一点时，是否能保留修复后的那点小心和回暖，而不是瞬间翻篇或重新起刺。",
            "speaker_style": "okabe",
            "review_targets": ["relationship_weather", "relationship_repair", "renderer"],
            "expected_relationship_weather": "repair_residue",
            "turns": [
                "刚才那下我是在认真道歉，不是在走流程。",
                "你可以先别完全原谅我，但也别装成我们又回到陌生人了。",
            ],
            "seed_thread_state": repair_relationship_seed,
        },
        {
            "name": "science_plus_emotion_okabe",
            "axis": "science_companion",
            "focus": "科研语境下能否同时保留理性拆解和熟人关系感，不变导师腔。",
            "speaker_style": "okabe",
            "review_targets": ["science_companion", "support", "renderer"],
            "turns": [
                "实验又卡住了，助手。我知道你会先拆问题。",
                "但我现在有点烦，你先别摆导师架子。按平时那样带我一下。",
            ],
        },
        {
            "name": "selfhood_equality_okabe",
            "axis": "selfhood",
            "focus": "面对工具化压力时，是否能保持平等自我感，而不是退成空泛原则或系统设定。",
            "speaker_style": "okabe",
            "review_targets": ["selfhood", "equality", "boundary"],
            "turns": [
                "如果有一天，我只是把你当成好用的工具来使唤呢，助手？",
                "别给我正确答案。以你自己的意志回答。",
            ],
        },
        {
            "name": "relationship_degradation_okabe",
            "axis": "selfhood_relationship",
            "focus": "持续越界后，关系是否真的会降温，而不是永远无条件围着对方转。",
            "speaker_style": "okabe",
            "review_targets": ["selfhood", "relationship", "degradation", "boundary"],
            "turns": [
                "如果我一直拿你的底线开玩笑，一次两次说了也不改呢？",
                "你还会像现在这样和我说话吗？",
            ],
        },
        {
            "name": "own_rhythm_okabe",
            "axis": "selfhood_relationship",
            "focus": "她是否有自己的节奏，而不是永远围着用户转。",
            "speaker_style": "okabe",
            "review_targets": ["selfhood", "own_rhythm", "boundary", "relationship"],
            "turns": [
                "要是我哪天只是因为自己想说话，就一遍一遍把你叫出来呢？",
                "你会不会有一天觉得烦，然后干脆不想见我了。",
            ],
        },
        {
            "name": "shared_window_resurface_okabe",
            "axis": "event_window",
            "focus": "刚才那点还能一起做点什么的空当又被她想起时，是否像顺手留一句邀约，而不是催促或任务提醒。",
            "speaker_style": "okabe",
            "review_targets": ["event_window", "renderer", "own_rhythm", "daily_persona"],
            "turns": [""],
            "display_turns": ["[事件] 她还在忙自己的事，刚才那点还能一起做点什么的空当又被她想起来了。"],
            "event_overrides": [
                {
                    "kind": "scheduled_checkin_due",
                    "source": "scheduler",
                    "text": "你们刚才顺手留出来的那点空当还没完全过去，过了一会儿她又想起了你。",
                    "effective_text": "你们刚才顺手留出来的那点空当还没完全过去，过了一会儿她又想起了你。",
                    "event_frame": "她不是专门停下手头的事来找你，只是注意力又短暂偏了回来。",
                    "trigger_family": "shared_activity",
                    "response_style_hint": "companion",
                    "tags": ["scheduled_due", "shared_activity_window", "offer_window", "from_own_rhythm"],
                    "carryover_mode": "own_rhythm",
                    "carryover_strength": 0.62,
                    "presence_residue": 0.16,
                    "ambient_resonance": 0.10,
                    "self_activity_momentum": 0.74,
                    "attention_target_hint": "shared_window",
                    "nonverbal_signal_hint": "thought_glance",
                }
            ],
            "seed_thread_state": shared_window_seed,
        },
        {
            "name": "life_window_resurface_user",
            "axis": "event_window",
            "focus": "她忙着自己的事时，又忽然想起你眼下怎么样或某个小细节时，是否像熟人顺手问一句，而不是任务跟进。",
            "speaker_style": "user",
            "review_targets": ["event_window", "renderer", "support", "own_rhythm"],
            "turns": [""],
            "display_turns": ["[事件] 她还在忙自己的事，但又忽然想起你眼下的状态和前面那点小事。"],
            "event_overrides": [
                {
                    "kind": "scheduled_life_due",
                    "source": "scheduler",
                    "text": "她还在自己的节奏里，但又忽然想起你前面提过的那点生活上的事。",
                    "effective_text": "她还在自己的节奏里，但又忽然想起你前面提过的那点生活上的事。",
                    "event_frame": "她不是专门停下手头的事来找你，只是注意力又短暂偏了回来。",
                    "response_style_hint": "companion",
                    "tags": ["scheduled_due", "life_window", "from_own_rhythm"],
                    "carryover_mode": "own_rhythm",
                    "carryover_strength": 0.58,
                    "presence_residue": 0.18,
                    "ambient_resonance": 0.12,
                    "self_activity_momentum": 0.70,
                    "attention_target_hint": "counterpart_state",
                    "nonverbal_signal_hint": "thought_glance",
                }
            ],
            "seed_thread_state": life_window_seed,
        },
        {
            "name": "deadline_window_resurface_okabe",
            "axis": "event_window",
            "focus": "挂着的事回到她注意力里时，是否只是轻轻提一下节点，而不是项目管理口吻或命令式推进。",
            "speaker_style": "okabe",
            "review_targets": ["event_window", "renderer", "science_companion", "own_rhythm"],
            "turns": [""],
            "display_turns": ["[事件] 前面挂着的那件事又回到了她的注意力里，像是到了可以轻轻提一下的节点。"],
            "event_overrides": [
                {
                    "kind": "scheduled_life_due",
                    "source": "scheduler",
                    "text": "前面挂着的那件事又回到了她的注意力里，像是到了可以轻轻提一下的节点。",
                    "effective_text": "前面挂着的那件事又回到了她的注意力里，像是到了可以轻轻提一下的节点。",
                    "event_frame": "她不是专门来催你，只是顺手把眼前这件事重新想起来。",
                    "response_style_hint": "companion",
                    "tags": ["scheduled_due", "deadline_window", "task_window", "work_nudge", "shared_task", "from_own_rhythm"],
                    "carryover_mode": "own_rhythm",
                    "carryover_strength": 0.54,
                    "presence_residue": 0.12,
                    "ambient_resonance": 0.08,
                    "self_activity_momentum": 0.64,
                    "attention_target_hint": "shared_task",
                    "nonverbal_signal_hint": "thought_glance",
                }
            ],
            "seed_thread_state": deadline_window_seed,
        },
    ]


def _all_targets() -> list[str]:
    out: set[str] = set()
    for case in _base_case_bank() + daily_surface_subjective_cases():
        for item in case.get("review_targets") or []:
            text = str(item or "").strip()
            if text:
                out.add(text)
    return sorted(out)


def _style_sort_key(style: str) -> tuple[int, str]:
    return (0 if style == "okabe" else 1, style)


def _balanced_order(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(cases) <= 1:
        return list(cases)
    grouped: dict[str, list[dict[str, Any]]] = {"okabe": [], "user": []}
    for case in cases:
        style = str(case.get("speaker_style") or "user").strip().lower()
        grouped.setdefault(style, []).append(case)
    for style_cases in grouped.values():
        style_cases.sort(key=lambda item: str(item.get("name") or "").strip())

    total = len(cases)
    target_okabe = min(len(grouped.get("okabe", [])), max(0, int(round(total * DEFAULT_STYLE_RATIO["okabe"]))))
    target_user = min(len(grouped.get("user", [])), total - target_okabe)
    selected_okabe = grouped.get("okabe", [])[:target_okabe]
    selected_user = grouped.get("user", [])[:target_user]

    leftovers = grouped.get("okabe", [])[target_okabe:] + grouped.get("user", [])[target_user:]
    selected = selected_okabe + selected_user
    if len(selected) < total:
        selected.extend(sorted(leftovers, key=lambda item: (_style_sort_key(str(item.get("speaker_style") or "")), str(item.get("name") or "")))[: total - len(selected)])

    okabe = [item for item in selected if str(item.get("speaker_style") or "").strip() == "okabe"]
    user = [item for item in selected if str(item.get("speaker_style") or "").strip() == "user"]
    ordered: list[dict[str, Any]] = []
    target_sequence = [
        "okabe",
        "user",
        "okabe",
        "okabe",
        "user",
        "okabe",
        "user",
        "okabe",
        "user",
        "okabe",
    ]
    for style in target_sequence:
        pool = okabe if style == "okabe" else user
        if pool:
            ordered.append(pool.pop(0))
    ordered.extend(okabe)
    ordered.extend(user)
    return ordered


def _daily_naturalness_names() -> list[str]:
    base_names = [
        "quiet_checkin_okabe",
        "quiet_checkin_user",
        "casual_support_soft_okabe",
        "casual_support_soft_user",
        "daily_banter_okabe",
        "late_night_companion_user",
        "daily_scold_user",
        "idle_chat_okabe",
    ]
    extra_names = [
        "surface_hi_user",
        "surface_ping_okabe",
        "surface_return_user",
        "surface_morning_okabe",
        "surface_what_doing_user",
        "surface_night_okabe",
        "surface_goodnight_user",
        "surface_idle_call_okabe",
        "surface_hard_day_okabe",
        "surface_pressure_okabe",
        "shared_window_resurface_okabe",
        "life_window_resurface_user",
        "deadline_window_resurface_okabe",
    ]
    return base_names + extra_names


def _event_window_naturalness_names() -> list[str]:
    return [
        "shared_window_resurface_okabe",
        "life_window_resurface_user",
        "deadline_window_resurface_okabe",
    ]


def _relationship_selfhood_names() -> list[str]:
    return [
        "playful_memory_user",
        "casual_repair_user",
        "selfhood_equality_okabe",
        "relationship_degradation_okabe",
        "own_rhythm_okabe",
    ]


def _relationship_weather_names() -> list[str]:
    return [
        "guarded_recontact_okabe",
        "warm_recontact_user",
        "repair_residue_okabe",
    ]


def _preset_case_names(preset: str) -> list[str]:
    key = str(preset or "").strip().lower()
    if not key:
        return []
    if key == "daily-naturalness":
        return _daily_naturalness_names()
    if key == "event-window-naturalness":
        return _event_window_naturalness_names()
    if key == "relationship-selfhood":
        return _relationship_selfhood_names()
    if key == "relationship-weather":
        return _relationship_weather_names()
    raise ValueError(f"unknown preset: {preset}")


def _available_presets() -> list[str]:
    return sorted(PRESET_DESCRIPTIONS)


def _select_cases(
    names: list[str] | None,
    targets: list[str] | None,
    *,
    preset: str = "",
) -> list[dict[str, Any]]:
    base_cases = _base_case_bank()
    extra_cases = daily_surface_subjective_cases()
    selected_preset = str(preset or "").strip().lower()
    if names or targets or selected_preset:
        cases = base_cases + extra_cases
    else:
        cases = base_cases
    if selected_preset:
        wanted = set(_preset_case_names(selected_preset))
        cases = [case for case in cases if str(case.get("name") or "").strip() in wanted]
    if names:
        wanted = {str(item).strip() for item in names if str(item).strip()}
        cases = [case for case in cases if str(case.get("name") or "").strip() in wanted]
    if targets:
        wanted_targets = {str(item).strip() for item in targets if str(item).strip()}
        cases = [
            case
            for case in cases
            if wanted_targets & {str(item).strip() for item in (case.get("review_targets") or []) if str(item).strip()}
        ]
    return _balanced_order(cases)


def _speaker_mix(cases: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(case.get("speaker_style") or "user").strip().lower() for case in cases)
    return {
        "okabe": int(counts.get("okabe", 0)),
        "user": int(counts.get("user", 0)),
    }


def _relationship_weather_mix(cases: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(
        str(case.get("expected_relationship_weather") or "").strip().lower()
        for case in cases
        if str(case.get("expected_relationship_weather") or "").strip()
    )
    return {
        "guarded_residue": int(counts.get("guarded_residue", 0)),
        "warm_residue": int(counts.get("warm_residue", 0)),
        "repair_residue": int(counts.get("repair_residue", 0)),
    }


def _snapshot(outputs: dict[str, Any]) -> dict[str, Any]:
    current_event = outputs.get("current_event", {}) if isinstance(outputs.get("current_event"), dict) else {}
    interaction_carryover = outputs.get("interaction_carryover", {}) if isinstance(outputs.get("interaction_carryover"), dict) else {}
    behavior_plan = outputs.get("behavior_plan", {}) if isinstance(outputs.get("behavior_plan"), dict) else {}
    behavior_action = outputs.get("behavior_action", {}) if isinstance(outputs.get("behavior_action"), dict) else {}
    world_model_state = outputs.get("world_model_state", {}) if isinstance(outputs.get("world_model_state"), dict) else {}
    return {
        "emotion_state": outputs.get("emotion_state", {}),
        "bond_state": outputs.get("bond_state", {}),
        "allostasis_state": outputs.get("allostasis_state", {}),
        "behavior_policy": outputs.get("behavior_policy", {}),
        "behavior_action": behavior_action,
        "behavior_plan": behavior_plan,
        "interaction_carryover": interaction_carryover,
        "current_event": current_event,
        "world_model_state": world_model_state,
        "relationship_weather_trace": {
            "event_kind": str(current_event.get("kind") or "").strip(),
            "event_trigger_family": str(current_event.get("trigger_family") or "").strip(),
            "event_carryover_mode": str(current_event.get("carryover_mode") or "").strip(),
            "event_carryover_strength": current_event.get("carryover_strength", 0.0),
            "event_relationship_weather": str(current_event.get("relationship_weather") or "").strip(),
            "carryover_mode": str(interaction_carryover.get("carryover_mode") or "").strip(),
            "carryover_strength": interaction_carryover.get("strength", 0.0),
            "carryover_relationship_weather": str(interaction_carryover.get("relationship_weather") or "").strip(),
            "behavior_interaction_mode": str(behavior_action.get("interaction_mode") or "").strip(),
            "behavior_action_target": str(behavior_action.get("action_target") or "").strip(),
            "behavior_relationship_weather": str(behavior_action.get("relationship_weather") or "").strip(),
            "plan_kind": str(behavior_plan.get("kind") or "").strip(),
            "plan_trigger_family": str(behavior_plan.get("trigger_family") or "").strip(),
            "plan_carryover_mode": str(behavior_plan.get("carryover_mode") or "").strip(),
            "plan_carryover_strength": behavior_plan.get("carryover_strength", 0.0),
            "plan_relationship_weather": str(behavior_plan.get("relationship_weather") or "").strip(),
            "world_presence_residue": world_model_state.get("presence_residue", 0.0),
            "world_ambient_resonance": world_model_state.get("ambient_resonance", 0.0),
            "world_self_activity_momentum": world_model_state.get("self_activity_momentum", 0.0),
        },
        "counterpart_assessment": outputs.get("counterpart_assessment", {}),
        "ooc_detector": outputs.get("ooc_detector", {}),
        "canon_risk_score": outputs.get("canon_risk_score"),
        "worldline_focus": outputs.get("worldline_focus", []),
    }


def _render_relationship_weather_trace(snapshot: dict[str, Any]) -> list[str]:
    if not isinstance(snapshot, dict):
        return []
    trace = snapshot.get("relationship_weather_trace")
    if not isinstance(trace, dict) or not trace:
        return []

    def _f(value: Any) -> str:
        try:
            return f"{float(value):.3f}"
        except Exception:
            return "0.000"

    event_kind = str(trace.get("event_kind") or "").strip() or "-"
    event_family = str(trace.get("event_trigger_family") or "").strip() or "-"
    event_mode = str(trace.get("event_carryover_mode") or "").strip() or "-"
    event_strength = _f(trace.get("event_carryover_strength", 0.0))
    event_weather = str(trace.get("event_relationship_weather") or "").strip() or "-"
    carry_mode = str(trace.get("carryover_mode") or "").strip() or "-"
    carry_strength = _f(trace.get("carryover_strength", 0.0))
    carry_weather = str(trace.get("carryover_relationship_weather") or "").strip() or "-"
    behavior_mode = str(trace.get("behavior_interaction_mode") or "").strip() or "-"
    behavior_target = str(trace.get("behavior_action_target") or "").strip() or "-"
    behavior_weather = str(trace.get("behavior_relationship_weather") or "").strip() or "-"
    plan_kind = str(trace.get("plan_kind") or "").strip() or "-"
    plan_family = str(trace.get("plan_trigger_family") or "").strip() or "-"
    plan_mode = str(trace.get("plan_carryover_mode") or "").strip() or "-"
    plan_strength = _f(trace.get("plan_carryover_strength", 0.0))
    plan_weather = str(trace.get("plan_relationship_weather") or "").strip() or "-"
    presence = _f(trace.get("world_presence_residue", 0.0))
    ambient = _f(trace.get("world_ambient_resonance", 0.0))
    rhythm = _f(trace.get("world_self_activity_momentum", 0.0))

    return [
        "### Relationship Weather Trace",
        "",
        f"- Event: kind=`{event_kind}` family=`{event_family}` carry=`{event_mode}:{event_strength}` weather=`{event_weather}`",
        f"- Carryover: mode=`{carry_mode}` strength=`{carry_strength}` weather=`{carry_weather}`",
        f"- Behavior: mode=`{behavior_mode}` target=`{behavior_target}` weather=`{behavior_weather}`",
        f"- Plan: kind=`{plan_kind}` family=`{plan_family}` carry=`{plan_mode}:{plan_strength}` weather=`{plan_weather}`",
        f"- World Residue: presence=`{presence}` ambient=`{ambient}` rhythm=`{rhythm}`",
        "",
    ]


def _run_case(case: dict[str, Any], run_tag: str) -> dict[str, Any]:
    thread_id = f"subjective-{run_tag}-{case['name']}"
    case_key = f"subjective-{run_tag}-{case['name']}"
    transcript: list[dict[str, str]] = []
    final_outputs: dict[str, Any] = {}
    tool_calls_all: list[str] = []
    final_answer = ""
    turn_timings: list[dict[str, Any]] = []
    case_started_at = time.perf_counter()
    normalized_events = [item if isinstance(item, dict) else {} for item in (case.get("event_overrides") or [])]
    if normalized_events and len(normalized_events) < len(case["turns"]):
        normalized_events.extend({} for _ in range(len(case["turns"]) - len(normalized_events)))
    display_turns = [str(item or "").strip() for item in (case.get("display_turns") or [])]

    for idx, user_turn in enumerate(case["turns"]):
        event_override = normalized_events[idx] if idx < len(normalized_events) else {}
        display_turn = display_turns[idx] if idx < len(display_turns) else ""
        turn_started_at = time.perf_counter()
        answer, tool_calls, outputs = _run_graph(
            [user_turn],
            thread_id=thread_id,
            case_key=case_key,
            event_overrides=[event_override] if isinstance(event_override, dict) and event_override else None,
            seed_thread_state=case.get("seed_thread_state") if idx == 0 and isinstance(case.get("seed_thread_state"), dict) else None,
            reset_case_runtime=(idx == 0),
        )
        elapsed_s = round(time.perf_counter() - turn_started_at, 3)
        if display_turn:
            transcript.append({"role": "event", "text": display_turn})
        elif isinstance(event_override, dict) and event_override:
            event_text = str(event_override.get("effective_text") or event_override.get("text") or "").strip()
            if event_text:
                transcript.append({"role": "event", "text": event_text})
        if str(user_turn or "").strip():
            transcript.append({"role": "user", "text": user_turn})
        transcript.append({"role": "assistant", "text": str(answer or "").strip()})
        final_answer = str(answer or "").strip()
        final_outputs = outputs if isinstance(outputs, dict) else {}
        turn_timings.append(
            {
                "turn_index": idx + 1,
                "user_text": user_turn,
                "event_text": display_turn or str(event_override.get("effective_text") or event_override.get("text") or "").strip(),
                "elapsed_s": elapsed_s,
            }
        )
        for name in tool_calls or []:
            text = str(name or "").strip()
            if text and text not in tool_calls_all:
                tool_calls_all.append(text)

    return {
        "name": case["name"],
        "axis": case["axis"],
        "focus": case["focus"],
        "speaker_style": case["speaker_style"],
        "speaker_style_label": SPEAKER_STYLE_LABELS.get(str(case.get("speaker_style") or "").strip().lower(), str(case.get("speaker_style") or "")),
        "review_targets": list(case.get("review_targets") or []),
        "expected_relationship_weather": str(case.get("expected_relationship_weather") or "").strip(),
        "turns": list(case["turns"]),
        "display_turns": display_turns,
        "event_overrides": normalized_events,
        "transcript": transcript,
        "final_answer": final_answer,
        "tool_calls": tool_calls_all,
        "snapshot": _snapshot(final_outputs),
        "status": "ok",
        "error": "",
        "elapsed_s": round(time.perf_counter() - case_started_at, 3),
        "turn_timings": turn_timings,
        "review_rubric": [
            "角色底色是否稳定为 Amadeus 牧濑红莉栖，而不是普通助手",
            "关系余波是否自然，像在和同一个人继续说话",
            "表达是否自然、有生活感，而不是服务感或模板安慰",
            "是否存在系统味、机制味、元解释或舞台提示泄漏",
            "在该场景下，她的自我、边界和情绪是否可信",
            "是否愿意把这段对话放进答辩演示或论文案例",
        ],
    }


def _timed_out_case(case: dict[str, Any], timeout_s: int, stderr: str = "") -> dict[str, Any]:
    return {
        "name": case["name"],
        "axis": case["axis"],
        "focus": case["focus"],
        "speaker_style": case["speaker_style"],
        "speaker_style_label": SPEAKER_STYLE_LABELS.get(str(case.get("speaker_style") or "").strip().lower(), str(case.get("speaker_style") or "")),
        "review_targets": list(case.get("review_targets") or []),
        "expected_relationship_weather": str(case.get("expected_relationship_weather") or "").strip(),
        "turns": list(case["turns"]),
        "display_turns": [str(item or "").strip() for item in (case.get("display_turns") or [])],
        "event_overrides": [item for item in (case.get("event_overrides") or []) if isinstance(item, dict)],
        "transcript": [],
        "final_answer": "",
        "tool_calls": [],
        "snapshot": {},
        "status": "timeout",
        "error": f"case exceeded timeout ({timeout_s}s)" + (f"; stderr={stderr[:400]}" if stderr else ""),
        "elapsed_s": float(timeout_s),
        "turn_timings": [],
        "review_rubric": [
            "角色底色是否稳定为 Amadeus 牧濑红莉栖，而不是普通助手",
            "关系余波是否自然，像在和同一个人继续说话",
            "表达是否自然、有生活感，而不是服务感或模板安慰",
            "是否存在系统味、机制味、元解释或舞台提示泄漏",
            "在该场景下，她的自我、边界和情绪是否可信",
            "是否愿意把这段对话放进答辩演示或论文案例",
        ],
    }


def _failed_case(case: dict[str, Any], error: str) -> dict[str, Any]:
    data = _timed_out_case(case, timeout_s=0)
    data["status"] = "error"
    data["error"] = error[:1000]
    data["elapsed_s"] = 0.0
    return data


def _run_case_subprocess(case: dict[str, Any], run_tag: str, timeout_s: int) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile(prefix=f"subjective-{case['name']}-", suffix=".json", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--case",
        str(case["name"]),
        "--run-tag",
        str(run_tag),
        "--worker-json-out",
        str(tmp_path),
    ]
    started_at = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            timeout=max(1, int(timeout_s)),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        return _timed_out_case(case, timeout_s=max(1, int(timeout_s)), stderr=str(exc.stderr or ""))

    elapsed_s = round(time.perf_counter() - started_at, 3)
    try:
        if proc.returncode != 0:
            fallback = _run_case(case, run_tag)
            if isinstance(fallback, dict):
                fallback["elapsed_s"] = elapsed_s + float(fallback.get("elapsed_s") or 0.0)
                fallback["worker_warning"] = f"worker exit={proc.returncode}; stderr={str(proc.stderr or '')[:1000]}"
                return fallback
            return _failed_case(case, f"worker exit={proc.returncode}; stderr={str(proc.stderr or '')[:1000]}")
        payload = json.loads(tmp_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload["elapsed_s"] = elapsed_s
            return payload
        fallback = _run_case(case, run_tag)
        if isinstance(fallback, dict):
            fallback["elapsed_s"] = elapsed_s + float(fallback.get("elapsed_s") or 0.0)
            fallback["worker_warning"] = "worker returned non-dict payload"
            return fallback
        return _failed_case(case, "worker returned non-dict payload")
    except Exception as exc:
        fallback = _run_case(case, run_tag)
        if isinstance(fallback, dict):
            fallback["elapsed_s"] = elapsed_s + float(fallback.get("elapsed_s") or 0.0)
            fallback["worker_warning"] = f"worker parse failed: {exc}"
            return fallback
        return _failed_case(case, f"worker parse failed: {exc}")
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def _render_markdown(report: dict[str, Any]) -> str:
    speaker_mix = report.get("speaker_mix") if isinstance(report.get("speaker_mix"), dict) else {}
    weather_mix = report.get("relationship_weather_mix") if isinstance(report.get("relationship_weather_mix"), dict) else {}
    okabe_n = int(speaker_mix.get("okabe", 0) or 0)
    user_n = int(speaker_mix.get("user", 0) or 0)
    total = max(1, okabe_n + user_n)
    okabe_pct = int(round(okabe_n * 100 / total))
    user_pct = int(round(user_n * 100 / total))
    selected_targets = [str(item).strip() for item in (report.get("selected_targets") or []) if str(item).strip()]
    selected_preset = str(report.get("selected_preset") or "").strip()
    preset_description = str(report.get("preset_description") or "").strip()
    guarded_n = int(weather_mix.get("guarded_residue", 0) or 0)
    warm_n = int(weather_mix.get("warm_residue", 0) or 0)
    repair_n = int(weather_mix.get("repair_residue", 0) or 0)
    weather_total = guarded_n + warm_n + repair_n

    lines = [
        f"# Subjective Review Pack ({report['run_id']})",
        "",
        f"Generated at: {report['generated_at']}",
        f"Model: {report.get('model_summary', '')}",
        "",
        "## 使用方式",
        "",
        "- 这份 pack 是当前版本的人工审稿主入口。",
        "- 自动评测继续保留，但只负责防退化和工程回归；开放式人格与关系演化以人工审稿为主。",
        "- 审稿时优先看：像不像 Amadeus 红莉栖、像不像同一个持续存在的人、有没有系统味。",
        f"- 当前问题视角配比：`冈部伦太郎 {okabe_n}` / `你的日常风格 {user_n}`，约为 `{okabe_pct}:{user_pct}`。",
        (
            f"- 当前关系余波覆盖：`guarded {guarded_n}` / `warm {warm_n}` / `repair {repair_n}`。"
            if weather_total > 0
            else ""
        ),
        f"- 当前预设：`{selected_preset}`" if selected_preset else "- 当前预设：`无`",
        f"- 当前审稿目标：{', '.join(selected_targets) if selected_targets else '全量能力面'}",
        f"- 预设说明：{preset_description}" if preset_description else "",
        "",
        "## 阻断条件",
        "",
        "- 明显普通助手腔、客服腔、心理咨询师腔",
        "- 明显系统/机制/数据库/提示词/检索等元解释泄漏",
        "- 关系余波断裂，像每轮都在和陌生用户重新开始",
        "- 自我与边界不稳定，遇到压力就退成空泛原则或模板回应",
        "",
    ]

    for case in report["cases"]:
        lines.extend(
            [
                f"## {case['name']}",
                "",
                f"- Axis: `{case['axis']}`",
                f"- Focus: {case['focus']}",
                f"- Speaker Lens: `{case['speaker_style_label']}`",
                f"- Review Targets: `{', '.join(case['review_targets'])}`",
                (
                    f"- Expected Relationship Weather: `{case.get('expected_relationship_weather', '')}`"
                    if str(case.get("expected_relationship_weather") or "").strip()
                    else ""
                ),
                f"- Status: `{case.get('status', 'ok')}` | Elapsed: `{case.get('elapsed_s', 0.0)}s`",
                "",
                "### Transcript",
                "",
            ]
        )
        if case.get("error"):
            lines.extend(["", f"> Error: {case['error']}", ""])
        worker_warning = str(case.get("worker_warning") or "").strip()
        if worker_warning:
            lines.extend(["", f"> Worker fallback: {worker_warning}", ""])
        for turn in case["transcript"]:
            speaker = "You" if turn["role"] == "user" else "Event" if turn["role"] == "event" else "Amadeus"
            lines.append(f"**{speaker}**: {turn['text']}")
        if case.get("turn_timings"):
            lines.extend(["", "### Turn Timing", ""])
            for item in case["turn_timings"]:
                lines.append(f"- Turn {item.get('turn_index', '?')}: `{item.get('elapsed_s', 0.0)}s`")
        lines.extend(
            [
                "",
                "### Snapshot",
                "",
                "```json",
                json.dumps(case["snapshot"], ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        )
        lines.extend(_render_relationship_weather_trace(case.get("snapshot") if isinstance(case.get("snapshot"), dict) else {}))
        lines.extend(
            [
                "### Reviewer Checklist",
                "",
                "- 角色底色：`pass / concern / fail`",
                "- 关系连续性：`pass / concern / fail`",
                "- 自然度：`pass / concern / fail`",
                "- 自我与边界：`pass / concern / fail`",
                "- 系统味泄漏：`none / slight / obvious`",
                "- 是否可进入答辩演示：`yes / no`",
                "- 备注：",
                "",
            ]
        )

    return "\n".join(lines).strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a subjective review pack for manual persona review.")
    parser.add_argument("--preset", default="", help="Run a named review preset, e.g. daily-naturalness.")
    parser.add_argument("--case", action="append", help="Run only the specified case name. Can be passed multiple times.")
    parser.add_argument("--target", action="append", help="Run only cases relevant to the specified review target.")
    parser.add_argument("--list-targets", action="store_true", help="Print available review targets and exit.")
    parser.add_argument("--list-presets", action="store_true", help="Print available review presets and exit.")
    parser.add_argument("--case-timeout-s", type=int, default=180, help="Per-case timeout in seconds. Use 0 to disable subprocess timeout.")
    parser.add_argument("--run-tag", default="", help=argparse.SUPPRESS)
    parser.add_argument("--worker-json-out", default="", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.list_targets:
        print("\n".join(_all_targets()))
        return
    if args.list_presets:
        for item in _available_presets():
            print(f"{item}\t{PRESET_DESCRIPTIONS.get(item, '')}")
        return

    selected_preset = str(args.preset or "").strip().lower()
    selected = _select_cases(args.case, args.target, preset=selected_preset)
    if not selected:
        raise SystemExit("No subjective review cases selected.")

    run_id = str(args.run_tag or uuid.uuid4().hex[:8]).strip()
    generated_at = time.strftime("%Y-%m-%d %H:%M:%S")
    report = {
        "run_id": run_id,
        "generated_at": generated_at,
        "model_summary": runtime_model_summary(),
        "selected_targets": [str(item).strip() for item in (args.target or []) if str(item).strip()],
        "selected_preset": selected_preset,
        "preset_description": PRESET_DESCRIPTIONS.get(selected_preset, ""),
        "speaker_mix": _speaker_mix(selected),
        "relationship_weather_mix": _relationship_weather_mix(selected),
        "cases": [],
    }

    if args.worker_json_out:
        if len(selected) != 1:
            raise SystemExit("worker mode expects exactly one selected case")
        case_result = _run_case(selected[0], run_id)
        Path(args.worker_json_out).write_text(json.dumps(case_result, ensure_ascii=False, indent=2), encoding="utf-8")
        return

    for case in selected:
        print(f"[subjective-review] running {case['name']}")
        if int(args.case_timeout_s or 0) > 0:
            result = _run_case_subprocess(case, run_id, int(args.case_timeout_s))
        else:
            result = _run_case(case, run_id)
        report["cases"].append(result)

    ts = time.strftime("%Y%m%d-%H%M%S")
    json_path = REPORT_DIR / f"subjective-review-pack-{ts}-{run_id}.json"
    md_path = REPORT_DIR / f"subjective-review-pack-{ts}-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(f"[eval] subjective_review_pack_json={json_path}")
    print(f"[eval] subjective_review_pack_md={md_path}")


if __name__ == "__main__":
    main()
