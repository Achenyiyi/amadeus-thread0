from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from amadeus_thread0.evolution_engine.reconsolidation import build_reconsolidation_snapshot  # noqa: E402
from amadeus_thread0.graph_parts.action_packets import build_tool_action_packet  # noqa: E402
from amadeus_thread0.runtime.browser_runner import reset_browser_session_manager_cache  # noqa: E402
from amadeus_thread0.utils.tools import (  # noqa: E402
    browser_begin_manual_takeover,
    browser_capture_page_to_source_ref,
    browser_click,
    browser_download_click,
    browser_fill,
    browser_follow_link,
    browser_open_url,
    browser_snapshot,
    browser_upload_file,
    build_browser_execution_spec_payload,
    inspect_source_ref,
    preview_browser_execution,
    reset_tool_runtime_caches,
)

REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
TMP_ROOT = PROJECT_ROOT / "evals" / "_tmp" / "live-browser-runtime"
TMP_ROOT.mkdir(parents=True, exist_ok=True)


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _env(runtime_dir: Path) -> dict[str, str]:
    return {
        "AMADEUS_DATA_DIR": str(runtime_dir),
        "AMADEUS_MODEL_PROVIDER": "openai_compatible",
        "AMADEUS_BROWSER_HEADLESS": "1",
    }


def _invoke(tool: Any, args: dict[str, Any], *, runtime_dir: Path) -> dict[str, Any]:
    with patch.dict(os.environ, _env(runtime_dir), clear=False):
        return tool.invoke(args)


