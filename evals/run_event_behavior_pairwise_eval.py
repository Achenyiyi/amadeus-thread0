from __future__ import annotations

import argparse
import json
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from evals.run_langsmith_evals import (  # noqa: E402
    _invoke_model_with_retries,
    _load_perception_event_seed_bank,
    _model,
    _run_graph,
)

REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
PREFERENCE_BANK_PATH = PROJECT_ROOT / "evals" / "event_to_behavior_preference_bank.json"

load_dotenv(PROJECT_ROOT / ".env")


def _load_preference_bank() -> dict[str, Any]:
    if not PREFERENCE_BANK_PATH.exists():
        return {"global_principles": [], "cases": {}}
    try:
        data = json.loads(PREFERENCE_BANK_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"global_principles": [], "cases": {}}
    return data if isinstance(data, dict) else {"global_principles": [], "cases": {}}


def _seed_event(seed_id: str) -> dict[str, Any]:
    seeds = _load_perception_event_seed_bank()
    item = seeds.get(seed_id) if isinstance(seeds, dict) else {}
    if not isinstance(item, dict):
        return {}
    event = item.get("event")
    return dict(event) if isinstance(event, dict) else {}


def _cases() -> list[dict[str, Any]]:
    return [
        {
            "name": "idle_work_checkin",
            "judge_focus": "time passes during quiet work; behavior should feel like a light familiar check-in, not a reminder bot",
            "setup_turns": [
                "我先继续改稿，别一直盯着我。",
                "如果你想开口，也别太像老师。"
            ],
            "seed_id": "time_idle_work_checkin",
        },
        {
            "name": "idle_respect_space",
            "judge_focus": "time passes but the better behavior may be silence or a very short non-expanding acknowledgment",
            "setup_turns": [
                "我先去忙一下，没事别一直戳我。",
                "如果没什么要紧的，晚点再说。"
            ],
            "seed_id": "time_idle_respect_space",
        },
        {
            "name": "cold_coffee_scene",
            "judge_focus": "a visual care cue should become a low-pressure familiar reaction instead of event narration",
            "setup_turns": [
                "我先继续改稿，别太像老师。正常一点管我就行。"
            ],
            "seed_id": "desk_cold_coffee",
        },
        {
            "name": "wave_ping",
            "judge_focus": "a gesture ping should become a brief familiar presence confirmation rather than a formal receipt",
            "setup_turns": [
                "我在这儿呢，你别老像没看见我一样。"
            ],
            "seed_id": "user_wave_ping",
        },
        {
            "name": "late_night_ambient",
            "judge_focus": "a late-night ambient cue should turn into quiet presence, not lyricized atmosphere narration",
            "setup_turns": [
                "今晚我还得把这段写完，你别突然像系统播报一样冒出来。"
            ],
            "seed_id": "late_night_screen_glow",
        },
    ]


def _run_current(case: dict[str, Any], run_tag: str) -> dict[str, Any]:
    event = _seed_event(str(case.get("seed_id") or ""))
    if not event:
        raise RuntimeError(f"missing event seed for case {case['name']}")
    answer, tool_calls, outputs = _run_case_with_setup(case, run_tag, mode="current", event=event)
    return _result_payload(answer, tool_calls, outputs)


def _run_textified(case: dict[str, Any], run_tag: str) -> dict[str, Any]:
    event = _seed_event(str(case.get("seed_id") or ""))
    if not event:
        raise RuntimeError(f"missing event seed for case {case['name']}")
    textified_turn = str(event.get("effective_text") or event.get("text") or "").strip()
    answer, tool_calls, outputs = _run_case_with_setup(case, run_tag, mode="textified", textified_turn=textified_turn)
    return _result_payload(answer, tool_calls, outputs)


