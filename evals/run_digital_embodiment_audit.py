from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

COMPANION_JSON_RE = re.compile(r"^\[companion-autonomy\]\s+json=(.+)$", re.MULTILINE)
COMPANION_MD_RE = re.compile(r"^\[companion-autonomy\]\s+md=(.+)$", re.MULTILINE)
COMPANION_STATUS_RE = re.compile(r"^\[companion-autonomy\]\s+overall_status=(.+)$", re.MULTILINE)
COMPANION_READINESS_RE = re.compile(r"^\[companion-autonomy\]\s+readiness=(.+)$", re.MULTILINE)
EMBODIMENT_SMOKES_JSON_RE = re.compile(r"^\[digital-embodiment-smokes\]\s+json=(.+)$", re.MULTILINE)
EMBODIMENT_SMOKES_MD_RE = re.compile(r"^\[digital-embodiment-smokes\]\s+md=(.+)$", re.MULTILINE)
EMBODIMENT_SMOKES_STATUS_RE = re.compile(
    r"^\[digital-embodiment-smokes\]\s+overall_status=(.+)$",
    re.MULTILINE,
)


def _python_cmd(*args: str) -> list[str]:
    return [sys.executable, *args]


def _base_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    return env


def _tail_text(text: str, *, limit: int = 2400) -> str:
    content = str(text or "").strip()
    return content if len(content) <= limit else content[-limit:]


def _format_command(command: Sequence[str]) -> str:
    return subprocess.list2cmdline([str(part) for part in command])


def _run_command(command: Sequence[str]) -> dict[str, Any]:
    start = time.time()
    completed = subprocess.run(
        [str(part) for part in command],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_base_env(),
    )
    return {
        "returncode": int(completed.returncode),
        "stdout": str(completed.stdout or ""),
        "stderr": str(completed.stderr or ""),
        "duration_s": round(time.time() - start, 3),
    }


def _load_json(path: str) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _parse_companion_autonomy_artifacts(stdout: str) -> dict[str, str]:
    text = str(stdout or "")
    payload: dict[str, str] = {}
    json_match = COMPANION_JSON_RE.search(text)
    md_match = COMPANION_MD_RE.search(text)
    status_match = COMPANION_STATUS_RE.search(text)
    readiness_match = COMPANION_READINESS_RE.search(text)
    if json_match:
        payload["json"] = json_match.group(1).strip()
    if md_match:
        payload["md"] = md_match.group(1).strip()
    if status_match:
        payload["overall_status"] = status_match.group(1).strip()
    if readiness_match:
        payload["readiness"] = readiness_match.group(1).strip()
    json_payload = _load_json(payload.get("json") or "")
    if json_payload:
        payload["freeze_gate_readiness"] = str(json_payload.get("freeze_gate_readiness") or "").strip()
        payload["companion_readiness"] = str(json_payload.get("readiness_status") or "").strip()
    else:
        payload["freeze_gate_readiness"] = ""
        payload["companion_readiness"] = payload.get("readiness", "")
    return payload


def _parse_digital_embodiment_smoke_artifacts(stdout: str) -> dict[str, str]:
    text = str(stdout or "")
    payload: dict[str, str] = {}
    json_match = EMBODIMENT_SMOKES_JSON_RE.search(text)
    md_match = EMBODIMENT_SMOKES_MD_RE.search(text)
    status_match = EMBODIMENT_SMOKES_STATUS_RE.search(text)
    if json_match:
        payload["json"] = json_match.group(1).strip()
    if md_match:
        payload["md"] = md_match.group(1).strip()
    if status_match:
        payload["overall_status"] = status_match.group(1).strip()
    json_payload = _load_json(payload.get("json") or "")
    if json_payload:
        payload["passed"] = str(json_payload.get("passed") or 0)
        payload["failed"] = str(json_payload.get("failed") or 0)
    return payload


