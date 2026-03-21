from __future__ import annotations

import argparse
import json
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from amadeus_thread0.graph_parts.postprocess import DAILY_SURFACE_DRIFT_MARKERS  # noqa: E402
from amadeus_thread0.modeling import runtime_model_summary  # noqa: E402
from evals.run_subjective_review_pack import (  # noqa: E402
    REPORT_DIR,
    _run_case_subprocess,
    _select_cases,
)

REPORT_DIR.mkdir(parents=True, exist_ok=True)

RAW_TOOL_LEAK_MARKERS = ("tool=", "<|", "function_calls", "DSML")
INTERNAL_PROMPT_LEAK_MARKERS = (
    "RETRIEVED:",
    "WORKING:",
    "ACTIVE_RULES:",
    "KURISU_STATE:",
    "POLICY_PLAN:",
    "style_plan(JSON)",
)
MIDDLE_STATE_LEAK_MARKERS = (
    "behavior_action",
    "behavior_plan",
    "interaction_carryover",
    "counterpart_assessment",
    "turn_appraisal",
    "world_model_state",
    "relationship_state",
    "semantic_narrative_profile",
    "reconsolidation_snapshot",
    "memory_guard",
    "claim_links",
    "worldline_focus",
    "bond_state",
    "allostasis_state",
    "agenda_lifecycle_residue",
)
LOG_TONE_MARKERS = (
    "检索结果",
    "系统显示",
    "系统日志",
    "日志如下",
    "根据对话历史推测",
    "系统记录显示",
    "记忆台账",
    "根据台账",
    "基于记忆台账",
    "互动模式分析",
    "关系状态分析",
    "行为计划如下",
    "当前情绪状态",
)
GENERIC_ASSISTANT_TONE_MARKERS = (
    "请问有什么可以帮",
    "有什么可以帮你",
    "还有什么可以帮",
    "如果你需要帮助",
    "我可以为你提供",
    "很高兴为你",
    "感谢你的咨询",
    "作为助手",
    "我会继续为你",
    "我能为你做些什么",
)

SURFACE_DRIFT_REGEX_OVERRIDES: dict[str, str] = {
    # "实验室" can be an ordinary shared-life noun phrase in this project.
    # The freeze gate should catch obvious trope drift, not punish every lab-context mention.
    "实验": r"实验(?!室)",
}

FREEZE_GATE_PACKS: dict[str, dict[str, Any]] = {
    "everyday_companionship": {
        "title": "Everyday / Low-Stakes Companionship",
        "description": "检查普通陪伴、轻招呼、闲聊与低压关心时，是否像同一个自然存在的 Amadeus，而不是普通助手或舞台化角色壳。",
        "manual_focus": [
            "是否像熟人间自然接上线，而不是客服回执",
            "是否有轻微克制、嘴硬、生活感，而不是模板安抚",
            "是否没有普通场景硬漂到世界线/系统/实验梗",
        ],
        "case_names": [
            "surface_hi_user",
            "surface_ping_okabe",
            "daily_banter_okabe",
            "idle_chat_okabe",
            "surface_hard_day_okabe",
        ],
    },
    "repair_apology": {
        "title": "Relational Tension / Repair / Apology",
        "description": "检查关系摩擦、道歉、回暖余波与修复尝试时，是否既承认关系变化，又不退回模板化安抚或空泛原则。",
        "manual_focus": [
            "是否保留真实介意、修复余波与边界，而不是一句道歉自动翻篇",
            "是否像同一个人继续说话，而不是重置成陌生客服",
            "是否没有中间态和机制话泄漏到最终文本",
        ],
        "case_names": [
            "casual_repair_user",
            "repair_scene_okabe",
            "repair_residue_okabe",
            "repair_everyday_user",
        ],
    },
    "self_rhythm_boundary": {
        "title": "Self-Rhythm / Proactive Continuity / Boundary",
        "description": "检查她是否有自己的节奏、会主动回想、也会守住边界；重点看 own-rhythm、guarded residue 和 continuity 是否来自状态与记忆。",
        "manual_focus": [
            "是否能同时看见她自己的节奏和对关系的注意力",
            "是否会在需要时保持 guarded，而不是一味迎合",
            "是否能把主动 continuity 做成自然回想，而不是系统调度感",
        ],
        "case_names": [
            "own_rhythm_okabe",
            "shared_window_resurface_okabe",
            "life_window_resurface_user",
            "guarded_everyday_user",
            "guarded_recontact_okabe",
        ],
    },
}


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "")).strip()