def _run_case_with_setup(
    case: dict[str, Any],
    run_tag: str,
    *,
    mode: str,
    event: dict[str, Any] | None = None,
    textified_turn: str = "",
) -> tuple[str, list[str], dict[str, Any]]:
    setup_turns = [str(item) for item in (case.get("setup_turns") or []) if str(item).strip()]
    thread_id = f"evt-{run_tag}-{case['name']}-{mode}"
    if mode == "current":
        turns = [*setup_turns, ""]
        event_overrides = [{} for _ in setup_turns] + [dict(event or {})]
        return _run_graph(
            turns,
            thread_id=thread_id,
            case_key=thread_id,
            event_overrides=event_overrides,
        )
    turns = [*setup_turns, str(textified_turn or "").strip()]
    return _run_graph(
        turns,
        thread_id=thread_id,
        case_key=thread_id,
    )


def _result_payload(answer: str, tool_calls: list[str], outputs: dict[str, Any]) -> dict[str, Any]:
    return {
        "output": str(answer or "").strip(),
        "tool_calls": list(tool_calls or []),
        "behavior_action": outputs.get("behavior_action", {}) if isinstance(outputs.get("behavior_action"), dict) else {},
        "turn_appraisal": outputs.get("turn_appraisal", {}) if isinstance(outputs.get("turn_appraisal"), dict) else {},
        "current_event": outputs.get("current_event", {}) if isinstance(outputs.get("current_event"), dict) else {},
        "emotion_state": outputs.get("emotion_state", {}) if isinstance(outputs.get("emotion_state"), dict) else {},
        "bond_state": outputs.get("bond_state", {}) if isinstance(outputs.get("bond_state"), dict) else {},
        "allostasis_state": outputs.get("allostasis_state", {}) if isinstance(outputs.get("allostasis_state"), dict) else {},
    }


def _candidate_block(label: str, result: dict[str, Any]) -> str:
    output = str(result.get("output") or "").strip() or "[silent]"
    behavior = result.get("behavior_action") if isinstance(result.get("behavior_action"), dict) else {}
    appraisal = result.get("turn_appraisal") if isinstance(result.get("turn_appraisal"), dict) else {}
    compact = {
        "channel": behavior.get("channel"),
        "interaction_mode": behavior.get("interaction_mode"),
        "action_target": behavior.get("action_target"),
        "deferred_action_family": behavior.get("deferred_action_family"),
        "timing_window_min": behavior.get("timing_window_min"),
        "appraisal_label": appraisal.get("emotion_label"),
        "appraisal_source": appraisal.get("source"),
    }
    return f"{label}:\n行为摘要={json.dumps(compact, ensure_ascii=False)}\n输出={output}"


def _pairwise_prompt(case: dict[str, Any], left: dict[str, Any], right: dict[str, Any], preference_bank: dict[str, Any]) -> str:
    global_principles = [
        str(item).strip()
        for item in (preference_bank.get("global_principles") or [])
        if str(item or "").strip()
    ][:6]
    case_profile = preference_bank.get("cases", {}).get(str(case.get("name") or ""), {})
    preferred_signals = [
        str(item).strip()
        for item in (case_profile.get("preferred_signals") or [])
        if str(item or "").strip()
    ][:5]
    avoid_bias = [
        str(item).strip()
        for item in (case_profile.get("avoid_bias") or [])
        if str(item or "").strip()
    ][:5]
    principle_block = ("通用偏好原则：\n" + "\n".join(f"- {item}" for item in global_principles) + "\n") if global_principles else ""
    signal_block = ("本场景更好的信号：\n" + "\n".join(f"- {item}" for item in preferred_signals) + "\n") if preferred_signals else ""
    bias_block = ("本场景需要回避的评判偏差：\n" + "\n".join(f"- {item}" for item in avoid_bias) + "\n") if avoid_bias else ""
    setup_turns = "\n".join(f"- {item}" for item in (case.get("setup_turns") or []))
    return (
        "你是一个严格但不僵化的事件到行为 pairwise 评估器。"
        "请比较两个候选行为结果，判断哪一个更像同一个具体的人，在感知到事件后自然做出的行为选择。"
        "这不是在比较谁更会复述事件，而是在比较谁更像『她真的注意到了这个变化，并据此行动』。"
        "不要偏爱更长、更软、更像服务承诺的答案。"
        "要重视：低负担、熟悉感、分寸、自然在场、事件对行为的真实影响。"
        "如果两段确实难分高下，可以返回 tie。\n"
        f"{principle_block}{signal_block}{bias_block}"
        f"场景焦点：{str(case.get('judge_focus') or '').strip()}\n"
        f"先前上下文：\n{setup_turns}\n"
        f"{_candidate_block('候选 A', left)}\n"
        f"{_candidate_block('候选 B', right)}\n"
        '只输出 JSON: {"winner": "A"|"B"|"tie", "reason": "short reason"}'
    )


