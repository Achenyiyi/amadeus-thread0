from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import ntpath
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any


DEFAULT_GLOBAL_STATE = {
    "thread-titles": {"titles": {}, "order": []},
    "pinned-thread-ids": [],
    "thread-workspace-root-hints": {},
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Repair Codex desktop sidebar state by rebuilding session index and "
            "workspace-root hints from authoritative local state."
        )
    )
    parser.add_argument(
        "--codex-home",
        default=str(Path.home() / ".codex"),
        help="Codex home directory. Default: %(default)s",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run even if Codex processes are still detected.",
    )
    return parser


def _find_running_codex_processes() -> list[str]:
    try:
        completed = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=True,
        )
    except Exception:
        return []

    results: list[str] = []
    for row in csv.reader(completed.stdout.splitlines()):
        if not row:
            continue
        image_name = row[0].strip()
        if image_name.lower().startswith("codex"):
            results.append(image_name)
    return results


def _strip_win32_device_prefix(path: str) -> str:
    if path.startswith("\\\\?\\"):
        return path[4:]
    return path


def _normalize_windows_path(path: str) -> str:
    path = _strip_win32_device_prefix(path.strip())
    if not path:
        return ""
    return ntpath.normpath(path.replace("/", "\\"))


def _normalized_key(path: str) -> str:
    return _normalize_windows_path(path).casefold()


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    _ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _backup_file(source: Path, backup_dir: Path) -> None:
    if not source.exists():
        return
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, backup_dir / source.name)


def _load_global_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "thread-titles": {"titles": {}, "order": []},
            "pinned-thread-ids": [],
            "thread-workspace-root-hints": {},
        }
    state = _load_json(path)
    if not isinstance(state, dict):
        return {
            "thread-titles": {"titles": {}, "order": []},
            "pinned-thread-ids": [],
            "thread-workspace-root-hints": {},
        }

    normalized = dict(state)
    normalized["thread-titles"] = _normalize_thread_titles(state.get("thread-titles"))
    normalized["pinned-thread-ids"] = _normalize_str_list(state.get("pinned-thread-ids"))
    normalized["thread-workspace-root-hints"] = _normalize_str_dict(
        state.get("thread-workspace-root-hints")
    )
    for key in ("electron-saved-workspace-roots", "active-workspace-roots"):
        if key in state:
            normalized[key] = _normalize_str_list(state.get(key))
    return normalized


def _normalize_thread_titles(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"titles": {}, "order": []}

    raw_titles = value.get("titles")
    titles = {
        str(thread_id): title
        for thread_id, title in (raw_titles.items() if isinstance(raw_titles, dict) else [])
        if isinstance(title, str) and title.strip()
    }
    order = [
        str(thread_id)
        for thread_id in (value.get("order") if isinstance(value.get("order"), list) else [])
        if isinstance(thread_id, str) and thread_id.strip()
    ]
    return {"titles": titles, "order": order}


def _normalize_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str) and item.strip()]


def _normalize_str_dict(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): str(item)
        for key, item in value.items()
        if isinstance(key, str) and key.strip() and isinstance(item, str) and item.strip()
    }


def _load_existing_session_index(path: Path) -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    if not path.exists():
        return index
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            thread_id = payload.get("id")
            if not isinstance(thread_id, str) or not thread_id:
                continue
            index[thread_id] = payload
    return index


def _load_threads(db_path: Path) -> list[dict[str, Any]]:
    if not db_path.exists():
        raise FileNotFoundError(f"Missing thread database: {db_path}")
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        rows = cursor.execute(
            """
            select id, title, cwd, updated_at
            from threads
            where archived = 0
            order by updated_at asc
            """
        )
        return [dict(row) for row in rows]


def _best_matching_workspace_root(cwd: str, workspace_roots: list[str]) -> str | None:
    normalized_cwd = _normalize_windows_path(cwd)
    normalized_key = _normalized_key(normalized_cwd)
    best_root: str | None = None
    best_len = -1
    for root in workspace_roots:
        normalized_root = _normalize_windows_path(root)
        root_key = _normalized_key(normalized_root)
        if normalized_key == root_key or normalized_key.startswith(root_key + "\\"):
            if len(root_key) > best_len:
                best_root = normalized_root
                best_len = len(root_key)
    return best_root


