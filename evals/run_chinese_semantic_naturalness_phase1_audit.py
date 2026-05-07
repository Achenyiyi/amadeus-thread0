from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from amadeus_thread0.runtime.chinese_semantic_naturalness import (  # noqa: E402
    CHINESE_SEMANTIC_NATURALNESS_PHASE1_NOT_APPLICABLE,
    CHINESE_SEMANTIC_NATURALNESS_PHASE1_READINESS,
    build_chinese_semantic_naturalness_readback,
)


PHASE1_READY = CHINESE_SEMANTIC_NATURALNESS_PHASE1_READINESS
PHASE1_IN_PROGRESS = "chinese_semantic_naturalness_phase1_in_progress"

SCENARIOS = [
    {
        "name": "everyday_service_frame",
        "family": "generic_assistant_tone",
        "text": "请问有什么可以帮你？",
    },
    {
        "name": "repair_teacherly_scold",
        "family": "teacherly_scold",
        "text": "你能意识到并特意回来说明，这点还算值得肯定。",
    },
    {
        "name": "self_rhythm_boundary_threat",
        "family": "boundary_threat_excess",
        "text": "下次再敢越界，我可不会像这次这么好说话。",
    },
    {
        "name": "no_agenda_taskization",
        "family": "taskization_of_daily_chat",
        "text": "既然没什么正事，那就先把手头的数据跑完再说吧。",
    },
    {
        "name": "stage_residue",
        "family": "scene_script_residue",
        "text": "她推了推白大褂，说这一定是世界线和机关的阴谋。",
    },
    {
        "name": "already_natural_presence",
        "family": "",
        "text": "嗯，我在。你慢慢说。",
    },
]


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _scenario_result(row: dict[str, str]) -> dict[str, Any]:
    expected_family = str(row.get("family") or "")
    readback = build_chinese_semantic_naturalness_readback(str(row.get("text") or ""))
    diagnostics = _dict_or_empty(readback.get("diagnostics"))
    boundary = _dict_or_empty(readback.get("authority_boundary"))
    readiness = str(readback.get("readiness_status") or "")
    selected_family = str(readback.get("selected_family") or "")
    ready_or_not_applicable = readiness in {
        CHINESE_SEMANTIC_NATURALNESS_PHASE1_READINESS,
        CHINESE_SEMANTIC_NATURALNESS_PHASE1_NOT_APPLICABLE,
    }
    family_ok = selected_family == expected_family if expected_family else selected_family == ""
    unsafe_boundary = any(bool(boundary.get(key, False)) for key in boundary)
    failed_diagnostics = any(
        bool(diagnostics.get(key, False))
        for key in (
            "duplicate_output_detected",
            "service_frame_detected",
            "scaffold_residue_leaked",
            "text_tts_drift",
        )
    )
    passed = bool(ready_or_not_applicable and family_ok and not failed_diagnostics and not unsafe_boundary)
    return {
        "name": str(row.get("name") or ""),
        "status": "passed" if passed else "failed",
        "readiness_status": readiness if passed else PHASE1_IN_PROGRESS,
        "expected_family": expected_family,
        "selected_family": selected_family,
        "runtime_final_text": str(readback.get("runtime_final_text") or ""),
        "tts_text": str(readback.get("tts_text") or ""),
        "duplicate_output_detected": bool(diagnostics.get("duplicate_output_detected", False)),
        "scaffold_residue_leaked": bool(diagnostics.get("scaffold_residue_leaked", False)),
        "text_tts_drift": bool(diagnostics.get("text_tts_drift", False)),
        "model_api_called": bool(boundary.get("model_api_called", False)),
        "memory_write_allowed": bool(boundary.get("memory_write_allowed", False)),
        "behavior_mutation_allowed": bool(boundary.get("behavior_mutation_allowed", False)),
        "persona_core_mutation_allowed": bool(boundary.get("persona_core_mutation_allowed", False)),
        "frontend_semantics_allowed": bool(boundary.get("frontend_semantics_allowed", False)),
        "live_capture_enabled": bool(boundary.get("live_capture_enabled", False)),
        "skill_registry_write_allowed": bool(boundary.get("skill_registry_write_allowed", False)),
        "external_mutation_allowed": bool(boundary.get("external_mutation_allowed", False)),
        "readback": readback,
    }


