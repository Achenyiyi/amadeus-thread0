from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from amadeus_thread0.runtime.backend_api import BackendApiEnvelope
from amadeus_thread0.runtime.http_transport import (
    HTTP_TRANSPORT_AUTHORITY_BOUNDARY,
    call_wsgi_app,
    create_http_transport_app,
)


REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
HTTP_TRANSPORT_SMOKE_READINESS = "http_transport_thin_wrapper_phase1_smokes_ready"


class _SmokeBackendApi:
    def __init__(self) -> None:
        self.turn_calls = []

    def runtime_productization(self) -> BackendApiEnvelope:
        return BackendApiEnvelope(
            kind="runtime_productization",
            thread_id="http-smoke",
            payload={"readiness_status": "runtime_productization_phase3_ready"},
        )

    def persona(self) -> BackendApiEnvelope:
        return BackendApiEnvelope(
            kind="persona_view",
            thread_id="http-smoke",
            payload={"persona_state": {"name": "Amadeus"}},
        )

    def build_turn_response(
        self,
        *,
        state_values: dict[str, Any],
        streamed_text: str = "",
        meta: dict[str, Any] | None = None,
    ) -> BackendApiEnvelope:
        self.turn_calls.append({"state_values": state_values, "streamed_text": streamed_text, "meta": meta})
        return BackendApiEnvelope(
            kind="assistant_turn",
            thread_id="http-smoke",
            payload={"final_text": streamed_text, "operator_readback": {"schema": "operator_readback.v2"}},
        )


def _scenario(passed: bool, **details: Any) -> dict[str, Any]:
    row = {"status": "passed" if passed else "failed"}
    row.update(details)
    return row


def run_http_transport_smokes() -> dict[str, Any]:
    api = _SmokeBackendApi()
    app = create_http_transport_app(api)
    runtime = call_wsgi_app(app, "GET", "/api/runtime-productization")
    turn = call_wsgi_app(
        app,
        "POST",
        "/api/turns/finalize",
        body={"state_values": {"phase": "http"}, "streamed_text": "transport ok", "meta": {"via": "wsgi"}},
    )
    invalid = call_wsgi_app(app, "POST", "/api/turns/finalize", raw_body=b"{bad")
    wrong_method = call_wsgi_app(app, "POST", "/api/persona-view")
    boundary = dict(HTTP_TRANSPORT_AUTHORITY_BOUNDARY)

    scenarios = {
        "runtime_productization_get": _scenario(
            runtime["status"] == 200
            and runtime["body"].get("schema_version") == "backend.v1"
            and runtime["body"].get("kind") == "runtime_productization"
        ),
        "assistant_turn_finalize_post": _scenario(
            turn["status"] == 200
            and turn["body"].get("kind") == "assistant_turn"
            and api.turn_calls
            and api.turn_calls[0]["streamed_text"] == "transport ok"
        ),
        "invalid_json_boundary": _scenario(
            invalid["status"] == 400 and invalid["body"].get("error", {}).get("code") == "INVALID_JSON"
        ),
        "method_not_allowed_boundary": _scenario(
            wrong_method["status"] == 405
            and wrong_method["body"].get("error", {}).get("code") == "METHOD_NOT_ALLOWED"
        ),
        "authority_boundary_closed": _scenario(
            boundary.get("transport_role") == "thin_wrapper"
            and boundary.get("backend_semantics_owner") is False
            and boundary.get("frontend_semantics_owner") is False
            and boundary.get("sse_or_websocket_streaming_enabled") is False
        ),
    }
    failures = [name for name, row in scenarios.items() if row["status"] != "passed"]
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": "failed" if failures else "passed",
        "readiness_status": "http_transport_thin_wrapper_phase1_smokes_blocked"
        if failures
        else HTTP_TRANSPORT_SMOKE_READINESS,
        "scenarios": scenarios,
        "authority_boundary": boundary,
        "failure_reasons": failures,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# HTTP Transport Thin Wrapper Phase 1 Smokes",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
        "",
        "## Scenarios",
        "",
        "| Scenario | Status |",
        "| --- | --- |",
    ]
    for key, row in (report.get("scenarios") or {}).items():
        if isinstance(row, dict):
            lines.append(f"| `{key}` | `{row.get('status', '')}` |")
    lines.extend(["", "## Authority Boundary", "", "| Boundary | Value |", "| --- | --- |"])
    for key, value in (report.get("authority_boundary") or {}).items():
        lines.append(f"| `{key}` | `{value}` |")
    failures = [str(reason) for reason in report.get("failure_reasons", []) if str(reason)]
    if failures:
        lines.extend(["", "## Failure Reasons", ""])
        lines.extend(f"- `{reason}`" for reason in failures)
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run HTTP transport thin-wrapper phase 1 smokes.")
    parser.add_argument("--reports-dir", default=str(REPORT_DIR))
    args = parser.parse_args()
    report_dir = Path(args.reports_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    report = run_http_transport_smokes()
    run_id = time.strftime("%Y%m%d-%H%M%S")
    json_path = report_dir / f"http-transport-smokes-{run_id}.json"
    md_path = report_dir / f"http-transport-smokes-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[http-transport-smokes] json={json_path}")
    print(f"[http-transport-smokes] md={md_path}")
    print(f"[http-transport-smokes] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[http-transport-smokes] readiness={report.get('readiness_status', 'unknown')}")
    return 0 if report.get("overall_status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
