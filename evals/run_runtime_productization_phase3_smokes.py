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
from amadeus_thread0.runtime.transport_adapter import BackendTransportAdapter


REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
READINESS = "runtime_productization_phase3_smokes_ready"

AUTHORITY_BOUNDARY = {
    "frontend_semantics_owner": False,
    "http_server_semantics_owner": False,
    "live_capture_enabled": False,
    "dynamic_skill_registry_auto_write_enabled": False,
}


class _SmokeBackendApi:
    def runtime_productization(self) -> BackendApiEnvelope:
        return BackendApiEnvelope(
            kind="runtime_productization",
            thread_id="phase3-smoke",
            payload={
                "schema": "operator_readback.v2",
                "readiness_status": "runtime_productization_phase2_ready",
                "operator_readback": {
                    "schema": "operator_readback.v2",
                    "readiness_status": "runtime_productization_phase2_ready",
                },
            },
        )

    def build_turn_response(
        self,
        *,
        state_values: dict[str, Any],
        streamed_text: str = "",
        meta: dict[str, Any] | None = None,
    ) -> BackendApiEnvelope:
        return BackendApiEnvelope(
            kind="assistant_turn",
            thread_id="phase3-smoke",
            payload={
                "final_text": streamed_text or "我在。",
                "operator_readback": {"schema": "operator_readback.v2"},
                "living_loop_realism": {"readiness_status": "living_loop_runtime_realism_phase3_ready"},
                "embodied_interaction": {"readiness_status": "embodied_interaction_runtime_phase5_ready"},
                "runtime_productization": {"readiness_status": "runtime_productization_phase2_ready"},
            },
        )

    def build_event_round_response(
        self,
        *,
        state_values: dict[str, Any],
        final_text: str,
        meta: dict[str, Any] | None = None,
    ) -> BackendApiEnvelope:
        return BackendApiEnvelope(
            kind="event_round",
            thread_id="phase3-smoke",
            payload={
                "final_text": final_text,
                "operator_readback": {"schema": "operator_readback.v2"},
                "living_loop_realism": {"readiness_status": "living_loop_runtime_realism_phase3_ready"},
                "embodied_interaction": {"readiness_status": "embodied_interaction_runtime_phase5_ready"},
            },
        )


def _scenario(status: bool, **details: Any) -> dict[str, Any]:
    row = {"status": "passed" if status else "failed"}
    row.update(details)
    return row


def run_runtime_productization_phase3_smokes() -> dict[str, Any]:
    adapter = BackendTransportAdapter(backend_api=_SmokeBackendApi())

    operator = adapter.handle("GET", "/api/runtime-productization")
    operator_body = operator.get("body") if isinstance(operator.get("body"), dict) else {}
    operator_payload = operator_body.get("payload") if isinstance(operator_body.get("payload"), dict) else {}

    turn = adapter.handle(
        "POST",
        "/api/turns/finalize",
        body={"state_values": {"phase": 3}, "streamed_text": "嗯，我在。", "meta": {"smoke": True}},
    )
    turn_body = turn.get("body") if isinstance(turn.get("body"), dict) else {}
    turn_payload = turn_body.get("payload") if isinstance(turn_body.get("payload"), dict) else {}

    event = adapter.handle(
        "POST",
        "/api/event-rounds/finalize",
        body={"state_values": {"phase": 3}, "final_text": "继续。", "meta": {"smoke": True}},
    )
    event_body = event.get("body") if isinstance(event.get("body"), dict) else {}
    event_payload = event_body.get("payload") if isinstance(event_body.get("payload"), dict) else {}

    frontend_consumes = (
        turn_body.get("schema_version") == "backend.v1"
        and turn_body.get("kind") == "assistant_turn"
        and "operator_readback" in turn_payload
        and "living_loop_realism" in turn_payload
        and "embodied_interaction" in turn_payload
    )
    scenarios = {
        "operator_readback_route": _scenario(
            operator.get("status") == 200
            and operator_body.get("kind") == "runtime_productization"
            and operator_payload.get("readiness_status") == "runtime_productization_phase2_ready"
        ),
        "assistant_turn_finalize": _scenario(
            turn.get("status") == 200
            and turn_body.get("kind") == "assistant_turn"
            and turn_payload.get("final_text") == "嗯，我在。"
            and "runtime_productization" in turn_payload
        ),
        "event_round_finalize": _scenario(
            event.get("status") == 200
            and event_body.get("kind") == "event_round"
            and event_payload.get("final_text") == "继续。"
            and "operator_readback" in event_payload
        ),
        "frontend_consumer_boundary": _scenario(frontend_consumes),
    }
    failures = [name for name, row in scenarios.items() if row["status"] != "passed"]
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": "failed" if failures else "passed",
        "readiness_status": "runtime_productization_phase3_smokes_blocked" if failures else READINESS,
        "scenarios": scenarios,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "failure_reasons": failures,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Runtime Productization Phase 3 Smokes",
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
    parser = argparse.ArgumentParser(description="Run runtime productization phase 3 smokes.")
    parser.add_argument("--reports-dir", default=str(REPORT_DIR))
    args = parser.parse_args()
    report_dir = Path(args.reports_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    report = run_runtime_productization_phase3_smokes()
    run_id = time.strftime("%Y%m%d-%H%M%S")
    json_path = report_dir / f"runtime-productization-phase3-smokes-{run_id}.json"
    md_path = report_dir / f"runtime-productization-phase3-smokes-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[runtime-productization-phase3-smokes] json={json_path}")
    print(f"[runtime-productization-phase3-smokes] md={md_path}")
    print(f"[runtime-productization-phase3-smokes] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[runtime-productization-phase3-smokes] readiness={report.get('readiness_status', 'unknown')}")
    return 0 if report.get("overall_status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
