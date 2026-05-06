from __future__ import annotations

from evals.run_frontend_runtime_shell_phase2_audit import evaluate_checks, render_markdown


def test_frontend_runtime_shell_phase2_audit_reports_ready_when_checks_pass():
    report = evaluate_checks(
        [
            {"name": "contract", "status": "passed", "command": "pytest"},
            {"name": "build", "status": "passed", "command": "npm build"},
        ]
    )

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "frontend_runtime_shell_phase2_ready"
    assert report["failure_reasons"] == []


def test_frontend_runtime_shell_phase2_audit_fails_when_check_fails():
    report = evaluate_checks(
        [
            {"name": "contract", "status": "passed", "command": "pytest"},
            {"name": "build", "status": "failed", "command": "npm build"},
        ]
    )

    assert report["overall_status"] == "failed"
    assert report["readiness_status"] == "frontend_runtime_shell_phase2_in_progress"
    assert report["failure_reasons"] == ["build"]


def test_frontend_runtime_shell_phase2_audit_markdown_names_ready_status():
    rendered = render_markdown(
        {
            "overall_status": "passed",
            "readiness_status": "frontend_runtime_shell_phase2_ready",
            "checks": [
                {"name": "contract", "status": "passed", "command": "pytest"},
                {"name": "build", "status": "passed", "command": "npm build"},
            ],
            "failure_reasons": [],
        }
    )

    assert "Frontend Runtime Shell Phase 2 Audit" in rendered
    assert "frontend_runtime_shell_phase2_ready" in rendered
    assert "| `contract` | `passed` | `pytest` |" in rendered

