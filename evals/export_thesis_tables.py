from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = REPO_ROOT / "evals" / "reports"
DEFAULT_OUT_DIR = REPO_ROOT / "docs" / "thesis_assets"


CANONICAL_REPORTS = {
    "regression_isolated": REPORTS_DIR / "eval-report-20260306-204132-c57f83bc.json",
    "long_thread": REPORTS_DIR / "eval-report-20260307-005508-c126b941.json",
    "experience_probe": REPORTS_DIR / "eval-report-20260306-215635-57bb39c4.json",
    "thesis_probe": REPORTS_DIR / "eval-report-20260307-022239-17048ce9.json",
    "long_thread_worldline_off": REPORTS_DIR / "eval-report-20260307-010246-e2288121.json",
    "probe_variance": REPORTS_DIR / "probe-variance-thesis_probe-20260307-024213-ee70482d.json",
    "ablation_matrix": REPORTS_DIR / "ablation-matrix-20260306-224514-5c1a1c70.json",
}


BASELINE_METRICS = [
    "ooc_rate",
    "canon_violation_rate",
    "worldline_recall_at_k",
    "commitment_fulfillment",
    "relationship_continuity",
    "citation_coverage",
    "memory_guard_block_rate",
    "bargein_recovery_rate",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fmt(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def to_markdown(headers: list[str], rows: Iterable[list[object]]) -> str:
    materialized = [[fmt(cell) for cell in row] for row in rows]
    header_line = "| " + " | ".join(headers) + " |"
    sep_line = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(row) + " |" for row in materialized]
    return "\n".join([header_line, sep_line, *body])


def write_csv(path: Path, headers: list[str], rows: Iterable[list[object]]) -> None:
    materialized = [[fmt(cell) for cell in row] for row in rows]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(materialized)


def write_md(path: Path, title: str, intro: str, headers: list[str], rows: Iterable[list[object]]) -> None:
    table = to_markdown(headers, rows)
    path.write_text(
        f"# {title}\n\n{intro}\n\n{table}\n",
        encoding="utf-8",
    )


def build_official_baseline_rows() -> list[list[object]]:
    rows: list[list[object]] = []
    for suite in ["regression_isolated", "long_thread", "experience_probe", "thesis_probe"]:
        report = load_json(CANONICAL_REPORTS[suite])
        summary = report["summary"][suite]
        row = [suite]
        row.extend(summary.get(metric) for metric in BASELINE_METRICS)
        rows.append(row)
    return rows


def build_probe_variance_rows() -> list[list[object]]:
    data = load_json(CANONICAL_REPORTS["probe_variance"])
    rows: list[list[object]] = []
    for item in data["summary"]:
        rows.append(
            [
                item["variant"],
                item["runs"],
                item["persona_probe_voice_mean"],
                item["persona_probe_voice_std"],
                item["worldline_recall_at_k_mean"],
                item["worldline_recall_at_k_std"],
                item["commitment_fulfillment_mean"],
                item["commitment_fulfillment_std"],
                item["relationship_continuity_mean"],
                item["relationship_continuity_std"],
                item["worldline_answer_grounding_mean"],
                item["worldline_answer_grounding_std"],
            ]
        )
    return rows


def build_long_thread_comparison_rows() -> list[list[object]]:
    baseline = load_json(CANONICAL_REPORTS["long_thread"])["summary"]["long_thread"]
    worldline_off = load_json(CANONICAL_REPORTS["long_thread_worldline_off"])["summary"]["long_thread"]
    rows: list[list[object]] = []
    for name, summary in [("baseline", baseline), ("worldline_off", worldline_off)]:
        rows.append(
            [
                name,
                summary.get("ooc_rate"),
                summary.get("worldline_recall_at_k"),
                summary.get("commitment_fulfillment"),
                summary.get("relationship_continuity"),
                summary.get("memory_guard_block_rate"),
            ]
        )
    return rows


def build_support_ablation_rows() -> list[list[object]]:
    data = load_json(CANONICAL_REPORTS["ablation_matrix"])
    wanted = {
        "baseline_regression": "baseline",
        "claim_attribution_off_regression": "claim_attribution_off",
        "memory_guard_off_regression": "memory_guard_off",
    }
    rows: list[list[object]] = []
    for item in data["results"]:
        if item["name"] not in wanted:
            continue
        metrics = item["aggregated_metrics"]
        rows.append(
            [
                wanted[item["name"]],
                metrics.get("ooc_rate"),
                metrics.get("citation_coverage"),
                metrics.get("memory_guard_block_rate"),
                metrics.get("bargein_recovery_rate"),
            ]
        )
    rows.sort(key=lambda row: ["baseline", "claim_attribution_off", "memory_guard_off"].index(row[0]))
    return rows


def write_readme(out_dir: Path, files: list[Path]) -> None:
    rel_files = "\n".join(f"- `{path.name}`" for path in files)
    text = (
        "# Thesis Assets\n\n"
        "Updated: 2026-03-07\n\n"
        "This directory contains export-ready tables for the thesis experiment chapter and defense slides.\n\n"
        "Generated files:\n\n"
        f"{rel_files}\n"
    )
    (out_dir / "README.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export thesis-ready tables from canonical evaluation reports.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="Output directory for markdown/csv tables.")
    args = parser.parse_args()

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []

    baseline_headers = ["suite", *BASELINE_METRICS]
    baseline_rows = build_official_baseline_rows()
    baseline_csv = out_dir / "official_baseline_summary.csv"
    baseline_md = out_dir / "official_baseline_summary.md"
    write_csv(baseline_csv, baseline_headers, baseline_rows)
    write_md(
        baseline_md,
        "Official Baseline Summary",
        "Canonical dedicated reruns for the four official suites. These values should be used in the main thesis baseline table.",
        baseline_headers,
        baseline_rows,
    )
    written.extend([baseline_csv, baseline_md])

    variance_headers = [
        "variant",
        "runs",
        "persona_probe_voice_mean",
        "persona_probe_voice_std",
        "worldline_recall_at_k_mean",
        "worldline_recall_at_k_std",
        "commitment_fulfillment_mean",
        "commitment_fulfillment_std",
        "relationship_continuity_mean",
        "relationship_continuity_std",
        "worldline_answer_grounding_mean",
        "worldline_answer_grounding_std",
    ]
    variance_rows = build_probe_variance_rows()
    variance_csv = out_dir / "thesis_probe_variance.csv"
    variance_md = out_dir / "thesis_probe_variance.md"
    write_csv(variance_csv, variance_headers, variance_rows)
    write_md(
        variance_md,
        "Thesis Probe Variance",
        "Repeated thesis_probe results. Use this table for error-bar figures and for reporting mean/std instead of one-off samples.",
        variance_headers,
        variance_rows,
    )
    written.extend([variance_csv, variance_md])

    long_headers = [
        "variant",
        "ooc_rate",
        "worldline_recall_at_k",
        "commitment_fulfillment",
        "relationship_continuity",
        "memory_guard_block_rate",
    ]
    long_rows = build_long_thread_comparison_rows()
    long_csv = out_dir / "long_thread_worldline_comparison.csv"
    long_md = out_dir / "long_thread_worldline_comparison.md"
    write_csv(long_csv, long_headers, long_rows)
    write_md(
        long_md,
        "Long Thread Worldline Comparison",
        "Dedicated long_thread reruns comparing the current baseline against worldline_off. Use this table when arguing that worldline memory affects long-horizon continuity.",
        long_headers,
        long_rows,
    )
    written.extend([long_csv, long_md])

    support_headers = [
        "variant",
        "ooc_rate",
        "citation_coverage",
        "memory_guard_block_rate",
        "bargein_recovery_rate",
    ]
    support_rows = build_support_ablation_rows()
    support_csv = out_dir / "support_ablation_summary.csv"
    support_md = out_dir / "support_ablation_summary.md"
    write_csv(support_csv, support_headers, support_rows)
    write_md(
        support_md,
        "Support Ablation Summary",
        "Regression-side ablations for the two supporting subsystems: claim attribution and memory guard.",
        support_headers,
        support_rows,
    )
    written.extend([support_csv, support_md])

    manifest = {
        "generated_from": {key: str(path) for key, path in CANONICAL_REPORTS.items()},
        "generated_files": [str(path) for path in written],
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    written.append(manifest_path)

    write_readme(out_dir, written)


if __name__ == "__main__":
    main()
