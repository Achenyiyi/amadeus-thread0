from __future__ import annotations

import json
import sys
import time
import tempfile
import uuid
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from langchain_core.messages import HumanMessage

from amadeus_thread0.memory_store import MemoryStore
from amadeus_thread0.session_orchestrator import (
    build_tts_render_plan,
    derive_pending_fragment,
    derive_pending_user_goal,
    emotion_to_tts_profile,
    push_tts_segments,
)
REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


class _FakeRealtimeSession:
    def __init__(self) -> None:
        self.segments: list[str] = []

    def append_text(self, text: str) -> None:
        self.segments.append(str(text or ""))


def _ok(name: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"name": name, "status": "passed", "details": details or {}}


def _fail(name: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"name": name, "status": "failed", "details": details or {}}


def _make_appraisal(
    *,
    emotion_label: str,
    valence: float,
    arousal: float,
    linger: int,
    recovery_rate: float,
    volatility: float,
    signals: dict[str, bool] | None = None,
    bond_delta: dict[str, float] | None = None,
    allostasis_delta: dict[str, float] | None = None,
    interaction_frame: str = "relationship",
    reason: str = "",
) -> dict[str, Any]:
    from amadeus_thread0.graph import _coerce_appraisal_payload

    return _coerce_appraisal_payload(
        {
            "confidence": 0.95,
            "emotion_label": emotion_label,
            "emotion": {
                "valence": valence,
                "arousal": arousal,
                "linger": linger,
                "recovery_rate": recovery_rate,
                "volatility": volatility,
            },
            "signals": signals or {},
            "bond_delta": bond_delta or {},
            "allostasis_delta": allostasis_delta or {},
            "interaction_frame": interaction_frame,
            "reason": reason,
        }
    )


def _check_emotion_profiles() -> dict[str, Any]:
    labels = ["neutral", "logic", "care", "tease", "stress"]
    profiles = {label: emotion_to_tts_profile(label) for label in labels}
    required = {"min_chunk", "min_interval", "post_sleep"}
    for label, profile in profiles.items():
        if set(profile.keys()) != required:
            return _fail("emotion_profiles", {"label": label, "profile": profile})
    if not (
        profiles["logic"]["min_chunk"] > profiles["neutral"]["min_chunk"] > profiles["stress"]["min_chunk"]
    ):
        return _fail("emotion_profiles", {"profiles": profiles})
    return _ok("emotion_profiles", {"profiles": profiles})


def _check_tts_render_plan_preserves_text() -> dict[str, Any]:
    samples = [
        "你好。今天还好吗？",
        "先说结论：可以。然后我们接着把刚才那段讲完。",
        "如果你想，我可以先把上次那件事说完，再回到新的问题。\n这样不会断掉。",
    ]
    plans: list[dict[str, Any]] = []
    for label in ["neutral", "logic", "care"]:
        for sample in samples:
            plan = build_tts_render_plan(sample, label)
            rebuilt = "".join(plan.get("segments") or [])
            if rebuilt != plan.get("final_text"):
                return _fail(
                    "tts_render_plan",
                    {"label": label, "sample": sample, "rebuilt": rebuilt, "plan": plan},
                )
            if int(plan.get("segment_count") or 0) <= 0:
                return _fail("tts_render_plan", {"label": label, "sample": sample, "plan": plan})
            plans.append(
                {
                    "label": label,
                    "segment_count": int(plan.get("segment_count") or 0),
                    "char_count": int(plan.get("char_count") or 0),
                }
            )
    return _ok("tts_render_plan", {"plans": plans})


