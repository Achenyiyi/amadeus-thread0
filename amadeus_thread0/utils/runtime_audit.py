from __future__ import annotations

import json
from pathlib import Path
from typing import Any


RUNTIME_ARTIFACT_NAMES = (
    "checkpoints.sqlite",
    "memories.sqlite",
    "decision_audit.jsonl",
    "mcp_audit.jsonl",
    "memory_store_audit.jsonl",
    "tool_audit.jsonl",
)

ASSET_DIR_NAMES = {
    "copy_wav",
    "tts_out",
    "__pycache__",
}

WORLDLINES_DIRNAME = "worldlines"


def _safe_stat(path: Path) -> tuple[int, int]:
    try:
        st = path.stat()
        return int(st.st_size), int(st.st_mtime)
    except Exception:
        return 0, 0


def _safe_total_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return _safe_stat(path)[0]
    total = 0
    try:
        for child in path.rglob("*"):
            if child.is_file():
                total += _safe_stat(child)[0]
    except Exception:
        return total
    return total


def _runtime_artifacts_in_dir(path: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for name in RUNTIME_ARTIFACT_NAMES:
        file_path = path / name
        if not file_path.exists() or not file_path.is_file():
            continue
        size, modified_at = _safe_stat(file_path)
        if size <= 0:
            continue
        artifacts.append(
            {
                "name": name,
                "path": str(file_path),
                "size_bytes": size,
                "modified_at": modified_at,
            }
        )
    return artifacts


def _entry_summary(path: Path, *, kind: str) -> dict[str, Any]:
    artifacts = _runtime_artifacts_in_dir(path)
    return {
        "name": path.name,
        "path": str(path),
        "kind": kind,
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "size_bytes": _safe_total_size(path),
        "modified_at": max((int(item.get("modified_at") or 0) for item in artifacts), default=0),
        "smoke_like": _is_smoke_like(path.name),
    }


def _is_smoke_like(name: str) -> bool:
    raw = str(name or "").strip().lower()
    if not raw:
        return False
    return raw.startswith("smoke") or "smoke" in raw or "debug" in raw


def audit_runtime_layout(data_dir: Path) -> dict[str, Any]:
    root = Path(data_dir)
    shared_runtime = _entry_summary(root, kind="shared_root_runtime")
    isolated_worldlines: list[dict[str, Any]] = []
    legacy_runtime_dirs: list[dict[str, Any]] = []
    asset_dirs: list[dict[str, Any]] = []
    other_dirs: list[dict[str, Any]] = []

    if root.exists():
        try:
            entries = sorted(root.iterdir(), key=lambda p: p.name.lower())
        except Exception:
            entries = []
        for entry in entries:
            if not entry.is_dir():
                continue
            if entry.name == WORLDLINES_DIRNAME:
                try:
                    worldline_entries = sorted(entry.iterdir(), key=lambda p: p.name.lower())
                except Exception:
                    worldline_entries = []
                for child in worldline_entries:
                    if not child.is_dir():
                        continue
                    summary = _entry_summary(child, kind="isolated_worldline")
                    if summary["artifact_count"] > 0:
                        isolated_worldlines.append(summary)
                    else:
                        other_dirs.append(summary)
                continue
            if entry.name in ASSET_DIR_NAMES:
                asset_dirs.append(
                    {
                        "name": entry.name,
                        "path": str(entry),
                        "kind": "asset_dir",
                        "size_bytes": _safe_total_size(entry),
                    }
                )
                continue
            summary = _entry_summary(entry, kind="legacy_runtime_dir")
            if summary["artifact_count"] > 0:
                legacy_runtime_dirs.append(summary)
            else:
                other_dirs.append(summary)

    isolated_worldlines.sort(key=lambda item: (int(item.get("modified_at") or 0), str(item.get("name") or "")), reverse=True)
    legacy_runtime_dirs.sort(key=lambda item: (int(item.get("modified_at") or 0), str(item.get("name") or "")), reverse=True)
    other_dirs.sort(key=lambda item: str(item.get("name") or ""))
    asset_dirs.sort(key=lambda item: str(item.get("name") or ""))

    recommendations: list[str] = []
    if shared_runtime["artifact_count"] > 0:
        recommendations.append(
            "默认 plain CLI 会继续使用 data/ 下的 shared thread0 运行数据；干净演示优先用 --fresh-thread。"
        )
    if legacy_runtime_dirs:
        smoke_dirs = [item for item in legacy_runtime_dirs if bool(item.get("smoke_like"))]
        if smoke_dirs:
            recommendations.append(
                f"发现 {len(smoke_dirs)} 个疑似 smoke/debug 运行目录；清理前先确认是否还需要保留回归证据。"
            )
        else:
            recommendations.append(
                f"发现 {len(legacy_runtime_dirs)} 个 data/ 根目录下的历史 runtime 目录；建议逐个审阅后迁移或删除。"
            )
    if isolated_worldlines:
        recommendations.append(
            f"发现 {len(isolated_worldlines)} 个隔离 worldline 目录；这类目录可安全作为独立演示/实验运行根。"
        )
    if not recommendations:
        recommendations.append("当前 data/ 目录结构干净，没有发现共享运行污染或历史 runtime 残留。")

    return {
        "data_dir": str(root),
        "exists": root.exists(),
        "shared_runtime": shared_runtime,
        "isolated_worldlines": isolated_worldlines,
        "legacy_runtime_dirs": legacy_runtime_dirs,
        "asset_dirs": asset_dirs,
        "other_dirs": other_dirs,
        "stats": {
            "shared_artifact_count": int(shared_runtime.get("artifact_count") or 0),
            "isolated_worldline_count": len(isolated_worldlines),
            "legacy_runtime_dir_count": len(legacy_runtime_dirs),
            "asset_dir_count": len(asset_dirs),
            "other_dir_count": len(other_dirs),
        },
        "recommendations": recommendations,
    }


def render_runtime_audit_report(audit: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("[runtime-audit]")
    lines.append("data_dir=" + str(audit.get("data_dir") or ""))
    lines.append("exists=" + ("yes" if bool(audit.get("exists")) else "no"))

    stats = audit.get("stats") if isinstance(audit.get("stats"), dict) else {}
    lines.append(
        "shared_artifacts={shared} | isolated_worldlines={isolated} | legacy_runtime_dirs={legacy}".format(
            shared=int(stats.get("shared_artifact_count") or 0),
            isolated=int(stats.get("isolated_worldline_count") or 0),
            legacy=int(stats.get("legacy_runtime_dir_count") or 0),
        )
    )

    shared = audit.get("shared_runtime") if isinstance(audit.get("shared_runtime"), dict) else {}
    shared_artifacts = shared.get("artifacts") if isinstance(shared.get("artifacts"), list) else []
    if shared_artifacts:
        lines.append("")
        lines.append("[shared-root]")
        lines.append("path=" + str(shared.get("path") or ""))
        lines.append(
            "artifacts=" + ", ".join(str(item.get("name") or "") for item in shared_artifacts if isinstance(item, dict))
        )

    isolated = audit.get("isolated_worldlines") if isinstance(audit.get("isolated_worldlines"), list) else []
    if isolated:
        lines.append("")
        lines.append("[isolated-worldlines]")
        for item in isolated:
            if not isinstance(item, dict):
                continue
            lines.append(
                "- {name} | size={size} | artifacts={artifacts}".format(
                    name=str(item.get("name") or ""),
                    size=int(item.get("size_bytes") or 0),
                    artifacts=int(item.get("artifact_count") or 0),
                )
            )

    legacy = audit.get("legacy_runtime_dirs") if isinstance(audit.get("legacy_runtime_dirs"), list) else []
    if legacy:
        lines.append("")
        lines.append("[legacy-runtime-dirs]")
        for item in legacy:
            if not isinstance(item, dict):
                continue
            lines.append(
                "- {name} | smoke_like={smoke_like} | size={size} | artifacts={artifacts}".format(
                    name=str(item.get("name") or ""),
                    smoke_like="yes" if bool(item.get("smoke_like")) else "no",
                    size=int(item.get("size_bytes") or 0),
                    artifacts=int(item.get("artifact_count") or 0),
                )
            )

    recs = audit.get("recommendations") if isinstance(audit.get("recommendations"), list) else []
    if recs:
        lines.append("")
        lines.append("[recommendations]")
        for item in recs:
            lines.append("- " + str(item))

    return "\n".join(lines)


def audit_runtime_layout_json(data_dir: Path) -> str:
    return json.dumps(audit_runtime_layout(data_dir), ensure_ascii=False, indent=2)
