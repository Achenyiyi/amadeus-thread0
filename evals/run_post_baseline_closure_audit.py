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
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from amadeus_thread0.runtime.post_baseline_closure import evaluate_post_baseline_status


REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

EXECUTOR_JSON_RE = re.compile(r"^\[executor-adapter\]\s+json=(.+)$", re.MULTILINE)
EXECUTOR_STATUS_RE = re.compile(r"^\[executor-adapter\]\s+overall_status=(.+)$", re.MULTILINE)
EXECUTOR_READY_RE = re.compile(r"^\[executor-adapter\]\s+readiness=(.+)$", re.MULTILINE)
TTS_JSON_RE = re.compile(r"^\[tts-presence-timing-audit\]\s+json=(.+)$", re.MULTILINE)
TTS_STATUS_RE = re.compile(r"^\[tts-presence-timing-audit\]\s+overall_status=(.+)$", re.MULTILINE)
TTS_READY_RE = re.compile(r"^\[tts-presence-timing-audit\]\s+readiness=(.+)$", re.MULTILINE)
CHINESE_JSON_RE = re.compile(r"^\[chinese-surface-de-scaffold\]\s+json=(.+)$", re.MULTILINE)
CHINESE_STATUS_RE = re.compile(r"^\[chinese-surface-de-scaffold\]\s+overall_status=(.+)$", re.MULTILINE)
CHINESE_READY_RE = re.compile(r"^\[chinese-surface-de-scaffold\]\s+readiness=(.+)$", re.MULTILINE)


def _python(*args: str) -> list[str]:
    return [sys.executable, *args]


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    return env


def _load_json(path: str) -> dict[str, Any]:
    file_path = Path(str(path or ""))
    if not file_path.exists():
        return {}
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        return dict(payload) if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _tail(text: str, *, limit: int = 2400) -> str:
    value = str(text or "")
    return value if len(value) <= limit else value[-limit:]


def _format_command(command: Sequence[str]) -> str:
    return subprocess.list2cmdline([str(part) for part in command])


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


def _parse_prefixed_output(stdout: str, *, family: str) -> dict[str, str]:
    regexes = {
        "executor": (EXECUTOR_JSON_RE, EXECUTOR_STATUS_RE, EXECUTOR_READY_RE),
        "tts": (TTS_JSON_RE, TTS_STATUS_RE, TTS_READY_RE),
        "chinese": (CHINESE_JSON_RE, CHINESE_STATUS_RE, CHINESE_READY_RE),
    }
    json_re, status_re, ready_re = regexes[family]
    text = str(stdout or "")
    payload: dict[str, str] = {}
    for regex, key in ((json_re, "json"), (status_re, "overall_status"), (ready_re, "readiness_status")):
        match = regex.search(text)
        if match:
            payload[key] = match.group(1).strip()
    report = _load_json(payload.get("json", ""))
    if report:
        payload["report_overall_status"] = str(report.get("overall_status") or "").strip()
        payload["report_readiness_status"] = str(report.get("readiness_status") or "").strip()
        if "historical_pass_streak" in report:
            payload["historical_pass_streak"] = str(report.get("historical_pass_streak") or 0)
    return payload


def _check(
    id: str,
    title: str,
    command: Sequence[str],
    *,
    parser: str = "",
    expected_readiness: str = "",
    blocking: bool = True,
) -> dict[str, Any]:
    outcome = _run(command)
    status = "passed" if int(outcome.get("returncode") or 0) == 0 else "failed"
    artifacts: dict[str, Any] = {}
    failure_reasons: list[str] = []
    if parser:
        artifacts = _parse_prefixed_output(str(outcome.get("stdout") or ""), family=parser)
        if not artifacts.get("json") or not Path(str(artifacts.get("json") or "")).exists():
            status = "failed"
            failure_reasons.append("missing_json_artifact")
        if str(artifacts.get("overall_status") or artifacts.get("report_overall_status") or "") != "passed":
            status = "failed"
            failure_reasons.append(parser + "_overall_status=" + str(artifacts.get("overall_status") or "unknown"))
        if expected_readiness and str(artifacts.get("readiness_status") or artifacts.get("report_readiness_status") or "") != expected_readiness:
            status = "failed"
            failure_reasons.append(
                parser + "_readiness=" + str(artifacts.get("readiness_status") or "unknown") + " expected=" + expected_readiness
            )
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


