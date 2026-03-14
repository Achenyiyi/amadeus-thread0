from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = PROJECT_ROOT / "evals" / "daily_surface_preference_seed.jsonl"
MANUAL_PATH = PROJECT_ROOT / "evals" / "daily_surface_preference_manual.jsonl"
REVIEW_QUEUE_PATH = PROJECT_ROOT / "evals" / "daily_surface_preference_review_queue.json"
OUTPUT_PATH = PROJECT_ROOT / "evals" / "daily_surface_preference_corpus.jsonl"
MANIFEST_PATH = PROJECT_ROOT / "evals" / "daily_surface_preference_corpus_manifest.json"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        data = json.loads(text)
        if isinstance(data, dict):
            rows.append(data)
    return rows


def _load_review_queue_cases(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []
    out: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("case_name") or "").strip()
        if name:
            out.append(name)
    return out


def _normalize_text(text: Any) -> str:
    return " ".join(str(text or "").split())


def _safe_case_name(value: str) -> str:
    text = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in str(value or "").strip())
    return text.strip("_") or "unknown_case"


def _normalize_turns(raw: Any, prompt_text: str) -> list[str]:
    out: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            text = str(item or "").strip()
            if text:
                out.append(text)
    elif prompt_text:
        out.append(prompt_text)
    return out


def _row_fingerprint(row: dict[str, Any]) -> str:
    return "||".join(
        [
            _safe_case_name(str(row.get("case_name") or "")),
            _normalize_text(row.get("prompt_text") or ""),
            _normalize_text(row.get("chosen") or ""),
            _normalize_text(row.get("rejected") or ""),
        ]
    )


def _normalize_row(
    row: dict[str, Any],
    *,
    source_label: str,
    source_path: Path,
    row_index: int,
) -> dict[str, Any] | None:
    chosen = str(row.get("chosen") or "").strip()
    rejected = str(row.get("rejected") or "").strip()
    if not chosen or not rejected:
        return None
    if _normalize_text(chosen) == _normalize_text(rejected):
        return None

    prompt_text = str(row.get("prompt_text") or "").strip()
    turns = _normalize_turns(row.get("turns"), prompt_text)
    if not prompt_text and turns:
        prompt_text = "\n".join(turns)
    if not turns and prompt_text:
        turns = [prompt_text]

    case_name = _safe_case_name(str(row.get("case_name") or ""))
    row_id = str(row.get("id") or "").strip()
    if not row_id:
        row_id = f"daily_surface::{source_label}::{case_name}::{row_index:04d}"

    normalized = dict(row)
    normalized["id"] = row_id
    normalized["task"] = str(row.get("task") or "daily_surface_preference").strip() or "daily_surface_preference"
    normalized["case_name"] = case_name
    normalized["focus"] = str(row.get("focus") or "").strip()
    normalized["turns"] = turns
    normalized["prompt_text"] = prompt_text
    normalized["chosen"] = chosen
    normalized["rejected"] = rejected
    normalized["source"] = str(row.get("source") or source_label).strip() or source_label
    normalized["source_file"] = str(source_path)
    normalized["corpus_built_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    return normalized


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    text = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows).strip()
    path.write_text(text + ("\n" if text else ""), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge automatic and manual daily-surface preference rows into one corpus.")
    parser.add_argument("--seed", default=str(SEED_PATH), help="Path to auto-exported seed JSONL.")
    parser.add_argument("--manual", default=str(MANUAL_PATH), help="Path to manually curated JSONL.")
    parser.add_argument("--review-queue", default=str(REVIEW_QUEUE_PATH), help="Path to unstable review queue JSON.")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Output merged corpus JSONL path.")
    parser.add_argument("--manifest", default=str(MANIFEST_PATH), help="Output manifest JSON path.")
    parser.add_argument("--seed-only", action="store_true", help="Build using only the auto-exported seed rows.")
    parser.add_argument("--manual-only", action="store_true", help="Build using only the manually curated rows.")
    args = parser.parse_args()

    if args.seed_only and args.manual_only:
        raise SystemExit("Choose either --seed-only or --manual-only, not both.")

    seed_path = Path(str(args.seed)).resolve()
    manual_path = Path(str(args.manual)).resolve()
    review_queue_path = Path(str(args.review_queue)).resolve()
    output_path = Path(str(args.output)).resolve()
    manifest_path = Path(str(args.manifest)).resolve()

    sources: list[tuple[str, Path]]
    if args.seed_only:
        sources = [("seed", seed_path)]
    elif args.manual_only:
        sources = [("manual", manual_path)]
    else:
        sources = [("manual", manual_path), ("seed", seed_path)]

    merged: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_fingerprints: set[str] = set()
    skipped = {"invalid": 0, "duplicate_id": 0, "duplicate_fingerprint": 0}
    counts_by_source = Counter()
    counts_by_case = Counter()

    for source_label, path in sources:
        for idx, raw_row in enumerate(_load_jsonl(path), start=1):
            row = _normalize_row(raw_row, source_label=source_label, source_path=path, row_index=idx)
            if row is None:
                skipped["invalid"] += 1
                continue
            row_id = str(row.get("id") or "").strip()
            fingerprint = _row_fingerprint(row)
            if row_id in seen_ids:
                skipped["duplicate_id"] += 1
                continue
            if fingerprint in seen_fingerprints:
                skipped["duplicate_fingerprint"] += 1
                continue
            seen_ids.add(row_id)
            seen_fingerprints.add(fingerprint)
            merged.append(row)
            counts_by_source[str(row.get("source") or source_label)] += 1
            counts_by_case[str(row.get("case_name") or "unknown_case")] += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output_path, merged)

    review_cases = _load_review_queue_cases(review_queue_path)
    covered_cases = sorted({name for name in review_cases if counts_by_case.get(name, 0) > 0})
    uncovered_cases = sorted({name for name in review_cases if counts_by_case.get(name, 0) == 0})
    manifest = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "output_path": str(output_path),
        "source_paths": {label: str(path) for label, path in sources},
        "total_rows": len(merged),
        "counts_by_source": dict(sorted(counts_by_source.items())),
        "counts_by_case": dict(sorted(counts_by_case.items())),
        "skipped": skipped,
        "review_queue_case_count": len(review_cases),
        "review_queue_covered_cases": covered_cases,
        "review_queue_uncovered_cases": uncovered_cases,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[daily-surface] corpus={output_path}")
    print(f"[daily-surface] manifest={manifest_path}")
    print(f"[daily-surface] total_rows={len(merged)}")
    print(f"[daily-surface] counts_by_source={dict(sorted(counts_by_source.items()))}")
    print(f"[daily-surface] review_queue_covered={covered_cases}")
    print(f"[daily-surface] review_queue_uncovered={uncovered_cases}")


if __name__ == "__main__":
    main()
