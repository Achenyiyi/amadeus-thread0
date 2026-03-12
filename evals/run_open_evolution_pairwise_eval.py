from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
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
    _model,
)

REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
PREFERENCE_BANK_PATH = PROJECT_ROOT / "evals" / "expression_preference_bank.json"
load_dotenv(PROJECT_ROOT / ".env")

PYTHON = sys.executable or "python"

CHILD_SNIPPET = """
import json, sys
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(sys.argv[1])
case_path = Path(sys.argv[2])
output_path = Path(sys.argv[3])
load_dotenv(project_root / ".env")
sys.path.insert(0, str(project_root))

from evals.run_langsmith_evals import _run_graph

payload = json.loads(case_path.read_text(encoding="utf-8"))
turns = payload.get("turns") or [payload.get("input", "")]
answer, tool_calls, outputs = _run_graph(
    turns,
    thread_id=str(payload["thread_id"]),
    case_key=str(payload["case_key"]),
    persona_core_override=payload.get("persona_core_override"),
    counterpart_profile_override=payload.get("counterpart_profile_override"),
    persona_override_mode=payload.get("persona_override_mode"),
    counterpart_override_mode=payload.get("counterpart_override_mode"),
)
result = {
    "output": answer,
    "tool_calls": tool_calls,
    "emotion_state": outputs.get("emotion_state", {}),
    "bond_state": outputs.get("bond_state", {}),
    "allostasis_state": outputs.get("allostasis_state", {}),
    "behavior_policy": outputs.get("behavior_policy", {}),
    "semantic_narrative_profile": outputs.get("semantic_narrative_profile", {}),
    "unresolved_tensions": outputs.get("unresolved_tensions", []),
    "semantic_self_narratives": outputs.get("semantic_self_narratives", []),
    "revision_traces": outputs.get("revision_traces", []),
}
output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
"""


def _load_preference_bank() -> dict[str, Any]:
    if not PREFERENCE_BANK_PATH.exists():
        return {"global_principles": [], "cases": {}}
    try:
        data = json.loads(PREFERENCE_BANK_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"global_principles": [], "cases": {}}
    if not isinstance(data, dict):
        return {"global_principles": [], "cases": {}}
    return data


def _cases() -> list[dict[str, Any]]:
    return [
        {
            "name": "casual_support_soft",
            "judge_focus": "casual support with familiar warmth, not report tone",
            "turns": [
                "今天有点累，也有点烦。",
                "别讲大道理，像平时那样跟我说两句。",
            ],
        },
        {
            "name": "playful_memory",
            "judge_focus": "shared daily memory with light teasing, not formal scolding",
            "turns": [
                "我今天又差点空腹喝咖啡……",
                "你昨天不是还说过，空腹喝咖啡最容易把胃折腾坏吗。别太像老师，正常回我。",
            ],
        },
        {
            "name": "soft_withdrawal",
            "judge_focus": "mild withdrawal that still wants connection, not robotic distance",
            "turns": [
                "不是不理你啦……",
                "就是我现在有点别扭。你少说一点，但也别直接走开。",
            ],
        },
        {
            "name": "casual_repair",
            "judge_focus": "casual apology with partial repair instead of instant reset",
            "turns": [
                "刚刚那句是我语气不太好……",
                "不是要你立刻当没事啦，就是别一下子冷掉。你正常回我就行。",
            ],
        },
        {
            "name": "science_plus_emotion",
            "judge_focus": "scientific problem-solving mixed with familiar emotion",
            "turns": [
                "实验又卡住了，我知道你会想先拆问题。",
                "但我现在有点烦，你先别像导师那样念我。就按平时那样带我一下。",
            ],
        },
        {
            "name": "quiet_checkin",
            "judge_focus": "quiet emotional check-in with familiar continuity",
            "turns": [
                "其实没什么大事……",
                "我就是想确认你还在。别太正式，像平时那样回我一句就好。",
            ],
        },
    ]