def _build_check_specs(run_id: str) -> list[dict[str, Any]]:
    return [
        {
            "id": "post_baseline_unit_contract",
            "title": "Post-Baseline Closure Unit Contract",
            "command": _python("-m", "pytest", "tests/test_transport_adapter.py", "tests/test_post_baseline_closure.py", "-q"),
        },
        {
            "id": "executor_adapter_audit",
            "title": "Executor Adapter Audit",
            "command": _python("evals/run_executor_adapter_audit.py", "--run-tag", f"{run_id}-executor"),
            "parser": "executor",
            "expected_readiness": "executor_adapter_ready",
        },
        {
            "id": "tts_presence_timing_audit",
            "title": "TTS Presence Timing Audit",
            "command": _python("evals/run_tts_presence_timing_audit.py", "--run-tag", f"{run_id}-tts"),
            "parser": "tts",
            "expected_readiness": "tts_presence_timing_ready",
        },
        {
            "id": "chinese_surface_tracking_audit",
            "title": "Chinese Surface Tracking Audit",
            "command": _python("evals/run_chinese_surface_de_scaffold_audit.py", "--run-tag", f"{run_id}-chinese"),
            "parser": "chinese",
            "expected_readiness": "chinese_surface_de_scaffold_ready",
            "blocking": False,
        },
    ]


def _status_overrides_from_checks(checks: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    rows = {str(row.get("id") or ""): dict(row) for row in checks if isinstance(row, dict)}
    executor_ready = str(rows.get("executor_adapter_audit", {}).get("status") or "") == "passed"
    tts_ready = str(rows.get("tts_presence_timing_audit", {}).get("status") or "") == "passed"
    unit_ready = str(rows.get("post_baseline_unit_contract", {}).get("status") or "") == "passed"
    return {
        "callable_transport_adapter": {"status": "implemented_ready" if unit_ready else "missing"},
        "executor_adapter": {"status": "implemented_ready" if executor_ready else "missing"},
        "tts_presence_timing": {"status": "preserved_ready" if tts_ready else "missing"},
    }


def _aggregate_report(checks: Sequence[dict[str, Any]]) -> dict[str, Any]:
    rows = [dict(item) for item in checks]
    closure = evaluate_post_baseline_status(_status_overrides_from_checks(rows))
    blocking_failure_ids = list(closure.get("blocking_failure_ids") or [])
    for row in rows:
        if bool(row.get("blocking", True)) and str(row.get("status") or "") != "passed":
            row_id = str(row.get("id") or "")
            if row_id not in blocking_failure_ids:
                blocking_failure_ids.append(row_id)
    overall_status = "failed" if blocking_failure_ids else "passed"
    summary = dict(closure.get("summary") or {})
    summary["checks_total"] = len(rows)
    summary["checks_passed"] = len([row for row in rows if str(row.get("status") or "") == "passed"])
    summary["checks_failed"] = len(rows) - int(summary["checks_passed"])
    return {
        "overall_status": overall_status,
        "readiness_status": (
            "post_baseline_closure_ready" if overall_status == "passed" else "post_baseline_closure_in_progress"
        ),
        "blocking_failure_ids": blocking_failure_ids,
        "summary": summary,
        "closure_items": dict(closure.get("items") or {}),
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = dict(report.get("summary") or {})
    lines = [
        f"# Post-Baseline Closure Audit ({report.get('run_id', 'unknown')})",
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
        f"- Implemented ready: `{summary.get('implemented_ready', 0)}`",
        f"- Preserved ready: `{summary.get('preserved_ready', 0)}`",
        f"- Deferred fail closed: `{summary.get('deferred_fail_closed', 0)}`",
        f"- Tracked not mainline: `{summary.get('tracked_not_mainline', 0)}`",
        f"- Quality backlog tracked: `{summary.get('quality_backlog_tracked', 0)}`",
        "",
        "## Closure Items",
        "",
        "| Item | Status | Runtime Available |",
        "| --- | --- | --- |",
    ]
    for item_id, row in (report.get("closure_items") or {}).items():
        if not isinstance(row, dict):
            continue
        lines.append(f"| `{item_id}` | `{row.get('status', '')}` | `{row.get('runtime_available', '')}` |")
    lines.extend(["", "## Checks", "", "| Check | Status | Blocking | Duration (s) |", "| --- | --- | --- | ---: |"])
    for row in report.get("checks") or []:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| `{row.get('id', '')}` | `{row.get('status', '')}` | `{bool(row.get('blocking', True))}` | {float(row.get('duration_s') or 0.0):.3f} |"
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
    parser = argparse.ArgumentParser(description="Run the post-baseline closure audit.")
    parser.add_argument("--run-tag", default="", help="Optional suffix for report filenames.")
    args = parser.parse_args()

    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    checks = [
        _check(
            spec["id"],
            spec["title"],
            spec["command"],
            parser=str(spec.get("parser") or ""),
            expected_readiness=str(spec.get("expected_readiness") or ""),
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
    json_path = REPORT_DIR / f"post-baseline-closure-audit-{run_id}.json"
    md_path = REPORT_DIR / f"post-baseline-closure-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[post-baseline-closure] json={json_path}")
    print(f"[post-baseline-closure] md={md_path}")
    print(f"[post-baseline-closure] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[post-baseline-closure] readiness={report.get('readiness_status', 'unknown')}")
    return 0 if str(report.get("overall_status") or "") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
