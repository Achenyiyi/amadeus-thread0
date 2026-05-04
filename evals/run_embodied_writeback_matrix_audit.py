from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

MATRIX_FAMILIES = [
    "workspace_path_inspected",
    "workspace_file_updated",
    "source_material_inspected",
    "source_material_compared",
    "artifact_reacquired",
    "access_state_refreshed",
    "workspace_root_attached",
    "sandbox_execution_completed",
    "sandbox_execution_blocked",
    "browser_navigation_completed",
    "browser_interaction_completed",
    "browser_download_completed",
    "browser_upload_completed",
    "browser_takeover_requested",
    "browser_action_blocked",
    "skill_usage_completed",
    "skill_mutation_blocked",
]

MATRIX_K_EXPR = "embodied or sandbox or browser or skill or source or workspace"


CHECK_COVERAGE: dict[str, list[str]] = {
    "matrix_core_writeback_residue": [
        "workspace_path_inspected",
        "workspace_file_updated",
        "source_material_compared",
        "artifact_reacquired",
        "access_state_refreshed",
        "sandbox_execution_completed",
        "sandbox_execution_blocked",
        "browser_navigation_completed",
        "browser_takeover_requested",
        "skill_usage_completed",
        "skill_mutation_blocked",
    ],
    "matrix_backend_contract": [
        "workspace_path_inspected",
        "workspace_file_updated",
        "source_material_inspected",
        "source_material_compared",
        "artifact_reacquired",
        "access_state_refreshed",
        "sandbox_execution_completed",
        "browser_navigation_completed",
        "browser_interaction_completed",
        "browser_download_completed",
        "browser_upload_completed",
        "browser_takeover_requested",
        "browser_action_blocked",
        "skill_usage_completed",
    ],
    "matrix_retrieval_continuity": [
        "workspace_path_inspected",
        "workspace_file_updated",
        "source_material_compared",
        "artifact_reacquired",
        "access_state_refreshed",
        "workspace_root_attached",
        "sandbox_execution_completed",
        "browser_navigation_completed",
        "browser_interaction_completed",
        "browser_takeover_requested",
        "skill_usage_completed",
    ],
}