def _check(
    id: str,
    title: str,
    command: Sequence[str],
    *,
    blocking: bool = True,
    artifact_parser: str = "",
) -> dict[str, Any]:
    outcome = _run_command(command)
    status = "passed" if int(outcome["returncode"]) == 0 else "failed"
    artifacts: dict[str, Any] = {}
    failure_reasons: list[str] = []

    if artifact_parser == "companion_autonomy":
        artifacts = _parse_companion_autonomy_artifacts(outcome.get("stdout") or "")
        if not str(artifacts.get("json") or "").strip():
            status = "failed"
            failure_reasons.append("missing_json_artifact")
        elif not Path(str(artifacts.get("json") or "")).exists():
            status = "failed"
            failure_reasons.append("missing_file:json")
        if not str(artifacts.get("md") or "").strip():
            status = "failed"
            failure_reasons.append("missing_md_artifact")
        elif not Path(str(artifacts.get("md") or "")).exists():
            status = "failed"
            failure_reasons.append("missing_file:md")
        if str(artifacts.get("overall_status") or "") != "passed":
            status = "failed"
            failure_reasons.append(
                "companion_overall_status=" + str(artifacts.get("overall_status") or "unknown")
            )
    elif artifact_parser == "digital_embodiment_smokes":
        artifacts = _parse_digital_embodiment_smoke_artifacts(outcome.get("stdout") or "")
        if not str(artifacts.get("json") or "").strip():
            status = "failed"
            failure_reasons.append("missing_json_artifact")
        elif not Path(str(artifacts.get("json") or "")).exists():
            status = "failed"
            failure_reasons.append("missing_file:json")
        if not str(artifacts.get("md") or "").strip():
            status = "failed"
            failure_reasons.append("missing_md_artifact")
        elif not Path(str(artifacts.get("md") or "")).exists():
            status = "failed"
            failure_reasons.append("missing_file:md")
        if str(artifacts.get("overall_status") or "") != "passed":
            status = "failed"
            failure_reasons.append(
                "digital_embodiment_smokes_overall_status=" + str(artifacts.get("overall_status") or "unknown")
            )

    return {
        "id": id,
        "title": title,
        "blocking": blocking,
        "command": _format_command(command),
        "status": status,
        "returncode": int(outcome["returncode"]),
        "duration_s": float(outcome["duration_s"]),
        "artifacts": artifacts,
        "failure_reasons": failure_reasons,
        "stdout_tail": _tail_text(outcome["stdout"]),
        "stderr_tail": _tail_text(outcome["stderr"]),
    }


def _build_check_specs(*, run_id: str) -> list[dict[str, Any]]:
    return [
        {
            "id": "baseline_companion_autonomy_gate",
            "title": "Baseline Freeze + Companion Autonomy Gate",
            "artifact_parser": "companion_autonomy",
            "command": _python_cmd(
                "evals/run_companion_autonomy_audit.py",
                "--run-tag",
                f"{run_id}-companion",
            ),
        },
        {
            "id": "digital_embodiment_manual_smokes",
            "title": "Digital Embodiment Manual Smokes",
            "artifact_parser": "digital_embodiment_smokes",
            "command": _python_cmd(
                "evals/run_digital_embodiment_smokes.py",
                "--run-tag",
                f"{run_id}-smokes",
            ),
        },
        {
            "id": "phase2_access_resource_truth",
            "title": "Phase 2 Access + Resource Truth",
            "command": _python_cmd(
                "-m",
                "pytest",
                "tests/test_digital_body_runtime.py",
                "tests/test_backend_api.py",
                "tests/test_backend_session.py",
                "tests/test_action_packet_contract.py",
                "tests/test_companion_autonomy_runtime.py",
                "tests/test_prepare_turn_runtime.py",
                "-q",
            ),
        },
        {
            "id": "workspace_session_account_truth",
            "title": "Workspace + Session/Account Truth",
            "command": _python_cmd(
                "-m",
                "pytest",
                "tests/test_inspect_workspace_path_tool.py",
                "tests/test_write_workspace_file_tool.py",
                "tests/test_backend_session.py",
                "tests/test_backend_api.py",
                "-q",
            ),
        },
        {
            "id": "saved_material_external_continuity",
            "title": "Saved Material External Continuity",
            "command": _python_cmd(
                "-m",
                "pytest",
                "tests/test_compare_source_refs_tool.py",
                "tests/test_inspect_source_ref_tool.py",
                "tests/test_retrieval_continuity.py",
                "tests/test_prepare_turn_runtime.py",
                "tests/test_world_model_residue.py",
                "-q",
            ),
        },
        {
            "id": "sandbox_contract_truth",
            "title": "Sandbox Contract Truth",
            "command": _python_cmd(
                "-m",
                "pytest",
                "tests/test_digital_body_runtime.py",
                "tests/test_backend_api.py",
                "tests/test_backend_session.py",
                "-q",
            ),
        },
        {
            "id": "unified_writeback_resurfacing",
            "title": "Unified Writeback + Resurfacing",
            "command": _python_cmd(
                "-m",
                "pytest",
                "tests/test_autonomy_writeback.py",
                "tests/test_world_model_residue.py",
                "tests/test_backend_session.py",
                "tests/test_backend_api.py",
                "-q",
            ),
        },
    ]