def _setup_browser_fixture(root: Path) -> dict[str, Any]:
    workspace = root / "workspaces" / "browser-smoke"
    pages = root / "pages"
    workspace.mkdir(parents=True, exist_ok=True)
    pages.mkdir(parents=True, exist_ok=True)
    (workspace / "upload.txt").write_text("upload-body\n", encoding="utf-8")
    (pages / "payload.txt").write_text("download-body\n", encoding="utf-8")
    (pages / "index.html").write_text(
        "\n".join(
            [
                "<!doctype html>",
                "<html>",
                "  <head>",
                '    <meta charset="utf-8" />',
                "    <title>Start Page</title>",
                "  </head>",
                "  <body>",
                "    <h1>Start Page</h1>",
                '    <a href="next.html">Read more</a>',
                '    <button onclick="document.getElementById(\'status\').textContent=\'clicked\';">Approve action</button>',
                '    <a href="payload.txt" download>Download payload</a>',
                '    <a href="login.html">Login</a>',
                '    <input type="file" aria-label="Upload document" onchange="document.getElementById(\'upload-result\').textContent = this.files[0] ? this.files[0].name : \"\";" />',
                '    <div id="status">idle</div>',
                '    <div id="upload-result"></div>',
                "  </body>",
                "</html>",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (pages / "next.html").write_text(
        "\n".join(
            [
                "<!doctype html>",
                "<html>",
                "  <head>",
                '    <meta charset="utf-8" />',
                "    <title>Next Page</title>",
                "  </head>",
                "  <body>",
                "    <h1>Next Page</h1>",
                "    <p>Live continuity target.</p>",
                "  </body>",
                "</html>",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (pages / "login.html").write_text(
        "\n".join(
            [
                "<!doctype html>",
                "<html>",
                "  <head>",
                '    <meta charset="utf-8" />',
                "    <title>Login Page</title>",
                "  </head>",
                "  <body>",
                "    <h1>Login Page</h1>",
                '    <label>User <input type="text" aria-label="User Name" /></label>',
                '    <label>Password <input type="password" aria-label="Password" /></label>',
                "    <button>Submit</button>",
                "  </body>",
                "</html>",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (pages / "logged-in.html").write_text(
        "\n".join(
            [
                "<!doctype html>",
                "<html>",
                "  <head>",
                '    <meta charset="utf-8" />',
                "    <title>Logged In</title>",
                "  </head>",
                "  <body>",
                "    <h1>Logged In</h1>",
                "    <p>Browser session resumed.</p>",
                "  </body>",
                "</html>",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "workspace": workspace,
        "pages": pages,
        "index_url": (pages / "index.html").resolve(strict=False).as_uri(),
        "next_url": (pages / "next.html").resolve(strict=False).as_uri(),
        "login_url": (pages / "login.html").resolve(strict=False).as_uri(),
        "logged_in_url": (pages / "logged-in.html").resolve(strict=False).as_uri(),
        "upload_source": workspace / "upload.txt",
    }


def _access_hints(fixture: dict[str, Any]) -> dict[str, Any]:
    workspace = Path(fixture["workspace"])
    return {
        "filesystem_state": "writable",
        "workspace_root": str(workspace),
        "active_artifact_kind": "workspace",
        "active_artifact_ref": str(workspace),
        "active_artifact_label": workspace.name,
    }


class _SmokeAttachmentHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, directory: str, **kwargs: Any) -> None:
        super().__init__(*args, directory=directory, **kwargs)

    def end_headers(self) -> None:
        if self.path.endswith("/payload.txt"):
            self.send_header("Content-Disposition", 'attachment; filename="payload.txt"')
            self.send_header("Content-Type", "text/plain; charset=utf-8")
        super().end_headers()

    def log_message(self, format: str, *args: Any) -> None:  # pragma: no cover - test noise suppression
        return


@contextmanager
def _attachment_server(pages_dir: Path):
    handler = partial(_SmokeAttachmentHandler, directory=str(pages_dir))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _target_ref(payload: dict[str, Any], *, label_contains: str = "", href_contains: str = "", input_type: str = "", tag: str = "") -> str:
    rows = _list(_dict(payload.get("browser_execution_result")).get("snapshot_targets"))
    for item in rows:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").lower()
        href = str(item.get("href") or "").lower()
        row_input_type = str(item.get("input_type") or "").lower()
        row_tag = str(item.get("tag") or "").lower()
        if label_contains and label_contains.lower() not in label:
            continue
        if href_contains and href_contains.lower() not in href:
            continue
        if input_type and input_type.lower() != row_input_type:
            continue
        if tag and tag.lower() != row_tag:
            continue
        return str(item.get("target_ref") or "")
    raise AssertionError(f"could not find target ref: label={label_contains!r} href={href_contains!r} input_type={input_type!r} tag={tag!r} rows={rows!r}")


def _body_from_payload(payload: dict[str, Any], *, surface: str = "tooling") -> dict[str, Any]:
    access = _dict(payload.get("access_state"))
    resource = _dict(payload.get("resource_state"))
    action_channels = ["language", "structured_action", "tooling"]
    if str(access.get("mode") or "").strip().lower() == "approval_pending":
        surface = "approval_gate"
        action_channels = ["language", "structured_action", "approval_gate", "tooling"]
    world_surfaces: list[str] = []
    if _dict(access.get("browser_runtime_state")) or str(access.get("browser_session") or "").strip():
        world_surfaces.append("browser")
    if str(access.get("filesystem_state") or "").strip():
        world_surfaces.append("filesystem")
    if str(access.get("network_access") or "").strip():
        world_surfaces.append("network")
    if not world_surfaces:
        world_surfaces = ["browser"]
    return {
        "active_surface": surface,
        "perception_channels": ["dialogue", "browser"],
        "action_channels": action_channels,
        "world_surfaces": list(dict.fromkeys(world_surfaces)),
        "access_state": access,
        "resource_state": resource,
    }


def _pending_body(current_payload: dict[str, Any]) -> dict[str, Any]:
    body = _body_from_payload(current_payload, surface="approval_gate")
    access = _dict(body.get("access_state"))
    permission = _dict(access.get("permission_state"))
    access["mode"] = "approval_pending"
    access["pending_approval_count"] = 1
    access["external_mutation_pending"] = True
    access["requestable_access"] = list(dict.fromkeys([*(_list(access.get("requestable_access"))), "human_approval"]))
    permission["approval_state"] = "approval_pending"
    permission["pending_approval_count"] = 1
    permission["external_mutation_pending"] = True
    permission["requestable_access"] = list(dict.fromkeys([*(_list(permission.get("requestable_access"))), "human_approval"]))
    access["permission_state"] = permission
    body["access_state"] = access
    resource = _dict(body.get("resource_state"))
    resource["pending_approval_count"] = 1
    body["resource_state"] = resource
    return body


def _browser_packet(tool_name: str, proposal_id: str, args: dict[str, Any], payload: dict[str, Any], *, status: str | None = None) -> dict[str, Any]:
    browser_result = _dict(payload.get("browser_execution_result"))
    packet_status = status or str(browser_result.get("status") or "completed").strip().lower() or "completed"
    return build_tool_action_packet(
        tool_name=tool_name,
        proposal_id=proposal_id,
        args=args,
        action="approve",
        status=packet_status,
        result_summary=str(payload.get("summary") or "").strip(),
        block_reason=str(browser_result.get("error_summary") or "").strip(),
        browser_execution_spec=_dict(payload.get("browser_execution_spec")),
        browser_execution_preview=_dict(payload.get("browser_execution_preview")),
        browser_execution_result=browser_result,
    )


def _pending_browser_packet(tool_name: str, proposal_id: str, args: dict[str, Any], *, runtime_dir: Path) -> dict[str, Any]:
    with patch.dict(os.environ, _env(runtime_dir), clear=False):
        browser_execution_spec = build_browser_execution_spec_payload(tool_name, args)
        browser_execution_preview = preview_browser_execution(tool_name, args)
    return build_tool_action_packet(
        tool_name=tool_name,
        proposal_id=proposal_id,
        args=args,
        action="approve",
        status="awaiting_approval",
        result_summary="pending browser approval",
        browser_execution_spec=browser_execution_spec,
        browser_execution_preview=browser_execution_preview,
    )


def _intent(proposal_id: str, mode: str) -> dict[str, Any]:
    return {
        "mode": mode,
        "origin": "counterpart_request",
        "reason": "live browser runtime phase 1",
        "primary_proposal_id": proposal_id,
    }


def _step(step_id: str, final_text: str, body: dict[str, Any], packet: dict[str, Any], *, mode: str, trace: list[dict[str, Any]] | None = None, pending: dict[str, Any] | None = None, carryover: dict[str, Any] | None = None) -> dict[str, Any]:
    trace_rows = list(trace or [])
    carry = dict(carryover or {})
    snapshot = build_reconsolidation_snapshot(
        current_event={"kind": "user_utterance"},
        appraisal={"interaction_frame": "task"},
        world_model_state={},
        semantic_narrative_profile={},
        latent_state={"self_coherence": 0.82},
        emotion_state={"label": "focused"},
        bond_state={"trust": 0.6},
        behavior_action={"interaction_mode": "tooling"},
        interaction_carryover=carry,
        autonomy_intent=_intent(str(packet.get("proposal_id") or ""), mode),
        action_packets=[packet],
        action_trace=trace_rows,
        digital_body_state=body,
    )
    consequence = _dict(snapshot.get("digital_body_consequence"))
    autonomy = {
        "intent": _intent(str(packet.get("proposal_id") or ""), mode),
        "action_packets": [packet],
        "pending_approval": dict(pending or {}),
        "execution_trace": trace_rows,
        "block_reason": str(packet.get("block_reason") or ""),
    }
    return {
        "id": step_id,
        "final_text": final_text,
        "autonomy": autonomy,
        "digital_body": body,
        "digital_body_consequence": consequence,
        "key_packet_trace": [packet],
        "reconsolidation_snapshot": snapshot,
        "interaction_carryover": carry,
    }

def _sc_open_follow_continue(run_root: Path) -> dict[str, Any]:
    runtime_dir = run_root / "open_follow_continue"
    fixture = _setup_browser_fixture(runtime_dir)
    try:
        open_payload = _invoke(browser_open_url, {"url": fixture["index_url"], "proposal_id": "ap-browser-open-1", "access_hints": _access_hints(fixture)}, runtime_dir=runtime_dir)
        link_ref = _target_ref(open_payload, href_contains="next.html")
        follow_payload = _invoke(browser_follow_link, {"target_ref": link_ref, "proposal_id": "ap-browser-follow-1", "access_hints": _dict(open_payload.get("access_hints"))}, runtime_dir=runtime_dir)
        continue_payload = _invoke(browser_snapshot, {"proposal_id": "ap-browser-snapshot-1", "access_hints": _dict(follow_payload.get("access_hints"))}, runtime_dir=runtime_dir)
        open_step = _step(
            "open",
            "Opened the live page in the persistent browser runtime.",
            _body_from_payload(open_payload),
            _browser_packet("browser_open_url", "ap-browser-open-1", {"url": fixture["index_url"]}, open_payload),
            mode="execute",
            trace=[{"proposal_id": "ap-browser-open-1", "event": "tool_completed", "tool_name": "browser_open_url", "status": "completed"}],
        )
        follow_step = _step(
            "follow",
            "Followed the link inside the same live browser tab.",
            _body_from_payload(follow_payload),
            _browser_packet("browser_follow_link", "ap-browser-follow-1", {"target_ref": link_ref}, follow_payload),
            mode="execute",
            trace=[{"proposal_id": "ap-browser-follow-1", "event": "tool_completed", "tool_name": "browser_follow_link", "status": "completed"}],
            carryover={"mode": "task_window", "note": "Continue from the same live page.", "embodied_context": _dict(open_step.get("digital_body_consequence"))},
        )
        continue_step = _step(
            "continue",
            "Continued from the same live page without falling back to saved material.",
            _body_from_payload(continue_payload),
            _browser_packet("browser_snapshot", "ap-browser-snapshot-1", {}, continue_payload),
            mode="continue",
            trace=[{"proposal_id": "ap-browser-snapshot-1", "event": "tool_completed", "tool_name": "browser_snapshot", "status": "completed"}],
            carryover={"mode": "task_window", "note": "Keep following the same live page.", "embodied_context": _dict(follow_step.get("digital_body_consequence"))},
        )
        return {"id": "open_follow_continue", "title": "open_follow_continue", "focus": "Open a public page, follow a link, then keep working on the same live page continuity.", "steps": [open_step, follow_step, continue_step]}
    finally:
        reset_tool_runtime_caches()
        reset_browser_session_manager_cache()


def _sc_login_takeover_resume(run_root: Path) -> dict[str, Any]:
    runtime_dir = run_root / "login_takeover_resume"
    fixture = _setup_browser_fixture(runtime_dir)
    try:
        login_payload = _invoke(browser_open_url, {"url": fixture["login_url"], "proposal_id": "ap-browser-login-open-1", "access_hints": _access_hints(fixture)}, runtime_dir=runtime_dir)
        password_ref = _target_ref(login_payload, input_type="password")
        pending_args = {"target_ref": password_ref, "text": "super-secret", "access_hints": _dict(login_payload.get("access_hints")), "proposal_id": "ap-browser-fill-1"}
        pending_packet = _pending_browser_packet("browser_fill", "ap-browser-fill-1", pending_args, runtime_dir=runtime_dir)
        pending_step = _step(
            "awaiting_approval",
            "Sensitive browser input is waiting at the approval and takeover boundary.",
            _pending_body(login_payload),
            pending_packet,
            mode="approval_pending",
            trace=[{"proposal_id": "ap-browser-fill-1", "event": "approval_requested", "tool_name": "browser_fill", "status": "awaiting_approval"}],
            pending=pending_packet,
        )
        blocked_payload = _invoke(browser_fill, pending_args, runtime_dir=runtime_dir)
        blocked_packet = _browser_packet("browser_fill", "ap-browser-fill-1", pending_args, blocked_payload, status="blocked")
        blocked_step = _step(
            "manual_takeover_required",
            "The browser runtime stopped at a sensitive credential step and requested manual takeover.",
            _body_from_payload(blocked_payload),
            blocked_packet,
            mode="blocked",
            trace=[{"proposal_id": "ap-browser-fill-1", "event": "tool_blocked", "tool_name": "browser_fill", "status": "blocked"}],
        )
        takeover_args = {"access_hints": _dict(blocked_payload.get("access_hints")), "proposal_id": "ap-browser-takeover-1"}
        takeover_payload = _invoke(browser_begin_manual_takeover, takeover_args, runtime_dir=runtime_dir)
        takeover_step = _step(
            "takeover_requested",
            "Manual browser takeover has been requested on the current persistent profile.",
            _body_from_payload(takeover_payload),
            _browser_packet("browser_begin_manual_takeover", "ap-browser-takeover-1", takeover_args, takeover_payload),
            mode="execute",
            trace=[{"proposal_id": "ap-browser-takeover-1", "event": "tool_completed", "tool_name": "browser_begin_manual_takeover", "status": "completed"}],
            carryover={"mode": "task_window", "note": "Manual takeover requested on the same browser profile.", "embodied_context": _dict(blocked_step.get("digital_body_consequence"))},
        )
        resume_payload = _invoke(browser_open_url, {"url": fixture["logged_in_url"], "proposal_id": "ap-browser-login-resume-1", "access_hints": _dict(takeover_payload.get("access_hints"))}, runtime_dir=runtime_dir)
        resume_step = _step(
            "resume",
            "Execution resumed on the same browser profile after manual takeover.",
            _body_from_payload(resume_payload),
            _browser_packet("browser_open_url", "ap-browser-login-resume-1", {"url": fixture["logged_in_url"]}, resume_payload),
            mode="execute",
            trace=[{"proposal_id": "ap-browser-login-resume-1", "event": "tool_completed", "tool_name": "browser_open_url", "status": "completed"}],
            carryover={"mode": "task_window", "note": "Resume on the same persistent profile after manual takeover.", "embodied_context": _dict(takeover_step.get("digital_body_consequence"))},
        )
        return {"id": "login_takeover_resume", "title": "login_takeover_resume", "focus": "Sensitive login input should request manual takeover, then resume on the same browser profile.", "steps": [pending_step, blocked_step, takeover_step, resume_step]}
    finally:
        reset_tool_runtime_caches()
        reset_browser_session_manager_cache()

def _sc_interaction_after_approval(run_root: Path) -> dict[str, Any]:
    runtime_dir = run_root / "interaction_after_approval"
    fixture = _setup_browser_fixture(runtime_dir)
    try:
        open_payload = _invoke(browser_open_url, {"url": fixture["index_url"], "proposal_id": "ap-browser-open-2", "access_hints": _access_hints(fixture)}, runtime_dir=runtime_dir)
        button_ref = _target_ref(open_payload, tag="button")
        args = {"target_ref": button_ref, "access_hints": _dict(open_payload.get("access_hints")), "proposal_id": "ap-browser-click-1"}
        pending_packet = _pending_browser_packet("browser_click", "ap-browser-click-1", args, runtime_dir=runtime_dir)
        pending_step = _step(
            "awaiting_approval",
            "The click is pending approval before any external browser mutation happens.",
            _pending_body(open_payload),
            pending_packet,
            mode="approval_pending",
            trace=[{"proposal_id": "ap-browser-click-1", "event": "approval_requested", "tool_name": "browser_click", "status": "awaiting_approval"}],
            pending=pending_packet,
        )
        completed_payload = _invoke(browser_click, args, runtime_dir=runtime_dir)
        completed_step = _step(
            "completed",
            "The approved browser interaction executed on the live page.",
            _body_from_payload(completed_payload),
            _browser_packet("browser_click", "ap-browser-click-1", args, completed_payload),
            mode="execute",
            trace=[
                {"proposal_id": "ap-browser-click-1", "event": "approval_requested", "tool_name": "browser_click", "status": "awaiting_approval"},
                {"proposal_id": "ap-browser-click-1", "event": "approval_resolved", "tool_name": "browser_click", "status": "approved"},
                {"proposal_id": "ap-browser-click-1", "event": "tool_completed", "tool_name": "browser_click", "status": "completed"},
            ],
        )
        return {"id": "interaction_after_approval", "title": "interaction_after_approval", "focus": "A button interaction should remain pending until approval, then execute truthfully on the live page.", "steps": [pending_step, completed_step]}
    finally:
        reset_tool_runtime_caches()
        reset_browser_session_manager_cache()


def _sc_download_boundary(run_root: Path) -> dict[str, Any]:
    runtime_dir = run_root / "download_boundary"
    fixture = _setup_browser_fixture(runtime_dir)
    try:
        with _attachment_server(Path(fixture["pages"])) as base_url:
            open_payload = _invoke(browser_open_url, {"url": f"{base_url}/index.html", "proposal_id": "ap-browser-open-3", "access_hints": _access_hints(fixture)}, runtime_dir=runtime_dir)
            link_ref = _target_ref(open_payload, href_contains="payload.txt")
            args = {"target_ref": link_ref, "download_target": "downloads/payload.txt", "access_hints": _dict(open_payload.get("access_hints")), "proposal_id": "ap-browser-download-1"}
            pending_packet = _pending_browser_packet("browser_download_click", "ap-browser-download-1", args, runtime_dir=runtime_dir)
            pending_step = _step(
                "awaiting_approval",
                "The download is waiting for approval before writing into the controlled directory.",
                _pending_body(open_payload),
                pending_packet,
                mode="approval_pending",
                trace=[{"proposal_id": "ap-browser-download-1", "event": "approval_requested", "tool_name": "browser_download_click", "status": "awaiting_approval"}],
                pending=pending_packet,
            )
            completed_payload = _invoke(browser_download_click, args, runtime_dir=runtime_dir)
            completed_step = _step(
                "completed",
                "The browser download completed into the controlled filesystem surface.",
                _body_from_payload(completed_payload),
                _browser_packet("browser_download_click", "ap-browser-download-1", args, completed_payload),
                mode="execute",
                trace=[
                    {"proposal_id": "ap-browser-download-1", "event": "approval_requested", "tool_name": "browser_download_click", "status": "awaiting_approval"},
                    {"proposal_id": "ap-browser-download-1", "event": "approval_resolved", "tool_name": "browser_download_click", "status": "approved"},
                    {"proposal_id": "ap-browser-download-1", "event": "tool_completed", "tool_name": "browser_download_click", "status": "completed"},
                ],
            )
        return {"id": "download_boundary", "title": "download_boundary", "focus": "Browser downloads should stay approval-gated and land in the controlled directory with truthful artifact continuity.", "steps": [pending_step, completed_step]}
    finally:
        reset_tool_runtime_caches()
        reset_browser_session_manager_cache()


def _sc_upload_boundary(run_root: Path) -> dict[str, Any]:
    runtime_dir = run_root / "upload_boundary"
    fixture = _setup_browser_fixture(runtime_dir)
    try:
        open_payload = _invoke(browser_open_url, {"url": fixture["index_url"], "proposal_id": "ap-browser-open-4", "access_hints": _access_hints(fixture)}, runtime_dir=runtime_dir)
        upload_ref = _target_ref(open_payload, input_type="file")
        args = {"target_ref": upload_ref, "upload_source": Path(fixture["upload_source"]).name, "access_hints": _dict(open_payload.get("access_hints")), "proposal_id": "ap-browser-upload-1"}
        pending_packet = _pending_browser_packet("browser_upload_file", "ap-browser-upload-1", args, runtime_dir=runtime_dir)
        pending_step = _step(
            "awaiting_approval",
            "The upload is waiting for approval before mutating the live page.",
            _pending_body(open_payload),
            pending_packet,
            mode="approval_pending",
            trace=[{"proposal_id": "ap-browser-upload-1", "event": "approval_requested", "tool_name": "browser_upload_file", "status": "awaiting_approval"}],
            pending=pending_packet,
        )
        completed_payload = _invoke(browser_upload_file, args, runtime_dir=runtime_dir)
        completed_step = _step(
            "completed",
            "The approved upload executed from the controlled workspace file.",
            _body_from_payload(completed_payload),
            _browser_packet("browser_upload_file", "ap-browser-upload-1", args, completed_payload),
            mode="execute",
            trace=[
                {"proposal_id": "ap-browser-upload-1", "event": "approval_requested", "tool_name": "browser_upload_file", "status": "awaiting_approval"},
                {"proposal_id": "ap-browser-upload-1", "event": "approval_resolved", "tool_name": "browser_upload_file", "status": "approved"},
                {"proposal_id": "ap-browser-upload-1", "event": "tool_completed", "tool_name": "browser_upload_file", "status": "completed"},
            ],
        )
        return {"id": "upload_boundary", "title": "upload_boundary", "focus": "Browser uploads should stay approval-gated and only use files from the controlled workspace roots.", "steps": [pending_step, completed_step]}
    finally:
        reset_tool_runtime_caches()
        reset_browser_session_manager_cache()


def _sc_capture_to_source_ref(run_root: Path) -> dict[str, Any]:
    runtime_dir = run_root / "capture_to_source_ref"
    fixture = _setup_browser_fixture(runtime_dir)
    try:
        open_payload = _invoke(browser_open_url, {"url": fixture["next_url"], "proposal_id": "ap-browser-open-5", "access_hints": _access_hints(fixture)}, runtime_dir=runtime_dir)
        capture_payload = _invoke(browser_capture_page_to_source_ref, {"proposal_id": "ap-browser-capture-1", "access_hints": _dict(open_payload.get("access_hints"))}, runtime_dir=runtime_dir)
        source_ref_id = int((_list(capture_payload.get("source_ref_ids")) or [0])[0] or 0)
        inspect_payload = _invoke(inspect_source_ref, {"source_ref_id": source_ref_id, "access_hints": _dict(capture_payload.get("access_hints"))}, runtime_dir=runtime_dir)
        capture_step = _step(
            "capture",
            "Captured the current live page into source_ref while preserving live browser continuity.",
            _body_from_payload(capture_payload),
            _browser_packet("browser_capture_page_to_source_ref", "ap-browser-capture-1", {}, capture_payload),
            mode="execute",
            trace=[{"proposal_id": "ap-browser-capture-1", "event": "tool_completed", "tool_name": "browser_capture_page_to_source_ref", "status": "completed"}],
        )
        inspect_packet = build_tool_action_packet(tool_name="inspect_source_ref", proposal_id="ap-source-inspect-1", args={"source_ref_id": source_ref_id}, status="completed", result_summary=str(inspect_payload.get("summary") or ""))
        inspect_step = _step(
            "inspect_saved_material",
            "Continued from the saved source_ref path after capturing the live page.",
            _body_from_payload(inspect_payload),
            inspect_packet,
            mode="continue",
            trace=[{"proposal_id": "ap-source-inspect-1", "event": "tool_completed", "tool_name": "inspect_source_ref", "status": "completed"}],
            carryover={"mode": "task_window", "note": "Continue from either the live page or the saved source_ref.", "embodied_context": _dict(capture_step.get("digital_body_consequence"))},
        )
        return {"id": "capture_to_source_ref", "title": "capture_to_source_ref", "focus": "Capturing a live page should write a saved source_ref while keeping both the live-page and saved-material paths truthful.", "steps": [capture_step, inspect_step]}
    finally:
        reset_tool_runtime_caches()
        reset_browser_session_manager_cache()

def _scenario_specs(run_root: Path) -> list[dict[str, Any]]:
    return [
        _sc_open_follow_continue(run_root),
        _sc_login_takeover_resume(run_root),
        _sc_interaction_after_approval(run_root),
        _sc_download_boundary(run_root),
        _sc_upload_boundary(run_root),
        _sc_capture_to_source_ref(run_root),
    ]


def _check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def _evaluate(result: dict[str, Any]) -> dict[str, Any]:
    scenario_id = str(result.get("id") or "")
    steps = [_dict(item) for item in _list(result.get("steps"))]
    checks: list[dict[str, Any]]
    if scenario_id == "open_follow_continue":
        _, follow_step, cont_step = steps
        follow_resource = _dict(_dict(follow_step.get("digital_body")).get("resource_state"))
        cont_resource = _dict(_dict(cont_step.get("digital_body")).get("resource_state"))
        follow_consequence = _dict(follow_step.get("digital_body_consequence"))
        cont_consequence = _dict(cont_step.get("digital_body_consequence"))
        checks = [
            _check("same_browser_profile", str(follow_resource.get("browser_profile_id") or "") == str(cont_resource.get("browser_profile_id") or ""), f"follow={follow_resource} continue={cont_resource}"),
            _check("same_live_page_ref", str(follow_resource.get("active_artifact_ref") or "") == str(cont_resource.get("active_artifact_ref") or ""), f"follow={follow_resource} continue={cont_resource}"),
            _check("follow_navigation_fact", follow_consequence.get("kind") == "browser_navigation_completed", str(follow_consequence)),
            _check("continue_stays_browser_page", cont_resource.get("artifact_carrier") == "browser_page" and cont_consequence.get("kind") == "browser_navigation_completed", f"resource={cont_resource} consequence={cont_consequence}"),
        ]
    elif scenario_id == "login_takeover_resume":
        pending_step, blocked_step, takeover_step, resume_step = steps
        blocked_consequence = _dict(blocked_step.get("digital_body_consequence"))
        takeover_consequence = _dict(takeover_step.get("digital_body_consequence"))
        resume_consequence = _dict(resume_step.get("digital_body_consequence"))
        blocked_access = _dict(_dict(blocked_step.get("digital_body")).get("access_state"))
        takeover_access = _dict(_dict(takeover_step.get("digital_body")).get("access_state"))
        resume_resource = _dict(_dict(resume_step.get("digital_body")).get("resource_state"))
        checks = [
            _check("pending_fill_is_approval_gated", bool(_dict(pending_step.get("autonomy")).get("pending_approval")), str(pending_step.get("autonomy"))),
            _check("blocked_fill_requests_takeover", blocked_consequence.get("kind") == "browser_takeover_requested" and bool(_dict(blocked_access.get("browser_runtime_state")).get("manual_takeover_required", False)), f"consequence={blocked_consequence} access={blocked_access}"),
            _check("explicit_takeover_recorded", takeover_consequence.get("kind") == "browser_takeover_requested" and bool(_dict(takeover_access.get("browser_runtime_state")).get("manual_takeover_required", False)), f"consequence={takeover_consequence} access={takeover_access}"),
            _check("resume_uses_same_profile", str(blocked_consequence.get("browser_profile_id") or "") == str(resume_resource.get("browser_profile_id") or "") and str(resume_consequence.get("kind") or "") == "browser_navigation_completed", f"blocked={blocked_consequence} resume_resource={resume_resource} resume_consequence={resume_consequence}"),
        ]
    elif scenario_id == "interaction_after_approval":
        pending_step, completed_step = steps
        pending_consequence = _dict(pending_step.get("digital_body_consequence"))
        completed_consequence = _dict(completed_step.get("digital_body_consequence"))
        completed_packet = _dict((_list(_dict(completed_step.get("autonomy")).get("action_packets")) or [{}])[0])
        browser_result = _dict(completed_packet.get("browser_execution_result"))
        checks = [
            _check("pending_not_written_as_completed", pending_consequence.get("kind") == "access_request_pending", str(pending_consequence)),
            _check("interaction_completed_after_approval", completed_consequence.get("kind") == "browser_interaction_completed", str(completed_consequence)),
            _check("interaction_result_completed", browser_result.get("status") == "completed" and browser_result.get("last_action_status") == "completed", str(browser_result)),
            _check("live_page_retained", _dict(_dict(completed_step.get("digital_body")).get("resource_state")).get("artifact_carrier") == "browser_page", str(completed_step.get("digital_body"))),
        ]
    elif scenario_id == "download_boundary":
        pending_step, completed_step = steps
        resource = _dict(_dict(completed_step.get("digital_body")).get("resource_state"))
        consequence = _dict(completed_step.get("digital_body_consequence"))
        packet = _dict((_list(_dict(completed_step.get("autonomy")).get("action_packets")) or [{}])[0])
        browser_result = _dict(packet.get("browser_execution_result"))
        checks = [
            _check("pending_download_is_approval_gated", bool(_dict(pending_step.get("autonomy")).get("pending_approval")), str(pending_step.get("autonomy"))),
            _check("download_artifact_exists", Path(str(browser_result.get("download_path") or "")).exists(), str(browser_result)),
            _check("download_promoted_to_filesystem", resource.get("artifact_carrier") == "filesystem" and resource.get("active_artifact_ref") == browser_result.get("download_path"), f"resource={resource} result={browser_result}"),
            _check("download_consequence_completed", consequence.get("kind") == "browser_download_completed", str(consequence)),
        ]
    elif scenario_id == "upload_boundary":
        pending_step, completed_step = steps
        consequence = _dict(completed_step.get("digital_body_consequence"))
        packet = _dict((_list(_dict(completed_step.get("autonomy")).get("action_packets")) or [{}])[0])
        browser_result = _dict(packet.get("browser_execution_result"))
        resource = _dict(_dict(completed_step.get("digital_body")).get("resource_state"))
        checks = [
            _check("pending_upload_is_approval_gated", bool(_dict(pending_step.get("autonomy")).get("pending_approval")), str(pending_step.get("autonomy"))),
            _check("upload_result_completed", browser_result.get("status") == "completed" and bool(str(browser_result.get("upload_source") or "").strip()), str(browser_result)),
            _check("upload_consequence_completed", consequence.get("kind") == "browser_upload_completed", str(consequence)),
            _check("upload_keeps_browser_page_surface", resource.get("artifact_carrier") == "browser_page", str(resource)),
        ]
    else:
        capture_step, inspect_step = steps
        capture_resource = _dict(_dict(capture_step.get("digital_body")).get("resource_state"))
        capture_consequence = _dict(capture_step.get("digital_body_consequence"))
        inspect_consequence = _dict(inspect_step.get("digital_body_consequence"))
        checks = [
            _check("capture_keeps_live_page_surface", capture_resource.get("artifact_carrier") == "browser_page", str(capture_resource)),
            _check("capture_writes_source_ref_identity", int(capture_resource.get("preferred_source_ref_id") or 0) > 0 and bool(_list(capture_resource.get("artifact_source_ref_ids"))), str(capture_resource)),
            _check("capture_consequence_is_browser_navigation", capture_consequence.get("kind") == "browser_navigation_completed", str(capture_consequence)),
            _check("followup_can_use_saved_material", inspect_consequence.get("kind") == "source_material_inspected", str(inspect_consequence)),
        ]
    return {"passed": all(check["passed"] for check in checks), "checks": checks}


def _run_single_scenario(spec: dict[str, Any]) -> dict[str, Any]:
    result = {key: spec[key] for key in ("id", "title", "focus")}
    result["steps"] = list(spec.get("steps") or [])
    result["duration_s"] = 0.0
    final_step = _dict(result["steps"][-1]) if result["steps"] else {}
    result["final_text"] = str(final_step.get("final_text") or "")
    result["autonomy"] = _dict(final_step.get("autonomy"))
    result["digital_body"] = _dict(final_step.get("digital_body"))
    result["digital_body_consequence"] = _dict(final_step.get("digital_body_consequence"))
    result["key_packet_trace"] = _list(final_step.get("key_packet_trace"))
    result["evaluation"] = _evaluate(result)
    return result

def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Live Browser Runtime Smokes ({report['run_id']})",
        "",
        f"Generated at: {report['generated_at']}",
        f"Overall Status: `{report['overall_status']}`",
        f"Passed: `{report['passed']}`",
        f"Failed: `{report['failed']}`",
        "",
        "## Scenario Summary",
        "",
        "| Scenario | Status |",
        "| --- | --- |",
    ]
    for result in report.get("results") or []:
        status = "passed" if _dict(result.get("evaluation")).get("passed") else "failed"
        lines.append(f"| `{result.get('id', '')}` | `{status}` |")
    for result in report.get("results") or []:
        evaluation = _dict(result.get("evaluation"))
        lines.extend([
            "",
            f"## {result.get('title', result.get('id', 'scenario'))}",
            "",
            f"- Focus: {result.get('focus', '')}",
            f"- Status: `{'passed' if evaluation.get('passed') else 'failed'}`",
            f"- Final Text: `{str(result.get('final_text') or '').strip()}`",
            f"- Autonomy: `{json.dumps(_dict(result.get('autonomy')), ensure_ascii=False)}`",
            f"- Digital Body: `{json.dumps(_dict(result.get('digital_body')), ensure_ascii=False)}`",
            f"- Digital Body Consequence: `{json.dumps(_dict(result.get('digital_body_consequence')), ensure_ascii=False)}`",
            f"- Key Packet Trace: `{json.dumps(_list(result.get('key_packet_trace')), ensure_ascii=False)}`",
            "- Checks:",
        ])
        for check in evaluation.get("checks") or []:
            lines.append(f"  - `{'pass' if check.get('passed') else 'fail'}` {check.get('name', '')}: {check.get('detail', '')}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run live browser runtime smoke scenarios.")
    parser.add_argument("--run-tag", default="")
    parser.add_argument("--scenario", action="append", default=[])
    args = parser.parse_args()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    run_root = TMP_ROOT / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    requested = {str(item or "").strip() for item in _list(args.scenario) if str(item or "").strip()}
    specs = _scenario_specs(run_root)
    if requested:
        specs = [spec for spec in specs if str(spec.get("id") or "") in requested]
        if not specs:
            available = ", ".join(sorted(str(spec.get("id") or "") for spec in _scenario_specs(run_root)))
            raise SystemExit(f"No live browser smoke scenarios matched {sorted(requested)!r}. Available: {available}")
    results = [_run_single_scenario(spec) for spec in specs]
    passed = len([result for result in results if _dict(result.get("evaluation")).get("passed")])
    failed = len(results) - passed
    report = {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": "passed" if failed == 0 else "failed",
        "passed": passed,
        "failed": failed,
        "results": results,
        "scenario_artifact_references": [
            {"id": str(result.get("id") or ""), "title": str(result.get("title") or ""), "status": "passed" if _dict(result.get("evaluation")).get("passed") else "failed"}
            for result in results
        ],
    }
    json_path = REPORT_DIR / f"live-browser-runtime-smokes-{run_id}.json"
    md_path = REPORT_DIR / f"live-browser-runtime-smokes-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(f"[live-browser-runtime-smokes] json={json_path}")
    print(f"[live-browser-runtime-smokes] md={md_path}")
    print(f"[live-browser-runtime-smokes] overall_status={report['overall_status']}")


if __name__ == "__main__":
    main()

