from __future__ import annotations

import argparse
import datetime as dt
import sqlite3
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from repair_codex_sidebar import (  # noqa: E402
    _backup_file,
    _find_running_codex_processes,
    _format_updated_at,
    _load_global_state,
    _load_threads,
    _normalized_key,
    _repair_global_state,
    _write_json,
    _write_session_index,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Repair Codex desktop sidebar state for setups that must keep "
            "model_provider=mycodex. This migrates matching workspace threads "
            "from openai -> mycodex without touching config.toml."
        )
    )
    parser.add_argument(
        "--codex-home",
        default=str(Path.home() / ".codex"),
        help="Codex home directory. Default: %(default)s",
    )
    parser.add_argument(
        "--workspace-root",
        default=r"E:\桌面\amadeus-thread0",
        help="Workspace whose legacy threads should be remapped.",
    )
    parser.add_argument(
        "--from-provider",
        default="openai",
        help="Existing provider namespace to migrate from.",
    )
    parser.add_argument(
        "--to-provider",
        default="mycodex",
        help="Provider namespace to migrate into.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run even if Codex processes are still detected.",
    )
    return parser


def _normalize_workspace_root(path: str) -> str:
    return path.replace("/", "\\").rstrip("\\")


def _thread_belongs_to_workspace(cwd: str, workspace_root: str) -> bool:
    cwd_key = _normalized_key(cwd)
    root_key = _normalized_key(workspace_root)
    return cwd_key == root_key or cwd_key.startswith(root_key + "\\")


def _migrate_thread_providers(
    db_path: Path,
    workspace_root: str,
    from_provider: str,
    to_provider: str,
) -> tuple[int, list[str]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            select id, cwd, model_provider
            from threads
            where archived = 0
            """
        ).fetchall()

        target_ids = [
            str(row["id"])
            for row in rows
            if row["model_provider"] == from_provider
            and _thread_belongs_to_workspace(str(row["cwd"]), workspace_root)
        ]
        if not target_ids:
            return 0, []

        conn.executemany(
            "update threads set model_provider = ? where id = ?",
            [(to_provider, thread_id) for thread_id in target_ids],
        )
        conn.commit()
        return len(target_ids), target_ids


def _rebuild_session_index_rows(threads: list[dict[str, object]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for row in threads:
        thread_id = str(row["id"])
        if thread_id in seen_ids:
            continue
        seen_ids.add(thread_id)
        rows.append(
            {
                "id": thread_id,
                "thread_name": str(row["title"]),
                "updated_at": _format_updated_at(row.get("updated_at")),
            }
        )
    return rows


def main() -> int:
    args = _build_parser().parse_args()
    codex_home = Path(args.codex_home).expanduser().resolve()
    workspace_root = _normalize_workspace_root(args.workspace_root)
    from_provider = args.from_provider
    to_provider = args.to_provider

    running = _find_running_codex_processes()
    if running and not args.force:
        print("Close Codex completely before running this mycodex sidebar repair.")
        print(f"Detected processes: {', '.join(sorted(set(running)))}")
        return 2

    db_path = codex_home / "state_5.sqlite"
    global_state_path = codex_home / ".codex-global-state.json"
    session_index_path = codex_home / "session_index.jsonl"

    if not codex_home.exists():
        print(f"Codex home does not exist: {codex_home}")
        return 1
    if not db_path.exists():
        print(f"Missing thread database: {db_path}")
        return 1

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = codex_home / "repair_backups" / f"mycodex_sidebar_repair_{timestamp}"
    _backup_file(db_path, backup_dir)
    _backup_file(global_state_path, backup_dir)
    _backup_file(session_index_path, backup_dir)

    migrated_count, migrated_ids = _migrate_thread_providers(
        db_path=db_path,
        workspace_root=workspace_root,
        from_provider=from_provider,
        to_provider=to_provider,
    )

    global_state = _load_global_state(global_state_path)
    threads = _load_threads(db_path)
    rebuilt_index = _rebuild_session_index_rows(threads)
    repaired_state = _repair_global_state(global_state, threads, rebuilt_index)

    _write_session_index(session_index_path, rebuilt_index)
    _write_json(global_state_path, repaired_state)

    print(f"[mycodex-repair] codex_home={codex_home}")
    print(f"[mycodex-repair] backup_dir={backup_dir}")
    print(f"[mycodex-repair] workspace_root={workspace_root}")
    print(f"[mycodex-repair] provider={from_provider}->{to_provider}")
    print(f"[mycodex-repair] migrated_threads={migrated_count}")
    if migrated_ids:
        print(f"[mycodex-repair] migrated_ids={','.join(migrated_ids)}")
    print(f"[mycodex-repair] session_index_rows={len(rebuilt_index)}")
    print("[mycodex-repair] completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