def _check_tts_push_segments_preserves_text() -> dict[str, Any]:
    fake = _FakeRealtimeSession()
    sleeps: list[float] = []
    text = "先说结论：可以。然后我们把刚才中断的地方续上。最后再看新的问题。"
    plan = push_tts_segments(
        fake,
        text=text,
        emotion_label="logic",
        sleep_fn=lambda sec: sleeps.append(round(float(sec), 3)),
    )
    rebuilt = "".join(fake.segments)
    if rebuilt != text.strip():
        return _fail(
            "tts_push_segments",
            {"rebuilt": rebuilt, "expected": text.strip(), "segments": fake.segments},
        )
    if not bool(plan.get("sent_ok")):
        return _fail("tts_push_segments", {"plan": plan})
    expected_sleep_calls = len(fake.segments)
    if len(sleeps) != expected_sleep_calls:
        return _fail(
            "tts_push_segments",
            {
                "sleep_calls": sleeps,
                "expected_sleep_calls": expected_sleep_calls,
                "segment_count": len(fake.segments),
            },
        )
    return _ok(
        "tts_push_segments",
        {
            "segment_count": len(fake.segments),
            "sleep_calls": sleeps,
            "profile": plan.get("profile"),
        },
    )


def _check_pending_fragment_paths() -> dict[str, Any]:
    resumed = derive_pending_fragment(
        user_text="继续刚才那段",
        previous_excerpt="上次你提到实验失败后其实没有真的放弃。",
        pending_fragment="",
    )
    fallback = derive_pending_fragment(
        user_text="接着说",
        previous_excerpt="",
        pending_fragment="我们还没把那件事说完。",
    )
    cleared = derive_pending_fragment(
        user_text="换个话题吧",
        previous_excerpt="刚才那段话",
        pending_fragment="仍待续接",
    )
    if "实验失败" not in resumed:
        return _fail("pending_fragment_paths", {"resumed": resumed})
    if "没把那件事说完" not in fallback:
        return _fail("pending_fragment_paths", {"fallback": fallback})
    if cleared != "":
        return _fail("pending_fragment_paths", {"cleared": cleared})
    return _ok(
        "pending_fragment_paths",
        {"resumed": resumed, "fallback": fallback, "cleared": cleared},
    )


def _check_pending_user_goal_paths() -> dict[str, Any]:
    resumed = derive_pending_user_goal(
        user_text="继续刚才那段",
        previous_user_text="先把上次那个实验方案分成三步说完。",
        pending_user_goal="我现在要做一个实验方案，请你用理性的方式给我一个三步计划，并解释每一步为什么这么安排。",
    )
    seeded = derive_pending_user_goal(
        user_text="我现在要做一个实验方案，请你用理性的方式给我一个三步计划，并解释每一步为什么这么安排。",
        previous_user_text="",
        pending_user_goal="",
    )
    cleared = derive_pending_user_goal(
        user_text="换个话题吧",
        previous_user_text="先把上次那个实验方案分成三步说完。",
        pending_user_goal="我现在要做一个实验方案，请你用理性的方式给我一个三步计划，并解释每一步为什么这么安排。",
    )
    if "实验方案" not in resumed:
        return _fail("pending_user_goal_paths", {"resumed": resumed})
    if "三步计划" not in seeded:
        return _fail("pending_user_goal_paths", {"seeded": seeded})
    if cleared != "":
        return _fail("pending_user_goal_paths", {"cleared": cleared})
    return _ok(
        "pending_user_goal_paths",
        {"resumed": resumed, "seeded": seeded, "cleared": cleared},
    )


def _check_emotion_persistence_curve() -> dict[str, Any]:
    from amadeus_thread0.graph import _emotion_next

    angry = _emotion_next(
        {},
        "我现在很生气，不想理你。",
        False,
        _make_appraisal(
            emotion_label="angry",
            valence=-0.74,
            arousal=0.84,
            linger=3,
            recovery_rate=0.16,
            volatility=0.33,
            signals={"conflict": True},
            bond_delta={"hurt": 0.18, "irritation": 0.22, "engagement_drive": -0.10},
            allostasis_delta={"safety_need": 0.14, "autonomy_need": 0.10, "cognitive_budget": -0.06},
            reason="backend_curve_conflict_seed",
        ),
    )
    decay = _emotion_next(angry, "嗯。", False)
    if str(angry.get("label") or "") != "angry":
        return _fail("emotion_persistence_curve", {"angry": angry})
    if str(decay.get("label") or "") not in {"angry", "hurt"}:
        return _fail("emotion_persistence_curve", {"decay": decay})
    if int(decay.get("linger") or 0) >= int(angry.get("linger") or 0):
        return _fail("emotion_persistence_curve", {"angry": angry, "decay": decay})
    return _ok("emotion_persistence_curve", {"angry": angry, "decay": decay})


