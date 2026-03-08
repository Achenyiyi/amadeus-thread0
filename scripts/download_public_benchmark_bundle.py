from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from huggingface_hub import snapshot_download


@dataclass
class DatasetSpec:
    key: str
    source_type: str
    source: str
    purpose: str
    notes: str
    allow_patterns: list[str] | None = None


BUNDLE: list[DatasetSpec] = [
    DatasetSpec(
        key="CharacterEval",
        source_type="git",
        source="https://github.com/morecry/CharacterEval.git",
        purpose="Role-playing fidelity and in-character dialogue evaluation.",
        notes="Useful as the closest public role-play benchmark for persona consistency.",
    ),
    DatasetSpec(
        key="ESConv",
        source_type="git",
        source="https://github.com/thu-coai/Emotional-Support-Conversation.git",
        purpose="Emotional support dialogue and repair-style response analysis.",
        notes="Useful for companionship, apology, repair, and support strategy analysis.",
    ),
    DatasetSpec(
        key="RoleBench",
        source_type="hf_dataset",
        source="ZenMoore/RoleBench",
        purpose="Role-playing benchmark with stronger breadth than a single-character probe.",
        notes="Useful as a transfer and role-consistency benchmark bundle.",
        allow_patterns=["*.json", "*.jsonl", "*.csv", "*.parquet", "*.txt", "README.md", "dataset_infos.json"],
    ),
    DatasetSpec(
        key="EmpatheticDialogues",
        source_type="hf_dataset",
        source="facebook/empathetic_dialogues",
        purpose="Empathy and emotionally grounded conversation.",
        notes="Useful for everyday companion dialogue and emotion-grounded response analysis.",
        allow_patterns=["*.json", "*.jsonl", "*.csv", "*.parquet", "*.txt", "README.md", "dataset_infos.json"],
    ),
    DatasetSpec(
        key="GoEmotions",
        source_type="hf_dataset",
        source="google-research-datasets/go_emotions",
        purpose="Emotion-label corpus for appraisal-layer calibration.",
        notes="Useful for calibrating affect appraisal beyond keyword heuristics.",
        allow_patterns=["*.json", "*.jsonl", "*.csv", "*.parquet", "*.txt", "README.md", "dataset_infos.json"],
    ),
    DatasetSpec(
        key="MultiSessionChat",
        source_type="hf_dataset",
        source="nayohan/multi_session_chat",
        purpose="Multi-session dialogue continuity and long-horizon recall.",
        notes="Supplementary mirror used for long-session continuity experiments.",
        allow_patterns=["*.json", "*.jsonl", "*.csv", "*.parquet", "*.txt", "README.md", "dataset_infos.json"],
    ),
]


def _run_git_clone(repo_url: str, target_dir: Path, refresh: bool) -> dict[str, Any]:
    if target_dir.exists() and refresh:
        shutil.rmtree(target_dir)
    if not target_dir.exists():
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(target_dir)],
            check=True,
        )
    return {
        "path": str(target_dir.resolve()),
        "files": sum(1 for _ in target_dir.rglob("*") if _.is_file()),
    }


def _run_hf_snapshot(repo_id: str, target_dir: Path, allow_patterns: list[str] | None, refresh: bool) -> dict[str, Any]:
    if target_dir.exists() and refresh:
        shutil.rmtree(target_dir)
    last_exc: Exception | None = None
    for max_workers in (8, 2, 1):
        try:
            local_dir = snapshot_download(
                repo_id=repo_id,
                repo_type="dataset",
                local_dir=str(target_dir),
                allow_patterns=allow_patterns,
                force_download=refresh,
                resume_download=not refresh,
                local_dir_use_symlinks=False,
                max_workers=max_workers,
            )
            break
        except Exception as exc:  # pragma: no cover - network variability
            last_exc = exc
            print(f"[bundle] retry {repo_id} with max_workers={max_workers} failed: {type(exc).__name__}: {exc}")
            time.sleep(2.0)
    else:
        assert last_exc is not None
        raise last_exc
    base = Path(local_dir)
    return {
        "path": str(base.resolve()),
        "files": sum(1 for _ in base.rglob("*") if _.is_file()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Download a reusable public benchmark bundle for Amadeus-K.")
    parser.add_argument(
        "--out-dir",
        default="third_party/benchmarks",
        help="Destination directory for downloaded public benchmarks.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force redownload by deleting existing benchmark directories first.",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bundle_root": str(out_dir.resolve()),
        "datasets": [],
    }

    for spec in BUNDLE:
        target_dir = out_dir / spec.key
        if spec.source_type == "git":
            result = _run_git_clone(spec.source, target_dir, refresh=args.refresh)
        elif spec.source_type == "hf_dataset":
            result = _run_hf_snapshot(spec.source, target_dir, spec.allow_patterns, refresh=args.refresh)
        else:
            raise ValueError(f"Unsupported source_type: {spec.source_type}")
        manifest["datasets"].append(
            {
                **asdict(spec),
                **result,
            }
        )
        print(f"[bundle] {spec.key} -> {result['path']} ({result['files']} files)")

    manifest_path = out_dir / "bundle_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[bundle] manifest={manifest_path.resolve()}")


if __name__ == "__main__":
    main()
