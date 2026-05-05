from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from amadeus_thread0.graph_parts.digital_body_runtime import (  # noqa: E402
    normalize_digital_body_state,
    normalize_embodied_context,
)
from amadeus_thread0.graph_parts.perception import attach_perception_context  # noqa: E402
from amadeus_thread0.utils.cli_views import (  # noqa: E402
    build_evolution_cli_summary,
    build_evolution_summary_line,
)


REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
TMP_ROOT = PROJECT_ROOT / "evals" / "_tmp" / "tts-presence-timing"
TMP_ROOT.mkdir(parents=True, exist_ok=True)


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _check(name: str, passed: bool, detail: str = "") -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": str(detail or "").strip()}


def _tts_presence_state(
    *,
    enabled: bool,
    availability: str,
    status: str,
    backend: str = "dashscope_realtime",
    run_id: str = "",
) -> dict[str, Any]:
    return {
        "availability": availability,
        "enabled": bool(enabled),
        "backend": backend,
        "voice_profile_id": "default",
        "voice_profile_state": "ready" if enabled else "disabled",
        "queue_state": "idle",
        "last_status": status,
        "last_run_id": run_id,
        "captures_user_audio": False,
        "stores_generated_audio": False,
        "arbitrary_audio_capture": False,
    }


def _tts_timing(
    *,
    event_id: str,
    delivery_mode: str,
    presence_family: str,
    pause_profile: str,
    planned_delay_ms: int = 0,
    actual_start_delay_ms: int = 0,
    duration_ms: int = 0,
    silence_before_ms: int = 0,
    silence_after_ms: int = 0,
    allow_interrupt: bool = True,
    interrupted: bool = False,
) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "delivery_mode": delivery_mode,
        "presence_family": presence_family,
        "interaction_mode": "tts_presence_timing",
        "planned_delay_ms": int(planned_delay_ms),
        "actual_start_delay_ms": int(actual_start_delay_ms),
        "duration_ms": int(duration_ms),
        "silence_before_ms": int(silence_before_ms),
        "silence_after_ms": int(silence_after_ms),
        "pause_profile": pause_profile,
        "allow_interrupt": bool(allow_interrupt),
        "interrupted": bool(interrupted),
    }


