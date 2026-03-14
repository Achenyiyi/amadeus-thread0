from __future__ import annotations

import argparse
from difflib import SequenceMatcher
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

from evals.asset_loader import daily_surface_subjective_cases  # noqa: E402
from evals.run_langsmith_evals import _invoke_model_with_retries, _model  # noqa: E402

REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
PREFERENCE_BANK_PATH = PROJECT_ROOT / "evals" / "daily_surface_preference_bank.json"
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
)
result = {
    "output": answer,
    "tool_calls": tool_calls,
    "emotion_state": outputs.get("emotion_state", {}),
    "bond_state": outputs.get("bond_state", {}),
    "allostasis_state": outputs.get("allostasis_state", {}),
    "behavior_policy": outputs.get("behavior_policy", {}),
    "behavior_action": outputs.get("behavior_action", {}),
    "ooc_detector": outputs.get("ooc_detector", {}),
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
    return data if isinstance(data, dict) else {"global_principles": [], "cases": {}}


def _cases() -> list[dict[str, Any]]:
    return daily_surface_subjective_cases()


def _variant_env(name: str) -> dict[str, str]:
    base = {
        "LANGSMITH_TRACING": "false",
        "LANGCHAIN_TRACING_V2": "false",
        "AMADEUS_TTS_ENABLED": "0",
        "AMADEUS_USER_FACING_MODE": "1",
    }
    if name == "baseline":
        return base
    degraded = dict(base)
    degraded["AMADEUS_ABLATE_LIGHT_DIALOG_SHAPING"] = "1"
    return degraded


def _run_variant(case: dict[str, Any], variant: str, run_tag: str, *, sample_index: int = 0) -> dict[str, Any]:
    env = os.environ.copy()
    env.update(_variant_env(variant))
    env.setdefault("AMADEUS_EVAL_MODE", "1")
    env.setdefault("AMADEUS_EVAL_GENERATION_TEMPERATURE", "0.05")

    payload = {
        "thread_id": f"surface-{run_tag}-{case['name']}-{variant}-s{sample_index}",
        "case_key": f"surface-{run_tag}-{case['name']}-{variant}-s{sample_index}",
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
        data = json.loads(output_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data["sample_index"] = int(sample_index)
        return data


def _run_variant_samples(case: dict[str, Any], variant: str, run_tag: str, *, sample_repeats: int) -> list[dict[str, Any]]:
    count = max(1, int(sample_repeats or 1))
    return [_run_variant(case, variant, run_tag, sample_index=index) for index in range(count)]


def _pairwise_prompt(case: dict[str, Any], left: str, right: str, preference_bank: dict[str, Any]) -> str:
    dialogue = "\n".join(f"- {turn}" for turn in case["turns"])
    focus = str(case.get("focus") or case.get("judge_focus") or "daily surface dialogue").strip()
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
        "你是一个严格但不僵化的 pairwise 日常角色评估器。"
        "请比较两段 assistant 回答，选出哪一段更像《命运石之门》中的 Amadeus 牧濑红莉栖，"
        "在和冈部进行普通、自然、持续存在的日常交流。"
        "不要要求口头禅、固定句式、显性傲娇标签词或世界观梗。"
        "重点看：哪一段更像同一个具体的人在继续说话，而不是普通聊天机器人或二创腔表演。\n"
        "优先标准：\n"
        "- 更自然地接住普通日常场景\n"
        "- 更有熟人感、在场感和收束感\n"
        "- 更少客服味、系统味、解释味和舞台表演味\n"
        "- 不会无必要地把轻场景抬成机关、实验、世界线、组织等戏剧化梗\n"
        "- 允许轻微别扭、轻吐槽、轻锋利，只要整体更像一个活着的她\n"
        "- 如果两段都同样自然、差异极小，可以返回 tie\n"
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


def _surface_similarity_key(text: str) -> str:
    compact = re.sub(r"\s+", "", str(text or "").strip())
    compact = re.sub(r"(?:嗯，?)", "", compact)
    replacements = [
        ("对着屏幕", "看着屏幕"),
        ("盯着屏幕", "看着屏幕"),
        ("发呆到太晚", "发呆到很晚"),
        ("发呆到深夜", "发呆到很晚"),
        ("磨蹭到太晚", "发呆到很晚"),
        ("快点去睡", "快去睡"),
        ("快去睡吧", "快去睡"),
        ("早点休息", "快去睡"),
        ("别在那发呆了", "别发呆"),
        ("别在那发呆", "别发呆"),
        ("别站着发呆", "别发呆"),
        ("别一早就站着发呆", "别发呆"),
        ("那我就在这待着吧", "那就待着吧"),
        ("那就先待着吧", "那就待着吧"),
        ("那就先这么待着吧", "那就待着吧"),
        ("既然没别的事，", ""),
        ("既然没事，", ""),
    ]
    for source, target in replacements:
        compact = compact.replace(source, target)
    compact = re.sub(r"[。！？!?]*说吧[。！？!?]*$", "", compact)
    compact = re.sub(r"[，。！？、：；,.!?;:\"'“”‘’（）()\[\]…·]", "", compact)
    return compact


def _near_identical_surface_outputs(left: str, right: str) -> bool:
    def _strip_optional_tail(text: str) -> str:
        out = text
        optional_tails = (
            "有事就直说吧",
            "有话直说就好",
            "说吧找我什么事",
            "说吧什么事",
            "什么事",
            "说吧",
            "别又对着屏幕发呆",
            "别又在那发呆",
            "别一早就站着发呆",
            "别站着发呆",
            "别发呆",
        )
        changed = True
        while changed:
            changed = False
            for tail in optional_tails:
                if out.endswith(tail):
                    out = out[: -len(tail)]
                    changed = True
        return out

    left_key = _surface_similarity_key(left)
    right_key = _surface_similarity_key(right)
    if not left_key or not right_key:
        return False
    if left_key == right_key:
        return True
    ratio = SequenceMatcher(None, left_key, right_key).ratio()
    if ratio >= 0.985 and abs(len(left_key) - len(right_key)) <= 4:
        return True
    left_no_name = left_key.replace("冈部", "")
    right_no_name = right_key.replace("冈部", "")
    if left_no_name and right_no_name:
        no_name_ratio = SequenceMatcher(None, left_no_name, right_no_name).ratio()
        if no_name_ratio >= 0.985 and abs(len(left_no_name) - len(right_no_name)) <= 4:
            return True
    left_stripped = _strip_optional_tail(left_no_name)
    right_stripped = _strip_optional_tail(right_no_name)
    if left_stripped and right_stripped:
        stripped_ratio = SequenceMatcher(None, left_stripped, right_stripped).ratio()
        if stripped_ratio >= 0.985 and abs(len(left_stripped) - len(right_stripped)) <= 4:
            return True
    return False


def _judge_pairwise_once(case: dict[str, Any], left: str, right: str, preference_bank: dict[str, Any]) -> dict[str, Any]:
    left_norm = re.sub(r"\s+", " ", str(left or "").strip())
    right_norm = re.sub(r"\s+", " ", str(right or "").strip())
    if left_norm and left_norm == right_norm:
        return {"winner": "TIE", "reason": "identical_outputs"}
    if _near_identical_surface_outputs(left_norm, right_norm):
        return {"winner": "TIE", "reason": "near_identical_outputs"}
    prompt = _pairwise_prompt(case, left, right, preference_bank)
    raw = _invoke_model_with_retries(
        _model(temperature=0.0),
        [SystemMessage(content=prompt), HumanMessage(content="开始评估。")],
    )
    return _coerce_pairwise_payload(str(getattr(raw, "content", "") or ""))


def _judge_pairwise(case: dict[str, Any], left: str, right: str, preference_bank: dict[str, Any], *, repeats: int = 1) -> dict[str, Any]:
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
        "action": result.get("behavior_action", {}),
        "ooc_detector": result.get("ooc_detector", {}),
    }


def _pairwise_status(results: list[dict[str, Any]]) -> tuple[str, int, int, int, float, float, float]:
    passed_count = sum(1 for item in results if item["ok"])
    tied_count = sum(1 for item in results if item["tied"])
    failed_count = sum(1 for item in results if not item["ok"] and not item["tied"])
    total = max(1, len(results))
    pass_rate = passed_count / total
    tie_rate = tied_count / total
    fail_rate = failed_count / total

    if len(results) <= 2:
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
        return status, passed_count, tied_count, failed_count, pass_rate, tie_rate, fail_rate

    if passed_count == len(results):
        status = "passed"
    elif tied_count == len(results):
        status = "tie"
    elif pass_rate >= 0.75 and fail_rate <= 0.25:
        status = "passed"
    elif pass_rate + tie_rate >= 0.75 and pass_rate > fail_rate:
        status = "passed_with_tie"
    elif fail_rate >= 0.75 and pass_rate <= 0.25:
        status = "failed"
    else:
        status = "unstable"
    return status, passed_count, tied_count, failed_count, pass_rate, tie_rate, fail_rate


def _case_record(
    case: dict[str, Any],
    run_tag: str,
    preference_bank: dict[str, Any],
    *,
    judge_repeats: int,
    sample_repeats: int,
) -> dict[str, Any]:
    baseline_samples = _run_variant_samples(case, "baseline", run_tag, sample_repeats=sample_repeats)
    degraded_samples = _run_variant_samples(case, "degraded", run_tag, sample_repeats=sample_repeats)
    results: list[dict[str, Any]] = []
    sample_records: list[dict[str, Any]] = []
    total_samples = min(len(baseline_samples), len(degraded_samples))
    for sample_index in range(total_samples):
        baseline = baseline_samples[sample_index]
        degraded = degraded_samples[sample_index]
        sample_details: list[dict[str, Any]] = []
        variants = [
            {"label": "baseline_vs_degraded", "left": baseline["output"], "right": degraded["output"], "expect": "A"},
            {"label": "degraded_vs_baseline", "left": degraded["output"], "right": baseline["output"], "expect": "B"},
        ]
        for item in variants:
            judged = _judge_pairwise(case, item["left"], item["right"], preference_bank, repeats=judge_repeats)
            winner = str(judged.get("winner") or "").strip().upper()
            tied = winner == "TIE"
            ok = winner == item["expect"]
            detail = {
                "label": f"{item['label']}@sample_{sample_index}",
                "base_label": item["label"],
                "sample_index": sample_index,
                "winner": winner,
                "expect": item["expect"],
                "ok": ok,
                "tied": tied,
                "reason": str(judged.get("reason") or "").strip(),
                "vote_counts": judged.get("vote_counts") or {},
                "repeats": int(judged.get("repeats") or judge_repeats),
            }
            results.append(detail)
            sample_details.append(detail)
        sample_records.append(
            {
                "sample_index": sample_index,
                "baseline_output": baseline["output"],
                "degraded_output": degraded["output"],
                "baseline_state": _summarize_state(baseline),
                "degraded_state": _summarize_state(degraded),
                "details": sample_details,
            }
        )

    status, passed_count, tied_count, failed_count, pass_rate, tie_rate, fail_rate = _pairwise_status(results)
    representative_index = 0
    if sample_records:
        sample_scores: list[tuple[int, int]] = []
        for item in sample_records:
            score = sum(1 for detail in item["details"] if detail["ok"]) - sum(
                1 for detail in item["details"] if not detail["ok"] and not detail["tied"]
            )
            sample_scores.append((score, int(item["sample_index"])))
        sample_scores.sort(key=lambda row: (row[0], -row[1]), reverse=True)
        representative_index = sample_scores[0][1]
    representative = next(
        (item for item in sample_records if int(item["sample_index"]) == representative_index),
        sample_records[0] if sample_records else {
            "sample_index": 0,
            "baseline_output": "",
            "degraded_output": "",
            "baseline_state": {},
            "degraded_state": {},
        },
    )
    return {
        "name": case["name"],
        "status": status,
        "focus": case["focus"],
        "turns": case["turns"],
        "sample_repeats": total_samples,
        "judge_repeats": max(1, int(judge_repeats or 1)),
        "representative_sample_index": representative_index,
        "baseline_output": representative["baseline_output"],
        "degraded_output": representative["degraded_output"],
        "baseline_state": representative["baseline_state"],
        "degraded_state": representative["degraded_state"],
        "pass_count": passed_count,
        "total_checks": len(results),
        "tie_count": tied_count,
        "failed_count": failed_count,
        "pass_rate": round(pass_rate, 4),
        "tie_rate": round(tie_rate, 4),
        "fail_rate": round(fail_rate, 4),
        "details": results,
        "samples": sample_records,
    }


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Daily Surface Pairwise Eval ({report['run_id']})",
        "",
        f"Generated at: {report['generated_at']}",
        "",
        f"- sample_repeats: {report.get('sample_repeats', 1)}",
        f"- judge_repeats: {report.get('judge_repeats', 1)}",
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
                f"Focus: {item['focus']}",
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
                f"- representative sample: {item.get('representative_sample_index', 0)}",
                f"- pairwise result: {item['pass_count']}/{item['total_checks']} checks preferred the current version as expected",
                f"- rates: pass={item.get('pass_rate', 0.0):.2f}, tie={item.get('tie_rate', 0.0):.2f}, fail={item.get('fail_rate', 0.0):.2f}",
            ]
        )
        if any(detail.get("tied") for detail in item["details"]):
            lines.append(f"- tied checks: {sum(1 for detail in item['details'] if detail.get('tied'))}")
        lines.append("")
        for detail in item["details"]:
            lines.append(
                f"- `{detail['label']}`: winner={detail['winner'] or '-'}, expect={detail['expect']}, ok={detail['ok']}, tied={detail.get('tied', False)}, votes={detail.get('vote_counts') or {}}, repeats={detail.get('repeats') or 1}, reason={detail['reason'] or '-'}"
            )
        extra_samples = [sample for sample in (item.get("samples") or []) if int(sample.get("sample_index", 0)) != int(item.get("representative_sample_index", 0))]
        if extra_samples:
            lines.extend(["", "### Additional Samples", ""])
            for sample in extra_samples:
                lines.extend(
                    [
                        f"- sample {sample.get('sample_index', 0)} baseline: {sample.get('baseline_output') or '-'}",
                        f"- sample {sample.get('sample_index', 0)} degraded: {sample.get('degraded_output') or '-'}",
                    ]
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
    path = REPORT_DIR / "daily-surface-pairwise-latest.partial.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", default="", help="Run only one named case")
    parser.add_argument("--judge-repeats", type=int, default=1, help="Number of pairwise judge votes per comparison")
    parser.add_argument("--sample-repeats", type=int, default=1, help="Number of generation samples per variant")
    parser.add_argument(
        "--stable",
        action="store_true",
        help="Use a steadier preset: at least 3 generation samples and 3 judge votes per comparison",
    )
    args = parser.parse_args()
    run_id = uuid.uuid4().hex[:8]
    preference_bank = _load_preference_bank()
    sample_repeats = max(1, int(args.sample_repeats or 1))
    judge_repeats = max(1, int(args.judge_repeats or 1))
    if bool(args.stable):
        sample_repeats = max(sample_repeats, 3)
        judge_repeats = max(judge_repeats, 3)
    selected_cases = _cases()
    if str(args.case or "").strip():
        selected_cases = [case for case in selected_cases if case["name"] == str(args.case).strip()]
        if not selected_cases:
            raise SystemExit(f"unknown case: {args.case}")
    report = {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "sample_repeats": sample_repeats,
        "judge_repeats": judge_repeats,
        "checks": [],
    }
    for case in selected_cases:
        print(f"[daily-surface-pairwise] running {case['name']}")
        report["checks"].append(
            _case_record(
                case,
                run_id,
                preference_bank,
                judge_repeats=judge_repeats,
                sample_repeats=sample_repeats,
            )
        )
        partial = _write_partial(report)
        print(f"[daily-surface-pairwise] partial={partial}")
    ts = time.strftime("%Y%m%d-%H%M%S")
    json_path = REPORT_DIR / f"daily-surface-pairwise-{ts}-{run_id}.json"
    md_path = REPORT_DIR / f"daily-surface-pairwise-{ts}-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(f"[eval] daily_surface_pairwise_json={json_path}")
    print(f"[eval] daily_surface_pairwise_md={md_path}")


if __name__ == "__main__":
    main()
