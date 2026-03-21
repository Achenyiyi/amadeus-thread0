from __future__ import annotations

import argparse
import datetime as dt
import re
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
    _load_existing_session_index,
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
            "Unify Codex desktop thread provider namespace so workspace history stays "
            "visible when switching between equivalent OpenAI-compatible providers."
        )
    )
    parser.add_argument(
        "--codex-home",
        default=str(Path.home() / ".codex"),
        help="Codex home directory. Default: %(default)s",
    )
    parser.add_argument(
        "--workspace-root",
        default=None,
        help=(
            "Optional workspace root to restrict the migration scope. "
            "When omitted, all threads using --from-provider are migrated."
        ),
    )
    parser.add_argument(
        "--from-provider",
        default="mycodex",
        help="Current custom provider name to migrate from.",
    )
    parser.add_argument(
        "--to-provider",
        default="openai",
        help="Provider namespace to converge on.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run even if Codex processes are still detected.",
    )
    return parser


def _rewrite_config_namespace(
    config_text: str,
    from_provider: str,
    to_provider: str,
) -> str:
    rewritten = config_text
    rewritten = re.sub(
        rf'(?m)^(\s*model_provider\s*=\s*"){re.escape(from_provider)}("\s*)$',
        rf"\g<1>{to_provider}\2",
        rewritten,
    )
    rewritten = re.sub(
        rf"(?m)^\[model_providers\.{re.escape(from_provider)}\]\s*$",
        f"[model_providers.{to_provider}]",
        rewritten,
    )
    rewritten = re.sub(
        rf'(?m)^(\s*name\s*=\s*"){re.escape(from_provider)}("\s*)$',
        rf"\g<1>{to_provider}\2",
        rewritten,
    )

    block_pattern = re.compile(
        rf"(\[model_providers\.{re.escape(to_provider)}\]\s*(?:\r?\n(?:[^\[].*))*)",
        re.MULTILINE,
    )
    match = block_pattern.search(rewritten)
    if match:
        block = match.group(1)
        block = re.sub(
            rf'(?m)^(\s*name\s*=\s*"){re.escape(from_provider)}("\s*)$',
            rf'\g<1>{to_provider}\2',
            block,
        )
        rewritten = rewritten[: match.start(1)] + block + rewritten[match.end(1) :]

    return rewritten


def _normalize_workspace_root(path: str) -> str:
    return path.replace("/", "\\").rstrip("\\")


def _thread_belongs_to_workspace(cwd: str, workspace_root: str | None) -> bool:
    if not workspace_root:
        return True
    cwd_key = _normalized_key(cwd)
    root_key = _normalized_key(workspace_root)
    return cwd_key == root_key or cwd_key.startswith(root_key + "\\")


def _migrate_thread_providers(
    db_path: Path,
    workspace_root: str | None,
    from_provider: str,
    to_provider: str,
) -> int:
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
            row["id"]
            for row in rows
            if row["model_provider"] == from_provider
            and _thread_belongs_to_workspace(str(row["cwd"]), workspace_root)
        ]
        if not target_ids:
            return 0

        conn.executemany(
            "update threads set model_provider = ? where id = ?",
            [(to_provider, thread_id) for thread_id in target_ids],
        )
        conn.commit()
        return len(target_ids)


def _rebuild_session_index_rows(threads: list[dict[str, object]]) -> list[dict[str, str]]:
    return [
        {
            "id": str(row["id"]),
            "thread_name": str(row["title"]),
            "updated_at": _format_updated_at(row.get("updated_at")),
        }
        for row in threads
    ]


def main() -> int:
    args = _build_parser().parse_args()
    codex_home = Path(args.codex_home).expanduser().resolve()
    workspace_root = _normalize_workspace_root(args.workspace_root) if args.workspace_root else None
    from_provider = args.from_provider
    to_provider = args.to_provider

    running = _find_running_codex_processes()
    if running and not args.force:
        print("Close Codex completely before running this provider-unify script.")
        print(f"Detected processes: {', '.join(sorted(set(running)))}")
        return 2

    config_path = codex_home / "config.toml"
    db_path = codex_home / "state_5.sqlite"
    global_state_path = codex_home / ".codex-global-state.json"
    session_index_path = codex_home / "session_index.jsonl"

    if not codex_home.exists():
        print(f"Codex home does not exist: {codex_home}")
        return 1
    if not config_path.exists():
        print(f"Missing config: {config_path}")
        return 1
    if not db_path.exists():
        print(f"Missing thread database: {db_path}")
        return 1

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = codex_home / "repair_backups" / f"provider_unify_{timestamp}"
    _backup_file(config_path, backup_dir)
    _backup_file(db_path, backup_dir)
    _backup_file(global_state_path, backup_dir)
    _backup_file(session_index_path, backup_dir)

    original_config = config_path.read_text(encoding="utf-8")
    rewritten_config = _rewrite_config_namespace(original_config, from_provider, to_provider)
    if rewritten_config != original_config:
        config_path.write_text(rewritten_config, encoding="utf-8", newline="\n")

    migrated = _migrate_thread_providers(db_path, workspace_root, from_provider, to_provider)

    global_state = _load_global_state(global_state_path)
    threads = _load_threads(db_path)
    _ = _load_existing_session_index(session_index_path)
    rebuilt_index = _rebuild_session_index_rows(threads)
    repaired_state = _repair_global_state(global_state, threads, rebuilt_index)
    _write_session_index(session_index_path, rebuilt_index)
    _write_json(global_state_path, repaired_state)

    print(f"[provider-unify] codex_home={codex_home}")
    print(f"[provider-unify] backup_dir={backup_dir}")
    print(f"[provider-unify] workspace_root={workspace_root or '<all>'}")
    print(f"[provider-unify] config_provider={from_provider}->{to_provider}")
    print(f"[provider-unify] migrated_threads={migrated}")
    print(f"[provider-unify] session_index_rows={len(rebuilt_index)}")
    print("[provider-unify] completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
