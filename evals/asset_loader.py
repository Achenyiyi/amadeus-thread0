from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DAILY_SURFACE_PACK_PATH = PROJECT_ROOT / "evals" / "daily_surface_adaptation_pack.json"
_DEFAULT_SURFACE_MARKERS = ("机关", "实验", "世界线", "组织", "时间旅行", "时间跳跃", "变动率")
_DAILY_SURFACE_PACK_CACHE: dict[str, Any] | None = None


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            out.append(text)
    return out


def load_daily_surface_pack() -> dict[str, Any]:
    global _DAILY_SURFACE_PACK_CACHE
    if _DAILY_SURFACE_PACK_CACHE is not None:
        return _DAILY_SURFACE_PACK_CACHE
    if not _DAILY_SURFACE_PACK_PATH.exists():
        _DAILY_SURFACE_PACK_CACHE = {
            "source_note": "",
            "global_principles": [],
            "cases": [],
        }
        return _DAILY_SURFACE_PACK_CACHE
    raw = _read_json(_DAILY_SURFACE_PACK_PATH)
    if not isinstance(raw, dict):
        raise ValueError(f"daily surface pack must be a JSON object: {_DAILY_SURFACE_PACK_PATH}")
    cases = raw.get("cases")
    if not isinstance(cases, list):
        raise ValueError(f"daily surface pack cases must be a list: {_DAILY_SURFACE_PACK_PATH}")
    _DAILY_SURFACE_PACK_CACHE = {
        "source_note": str(raw.get("source_note") or "").strip(),
        "global_principles": _string_list(raw.get("global_principles")),
        "cases": [item for item in cases if isinstance(item, dict)],
    }
    return _DAILY_SURFACE_PACK_CACHE


def daily_surface_marker_set() -> tuple[str, ...]:
    markers: list[str] = []
    seen: set[str] = set()
    for item in _DEFAULT_SURFACE_MARKERS:
        if item not in seen:
            markers.append(item)
            seen.add(item)
    for case in load_daily_surface_pack().get("cases", []):
        for item in _string_list(case.get("surface_markers_avoid")):
            if item not in seen:
                markers.append(item)
                seen.add(item)
    return tuple(markers)


def daily_surface_provider_cases(*, names: list[str] | None = None) -> list[dict[str, Any]]:
    wanted = {str(item or "").strip() for item in (names or []) if str(item or "").strip()}
    out: list[dict[str, Any]] = []
    for case in load_daily_surface_pack().get("cases", []):
        name = str(case.get("name") or "").strip()
        if wanted and name not in wanted:
            continue
        if not bool(case.get("provider_probe_enabled")):
            continue
        input_text = str(case.get("input") or "").strip()
        if not name or not input_text:
            continue
        markers = list(dict.fromkeys(_string_list(case.get("surface_markers_avoid")) + list(_DEFAULT_SURFACE_MARKERS)))
        out.append(
            {
                "name": name,
                "input": input_text,
                "judge_focus": str(case.get("judge_focus") or case.get("focus") or "").strip(),
                "surface_markers_avoid": markers,
                "preferred_signals": _string_list(case.get("preferred_signals")),
                "avoid_bias": _string_list(case.get("avoid_bias")),
            }
        )
    return out


def daily_surface_subjective_cases() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for case in load_daily_surface_pack().get("cases", []):
        name = str(case.get("name") or "").strip()
        if not name:
            continue
        turns = _string_list(case.get("turns"))
        input_text = str(case.get("input") or "").strip()
        if not turns and input_text:
            turns = [input_text]
        if not turns:
            continue
        out.append(
            {
                "name": name,
                "axis": str(case.get("axis") or "daily_surface").strip() or "daily_surface",
                "focus": str(case.get("focus") or case.get("judge_focus") or "").strip(),
                "speaker_style": str(case.get("speaker_style") or "user").strip().lower() or "user",
                "review_targets": _string_list(case.get("review_targets"))
                or ["daily_surface", "daily_persona", "renderer"],
                "turns": turns,
            }
        )
    return out


def daily_surface_eval_examples(run_id: str) -> list[dict[str, Any]]:
    base = f"daily-{str(run_id or '').strip()}"
    out: list[dict[str, Any]] = []
    for case in load_daily_surface_pack().get("cases", []):
        name = str(case.get("name") or "").strip()
        if not name:
            continue
        turns = _string_list(case.get("turns"))
        input_text = str(case.get("input") or "").strip()
        if not turns and input_text:
            payload: dict[str, Any] = {"input": input_text}
        elif turns:
            payload = {"turns": turns}
        else:
            continue
        slug = name.replace("_", "-")
        row: dict[str, Any] = {
            "thread_id": f"{base}-{slug}-0",
            "tags": ["daily_persona", "natural_style"] + _string_list(case.get("probe_tags")),
            "judge_focus": str(case.get("judge_focus") or case.get("focus") or "").strip(),
        }
        row.update(payload)
        for key, value in case.items():
            if key.startswith("expect_"):
                row[key] = value
        out.append(row)
    return out