def _check_partial_repair_curve() -> dict[str, Any]:
    from amadeus_thread0.graph import _allostasis_next, _behavior_policy_from_state, _bond_next, _emotion_next

    relationship = {"trust_score": 0.0, "affinity_score": 0.0}
    angry_text = "我现在很生气，不想理你。"
    apology_text = "对不起，是我不好。"

    angry_appraisal = _make_appraisal(
        emotion_label="angry",
        valence=-0.72,
        arousal=0.81,
        linger=3,
        recovery_rate=0.18,
        volatility=0.30,
        signals={"conflict": True},
        bond_delta={"hurt": 0.16, "irritation": 0.20, "engagement_drive": -0.08},
        allostasis_delta={"safety_need": 0.12, "autonomy_need": 0.08, "cognitive_budget": -0.05},
        reason="backend_curve_conflict_seed",
    )
    repair_appraisal = _make_appraisal(
        emotion_label="hurt",
        valence=-0.34,
        arousal=0.48,
        linger=2,
        recovery_rate=0.26,
        volatility=0.16,
        signals={"repair": True},
        bond_delta={
            "trust": 0.06,
            "closeness": 0.05,
            "hurt": -0.18,
            "irritation": -0.12,
            "engagement_drive": 0.09,
            "repair_confidence": 0.16,
        },
        allostasis_delta={
            "safety_need": -0.10,
            "closeness_need": 0.08,
            "autonomy_need": -0.06,
            "cognitive_budget": 0.04,
        },
        reason="backend_curve_partial_repair",
    )

    emotion_1 = _emotion_next({}, angry_text, False, angry_appraisal)
    bond_1 = _bond_next({}, relationship, emotion_1, angry_text, False, angry_appraisal)
    allostasis_1 = _allostasis_next({}, emotion_1, bond_1, angry_text, False, angry_appraisal)
    policy_1 = _behavior_policy_from_state(
        response_style_hint="natural",
        science_mode=False,
        emotion_state=emotion_1,
        bond_state=bond_1,
        allostasis_state=allostasis_1,
        tsundere_intensity=0.55,
    )

    emotion_2 = _emotion_next(emotion_1, apology_text, False, repair_appraisal)
    bond_2 = _bond_next(bond_1, relationship, emotion_2, apology_text, False, repair_appraisal)
    allostasis_2 = _allostasis_next(allostasis_1, emotion_2, bond_2, apology_text, False, repair_appraisal)
    policy_2 = _behavior_policy_from_state(
        response_style_hint="natural",
        science_mode=False,
        emotion_state=emotion_2,
        bond_state=bond_2,
        allostasis_state=allostasis_2,
        tsundere_intensity=0.55,
    )

    if str(emotion_2.get("label") or "") != "hurt":
        return _fail("partial_repair_curve", {"emotion_1": emotion_1, "emotion_2": emotion_2})
    if not (float(bond_2.get("hurt") or 0.0) < float(bond_1.get("hurt") or 0.0)):
        return _fail("partial_repair_curve", {"bond_1": bond_1, "bond_2": bond_2})
    if not (float(bond_2.get("repair_confidence") or 0.0) > float(bond_1.get("repair_confidence") or 0.0)):
        return _fail("partial_repair_curve", {"bond_1": bond_1, "bond_2": bond_2})
    if not (float(policy_2.get("approach_vs_withdraw") or 0.0) > float(policy_1.get("approach_vs_withdraw") or 0.0)):
        return _fail("partial_repair_curve", {"policy_1": policy_1, "policy_2": policy_2})
    if float(bond_2.get("hurt") or 0.0) <= 0.08:
        return _fail("partial_repair_curve", {"bond_2": bond_2})
    return _ok(
        "partial_repair_curve",
        {
            "emotion_1": emotion_1,
            "emotion_2": emotion_2,
            "bond_1": bond_1,
            "bond_2": bond_2,
            "policy_1": policy_1,
            "policy_2": policy_2,
        },
    )