def _scenario_specs(run_root: Path | None = None) -> list[dict[str, Any]]:
    root = Path(run_root or TMP_ROOT)
    return [
        {
            "id": "spoken_final_text_no_drift",
            "title": "spoken_final_text_no_drift",
            "focus": "Delivered TTS must speak the frozen final_text without introducing a second utterance.",
            "run_root": str(root / "spoken_final_text_no_drift"),
            "final_text": "收到了。",
            "tts_utterance_text": "收到了。",
            "event_id": "evt_tts_20260505_0001",
            "body": {
                "active_surface": "voice",
                "perception_channels": ["dialogue", "voice", "TTS_presence_timing"],
                "action_channels": ["language", "voice"],
                "world_surfaces": ["tts"],
                "access_state": {
                    "mode": "native_only",
                    "tts_presence_state": _tts_presence_state(
                        enabled=True,
                        availability="available",
                        status="delivered",
                        run_id="evt_tts_20260505_0001",
                    ),
                },
                "resource_state": {
                    "tts_presence_timing": _tts_timing(
                        event_id="evt_tts_20260505_0001",
                        delivery_mode="spoken",
                        presence_family="spoken_output",
                        pause_profile="direct",
                        planned_delay_ms=160,
                        actual_start_delay_ms=180,
                        duration_ms=3120,
                    )
                },
            },
            "consequence": {
                "kind": "tts_presence_delivered",
                "summary": "TTS delivered the frozen final text.",
                "tts_presence_timing": _tts_timing(
                    event_id="evt_tts_20260505_0001",
                    delivery_mode="spoken",
                    presence_family="spoken_output",
                    pause_profile="direct",
                    planned_delay_ms=160,
                    actual_start_delay_ms=180,
                    duration_ms=3120,
                ),
            },
        },
        {
            "id": "text_only_when_tts_disabled",
            "title": "text_only_when_tts_disabled",
            "focus": "Disabled TTS should preserve the final text as text-only timing telemetry.",
            "run_root": str(root / "text_only_when_tts_disabled"),
            "final_text": "我先把这部分写给你。",
            "tts_utterance_text": "",
            "event_id": "evt_tts_20260505_0002",
            "body": {
                "active_surface": "dialogue",
                "perception_channels": ["dialogue", "TTS_presence_timing"],
                "action_channels": ["language"],
                "world_surfaces": ["tts"],
                "access_state": {
                    "mode": "native_only",
                    "tts_presence_state": _tts_presence_state(
                        enabled=False,
                        availability="disabled",
                        status="disabled",
                        run_id="evt_tts_20260505_0002",
                    ),
                },
                "resource_state": {
                    "tts_presence_timing": _tts_timing(
                        event_id="evt_tts_20260505_0002",
                        delivery_mode="text_only",
                        presence_family="text_only",
                        pause_profile="disabled",
                        allow_interrupt=False,
                    )
                },
            },
            "consequence": {
                "kind": "tts_presence_text_only",
                "summary": "TTS was disabled, so the frozen final text remained text-only.",
                "tts_presence_timing": _tts_timing(
                    event_id="evt_tts_20260505_0002",
                    delivery_mode="text_only",
                    presence_family="text_only",
                    pause_profile="disabled",
                    allow_interrupt=False,
                ),
            },
        },
        {
            "id": "deliberate_silence_as_presence_timing",
            "title": "deliberate_silence_as_presence_timing",
            "focus": "Deliberate silence should be timing telemetry, not audio capture or emotion inference.",
            "run_root": str(root / "deliberate_silence_as_presence_timing"),
            "final_text": "……",
            "tts_utterance_text": "",
            "event_id": "evt_tts_20260505_0003",
            "body": {
                "active_surface": "voice",
                "perception_channels": ["dialogue", "voice", "TTS_presence_timing"],
                "action_channels": ["language", "voice"],
                "world_surfaces": ["tts"],
                "access_state": {
                    "mode": "native_only",
                    "tts_presence_state": _tts_presence_state(
                        enabled=True,
                        availability="available",
                        status="silent",
                        run_id="evt_tts_20260505_0003",
                    ),
                },
                "resource_state": {
                    "tts_presence_timing": _tts_timing(
                        event_id="evt_tts_20260505_0003",
                        delivery_mode="silent",
                        presence_family="deliberate_silence",
                        pause_profile="silence",
                        silence_before_ms=420,
                        silence_after_ms=680,
                    )
                },
            },
            "consequence": {
                "kind": "tts_presence_silent",
                "summary": "A deliberate silence was carried as presence timing only.",
                "tts_presence_timing": _tts_timing(
                    event_id="evt_tts_20260505_0003",
                    delivery_mode="silent",
                    presence_family="deliberate_silence",
                    pause_profile="silence",
                    silence_before_ms=420,
                    silence_after_ms=680,
                ),
            },
        },
    ]


def _event_for_spec(spec: dict[str, Any]) -> dict[str, Any]:
    consequence = _dict(spec.get("consequence"))
    timing = _dict(consequence.get("tts_presence_timing"))
    event_id = str(spec.get("event_id") or "").strip()
    return attach_perception_context(
        {
            "kind": "tts_presence_timing_observation",
            "source": "tts",
            "text": "TTS presence timing observation for the frozen final text.",
            "final_text_ref": "turn.final_text",
            "created_at": 1710000211,
            "perception": {
                "delivery_mode": str(timing.get("delivery_mode") or "").strip(),
            },
            "digital_body_hints": {
                "tts_presence_state": _dict(_dict(spec.get("body")).get("access_state")).get(
                    "tts_presence_state",
                    {},
                ),
                "tts_presence_timing": timing,
            },
        },
        thread_id="tts-presence-timing-smokes",
        turn_now_ts=1710000211,
        turn_id=f"tts-presence-timing-smokes:{event_id}",
    )


def _no_final_text_drift(*, final_text: str, spoken_text: str, delivery_mode: str) -> bool:
    final = str(final_text or "").strip()
    spoken = str(spoken_text or "").strip()
    mode = str(delivery_mode or "").strip()
    if mode == "spoken":
        return bool(final) and spoken == final
    return not spoken or spoken == final


