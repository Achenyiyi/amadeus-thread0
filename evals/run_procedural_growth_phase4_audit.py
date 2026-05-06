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

SMOKES_JSON_RE = re.compile(r"^\[procedural-growth-phase4-smokes\]\s+json=(.+)$", re.MULTILINE)
SMOKES_MD_RE = re.compile(r"^\[procedural-growth-phase4-smokes\]\s+md=(.+)$", re.MULTILINE)
SMOKES_STATUS_RE = re.compile(r"^\[procedural-growth-phase4-smokes\]\s+overall_status=(.+)$", re.MULTILINE)


def _python(*args: str) -> list[str]:
    return [sys.executable, *args]


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    return env


def _tail(text: str, *, limit: int = 2400) -> str:
    value = str(text or "").strip()
    return value if len(value) <= limit else value[-limit:]


def _format_command(command: Sequence[str]) -> str:
    return subprocess.list2cmdline([str(part) for part in command])


def _load_json(path: str) -> dict[str, Any]:
    file_path = Path(str(path or ""))
    if not file_path.exists():
        return {}
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        return dict(payload) if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _parse_smoke_stdout(stdout: str) -> dict[str, str]:
    text = str(stdout or "")
    parsed: dict[str, str] = {}
    json_match = SMOKES_JSON_RE.search(text)
    md_match = SMOKES_MD_RE.search(text)
    status_match = SMOKES_STATUS_RE.search(text)
    if json_match:
        parsed["json"] = json_match.group(1).strip()
    if md_match:
        parsed["md"] = md_match.group(1).strip()
    if status_match:
        parsed["overall_status"] = status_match.group(1).strip()
    report = _load_json(parsed.get("json") or "")
    if report:
        parsed["report_overall_status"] = str(report.get("overall_status") or "").strip()
        parsed["passed"] = str(report.get("passed") or 0)
        parsed["failed"] = str(report.get("failed") or 0)
    return parsed


def _run_command(command: Sequence[str]) -> dict[str, Any]:
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


def _build_check_specs(run_id: str) -> list[dict[str, Any]]:
    return [
        {
            "id": "procedural_recovery_unit_tests",
            "title": "Procedural Recovery Unit Tests",
            "command": _python("-m", "pytest", "tests/test_procedural_recovery.py", "-q"),
        },
        {
            "id": "procedural_recovery_planning_tests",
            "title": "Procedural Recovery Planning Tests",
            "command": _python(
                "-m",
                "pytest",
                "tests/test_procedural_planning.py",
                "tests/test_procedural_growth_writeback.py",
                "-k",
                "recovery",
                "-q",
            ),
        },
        {
            "id": "procedural_recovery_backend_readback_tests",
            "title": "Procedural Recovery Backend Readback Tests",
            "command": _python(
                "-m",
                "pytest",
                "tests/test_backend_api.py",
                "tests/test_backend_session.py",
                "tests/test_cli_views.py",
                "-k",
                "procedural_recovery",
                "-q",
            ),
        },
        {
            "id": "procedural_growth_phase4_smokes",
            "title": "Procedural Growth Phase 4 Smokes",
            "command": _python("evals/run_procedural_growth_phase4_smokes.py", "--run-tag", f"{run_id}-smokes"),
            "parser": "smokes",
        },
    ]