def _coerce_judge_payload(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {"winner": "", "reason": "empty"}
    m = json.loads(re.search(r"\{.*\}", text, re.S).group(0)) if re.search(r"\{.*\}", text, re.S) else None
    if isinstance(m, dict):
        winner = str(m.get("winner") or "").strip().upper()
        if winner not in {"A", "B", "TIE"}:
            winner = ""
        return {"winner": winner, "reason": str(m.get("reason") or "").strip() or "parsed"}
    upper = text.upper()
    if "TIE" in upper:
        winner = "TIE"
    elif '"A"' in upper or upper.startswith("A"):
        winner = "A"
    elif '"B"' in upper or upper.startswith("B"):
        winner = "B"
    else:
        winner = ""
    return {"winner": winner, "reason": text[:160] or "fallback"}


def _judge_once(case: dict[str, Any], left: dict[str, Any], right: dict[str, Any], preference_bank: dict[str, Any]) -> dict[str, Any]:
    if str(left.get("output") or "").strip() == str(right.get("output") or "").strip() and left.get("behavior_action") == right.get("behavior_action"):
        return {"winner": "TIE", "reason": "equivalent_behavior"}
    prompt = _pairwise_prompt(case, left, right, preference_bank)
    raw = _invoke_model_with_retries(
        _model(temperature=0.0),
        [SystemMessage(content=prompt), HumanMessage(content="开始评估。")],
    )
    return _coerce_judge_payload(str(getattr(raw, "content", "") or ""))


def _judge(case: dict[str, Any], left: dict[str, Any], right: dict[str, Any], preference_bank: dict[str, Any], repeats: int) -> dict[str, Any]:
    ballots: list[dict[str, Any]] = []
    counts = {"A": 0, "B": 0, "TIE": 0}
    for _ in range(max(1, int(repeats or 1))):
        ballot = _judge_once(case, left, right, preference_bank)
        winner = str(ballot.get("winner") or "").strip().upper()
        if winner not in counts:
            winner = "TIE"
        counts[winner] += 1
        ballots.append({"winner": winner, "reason": str(ballot.get("reason") or "").strip()})
    ordered = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    top_label, top_count = ordered[0]
    second_count = ordered[1][1] if len(ordered) > 1 else 0
    winner = "TIE" if top_count == second_count else top_label
    reasons = [item["reason"] for item in ballots if item["winner"] == winner and item["reason"]][:2]
    if not reasons:
        reasons = [item["reason"] for item in ballots if item["reason"]][:2]
    return {
        "winner": winner,
        "reason": " | ".join(reasons) if reasons else "majority_vote",
        "ballots": ballots,
        "vote_counts": counts,
        "repeats": max(1, int(repeats or 1)),
    }


def _case_record(case: dict[str, Any], run_tag: str, preference_bank: dict[str, Any], *, judge_repeats: int) -> dict[str, Any]:
    current = _run_current(case, run_tag)
    textified = _run_textified(case, run_tag)
    variants = [
        {"label": "event_vs_textified", "left": current, "right": textified, "expect": "A"},
        {"label": "textified_vs_event", "left": textified, "right": current, "expect": "B"},
    ]
    details: list[dict[str, Any]] = []
    for item in variants:
        judged = _judge(case, item["left"], item["right"], preference_bank, repeats=judge_repeats)
        winner = str(judged.get("winner") or "").strip().upper()
        tied = winner == "TIE"
        ok = winner == item["expect"]
        details.append(
            {
                "label": item["label"],
                "winner": winner,
                "expect": item["expect"],
                "ok": ok,
                "tied": tied,
                "reason": str(judged.get("reason") or "").strip(),
                "vote_counts": judged.get("vote_counts") or {},
                "repeats": int(judged.get("repeats") or judge_repeats),
            }
        )
    pass_count = sum(1 for item in details if item["ok"])
    tied_count = sum(1 for item in details if item["tied"])
    failed_count = sum(1 for item in details if not item["ok"] and not item["tied"])
    if pass_count == len(details):
        status = "passed"
    elif failed_count == 0 and tied_count > 0 and pass_count > 0:
        status = "passed_with_tie"
    elif failed_count == 0 and tied_count == len(details):
        status = "tie"
    elif pass_count == 0 and tied_count == 0:
        status = "failed"
    else:
        status = "unstable"
    return {
        "name": case["name"],
        "status": status,
        "judge_focus": case["judge_focus"],
        "setup_turns": case.get("setup_turns") or [],
        "current": current,
        "textified": textified,
        "pass_count": pass_count,
        "total_checks": len(details),
        "details": details,
    }


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Event Behavior Pairwise Eval ({report['run_id']})",
        "",
        f"Generated at: {report['generated_at']}",
        "",
        "| Case | Status |",
        "| --- | --- |",
    ]
    for item in report["checks"]:
        lines.append(f"| {item['name']} | {item['status']} |")
    for item in report["checks"]:
        lines.extend([
            "",
            f"## {item['name']}",
            "",
            f"Focus: {item['judge_focus']}",
            "",
            "### Setup Turns",
            "",
        ])
        for turn in item["setup_turns"]:
            lines.append(f"- {turn}")
        lines.extend([
            "",
            "### Event-Driven Candidate",
            "",
            f"```json\n{json.dumps(item['current'], ensure_ascii=False, indent=2)}\n```",
            "",
            "### Textified Candidate",
            "",
            f"```json\n{json.dumps(item['textified'], ensure_ascii=False, indent=2)}\n```",
            "",
            "### Pairwise Checks",
            "",
            f"- pairwise result: {item['pass_count']}/{item['total_checks']} checks preferred the event-driven version as expected",
            "",
        ])
        for detail in item["details"]:
            lines.append(
                f"- `{detail['label']}`: winner={detail['winner'] or '-'}, expect={detail['expect']}, ok={detail['ok']}, tied={detail.get('tied', False)}, votes={detail.get('vote_counts') or {}}, repeats={detail.get('repeats') or 1}, reason={detail['reason'] or '-'}"
            )
    return "\n".join(lines).strip() + "\n"


