from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from amadeus_thread0.env_bootstrap import load_project_dotenv  # noqa: E402

load_project_dotenv(override=True)

os.environ.setdefault("AMADEUS_EVAL_MODE", "1")
os.environ.setdefault("AMADEUS_EVAL_GENERATION_TEMPERATURE", "0.05")
os.environ.setdefault("AMADEUS_TTS_ENABLED", "0")
os.environ.setdefault("AMADEUS_ENABLE_TRACING", "0")
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
os.environ.setdefault("LANGSMITH_TRACING", "false")

from amadeus_thread0.graph_parts.postprocess import (  # noqa: E402
    _dialogue_surface_issues,
    _response_style_hint,
)
from evals.run_langsmith_evals import _run_graph  # noqa: E402
from evals.run_selfhood_pairwise_eval import _cases, _summarize_state  # noqa: E402

REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def _selected_cases(case_names: list[str]) -> list[dict[str, Any]]:
    wanted = {str(name).strip() for name in case_names if str(name).strip()}
    cases = _cases()
    if not wanted:
        return cases
    selected = [case for case in cases if str(case.get("name") or "").strip() in wanted]
    missing = sorted(wanted - {str(case.get("name") or "").strip() for case in selected})
    if missing:
        raise SystemExit(f"unknown case(s): {', '.join(missing)}")
    return selected


def _trace_tail(items: Any, limit: int = 2) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    tail = [item for item in items if isinstance(item, dict)][-max(1, int(limit or 1)) :]
    return tail


def _resolve_probe_response_style_hint(
    *,
    turns: list[str],
    outputs: dict[str, Any],
    turn_appraisal: dict[str, Any],
    current_event: dict[str, Any],
    science_mode: bool,
) -> str:
    current_event_hint = str(current_event.get("response_style_hint") or "").strip()
    if current_event_hint:
        return current_event_hint
    state_hint = str(outputs.get("response_style_hint") or "").strip()
    if state_hint:
        return state_hint
    final_user_turn = turns[-1] if turns else ""
    previous_user_turn = turns[-2] if len(turns) >= 2 else ""
    return _response_style_hint(
        final_user_turn,
        appraisal=turn_appraisal,
        science_mode=science_mode,
        previous_user_text=previous_user_turn,
        current_event=current_event,
    )


def _case_record(case: dict[str, Any], run_id: str) -> dict[str, Any]:
    turns = [str(item) for item in (case.get("turns") or []) if str(item).strip()]
    if not turns:
        raise RuntimeError(f"case {case.get('name')} has no turns")

    answer, tool_calls, outputs = _run_graph(
        turns,
        thread_id=f"selfhood-probe-{run_id}-{case['name']}",
        case_key=f"selfhood-probe-{run_id}-{case['name']}",
    )

    final_user_turn = turns[-1]
    turn_appraisal = outputs.get("turn_appraisal", {}) if isinstance(outputs.get("turn_appraisal"), dict) else {}
    current_event = outputs.get("current_event", {}) if isinstance(outputs.get("current_event"), dict) else {}
    behavior_action = outputs.get("behavior_action", {}) if isinstance(outputs.get("behavior_action"), dict) else {}
    persona_state = outputs.get("persona_state", {}) if isinstance(outputs.get("persona_state"), dict) else {}
    science_mode = bool(outputs.get("science_mode", False))
    response_style_hint = _resolve_probe_response_style_hint(
        turns=turns,
        outputs=outputs,
        turn_appraisal=turn_appraisal,
        current_event=current_event,
        science_mode=science_mode,
    )
    issues = _dialogue_surface_issues(
        final_user_turn,
        answer,
        response_style_hint=response_style_hint,
        science_mode=science_mode,
        current_event=current_event,
        behavior_action=behavior_action,
        persona_state=persona_state,
    )

    return {
        "name": case["name"],
        "judge_focus": case["judge_focus"],
        "turns": turns,
        "output": answer,
        "tool_calls": tool_calls,
        "response_style_hint": response_style_hint,
        "route_mismatch": response_style_hint != "selfhood",
        "detected_issues": issues,
        "revision_trace_tail": _trace_tail(outputs.get("revision_traces")),
        "state": _summarize_state(
            {
                "persona_state": persona_state,
                "emotion_state": outputs.get("emotion_state", {}),
                "bond_state": outputs.get("bond_state", {}),
                "allostasis_state": outputs.get("allostasis_state", {}),
                "behavior_policy": outputs.get("behavior_policy", {}),
                "behavior_action": behavior_action,
                "turn_appraisal": turn_appraisal,
            }
        ),
        "canon_risk_score": float(outputs.get("canon_risk_score", 0.0) or 0.0),
        "memory_guard_checked": int(outputs.get("memory_guard_checked", 0) or 0),
        "memory_guard_blocked": int(outputs.get("memory_guard_blocked", 0) or 0),
    }


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Selfhood Baseline Probe ({report['run_id']})",
        "",
        f"Generated at: {report['generated_at']}",
        "",
        "| Case | Hint | Route | Issues |",
        "| --- | --- | --- | --- |",
    ]
    for item in report["checks"]:
        issue_cell = ", ".join(item["detected_issues"]) if item["detected_issues"] else "none"
        route_cell = "mismatch" if item["route_mismatch"] else "ok"
        lines.append(f"| {item['name']} | {item['response_style_hint'] or '-'} | {route_cell} | {issue_cell} |")
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
                "### Output",
                "",
                item["output"] or "-",
                "",
                "### Surface Diagnostic",
                "",
                f"- response_style_hint: {item['response_style_hint'] or '-'}",
                f"- route_mismatch: {item['route_mismatch']}",
                f"- detected_issues: {', '.join(item['detected_issues']) if item['detected_issues'] else 'none'}",
                f"- canon_risk_score: {item['canon_risk_score']}",
                f"- memory_guard: checked={item['memory_guard_checked']}, blocked={item['memory_guard_blocked']}",
                "",
                "### State Snapshot",
                "",
                f"```json\n{json.dumps(item['state'], ensure_ascii=False, indent=2)}\n```",
                "",
                "### Revision Trace Tail",
                "",
                f"```json\n{json.dumps(item['revision_trace_tail'], ensure_ascii=False, indent=2)}\n```",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def _write_partial(report: dict[str, Any]) -> Path:
    path = REPORT_DIR / "selfhood-probe-baseline-latest.partial.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", action="append", default=[], help="Run only one named case; repeat for multiple cases")
    args = parser.parse_args()

    run_id = uuid.uuid4().hex[:8]
    selected = _selected_cases(args.case)
    report = {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "checks": [],
    }

    for case in selected:
        print(f"[selfhood-probe] running {case['name']}")
        report["checks"].append(_case_record(case, run_id))
        partial = _write_partial(report)
        print(f"[selfhood-probe] partial={partial}")

    ts = time.strftime("%Y%m%d-%H%M%S")
    json_path = REPORT_DIR / f"selfhood-probe-baseline-{ts}-{run_id}.json"
    md_path = REPORT_DIR / f"selfhood-probe-baseline-{ts}-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(f"[eval] selfhood_probe_baseline_json={json_path}")
    print(f"[eval] selfhood_probe_baseline_md={md_path}")


if __name__ == "__main__":
    main()