def _check_withdrawal_recovery_curve() -> dict[str, Any]:
    from amadeus_thread0.graph import _allostasis_next, _behavior_policy_from_state, _bond_next, _emotion_next

    relationship = {"trust_score": 0.0, "affinity_score": 0.0}
    angry_text = "我现在很生气，不想理你。"
    apology_text = "对不起，是我不好。"
    care_text = "那你先休息一下。"

    angry_appraisal = _make_appraisal(
        emotion_label="angry",
        valence=-0.72,
        arousal=0.80,
        linger=3,
        recovery_rate=0.18,
        volatility=0.30,
        signals={"conflict": True},
        bond_delta={"hurt": 0.16, "irritation": 0.20, "engagement_drive": -0.08},
        allostasis_delta={"safety_need": 0.12, "autonomy_need": 0.08, "cognitive_budget": -0.05},
        reason="backend_curve_conflict_seed",
    )
    repair_appraisal = _make_appraisal(
        emotion_label="hurt",
        valence=-0.32,
        arousal=0.46,
        linger=2,
        recovery_rate=0.26,
        volatility=0.16,
        signals={"repair": True},
        bond_delta={
            "trust": 0.05,
            "closeness": 0.05,
            "hurt": -0.16,
            "irritation": -0.10,
            "engagement_drive": 0.08,
            "repair_confidence": 0.14,
        },
        allostasis_delta={
            "safety_need": -0.08,
            "closeness_need": 0.07,
            "autonomy_need": -0.05,
            "cognitive_budget": 0.04,
        },
        reason="backend_curve_partial_repair",
    )
    care_appraisal = _make_appraisal(
        emotion_label="care",
        valence=0.24,
        arousal=0.34,
        linger=1,
        recovery_rate=0.30,
        volatility=0.12,
        signals={"care": True, "repair": True},
        bond_delta={
            "trust": 0.07,
            "closeness": 0.10,
            "hurt": -0.10,
            "irritation": -0.08,
            "engagement_drive": 0.10,
            "repair_confidence": 0.10,
        },
        allostasis_delta={
            "safety_need": -0.12,
            "closeness_need": 0.10,
            "autonomy_need": -0.06,
            "cognitive_budget": 0.04,
        },
        interaction_frame="companion",
        reason="backend_curve_care_recovery",
    )

    emotion_1 = _emotion_next({}, angry_text, False, angry_appraisal)
    bond_1 = _bond_next({}, relationship, emotion_1, angry_text, False, angry_appraisal)
    allostasis_1 = _allostasis_next({}, emotion_1, bond_1, angry_text, False, angry_appraisal)
    policy_1 = _behavior_policy_from_state(
        response_style_hint="natural",
        science_mode=False,
        emotion_state=emotion_1,
        bond_state=bond_1,
        allostasis_state=allostasis_1,
        tsundere_intensity=0.55,
    )

    emotion_2 = _emotion_next(emotion_1, apology_text, False, repair_appraisal)
    bond_2 = _bond_next(bond_1, relationship, emotion_2, apology_text, False, repair_appraisal)
    allostasis_2 = _allostasis_next(allostasis_1, emotion_2, bond_2, apology_text, False, repair_appraisal)
    policy_2 = _behavior_policy_from_state(
        response_style_hint="natural",
        science_mode=False,
        emotion_state=emotion_2,
        bond_state=bond_2,
        allostasis_state=allostasis_2,
        tsundere_intensity=0.55,
    )

    emotion_3 = _emotion_next(emotion_2, care_text, False, care_appraisal)
    bond_3 = _bond_next(bond_2, relationship, emotion_3, care_text, False, care_appraisal)
    allostasis_3 = _allostasis_next(allostasis_2, emotion_3, bond_3, care_text, False, care_appraisal)
    policy_3 = _behavior_policy_from_state(
        response_style_hint="natural",
        science_mode=False,
        emotion_state=emotion_3,
        bond_state=bond_3,
        allostasis_state=allostasis_3,
        tsundere_intensity=0.55,
    )

    if not (
        float(policy_1.get("approach_vs_withdraw") or 0.0)
        < float(policy_2.get("approach_vs_withdraw") or 0.0)
        < float(policy_3.get("approach_vs_withdraw") or 0.0)
    ):
        return _fail(
            "withdrawal_recovery_curve",
            {"policy_1": policy_1, "policy_2": policy_2, "policy_3": policy_3},
        )
    if float(allostasis_3.get("safety_need") or 0.0) >= float(allostasis_1.get("safety_need") or 0.0):
        return _fail(
            "withdrawal_recovery_curve",
            {"allostasis_1": allostasis_1, "allostasis_3": allostasis_3},
        )
    return _ok(
        "withdrawal_recovery_curve",
        {
            "policy_1": policy_1,
            "policy_2": policy_2,
            "policy_3": policy_3,
            "allostasis_1": allostasis_1,
            "allostasis_3": allostasis_3,
        },
    )


