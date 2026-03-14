from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
SEED_PATH = PROJECT_ROOT / "evals" / "daily_surface_preference_seed.jsonl"
REVIEW_QUEUE_PATH = PROJECT_ROOT / "evals" / "daily_surface_preference_review_queue.json"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_report_path() -> Path:
    candidates = sorted(
        [
            path
            for path in REPORT_DIR.glob("daily-surface-pairwise-*.json")
            if path.name != "daily-surface-pairwise-latest.partial.json"
        ],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("No daily surface pairwise report found.")
    return candidates[0]


def _normalize_text(text: str) -> str:
    return " ".join(str(text or "").split())


def _pairwise_reasons(case: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for item in case.get("details") or []:
        if not isinstance(item, dict):
            continue
        reason = str(item.get("reason") or "").strip()
        if reason:
            out.append(reason)
    return out


def _build_seed_row(case: dict[str, Any], *, source_report: Path) -> dict[str, Any] | None:
    status = str(case.get("status") or "").strip().lower()
    if status not in {"passed", "failed"}:
        return None

    baseline = str(case.get("baseline_output") or "").strip()
    degraded = str(case.get("degraded_output") or "").strip()
    if not baseline or not degraded or _normalize_text(baseline) == _normalize_text(degraded):
        return None

    if status == "passed":
        chosen = baseline
        rejected = degraded
        chosen_variant = "baseline"
        rejected_variant = "degraded"
    else:
        chosen = degraded
        rejected = baseline
        chosen_variant = "degraded"
        rejected_variant = "baseline"

    turns = [str(item or "").strip() for item in (case.get("turns") or []) if str(item or "").strip()]
    return {
        "id": f"daily_surface::{str(case.get('name') or '').strip()}::{chosen_variant}",
        "task": "daily_surface_preference",
        "case_name": str(case.get("name") or "").strip(),
        "focus": str(case.get("focus") or "").strip(),
        "turns": turns,
        "prompt_text": "\n".join(turns),
        "chosen": chosen,
        "rejected": rejected,
        "chosen_variant": chosen_variant,
        "rejected_variant": rejected_variant,
        "pairwise_status": status,
        "preference_strength": "clear_2_of_2",
        "judge_reasons": _pairwise_reasons(case),
        "source_report": str(source_report),
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _build_review_row(case: dict[str, Any], *, source_report: Path) -> dict[str, Any]:
    turns = [str(item or "").strip() for item in (case.get("turns") or []) if str(item or "").strip()]
    return {
        "case_name": str(case.get("name") or "").strip(),
        "focus": str(case.get("focus") or "").strip(),
        "turns": turns,
        "prompt_text": "\n".join(turns),
        "status": str(case.get("status") or "").strip(),
        "baseline_output": str(case.get("baseline_output") or "").strip(),
        "degraded_output": str(case.get("degraded_output") or "").strip(),
        "judge_reasons": _pairwise_reasons(case),
        "details": case.get("details") or [],
        "source_report": str(source_report),
    }


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    text = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows).strip()
    path.write_text(text + ("\n" if text else ""), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export daily-surface preference seeds from the latest pairwise report.")
    parser.add_argument("--report", default="", help="Explicit daily-surface pairwise report path.")
    args = parser.parse_args()

    report_path = Path(str(args.report).strip()) if str(args.report or "").strip() else _latest_report_path()
    report = _load_json(report_path)
    checks = report.get("checks") if isinstance(report, dict) else None
    if not isinstance(checks, list):
        raise SystemExit(f"Invalid report: {report_path}")

    seeds: list[dict[str, Any]] = []
    review_queue: list[dict[str, Any]] = []
    for case in checks:
        if not isinstance(case, dict):
            continue
        seed = _build_seed_row(case, source_report=report_path)
        if seed is not None:
            seeds.append(seed)
        else:
            review_queue.append(_build_review_row(case, source_report=report_path))

    _write_jsonl(SEED_PATH, seeds)
    REVIEW_QUEUE_PATH.write_text(
        json.dumps(
            {
                "source_report": str(report_path),
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "seed_count": len(seeds),
                "review_count": len(review_queue),
                "items": review_queue,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"[export] source_report={report_path}")
    print(f"[export] preference_seed={SEED_PATH}")
    print(f"[export] review_queue={REVIEW_QUEUE_PATH}")
    print(f"[export] seed_count={len(seeds)}")
    print(f"[export] review_count={len(review_queue)}")


if __name__ == "__main__":
    main()
