from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from amadeus_thread0.runtime.browser_runner import (
    BrowserSessionManager,
    BrowserValidationError,
    build_browser_execution_spec,
)


def _site_fixture(root: Path) -> dict[str, Path | str]:
    workspace = root / "workspace"
    pages = root / "pages"
    workspace.mkdir(parents=True, exist_ok=True)
    pages.mkdir(parents=True, exist_ok=True)
    (pages / "index.html").write_text(
        "\n".join(
            [
                "<!doctype html>",
                "<html><head><meta charset=\"utf-8\" /><title>Start</title></head>",
                "<body>",
                "<a href=\"next.html\">Read more</a>",
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
    }


def _target_ref(snapshot_targets: list[dict[str, object]], *, href_contains: str = "", input_type: str = "") -> str:
    for item in snapshot_targets:
        href = str(item.get("href") or "").lower()
        row_input_type = str(item.get("input_type") or "").lower()
        if href_contains and href_contains.lower() not in href:
            continue
        if input_type and input_type.lower() != row_input_type:
            continue
        return str(item.get("target_ref") or "")
    raise AssertionError(f"missing target ref for href={href_contains!r} input_type={input_type!r}")


def test_build_browser_execution_spec_rejects_download_outside_allowed_roots():
    with TemporaryDirectory() as td:
        workspace = Path(td) / "workspace"
        workspace.mkdir(parents=True)
        with pytest.raises(BrowserValidationError, match="escapes allowed roots"):
            build_browser_execution_spec(
                operation="download_click",
                profile_id="thread-browser",
                target_ref="e1",
                download_target=str((Path(td) / "outside" / "payload.txt").resolve(strict=False)),
                allowed_roots=[str(workspace)],
                browser_downloads_root=str((Path(td) / "downloads").resolve(strict=False)),
                timeout_s=20,
            )


def test_browser_session_manager_opens_and_follows_link_in_same_profile():
    with TemporaryDirectory() as td:
        runtime_dir = Path(td) / "runtime"
        fixture = _site_fixture(runtime_dir)
        manager = BrowserSessionManager(data_dir=runtime_dir)
        try:
            open_spec = build_browser_execution_spec(
                operation="open_url",
                profile_id="thread-browser",
                navigation_url=str(fixture["index_url"]),
                allowed_roots=[str(fixture["workspace"])],
                browser_downloads_root=str((runtime_dir / "downloads").resolve(strict=False)),
                timeout_s=20,
            )
            open_result = manager.execute(
                proposal_id="ap-browser-open-1",
                spec=open_spec,
                run_root=runtime_dir / "runs" / "ap-browser-open-1",
            )
            link_ref = _target_ref(open_result.snapshot_targets, href_contains="next.html")
            page_state = manager.current_page_state(profile_id="thread-browser")
            follow_spec = build_browser_execution_spec(
                operation="follow_link",
                profile_id="thread-browser",
                page_ref=str(page_state["page_ref"]),
                target_ref=link_ref,
                allowed_roots=[str(fixture["workspace"])],
                browser_downloads_root=str((runtime_dir / "downloads").resolve(strict=False)),
                timeout_s=20,
            )
            follow_result = manager.execute(
                proposal_id="ap-browser-follow-1",
                spec=follow_spec,
                run_root=runtime_dir / "runs" / "ap-browser-follow-1",
            )
        finally:
            manager.close_all()

        assert open_result.status == "completed"
        assert follow_result.status == "completed"
        assert follow_result.profile_id == "thread-browser"
        assert follow_result.page_id == "page-1"
        assert follow_result.tab_id == "tab-1"
        assert follow_result.title == "Next"


def test_browser_session_manager_blocks_sensitive_fill_and_requests_manual_takeover():
    with TemporaryDirectory() as td:
        runtime_dir = Path(td) / "runtime"
        fixture = _site_fixture(runtime_dir)
        manager = BrowserSessionManager(data_dir=runtime_dir)
        try:
            open_spec = build_browser_execution_spec(
                operation="open_url",
                profile_id="thread-browser",
                navigation_url=str(fixture["index_url"]),
                allowed_roots=[str(fixture["workspace"])],
                browser_downloads_root=str((runtime_dir / "downloads").resolve(strict=False)),
                timeout_s=20,
            )
            open_result = manager.execute(
                proposal_id="ap-browser-login-1",
                spec=open_spec,
                run_root=runtime_dir / "runs" / "ap-browser-login-1",
            )
            password_ref = _target_ref(open_result.snapshot_targets, input_type="password")
            page_state = manager.current_page_state(profile_id="thread-browser")
            fill_spec = build_browser_execution_spec(
                operation="fill",
                profile_id="thread-browser",
                page_ref=str(page_state["page_ref"]),
                target_ref=password_ref,
                input_text="secret",
                allowed_roots=[str(fixture["workspace"])],
                browser_downloads_root=str((runtime_dir / "downloads").resolve(strict=False)),
                timeout_s=20,
            )
            fill_result = manager.execute(
                proposal_id="ap-browser-fill-1",
                spec=fill_spec,
                run_root=runtime_dir / "runs" / "ap-browser-fill-1",
            )
        finally:
            manager.close_all()

        assert fill_result.status == "blocked"
        assert fill_result.manual_takeover_required is True
        assert fill_result.error_summary == "sensitive credential entry requires manual browser takeover"
