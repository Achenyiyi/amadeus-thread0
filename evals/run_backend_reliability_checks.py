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

    angry = _emotion_next({}, "我现在很生气，不想理你。", False)
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

    emotion_1 = _emotion_next({}, angry_text, False)
    bond_1 = _bond_next({}, relationship, emotion_1, angry_text)
    allostasis_1 = _allostasis_next({}, emotion_1, bond_1, angry_text, False)
    policy_1 = _behavior_policy_from_state(
        response_style_hint="natural",
        science_mode=False,
        emotion_state=emotion_1,
        bond_state=bond_1,
        allostasis_state=allostasis_1,
        tsundere_intensity=0.55,
    )

    emotion_2 = _emotion_next(emotion_1, apology_text, False)
    bond_2 = _bond_next(bond_1, relationship, emotion_2, apology_text)
    allostasis_2 = _allostasis_next(allostasis_1, emotion_2, bond_2, apology_text, False)
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

    emotion_1 = _emotion_next({}, angry_text, False)
    bond_1 = _bond_next({}, relationship, emotion_1, angry_text)
    allostasis_1 = _allostasis_next({}, emotion_1, bond_1, angry_text, False)
    policy_1 = _behavior_policy_from_state(
        response_style_hint="natural",
        science_mode=False,
        emotion_state=emotion_1,
        bond_state=bond_1,
        allostasis_state=allostasis_1,
        tsundere_intensity=0.55,
    )

    emotion_2 = _emotion_next(emotion_1, apology_text, False)
    bond_2 = _bond_next(bond_1, relationship, emotion_2, apology_text)
    allostasis_2 = _allostasis_next(allostasis_1, emotion_2, bond_2, apology_text, False)
    policy_2 = _behavior_policy_from_state(
        response_style_hint="natural",
        science_mode=False,
        emotion_state=emotion_2,
        bond_state=bond_2,
        allostasis_state=allostasis_2,
        tsundere_intensity=0.55,
    )

    emotion_3 = _emotion_next(emotion_2, care_text, False)
    bond_3 = _bond_next(bond_2, relationship, emotion_3, care_text)
    allostasis_3 = _allostasis_next(allostasis_2, emotion_3, bond_3, care_text, False)
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
        _check_reconsolidation_namespaces,
        _check_conflict_events_do_not_fake_repairs,
        _check_auto_reconsolidation_flow,
        _check_transfer_probe_second_persona,
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