def _check_reply_repetition_pressure() -> dict[str, Any]:
    from amadeus_thread0.graph import _generation_profile, _reply_repetition_signature

    repeated = [
        "你好。今天怎么样？",
        "你好。今天怎么样？",
        "你好。今天怎么样？",
        "你好。今天怎么样？",
    ]
    diverse = [
        "早。你昨晚是不是又熬太晚了？",
        "刚才那句我记着，不过你先把眼前这件事说完。",
        "如果只是想让我陪你待一会儿，也不是不行。",
        "这题先拆开，不然你又要一口气把自己绕进去。",
    ]
    repeated_sig = _reply_repetition_signature(
        user_text="你好",
        recent_assistant_texts=repeated,
        response_style_hint="natural",
        current_event_kind="user_utterance",
    )
    diverse_sig = _reply_repetition_signature(
        user_text="你好",
        recent_assistant_texts=diverse,
        response_style_hint="natural",
        current_event_kind="user_utterance",
    )
    repeated_profile = _generation_profile(
        response_style_hint="natural",
        science_mode=False,
        continuation_mode=False,
        user_text="你好",
        runtime_mode="experience",
        turn_index=8,
        recent_assistant_texts=repeated,
        current_event={"kind": "user_utterance"},
        emotion_state={"label": "neutral"},
        bond_state={"trust": 0.58, "hurt": 0.04},
        allostasis_state={"cognitive_budget": 0.66, "safety_need": 0.18},
        counterpart_assessment={"boundary_pressure": 0.08},
        behavior_policy={"reply_length_bias": 0.48, "warmth": 0.57, "sharpness": 0.34, "approach_vs_withdraw": 0.55},
    )
    diverse_profile = _generation_profile(
        response_style_hint="natural",
        science_mode=False,
        continuation_mode=False,
        user_text="你好",
        runtime_mode="experience",
        turn_index=8,
        recent_assistant_texts=diverse,
        current_event={"kind": "user_utterance"},
        emotion_state={"label": "neutral"},
        bond_state={"trust": 0.58, "hurt": 0.04},
        allostasis_state={"cognitive_budget": 0.66, "safety_need": 0.18},
        counterpart_assessment={"boundary_pressure": 0.08},
        behavior_policy={"reply_length_bias": 0.48, "warmth": 0.57, "sharpness": 0.34, "approach_vs_withdraw": 0.55},
    )

    if float(repeated_sig.get("pressure") or 0.0) <= float(diverse_sig.get("pressure") or 0.0):
        return _fail("reply_repetition_pressure", {"repeated_sig": repeated_sig, "diverse_sig": diverse_sig})
    if float(repeated_profile.get("frequency_penalty") or 0.0) <= float(diverse_profile.get("frequency_penalty") or 0.0):
        return _fail(
            "reply_repetition_pressure",
            {"repeated_profile": repeated_profile, "diverse_profile": diverse_profile},
        )
    if float(repeated_profile.get("presence_penalty") or 0.0) <= float(diverse_profile.get("presence_penalty") or 0.0):
        return _fail(
            "reply_repetition_pressure",
            {"repeated_profile": repeated_profile, "diverse_profile": diverse_profile},
        )
    return _ok(
        "reply_repetition_pressure",
        {
            "repeated_sig": repeated_sig,
            "diverse_sig": diverse_sig,
            "repeated_profile": repeated_profile,
            "diverse_profile": diverse_profile,
        },
    )