def _aggregate_overall_status(checks: Sequence[dict[str, Any]]) -> dict[str, Any]:
    rows = [dict(item) for item in checks]
    passed = len([row for row in rows if str(row.get("status") or "") == "passed"])
    failed = len(rows) - passed
    blocking_failures = [
        str(row.get("id") or "").strip()
        for row in rows
        if str(row.get("status") or "") != "passed" and bool(row.get("blocking", True))
    ]
    overall_status = "passed" if not blocking_failures else "failed"
    return {
        "overall_status": overall_status,
        "readiness_status": "digital_embodiment_phase2_in_progress",
        "summary": {
            "total": len(rows),
            "passed": passed,
            "failed": failed,
        },
        "blocking_failure_ids": blocking_failures,
    }


def _compute_pass_streak(statuses: Sequence[str]) -> int:
    streak = 0
    for status in reversed([str(item or "").strip() for item in statuses]):
        if status != "passed":
            break
        streak += 1
    return streak


def _load_previous_reports() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(REPORT_DIR.glob("digital-embodiment-audit-*.json")):
        payload = _load_json(str(path))
        if not payload:
            continue
        rows.append(
            {
                "run_id": str(payload.get("run_id") or "").strip() or path.stem,
                "generated_at": str(payload.get("generated_at") or "").strip(),
                "overall_status": str(payload.get("overall_status") or "").strip(),
                "readiness_status": str(payload.get("readiness_status") or "").strip(),
            }
        )
    return rows


def _recent_audit_history(
    *,
    previous_rows: Sequence[dict[str, Any]],
    current_report: dict[str, Any],
    limit: int = 10,
) -> dict[str, Any]:
    rows = [dict(item) for item in previous_rows]
    rows.append(
        {
            "run_id": str(current_report.get("run_id") or "").strip(),
            "generated_at": str(current_report.get("generated_at") or "").strip(),
            "overall_status": str(current_report.get("overall_status") or "").strip(),
            "readiness_status": str(current_report.get("readiness_status") or "").strip(),
        }
    )
    statuses = [str(item.get("overall_status") or "").strip() for item in rows]
    return {
        "historical_pass_streak": _compute_pass_streak(statuses),
        "recent_audits": rows[-max(1, int(limit or 10)) :],
    }


def _apply_historical_readiness(
    report: dict[str, Any],
    *,
    historical_pass_streak: int,
    freeze_gate_readiness: str,
    companion_readiness: str,
) -> dict[str, Any]:
    result = dict(report)
    summary = dict(result.get("summary") or {})
    ready = (
        str(result.get("overall_status") or "") == "passed"
        and str(freeze_gate_readiness or "") == "freeze_gate_ready"
        and str(companion_readiness or "") == "companion_autonomy_ready"
        and int(historical_pass_streak or 0) >= 3
    )
    result["readiness_status"] = "digital_embodiment_phase2_ready" if ready else "digital_embodiment_phase2_in_progress"
    result["freeze_gate_readiness"] = str(freeze_gate_readiness or "").strip()
    result["companion_readiness"] = str(companion_readiness or "").strip()
    summary["historical_pass_streak"] = int(historical_pass_streak or 0)
    result["summary"] = summary
    return result


