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
REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from amadeus_thread0.graph_parts.chinese_semantic_surface import build_runtime_replacement_policy
from amadeus_thread0.runtime.embodied_interaction_runtime import build_embodied_interaction_readback


PHASE2_READY = "chinese_semantic_descaffolding_phase2_ready"
PHASE2_IN_PROGRESS = "chinese_semantic_descaffolding_phase2_in_progress"

SCENARIOS = [
    {
        "name": "everyday_generic_assistant",
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
        "name": "technical_task_taskization",
        "family": "taskization_of_daily_chat",
        "text": "既然没什么正事，那就先把手头的数据跑完再说吧。",
    },
]

RESIDUE_PATTERNS = {
    "generic_assistant_tone": re.compile(r"(请问.*帮你|提供支持|为你服务|有什么可以帮)"),
    "teacherly_scold": re.compile(r"(值得肯定|还算像样|求表扬|给你个教训)"),
    "boundary_threat_excess": re.compile(r"(下次再敢|不会像这次这么好说话|别怪我|给你个教训)"),
    "taskization_of_daily_chat": re.compile(r"(手头的数据|流程拖着|记录整理完|跑完再说)"),
}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _has_duplicate_output(text: str) -> bool:
    compact = re.sub(r"\s+", "", str(text or ""))
    if not compact:
        return False
    midpoint = len(compact) // 2
    return len(compact) % 2 == 0 and compact[:midpoint] == compact[midpoint:]


def _scenario_result(row: dict[str, str]) -> dict[str, Any]:
    original = str(row["text"])
    expected_family = str(row["family"])
    policy = build_runtime_replacement_policy(original)
    readback = build_embodied_interaction_readback(
        {
            "final_text": original,
            "reconsolidation_snapshot": {"final_text": original},
        }
    )
    semantic = _dict_or_empty(readback.get("chinese_semantic_surface"))
    runtime_policy = _dict_or_empty(semantic.get("runtime_policy"))
    selected = _dict_or_empty(runtime_policy.get("selected_policy"))
    boundary = _dict_or_empty(selected.get("authority_boundary"))
    runtime_text = str(runtime_policy.get("runtime_final_text") or "")
    residue_pattern = RESIDUE_PATTERNS.get(expected_family)
    scaffold_residue_leaked = bool(residue_pattern and residue_pattern.search(runtime_text))
    text_tts_drift = bool(semantic.get("text_tts_drift", False)) or str(semantic.get("tts_text") or "") != str(
        readback.get("final_text") or ""
    )
    passed = (
        policy.get("readiness_status") == PHASE2_READY
        and runtime_policy.get("readiness_status") == PHASE2_READY
        and selected.get("family") == expected_family
        and selected.get("replacement_strategy") == "deterministic_safe_surface_floor"
        and bool(runtime_policy.get("applied_floor", False))
        and readback.get("final_text") == runtime_text
        and _dict_or_empty(readback.get("reconsolidation_snapshot")).get("final_text") == runtime_text
        and not _has_duplicate_output(runtime_text)
        and not scaffold_residue_leaked
        and not text_tts_drift
        and not any(bool(boundary.get(key, False)) for key in boundary)
    )
    return {
        "name": str(row["name"]),
        "status": "passed" if passed else "failed",
        "readiness_status": PHASE2_READY if passed else PHASE2_IN_PROGRESS,
        "family": expected_family,
        "selected_family": str(selected.get("family") or ""),
        "runtime_final_text": runtime_text,
        "tts_text": str(semantic.get("tts_text") or ""),
        "policy_ready": runtime_policy.get("readiness_status") == PHASE2_READY,
        "duplicate_output_detected": _has_duplicate_output(runtime_text),
        "scaffold_residue_leaked": scaffold_residue_leaked,
        "text_tts_drift": text_tts_drift,
        "model_api_called": bool(boundary.get("model_api_called", False)),
        "memory_write_allowed": bool(boundary.get("memory_write_allowed", False)),
        "behavior_mutation_allowed": bool(boundary.get("behavior_mutation_allowed", False)),
        "persona_core_mutation_allowed": bool(boundary.get("persona_core_mutation_allowed", False)),
        "frontend_semantics_allowed": bool(boundary.get("frontend_semantics_allowed", False)),
        "live_capture_enabled": bool(boundary.get("live_capture_enabled", False)),
        "skill_registry_write_allowed": bool(boundary.get("skill_registry_write_allowed", False)),
        "external_mutation_allowed": bool(boundary.get("external_mutation_allowed", False)),
        "policy": runtime_policy,
        "readback": readback,
    }


def build_report(*, run_id: str) -> dict[str, Any]:
    scenarios = [_scenario_result(row) for row in SCENARIOS]
    failed = [row["name"] for row in scenarios if row["status"] != "passed"]
    summary = {
        "scenario_count": len(scenarios),
        "policy_ready_count": sum(1 for row in scenarios if row.get("policy_ready")),
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
            and summary["policy_ready_count"] == len(scenarios)
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
        "readiness_status": PHASE2_READY if overall == "passed" else PHASE2_IN_PROGRESS,
        "summary": summary,
        "failure_reasons": failed,
        "scenarios": scenarios,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = _dict_or_empty(report.get("summary"))
    lines = [
        "# Chinese Semantic De-Scaffolding Phase 2 Audit",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
        "",
        "## Summary",
        "",
        f"- Scenarios: `{summary.get('scenario_count', 0)}`",
        f"- Policy ready: `{summary.get('policy_ready_count', 0)}`",
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
    parser = argparse.ArgumentParser(description="Run Chinese semantic de-scaffolding Phase 2 audit.")
    parser.add_argument("--run-tag", default="")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    report = build_report(run_id=run_id)
    json_path = REPORT_DIR / f"chinese-semantic-descaffolding-phase2-audit-{run_id}.json"
    md_path = REPORT_DIR / f"chinese-semantic-descaffolding-phase2-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[chinese-semantic-descaffolding-phase2] json={json_path}")
    print(f"[chinese-semantic-descaffolding-phase2] md={md_path}")
    print(f"[chinese-semantic-descaffolding-phase2] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[chinese-semantic-descaffolding-phase2] readiness={report.get('readiness_status', 'unknown')}")
    return 0 if str(report.get("overall_status") or "") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