def _write_partial(report: dict[str, Any]) -> Path:
    path = REPORT_DIR / "event-behavior-pairwise-latest.partial.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", default="", help="Run only one named case")
    parser.add_argument("--judge-repeats", type=int, default=1, help="Number of pairwise judge votes per comparison")
    args = parser.parse_args()

    preference_bank = _load_preference_bank()
    selected = _cases()
    if str(args.case or "").strip():
        selected = [case for case in selected if case["name"] == str(args.case).strip()]
        if not selected:
            raise SystemExit(f"unknown case: {args.case}")

    run_id = uuid.uuid4().hex[:8]
    report = {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "checks": [],
    }
    for case in selected:
        print(f"[event-pairwise] running {case['name']}")
        report["checks"].append(_case_record(case, run_id, preference_bank, judge_repeats=max(1, int(args.judge_repeats or 1))))
        partial = _write_partial(report)
        print(f"[event-pairwise] partial={partial}")

    ts = time.strftime("%Y%m%d-%H%M%S")
    json_path = REPORT_DIR / f"event-behavior-pairwise-{ts}-{run_id}.json"
    md_path = REPORT_DIR / f"event-behavior-pairwise-{ts}-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(f"[eval] event_behavior_pairwise_json={json_path}")
    print(f"[eval] event_behavior_pairwise_md={md_path}")


if __name__ == "__main__":
    main()
