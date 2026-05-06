from __future__ import annotations

from evals.run_living_loop_realism_phase2_audit import (
    build_backend_payload_fixture,
    build_report,
    render_markdown,
)


def test_phase2_report_returns_ready():
    report = build_report(run_id="test-run")

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "living_loop_runtime_realism_phase2_ready"
    assert report["readback"]["backend_payload"]["status"] == "ready"
    assert report["readback"]["causality"]["status"] == "ready"


def test_phase2_fixture_contains_backend_only_surfaces():
    payload = build_backend_payload_fixture()

    assert "turn_summary" in payload
    assert "writeback_trace" in payload
    assert "operator_readback" in payload
    assert "living_loop_realism" not in payload


def test_phase2_markdown_renders_backend_payload_status():
    rendered = render_markdown(build_report(run_id="render-test"))

    assert "# Living Loop Runtime Realism Phase 2 Audit" in rendered
    assert "`living_loop_runtime_realism_phase2_ready`" in rendered
    assert "Backend Payload" in rendered
    assert "| `backend_payload` | `ready` |" in rendered