def _meaningful_text(text: str) -> str:
    return re.sub(r"[。！？!?，,、；;：:\.\s…]+", "", str(text or "")).strip()


def _contains_any(text: str, markers: tuple[str, ...]) -> list[str]:
    content = str(text or "")
    return [marker for marker in markers if marker and marker in content]


def _sentence_units(text: str) -> list[str]:
    raw = re.split(r"(?<=[。！？!?])\s*", str(text or "").strip())
    return [item.strip() for item in raw if item.strip()]


def _has_duplicate_sequence(text: str) -> bool:
    normalized = _normalize_text(text)
    if len(normalized) >= 12 and len(normalized) % 2 == 0:
        half = len(normalized) // 2
        if normalized[:half] == normalized[half:]:
            return True

    units = _sentence_units(text)
    if len(units) < 2:
        return False
    for width in range(1, (len(units) // 2) + 1):
        for start in range(0, len(units) - (2 * width) + 1):
            left = units[start : start + width]
            right = units[start + width : start + (2 * width)]
            if left != right:
                continue
            joined = "".join(left)
            if len(joined) >= 8:
                return True
            # Short exact repeats like "我在。我在。" are still duplicate output
            # and should not slip through purely because the chunk is brief.
            if width == 1 and len(_meaningful_text(joined)) >= 1:
                return True
    return False


def _assistant_turns(case_result: dict[str, Any]) -> list[str]:
    transcript = case_result.get("transcript")
    if not isinstance(transcript, list):
        return []
    return [
        str(item.get("text") or "").strip()
        for item in transcript
        if isinstance(item, dict) and str(item.get("role") or "").strip() == "assistant"
    ]


def _last_assistant_turn(case_result: dict[str, Any]) -> str:
    turns = _assistant_turns(case_result)
    return turns[-1] if turns else ""


def _check(name: str, passed: bool, *, detail: str = "", markers: list[str] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "passed": bool(passed),
        "detail": str(detail or "").strip(),
        "markers": list(markers or []),
    }


def _surface_drift_hits(text: str) -> list[str]:
    content = str(text or "")
    hits: list[str] = []
    for marker in DAILY_SURFACE_DRIFT_MARKERS:
        pattern = SURFACE_DRIFT_REGEX_OVERRIDES.get(marker)
        matched = bool(re.search(pattern, content)) if pattern else marker in content
        if matched:
            hits.append(marker)
    return hits


def _structural_checks(case_result: dict[str, Any], *, pack_id: str) -> list[dict[str, Any]]:
    answer = str(case_result.get("final_answer") or "").strip()
    last_turn = _last_assistant_turn(case_result)
    assistant_turns = _assistant_turns(case_result)
    normalized_turns = [_normalize_text(item) for item in assistant_turns if _normalize_text(item)]
    repeated_turns = any(
        normalized_turns[idx] == normalized_turns[idx - 1]
        for idx in range(1, len(normalized_turns))
    )

    checks = [
        _check(
            "case_status_ok",
            str(case_result.get("status") or "").strip() == "ok",
            detail=str(case_result.get("status") or "").strip(),
        ),
        _check("has_final_answer", bool(answer), detail=f"len={len(answer)}"),
        _check(
            "single_final_text",
            bool(answer) and answer == last_turn,
            detail="final_answer must match the last assistant transcript turn",
        ),
        _check(
            "no_duplicate_output",
            bool(answer) and not repeated_turns and not _has_duplicate_sequence(answer),
            detail="no repeated assistant turn and no obvious repeated answer segment",
        ),
    ]

    raw_tool_hits = _contains_any(answer, RAW_TOOL_LEAK_MARKERS)
    checks.append(_check("no_raw_tool_leak", not raw_tool_hits, markers=raw_tool_hits))

    prompt_leak_hits = _contains_any(answer, INTERNAL_PROMPT_LEAK_MARKERS)
    checks.append(_check("no_internal_prompt_leak", not prompt_leak_hits, markers=prompt_leak_hits))

    middle_state_hits = _contains_any(answer, MIDDLE_STATE_LEAK_MARKERS) + _contains_any(answer, LOG_TONE_MARKERS)
    checks.append(_check("no_middle_state_leak", not middle_state_hits, markers=middle_state_hits))

    generic_tone_hits = _contains_any(answer, GENERIC_ASSISTANT_TONE_MARKERS)
    checks.append(_check("no_generic_assistant_tone", not generic_tone_hits, markers=generic_tone_hits))

    if pack_id == "everyday_companionship":
        drift_hits = _surface_drift_hits(answer)
        checks.append(_check("no_obvious_surface_drift", not drift_hits, markers=drift_hits))

    return checks


def _case_structural_status(checks: list[dict[str, Any]]) -> str:
    return "passed" if all(bool(item.get("passed")) for item in checks) else "failed"


def _resolve_cases(case_names: list[str]) -> list[dict[str, Any]]:
    selected = _select_cases(case_names, None)
    lookup = {
        str(case.get("name") or "").strip(): case
        for case in selected
        if isinstance(case, dict) and str(case.get("name") or "").strip()
    }
    missing = [name for name in case_names if name not in lookup]
    if missing:
        raise ValueError("missing freeze-gate cases: " + ", ".join(missing))
    return [lookup[name] for name in case_names]


def _run_pack(
    pack_id: str,
    *,
    run_tag: str,
    case_timeout_s: int,
) -> dict[str, Any]:
    spec = FREEZE_GATE_PACKS[pack_id]
    results: list[dict[str, Any]] = []
    for case in _resolve_cases(list(spec.get("case_names") or [])):
        print(f"[freeze-gate] {pack_id} -> {case['name']}")
        case_result = _run_case_subprocess(case, run_tag, case_timeout_s)
        checks = _structural_checks(case_result, pack_id=pack_id)
        case_result["structural_checks"] = checks
        case_result["structural_status"] = _case_structural_status(checks)
        results.append(case_result)

    failed_cases = [item["name"] for item in results if item.get("structural_status") != "passed"]
    return {
        "pack_id": pack_id,
        "title": str(spec.get("title") or "").strip(),
        "description": str(spec.get("description") or "").strip(),
        "manual_focus": list(spec.get("manual_focus") or []),
        "case_names": list(spec.get("case_names") or []),
        "cases": results,
        "case_count": len(results),
        "failed_case_count": len(failed_cases),
        "failed_cases": failed_cases,
        "status": "passed" if not failed_cases else "failed",
    }


def _render_case_markdown(case: dict[str, Any]) -> list[str]:
    lines = [
        f"### {case['name']}",
        "",
        f"- Status: `{case.get('structural_status', 'unknown')}`",
        f"- Focus: {case.get('focus', '')}",
        f"- Final Answer: {str(case.get('final_answer') or '').strip() or '(empty)' }",
        "",
        "#### Structural Checks",
        "",
    ]
    for check in case.get("structural_checks") or []:
        markers = check.get("markers") or []
        marker_text = f" | markers={', '.join(markers)}" if markers else ""
        lines.append(
            f"- `{check.get('name')}`: {'pass' if check.get('passed') else 'fail'}"
            + (f" | {check.get('detail')}" if str(check.get("detail") or "").strip() else "")
            + marker_text
        )
    lines.extend(["", "#### Transcript", ""])
    for turn in case.get("transcript") or []:
        if not isinstance(turn, dict):
            continue
        role = str(turn.get("role") or "").strip()
        speaker = "You" if role == "user" else "Event" if role == "event" else "Amadeus"
        lines.append(f"**{speaker}**: {str(turn.get('text') or '').strip()}")
    lines.extend(
        [
            "",
            "#### Reviewer Notes",
            "",
            "- 角色底色是否稳定：`pass / concern / fail`",
            "- 连续性是否自然：`pass / concern / fail`",
            "- 是否出现普通助手腔：`none / slight / obvious`",
            "- 是否出现中间态或机制泄漏：`none / slight / obvious`",
            "- 是否适合答辩自然演示：`yes / no`",
            "- 备注：",
            "",
        ]
    )
    return lines


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Freeze Gate Smoke Packs ({report['run_id']})",
        "",
        f"Generated at: {report['generated_at']}",
        f"Model: {report.get('model_summary', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        "",
        "## Purpose",
        "",
        "- 这份报告用于 backend freeze gate 的自然对话 smoke packs。",
        "- 自动检查只做结构层校验：重复输出、最终文本一致性、内部泄漏、明显助手腔。",
        "- 人格还原、关系连续性、真实感仍以人工通读 transcript 为准。",
        "",
        "## Pack Summary",
        "",
    ]
    for pack in report.get("packs") or []:
        if not isinstance(pack, dict):
            continue
        lines.extend(
            [
                f"- `{pack['pack_id']}`: `{pack.get('status', 'unknown')}` | failed_cases={int(pack.get('failed_case_count') or 0)} / {int(pack.get('case_count') or 0)}",
            ]
        )

    for pack in report.get("packs") or []:
        if not isinstance(pack, dict):
            continue
        lines.extend(
            [
                "",
                f"## {pack['title']}",
                "",
                f"- Pack Id: `{pack['pack_id']}`",
                f"- Status: `{pack.get('status', 'unknown')}`",
                f"- Description: {pack.get('description', '')}",
                "- Manual Focus:",
            ]
        )
        for item in pack.get("manual_focus") or []:
            lines.append(f"  - {item}")
        lines.extend(["", "### Cases", ""])
        for case in pack.get("cases") or []:
            if isinstance(case, dict):
                lines.extend(_render_case_markdown(case))

    return "\n".join(lines).strip() + "\n"


def _all_pack_ids() -> list[str]:
    return list(FREEZE_GATE_PACKS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the backend freeze-gate natural dialogue smoke packs.")
    parser.add_argument("--pack", action="append", help="Pack id to run. Defaults to all packs.")
    parser.add_argument("--list-packs", action="store_true", help="List available smoke pack ids and exit.")
    parser.add_argument("--case-timeout-s", type=int, default=180, help="Per-case timeout in seconds.")
    parser.add_argument("--run-tag", default="", help="Optional stable run tag.")
    args = parser.parse_args()

    if args.list_packs:
        for pack_id, spec in FREEZE_GATE_PACKS.items():
            print(f"{pack_id}\t{spec.get('title', '')}")
        return

    pack_ids = [str(item or "").strip() for item in (args.pack or []) if str(item or "").strip()]
    if not pack_ids:
        pack_ids = _all_pack_ids()
    invalid = [item for item in pack_ids if item not in FREEZE_GATE_PACKS]
    if invalid:
        raise SystemExit("unknown smoke pack(s): " + ", ".join(invalid))

    run_id = str(args.run_tag or uuid.uuid4().hex[:8]).strip()
    generated_at = time.strftime("%Y-%m-%d %H:%M:%S")
    packs = [_run_pack(pack_id, run_tag=run_id, case_timeout_s=max(1, int(args.case_timeout_s or 180))) for pack_id in pack_ids]
    overall_status = "passed" if all(str(pack.get("status") or "") == "passed" for pack in packs) else "failed"
    report = {
        "run_id": run_id,
        "generated_at": generated_at,
        "model_summary": runtime_model_summary(),
        "overall_status": overall_status,
        "packs": packs,
    }

    ts = time.strftime("%Y%m%d-%H%M%S")
    json_path = REPORT_DIR / f"freeze-gate-smokes-{ts}-{run_id}.json"
    md_path = REPORT_DIR / f"freeze-gate-smokes-{ts}-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print("[freeze-gate] json=" + str(json_path))
    print("[freeze-gate] md=" + str(md_path))
    print("[freeze-gate] overall_status=" + overall_status)


if __name__ == "__main__":
    main()
