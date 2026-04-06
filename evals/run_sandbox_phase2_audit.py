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

LIVE_JSON_RE = re.compile(r"^\[live-browser-runtime\]\s+json=(.+)$", re.MULTILINE)
LIVE_MD_RE = re.compile(r"^\[live-browser-runtime\]\s+md=(.+)$", re.MULTILINE)
LIVE_STATUS_RE = re.compile(r"^\[live-browser-runtime\]\s+overall_status=(.+)$", re.MULTILINE)
LIVE_READY_RE = re.compile(r"^\[live-browser-runtime\]\s+readiness=(.+)$", re.MULTILINE)
SMOKE_JSON_RE = re.compile(r"^\[sandbox-phase2-smokes\]\s+json=(.+)$", re.MULTILINE)
SMOKE_MD_RE = re.compile(r"^\[sandbox-phase2-smokes\]\s+md=(.+)$", re.MULTILINE)
SMOKE_STATUS_RE = re.compile(r"^\[sandbox-phase2-smokes\]\s+overall_status=(.+)$", re.MULTILINE)


def _python(*args: str) -> list[str]:
    return [sys.executable, *args]


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("AMADEUS_BROWSER_HEADLESS", "1")
    return env


def _load_json(path: str) -> dict[str, Any]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")) if path and Path(path).exists() else {}
    except Exception:
        return {}


def _tail(text: str, limit: int = 2400) -> str:
    text = str(text or "")
    return text if len(text) <= limit else text[-limit:]


def _fmt(command: Sequence[str]) -> str:
    return subprocess.list2cmdline([str(part) for part in command])


def _run(command: Sequence[str]) -> dict[str, Any]:
    start = time.time()
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
        "duration_s": round(time.time() - start, 3),
    }


def _parse_live_browser_baseline(stdout: str) -> dict[str, str]:
    data: dict[str, str] = {}
    text = str(stdout or "")
    for regex, key in (
        (LIVE_JSON_RE, "json"),
        (LIVE_MD_RE, "md"),
        (LIVE_STATUS_RE, "overall_status"),
        (LIVE_READY_RE, "readiness"),
    ):
        match = regex.search(text)
        if match:
            data[key] = match.group(1).strip()
    payload = _load_json(data.get("json", ""))
    if payload:
        data["freeze_gate_readiness"] = str(payload.get("freeze_gate_readiness") or "").strip()
        data["companion_readiness"] = str(payload.get("companion_readiness") or "").strip()
        data["digital_embodiment_readiness"] = str(payload.get("digital_embodiment_readiness") or "").strip()
        data["sandbox_readiness"] = str(payload.get("sandbox_readiness") or "").strip()
        data["skills_readiness"] = str(payload.get("skills_readiness") or "").strip()
        data["live_browser_readiness"] = str(payload.get("readiness_status") or "").strip()
    return data


def _parse_smokes(stdout: str) -> dict[str, str]:
    data: dict[str, str] = {}
    text = str(stdout or "")
    for regex, key in (
        (SMOKE_JSON_RE, "json"),
        (SMOKE_MD_RE, "md"),
        (SMOKE_STATUS_RE, "overall_status"),
    ):
        match = regex.search(text)
        if match:
            data[key] = match.group(1).strip()
    payload = _load_json(data.get("json", ""))
    if payload:
        data["passed"] = str(payload.get("passed") or 0)
        data["failed"] = str(payload.get("failed") or 0)
    return data


def _check(id: str, title: str, command: Sequence[str], *, parser: str = "") -> dict[str, Any]:
    outcome = _run(command)
    status = "passed" if int(outcome["returncode"]) == 0 else "failed"
    artifacts: dict[str, Any] = {}
    failures: list[str] = []
    if parser == "live_browser_baseline":
        artifacts = _parse_live_browser_baseline(outcome.get("stdout", ""))
        if str(artifacts.get("overall_status") or "") != "passed":
            status = "failed"
            failures.append("live_browser_overall_status=" + str(artifacts.get("overall_status") or "unknown"))
        for key in ("json", "md"):
            if not str(artifacts.get(key) or "").strip() or not Path(str(artifacts.get(key) or "")).exists():
                status = "failed"
                failures.append("missing_" + key + "_artifact")
    elif parser == "phase2_smokes":
        artifacts = _parse_smokes(outcome.get("stdout", ""))
        if str(artifacts.get("overall_status") or "") != "passed":
            status = "failed"
            failures.append("sandbox_phase2_smokes_overall_status=" + str(artifacts.get("overall_status") or "unknown"))
        for key in ("json", "md"):
            if not str(artifacts.get(key) or "").strip() or not Path(str(artifacts.get(key) or "")).exists():
                status = "failed"
                failures.append("missing_" + key + "_artifact")
    return {
        "id": id,
        "title": title,
        "blocking": True,
        "command": _fmt(command),
        "status": status,
        "returncode": int(outcome["returncode"]),
        "duration_s": float(outcome["duration_s"]),
        "artifacts": artifacts,
        "failure_reasons": failures,
        "stdout_tail": _tail(outcome["stdout"]),
        "stderr_tail": _tail(outcome["stderr"]),
    }