def _finalize_report(
    preliminary_report: dict[str, Any],
    *,
    previous_rows: Sequence[dict[str, Any]],
    freeze_gate_readiness: str,
    companion_readiness: str,
) -> dict[str, Any]:
    initial_history = _recent_audit_history(
        previous_rows=previous_rows,
        current_report=preliminary_report,
    )
    finalized = _apply_historical_readiness(
        preliminary_report,
        historical_pass_streak=int(initial_history.get("historical_pass_streak") or 0),
        freeze_gate_readiness=freeze_gate_readiness,
        companion_readiness=companion_readiness,
    )
    final_history = _recent_audit_history(
        previous_rows=previous_rows,
        current_report=finalized,
    )
    finalized["recent_audits"] = final_history.get("recent_audits") or []
    finalized["historical_pass_streak"] = int(final_history.get("historical_pass_streak") or 0)
    summary = dict(finalized.get("summary") or {})
    summary["historical_pass_streak"] = int(final_history.get("historical_pass_streak") or 0)
    finalized["summary"] = summary
    return finalized


def _render_markdown(report: dict[str, Any]) -> str:
    summary = dict(report.get("summary") or {})
    lines = [
        f"# Digital Embodiment Phase 2 Audit ({report.get('run_id', 'unknown')})",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
        f"Freeze Gate Readiness: `{report.get('freeze_gate_readiness', 'unknown')}`",
        f"Companion Autonomy Readiness: `{report.get('companion_readiness', 'unknown')}`",
        "",
        "## Summary",
        "",
        f"- Total checks: `{summary.get('total', 0)}`",
        f"- Passed: `{summary.get('passed', 0)}`",
        f"- Failed: `{summary.get('failed', 0)}`",
        f"- Historical pass streak: `{summary.get('historical_pass_streak', 0)}`",
        "",
        "## Recent Audit History",
        "",
        "| Run | Generated At | Overall | Readiness |",
        "| --- | --- | --- | --- |",
    ]
    for row in report.get("recent_audits") or []:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| `{row.get('run_id', '')}` | `{row.get('generated_at', '')}` | `{row.get('overall_status', '')}` | `{row.get('readiness_status', '')}` |"
        )

    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Check | Status | Duration (s) |",
            "| --- | --- | ---: |",
        ]
    )
    for row in report.get("checks") or []:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| `{row.get('id', '')}` | `{row.get('status', '')}` | {float(row.get('duration_s') or 0.0):.3f} |"
        )

    for row in report.get("checks") or []:
        if not isinstance(row, dict):
            continue
        lines.extend(
            [
                "",
                f"## {row.get('title', row.get('id', 'unknown'))}",
                "",
                f"- Check Id: `{row.get('id', '')}`",
                f"- Status: `{row.get('status', '')}`",
                f"- Command: `{row.get('command', '')}`",
            ]
        )
        for reason in row.get("failure_reasons") or []:
            lines.append(f"- Failure: `{reason}`")
        artifacts = row.get("artifacts") if isinstance(row.get("artifacts"), dict) else {}
        if artifacts:
            lines.append("- Artifacts:")
            for key in sorted(artifacts):
                lines.append(f"  - `{key}`: `{artifacts.get(key, '')}`")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Digital Embodiment closure audit.")
    parser.add_argument("--run-tag", default="", help="Optional suffix for report filenames.")
    args = parser.parse_args()

    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    checks: list[dict[str, Any]] = []
    for spec in _build_check_specs(run_id=run_id):
        checks.append(
            _check(
                spec["id"],
                spec["title"],
                spec["command"],
                artifact_parser=str(spec.get("artifact_parser") or ""),
            )
        )

    aggregate = _aggregate_overall_status(checks)
    baseline_check = next(
        (row for row in checks if str(row.get("id") or "") == "baseline_companion_autonomy_gate"),
        {},
    )
    baseline_artifacts = baseline_check.get("artifacts") if isinstance(baseline_check.get("artifacts"), dict) else {}
    report = {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "checks": checks,
        **aggregate,
    }
    previous = _load_previous_reports()
    report = _finalize_report(
        report,
        previous_rows=previous,
        freeze_gate_readiness=str(baseline_artifacts.get("freeze_gate_readiness") or ""),
        companion_readiness=str(baseline_artifacts.get("companion_readiness") or ""),
    )
    json_path = REPORT_DIR / f"digital-embodiment-audit-{run_id}.json"
    md_path = REPORT_DIR / f"digital-embodiment-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(f"[digital-embodiment] json={json_path}")
    print(f"[digital-embodiment] md={md_path}")
    print(f"[digital-embodiment] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[digital-embodiment] readiness={report.get('readiness_status', 'unknown')}")


if __name__ == "__main__":
    main()
