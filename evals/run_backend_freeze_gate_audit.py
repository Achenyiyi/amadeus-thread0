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

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency shim
    load_dotenv = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

if load_dotenv is not None:
    load_dotenv(PROJECT_ROOT / ".env")


FREEZE_GATE_JSON_RE = re.compile(r"^\[freeze-gate\]\s+json=(.+)$", re.MULTILINE)
FREEZE_GATE_MD_RE = re.compile(r"^\[freeze-gate\]\s+md=(.+)$", re.MULTILINE)
FREEZE_GATE_STATUS_RE = re.compile(r"^\[freeze-gate\]\s+overall_status=(.+)$", re.MULTILINE)


def _python_cmd(*args: str) -> list[str]:
    return [sys.executable, *args]


def _runtime_model_summary() -> str:
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from amadeus_thread0.modeling import runtime_model_summary

        return str(runtime_model_summary() or "").strip()
    except Exception as exc:  # pragma: no cover - defensive metadata path
        return f"unavailable: {exc.__class__.__name__}"


def _base_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    return env


def _tail_text(text: str, *, limit: int = 2400) -> str:
    content = str(text or "").strip()
    if len(content) <= limit:
        return content
    return content[-limit:]


def _format_command(command: Sequence[str]) -> str:
    return subprocess.list2cmdline([str(part) for part in command])


def _parse_freeze_gate_artifacts(stdout: str) -> dict[str, str]:
    text = str(stdout or "")
    payload: dict[str, str] = {}
    json_match = FREEZE_GATE_JSON_RE.search(text)
    md_match = FREEZE_GATE_MD_RE.search(text)
    status_match = FREEZE_GATE_STATUS_RE.search(text)
    if json_match:
        payload["json"] = json_match.group(1).strip()
    if md_match:
        payload["md"] = md_match.group(1).strip()
    if status_match:
        payload["overall_status"] = status_match.group(1).strip()
    return payload


def _run_command(command: Sequence[str], *, cwd: Path) -> dict[str, Any]:
    start = time.time()
    completed = subprocess.run(
        [str(part) for part in command],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_base_env(),
    )
    duration_s = round(time.time() - start, 3)
    return {
        "returncode": int(completed.returncode),
        "stdout": str(completed.stdout or ""),
        "stderr": str(completed.stderr or ""),
        "duration_s": duration_s,
    }


def _evaluate_check(spec: dict[str, Any], outcome: dict[str, Any]) -> dict[str, Any]:
    status = "passed" if int(outcome.get("returncode") or 0) == 0 else "failed"
    failure_reasons: list[str] = []
    artifacts: dict[str, Any] = {}

    if str(spec.get("artifact_parser") or "") == "freeze_gate":
        artifacts = _parse_freeze_gate_artifacts(str(outcome.get("stdout") or ""))
        smoke_status = str(artifacts.get("overall_status") or "").strip()
        if smoke_status and smoke_status != "passed":
            status = "failed"
            failure_reasons.append(f"freeze_gate_overall_status={smoke_status}")
        for key in ("json", "md"):
            artifact_path = str(artifacts.get(key) or "").strip()
            if key in set(spec.get("required_artifacts") or []) and not artifact_path:
                status = "failed"
                failure_reasons.append(f"missing_{key}_artifact")
            if artifact_path and not Path(artifact_path).exists():
                status = "failed"
                failure_reasons.append(f"missing_file:{key}")

    expected_stdout = str(spec.get("expect_stdout_contains") or "").strip()
    if expected_stdout and expected_stdout not in str(outcome.get("stdout") or ""):
        status = "failed"
        failure_reasons.append(f"stdout_missing:{expected_stdout}")

    return {
        "id": str(spec.get("id") or "").strip(),
        "title": str(spec.get("title") or "").strip(),
        "category": str(spec.get("category") or "").strip(),
        "blocking": bool(spec.get("blocking", True)),
        "status": status,
        "duration_s": float(outcome.get("duration_s") or 0.0),
        "returncode": int(outcome.get("returncode") or 0),
        "command": _format_command(spec.get("command") or []),
        "artifacts": artifacts,
        "failure_reasons": failure_reasons,
        "stdout_tail": _tail_text(str(outcome.get("stdout") or "")),
        "stderr_tail": _tail_text(str(outcome.get("stderr") or "")),
    }