def _build_check_specs(run_id: str) -> list[dict[str, Any]]:
    return [
        {
            "id": "baseline_live_browser_gate",
            "title": "Baseline Live Browser Gate",
            "parser": "live_browser_baseline",
            "command": _python("evals/run_live_browser_runtime_audit.py", "--run-tag", f"{run_id}-baseline"),
        },
        {
            "id": "sandbox_phase2_manual_smokes",
            "title": "Sandbox Phase 2 Manual Smokes",
            "parser": "phase2_smokes",
            "command": _python("evals/run_sandbox_phase2_smokes.py", "--run-tag", f"{run_id}-smokes"),
        },
        {
            "id": "sandbox_phase2_runtime_contract",
            "title": "Sandbox Phase 2 Runtime Contract",
            "command": _python(
                "-m",
                "pytest",
                "tests/test_sandbox_runner.py",
                "tests/test_docker_sandbox_runner.py",
                "tests/test_sandbox_execution_runtime.py",
                "tests/test_sandbox_backend_contract.py",
                "tests/test_sandbox_phase2_backend_contract.py",
                "tests/test_sandbox_phase2_repo_fixture.py",
                "-q",
            ),
        },
        {
            "id": "sandbox_phase2_backend_writeback_residue",
            "title": "Sandbox Phase 2 Backend Writeback + Residue",
            "command": _python(
                "-m",
                "pytest",
                "tests/test_backend_session.py",
                "tests/test_backend_api.py",
                "tests/test_tool_approval_policy.py",
                "tests/test_autonomy_writeback.py",
                "tests/test_cli_views.py",
                "tests/test_world_model_residue.py",
                "-k",
                "sandbox or attach_repo_root or workspace_root_attached",
                "-q",
            ),
        },
    ]


def _overall(checks: Sequence[dict[str, Any]]) -> dict[str, Any]:
    rows = [dict(item) for item in checks]
    failed = [
        str(row.get("id") or "")
        for row in rows
        if str(row.get("status") or "") != "passed" and bool(row.get("blocking", True))
    ]
    return {
        "overall_status": "passed" if not failed else "failed",
        "readiness_status": "sandbox_embodied_execution_phase2_in_progress",
        "summary": {"total": len(rows), "passed": len(rows) - len(failed), "failed": len(failed)},
        "blocking_failure_ids": failed,
    }


def _pass_streak(statuses: Sequence[str]) -> int:
    streak = 0
    for status in reversed([str(item or "").strip() for item in statuses]):
        if status != "passed":
            break
        streak += 1
    return streak


def _history_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(REPORT_DIR.glob("sandbox-phase2-audit-*.json")):
        payload = _load_json(str(path))
        if payload:
            rows.append(
                {
                    "run_id": str(payload.get("run_id") or path.stem),
                    "generated_at": str(payload.get("generated_at") or ""),
                    "overall_status": str(payload.get("overall_status") or ""),
                    "readiness_status": str(payload.get("readiness_status") or ""),
                }
            )
    return rows