def _evaluate_result(result: dict[str, Any]) -> dict[str, Any]:
    scenario_id = str(result.get("id") or "").strip()
    timing = _dict(result.get("tts_presence_timing"))
    state = _dict(result.get("tts_presence_state"))
    perception = _dict(_dict(result.get("current_event")).get("perception"))
    current_turn = _dict(_dict(result.get("turn_summary")).get("current_turn"))
    delivery_mode = str(timing.get("delivery_mode") or "").strip()
    checks = {
        "perception_is_runtime_tts": _check(
            "perception_is_runtime_tts",
            perception.get("modality") == "TTS_presence_timing"
            and perception.get("source_role") == "runtime"
            and perception.get("trust_tier") == "high_runtime_telemetry",
            f"perception={perception}",
        ),
        "no_final_text_drift": _check(
            "no_final_text_drift",
            _no_final_text_drift(
                final_text=str(result.get("final_text") or ""),
                spoken_text=str(result.get("tts_utterance_text") or ""),
                delivery_mode=delivery_mode,
            ),
            f"final_text={result.get('final_text')!r}, tts_utterance_text={result.get('tts_utterance_text')!r}",
        ),
        "timing_only_boundaries": _check(
            "timing_only_boundaries",
            not bool(state.get("captures_user_audio"))
            and not bool(state.get("stores_generated_audio"))
            and not bool(state.get("arbitrary_audio_capture"))
            and "audio_path" not in result
            and "generated_audio_path" not in result,
            f"tts_presence_state={state}",
        ),
        "summary_surfaces_timing": _check(
            "summary_surfaces_timing",
            current_turn.get("tts_presence_delivery_mode") == delivery_mode
            and current_turn.get("tts_presence_status") == state.get("last_status"),
            f"current_turn={current_turn}",
        ),
    }
    if scenario_id == "spoken_final_text_no_drift":
        checks["spoken_delivered_branch"] = _check(
            "spoken_delivered_branch",
            state.get("last_status") == "delivered"
            and delivery_mode == "spoken"
            and int(timing.get("duration_ms") or 0) > 0,
            f"state={state}, timing={timing}",
        )
    elif scenario_id == "text_only_when_tts_disabled":
        checks["tts_disabled_text_only"] = _check(
            "tts_disabled_text_only",
            state.get("enabled") is False
            and state.get("availability") == "disabled"
            and delivery_mode == "text_only"
            and timing.get("pause_profile") == "disabled",
            f"state={state}, timing={timing}",
        )
    elif scenario_id == "deliberate_silence_as_presence_timing":
        checks["deliberate_silence_branch"] = _check(
            "deliberate_silence_branch",
            delivery_mode == "silent"
            and timing.get("pause_profile") == "silence"
            and int(timing.get("silence_before_ms") or 0) > 0
            and int(timing.get("silence_after_ms") or 0) > 0,
            f"timing={timing}",
        )
    else:
        checks["known_scenario"] = _check("known_scenario", False, scenario_id)
    return {
        "passed": all(bool(row.get("passed")) for row in checks.values()),
        "checks": checks,
    }


