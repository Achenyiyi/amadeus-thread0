from __future__ import annotations

from typing import Any


POST_BASELINE_ITEMS = [
    "callable_transport_adapter",
    "tts_presence_timing",
    "multimodal_input_capture",
    "executor_adapter",
    "external_executor_harnesses",
    "dynamic_skill_generation",
    "chinese_de_scaffolding",
    "bounded_capability_growth",
    "natural_long_horizon_calibration",
    "frontend_runtime_shell",
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
    "unlocked_planned",
}

POST_UNLOCK_LANE_ITEM_MAP = {
    "multimodal_capture_phase1": {
        "item_id": "multimodal_input_capture",
        "expected_readiness": "multimodal_capture_phase1_ready",
        "status": "implemented_ready",
        "runtime_available": True,
        "summary": "Consent-bound source-artifact multimodal ingestion is implemented for phase 1; live microphone/camera/screen capture remains blocked.",
    },
    "dynamic_skills_phase1": {
        "item_id": "dynamic_skill_generation",
        "expected_readiness": "dynamic_skills_phase1_ready",
        "status": "implemented_ready",
        "runtime_available": False,
        "summary": "Dynamic skill candidates are implemented as proposal-only, approval-gated registry drafts; no auto-install or persona-core patching is available.",
    },
    "external_executor_harness_phase1": {
        "item_id": "external_executor_harnesses",
        "expected_readiness": "external_executor_harness_phase1_ready",
        "status": "implemented_ready",
        "runtime_available": False,
        "summary": "External executor harness registry is implemented as fail-closed metadata; non-sandbox harnesses remain disabled until separately audited.",
    },
    "frontend_runtime_shell_phase1": {
        "item_id": "frontend_runtime_shell",
        "expected_readiness": "frontend_runtime_shell_phase1_ready",
        "status": "implemented_ready",
        "runtime_available": True,
        "summary": "Frontend runtime shell phase 1 builds against backend.v1 envelopes and does not own memory, body, autonomy, or graph semantics.",
    },
    "chinese_semantic_descaffolding_phase1": {
        "item_id": "chinese_de_scaffolding",
        "expected_readiness": "chinese_semantic_descaffolding_phase1_ready",
        "status": "implemented_ready",
        "runtime_available": False,
        "summary": "Chinese semantic de-scaffolding phase 1 has audit-backed semantic diagnostics; runtime reply rewriting remains guarded by preserved baselines.",
    },
    "capability_growth_phase5": {
        "item_id": "bounded_capability_growth",
        "expected_readiness": "capability_growth_phase5_ready",
        "status": "implemented_ready",
        "runtime_available": False,
        "summary": "Capability growth phase 5 is implemented as advisory workflow candidates over completed evidence; it grants no new tools or skill installs.",
    },
    "natural_long_horizon_calibration_phase1": {
        "item_id": "natural_long_horizon_calibration",
        "expected_readiness": "natural_long_horizon_calibration_phase1_ready",
        "status": "preserved_ready",
        "runtime_available": False,
        "summary": "Natural long-horizon calibration phase 1 is ready as an offline audit/smoke gate over the preserved lifeform loop.",
    },
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
            "status": "unlocked_planned",
            "runtime_available": False,
            "summary": "Audio/image/screen capture is unlocked for a bounded implementation phase, but no capture runtime is active in this closure layer.",
            "blocked_surfaces": [
                "capture_without_consent",
                "secret_recording",
                "browser_capture_without_existing_runtime_profile",
                "writeback_without_source_artifact",
            ],
        }
    if item == "executor_adapter":
        return {
            "id": item,
            "status": "implemented_ready",
            "runtime_available": True,
            "summary": "Executor adapter exposes the existing sandbox runner as the enabled harness surface.",
            "blocked_surfaces": [
                "arbitrary_host_shell",
                "privileged_container",
                "host_secret_passthrough",
            ],
        }
    if item == "external_executor_harnesses":
        return {
            "id": item,
            "status": "unlocked_planned",
            "runtime_available": False,
            "summary": "External harness integration is unlocked as a future adapter family, but each harness must remain approval-gated and result-only until separately audited.",
            "blocked_surfaces": [
                "arbitrary_host_shell",
                "git_mutation_without_packet_approval",
                "networked_execution_without_policy",
                "persona_memory_write_by_harness",
            ],
        }
    if item == "dynamic_skill_generation":
        return {
            "id": item,
            "status": "unlocked_planned",
            "runtime_available": False,
            "summary": "Dynamic skill generation is unlocked for a bounded registry-backed design, but runtime skill authoring is not active here.",
            "blocked_surfaces": [
                "autonomous_skill_install_without_proposal",
                "persona_core_skill_patch",
                "registry_write_without_hash_verification",
            ],
        }
    if item == "chinese_de_scaffolding":
        return {
            "id": item,
            "status": "unlocked_planned",
            "runtime_available": False,
            "summary": "Chinese lexical de-scaffolding is unlocked as a semantic-replacement phase, not as ad hoc reply-tone micro-polish.",
            "blocked_surfaces": [
                "prompt_sprawl_rewrite",
                "persona_core_redefinition",
            ],
        }
    if item == "bounded_capability_growth":
        return {
            "id": item,
            "status": "unlocked_planned",
            "runtime_available": False,
            "summary": "Capability growth beyond procedural phase 4 is unlocked for the next bounded slice, while preserving packet-owned execution and one memory substrate.",
            "blocked_surfaces": [
                "second_capability_memory_store",
                "unbounded_tool_suite_expansion",
            ],
        }
    if item == "natural_long_horizon_calibration":
        return {
            "id": item,
            "status": "unlocked_planned",
            "runtime_available": False,
            "summary": "Natural long-horizon calibration is unlocked as an evaluation-backed behavior phase over existing state/writeback contracts.",
            "blocked_surfaces": [
                "keyword_scene_script_sprawl",
                "final_text_tts_drift",
            ],
        }
    if item == "frontend_runtime_shell":
        return {
            "id": item,
            "status": "unlocked_planned",
            "runtime_available": False,
            "summary": "Frontend runtime work is unlocked for a contract-consuming shell, but it must consume backend.v1 envelopes rather than invent a second state schema.",
            "blocked_surfaces": [
                "frontend_owned_backend_semantics",
                "alternate_memory_or_body_truth",
            ],
        }
    return {
        "id": item,
        "status": "unknown",
        "runtime_available": False,
        "summary": "Unknown post-baseline item.",
        "blocked_surfaces": [],
    }


