from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - import exercised in runtime/tests
    PlaywrightTimeoutError = RuntimeError  # type: ignore[assignment]
    sync_playwright = None  # type: ignore[assignment]


_ALLOWED_OPERATIONS = {
    "open_url",
    "follow_link",
    "list_tabs",
    "select_tab",
    "go_back",
    "go_forward",
    "reload",
    "snapshot",
    "capture_page",
    "click",
    "fill",
    "press_key",
    "download_click",
    "upload_file",
    "begin_manual_takeover",
}
_SENSITIVE_INPUT_TYPES = {"password", "otp", "one-time-code", "passkey"}
_FALSEY = {"0", "false", "no", "n", "off"}
_WAIT_UNTIL = {"commit", "domcontentloaded", "load", "networkidle"}


class BrowserValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = str(code or "INVALID_BROWSER_SPEC").strip().upper() or "INVALID_BROWSER_SPEC"


@dataclass(frozen=True)
class BrowserExecutionSpec:
    operation: str
    profile_id: str
    page_ref: str
    navigation_url: str
    target_ref: str
    input_text: str
    key: str
    upload_source: str
    download_target: str
    allowed_roots: list[str]
    browser_downloads_root: str
    timeout_s: int
    wait_until: str


@dataclass(frozen=True)
class BrowserExecutionResult:
    run_id: str
    status: str
    profile_id: str
    page_id: str
    tab_id: str
    url: str
    title: str
    action_kind: str
    target_ref: str
    duration_ms: int
    active_tab_count: int
    last_action_status: str
    download_path: str
    upload_source: str
    error_summary: str
    manual_takeover_required: bool
    snapshot_targets: list[dict[str, Any]] = field(default_factory=list)
    text_preview: str = ""


@dataclass
class _BrowserSession:
    profile_id: str
    profile_root: Path
    downloads_dir: Path
    context: Any
    target_maps: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    active_page_ref: str = ""
    manual_takeover_required: bool = False


def _clean_text(value: Any, *, limit: int = 320) -> str:
    return str(value or "").strip()[:limit]


