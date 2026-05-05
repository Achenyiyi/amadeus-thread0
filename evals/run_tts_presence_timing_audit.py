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

SMOKES_JSON_RE = re.compile(r"^\[tts-presence-timing-smokes\]\s+json=(.+)$", re.MULTILINE)
SMOKES_MD_RE = re.compile(r"^\[tts-presence-timing-smokes\]\s+md=(.+)$", re.MULTILINE)
SMOKES_STATUS_RE = re.compile(r"^\[tts-presence-timing-smokes\]\s+overall_status=(.+)$", re.MULTILINE)


def _python(*args: str) -> list[str]:
    return [sys.executable, *args]


def _base_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    return env


def _tail(text: str, *, limit: int = 2400) -> str:
    value = str(text or "").strip()
    return value if len(value) <= limit else value[-limit:]


def _format_command(command: Sequence[str]) -> str:
    return subprocess.list2cmdline([str(part) for part in command])


def _run_command(command: Sequence[str]) -> dict[str, Any]:
    started = time.time()
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
        "duration_s": round(time.time() - started, 3),
    }


def _load_json(path: str) -> dict[str, Any]:
    file_path = Path(str(path or ""))
    if not file_path.exists():
        return {}
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _parse_smokes(stdout: str) -> dict[str, str]:
    text = str(stdout or "")
    payload: dict[str, str] = {}
    json_match = SMOKES_JSON_RE.search(text)
    md_match = SMOKES_MD_RE.search(text)
    status_match = SMOKES_STATUS_RE.search(text)
    if json_match:
        payload["json"] = json_match.group(1).strip()
    if md_match:
        payload["md"] = md_match.group(1).strip()
    if status_match:
        payload["overall_status"] = status_match.group(1).strip()
    report = _load_json(payload.get("json") or "")
    if report:
        payload["passed"] = str(report.get("passed") or 0)
        payload["failed"] = str(report.get("failed") or 0)
    return payload


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
        artifacts = _parse_smokes(str(outcome.get("stdout") or ""))
        json_path = str(artifacts.get("json") or "").strip()
        md_path = str(artifacts.get("md") or "").strip()
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
        if str(artifacts.get("overall_status") or "") != "passed":
            status = "failed"
            failure_reasons.append("tts_smokes_overall_status=" + str(artifacts.get("overall_status") or "unknown"))
        if str(artifacts.get("failed") or "0") not in {"", "0"}:
            status = "failed"
            failure_reasons.append("tts_smokes_failed=" + str(artifacts.get("failed")))
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


def _build_check_specs(run_id: str) -> list[dict[str, Any]]:
    return [
        {
            "id": "tts_presence_smokes",
            "title": "TTS Presence Timing Smokes",
            "parser": "smokes",
            "command": _python("evals/run_tts_presence_timing_smokes.py", "--run-tag", f"{run_id}-smokes"),
        },
        {
            "id": "tts_presence_audit_contract",
            "title": "TTS Presence Timing Audit Contract Tests",
            "command": _python(
                "-m",
                "pytest",
                "tests/test_tts_presence_timing_smokes.py",
                "tests/test_tts_presence_timing_audit.py",
                "-q",
            ),
        },
        {
            "id": "tts_presence_render_contract",
            "title": "TTS Presence Timing Backend Readback Contract",
            "command": _python(
                "-m",
                "pytest",
                "tests/test_backend_api.py",
                "tests/test_backend_session.py",
                "tests/test_cli_views.py",
                "-k",
                "tts_presence_timing",
                "-q",
            ),
        },
    ]


def _aggregate_overall_status(checks: Sequence[dict[str, Any]]) -> dict[str, Any]:
    rows = [dict(item) for item in checks]
    blocking_failure_ids = [
        str(row.get("id") or "").strip()
        for row in rows
        if bool(row.get("blocking", True)) and str(row.get("status") or "").strip() != "passed"
    ]
    failed = len([row for row in rows if str(row.get("status") or "").strip() != "passed"])
    passed = len(rows) - failed
    overall = "failed" if blocking_failure_ids else "passed"
    return {
        "overall_status": overall,
        "readiness_status": "tts_presence_timing_ready" if overall == "passed" else "tts_presence_timing_in_progress",
        "blocking_failure_ids": blocking_failure_ids,
        "summary": {
            "total": len(rows),
            "passed": passed,
            "failed": failed,
        },
    }


def _pass_streak(statuses: Sequence[str]) -> int:
    streak = 0
    for status in reversed([str(item or "").strip() for item in statuses]):
        if status != "passed":
            break
        streak += 1
    return streak


def _load_previous_reports() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(REPORT_DIR.glob("tts-presence-timing-audit-*.json")):
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
    previous_rows: Sequence[dict[str, Any]],
    current_report: dict[str, Any],
    *,
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
    statuses = [str(row.get("overall_status") or "").strip() for row in rows]
    return {
        "historical_pass_streak": _pass_streak(statuses),
        "recent_audits": rows[-max(1, int(limit or 10)) :],
    }


def _finalize_report(
    preliminary_report: dict[str, Any],
    *,
    previous_rows: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    report = dict(preliminary_report)
    report["readiness_status"] = (
        "tts_presence_timing_ready"
        if str(report.get("overall_status") or "").strip() == "passed"
        else "tts_presence_timing_in_progress"
    )
    history = _recent_audit_history(previous_rows, report)
    report["recent_audits"] = history["recent_audits"]
    report["historical_pass_streak"] = int(history.get("historical_pass_streak") or 0)
    summary = dict(report.get("summary") or {})
    summary["historical_pass_streak"] = int(history.get("historical_pass_streak") or 0)
    report["summary"] = summary
    return report


def _render_markdown(report: dict[str, Any]) -> str:
    summary = dict(report.get("summary") or {})
    lines = [
        f"# TTS Presence Timing Audit ({report.get('run_id', 'unknown')})",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
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
    parser = argparse.ArgumentParser(description="Run TTS presence timing closure audit.")
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
                parser=str(spec.get("parser") or ""),
                blocking=bool(spec.get("blocking", True)),
            )
        )
    aggregate = _aggregate_overall_status(checks)
    report = {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "checks": checks,
        **aggregate,
    }
    report = _finalize_report(report, previous_rows=_load_previous_reports())
    json_path = REPORT_DIR / f"tts-presence-timing-audit-{run_id}.json"
    md_path = REPORT_DIR / f"tts-presence-timing-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(f"[tts-presence-timing-audit] json={json_path}")
    print(f"[tts-presence-timing-audit] md={md_path}")
    print(f"[tts-presence-timing-audit] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[tts-presence-timing-audit] readiness={report.get('readiness_status', 'unknown')}")


if __name__ == "__main__":
    main()