def _roadmap_readiness(row: dict[str, Any]) -> str:
    return str(row.get("readiness_status") or row.get("readiness") or "").strip()


def _roadmap_lane_ready(row: dict[str, Any], *, expected_readiness: str) -> bool:
    return bool(
        str(row.get("status") or "").strip() == "ready"
        and str(row.get("overall_status") or "passed").strip() == "passed"
        and _roadmap_readiness(row) == expected_readiness
    )


def post_unlock_overrides_from_roadmap(roadmap: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    report = dict(roadmap or {}) if isinstance(roadmap, dict) else {}
    lanes = report.get("lanes") if isinstance(report.get("lanes"), dict) else {}
    overrides: dict[str, dict[str, Any]] = {}
    for lane_id, spec in POST_UNLOCK_LANE_ITEM_MAP.items():
        row = lanes.get(lane_id) if isinstance(lanes.get(lane_id), dict) else {}
        expected = str(spec.get("expected_readiness") or "")
        if not _roadmap_lane_ready(row, expected_readiness=expected):
            continue
        item_id = str(spec.get("item_id") or "")
        if not item_id:
            continue
        overrides[item_id] = {
            "status": str(spec.get("status") or "implemented_ready"),
            "runtime_available": bool(spec.get("runtime_available", False)),
            "summary": str(spec.get("summary") or ""),
            "readiness_status": expected,
            "post_unlock_lane": lane_id,
            "blocked_surfaces": describe_post_baseline_item(item_id).get("blocked_surfaces", []),
        }
    return overrides


def _merge_description(base: dict[str, Any], override: Any) -> dict[str, Any]:
    merged = dict(base)
    if isinstance(override, dict):
        merged.update(override)
    return merged


def evaluate_post_baseline_status(
    overrides: dict[str, Any] | None = None,
    *,
    post_unlock_roadmap: dict[str, Any] | None = None,
) -> dict[str, Any]:
    override_rows = post_unlock_overrides_from_roadmap(post_unlock_roadmap)
    if isinstance(overrides, dict):
        override_rows.update(dict(overrides))
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
    "POST_UNLOCK_LANE_ITEM_MAP",
    "REQUIRED_RUNTIME_ITEMS",
    "describe_post_baseline_item",
    "evaluate_post_baseline_status",
    "post_unlock_overrides_from_roadmap",
]