def _finalize(report: dict[str, Any], previous: Sequence[dict[str, Any]], baseline: dict[str, Any]) -> dict[str, Any]:
    rows = [dict(item) for item in previous] + [
        {
            "run_id": str(report.get("run_id") or ""),
            "generated_at": str(report.get("generated_at") or ""),
            "overall_status": str(report.get("overall_status") or ""),
            "readiness_status": str(report.get("readiness_status") or ""),
        }
    ]
    streak = _pass_streak([str(row.get("overall_status") or "") for row in rows])
    ready = (
        str(report.get("overall_status") or "") == "passed"
        and str(baseline.get("freeze_gate_readiness") or "") == "freeze_gate_ready"
        and str(baseline.get("companion_readiness") or "") == "companion_autonomy_ready"
        and str(baseline.get("digital_embodiment_readiness") or "") == "digital_embodiment_phase2_ready"
        and str(baseline.get("sandbox_readiness") or "") == "sandbox_embodied_execution_phase1_ready"
        and str(baseline.get("skills_readiness") or "") == "skills_ecosystem_ready"
        and str(baseline.get("live_browser_readiness") or "") == "live_browser_runtime_phase1_ready"
        and streak >= 3
    )
    report["readiness_status"] = (
        "sandbox_embodied_execution_phase2_ready" if ready else "sandbox_embodied_execution_phase2_in_progress"
    )
    report["freeze_gate_readiness"] = str(baseline.get("freeze_gate_readiness") or "")
    report["companion_readiness"] = str(baseline.get("companion_readiness") or "")
    report["digital_embodiment_readiness"] = str(baseline.get("digital_embodiment_readiness") or "")
    report["sandbox_readiness"] = str(baseline.get("sandbox_readiness") or "")
    report["skills_readiness"] = str(baseline.get("skills_readiness") or "")
    report["live_browser_readiness"] = str(baseline.get("live_browser_readiness") or "")
    final_rows = [dict(item) for item in previous] + [
        {
            "run_id": str(report.get("run_id") or ""),
            "generated_at": str(report.get("generated_at") or ""),
            "overall_status": str(report.get("overall_status") or ""),
            "readiness_status": str(report.get("readiness_status") or ""),
        }
    ]
    report["recent_audits"] = final_rows[-10:]
    report["historical_pass_streak"] = _pass_streak([str(row.get("overall_status") or "") for row in final_rows])
    report["summary"]["historical_pass_streak"] = report["historical_pass_streak"]
    return report


def _render(report: dict[str, Any]) -> str:
    lines = [
        f"# Sandbox Embodied Execution Phase 2 Audit ({report.get('run_id', 'unknown')})",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
        f"Freeze Gate Readiness: `{report.get('freeze_gate_readiness', 'unknown')}`",
        f"Companion Autonomy Readiness: `{report.get('companion_readiness', 'unknown')}`",
        f"Digital Embodiment Readiness: `{report.get('digital_embodiment_readiness', 'unknown')}`",
        f"Sandbox Phase 1 Readiness: `{report.get('sandbox_readiness', 'unknown')}`",
        f"Skills Readiness: `{report.get('skills_readiness', 'unknown')}`",
        f"Live Browser Readiness: `{report.get('live_browser_readiness', 'unknown')}`",
        "",
        "## Summary",
        "",
        f"- Total checks: `{report.get('summary', {}).get('total', 0)}`",
        f"- Passed: `{report.get('summary', {}).get('passed', 0)}`",
        f"- Failed: `{report.get('summary', {}).get('failed', 0)}`",
        f"- Historical pass streak: `{report.get('summary', {}).get('historical_pass_streak', 0)}`",
        "",
        "## Recent Audit History",
        "",
        "| Run | Generated At | Overall | Readiness |",
        "| --- | --- | --- | --- |",
    ]
    for row in report.get("recent_audits") or []:
        lines.append(
            f"| `{row.get('run_id', '')}` | `{row.get('generated_at', '')}` | `{row.get('overall_status', '')}` | `{row.get('readiness_status', '')}` |"
        )
    lines.extend(["", "## Checks", "", "| Check | Status | Duration (s) |", "| --- | --- | ---: |"])
    for row in report.get("checks") or []:
        lines.append(
            f"| `{row.get('id', '')}` | `{row.get('status', '')}` | {float(row.get('duration_s') or 0.0):.3f} |"
        )
    for row in report.get("checks") or []:
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
    parser = argparse.ArgumentParser(description="Run Sandbox Embodied Execution Phase 2 audit.")
    parser.add_argument("--run-tag", default="")
    args = parser.parse_args()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    checks = [
        _check(spec["id"], spec["title"], spec["command"], parser=str(spec.get("parser") or ""))
        for spec in _build_check_specs(run_id)
    ]
    report = {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "checks": checks,
        **_overall(checks),
    }
    baseline = next(
        (
            row.get("artifacts")
            for row in checks
            if str(row.get("id") or "") == "baseline_live_browser_gate"
            and isinstance(row.get("artifacts"), dict)
        ),
        {},
    ) or {}
    report = _finalize(report, _history_rows(), baseline)
    json_path = REPORT_DIR / f"sandbox-phase2-audit-{run_id}.json"
    md_path = REPORT_DIR / f"sandbox-phase2-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render(report), encoding="utf-8")
    print(f"[sandbox-phase2] json={json_path}")
    print(f"[sandbox-phase2] md={md_path}")
    print(f"[sandbox-phase2] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[sandbox-phase2] readiness={report.get('readiness_status', 'unknown')}")


if __name__ == "__main__":
    main()