def _clean_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _path_within_root(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except Exception:
        return False


def _normalize_allowed_roots(value: Any) -> list[Path]:
    if not isinstance(value, list):
        return []
    rows: list[Path] = []
    seen: set[str] = set()
    for item in value:
        text = _clean_text(item, limit=520)
        if not text:
            continue
        path = Path(text).expanduser().resolve(strict=False)
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        rows.append(path)
    return rows


def _clean_profile_id(value: Any) -> str:
    raw = _clean_text(value, limit=120).lower()
    raw = re.sub(r"[^a-z0-9._-]+", "-", raw)
    raw = re.sub(r"-{2,}", "-", raw).strip("-")
    return raw or "thread0"


def _page_id(index: int) -> str:
    return f"page-{max(1, int(index) + 1)}"


def _tab_id(index: int) -> str:
    return f"tab-{max(1, int(index) + 1)}"


def _page_ref(index: int) -> str:
    return f"page:{_page_id(index)}"


def _parse_page_index(page_ref: Any) -> int | None:
    text = _clean_text(page_ref, limit=64).lower()
    if not text:
        return None
    if text.startswith("page:"):
        text = text.split(":", 1)[1]
    match = re.fullmatch(r"(?:page-|tab-)?(\d+)", text)
    if not match:
        return None
    return max(1, int(match.group(1))) - 1


def _looks_sensitive_target(target: dict[str, Any]) -> bool:
    input_type = _clean_text(target.get("input_type"), limit=64).lower()
    autocomplete = _clean_text(target.get("autocomplete"), limit=64).lower()
    label = _clean_text(target.get("label"), limit=160).lower()
    if input_type in _SENSITIVE_INPUT_TYPES:
        return True
    if autocomplete in {"one-time-code", "current-password", "new-password"}:
        return True
    return any(marker in label for marker in ("验证码", "otp", "passkey", "password", "密码"))


def _normalized_url(value: Any) -> str:
    text = _clean_text(value, limit=1200)
    if not text:
        return ""
    parsed = urlparse(text)
    if parsed.scheme in {"http", "https", "file", "data"}:
        return text
    raise BrowserValidationError("INVALID_URL", "browser url must be http(s), file, or data")


def _resolve_upload_source(value: Any, *, allowed_roots: list[Path]) -> str:
    text = _clean_text(value, limit=520)
    if not text:
        return ""
    path = Path(text).expanduser()
    if not path.is_absolute():
        if not allowed_roots:
            raise BrowserValidationError("UPLOAD_ROOT_REQUIRED", "upload requires an allowed workspace root")
        path = (allowed_roots[0] / path).resolve(strict=False)
    else:
        path = path.resolve(strict=False)
    if not any(_path_within_root(path, root) for root in allowed_roots):
        raise BrowserValidationError("UPLOAD_OUTSIDE_ROOT", "upload source escapes allowed roots")
    if not path.exists() or not path.is_file():
        raise BrowserValidationError("UPLOAD_NOT_FOUND", "upload source file does not exist")
    return str(path)


def _resolve_download_target(value: Any, *, allowed_roots: list[Path], downloads_root: Path) -> str:
    text = _clean_text(value, limit=520)
    if not text:
        return ""
    path = Path(text).expanduser()
    if not path.is_absolute():
        base = allowed_roots[0] if allowed_roots else downloads_root
        path = (base / path).resolve(strict=False)
    else:
        path = path.resolve(strict=False)
    allowed = [*allowed_roots, downloads_root.resolve(strict=False)]
    if not any(_path_within_root(path, root) for root in allowed):
        raise BrowserValidationError("DOWNLOAD_OUTSIDE_ROOT", "download target escapes allowed roots")
    return str(path)


def build_browser_execution_spec(
    *,
    operation: Any,
    profile_id: Any,
    page_ref: Any = "",
    navigation_url: Any = "",
    target_ref: Any = "",
    input_text: Any = "",
    key: Any = "",
    upload_source: Any = "",
    download_target: Any = "",
    allowed_roots: Any = None,
    browser_downloads_root: Any = "",
    timeout_s: Any = 20,
    wait_until: Any = "load",
) -> BrowserExecutionSpec:
    op_name = _clean_text(operation, limit=64).lower()
    if op_name not in _ALLOWED_OPERATIONS:
        raise BrowserValidationError("INVALID_OPERATION", f"unsupported browser operation: {op_name}")
    profile = _clean_profile_id(profile_id)
    timeout_value = max(1, min(_clean_int(timeout_s, 20), 180))
    wait_state = _clean_text(wait_until, limit=32).lower() or "load"
    if wait_state not in _WAIT_UNTIL:
        wait_state = "load"
    roots = _normalize_allowed_roots(allowed_roots)
    downloads_root = Path(_clean_text(browser_downloads_root, limit=520) or ".").expanduser().resolve(strict=False)
    if op_name == "open_url":
        url = _normalized_url(navigation_url)
        if not url:
            raise BrowserValidationError("URL_REQUIRED", "browser_open_url requires a navigation url")
    else:
        url = _normalized_url(navigation_url) if _clean_text(navigation_url, limit=1200) else ""
    normalized_page_ref = _clean_text(page_ref, limit=64)
    normalized_target_ref = _clean_text(target_ref, limit=64)
    normalized_input_text = _clean_text(input_text, limit=4000)
    normalized_key = _clean_text(key, limit=64)
    if op_name in {"follow_link", "click", "fill", "download_click", "upload_file"} and not normalized_target_ref:
        raise BrowserValidationError("TARGET_REQUIRED", f"{op_name} requires a snapshot target_ref")
    if op_name == "fill" and not normalized_input_text:
        raise BrowserValidationError("INPUT_REQUIRED", "browser_fill requires input_text")
    if op_name == "press_key" and not normalized_key:
        raise BrowserValidationError("KEY_REQUIRED", "browser_press_key requires a key value")
    normalized_upload_source = ""
    if op_name == "upload_file":
        normalized_upload_source = _resolve_upload_source(upload_source, allowed_roots=roots)
    normalized_download_target = ""
    if op_name == "download_click":
        normalized_download_target = _resolve_download_target(download_target, allowed_roots=roots, downloads_root=downloads_root)
    return BrowserExecutionSpec(
        operation=op_name,
        profile_id=profile,
        page_ref=normalized_page_ref,
        navigation_url=url,
        target_ref=normalized_target_ref,
        input_text=normalized_input_text,
        key=normalized_key,
        upload_source=normalized_upload_source,
        download_target=normalized_download_target,
        allowed_roots=[str(root) for root in roots],
        browser_downloads_root=str(downloads_root),
        timeout_s=timeout_value,
        wait_until=wait_state,
    )


def build_browser_execution_preview(
    spec: BrowserExecutionSpec,
    *,
    page_url: str = "",
    page_title: str = "",
    target: dict[str, Any] | None = None,
    verification_summary: str = "",
) -> dict[str, Any]:
    target_row = dict(target or {}) if isinstance(target, dict) else {}
    preview = {
        "runner_kind": "playwright_persistent_context",
        "isolation_level": "persistent_profile_runtime",
        "operation": spec.operation,
        "profile_id": spec.profile_id,
        "page_ref": spec.page_ref,
        "page_url": _clean_text(page_url, limit=1200),
        "page_title": _clean_text(page_title, limit=220),
        "target_ref": spec.target_ref,
        "target_tag": _clean_text(target_row.get("tag"), limit=32).lower(),
        "target_label": _clean_text(target_row.get("label"), limit=220),
        "target_role": _clean_text(target_row.get("role"), limit=64).lower(),
        "target_input_type": _clean_text(target_row.get("input_type"), limit=64).lower(),
        "input_payload_schema": "",
        "download_target": spec.download_target,
        "upload_source": spec.upload_source,
        "allowed_roots": list(spec.allowed_roots),
        "downloads_root": spec.browser_downloads_root,
        "timeout_s": int(spec.timeout_s),
        "verification_summary": _clean_text(verification_summary, limit=220),
        "requires_manual_takeover": bool(target_row.get("sensitive", False)) and spec.operation == "fill",
    }
    if spec.operation == "fill":
        preview["input_payload_schema"] = "plain_text"
    elif spec.operation == "press_key":
        preview["input_payload_schema"] = "keyboard_key"
    elif spec.operation == "upload_file":
        preview["input_payload_schema"] = "workspace_file_path"
    if preview["requires_manual_takeover"] and not preview["verification_summary"]:
        preview["verification_summary"] = "sensitive credential entry requires manual browser takeover"
    return preview


def _read_bool_env(name: str, default: bool) -> bool:
    raw = str(os.getenv(name, "")).strip().lower()
    if not raw:
        return default
    return raw not in _FALSEY


class BrowserSessionManager:
    runner_kind = "playwright_persistent_context"
    isolation_level = "persistent_profile_runtime"

    def __init__(self, *, data_dir: Path) -> None:
        self.data_dir = Path(data_dir).resolve(strict=False)
        self.browser_root = self.data_dir / "browser"
        self.profiles_root = self.browser_root / "profiles"
        self.runs_root = self.browser_root / "runs"
        self.downloads_root = self.browser_root / "downloads"
        self.profiles_root.mkdir(parents=True, exist_ok=True)
        self.runs_root.mkdir(parents=True, exist_ok=True)
        self.downloads_root.mkdir(parents=True, exist_ok=True)
        self._playwright = None
        self._sessions: dict[str, _BrowserSession] = {}
        self._headless = _read_bool_env("AMADEUS_BROWSER_HEADLESS", default=False)

    def close_all(self) -> None:
        for session in self._sessions.values():
            try:
                session.context.close()
            except Exception:
                pass
        self._sessions.clear()
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

    def describe_target(self, *, profile_id: str, page_ref: str = "", target_ref: str = "") -> dict[str, Any]:
        if not target_ref:
            return {}
        session = self._session(profile_id)
        page, page_id, _ = self._resolve_page(session, page_ref=page_ref)
        if page_id not in session.target_maps or target_ref not in session.target_maps[page_id]:
            self._snapshot_page(session, page=page, page_id=page_id)
        return dict(session.target_maps.get(page_id, {}).get(target_ref) or {})

    def current_page_state(self, *, profile_id: str, page_ref: str = "") -> dict[str, Any]:
        session = self._session(profile_id)
        page, page_id, tab_id = self._resolve_page(session, page_ref=page_ref)
        self._sync_metadata(session, active_page=page)
        return {
            "profile_id": session.profile_id,
            "profile_root": str(session.profile_root),
            "downloads_dir": str(session.downloads_dir),
            "page_id": page_id,
            "tab_id": tab_id,
            "page_ref": _page_ref(self._page_index(session, page)),
            "url": _clean_text(page.url, limit=1200),
            "title": _clean_text(page.title(), limit=220) if page.url else "",
            "active_tab_count": len(session.context.pages),
            "manual_takeover_required": bool(session.manual_takeover_required),
            "context_status": "manual_takeover" if session.manual_takeover_required else "active",
        }

    def execute(self, *, proposal_id: str, spec: BrowserExecutionSpec, run_root: Path) -> BrowserExecutionResult:
        run_id = _clean_text(proposal_id, limit=128) or f"browser-run-{int(time.time())}"
        run_dir = Path(run_root).resolve(strict=False)
        run_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = run_dir / "run.json"
        if manifest_path.exists():
            cached = self._cached_result(manifest_path=manifest_path, spec=spec)
            if cached is not None:
                return cached

        session = self._session(spec.profile_id)
        start = time.time()
        error_summary = ""
        status = "completed"
        download_path = ""
        upload_source = spec.upload_source
        manual_takeover_required = False
        snapshot_targets: list[dict[str, Any]] = []
        text_preview = ""

        try:
            page, page_id, _ = self._resolve_page(session, page_ref=spec.page_ref)
            if spec.operation == "open_url":
                session.manual_takeover_required = False
                page.goto(spec.navigation_url, wait_until=spec.wait_until, timeout=spec.timeout_s * 1000)
            elif spec.operation == "follow_link":
                session.manual_takeover_required = False
                target = self.describe_target(profile_id=spec.profile_id, page_ref=spec.page_ref, target_ref=spec.target_ref)
                href = _clean_text(target.get("href"), limit=1200)
                if not href:
                    raise BrowserValidationError("TARGET_NOT_LINK", "follow_link requires a link-like target with href")
                self._locator(session, page=page, page_id=page_id, target_ref=spec.target_ref).click(timeout=spec.timeout_s * 1000)
            elif spec.operation == "list_tabs":
                pass
            elif spec.operation == "select_tab":
                session.manual_takeover_required = False
                page = self._select_page(session, spec.page_ref)
                page_id = _page_id(self._page_index(session, page))
            elif spec.operation == "go_back":
                session.manual_takeover_required = False
                page.go_back(timeout=spec.timeout_s * 1000, wait_until=spec.wait_until)
            elif spec.operation == "go_forward":
                session.manual_takeover_required = False
                page.go_forward(timeout=spec.timeout_s * 1000, wait_until=spec.wait_until)
            elif spec.operation == "reload":
                session.manual_takeover_required = False
                page.reload(wait_until=spec.wait_until, timeout=spec.timeout_s * 1000)
            elif spec.operation == "snapshot":
                session.manual_takeover_required = False
                snapshot_targets, text_preview = self._snapshot_page(session, page=page, page_id=page_id)
            elif spec.operation == "capture_page":
                session.manual_takeover_required = False
                snapshot_targets, text_preview = self._snapshot_page(session, page=page, page_id=page_id)
            elif spec.operation == "click":
                session.manual_takeover_required = False
                self._locator(session, page=page, page_id=page_id, target_ref=spec.target_ref).click(timeout=spec.timeout_s * 1000)
            elif spec.operation == "fill":
                target = self.describe_target(profile_id=spec.profile_id, page_ref=spec.page_ref, target_ref=spec.target_ref)
                if _looks_sensitive_target(target):
                    status = "blocked"
                    error_summary = "sensitive credential entry requires manual browser takeover"
                    manual_takeover_required = True
                    session.manual_takeover_required = True
                else:
                    session.manual_takeover_required = False
                    self._locator(session, page=page, page_id=page_id, target_ref=spec.target_ref).fill(spec.input_text, timeout=spec.timeout_s * 1000)
            elif spec.operation == "press_key":
                session.manual_takeover_required = False
                page.keyboard.press(spec.key)
            elif spec.operation == "download_click":
                session.manual_takeover_required = False
                target = self._locator(session, page=page, page_id=page_id, target_ref=spec.target_ref)
                with page.expect_download(timeout=spec.timeout_s * 1000) as pending_download:
                    target.click(timeout=spec.timeout_s * 1000)
                download = pending_download.value
                target_path = Path(spec.download_target) if spec.download_target else session.downloads_dir / (download.suggested_filename or f"{run_id}.bin")
                target_path.parent.mkdir(parents=True, exist_ok=True)
                download.save_as(str(target_path))
                download_path = str(target_path.resolve(strict=False))
            elif spec.operation == "upload_file":
                session.manual_takeover_required = False
                self._locator(session, page=page, page_id=page_id, target_ref=spec.target_ref).set_input_files(spec.upload_source)
            elif spec.operation == "begin_manual_takeover":
                session.manual_takeover_required = True
                manual_takeover_required = True
                try:
                    page.bring_to_front()
                except Exception:
                    pass
            else:  # pragma: no cover
                raise BrowserValidationError("INVALID_OPERATION", f"unsupported browser operation: {spec.operation}")

            page, page_id, tab_id = self._resolve_page(session, page_ref=spec.page_ref)
            if spec.operation != "snapshot":
                snapshot_targets, text_preview = self._snapshot_page(session, page=page, page_id=page_id)
            self._sync_metadata(session, active_page=page)
        except BrowserValidationError as exc:
            status = "blocked"
            error_summary = str(exc)
            tab_id = ""
        except PlaywrightTimeoutError:
            status = "blocked"
            error_summary = f"browser action timed out after {int(spec.timeout_s)}s"
            tab_id = ""
        except Exception as exc:
            status = "blocked"
            error_summary = _clean_text(exc, limit=220)
            tab_id = ""

        page_state = self.current_page_state(profile_id=spec.profile_id, page_ref=spec.page_ref)
        result = BrowserExecutionResult(
            run_id=run_id,
            status=status,
            profile_id=spec.profile_id,
            page_id=str(page_state.get("page_id") or ""),
            tab_id=str(page_state.get("tab_id") or tab_id),
            url=str(page_state.get("url") or ""),
            title=str(page_state.get("title") or ""),
            action_kind=spec.operation,
            target_ref=spec.target_ref,
            duration_ms=max(0, int((time.time() - start) * 1000)),
            active_tab_count=max(1, int(page_state.get("active_tab_count") or 1)),
            last_action_status="manual_takeover_required" if manual_takeover_required else ("completed" if status == "completed" else "blocked"),
            download_path=download_path,
            upload_source=upload_source,
            error_summary=error_summary,
            manual_takeover_required=manual_takeover_required or bool(page_state.get("manual_takeover_required")),
            snapshot_targets=snapshot_targets[:64],
            text_preview=text_preview[:2400],
        )
        manifest = {
            "run_id": run_id,
            "runner_kind": self.runner_kind,
            "isolation_level": self.isolation_level,
            "spec": asdict(spec),
            "result": asdict(result),
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    def _cached_result(self, *, manifest_path: Path, spec: BrowserExecutionSpec) -> BrowserExecutionResult | None:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        saved_spec = manifest.get("spec") if isinstance(manifest.get("spec"), dict) else {}
        if saved_spec and saved_spec != asdict(spec):
            raise BrowserValidationError("REPLAY_SPEC_MISMATCH", "proposal_id is already bound to a different browser execution spec")
        result = manifest.get("result") if isinstance(manifest.get("result"), dict) else {}
        if not result:
            return None
        return BrowserExecutionResult(
            run_id=_clean_text(result.get("run_id"), limit=128),
            status=_clean_text(result.get("status"), limit=64).lower() or "blocked",
            profile_id=_clean_text(result.get("profile_id"), limit=120),
            page_id=_clean_text(result.get("page_id"), limit=64),
            tab_id=_clean_text(result.get("tab_id"), limit=64),
            url=_clean_text(result.get("url"), limit=1200),
            title=_clean_text(result.get("title"), limit=220),
            action_kind=_clean_text(result.get("action_kind"), limit=64).lower(),
            target_ref=_clean_text(result.get("target_ref"), limit=64),
            duration_ms=max(0, _clean_int(result.get("duration_ms"), 0)),
            active_tab_count=max(1, _clean_int(result.get("active_tab_count"), 1)),
            last_action_status=_clean_text(result.get("last_action_status"), limit=64).lower(),
            download_path=_clean_text(result.get("download_path"), limit=520),
            upload_source=_clean_text(result.get("upload_source"), limit=520),
            error_summary=_clean_text(result.get("error_summary"), limit=220),
            manual_takeover_required=bool(result.get("manual_takeover_required", False)),
            snapshot_targets=list(result.get("snapshot_targets") or [])[:64] if isinstance(result.get("snapshot_targets"), list) else [],
            text_preview=_clean_text(result.get("text_preview"), limit=2400),
        )

    def _session(self, profile_id: str) -> _BrowserSession:
        profile = _clean_profile_id(profile_id)
        existing = self._sessions.get(profile)
        if existing is not None:
            return existing
        if sync_playwright is None:
            raise BrowserValidationError("MISSING_DEP", "playwright is not installed")
        if self._playwright is None:
            self._playwright = sync_playwright().start()
        profile_root = self.profiles_root / profile
        profile_root.mkdir(parents=True, exist_ok=True)
        downloads_dir = self.downloads_root / profile
        downloads_dir.mkdir(parents=True, exist_ok=True)
        context = self._playwright.chromium.launch_persistent_context(user_data_dir=str(profile_root), headless=self._headless, accept_downloads=True, downloads_path=str(downloads_dir))
        session = _BrowserSession(profile_id=profile, profile_root=profile_root, downloads_dir=downloads_dir, context=context)
        if not context.pages:
            page = context.new_page()
            last_url = self._load_metadata(profile_root).get("active_url")
            if last_url:
                try:
                    page.goto(str(last_url), wait_until="load", timeout=15000)
                except Exception:
                    pass
        self._sync_metadata(session, active_page=context.pages[0] if context.pages else None)
        self._sessions[profile] = session
        return session

    def _page_index(self, session: _BrowserSession, page: Any) -> int:
        for idx, candidate in enumerate(session.context.pages):
            if candidate == page:
                return idx
        return 0

    def _resolve_page(self, session: _BrowserSession, *, page_ref: str = "") -> tuple[Any, str, str]:
        pages = list(session.context.pages)
        if not pages:
            pages = [session.context.new_page()]
        index = _parse_page_index(page_ref)
        if index is None:
            index = _parse_page_index(session.active_page_ref)
        if index is None or index >= len(pages):
            index = 0
        page = pages[index]
        return page, _page_id(index), _tab_id(index)

    def _select_page(self, session: _BrowserSession, page_ref: str) -> Any:
        page, _, _ = self._resolve_page(session, page_ref=page_ref)
        self._sync_metadata(session, active_page=page)
        return page

    def _load_metadata(self, profile_root: Path) -> dict[str, Any]:
        path = profile_root / "session.json"
        try:
            return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except Exception:
            return {}

    def _sync_metadata(self, session: _BrowserSession, *, active_page: Any | None) -> None:
        pages = list(session.context.pages)
        active_idx = self._page_index(session, active_page) if active_page is not None else 0
        if pages:
            session.active_page_ref = _page_ref(active_idx)
        metadata = {
            "profile_id": session.profile_id,
            "active_page_ref": session.active_page_ref,
            "active_url": _clean_text(pages[active_idx].url, limit=1200) if pages else "",
            "active_title": _clean_text(pages[active_idx].title(), limit=220) if pages else "",
            "tab_count": len(pages),
            "manual_takeover_required": bool(session.manual_takeover_required),
            "tabs": [
                {
                    "page_id": _page_id(idx),
                    "tab_id": _tab_id(idx),
                    "url": _clean_text(page.url, limit=1200),
                    "title": _clean_text(page.title(), limit=220),
                }
                for idx, page in enumerate(pages)
            ],
        }
        (session.profile_root / "session.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    def _snapshot_page(self, session: _BrowserSession, *, page: Any, page_id: str) -> tuple[list[dict[str, Any]], str]:
        try:
            page.wait_for_load_state("domcontentloaded", timeout=10000)
        except Exception:
            pass
        payload = page.evaluate("""
() => {
  const clean = (value, limit = 220) => String(value ?? "").replace(/\\s+/g, " ").trim().slice(0, limit);
  const nodes = Array.from(document.querySelectorAll("a,button,input,textarea,select,[role='button'],[onclick]")).slice(0, 64);
  return {
    textPreview: clean(document.body ? document.body.innerText : "", 2400),
    targets: nodes.map((el, idx) => {
      const ref = `e${idx + 1}`;
      el.setAttribute("data-amadeus-target", ref);
      const tag = (el.tagName || "").toLowerCase();
      const inputType = clean(el.getAttribute("type"), 64).toLowerCase();
      const autocomplete = clean(el.getAttribute("autocomplete"), 64).toLowerCase();
      const role = clean(el.getAttribute("role"), 64).toLowerCase();
      const text = clean(el.innerText || el.textContent || el.value || "", 160);
      const label = clean(el.getAttribute("aria-label") || el.getAttribute("placeholder") || el.getAttribute("name") || text, 220);
      return {
        target_ref: ref,
        tag,
        role,
        label,
        text,
        href: clean(el.getAttribute("href"), 520),
        input_type: inputType,
        autocomplete,
        sensitive: ["password", "otp", "one-time-code", "passkey"].includes(inputType)
          || ["one-time-code", "current-password", "new-password"].includes(autocomplete)
          || /otp|passkey|password|密码|验证码/i.test(label),
      };
    }),
  };
}
""")
        targets = payload.get("targets") if isinstance(payload, dict) else []
        normalized_targets: list[dict[str, Any]] = []
        target_map: dict[str, dict[str, Any]] = {}
        if isinstance(targets, list):
            for item in targets[:64]:
                if not isinstance(item, dict):
                    continue
                target = {
                    "target_ref": _clean_text(item.get("target_ref"), limit=64),
                    "tag": _clean_text(item.get("tag"), limit=32).lower(),
                    "role": _clean_text(item.get("role"), limit=64).lower(),
                    "label": _clean_text(item.get("label"), limit=220),
                    "text": _clean_text(item.get("text"), limit=160),
                    "href": _clean_text(item.get("href"), limit=520),
                    "input_type": _clean_text(item.get("input_type"), limit=64).lower(),
                    "autocomplete": _clean_text(item.get("autocomplete"), limit=64).lower(),
                    "sensitive": bool(item.get("sensitive", False)),
                }
                if not target["target_ref"]:
                    continue
                normalized_targets.append(target)
                target_map[target["target_ref"]] = target
        session.target_maps[page_id] = target_map
        text_preview = _clean_text((payload or {}).get("textPreview"), limit=2400)
        return normalized_targets, text_preview

    def _locator(self, session: _BrowserSession, *, page: Any, page_id: str, target_ref: str) -> Any:
        if page_id not in session.target_maps or target_ref not in session.target_maps[page_id]:
            self._snapshot_page(session, page=page, page_id=page_id)
        locator = page.locator(f'[data-amadeus-target="{target_ref}"]').first
        try:
            count = locator.count()
        except Exception:
            count = 0
        if count <= 0:
            raise BrowserValidationError("TARGET_NOT_FOUND", "snapshot target is missing or stale; refresh the page snapshot first")
        return locator


_BROWSER_SESSION_MANAGERS: set[BrowserSessionManager] = set()


@lru_cache(maxsize=8)
def get_browser_session_manager(data_dir: str) -> BrowserSessionManager:
    manager = BrowserSessionManager(data_dir=Path(data_dir))
    _BROWSER_SESSION_MANAGERS.add(manager)
    return manager


def reset_browser_session_manager_cache() -> None:
    for manager in list(_BROWSER_SESSION_MANAGERS):
        try:
            manager.close_all()
        finally:
            _BROWSER_SESSION_MANAGERS.discard(manager)
    get_browser_session_manager.cache_clear()


__all__ = [
    "BrowserExecutionResult",
    "BrowserExecutionSpec",
    "BrowserSessionManager",
    "BrowserValidationError",
    "build_browser_execution_preview",
    "build_browser_execution_spec",
    "get_browser_session_manager",
    "reset_browser_session_manager_cache",
]
