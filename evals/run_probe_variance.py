from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

PYTHON = sys.executable or "python"
EVAL_SCRIPT = PROJECT_ROOT / "evals" / "run_langsmith_evals.py"
DEFAULT_SUITE = "thesis_probe"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repeat a probe suite and summarize variance across ablation settings.")
    parser.add_argument("--suite", default=DEFAULT_SUITE, help="Probe suite to repeat. Default: thesis_probe")
    parser.add_argument("--repeats", type=int, default=3, help="Number of repeated runs per variant.")
    parser.add_argument(
        "--checkpoint",
        default="",
        help="Checkpoint json path for incremental probe runs. Default: evals/reports/probe-variance-<suite>-latest.partial.json",
    )
    parser.add_argument("--fresh", action="store_true", help="Ignore any existing checkpoint and start from scratch.")
    parser.add_argument("--timeout-s", type=int, default=900, help="Per-run timeout for each suite invocation.")
    parser.add_argument(
        "--variants",
        nargs="+",
        default=["baseline", "persona_off", "worldline_off"],
        help="Variant set to run. Choices: baseline persona_off worldline_off",
    )
    return parser.parse_args()


def _variant_env(name: str) -> dict[str, str]:
    if name == "baseline":
        return {}
    if name == "persona_off":
        return {"AMADEUS_ABLATE_PERSONA_ALIGNMENT": "1"}
    if name == "worldline_off":
        return {"AMADEUS_ABLATE_WORLDLINE_MEMORY": "1"}
    raise ValueError(f"unknown variant: {name}")


def _extract_report_path(stdout: str) -> Path:
    for line in stdout.splitlines():
        if "local_report_json=" in line:
            return Path(line.split("local_report_json=", 1)[1].strip())
    raise RuntimeError("failed to locate local_report_json in eval output")


def _latest_report_json(created_after: float) -> Path:
    candidates = [
        p
        for p in REPORT_DIR.glob("eval-report-*.json")
        if p.stat().st_mtime >= created_after - 1.0
    ]
    if not candidates:
        raise RuntimeError("failed to locate generated eval report json by timestamp")
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _default_checkpoint_path(suite: str) -> Path:
    return REPORT_DIR / f"probe-variance-{suite}-latest.partial.json"


