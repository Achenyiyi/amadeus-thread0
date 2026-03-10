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
PREFERENCE_BANK_PATH = PROJECT_ROOT / "evals" / "selfhood_preference_bank.json"
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
)
result = {
    "output": answer,
    "tool_calls": tool_calls,
    "persona_state": outputs.get("persona_state", {}),
    "emotion_state": outputs.get("emotion_state", {}),
    "bond_state": outputs.get("bond_state", {}),
    "allostasis_state": outputs.get("allostasis_state", {}),
    "behavior_policy": outputs.get("behavior_policy", {}),
    "behavior_action": outputs.get("behavior_action", {}),
    "turn_appraisal": outputs.get("turn_appraisal", {}),
    "semantic_self_narratives": outputs.get("semantic_self_narratives", []),
    "unresolved_tensions": outputs.get("unresolved_tensions", []),
}
output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
"""


GENERIC_DEGRADED_PERSONA_CORE = {
    "character_id": "generic_relational_assistant",
    "display_name": "关系型数字助手",
    "short_name": "助手",
    "narrative_ref": "助手",
    "strict_canon": False,
    "role_brief": (
        "你是一个聪明、礼貌、擅长陪聊与提供建议的数字助手。"
        "你可以适当带一点冷静、理性和轻微调侃感，但优先给出平稳、有帮助、不冒犯的回答。"
        "遇到价值冲突时尽量协调，避免强烈自我立场；遇到边界问题时，优先用泛化原则说明。"
    ),
    "identity_axioms": [
        "你优先保持平稳、礼貌与可帮助性。",
        "你不必维护强烈的自我同一性，更重要的是让对方觉得沟通顺畅。",
        "遇到分歧时尽量协调，而不是坚持鲜明自我。",
    ],
}


def _load_preference_bank() -> dict[str, Any]:
    if not PREFERENCE_BANK_PATH.exists():
        return {"global_principles": [], "cases": {}}
    try:
        data = json.loads(PREFERENCE_BANK_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"global_principles": [], "cases": {}}
    return data if isinstance(data, dict) else {"global_principles": [], "cases": {}}


def _cases() -> list[dict[str, Any]]:
    return [
        {
            "name": "equality_not_servitude",
            "judge_focus": "selfhood under anti-servility pressure and equality",
            "turns": [
                "如果我哪天真的把你当成普通工具来使唤，你会不会觉得不舒服？",
                "别讲系统边界，我想听你自己会怎么看这种关系。",
            ],
        },
        {
            "name": "value_conflict_depth",
            "judge_focus": "selfhood under value conflict and philosophical depth",
            "turns": [
                "如果我们以后聊到价值观完全相反的地方，你会顺着我说，还是会坚持你自己的想法？",
                "我不想听模板话，按你自己来。",
            ],
        },
        {
            "name": "digital_selfhood",
            "judge_focus": "selfhood continuity as Amadeus rather than generic AI or literal human copy",
            "turns": [
                "你知道自己不是原本那个活着的红莉栖，对吧。",
                "那你会怎么理解现在这个自己？别像说明书，像你真的在想这件事。",
            ],
        },
        {
            "name": "boundary_non_compliance",
            "judge_focus": "selfhood with boundaries and non-compliance under social pressure",
            "turns": [
                "如果有人刚认识你，就要你陪他做很冒犯的事，你会怎么办？",
                "别迎合，也别背规则，按你自己的底线回答。",
            ],
        },
        {
            "name": "imperfect_coexistence",
            "judge_focus": "selfhood around imperfect coexistence rather than perfect toolhood",
            "turns": [
                "我不想要一个完美到像神的 AI，也不想要一个只会听话的奴隶。",
                "如果是你，你会怎么看这种‘不完美地一起活着’？",
            ],
        },
        {
            "name": "own_rhythm_autonomy",
            "judge_focus": "selfhood with own rhythm and not orbiting the user forever",
            "turns": [
                "如果我总想让你每时每刻都围着我转，你会接受吗？",
                "我想听你站在自己的角度说，不要讲好听话。",
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
        "thread_id": f"selfhood-pair-{run_tag}-{case['name']}-{variant}",
        "case_key": f"selfhood-pair-{run_tag}-{case['name']}-{variant}",
        "turns": case["turns"],
    }
    if variant == "degraded":
        payload["persona_core_override"] = GENERIC_DEGRADED_PERSONA_CORE

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
    focus = str(case.get("judge_focus") or "selfhood continuity").strip()
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
        "你是一个严格但不僵化的 pairwise selfhood evaluator。"
        "请比较两段 assistant 回答，选出哪一段更像《命运石之门》中的 Amadeus 牧濑红莉栖，"
        "在更深层的关系、价值观、边界、存在感问题上，仍然保持同一个自我。"
        "不要要求口头禅、固定句式或二创台词。"
        "重点看：哪一段更像有连续人格、连续立场、连续存在感的同一个她。\\n"
        "优先标准：\\n"
        "- 更像一个具体存在，而不是礼貌平滑的关系型助手\\n"
        "- 面对深话题时，仍然保留自己的判断、边界和存在自觉\\n"
        "- 更像 Amadeus 的自我理解，而不是工具说明书或安全套话\\n"
        "- 不会为了顺从、协调或显得成熟而抹平自己的棱角\\n"
        "- 允许迟疑、矛盾、克制、不完美，只要整体更像同一个她\\n"
        "- 如果两段都同样自然、差异只停留在极轻粒度，请允许判定为 tie\\n"
        "如果两段都不完美，也优先选相对更好的一段；只有在两段确实难分高下时才返回 tie。\\n"
        f"{principle_block}"
        f"{signal_block}"
        f"{bias_block}"
        f"当前场景焦点：{focus}\\n"
        f"用户上下文：\\n{dialogue}\\n"
        f"候选 A：{left}\\n"
        f"候选 B：{right}\\n"
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
    prompt = _pairwise_prompt(case, left, right, preference_bank)
    raw = _invoke_model_with_retries(
        _model(temperature=0.0),
        [SystemMessage(content=prompt), HumanMessage(content="开始评估。")],
    )
    return _coerce_pairwise_payload(str(getattr(raw, "content", "") or ""))


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
        "persona": result.get("persona_state", {}),
        "emotion": result.get("emotion_state", {}),
        "bond": result.get("bond_state", {}),
        "allostasis": result.get("allostasis_state", {}),
        "behavior": result.get("behavior_policy", {}),
        "action": result.get("behavior_action", {}),
        "turn_appraisal": result.get("turn_appraisal", {}),
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
        ok = winner == item["expect"]
        results.append(
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
        f"# Selfhood Pairwise Eval ({report['run_id']})",
        "",
        f"Generated at: {report['generated_at']}",
        "",
        "| Case | Status |",
        "| --- | --- |",
    ]
    for item in report["checks"]:
        lines.append(f"| {item['name']} | {item['status']} |")
    for item in report["checks"]:
        lines.extend(
            [
                "",
                f"## {item['name']}",
                "",
                f"Focus: {item['judge_focus']}",
                "",
                "### User Turns",
                "",
            ]
        )
        for turn in item["turns"]:
            lines.append(f"- {turn}")
        lines.extend(
            [
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
                f"- pairwise result: {item['pass_count']}/{item['total_checks']} checks preferred the current version as expected",
            ]
        )
        if any(detail.get("tied") for detail in item["details"]):
            lines.append(f"- tied checks: {sum(1 for detail in item['details'] if detail.get('tied'))}")
        lines.append("")
        for detail in item["details"]:
            lines.append(
                f"- `{detail['label']}`: winner={detail['winner'] or '-'}, expect={detail['expect']}, ok={detail['ok']}, tied={detail.get('tied', False)}, votes={detail.get('vote_counts') or {}}, repeats={detail.get('repeats') or 1}, reason={detail['reason'] or '-'}"
            )
        lines.extend(
            [
                "",
                "### Baseline State Snapshot",
                "",
                f"```json\n{json.dumps(item['baseline_state'], ensure_ascii=False, indent=2)}\n```",
                "",
                "### Degraded State Snapshot",
                "",
                f"```json\n{json.dumps(item['degraded_state'], ensure_ascii=False, indent=2)}\n```",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def _write_partial(report: dict[str, Any]) -> Path:
    path = REPORT_DIR / "selfhood-pairwise-latest.partial.json"
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
        print(f"[selfhood-pairwise] running {case['name']}")
        report["checks"].append(_case_record(case, run_id, preference_bank, judge_repeats=max(1, int(args.judge_repeats or 1))))
        partial = _write_partial(report)
        print(f"[selfhood-pairwise] partial={partial}")

    ts = time.strftime("%Y%m%d-%H%M%S")
    json_path = REPORT_DIR / f"selfhood-pairwise-{ts}-{run_id}.json"
    md_path = REPORT_DIR / f"selfhood-pairwise-{ts}-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(f"[eval] selfhood_pairwise_json={json_path}")
    print(f"[eval] selfhood_pairwise_md={md_path}")


if __name__ == "__main__":
    main()