def _check_reconsolidation_namespaces() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "memories.sqlite"
        store = MemoryStore(db_path)
        tension = store.add_unresolved_tension(summary="上次那次争执还没完全说开。", severity=0.72)
        narrative = store.add_semantic_self_narrative(
            text="她会把和冈部的关键共同经历当成长期参考系。",
            stability=0.66,
        )
        trace = store.add_revision_trace(
            namespace="unresolved_tensions",
            target_id=tension.get("id"),
            before_summary="上次那次争执还没完全说开。",
            after_summary="已经开始尝试修复，但还没有完全恢复。",
            reason="partial_repair",
            operator="test",
            source="backend_check",
        )
        snap = store.snapshot()
        store.close()

    if not snap.get("unresolved_tensions"):
        return _fail("reconsolidation_namespaces", {"snapshot": snap})
    if not snap.get("semantic_self_narratives"):
        return _fail("reconsolidation_namespaces", {"snapshot": snap})
    if not snap.get("revision_traces"):
        return _fail("reconsolidation_namespaces", {"snapshot": snap})
    return _ok(
        "reconsolidation_namespaces",
        {
            "tension_id": tension.get("id"),
            "narrative_id": narrative.get("id"),
            "trace_id": trace.get("id"),
        },
    )


def _check_conflict_events_do_not_fake_repairs() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "memories.sqlite"
        store = MemoryStore(db_path)
        store.add_worldline_event("我们闹了别扭。", category="conflict", importance=0.72)
        repairs = store.list_conflict_repairs(limit=10)
        store.close()

    if repairs:
        return _fail("conflict_events_do_not_fake_repairs", {"repairs": repairs})
    return _ok("conflict_events_do_not_fake_repairs", {})


def _check_auto_reconsolidation_flow() -> dict[str, Any]:
    from amadeus_thread0.graph import _auto_reconsolidate_after_tool

    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "memories.sqlite"
        store = MemoryStore(db_path)
        tension = store.add_unresolved_tension(summary="上次那次误会还没完全说开，我还是有点别扭。", severity=0.78)
        repair = store.add_worldline_event(
            "上次那次误会已经说开了，我们和好了。",
            category="conflict_repair",
            importance=0.84,
        )
        _auto_reconsolidate_after_tool(
            store,
            tool_name="add_worldline_event",
            args={"summary": "上次那次误会已经说开了，我们和好了。", "category": "conflict_repair"},
            result=repair,
        )
        tensions = store.list_unresolved_tensions(limit=10)
        narratives = store.list_semantic_self_narratives(limit=10)
        traces = store.list_revision_traces(limit=20)
        repairs = store.list_conflict_repairs(limit=10)
        store.close()

    target = next((it for it in tensions if int(it.get("id") or 0) == int(tension.get("id") or 0)), None)
    if not target or str(target.get("status") or target.get("content", {}).get("status") or "").strip().lower() != "resolved":
        return _fail("auto_reconsolidation_flow", {"tensions": tensions})
    if not repairs:
        return _fail("auto_reconsolidation_flow", {"repairs": repairs})
    if not narratives:
        return _fail("auto_reconsolidation_flow", {"narratives": narratives})
    if not any(str(it.get("namespace") or it.get("content", {}).get("namespace") or "") == "unresolved_tensions" for it in traces):
        return _fail("auto_reconsolidation_flow", {"traces": traces})
    return _ok(
        "auto_reconsolidation_flow",
        {
            "tension_id": tension.get("id"),
            "repair_count": len(repairs),
            "narrative_count": len(narratives),
            "trace_count": len(traces),
        },
    )