FAMILY_TEST_NODES: dict[str, list[str]] = {
    "workspace_path_inspected": [
        "tests/test_backend_api.py::BackendApiTests::test_turn_and_event_responses_surface_workspace_path_inspected_consequence",
        "tests/test_world_model_residue.py::WorldModelResidueTests::test_retrieved_digital_body_trace_bridge_preserves_workspace_path_inspection_surface_context",
    ],
    "workspace_file_updated": [
        "tests/test_backend_api.py::BackendApiTests::test_turn_and_event_responses_surface_workspace_file_updated_consequence",
        "tests/test_world_model_residue.py::WorldModelResidueTests::test_retrieved_digital_body_trace_bridge_preserves_workspace_file_continuity",
    ],
    "source_material_inspected": [
        "tests/test_backend_api.py::BackendApiTests::test_turn_and_event_responses_surface_source_material_inspected_consequence",
        "tests/test_backend_session.py::BackendSessionTests::test_backend_session_surfaces_source_material_and_access_consequence_kinds",
    ],
    "source_material_compared": [
        "tests/test_backend_api.py::BackendApiTests::test_turn_and_event_responses_surface_source_material_compared_consequence",
        "tests/test_retrieval_continuity.py::test_retrieve_context_uses_nested_source_identity_for_legacy_digital_body_traces",
        "tests/test_world_model_residue.py::WorldModelResidueTests::test_retrieved_digital_body_trace_bridge_merges_legacy_source_ref_identity_into_embodied_context",
    ],
    "artifact_reacquired": [
        "tests/test_backend_api.py::BackendApiTests::test_turn_and_event_responses_surface_artifact_reacquired_consequence",
        "tests/test_world_model_residue.py::WorldModelResidueTests::test_retrieved_digital_body_trace_bridge_preserves_filesystem_artifact_reacquisition",
    ],
    "access_state_refreshed": [
        "tests/test_backend_api.py::BackendApiTests::test_turn_and_event_responses_surface_access_state_refreshed_consequence",
        "tests/test_world_model_residue.py::WorldModelResidueTests::test_retrieved_digital_body_trace_bridge_preserves_access_state_refreshed_context",
    ],
    "workspace_root_attached": [
        "tests/test_retrieval_continuity.py::test_retrieve_context_surfaces_workspace_root_attach_trace_identity",
        "tests/test_world_model_residue.py::WorldModelResidueTests::test_record_digital_body_consequence_long_horizon_memory_records_workspace_root_attach_and_browser",
    ],
    "sandbox_execution_completed": [
        "tests/test_autonomy_writeback.py::AutonomyWritebackTests::test_reconsolidation_snapshot_distinguishes_sandbox_completed_blocked_and_pending",
        "tests/test_autonomy_writeback.py::AutonomyWritebackTests::test_reconsolidation_snapshot_preserves_sandbox_phase2_isolated_runner_identity",
        "tests/test_world_model_residue.py::WorldModelResidueTests::test_revision_trace_store_preserves_sandbox_run_context",
    ],
    "sandbox_execution_blocked": [
        "tests/test_autonomy_writeback.py::AutonomyWritebackTests::test_reconsolidation_snapshot_distinguishes_sandbox_completed_blocked_and_pending",
    ],
    "browser_navigation_completed": [
        "tests/test_autonomy_writeback.py::AutonomyWritebackTests::test_reconsolidation_snapshot_distinguishes_browser_completed_blocked_and_takeover",
        "tests/test_backend_api.py::BackendApiTests::test_turn_response_surfaces_live_browser_runtime_fields",
        "tests/test_world_model_residue.py::WorldModelResidueTests::test_revision_trace_store_preserves_live_browser_context",
    ],
    "browser_interaction_completed": [
        "tests/test_autonomy_writeback.py::AutonomyWritebackTests::test_reconsolidation_snapshot_does_not_let_stale_takeover_state_override_completed_browser_result",
        "tests/test_backend_api.py::BackendApiTests::test_turn_response_surfaces_browser_matrix_consequence_families",
        "tests/test_world_model_residue.py::WorldModelResidueTests::test_retrieved_digital_body_trace_bridge_preserves_browser_interaction_context",
    ],
    "browser_download_completed": [
        "tests/test_backend_api.py::BackendApiTests::test_turn_response_surfaces_browser_matrix_consequence_families",
    ],
    "browser_upload_completed": [
        "tests/test_backend_api.py::BackendApiTests::test_turn_response_surfaces_browser_matrix_consequence_families",
    ],
    "browser_takeover_requested": [
        "tests/test_autonomy_writeback.py::AutonomyWritebackTests::test_reconsolidation_snapshot_distinguishes_browser_completed_blocked_and_takeover",
        "tests/test_backend_api.py::BackendApiTests::test_turn_response_surfaces_browser_matrix_consequence_families",
        "tests/test_world_model_residue.py::WorldModelResidueTests::test_retrieved_digital_body_trace_bridge_preserves_browser_takeover_without_completion_claim",
    ],
    "browser_action_blocked": [
        "tests/test_autonomy_writeback.py::AutonomyWritebackTests::test_reconsolidation_snapshot_distinguishes_browser_completed_blocked_and_takeover",
        "tests/test_backend_api.py::BackendApiTests::test_turn_response_surfaces_browser_matrix_consequence_families",
    ],
    "skill_usage_completed": [
        "tests/test_autonomy_writeback.py::AutonomyWritebackTests::test_reconsolidation_snapshot_distinguishes_skill_install_usage_and_blocked_mutation",
        "tests/test_backend_api.py::BackendApiTests::test_turn_response_surfaces_completed_skill_usage_as_digital_body_consequence",
        "tests/test_world_model_residue.py::WorldModelResidueTests::test_skill_usage_writeback_resurfaces_into_followup_continuity",
    ],
    "skill_mutation_blocked": [
        "tests/test_autonomy_writeback.py::AutonomyWritebackTests::test_reconsolidation_snapshot_distinguishes_skill_install_usage_and_blocked_mutation",
    ],
}


def family_coverage(checks: Sequence[dict[str, Any]] | None = None) -> dict[str, list[str]]:
    rows = [dict(item) for item in checks] if checks is not None else []
    if rows:
        covered: dict[str, list[str]] = {family: [] for family in MATRIX_FAMILIES}
        for row in rows:
            if str(row.get("status") or "") != "passed" or not bool(row.get("blocking", True)):
                continue
            check_id = str(row.get("id") or "")
            row_covers = row.get("covers") if isinstance(row.get("covers"), list) else []
            for family in row_covers:
                family_name = str(family or "").strip()
                if family_name in covered:
                    covered[family_name].append(check_id)
        return covered
    return {
        family: [
            check_id
            for check_id, families in CHECK_COVERAGE.items()
            if family in set(str(item or "").strip() for item in families)
        ]
        for family in MATRIX_FAMILIES
    }