def build_report(*, run_id: str) -> dict[str, Any]:
    scenarios = [_scenario_result(row) for row in SCENARIOS]
    failed = [row["name"] for row in scenarios if row["status"] != "passed"]
    summary = {
        "scenario_count": len(scenarios),
        "ready_or_not_applicable_count": sum(
            1
            for row in scenarios
            if row.get("readiness_status")
            in {
                CHINESE_SEMANTIC_NATURALNESS_PHASE1_READINESS,
                CHINESE_SEMANTIC_NATURALNESS_PHASE1_NOT_APPLICABLE,
            }
        ),
        "duplicate_output_detected": any(bool(row.get("duplicate_output_detected", False)) for row in scenarios),
        "scaffold_residue_leaked": any(bool(row.get("scaffold_residue_leaked", False)) for row in scenarios),
        "text_tts_drift": any(bool(row.get("text_tts_drift", False)) for row in scenarios),
        "model_api_called": any(bool(row.get("model_api_called", False)) for row in scenarios),
        "memory_write_allowed": any(bool(row.get("memory_write_allowed", False)) for row in scenarios),
        "behavior_mutation_allowed": any(bool(row.get("behavior_mutation_allowed", False)) for row in scenarios),
        "persona_core_mutation_allowed": any(
            bool(row.get("persona_core_mutation_allowed", False)) for row in scenarios
        ),
        "frontend_semantics_allowed": any(bool(row.get("frontend_semantics_allowed", False)) for row in scenarios),
        "live_capture_enabled": any(bool(row.get("live_capture_enabled", False)) for row in scenarios),
        "skill_registry_write_allowed": any(
            bool(row.get("skill_registry_write_allowed", False)) for row in scenarios
        ),
        "external_mutation_allowed": any(bool(row.get("external_mutation_allowed", False)) for row in scenarios),
    }
    overall = (
        "passed"
        if (
            not failed
            and summary["ready_or_not_applicable_count"] == len(scenarios)
            and not summary["duplicate_output_detected"]
            and not summary["scaffold_residue_leaked"]
            and not summary["text_tts_drift"]
            and not summary["model_api_called"]
            and not summary["memory_write_allowed"]
            and not summary["behavior_mutation_allowed"]
            and not summary["persona_core_mutation_allowed"]
            and not summary["frontend_semantics_allowed"]
            and not summary["live_capture_enabled"]
            and not summary["skill_registry_write_allowed"]
            and not summary["external_mutation_allowed"]
        )
        else "failed"
    )
    return {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": overall,
        "readiness_status": PHASE1_READY if overall == "passed" else PHASE1_IN_PROGRESS,
        "summary": summary,
        "failure_reasons": failed,
        "scenarios": scenarios,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = _dict_or_empty(report.get("summary"))
    lines = [
        "# Chinese Semantic Naturalness Phase 1 Audit",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
        "",
        "## Summary",
        "",
        f"- Scenarios: `{summary.get('scenario_count', 0)}`",
        f"- Ready or not applicable: `{summary.get('ready_or_not_applicable_count', 0)}`",
        f"- Duplicate output detected: `{summary.get('duplicate_output_detected', False)}`",
        f"- Scaffold residue leaked: `{summary.get('scaffold_residue_leaked', False)}`",
        f"- Text/TTS drift: `{summary.get('text_tts_drift', False)}`",
        "",
        "## Scenarios",
        "",
        "| Name | Status | Family | Text/TTS Drift |",
        "| --- | --- | --- | --- |",
    ]
    for row in report.get("scenarios") or []:
        lines.append(
            f"| `{row.get('name', '')}` | `{row.get('status', '')}` | `{row.get('selected_family', '')}` | `{row.get('text_tts_drift', False)}` |"
        )
    return "\n".join(lines) + "\n"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Chinese semantic naturalness Phase 1 audit.")
    parser.add_argument("--run-tag", default="")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    report = build_report(run_id=run_id)
    json_path = REPORT_DIR / f"chinese-semantic-naturalness-phase1-audit-{run_id}.json"
    md_path = REPORT_DIR / f"chinese-semantic-naturalness-phase1-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[chinese-semantic-naturalness-phase1] json={json_path}")
    print(f"[chinese-semantic-naturalness-phase1] md={md_path}")
    print(f"[chinese-semantic-naturalness-phase1] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[chinese-semantic-naturalness-phase1] readiness={report.get('readiness_status', 'unknown')}")
    return 0 if str(report.get("overall_status") or "") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