def _check(
    id: str,
    title: str,
    command: Sequence[str],
    *,
    parser: str = "",
    blocking: bool = True,
) -> dict[str, Any]:
    outcome = _run_command(command)
    status = "passed" if int(outcome.get("returncode") or 0) == 0 else "failed"
    artifacts: dict[str, Any] = {}
    failure_reasons: list[str] = []
    if parser == "smokes":
        artifacts = _parse_smoke_stdout(str(outcome.get("stdout") or ""))
        json_path = str(artifacts.get("json") or "").strip()
        md_path = str(artifacts.get("md") or "").strip()
        smoke_status = str(artifacts.get("overall_status") or artifacts.get("report_overall_status") or "").strip()
        if not json_path:
            status = "failed"
            failure_reasons.append("missing_json_artifact")
        elif not Path(json_path).exists():
            status = "failed"
            failure_reasons.append("missing_file:json")
        if not md_path:
            status = "failed"
            failure_reasons.append("missing_md_artifact")
        elif not Path(md_path).exists():
            status = "failed"
            failure_reasons.append("missing_file:md")
        if smoke_status != "passed":
            status = "failed"
            failure_reasons.append("procedural_growth_phase4_smokes_overall_status=" + (smoke_status or "unknown"))
        if str(artifacts.get("failed") or "0") not in {"", "0"}:
            status = "failed"
            failure_reasons.append("procedural_growth_phase4_smokes_failed=" + str(artifacts.get("failed")))
    elif status != "passed":
        failure_reasons.append("command_returncode=" + str(outcome.get("returncode")))
    return {
        "id": id,
        "title": title,
        "blocking": bool(blocking),
        "command": _format_command(command),
        "status": status,
        "returncode": int(outcome.get("returncode") or 0),
        "duration_s": float(outcome.get("duration_s") or 0.0),
        "artifacts": artifacts,
        "failure_reasons": failure_reasons,
        "stdout_tail": _tail(str(outcome.get("stdout") or "")),
        "stderr_tail": _tail(str(outcome.get("stderr") or "")),
    }


def _aggregate_report(checks: Sequence[dict[str, Any]]) -> dict[str, Any]:
    rows = [dict(item) for item in checks]
    blocking_failure_ids = [
        str(row.get("id") or "")
        for row in rows
        if bool(row.get("blocking", True)) and str(row.get("status") or "") != "passed"
    ]
    failed = len([row for row in rows if str(row.get("status") or "") != "passed"])
    passed = len(rows) - failed
    overall_status = "failed" if blocking_failure_ids else "passed"
    return {
        "overall_status": overall_status,
        "readiness_status": (
            "procedural_growth_phase4_ready"
            if overall_status == "passed"
            else "procedural_growth_phase4_in_progress"
        ),
        "blocking_failure_ids": blocking_failure_ids,
        "summary": {
            "checks_total": len(rows),
            "checks_passed": passed,
            "checks_failed": failed,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = dict(report.get("summary") or {})
    lines = [
        f"# Procedural Growth Phase 4 Audit ({report.get('run_id', 'unknown')})",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
        "",
        "## Summary",
        "",
        f"- Checks total: `{summary.get('checks_total', 0)}`",
        f"- Checks passed: `{summary.get('checks_passed', 0)}`",
        f"- Checks failed: `{summary.get('checks_failed', 0)}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Blocking | Duration (s) |",
        "| --- | --- | --- | ---: |",
    ]
    for row in report.get("checks") or []:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| `{row.get('id', '')}` | `{row.get('status', '')}` | "
            f"`{bool(row.get('blocking', True))}` | {float(row.get('duration_s') or 0.0):.3f} |"
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
                f"- Blocking: `{bool(row.get('blocking', True))}`",
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Procedural Growth Phase 4 audit.")
    parser.add_argument("--run-tag", default="", help="Optional suffix for report filenames.")
    args = parser.parse_args()
    run_id = str(args.run_tag or "").strip() or f"phase4-audit-{uuid.uuid4().hex[:8]}"
    checks = [
        _check(
            spec["id"],
            spec["title"],
            spec["command"],
            parser=str(spec.get("parser") or ""),
            blocking=bool(spec.get("blocking", True)),
        )
        for spec in _build_check_specs(run_id)
    ]
    report = {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "checks": checks,
        **_aggregate_report(checks),
    }
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    suffix = f"-{run_id}" if run_id else ""
    json_path = REPORT_DIR / f"procedural-growth-phase4-audit-{timestamp}{suffix}.json"
    md_path = REPORT_DIR / f"procedural-growth-phase4-audit-{timestamp}{suffix}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[procedural-growth-phase4-audit] json={json_path}")
    print(f"[procedural-growth-phase4-audit] md={md_path}")
    print(f"[procedural-growth-phase4-audit] overall_status={report['overall_status']}")
    print(f"[procedural-growth-phase4-audit] readiness_status={report['readiness_status']}")
    return 0 if report["overall_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