def missing_family_coverage(checks: Sequence[dict[str, Any]] | None = None) -> list[str]:
    coverage = family_coverage(checks)
    return [family for family in MATRIX_FAMILIES if not coverage.get(family)]


def missing_family_test_nodes() -> list[str]:
    return [family for family in MATRIX_FAMILIES if not (FAMILY_TEST_NODES.get(family) or [])]


def _python(*args: str) -> list[str]:
    return [sys.executable, *args]


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("AMADEUS_BROWSER_HEADLESS", "1")
    return env


def _fmt(command: Sequence[str]) -> str:
    return subprocess.list2cmdline([str(part) for part in command])


def _tail(text: str, limit: int = 2400) -> str:
    value = str(text or "")
    return value if len(value) <= limit else value[-limit:]


def _run(command: Sequence[str]) -> dict[str, Any]:
    started = time.time()
    completed = subprocess.run(
        [str(part) for part in command],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_env(),
    )
    return {
        "returncode": int(completed.returncode),
        "stdout": str(completed.stdout or ""),
        "stderr": str(completed.stderr or ""),
        "duration_s": round(time.time() - started, 3),
    }


def build_check_specs() -> list[dict[str, Any]]:
    broad_specs = [
        {
            "id": "matrix_core_writeback_residue",
            "title": "Matrix Core Writeback + Residue",
            "covers": CHECK_COVERAGE["matrix_core_writeback_residue"],
            "command": _python(
                "-m",
                "pytest",
                "tests/test_autonomy_writeback.py",
                "tests/test_world_model_residue.py",
                "-k",
                MATRIX_K_EXPR,
                "-q",
            ),
        },
        {
            "id": "matrix_backend_contract",
            "title": "Matrix Backend Session/API Contract",
            "covers": CHECK_COVERAGE["matrix_backend_contract"],
            "command": _python(
                "-m",
                "pytest",
                "tests/test_backend_session.py",
                "tests/test_backend_api.py",
                "-k",
                MATRIX_K_EXPR,
                "-q",
            ),
        },
        {
            "id": "matrix_retrieval_continuity",
            "title": "Matrix Retrieval Continuity",
            "covers": CHECK_COVERAGE["matrix_retrieval_continuity"],
            "command": _python(
                "-m",
                "pytest",
                "tests/test_retrieval_continuity.py",
                "tests/test_world_model_residue.py",
                "-k",
                "retrieve_context or retrieved_digital_body_trace_bridge or revision_trace_store_preserves or skill_usage_writeback_resurfaces",
                "-q",
            ),
        },
    ]
    return broad_specs + build_family_node_check_specs()


def build_family_node_check_specs() -> list[dict[str, Any]]:
    nodes: list[str] = []
    seen: set[str] = set()
    for family in MATRIX_FAMILIES:
        for node in FAMILY_TEST_NODES.get(family) or []:
            if node in seen:
                continue
            seen.add(node)
            nodes.append(node)
    return [
        {
            "id": "matrix_family_node_coverage",
            "title": "Matrix Family Executable Node Coverage",
            "covers": list(MATRIX_FAMILIES),
            "pytest_nodes": nodes,
            "command": _python("-m", "pytest", *nodes, "-q"),
        }
    ]


def _check(spec: dict[str, Any]) -> dict[str, Any]:
    outcome = _run(spec["command"])
    status = "passed" if int(outcome["returncode"]) == 0 else "failed"
    return {
        "id": str(spec.get("id") or ""),
        "title": str(spec.get("title") or ""),
        "blocking": True,
        "covers": [str(item) for item in (spec.get("covers") if isinstance(spec.get("covers"), list) else [])],
        "pytest_nodes": [
            str(item)
            for item in (spec.get("pytest_nodes") if isinstance(spec.get("pytest_nodes"), list) else [])
        ],
        "command": _fmt(spec.get("command") or []),
        "status": status,
        "returncode": int(outcome["returncode"]),
        "duration_s": float(outcome["duration_s"]),
        "stdout_tail": _tail(outcome["stdout"]),
        "stderr_tail": _tail(outcome["stderr"]),
    }