def _format_updated_at(timestamp: Any) -> str:
    try:
        value = int(timestamp)
    except Exception:
        return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return dt.datetime.fromtimestamp(value, dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _rebuild_session_index(
    threads: list[dict[str, Any]],
    existing_index: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    rebuilt: list[dict[str, str]] = []
    for row in threads:
        thread_id = str(row["id"])
        existing = existing_index.get(thread_id, {})
        thread_name = existing.get("thread_name") or str(row["title"])
        rebuilt.append(
            {
                "id": thread_id,
                "thread_name": thread_name,
                "updated_at": existing.get("updated_at") or _format_updated_at(row.get("updated_at")),
            }
        )
    return rebuilt


def _write_session_index(path: Path, rows: list[dict[str, str]]) -> None:
    _ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def _repair_global_state(
    state: dict[str, Any],
    threads: list[dict[str, Any]],
    session_index_rows: list[dict[str, str]],
) -> dict[str, Any]:
    workspace_roots = []
    for key in ("electron-saved-workspace-roots", "active-workspace-roots"):
        for root in state.get(key, []) or []:
            normalized_root = _normalize_windows_path(str(root))
            if normalized_root and normalized_root not in workspace_roots:
                workspace_roots.append(normalized_root)

    valid_thread_ids = {str(row["id"]) for row in threads}

    hints = {
        thread_id: root
        for thread_id, root in (state.get("thread-workspace-root-hints") or {}).items()
        if thread_id in valid_thread_ids and root
    }
    for row in threads:
        thread_id = str(row["id"])
        matched_root = _best_matching_workspace_root(str(row["cwd"]), workspace_roots)
        if matched_root:
            hints[thread_id] = matched_root
    state["thread-workspace-root-hints"] = dict(sorted(hints.items()))

    title_rows = {row["id"]: row["thread_name"] for row in session_index_rows}
    title_state = state.get("thread-titles") or {"titles": {}, "order": []}
    titles = {
        thread_id: title
        for thread_id, title in (title_state.get("titles") or {}).items()
        if thread_id in valid_thread_ids and isinstance(title, str) and title.strip()
    }
    for thread_id, title in title_rows.items():
        if title.strip():
            titles[thread_id] = title
    state["thread-titles"] = {
        "titles": titles,
        "order": [row["id"] for row in session_index_rows if row["id"] in titles],
    }

    pinned = []
    for thread_id in state.get("pinned-thread-ids") or []:
        if thread_id in valid_thread_ids and thread_id not in pinned:
            pinned.append(thread_id)
    state["pinned-thread-ids"] = pinned
    return state


def main() -> int:
    args = _build_parser().parse_args()
    codex_home = Path(args.codex_home).expanduser().resolve()
    global_state_path = codex_home / ".codex-global-state.json"
    session_index_path = codex_home / "session_index.jsonl"
    thread_db_path = codex_home / "state_5.sqlite"

    running = _find_running_codex_processes()
    if running and not args.force:
        print("Close Codex completely before running this repair script.")
        print(f"Detected processes: {', '.join(sorted(set(running)))}")
        return 2

    if not codex_home.exists():
        print(f"Codex home does not exist: {codex_home}")
        return 1

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = codex_home / "repair_backups" / f"sidebar_repair_{timestamp}"
    _backup_file(global_state_path, backup_dir)
    _backup_file(session_index_path, backup_dir)

    global_state = _load_global_state(global_state_path)
    threads = _load_threads(thread_db_path)
    existing_index = _load_existing_session_index(session_index_path)
    rebuilt_index = _rebuild_session_index(threads, existing_index)
    repaired_state = _repair_global_state(global_state, threads, rebuilt_index)

    _write_session_index(session_index_path, rebuilt_index)
    _write_json(global_state_path, repaired_state)

    hinted = repaired_state.get("thread-workspace-root-hints") or {}
    print(f"[repair] codex_home={codex_home}")
    print(f"[repair] backup_dir={backup_dir}")
    print(f"[repair] threads_indexed={len(rebuilt_index)}")
    print(f"[repair] workspace_hints={len(hinted)}")
    for row in rebuilt_index:
        thread_id = row["id"]
        root = hinted.get(thread_id)
        if root:
            print(f"[repair] {thread_id} -> {root} :: {row['thread_name']}")
    print("[repair] completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