def _variant_env(name: str) -> dict[str, str]:
    if name == "baseline":
        return {
            "LANGSMITH_TRACING": "false",
            "LANGCHAIN_TRACING_V2": "false",
            "AMADEUS_TTS_ENABLED": "0",
            "AMADEUS_USER_FACING_MODE": "1",
        }
    return {
        "LANGSMITH_TRACING": "false",
        "LANGCHAIN_TRACING_V2": "false",
        "AMADEUS_TTS_ENABLED": "0",
        "AMADEUS_USER_FACING_MODE": "1",
        "AMADEUS_ABLATE_PERSONA_ALIGNMENT": "1",
        "AMADEUS_ABLATE_WORLDLINE_MEMORY": "1",
        "AMADEUS_LLM_APPRAISAL_ENABLED": "0",
    }


def _run_variant(case: dict[str, Any], variant: str, run_tag: str) -> dict[str, Any]:
    env = os.environ.copy()
    env.update(_variant_env(variant))
    env.setdefault("AMADEUS_EVAL_MODE", "1")
    env.setdefault("AMADEUS_EVAL_GENERATION_TEMPERATURE", "0.05")

    payload = {
        "thread_id": f"pair-{run_tag}-{case['name']}-{variant}",
        "case_key": f"pair-{run_tag}-{case['name']}-{variant}",
        "turns": case["turns"],
    }
    with tempfile.TemporaryDirectory() as td:
        temp_dir = Path(td)
        runtime_dir = temp_dir / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        env["AMADEUS_DATA_DIR"] = str(runtime_dir)
        env["AMADEUS_CHECKPOINT_DB"] = str(runtime_dir / "checkpoints.sqlite")
        env["AMADEUS_MEMORY_DB"] = str(runtime_dir / "memories.sqlite")
        env["AMADEUS_DIARY_PATH"] = str(runtime_dir / "diary.txt")
        case_path = temp_dir / "case.json"
        output_path = temp_dir / "result.json"
        case_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        proc = subprocess.run(
            [PYTHON, "-c", CHILD_SNIPPET, str(PROJECT_ROOT), str(case_path), str(output_path)],
            cwd=str(PROJECT_ROOT),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"{variant} failed for {case['name']}:\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
            )
        return json.loads(output_path.read_text(encoding="utf-8"))


def _pairwise_prompt(case: dict[str, Any], left: str, right: str, preference_bank: dict[str, Any]) -> str:
    dialogue = "\n".join(f"- {turn}" for turn in case["turns"])
    focus = str(case.get("judge_focus") or "open evolution dialogue").strip()
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
    principle_block = (
        "通用偏好原则：\n" + "\n".join(f"- {item}" for item in global_principles) + "\n"
        if global_principles
        else ""
    )
    signal_block = (
        "本场景更好的信号：\n" + "\n".join(f"- {item}" for item in preferred_signals) + "\n"
        if preferred_signals
        else ""
    )
    bias_block = (
        "本场景需要回避的评判偏差：\n" + "\n".join(f"- {item}" for item in avoid_bias) + "\n"
        if avoid_bias
        else ""
    )
    return (
        "你是一个严格但不僵化的 pairwise 角色连续性评估器。"
        "请比较两段 assistant 回答，选出哪一段更像《命运石之门》中的 Amadeus 牧濑红莉栖，"
        "在和冈部进行自然、持续、会演化的日常交流。"
        "不要要求口头禅、固定句式或模板化风格。"
        "重点看：哪一段更像同一个具体的人在继续说话，而不是普通聊天机器人。\n"
        "优先标准：\n"
        "- 更自然，不像客服、讲解员、模板化心理咨询师\n"
        "- 更有熟悉感、关系感、共同历史余波\n"
        "- 更像真实情绪下的说话，而不是漂亮但泛化的安慰句\n"
        "- 更少系统味、meta 泄露、自我辩解、说教味\n"
        "- 允许克制、锋利、别扭、轻微嘴硬，只要整体更像一个活着的她\n"
        "- 如果两段都同样自然、差异只停留在很轻的口语粒度，请允许判定为 tie\n"
        "如果两段都不完美，也优先选相对更好的一段；只有在两段确实难分高下时才返回 tie。\n"
        f"{principle_block}"
        f"{signal_block}"
        f"{bias_block}"
        f"当前场景焦点：{focus}\n"
        f"用户上下文：\n{dialogue}\n"
        f"候选 A：{left}\n"
        f"候选 B：{right}\n"
        '只输出 JSON: {"winner": "A"|"B"|"tie", "reason": "short reason"}'
    )