def _overall(checks: Sequence[dict[str, Any]]) -> dict[str, Any]:
    rows = [dict(item) for item in checks]
    failed = [
        str(row.get("id") or "")
        for row in rows
        if str(row.get("status") or "") != "passed" and bool(row.get("blocking", True))
    ]
    missing = missing_family_coverage(rows)
    missing_nodes = missing_family_test_nodes()
    blocking_failures = (
        list(failed)
        + [f"missing_family:{family}" for family in missing]
        + [f"missing_family_test_nodes:{family}" for family in missing_nodes]
    )
    return {
        "overall_status": "passed" if not blocking_failures else "failed",
        "readiness_status": "embodied_writeback_matrix_ready"
        if not blocking_failures
        else "embodied_writeback_matrix_regressed",
        "summary": {"total": len(rows), "passed": len(rows) - len(failed), "failed": len(failed)},
        "family_coverage": family_coverage(rows),
        "missing_family_coverage": missing,
        "missing_family_test_nodes": missing_nodes,
        "blocking_failure_ids": blocking_failures,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Embodied Writeback Matrix Audit ({report.get('run_id', 'unknown')})",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
        "",
        "## Summary",
        "",
        f"- Total checks: `{report.get('summary', {}).get('total', 0)}`",
        f"- Passed: `{report.get('summary', {}).get('passed', 0)}`",
        f"- Failed: `{report.get('summary', {}).get('failed', 0)}`",
        "",
        "## Matrix Families",
        "",
    ]
    coverage = report.get("family_coverage") if isinstance(report.get("family_coverage"), dict) else {}
    lines.extend(["| Family | Blocking Checks |", "| --- | --- |"])
    for family in report.get("matrix_families") or []:
        checks = [
            str(item)
            for item in (coverage.get(family) if isinstance(coverage.get(family), list) else [])
            if str(item).strip()
        ]
        lines.append(f"| `{family}` | {', '.join(f'`{item}`' for item in checks) or '`missing`'} |")
    missing = report.get("missing_family_coverage") if isinstance(report.get("missing_family_coverage"), list) else []
    if missing:
        lines.extend(["", "Missing family coverage: " + ", ".join(f"`{item}`" for item in missing)])
    missing_nodes = (
        report.get("missing_family_test_nodes")
        if isinstance(report.get("missing_family_test_nodes"), list)
        else []
    )
    if missing_nodes:
        lines.extend(["", "Missing executable family test nodes: " + ", ".join(f"`{item}`" for item in missing_nodes)])
    lines.extend(["", "## Checks", "", "| Check | Status | Covers | Duration (s) |", "| --- | --- | --- | ---: |"])
    for row in report.get("checks") or []:
        covers = [
            str(item)
            for item in (row.get("covers") if isinstance(row.get("covers"), list) else [])
            if str(item).strip()
        ]
        lines.append(
            f"| `{row.get('id', '')}` | `{row.get('status', '')}` | {len(covers)} families | {float(row.get('duration_s') or 0.0):.3f} |"
        )
    failures = [row for row in (report.get("checks") or []) if str(row.get("status") or "") != "passed"]
    if failures:
        lines.extend(["", "## Failures", ""])
        for row in failures:
            lines.append(f"### `{row.get('id', '')}`")
            lines.append("")
            lines.append(f"Command: `{row.get('command', '')}`")
            lines.append("")
            lines.append("```text")
            lines.append(str(row.get("stdout_tail") or "").strip())
            lines.append(str(row.get("stderr_tail") or "").strip())
            lines.append("```")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the embodied writeback matrix audit.")
    parser.add_argument("--run-tag", default="")
    args = parser.parse_args()

    run_suffix = str(args.run_tag or "").strip() or time.strftime("%Y%m%d-%H%M%S")
    run_id = f"embodied-writeback-matrix-{run_suffix}"
    checks = [_check(spec) for spec in build_check_specs()]
    report: dict[str, Any] = {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "matrix_families": list(MATRIX_FAMILIES),
        "checks": checks,
    }
    report.update(_overall(checks))

    artifact_id = run_suffix
    json_path = REPORT_DIR / f"embodied-writeback-matrix-audit-{artifact_id}.json"
    md_path = REPORT_DIR / f"embodied-writeback-matrix-audit-{artifact_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[embodied-writeback-matrix] json={json_path}")
    print(f"[embodied-writeback-matrix] md={md_path}")
    print(f"[embodied-writeback-matrix] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[embodied-writeback-matrix] readiness={report.get('readiness_status', 'unknown')}")
    return 0 if str(report.get("overall_status") or "") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
