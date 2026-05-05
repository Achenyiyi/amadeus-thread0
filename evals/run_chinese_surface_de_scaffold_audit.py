from __future__ import annotations

import argparse
import json
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
RESIDUE_BANK_PATH = PROJECT_ROOT / "evals" / "chinese_surface_residue_bank.json"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

REQUIRED_CATEGORIES = (
    "teacherly_scold",
    "meta_persona_proof",
    "generic_assistant_tone",
    "hardline_autonomy_overreach",
    "scene_script residue",
    "taskization_of_daily_chat",
    "repair_scorekeeping",
    "boundary_threat_excess",
)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object at {path}")
    return payload


def load_residue_bank(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path)
    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("Residue bank must contain an items list")
    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"Residue item #{idx} is not an object")
        normalized.append(
            {
                "id": str(item.get("id") or f"item_{idx}"),
                "category": str(item.get("category") or "").strip(),
                "input_context": str(item.get("input_context") or "").strip(),
                "bad_surface": str(item.get("bad_surface") or "").strip(),
                "reason": str(item.get("reason") or "").strip(),
                "target_semantic": str(item.get("target_semantic") or "").strip(),
            }
        )
    return normalized


def _call_live_model_forbidden(_: str) -> None:
    raise RuntimeError("Chinese surface de-scaffolding audit must remain offline")


def detect_legacy_surface_families(text: str) -> list[str]:
    from amadeus_thread0.graph_parts.postprocess import (
        _has_autonomy_hardline_surface,
        _has_boundary_abstraction_surface,
        _has_repair_punitive_tail,
        _has_repair_scorekeeping_tail,
        _has_repair_underresolved_brief,
        _has_wording_meta_detour,
        _has_idle_task_reframe_surface,
        _semantic_chinese_surface_residue_families,
    )

    content = str(text or "").strip()
    if not content:
        return []

    families = list(_semantic_chinese_surface_residue_families(content))
    legacy_checks = {
        "generic_scold_template": bool(re.search(r"(?:这点还算(?:像样|值得肯定)|这点还算不错|你能意识到并特意回来说明)", content)),
        "wording_meta_detour": _has_wording_meta_detour(content),
        "boundary_abstraction_surface": _has_boundary_abstraction_surface(content),
        "repair_scorekeeping_tail": _has_repair_scorekeeping_tail(content),
        "repair_punitive_tail": _has_repair_punitive_tail(content),
        "repair_underresolved_brief": _has_repair_underresolved_brief(content),
        "autonomy_hardline_surface": _has_autonomy_hardline_surface(content),
        "idle_task_reframe_surface": _has_idle_task_reframe_surface(content),
    }
    for legacy_family, matched in legacy_checks.items():
        if matched and legacy_family not in families:
            families.append(legacy_family)
    return families


def evaluate_residue_bank(items: list[dict[str, Any]], *, run_id: str) -> dict[str, Any]:
    category_counts: dict[str, int] = {category: 0 for category in REQUIRED_CATEGORIES}
    evaluated: list[dict[str, Any]] = []
    detected_total = 0

    for item in items:
        category = str(item.get("category") or "").strip()
        detected_families = detect_legacy_surface_families(str(item.get("bad_surface") or ""))
        detected = bool(detected_families)
        if category in category_counts:
            category_counts[category] += 1
        if detected:
            detected_total += 1
        evaluated.append(
            {
                **item,
                "detected_families": detected_families,
                "status": "passed" if detected else "failed",
            }
        )

    missing_required_categories = [category for category, count in category_counts.items() if count <= 0]
    category_mismatches = [
        item["id"]
        for item in evaluated
        if str(item.get("category") or "").strip() not in item.get("detected_families", [])
    ]
    overall_status = "passed" if not missing_required_categories and not category_mismatches else "failed"
    return {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": overall_status,
        "readiness_status": "chinese_surface_de_scaffold_ready" if overall_status == "passed" else "chinese_surface_de_scaffold_in_progress",
        "summary": {
            "total_items": len(evaluated),
            "detected_items": detected_total,
            "undetected_items": len(evaluated) - detected_total,
        },
        "category_counts": category_counts,
        "missing_required_categories": missing_required_categories,
        "category_mismatches": category_mismatches,
        "items": evaluated,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Chinese Surface De-Scaffolding Audit",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
        "",
        "## Summary",
        "",
        f"- Total items: `{report.get('summary', {}).get('total_items', 0)}`",
        f"- Detected items: `{report.get('summary', {}).get('detected_items', 0)}`",
        f"- Undetected items: `{report.get('summary', {}).get('undetected_items', 0)}`",
        "",
        "## Category Counts",
        "",
        "| Category | Count |",
        "| --- | ---: |",
    ]
    for category, count in (report.get("category_counts") or {}).items():
        lines.append(f"| `{category}` | {int(count) if str(count).isdigit() else count} |")
    missing = list(report.get("missing_required_categories") or [])
    if missing:
        lines.extend(["", f"Missing Required Categories: `{', '.join(missing)}`"])
    mismatches = list(report.get("category_mismatches") or [])
    if mismatches:
        lines.extend(["", "## Category Mismatches", ""])
        for item_id in mismatches:
            lines.append(f"- `{item_id}`")
    lines.extend(["", "## Items", "", "| Id | Category | Status | Families |", "| --- | --- | --- | --- |"])
    for item in report.get("items") or []:
        families = ", ".join(item.get("detected_families") or [])
        lines.append(
            f"| `{item.get('id', '')}` | `{item.get('category', '')}` | `{item.get('status', '')}` | `{families}` |"
        )
    return "\n".join(lines) + "\n"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Chinese surface de-scaffolding audit.")
    parser.add_argument("--residue-bank", default=str(RESIDUE_BANK_PATH))
    parser.add_argument("--run-tag", default="")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    bank_path = Path(args.residue_bank)
    items = load_residue_bank(bank_path)
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    report = evaluate_residue_bank(items, run_id=run_id)
    json_path = REPORT_DIR / f"chinese-surface-de-scaffold-audit-{run_id}.json"
    md_path = REPORT_DIR / f"chinese-surface-de-scaffold-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[chinese-surface-de-scaffold] json={json_path}")
    print(f"[chinese-surface-de-scaffold] md={md_path}")
    print(f"[chinese-surface-de-scaffold] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[chinese-surface-de-scaffold] readiness={report.get('readiness_status', 'unknown')}")
    return 0 if str(report.get("overall_status") or "") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