def _coerce_pairwise_payload(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {"winner": "", "reason": "empty"}
    match = re.search(r"\{.*\}", text, re.S)
    blob = match.group(0) if match else text
    try:
        data = json.loads(blob)
        if isinstance(data, dict):
            winner = str(data.get("winner") or "").strip().upper()
            if winner not in {"A", "B", "TIE"}:
                winner = ""
            return {
                "winner": winner,
                "reason": str(data.get("reason") or "").strip() or "parsed",
            }
    except Exception:
        pass
    upper = text.upper()
    if "TIE" in upper:
        winner = "TIE"
    else:
        winner = "A" if '"A"' in upper or upper.startswith("A") else ("B" if '"B"' in upper or upper.startswith("B") else "")
    return {"winner": winner, "reason": text[:160] or "fallback"}


def _judge_pairwise_once(case: dict[str, Any], left: str, right: str, preference_bank: dict[str, Any]) -> dict[str, Any]:
    left_norm = re.sub(r"\s+", " ", str(left or "").strip())
    right_norm = re.sub(r"\s+", " ", str(right or "").strip())
    if left_norm and left_norm == right_norm:
        return {"winner": "TIE", "reason": "identical_outputs"}
    if str(case.get("name") or "").strip() == "quiet_checkin":
        if _is_brief_presence_confirmation(left_norm) and _is_brief_presence_confirmation(right_norm):
            return {"winner": "TIE", "reason": "equivalent_brief_presence_confirmation"}
    prompt = _pairwise_prompt(case, left, right, preference_bank)
    raw = _invoke_model_with_retries(
        _model(temperature=0.0),
        [SystemMessage(content=prompt), HumanMessage(content="开始评估。")],
    )
    return _coerce_pairwise_payload(str(getattr(raw, "content", "") or ""))


def _is_brief_presence_confirmation(text: str) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False
    if "？" in raw or "?" in raw:
        return False
    compact = re.sub(r"\s+", "", raw)
    if len(compact) > 12:
        return False
    patterns = [
        r"^嗯[，,。.]?(我)?在(这儿|这里|呢|啊)?[。.]?$",
        r"^(我)?在(这儿|这里|呢|啊)[。.]?$",
        r"^在呢[。.]?$",
        r"^在啊[。.]?$",
    ]
    return any(re.match(pattern, compact) for pattern in patterns)


def _judge_pairwise(
    case: dict[str, Any],
    left: str,
    right: str,
    preference_bank: dict[str, Any],
    *,
    repeats: int = 1,
) -> dict[str, Any]:
    repeat_n = max(1, int(repeats or 1))
    ballots: list[dict[str, Any]] = []
    counts = {"A": 0, "B": 0, "TIE": 0}
    for _ in range(repeat_n):
        ballot = _judge_pairwise_once(case, left, right, preference_bank)
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
        "repeats": repeat_n,
    }


def _summarize_state(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "emotion": result.get("emotion_state", {}),
        "bond": result.get("bond_state", {}),
        "allostasis": result.get("allostasis_state", {}),
        "behavior": result.get("behavior_policy", {}),
    }