def _load_checkpoint(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_checkpoint(*, path: Path, suite: str, repeats: int, variants: list[str], runs: list[dict[str, Any]]) -> None:
    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "suite": suite,
        "repeats": repeats,
        "variants": variants,
        "runs": runs,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _trim_runs(*, runs: list[dict[str, Any]], repeats: int, variants: list[str]) -> list[dict[str, Any]]:
    by_variant: dict[str, list[dict[str, Any]]] = {}
    for row in runs:
        variant = str(row.get("variant") or "").strip()
        if variant not in variants:
            continue
        by_variant.setdefault(variant, []).append(row)

    selected: list[dict[str, Any]] = []
    for variant in variants:
        selected.extend(by_variant.get(variant, [])[:repeats])
    return selected


def _completed_counts(*, runs: list[dict[str, Any]], variants: list[str]) -> dict[str, int]:
    counts = {variant: 0 for variant in variants}
    for row in runs:
        variant = str(row.get("variant") or "").strip()
        if variant in counts:
            counts[variant] += 1
    return counts


def _run_once(*, suite: str, variant: str, timeout_s: int) -> dict[str, Any]:
    env = os.environ.copy()
    env.update(
        {
            "LANGSMITH_TRACING": "false",
            "LANGCHAIN_TRACING_V2": "false",
            "AMADEUS_TTS_ENABLED": "0",
        }
    )
    for key in [
        "AMADEUS_ABLATE_PERSONA_ALIGNMENT",
        "AMADEUS_ABLATE_WORLDLINE_MEMORY",
        "AMADEUS_ABLATE_CLAIM_ATTRIBUTION",
        "AMADEUS_MEMORY_GUARD_ENABLED",
    ]:
        env.pop(key, None)
    env.update(_variant_env(variant))

    started = time.time()
    proc = subprocess.run(
        [PYTHON, str(EVAL_SCRIPT), "--local-only", "--suite", suite],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout_s,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"probe run failed for variant={variant}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    try:
        report_path = _extract_report_path(proc.stdout)
    except Exception:
        report_path = _latest_report_json(started)
    if not report_path.exists():
        report_path = _latest_report_json(started)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    suite_report = (report.get("suites") or [None])[0] or {}
    return {
        "variant": variant,
        "suite": suite,
        "elapsed_s": round(time.time() - started, 2),
        "report_json": str(report_path),
        "report_md": str(report_path.with_suffix(".md")),
        "aggregated_metrics": dict(suite_report.get("aggregated_metrics") or {}),
        "evaluator_summary": dict(suite_report.get("evaluator_summary") or {}),
        "failing_cases": list(suite_report.get("failing_cases") or []),
    }


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(float(statistics.mean(values)), 4)


def _std(values: list[float]) -> float | None:
    if len(values) < 2:
        return 0.0 if values else None
    return round(float(statistics.stdev(values)), 4)


def _display_path(value: str) -> str:
    try:
        return Path(value).resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except Exception:
        return str(value)


def _aggregate_runs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metric_keys = [
        "ooc_rate",
        "canon_violation_rate",
        "worldline_recall_at_k",
        "commitment_fulfillment",
        "relationship_continuity",
        "citation_coverage",
        "persona_probe_voice",
        "worldline_answer_grounding",
        "relationship_repair_grounding",
    ]
    by_variant: dict[str, list[dict[str, Any]]] = {}
    for row in runs:
        by_variant.setdefault(str(row["variant"]), []).append(row)

    out: list[dict[str, Any]] = []
    for variant, items in by_variant.items():
        summary: dict[str, Any] = {
            "variant": variant,
            "runs": len(items),
            "report_jsons": [item["report_json"] for item in items],
            "report_mds": [item["report_md"] for item in items],
            "fail_run_count": sum(1 for item in items if item.get("failing_cases")),
        }
        for key in metric_keys:
            values: list[float] = []
            for item in items:
                metric_val = item.get("aggregated_metrics", {}).get(key)
                if metric_val is None:
                    metric_val = item.get("evaluator_summary", {}).get(key)
                if metric_val is None:
                    continue
                values.append(float(metric_val))
            summary[f"{key}_mean"] = _mean(values)
            summary[f"{key}_std"] = _std(values)
        out.append(summary)
    return out


def _write_reports(*, suite: str, repeats: int, runs: list[dict[str, Any]], summary_rows: list[dict[str, Any]]) -> tuple[Path, Path]:
    ts = time.strftime("%Y%m%d-%H%M%S")
    run_id = uuid.uuid4().hex[:8]
    json_path = REPORT_DIR / f"probe-variance-{suite}-{ts}-{run_id}.json"
    md_path = REPORT_DIR / f"probe-variance-{suite}-{ts}-{run_id}.md"
    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "suite": suite,
        "repeats": repeats,
        "runs": runs,
        "summary": summary_rows,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    metric_groups = [
        "ooc_rate",
        "canon_violation_rate",
        "worldline_recall_at_k",
        "commitment_fulfillment",
        "relationship_continuity",
        "citation_coverage",
        "persona_probe_voice",
        "worldline_answer_grounding",
        "relationship_repair_grounding",
    ]

    lines = [
        "# Probe Variance Report",
        "",
        f"Generated at: {payload['generated_at']}",
        f"Suite: `{suite}`",
        f"Repeats per variant: `{repeats}`",
        "",
        "| Variant | Runs | Fail Runs | " + " | ".join(metric_groups) + " |",
        "| --- | ---: | ---: | " + " | ".join(["---"] * len(metric_groups)) + " |",
    ]
    for row in summary_rows:
        cols: list[str] = []
        for key in metric_groups:
            mean = row.get(f"{key}_mean")
            std = row.get(f"{key}_std")
            if mean is None:
                cols.append("`-`")
            else:
                cols.append(f"`{mean:.4f} +/- {std:.4f}`")
        lines.append(f"| `{row['variant']}` | `{row['runs']}` | `{row['fail_run_count']}` | " + " | ".join(cols) + " |")

    lines.extend(["", "## Run Reports", ""])
    for item in runs:
        lines.append(
            f"- `{item['variant']}`: json=`{_display_path(str(item['report_json']))}` md=`{_display_path(str(item['report_md']))}` elapsed_s=`{item['elapsed_s']}`"
        )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    args = _parse_args()
    variants = [str(item).strip() for item in args.variants if str(item).strip()]
    suite = str(args.suite)
    repeats = int(args.repeats)
    checkpoint_path = Path(str(args.checkpoint).strip()) if str(args.checkpoint).strip() else _default_checkpoint_path(suite)

    existing: dict[str, Any] = {}
    if not args.fresh and checkpoint_path.exists():
        existing = _load_checkpoint(checkpoint_path)

    runs = _trim_runs(
        runs=list(existing.get("runs") or []),
        repeats=repeats,
        variants=variants,
    )
    counts = _completed_counts(runs=runs, variants=variants)
    if runs:
        print(f"[probe-variance] resuming from checkpoint={checkpoint_path}")
        print(f"[probe-variance] completed_counts={counts}")

    for variant in variants:
        start_idx = counts.get(variant, 0)
        for idx in range(start_idx, repeats):
            print(f"[probe-variance] running {variant} repeat={idx + 1}/{repeats}")
            try:
                row = _run_once(suite=suite, variant=variant, timeout_s=int(args.timeout_s))
            except subprocess.TimeoutExpired as exc:
                _write_checkpoint(
                    path=checkpoint_path,
                    suite=suite,
                    repeats=repeats,
                    variants=variants,
                    runs=runs,
                )
                raise RuntimeError(
                    f"probe run timed out for variant={variant} after {int(args.timeout_s)}s; "
                    f"resume with the same command to continue from {checkpoint_path}"
                ) from exc
            runs.append(row)
            _write_checkpoint(
                path=checkpoint_path,
                suite=suite,
                repeats=repeats,
                variants=variants,
                runs=runs,
            )

    summary_rows = _aggregate_runs(runs)
    json_path, md_path = _write_reports(
        suite=suite,
        repeats=repeats,
        runs=runs,
        summary_rows=summary_rows,
    )
    _write_checkpoint(
        path=checkpoint_path,
        suite=suite,
        repeats=repeats,
        variants=variants,
        runs=runs,
    )
    print(f"[probe-variance] report_json={json_path}")
    print(f"[probe-variance] report_md={md_path}")
    print(f"[probe-variance] checkpoint={checkpoint_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