def _aggregate_overall_status(checks: Sequence[dict[str, Any]]) -> dict[str, Any]:
    rows = [dict(item) for item in checks]
    passed = len([item for item in rows if str(item.get("status") or "") == "passed"])
    failed = len(rows) - passed
    blocking_failures = [
        str(item.get("id") or "").strip()
        for item in rows
        if str(item.get("status") or "") != "passed" and bool(item.get("blocking", True))
    ]
    warning_failures = [
        str(item.get("id") or "").strip()
        for item in rows
        if str(item.get("status") or "") != "passed" and not bool(item.get("blocking", True))
    ]
    overall_status = "passed" if not blocking_failures else "failed"
    readiness_status = "freeze_gate_candidate" if overall_status == "passed" else "backend_maturation_required"
    return {
        "overall_status": overall_status,
        "readiness_status": readiness_status,
        "summary": {
            "total": len(rows),
            "passed": passed,
            "failed": failed,
            "blocking_failures": len(blocking_failures),
            "warning_failures": len(warning_failures),
        },
        "blocking_failure_ids": blocking_failures,
        "warning_failure_ids": warning_failures,
    }


def _compute_pass_streak(statuses: Sequence[str]) -> int:
    streak = 0
    for status in reversed([str(item or "").strip() for item in statuses]):
        if status != "passed":
            break
        streak += 1
    return streak


def _load_previous_audit_rows(*, report_dir: Path) -> list[dict[str, Any]]:
    previous_rows: list[dict[str, Any]] = []
    for path in sorted(report_dir.glob("backend-freeze-gate-audit-*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        previous_rows.append(
            {
                "run_id": str(payload.get("run_id") or "").strip() or path.stem,
                "generated_at": str(payload.get("generated_at") or "").strip(),
                "overall_status": str(payload.get("overall_status") or "").strip(),
                "readiness_status": str(payload.get("readiness_status") or "").strip(),
                "path": str(path),
            }
        )
    return previous_rows


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
            "path": "(current run)",
        }
    )
    statuses = [str(item.get("overall_status") or "").strip() for item in rows]
    return {
        "historical_pass_streak": _compute_pass_streak(statuses),
        "recent_audits": rows[-max(1, int(limit or 10)) :],
    }


def _apply_historical_readiness(aggregate: dict[str, Any], *, historical_pass_streak: int) -> dict[str, Any]:
    result = dict(aggregate)
    summary = dict(result.get("summary") or {})
    if str(result.get("overall_status") or "") != "passed":
        result["readiness_status"] = "backend_maturation_required"
    elif int(historical_pass_streak or 0) >= 3:
        result["readiness_status"] = "freeze_gate_ready"
    else:
        result["readiness_status"] = "freeze_gate_candidate"
    summary["historical_pass_streak"] = int(historical_pass_streak or 0)
    result["summary"] = summary
    return result