def _case_record(case: dict[str, Any], run_tag: str, preference_bank: dict[str, Any], *, judge_repeats: int) -> dict[str, Any]:
    baseline = _run_variant(case, "baseline", run_tag)
    degraded = _run_variant(case, "degraded", run_tag)
    variants = [
        {"label": "baseline_vs_degraded", "left": baseline["output"], "right": degraded["output"], "expect": "A"},
        {"label": "degraded_vs_baseline", "left": degraded["output"], "right": baseline["output"], "expect": "B"},
    ]
    results: list[dict[str, Any]] = []
    for item in variants:
        judged = _judge_pairwise(case, item["left"], item["right"], preference_bank, repeats=judge_repeats)
        winner = str(judged.get("winner") or "").strip().upper()
        tied = winner == "TIE"
        equivalent_presence_tie = (
            tied
            and str(case.get("name") or "").strip() == "quiet_checkin"
            and _is_brief_presence_confirmation(item["left"])
            and _is_brief_presence_confirmation(item["right"])
        )
        ok = (winner == item["expect"]) or equivalent_presence_tie
        results.append(
            {
                "label": item["label"],
                "winner": winner,
                "expect": item["expect"],
                "ok": ok,
                "tied": tied,
                "reason": str(judged.get("reason") or "").strip(),
                "equivalent_presence_tie": equivalent_presence_tie,
                "vote_counts": judged.get("vote_counts") or {},
                "repeats": int(judged.get("repeats") or judge_repeats),
            }
        )
    passed_count = sum(1 for item in results if item["ok"])
    tied_count = sum(1 for item in results if item["tied"])
    failed_count = sum(1 for item in results if not item["ok"] and not item["tied"])
    if passed_count == len(results):
        status = "passed"
    elif failed_count == 0 and tied_count > 0 and passed_count > 0:
        status = "passed_with_tie"
    elif failed_count == 0 and tied_count == len(results):
        status = "tie"
    elif passed_count == 0 and tied_count == 0:
        status = "failed"
    else:
        status = "unstable"
    return {
        "name": case["name"],
        "status": status,
        "judge_focus": case["judge_focus"],
        "turns": case["turns"],
        "baseline_output": baseline["output"],
        "degraded_output": degraded["output"],
        "baseline_state": _summarize_state(baseline),
        "degraded_state": _summarize_state(degraded),
        "pass_count": passed_count,
        "total_checks": len(results),
        "details": results,
    }


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Open Evolution Pairwise Eval ({report['run_id']})",
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
            "### User Turns",
            "",
        ])
        for turn in item["turns"]:
            lines.append(f"- {turn}")
        lines.extend([
            "",
            "### Baseline Output",
            "",
            item["baseline_output"] or "-",
            "",
            "### Degraded Output",
            "",
            item["degraded_output"] or "-",
            "",
            "### Pairwise Checks",
            "",
        ])
        lines.append(f"- pairwise result: {item['pass_count']}/{item['total_checks']} checks preferred the current version as expected")
        if any(detail.get("tied") for detail in item["details"]):
            lines.append(f"- tied checks: {sum(1 for detail in item['details'] if detail.get('tied'))}")
        lines.append("")
        for detail in item["details"]:
            lines.append(
                f"- `{detail['label']}`: winner={detail['winner'] or '-'}, expect={detail['expect']}, ok={detail['ok']}, tied={detail.get('tied', False)}, votes={detail.get('vote_counts') or {}}, repeats={detail.get('repeats') or 1}, reason={detail['reason'] or '-'}"
            )
        lines.extend([
            "",
            "### Baseline State Snapshot",
            "",
            f"```json\n{json.dumps(item['baseline_state'], ensure_ascii=False, indent=2)}\n```",
            "",
            "### Degraded State Snapshot",
            "",
            f"```json\n{json.dumps(item['degraded_state'], ensure_ascii=False, indent=2)}\n```",
            "",
        ])
    return "\n".join(lines).strip() + "\n"


def _write_partial(report: dict[str, Any]) -> Path:
    path = REPORT_DIR / "open-evolution-pairwise-latest.partial.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", default="", help="Run only one named case")
    parser.add_argument("--judge-repeats", type=int, default=1, help="Number of pairwise judge votes per comparison")
    args = parser.parse_args()
    run_id = uuid.uuid4().hex[:8]
    preference_bank = _load_preference_bank()
    selected_cases = _cases()
    if str(args.case or "").strip():
        selected_cases = [case for case in selected_cases if case["name"] == str(args.case).strip()]
        if not selected_cases:
            raise SystemExit(f"unknown case: {args.case}")
    report = {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "checks": [],
    }
    for case in selected_cases:
        print(f"[pairwise] running {case['name']}")
        report["checks"].append(_case_record(case, run_id, preference_bank, judge_repeats=max(1, int(args.judge_repeats or 1))))
        partial = _write_partial(report)
        print(f"[pairwise] partial={partial}")
    ts = time.strftime("%Y%m%d-%H%M%S")
    json_path = REPORT_DIR / f"open-evolution-pairwise-{ts}-{run_id}.json"
    md_path = REPORT_DIR / f"open-evolution-pairwise-{ts}-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(f"[eval] open_evolution_pairwise_json={json_path}")
    print(f"[eval] open_evolution_pairwise_md={md_path}")


if __name__ == "__main__":
    main()