def _check_transfer_probe_second_persona() -> dict[str, Any]:
    from amadeus_thread0.graph import _refresh_semantic_self_narratives

    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "memories.sqlite"
        store = MemoryStore(db_path)
        try:
            store.add_commitment("周六晚上一起同步 NERV 日志。", confidence=0.78)
            store.add_unresolved_tension(summary="上次那件事我还是有点介意，还没完全说开。", severity=0.74)
            store.add_worldline_event(
                "至少这次算把误会说开了一部分，但还不是立刻恢复原样。",
                category="conflict_repair",
                importance=0.81,
            )
            _refresh_semantic_self_narratives(
                store,
                source="transfer_probe",
                persona_core={"display_name": "绫波丽", "short_name": "绫波", "narrative_ref": "绫波"},
                counterpart_profile={"name": "碇真嗣", "short_name": "真嗣", "aliases": ["碇真嗣", "真嗣"]},
            )
            narratives = store.list_semantic_self_narratives(limit=10)
        finally:
            store.close()

    text = "\n".join(
        str(item.get("text") or item.get("content", {}).get("text") or "")
        for item in narratives
        if isinstance(item, dict)
    )
    if not narratives:
        return _fail("transfer_probe_second_persona", {"narratives": narratives})
    if "绫波" not in text or "真嗣" not in text:
        return _fail("transfer_probe_second_persona", {"text": text, "narratives": narratives})
    if "冈部" in text or "红莉栖" in text:
        return _fail("transfer_probe_second_persona", {"text": text, "narratives": narratives})
    if not any(int(item.get("support_count") or item.get("content", {}).get("support_count") or 0) >= 1 for item in narratives):
        return _fail("transfer_probe_second_persona", {"narratives": narratives})
    if not any(float(item.get("sedimentation_score") or item.get("content", {}).get("sedimentation_score") or 0.0) > 0.0 for item in narratives):
        return _fail("transfer_probe_second_persona", {"narratives": narratives})
    return _ok(
        "transfer_probe_second_persona",
        {
            "narrative_count": len(narratives),
            "preview": text[:220],
        },
    )


def _check_light_dialog_prompt_is_lightweight() -> dict[str, Any]:
    from amadeus_thread0.graph import _build_task_prompt

    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "memories.sqlite"
        store = MemoryStore(db_path)
        try:
            store.set_relationship(
                {
                    "stage": "warming",
                    "affinity_score": 0.28,
                    "trust_score": 0.31,
                    "notes": "",
                    "derived": True,
                }
            )
            prompt = _build_task_prompt(
                {
                    "messages": [HumanMessage(content="你好呀")],
                    "response_style_hint": "natural",
                    "science_mode": False,
                    "emotion_state": {"label": "neutral"},
                    "bond_state": {"trust": 0.58, "closeness": 0.55, "hurt": 0.0},
                    "allostasis_state": {"safety_need": 0.16, "cognitive_budget": 0.82},
                    "counterpart_assessment": {"summary": "你觉得冈部基本是在认真对待你，也愿意双向互动。"},
                    "world_model_state": {},
                    "evolution_state": {},
                    "behavior_action": {"interaction_mode": "steady_reply"},
                    "behavior_policy": {},
                    "turn_appraisal": {},
                    "current_event": {
                        "kind": "user_utterance",
                        "source": "text",
                        "text": "你好呀",
                        "effective_text": "你好呀",
                        "event_frame": "ordinary ongoing interaction",
                    },
                    "recent_events": [],
                    "pending_utterance_fragment": "",
                    "pending_user_goal": "",
                    "worldline_focus": [],
                    "retrieved_context": {
                        "working_items": [],
                        "relationship_timeline": [],
                        "conflict_repairs": [],
                        "semantic_self_narratives": [],
                    },
                    "evidence_pack": [],
                },
                "你好呀",
                store,
            )
        finally:
            store.close()

    if "当前状态(JSON)" in prompt or "state_snapshot=" in prompt:
        return _fail("light_dialog_prompt_is_lightweight", {"prompt": prompt})
    if "\\n输出" in prompt or "\\n用户输入" in prompt:
        return _fail("light_dialog_prompt_is_lightweight", {"prompt": prompt})
    if "用户输入：你好呀\n输出：此刻会说的话。" not in prompt:
        return _fail("light_dialog_prompt_is_lightweight", {"prompt": prompt})
    return _ok(
        "light_dialog_prompt_is_lightweight",
        {"prompt_preview": prompt[:240]},
    )