def _render_markdown(report: dict[str, Any]) -> str:
    summary = dict(report.get("summary") or {})
    lines = [
        f"# Backend Freeze Gate Audit ({report.get('run_id', 'unknown')})",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Model: {report.get('model_summary', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
        "",
        "## Summary",
        "",
        f"- Total checks: `{summary.get('total', 0)}`",
        f"- Passed: `{summary.get('passed', 0)}`",
        f"- Failed: `{summary.get('failed', 0)}`",
        f"- Blocking failures: `{summary.get('blocking_failures', 0)}`",
        f"- Warning failures: `{summary.get('warning_failures', 0)}`",
        f"- Historical pass streak: `{summary.get('historical_pass_streak', 0)}`",
    ]

    if report.get("blocking_failure_ids"):
        lines.extend(
            [
                "",
                "## Blocking Failures",
                "",
            ]
        )
        for check_id in report.get("blocking_failure_ids") or []:
            lines.append(f"- `{check_id}`")

    if report.get("warning_failure_ids"):
        lines.extend(
            [
                "",
                "## Warning Failures",
                "",
            ]
        )
        for check_id in report.get("warning_failure_ids") or []:
            lines.append(f"- `{check_id}`")

    lines.extend(
        [
            "",
            "## Recent Audit History",
            "",
            "| Run | Generated At | Overall | Readiness |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in report.get("recent_audits") or []:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| `{row.get('run_id', '')}` | `{row.get('generated_at', '')}` | `{row.get('overall_status', '')}` | `{row.get('readiness_status', '')}` |"
        )

    lines.extend(
        [
            "",
            "## Check Matrix",
            "",
            "| Check | Category | Status | Duration (s) |",
            "| --- | --- | --- | ---: |",
        ]
    )
    for row in report.get("checks") or []:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| `{row.get('id', '')}` | `{row.get('category', '')}` | `{row.get('status', '')}` | {float(row.get('duration_s') or 0.0):.3f} |"
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
                f"- Category: `{row.get('category', '')}`",
                f"- Blocking: `{bool(row.get('blocking', True))}`",
                f"- Status: `{row.get('status', 'unknown')}`",
                f"- Duration: `{float(row.get('duration_s') or 0.0):.3f}s`",
                f"- Return Code: `{int(row.get('returncode') or 0)}`",
                f"- Command: `{row.get('command', '')}`",
            ]
        )
        if row.get("artifacts"):
            lines.extend(["- Artifacts:"])
            for key, value in dict(row.get("artifacts") or {}).items():
                lines.append(f"  - `{key}`: `{value}`")
        if row.get("failure_reasons"):
            lines.extend(["- Failure Reasons:"])
            for reason in row.get("failure_reasons") or []:
                lines.append(f"  - `{reason}`")
        if row.get("stdout_tail"):
            lines.extend(["", "### Stdout Tail", "", "```text", str(row.get("stdout_tail") or ""), "```"])
        if row.get("stderr_tail"):
            lines.extend(["", "### Stderr Tail", "", "```text", str(row.get("stderr_tail") or ""), "```"])

    return "\n".join(lines).strip() + "\n"


def _write_report(report: dict[str, Any]) -> tuple[Path, Path]:
    ts = time.strftime("%Y%m%d-%H%M%S")
    run_id = str(report.get("run_id") or uuid.uuid4().hex[:8]).strip()
    json_path = REPORT_DIR / f"backend-freeze-gate-audit-{ts}-{run_id}.json"
    md_path = REPORT_DIR / f"backend-freeze-gate-audit-{ts}-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    return json_path, md_path


def _build_check_specs(*, case_timeout_s: int, smoke_run_tag: str) -> list[dict[str, Any]]:
    return [
        {
            "id": "py_compile_runtime_contract",
            "title": "PyCompile Runtime Contract",
            "category": "compile",
            "blocking": True,
            "command": _python_cmd(
                "-m",
                "py_compile",
                "amadeus_thread0/agent.py",
                "amadeus_thread0/graph.py",
                "amadeus_thread0/runtime/final_state.py",
            ),
        },
        {
            "id": "py_compile_core_loop",
            "title": "PyCompile Core Loop Modules",
            "category": "compile",
            "blocking": True,
            "command": _python_cmd(
                "-m",
                "py_compile",
                "amadeus_thread0/graph_parts/prepare_turn_runtime.py",
                "amadeus_thread0/graph_parts/behavior_runtime.py",
                "amadeus_thread0/graph_parts/response_finalize.py",
            ),
        },
        {
            "id": "handoff_contract_baseline",
            "title": "Backend Handoff Contract Baseline",
            "category": "pytest",
            "blocking": True,
            "command": _python_cmd(
                "-m",
                "pytest",
                "tests/test_final_state.py",
                "tests/test_backend_session.py",
                "tests/test_backend_api.py",
                "tests/test_freeze_gate_smokes.py",
                "tests/test_subjective_review_pack.py",
                "tests/test_memory_guard.py",
                "tests/test_session_orchestrator.py",
                "tests/test_cli_views.py",
                "-q",
            ),
        },
        {
            "id": "core_loop_chain",
            "title": "Core Loop Chain Regression",
            "category": "pytest",
            "blocking": True,
            "command": _python_cmd(
                "-m",
                "pytest",
                "tests/test_appraisal_calibration.py",
                "tests/test_behavior_runtime_alignment.py",
                "tests/test_prepare_turn_runtime.py",
                "-q",
            ),
        },
        {
            "id": "agents_graph_subset",
            "title": "AGENTS Required Graph Subset",
            "category": "pytest",
            "blocking": True,
            "command": _python_cmd(
                "-m",
                "pytest",
                "tests/test_daily_surface_gating.py",
                "tests/test_generation_profile.py",
                "tests/test_dialogue_mode_counterpart.py",
                "tests/test_world_model_residue.py",
                "tests/test_subjective_review_pack.py",
                "-q",
            ),
        },
        {
            "id": "graph_build_entrypoint",
            "title": "Graph Build Entrypoint",
            "category": "runtime",
            "blocking": True,
            "expect_stdout_contains": "CompiledStateGraph",
            "command": _python_cmd(
                "-c",
                "from amadeus_thread0.agent import agent; print(type(agent).__name__)",
            ),
        },
        {
            "id": "freeze_gate_smokes",
            "title": "Freeze Gate Smoke Packs",
            "category": "smoke",
            "blocking": True,
            "artifact_parser": "freeze_gate",
            "required_artifacts": ("json", "md"),
            "command": _python_cmd(
                "evals/run_freeze_gate_smokes.py",
                "--case-timeout-s",
                str(max(1, int(case_timeout_s or 180))),
                "--run-tag",
                smoke_run_tag,
            ),
        },
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a single backend freeze-gate audit and write a report.")
    parser.add_argument("--case-timeout-s", type=int, default=180, help="Per-case timeout passed to freeze-gate smokes.")
    parser.add_argument("--run-tag", default="", help="Optional stable audit run tag.")
    args = parser.parse_args()

    run_id = str(args.run_tag or uuid.uuid4().hex[:8]).strip()
    checks: list[dict[str, Any]] = []
    for spec in _build_check_specs(case_timeout_s=int(args.case_timeout_s or 180), smoke_run_tag=run_id):
        print(f"[backend-freeze-gate] running {spec['id']}")
        outcome = _run_command(spec["command"], cwd=PROJECT_ROOT)
        checks.append(_evaluate_check(spec, outcome))

    aggregate = _aggregate_overall_status(checks)
    report = {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model_summary": _runtime_model_summary(),
        "checks": checks,
        **aggregate,
    }
    previous_rows = _load_previous_audit_rows(report_dir=REPORT_DIR)
    history = _recent_audit_history(previous_rows=previous_rows, current_report=report)
    report.update(history)
    report.update(_apply_historical_readiness(report, historical_pass_streak=int(history.get("historical_pass_streak") or 0)))
    report["recent_audits"] = _recent_audit_history(previous_rows=previous_rows, current_report=report).get("recent_audits") or []
    json_path, md_path = _write_report(report)
    print("[backend-freeze-gate] json=" + str(json_path))
    print("[backend-freeze-gate] md=" + str(md_path))
    print("[backend-freeze-gate] overall_status=" + str(report.get("overall_status") or "unknown"))
    print("[backend-freeze-gate] readiness=" + str(report.get("readiness_status") or "unknown"))
    print("[backend-freeze-gate] historical_pass_streak=" + str(report.get("historical_pass_streak") or 0))
    return 0 if str(report.get("overall_status") or "") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
