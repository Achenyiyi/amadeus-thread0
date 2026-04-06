from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from amadeus_thread0.evolution_engine.reconsolidation import build_reconsolidation_snapshot
from amadeus_thread0.graph_parts.action_packets import build_tool_action_packet
from amadeus_thread0.runtime.browser_runner import reset_browser_session_manager_cache
from amadeus_thread0.runtime.final_state import resolve_digital_body_consequence
from amadeus_thread0.utils.tools import (
    browser_capture_page_to_source_ref,
    browser_fill,
    browser_open_url,
    reset_tool_runtime_caches,
)


def _browser_env(runtime_dir: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
        "AMADEUS_DATA_DIR": str(runtime_dir),
        "AMADEUS_MODEL_PROVIDER": "openai_compatible",
        "AMADEUS_BROWSER_HEADLESS": "1",
        }
    )
    return env


def _site_fixture(root: Path) -> dict[str, Any]:
    workspace = root / "workspaces" / "browser-runtime"
    pages = root / "pages"
    workspace.mkdir(parents=True, exist_ok=True)
    pages.mkdir(parents=True, exist_ok=True)
    (pages / "index.html").write_text(
        "\n".join(
            [
                "<!doctype html>",
                "<html><head><meta charset=\"utf-8\" /><title>Start</title></head>",
                "<body>",
                "<h1>Start</h1>",
                "<input type=\"password\" aria-label=\"Password\" />",
                "</body></html>",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (pages / "next.html").write_text(
        "<!doctype html><html><head><title>Next</title></head><body>next</body></html>\n",
        encoding="utf-8",
    )
    return {
        "workspace": workspace,
        "index_url": (pages / "index.html").resolve(strict=False).as_uri(),
        "access_hints": {
            "filesystem_state": "writable",
            "workspace_root": str(workspace),
            "active_artifact_kind": "workspace",
            "active_artifact_ref": str(workspace),
            "active_artifact_label": workspace.name,
        },
    }


def _password_ref(payload: dict[str, object]) -> str:
    for item in payload["browser_execution_result"]["snapshot_targets"]:
        if item.get("input_type") == "password":
            return str(item.get("target_ref") or "")
    raise AssertionError("password target not found")


def _digital_body_from_payload(payload: dict[str, object]) -> dict[str, object]:
    return {
        "active_surface": "tooling",
        "perception_channels": ["dialogue", "browser"],
        "action_channels": ["language", "structured_action", "tooling"],
        "world_surfaces": ["browser", "filesystem"],
        "access_state": dict(payload.get("access_state") or {}),
        "resource_state": dict(payload.get("resource_state") or {}),
    }


def test_browser_capture_to_source_ref_writes_navigation_truth_and_saved_material_identity():
    with TemporaryDirectory() as td:
        runtime_dir = Path(td) / "runtime"
        fixture = _site_fixture(runtime_dir)
        try:
            with patch.dict(os.environ, _browser_env(runtime_dir), clear=True):
                open_payload = browser_open_url.invoke(
                    {"url": fixture["index_url"], "proposal_id": "ap-browser-open-1", "access_hints": fixture["access_hints"]}
                )
                capture_payload = browser_capture_page_to_source_ref.invoke(
                    {"proposal_id": "ap-browser-capture-1", "access_hints": dict(open_payload.get("access_hints") or {})}
                )

            packet = build_tool_action_packet(
                tool_name="browser_capture_page_to_source_ref",
                proposal_id="ap-browser-capture-1",
                args={},
                action="approve",
                status="completed",
                result_summary=str(capture_payload.get("summary") or ""),
                browser_execution_spec=dict(capture_payload.get("browser_execution_spec") or {}),
                browser_execution_preview=dict(capture_payload.get("browser_execution_preview") or {}),
                browser_execution_result=dict(capture_payload.get("browser_execution_result") or {}),
            )
            body = _digital_body_from_payload(capture_payload)
            snapshot = build_reconsolidation_snapshot(
                current_event={"kind": "user_utterance"},
                appraisal={"interaction_frame": "task"},
                world_model_state={},
                semantic_narrative_profile={},
                latent_state={"self_coherence": 0.8},
                emotion_state={"label": "focused"},
                bond_state={"trust": 0.6},
                behavior_action={"interaction_mode": "tooling"},
                action_packets=[packet],
                digital_body_state=body,
            )
            consequence = resolve_digital_body_consequence(
                digital_body_consequence={},
                digital_body_state=body,
                action_packets=[packet],
                reconsolidation_snapshot=snapshot,
            )
        finally:
            reset_tool_runtime_caches()
            reset_browser_session_manager_cache()

        assert consequence["kind"] == "browser_navigation_completed"
        assert consequence["browser_run_id"] == "ap-browser-capture-1"
        assert consequence["browser_profile_id"]
        assert consequence["browser_page_id"] == "page-1"
        assert consequence["artifact_carrier"] == "browser_page"
        assert consequence["preferred_source_ref_id"] > 0
        assert consequence["browser_runtime_state"]["last_run_id"] == "ap-browser-capture-1"


def test_sensitive_fill_resolves_to_takeover_requested_not_completed_fact():
    with TemporaryDirectory() as td:
        runtime_dir = Path(td) / "runtime"
        fixture = _site_fixture(runtime_dir)
        try:
            with patch.dict(os.environ, _browser_env(runtime_dir), clear=True):
                open_payload = browser_open_url.invoke(
                    {"url": fixture["index_url"], "proposal_id": "ap-browser-open-2", "access_hints": fixture["access_hints"]}
                )
                fill_payload = browser_fill.invoke(
                    {
                        "target_ref": _password_ref(open_payload),
                        "text": "secret",
                        "proposal_id": "ap-browser-fill-1",
                        "access_hints": dict(open_payload.get("access_hints") or {}),
                    }
                )

            packet = build_tool_action_packet(
                tool_name="browser_fill",
                proposal_id="ap-browser-fill-1",
                args={"text": "secret"},
                action="approve",
                status="blocked",
                result_summary=str(fill_payload.get("summary") or ""),
                block_reason=str(fill_payload.get("browser_execution_result", {}).get("error_summary") or ""),
                browser_execution_spec=dict(fill_payload.get("browser_execution_spec") or {}),
                browser_execution_preview=dict(fill_payload.get("browser_execution_preview") or {}),
                browser_execution_result=dict(fill_payload.get("browser_execution_result") or {}),
            )
            body = _digital_body_from_payload(fill_payload)
            snapshot = build_reconsolidation_snapshot(
                current_event={"kind": "user_utterance"},
                appraisal={"interaction_frame": "task"},
                world_model_state={},
                semantic_narrative_profile={},
                latent_state={"self_coherence": 0.8},
                emotion_state={"label": "focused"},
                bond_state={"trust": 0.6},
                behavior_action={"interaction_mode": "tooling"},
                action_packets=[packet],
                digital_body_state=body,
            )
            consequence = resolve_digital_body_consequence(
                digital_body_consequence={},
                digital_body_state=body,
                action_packets=[packet],
                reconsolidation_snapshot=snapshot,
            )
        finally:
            reset_tool_runtime_caches()
            reset_browser_session_manager_cache()

        assert consequence["kind"] == "browser_takeover_requested"
        assert consequence["browser_last_exit_status"] == "blocked"
        assert consequence["browser_runtime_state"]["manual_takeover_required"] is True