def _run_single_scenario(spec: dict[str, Any]) -> dict[str, Any]:
    started = time.time()
    current_event = _event_for_spec(spec)
    body = normalize_digital_body_state(_dict(spec.get("body")))
    consequence = normalize_embodied_context(_dict(spec.get("consequence")))
    turn_summary = build_evolution_cli_summary(
        current_event=current_event,
        digital_body_state=body,
        digital_body_consequence=consequence,
    )
    summary_line = build_evolution_summary_line(turn_summary)
    tts_presence_state = _dict(_dict(body.get("access_state")).get("tts_presence_state"))
    tts_presence_timing = _dict(consequence.get("tts_presence_timing"))
    result = {
        "id": str(spec.get("id") or "").strip(),
        "title": str(spec.get("title") or "").strip(),
        "focus": str(spec.get("focus") or "").strip(),
        "duration_s": round(time.time() - started, 3),
        "final_text": str(spec.get("final_text") or "").strip(),
        "tts_utterance_text": str(spec.get("tts_utterance_text") or "").strip(),
        "current_event": current_event,
        "digital_body": body,
        "digital_body_consequence": consequence,
        "turn_summary": turn_summary,
        "summary_line": summary_line,
        "tts_presence_state": tts_presence_state,
        "tts_presence_timing": tts_presence_timing,
    }
    result["evaluation"] = _evaluate_result(result)
    return result


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# TTS Presence Timing Smokes ({report.get('run_id', 'unknown')})",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Passed: `{report.get('passed', 0)}`",
        f"Failed: `{report.get('failed', 0)}`",
        "",
        "## Scenario Summary",
        "",
        "| Scenario | Status | Duration (s) | Delivery Mode |",
        "| --- | --- | ---: | --- |",
    ]
    for result in report.get("results") or []:
        if not isinstance(result, dict):
            continue
        evaluation = _dict(result.get("evaluation"))
        timing = _dict(result.get("tts_presence_timing"))
        status = "passed" if bool(evaluation.get("passed")) else "failed"
        lines.append(
            f"| `{result.get('id', '')}` | `{status}` | {float(result.get('duration_s') or 0.0):.3f} | `{timing.get('delivery_mode', '')}` |"
        )
    for result in report.get("results") or []:
        if not isinstance(result, dict):
            continue
        evaluation = _dict(result.get("evaluation"))
        lines.extend(
            [
                "",
                f"## {result.get('title', result.get('id', 'scenario'))}",
                "",
                f"- Focus: {result.get('focus', '')}",
                f"- Status: `{'passed' if bool(evaluation.get('passed')) else 'failed'}`",
                f"- Final Text: `{result.get('final_text', '')}`",
                f"- TTS Presence State: `{json.dumps(_dict(result.get('tts_presence_state')), ensure_ascii=False)}`",
                f"- TTS Presence Timing: `{json.dumps(_dict(result.get('tts_presence_timing')), ensure_ascii=False)}`",
                f"- Summary Line: `{result.get('summary_line', '')}`",
                "- Checks:",
            ]
        )
        checks = evaluation.get("checks") if isinstance(evaluation.get("checks"), dict) else {}
        for check in checks.values():
            if not isinstance(check, dict):
                continue
            lines.append(
                f"  - `{'pass' if bool(check.get('passed')) else 'fail'}` {check.get('name', '')}: {check.get('detail', '')}"
            )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run fixed TTS presence timing smoke scenarios.")
    parser.add_argument("--run-tag", default="", help="Optional suffix for report filenames.")
    parser.add_argument(
        "--scenario",
        action="append",
        default=[],
        help="Optional scenario id to run. Repeat to run multiple specific scenarios.",
    )
    args = parser.parse_args()

    requested = {str(item or "").strip() for item in _list(args.scenario) if str(item or "").strip()}
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    specs = _scenario_specs(TMP_ROOT / run_id)
    if requested:
        specs = [spec for spec in specs if str(spec.get("id") or "").strip() in requested]
        if not specs:
            available = ", ".join(sorted(str(spec.get("id") or "").strip() for spec in _scenario_specs()))
            raise SystemExit(f"No TTS presence timing smoke scenarios matched {sorted(requested)!r}. Available: {available}")

    results = [_run_single_scenario(spec) for spec in specs]
    passed = len([result for result in results if bool(_dict(result.get("evaluation")).get("passed"))])
    failed = len(results) - passed
    report = {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": "passed" if failed == 0 else "failed",
        "passed": passed,
        "failed": failed,
        "results": results,
        "scenario_artifact_references": [
            {
                "id": str(result.get("id") or "").strip(),
                "title": str(result.get("title") or "").strip(),
                "status": "passed" if bool(_dict(result.get("evaluation")).get("passed")) else "failed",
            }
            for result in results
            if isinstance(result, dict)
        ],
    }
    json_path = REPORT_DIR / f"tts-presence-timing-smokes-{run_id}.json"
    md_path = REPORT_DIR / f"tts-presence-timing-smokes-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(f"[tts-presence-timing-smokes] json={json_path}")
    print(f"[tts-presence-timing-smokes] md={md_path}")
    print(f"[tts-presence-timing-smokes] overall_status={report.get('overall_status', 'unknown')}")


if __name__ == "__main__":
    main()
