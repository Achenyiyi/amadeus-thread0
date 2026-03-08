from __future__ import annotations

import json
import os
import re
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


def _variants() -> list[dict[str, Any]]:
    return [
        {"name": "baseline_regression", "suite": "regression_isolated", "env": {}},
        {"name": "baseline_long_thread", "suite": "long_thread", "env": {}},
        {"name": "baseline_experience", "suite": "experience_probe", "env": {}},
        {"name": "baseline_thesis_probe", "suite": "thesis_probe", "env": {}},
        {
            "name": "persona_off_regression",
            "suite": "regression_isolated",
            "env": {"AMADEUS_ABLATE_PERSONA_ALIGNMENT": "1"},
        },
        {
            "name": "persona_off_experience",
            "suite": "experience_probe",
            "env": {"AMADEUS_ABLATE_PERSONA_ALIGNMENT": "1"},
        },
        {
            "name": "persona_off_thesis_probe",
            "suite": "thesis_probe",
            "env": {"AMADEUS_ABLATE_PERSONA_ALIGNMENT": "1"},
        },
        {
            "name": "worldline_off_long_thread",
            "suite": "long_thread",
            "env": {"AMADEUS_ABLATE_WORLDLINE_MEMORY": "1"},
        },
        {
            "name": "worldline_off_thesis_probe",
            "suite": "thesis_probe",
            "env": {"AMADEUS_ABLATE_WORLDLINE_MEMORY": "1"},
        },
        {
            "name": "claim_attribution_off_regression",
            "suite": "regression_isolated",
            "env": {"AMADEUS_ABLATE_CLAIM_ATTRIBUTION": "1"},
        },
        {
            "name": "memory_guard_off_regression",
            "suite": "regression_isolated",
            "env": {"AMADEUS_MEMORY_GUARD_ENABLED": "0"},
        },
    ]


def _extract_report_path(stdout: str) -> Path:
    match = re.search(r"local_report_json=(.+)", stdout)
    if not match:
        raise RuntimeError("failed to locate local_report_json in eval output")
    return Path(match.group(1).strip())


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


def _run_variant(spec: dict[str, Any]) -> dict[str, Any]:
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
    for key, value in (spec.get("env") or {}).items():
        env[str(key)] = str(value)

    cmd = [PYTHON, str(EVAL_SCRIPT), "--local-only", "--suite", str(spec["suite"])]
    started = time.time()
    proc = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    elapsed = round(time.time() - started, 2)
    if proc.returncode != 0:
        raise RuntimeError(
            f"variant {spec['name']} failed with code {proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )

    try:
        report_json = _extract_report_path(proc.stdout)
    except Exception:
        report_json = _latest_report_json(started)
    if not report_json.exists():
        report_json = _latest_report_json(started)
    report = json.loads(report_json.read_text(encoding="utf-8"))
    suite_report = (report.get("suites") or [None])[0] or {}
    return {
        "name": spec["name"],
        "suite": spec["suite"],
        "env": dict(spec.get("env") or {}),
        "elapsed_s": elapsed,
        "report_json": str(report_json),
        "report_md": str(report_json.with_suffix(".md")),
        "aggregated_metrics": dict(suite_report.get("aggregated_metrics") or {}),
        "metric_coverage": dict(suite_report.get("metric_coverage") or {}),
        "evaluator_summary": dict(suite_report.get("evaluator_summary") or {}),
        "failing_cases": list(suite_report.get("failing_cases") or []),
    }


def _baseline_map(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in results:
        if str(row.get("name") or "").startswith("baseline_"):
            out[str(row.get("suite") or "")] = row
    return out


def _metric_delta(cur: Any, base: Any) -> str:
    if cur is None or base is None:
        return "-"
    try:
        delta = float(cur) - float(base)
    except Exception:
        return "-"
    return f"{delta:+.4f}"


def _write_reports(results: list[dict[str, Any]]) -> tuple[Path, Path]:
    ts = time.strftime("%Y%m%d-%H%M%S")
    run_id = uuid.uuid4().hex[:8]
    json_path = REPORT_DIR / f"ablation-matrix-{ts}-{run_id}.json"
    md_path = REPORT_DIR / f"ablation-matrix-{ts}-{run_id}.md"
    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "results": results,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    baselines = _baseline_map(results)
    metric_keys = [
        "ooc_rate",
        "canon_violation_rate",
        "worldline_recall_at_k",
        "commitment_fulfillment",
        "relationship_continuity",
        "citation_coverage",
        "memory_guard_block_rate",
        "bargein_recovery_rate",
    ]

    lines = [
        "# Ablation Matrix Report",
        "",
        f"Generated at: {payload['generated_at']}",
        "",
        "| Variant | Suite | Failures | Runtime(s) |",
        "| --- | --- | ---: | ---: |",
    ]
    for row in results:
        lines.append(
            f"| `{row['name']}` | `{row['suite']}` | `{len(row.get('failing_cases') or [])}` | `{row.get('elapsed_s')}` |"
        )

    lines.extend(["", "## Metrics", ""])
    header = "| Variant | Suite | " + " | ".join(metric_keys) + " |"
    sep = "| --- | --- | " + " | ".join(["---:"] * len(metric_keys)) + " |"
    lines.extend([header, sep])
    for row in results:
        metrics = row.get("aggregated_metrics") or {}
        cols = []
        for key in metric_keys:
            val = metrics.get(key)
            if val is None:
                cols.append("`-`")
            else:
                cols.append(f"`{float(val):.4f}`")
        lines.append(f"| `{row['name']}` | `{row['suite']}` | " + " | ".join(cols) + " |")

    lines.extend(["", "## Delta Vs Baseline", ""])
    lines.extend([header, sep])
    for row in results:
        base = baselines.get(str(row.get("suite") or ""))
        metrics = row.get("aggregated_metrics") or {}
        base_metrics = (base or {}).get("aggregated_metrics") or {}
        cols = [_metric_delta(metrics.get(key), base_metrics.get(key)) for key in metric_keys]
        lines.append(f"| `{row['name']}` | `{row['suite']}` | " + " | ".join(f"`{c}`" for c in cols) + " |")

    lines.extend(["", "## Report Paths", ""])
    for row in results:
        lines.append(
            f"- `{row['name']}`: json=`{row.get('report_json', '-')}` md=`{row.get('report_md', '-')}`"
        )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def _write_partial(results: list[dict[str, Any]]) -> Path:
    path = REPORT_DIR / "ablation-matrix-latest.partial.json"
    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "results": results,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> int:
    results: list[dict[str, Any]] = []
    for spec in _variants():
        print(f"[ablation] running {spec['name']} ({spec['suite']})")
        try:
            results.append(_run_variant(spec))
        except Exception as e:
            results.append(
                {
                    "name": spec["name"],
                    "suite": spec["suite"],
                    "env": dict(spec.get("env") or {}),
                    "error": str(e),
                    "failing_cases": ["RUN_FAILED"],
                }
            )
        partial_path = _write_partial(results)
        print(f"[ablation] partial={partial_path}")

    json_path, md_path = _write_reports(results)
    print(f"[ablation] report_json={json_path}")
    print(f"[ablation] report_md={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
