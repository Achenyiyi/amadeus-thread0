from __future__ import annotations

from typing import Any


POST_BASELINE_ITEMS = [
    "callable_transport_adapter",
    "tts_presence_timing",
    "multimodal_input_capture",
    "executor_adapter",
    "dynamic_skill_generation",
    "chinese_de_scaffolding",
    "bounded_capability_growth",
    "natural_long_horizon_calibration",
]

REQUIRED_RUNTIME_ITEMS = {
    "callable_transport_adapter",
    "tts_presence_timing",
    "executor_adapter",
}

ACCEPTED_STATUSES = {
    "implemented_ready",
    "preserved_ready",
    "deferred_fail_closed",
    "tracked_not_mainline",
    "quality_backlog_tracked",
}


def describe_post_baseline_item(item_id: str) -> dict[str, Any]:
    item = str(item_id or "").strip()
    if item == "callable_transport_adapter":
        return {
            "id": item,
            "status": "implemented_ready",
            "runtime_available": True,
            "summary": "Transport-neutral Python callable adapter wraps the existing BackendAPI envelopes.",
            "blocked_surfaces": [],
        }
    if item == "tts_presence_timing":
        return {
            "id": item,
            "status": "preserved_ready",
            "runtime_available": True,
            "summary": "TTS presence timing remains a preserved digital-body telemetry baseline.",
            "blocked_surfaces": [],
        }
    if item == "multimodal_input_capture":
        return {
            "id": item,
            "status": "deferred_fail_closed",
            "runtime_available": False,
            "summary": "True audio/image/screen capture is not opened in this backend phase.",
            "blocked_surfaces": [
                "audio_input",
                "image_observation",
                "screen_observation",
                "live_browser_plus_capture",
            ],
        }
    if item == "executor_adapter":
        return {
            "id": item,
            "status": "implemented_ready",
            "runtime_available": True,
            "summary": "Executor adapter exposes the existing sandbox runner as the only enabled harness.",
            "blocked_surfaces": [
                "deep_agents_executor",
                "codex_harness",
                "claude_harness",
                "openclaw_harness",
            ],
        }
    if item == "dynamic_skill_generation":
        return {
            "id": item,
            "status": "deferred_fail_closed",
            "runtime_available": False,
            "summary": "Runtime skill generation remains disabled; skill mutations stay approval-gated registry operations.",
            "blocked_surfaces": [
                "runtime_skill_authoring",
                "autonomous_skill_install",
                "persona_core_skill_patch",
            ],
        }
    if item == "chinese_de_scaffolding":
        return {
            "id": item,
            "status": "tracked_not_mainline",
            "runtime_available": False,
            "summary": "Chinese lexical replacement is tracked by diagnostics but remains off the mainline closure path.",
            "blocked_surfaces": [],
        }
    if item == "bounded_capability_growth":
        return {
            "id": item,
            "status": "quality_backlog_tracked",
            "runtime_available": False,
            "summary": "Capability self-growth remains a bounded procedural-learning backlog, not a widened executor surface.",
            "blocked_surfaces": [],
        }
    if item == "natural_long_horizon_calibration":
        return {
            "id": item,
            "status": "quality_backlog_tracked",
            "runtime_available": False,
            "summary": "Natural long-horizon behavior calibration remains a quality lane over preserved backend contracts.",
            "blocked_surfaces": [],
        }
    return {
        "id": item,
        "status": "unknown",
        "runtime_available": False,
        "summary": "Unknown post-baseline item.",
        "blocked_surfaces": [],
    }


def _merge_description(base: dict[str, Any], override: Any) -> dict[str, Any]:
    merged = dict(base)
    if isinstance(override, dict):
        merged.update(override)
    return merged


def evaluate_post_baseline_status(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    override_rows = dict(overrides or {}) if isinstance(overrides, dict) else {}
    items: dict[str, dict[str, Any]] = {}
    summary: dict[str, int] = {}
    blocking_failure_ids: list[str] = []

    for item_id in POST_BASELINE_ITEMS:
        row = _merge_description(describe_post_baseline_item(item_id), override_rows.get(item_id))
        row["id"] = item_id
        status = str(row.get("status") or "").strip()
        summary[status or "missing"] = int(summary.get(status or "missing") or 0) + 1
        if item_id in REQUIRED_RUNTIME_ITEMS and status not in {"implemented_ready", "preserved_ready"}:
            blocking_failure_ids.append(item_id)
        elif status not in ACCEPTED_STATUSES:
            blocking_failure_ids.append(item_id)
        items[item_id] = row

    # Surface explicitly supplied unknown overrides as failures instead of silently dropping them.
    for item_id in sorted(set(override_rows) - set(POST_BASELINE_ITEMS)):
        blocking_failure_ids.append(str(item_id))

    overall_status = "failed" if blocking_failure_ids else "passed"
    return {
        "overall_status": overall_status,
        "readiness_status": (
            "post_baseline_closure_ready" if overall_status == "passed" else "post_baseline_closure_in_progress"
        ),
        "blocking_failure_ids": blocking_failure_ids,
        "summary": summary,
        "items": items,
    }


__all__ = [
    "ACCEPTED_STATUSES",
    "POST_BASELINE_ITEMS",
    "REQUIRED_RUNTIME_ITEMS",
    "describe_post_baseline_item",
    "evaluate_post_baseline_status",
]
