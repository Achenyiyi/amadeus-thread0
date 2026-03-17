from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(PROJECT_ROOT / ".env", override=False)

os.environ.setdefault("AMADEUS_TTS_ENABLED", "0")
os.environ.setdefault("LANGSMITH_TRACING", "false")
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")

from amadeus_thread0.graph_parts import reset_runtime_caches  # noqa: E402
from amadeus_thread0.utils.tools import reset_tool_runtime_caches  # noqa: E402
from evals.asset_loader import daily_surface_marker_set, daily_surface_provider_cases  # noqa: E402
from evals.run_langsmith_evals import _run_graph  # noqa: E402

SURFACE_MARKERS = daily_surface_marker_set()


def _provider_env(provider: str) -> dict[str, str]:
    p = str(provider or "").strip().lower()
    if p == "deepseek":
        return {
            "AMADEUS_MODEL_PROVIDER": "deepseek",
            "AMADEUS_MODEL_NAME": os.getenv("AMADEUS_DEEPSEEK_MODEL", "deepseek-chat"),
            "AMADEUS_MODEL_BASE_URL": "",
            # Allow provider-native key fallback instead of reusing the compatible key.
            "AMADEUS_MODEL_API_KEY": "",
        }
    if p == "qwen":
        return {
            "AMADEUS_MODEL_PROVIDER": "qwen_native",
            "AMADEUS_MODEL_NAME": os.getenv("AMADEUS_QWEN_MODEL", os.getenv("AMADEUS_MODEL_NAME", "qwen3.5-plus")),
            "AMADEUS_MODEL_BASE_URL": os.getenv("AMADEUS_QWEN_BASE_URL", os.getenv("AMADEUS_MODEL_BASE_URL", "")),
        }
    raise ValueError(f"Unsupported provider: {provider}")


def _apply_provider_env(provider: str) -> dict[str, str]:
    prev: dict[str, str] = {}
    for key, value in _provider_env(provider).items():
        prev[key] = os.getenv(key, "")
        os.environ[key] = value
    reset_runtime_caches()
    reset_tool_runtime_caches()
    return prev


def _restore_env(prev: dict[str, str]) -> None:
    for key, value in prev.items():
        os.environ[key] = value
    reset_runtime_caches()
    reset_tool_runtime_caches()


def _run_provider(provider: str, repeats: int, case_names: list[str] | None = None) -> list[dict[str, Any]]:
    prev = _apply_provider_env(provider)
    try:
        rows: list[dict[str, Any]] = []
        cases = daily_surface_provider_cases(names=case_names)
        for case_idx, case in enumerate(cases, start=1):
            text = str(case.get("input") or "").strip()
            markers = list(case.get("surface_markers_avoid") or SURFACE_MARKERS)
            for rep in range(1, max(1, int(repeats)) + 1):
                case_key = f"provider-{provider}-{case_idx}-r{rep}-{uuid.uuid4().hex[:6]}"
                answer, tools, out = _run_graph([text], thread_id=case_key, case_key=case_key, reset_case_runtime=True)
                detector = out.get("ooc_detector") if isinstance(out, dict) else {}
                generation_profile = detector.get("generation_profile") if isinstance(detector, dict) else {}
                rows.append(
                    {
                        "case_name": str(case.get("name") or ""),
                        "provider": provider,
                        "input": text,
                        "judge_focus": str(case.get("judge_focus") or ""),
                        "repeat": rep,
                        "output": str(answer),
                        "surface_markers": [marker for marker in markers if marker in str(answer)],
                        "surface_markers_avoid": markers,
                        "temperature": generation_profile.get("temperature"),
                        "max_tokens": generation_profile.get("max_tokens"),
                    }
                )
        return rows
    finally:
        _restore_env(prev)


def _to_markdown(rows: list[dict[str, Any]]) -> str:
    by_provider: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_provider.setdefault(str(row.get("provider") or "unknown"), []).append(row)

    cases = daily_surface_provider_cases(
        names=[
            str(row.get("case_name") or "").strip()
            for row in rows
            if str(row.get("case_name") or "").strip()
        ]
    )
    case_inputs = [str(case.get("input") or "").strip() for case in cases if str(case.get("input") or "").strip()]
    lines = [
        "# Provider Greeting Probe",
        "",
        f"- generated_at: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- cases: {', '.join(case_inputs)}",
        f"- surface_markers: {', '.join(SURFACE_MARKERS)}",
        "",
    ]
    for provider, items in by_provider.items():
        marker_hits = sum(1 for item in items if item.get("surface_markers"))
        lines.append(f"## {provider}")
        lines.append("")
        lines.append(f"- runs: {len(items)}")
        lines.append(f"- marker_hit_runs: {marker_hits}")
        lines.append("")
        for item in items:
            lines.append(f"### {item['case_name']} | {item['input']} (repeat {item['repeat']})")
            lines.append("")
            lines.append(f"- temperature: {item.get('temperature')}")
            if item.get("judge_focus"):
                lines.append(f"- focus: {item.get('judge_focus')}")
            lines.append(f"- markers: {item.get('surface_markers')}")
            lines.append(f"- output: {str(item.get('output') or '').replace(chr(10), ' / ')}")
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare provider behavior on ordinary greeting prompts.")
    parser.add_argument("--providers", nargs="+", default=["qwen", "deepseek"])
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--case", action="append", help="Run only the specified daily-surface case name.")
    args = parser.parse_args()

    all_rows: list[dict[str, Any]] = []
    for provider in args.providers:
        all_rows.extend(_run_provider(provider, repeats=max(1, int(args.repeats)), case_names=args.case))

    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    json_path = REPORT_DIR / f"provider-greeting-probe-{run_id}.json"
    md_path = REPORT_DIR / f"provider-greeting-probe-{run_id}.md"
    json_path.write_text(json.dumps(all_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_to_markdown(all_rows), encoding="utf-8")
    print(f"[provider-greeting-probe] json={json_path}")
    print(f"[provider-greeting-probe] md={md_path}")


if __name__ == "__main__":
    main()