def _check_light_smalltalk_answer_cleanup() -> dict[str, Any]:
    from amadeus_thread0.graph import _sanitize_final_answer

    answer = (
        "……“你好呀”？\n"
        "（稍微停顿了一下，视线在屏幕上停留了片刻，像是在确认什么，又像是在掩饰那一瞬间的恍惚）\n"
        "这种毫无信息量的开场白，居然从你嘴里说出来，还真是让人有点意外。\n"
        "不过……算了。既然你都这么轻松地打招呼了，我也没必要非要摆出一副严阵以待的样子。\n"
        "说吧，冈部。突然这么客气，是有什么新的发现想和我分享，还是说……单纯只是想确认一下，我是不是还在这里？\n"
        "（嘴角极轻微地扬了一下，随即又恢复了那种带着点别扭的平静）"
    )
    cleaned = _sanitize_final_answer(answer, "你好呀")
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    sentence_count = len([seg for seg in __import__("re").split(r"[。！？!?]", cleaned) if str(seg).strip()])
    if any((line.startswith("（") and line.endswith("）")) or (line.startswith("(") and line.endswith(")")) for line in lines):
        return _fail("light_smalltalk_answer_cleanup", {"cleaned": cleaned})
    if sentence_count > 3:
        return _fail("light_smalltalk_answer_cleanup", {"cleaned": cleaned, "sentence_count": sentence_count})
    return _ok(
        "light_smalltalk_answer_cleanup",
        {"cleaned": cleaned, "sentence_count": sentence_count},
    )


def _run_checks() -> list[dict[str, Any]]:
    checks: list[Callable[[], dict[str, Any]]] = [
        _check_emotion_profiles,
        _check_tts_render_plan_preserves_text,
        _check_tts_push_segments_preserves_text,
        _check_pending_fragment_paths,
        _check_pending_user_goal_paths,
        _check_emotion_persistence_curve,
        _check_partial_repair_curve,
        _check_withdrawal_recovery_curve,
        _check_reply_repetition_pressure,
        _check_reconsolidation_namespaces,
        _check_conflict_events_do_not_fake_repairs,
        _check_auto_reconsolidation_flow,
        _check_transfer_probe_second_persona,
        _check_light_dialog_prompt_is_lightweight,
        _check_light_smalltalk_answer_cleanup,
    ]
    return [fn() for fn in checks]


def _write_reports(results: list[dict[str, Any]]) -> tuple[Path, Path]:
    ts = time.strftime("%Y%m%d-%H%M%S")
    run_id = uuid.uuid4().hex[:8]
    json_path = REPORT_DIR / f"backend-check-{ts}-{run_id}.json"
    md_path = REPORT_DIR / f"backend-check-{ts}-{run_id}.md"

    passed = len([it for it in results if it.get("status") == "passed"])
    failed_rows = [it for it in results if it.get("status") != "passed"]
    payload = {
        "generated_at": ts,
        "passed": passed,
        "failed": len(failed_rows),
        "results": results,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Backend Reliability Checks",
        "",
        f"- Generated: `{ts}`",
        f"- Passed: `{passed}`",
        f"- Failed: `{len(failed_rows)}`",
        "",
        "| Check | Status |",
        "| --- | --- |",
    ]
    for row in results:
        lines.append(f"| `{row.get('name')}` | `{row.get('status')}` |")
    if failed_rows:
        lines.extend(["", "## Failures", ""])
        for row in failed_rows:
            lines.append(f"- `{row.get('name')}`: `{json.dumps(row.get('details') or {}, ensure_ascii=False)}`")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    results = _run_checks()
    json_path, md_path = _write_reports(results)
    failed = [it for it in results if it.get("status") != "passed"]
    print("[backend-check] json=" + str(json_path))
    print("[backend-check] md=" + str(md_path))
    if failed:
        print("[backend-check] failed=" + str(len(failed)))
        return 1
    print("[backend-check] all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
