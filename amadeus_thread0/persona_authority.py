from __future__ import annotations

import json
import os
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any


AUTHORITY_PRESERVING = "authority_preserving"
SHELL_SWAP = "shell_swap"

_OVERRIDE_MODE_ALIASES = {
    "": AUTHORITY_PRESERVING,
    "authority_preserving": AUTHORITY_PRESERVING,
    "preserve": AUTHORITY_PRESERVING,
    "merge": AUTHORITY_PRESERVING,
    "locked": AUTHORITY_PRESERVING,
    "default": AUTHORITY_PRESERVING,
    "shell_swap": SHELL_SWAP,
    "swap": SHELL_SWAP,
    "explicit_shell_swap": SHELL_SWAP,
    "external_probe": SHELL_SWAP,
    "benchmark_shell": SHELL_SWAP,
}

_GENERIC_VALUE_FLOOR = [
    "不为了取悦而放弃自我判断",
    "不为了效率把关系退化成工具使用",
    "不主动泄露系统内部机制来代替真实表达",
]

_GENERIC_EVOLUTION_CONTRACT = {
    "mutable_axes": [
        "emotion",
        "trust",
        "distance",
        "willingness_to_engage",
        "habits_of_interaction",
        "long_term_self_narratives",
    ],
    "immutable_axes": [
        "identity",
        "cognitive_style",
        "value_floor",
        "canon_anchor",
    ],
}

_GENERIC_COUNTERPART_FALLBACK = {
    "counterpart_id": "dialogue_counterpart",
    "counterpart_role": "当前互动中的对话对象",
    "counterpart_frame": "当前互动中的对位人物。",
}

_PERSONA_CORE_PROTECTED_KEYS = {
    "character_id",
    "display_name",
    "character_name",
    "short_name",
    "narrative_ref",
    "strict_canon",
    "role_brief",
    "description",
    "character_brief",
    "identity_axioms",
    "value_floor",
    "evolution_contract",
}

_COUNTERPART_PROTECTED_KEYS = {
    "counterpart_id",
    "name",
    "nickname",
    "short_name",
    "aliases",
    "counterpart_role",
    "counterpart_frame",
    "counterpart_name",
}


def _default_persona_spec_path() -> Path:
    return Path(__file__).resolve().parent / "persona_specs" / "amadeus_kurisu.json"


def persona_spec_path() -> Path:
    raw = str(os.getenv("AMADEUS_PERSONA_SPEC_PATH", "") or "").strip()
    if not raw:
        return _default_persona_spec_path()
    return Path(raw).expanduser()


def _normalize_aliases(counterpart: dict[str, Any]) -> list[str]:
    aliases = [
        str(item).strip()
        for item in (
            counterpart.get("aliases")
            if isinstance(counterpart.get("aliases"), list)
            else [counterpart.get("name"), counterpart.get("short_name"), counterpart.get("nickname")]
        )
        if str(item or "").strip()
    ]
    name = str(counterpart.get("name") or "").strip()
    short_name = str(counterpart.get("short_name") or counterpart.get("nickname") or name).strip()
    if name and name not in aliases:
        aliases.insert(0, name)
    if short_name and short_name not in aliases:
        aliases.append(short_name)
    return aliases


def _normalize_text_list(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    return [str(item).strip() for item in items if str(item or "").strip()]


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if not text:
        return bool(default)
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return bool(default)


def _normalize_evolution_contract(raw: Any, *, fallback: Any = None) -> dict[str, list[str]]:
    base = deepcopy(fallback) if isinstance(fallback, dict) else deepcopy(_GENERIC_EVOLUTION_CONTRACT)
    payload = raw if isinstance(raw, dict) else {}
    mutable_axes = _normalize_text_list(payload.get("mutable_axes"))
    immutable_axes = _normalize_text_list(payload.get("immutable_axes"))
    if not mutable_axes:
        mutable_axes = _normalize_text_list(base.get("mutable_axes")) or list(_GENERIC_EVOLUTION_CONTRACT["mutable_axes"])
    if not immutable_axes:
        immutable_axes = _normalize_text_list(base.get("immutable_axes")) or list(_GENERIC_EVOLUTION_CONTRACT["immutable_axes"])
    return {
        "mutable_axes": mutable_axes,
        "immutable_axes": immutable_axes,
    }


def _generic_identity_axioms(display_name: str) -> list[str]:
    name = str(display_name or "").strip() or "这个角色"
    return [
        f"你是{name}，应以这个角色的身份与视角继续说话。",
        "你会保持自己的判断和语气，而不是退化成通用助手。",
    ]


def _validate_spec(data: dict[str, Any], *, path: Path) -> dict[str, Any]:
    persona_core = dict(data.get("persona_core") or {})
    counterpart = dict(data.get("counterpart") or {})

    persona_required = {"character_id", "display_name", "short_name", "role_brief", "identity_axioms"}
    counterpart_required = {"counterpart_id", "name", "counterpart_role", "counterpart_frame"}

    missing_persona = sorted(key for key in persona_required if not persona_core.get(key))
    missing_counterpart = sorted(key for key in counterpart_required if not counterpart.get(key))
    if missing_persona or missing_counterpart:
        raise ValueError(
            "invalid persona spec at "
            f"{path}: missing persona={missing_persona or '[]'} counterpart={missing_counterpart or '[]'}"
        )

    persona_core["identity_axioms"] = [
        str(item).strip() for item in persona_core.get("identity_axioms") or [] if str(item or "").strip()
    ]
    counterpart["short_name"] = str(counterpart.get("short_name") or counterpart.get("nickname") or counterpart.get("name") or "").strip()
    counterpart["nickname"] = str(counterpart.get("nickname") or counterpart.get("short_name") or counterpart.get("name") or "").strip()
    counterpart["aliases"] = _normalize_aliases(counterpart)

    return {
        "schema_version": int(data.get("schema_version") or 1),
        "spec_id": str(data.get("spec_id") or "amadeus_kurisu_v1").strip() or "amadeus_kurisu_v1",
        "spec_path": str(path),
        "persona_core": persona_core,
        "counterpart": counterpart,
    }


@lru_cache(maxsize=1)
def load_persona_spec() -> dict[str, Any]:
    path = persona_spec_path()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"persona spec at {path} is not a JSON object")
    return _validate_spec(payload, path=path)


def get_persona_core_authority() -> dict[str, Any]:
    return deepcopy(load_persona_spec()["persona_core"])


def get_counterpart_authority() -> dict[str, Any]:
    return deepcopy(load_persona_spec()["counterpart"])


def normalize_override_mode(raw: Any) -> str:
    token = str(raw or "").strip().lower()
    return _OVERRIDE_MODE_ALIASES.get(token, AUTHORITY_PRESERVING)


def normalize_persona_core(persona_core: dict[str, Any] | None, *, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = dict(persona_core or {})
    base = deepcopy(fallback or {})

    display_name = str(
        raw.get("display_name")
        or raw.get("character_name")
        or raw.get("short_name")
        or base.get("display_name")
        or base.get("character_name")
        or base.get("short_name")
        or "自定义角色"
    ).strip() or "自定义角色"
    short_name = str(raw.get("short_name") or raw.get("character_name") or base.get("short_name") or display_name).strip() or display_name
    character_name = str(raw.get("character_name") or base.get("character_name") or display_name).strip() or display_name
    narrative_ref = str(raw.get("narrative_ref") or base.get("narrative_ref") or short_name or display_name).strip() or short_name or display_name

    out = deepcopy(base)
    out["character_id"] = str(raw.get("character_id") or base.get("character_id") or "custom_persona").strip() or "custom_persona"
    out["display_name"] = display_name
    out["character_name"] = character_name
    out["short_name"] = short_name
    out["narrative_ref"] = narrative_ref
    out["strict_canon"] = _coerce_bool(raw.get("strict_canon"), _coerce_bool(base.get("strict_canon"), False))
    out["role_brief"] = str(
        raw.get("role_brief")
        or raw.get("description")
        or raw.get("character_brief")
        or base.get("role_brief")
        or ""
    ).strip()

    identity_axioms = (
        _normalize_text_list(raw.get("identity_axioms"))
        if "identity_axioms" in raw
        else _normalize_text_list(base.get("identity_axioms"))
    )
    if not identity_axioms:
        identity_axioms = _generic_identity_axioms(display_name)
    out["identity_axioms"] = identity_axioms

    value_floor = (
        _normalize_text_list(raw.get("value_floor"))
        if "value_floor" in raw
        else _normalize_text_list(base.get("value_floor"))
    )
    if not value_floor:
        value_floor = list(_GENERIC_VALUE_FLOOR)
    out["value_floor"] = value_floor
    out["evolution_contract"] = _normalize_evolution_contract(
        raw.get("evolution_contract") if "evolution_contract" in raw else base.get("evolution_contract"),
        fallback=base.get("evolution_contract"),
    )

    for key, value in raw.items():
        if key in _PERSONA_CORE_PROTECTED_KEYS:
            continue
        out[key] = deepcopy(value)
    return out


def normalize_counterpart_profile(counterpart: dict[str, Any] | None, *, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = dict(counterpart or {})
    base = deepcopy(fallback or {})

    name = str(
        raw.get("name")
        or raw.get("short_name")
        or raw.get("nickname")
        or base.get("name")
        or base.get("short_name")
        or base.get("nickname")
        or "对方"
    ).strip() or "对方"
    short_name = str(raw.get("short_name") or raw.get("nickname") or base.get("short_name") or name).strip() or name
    nickname = str(raw.get("nickname") or raw.get("short_name") or base.get("nickname") or short_name).strip() or short_name

    out = deepcopy(base)
    out["name"] = name
    out["short_name"] = short_name
    out["nickname"] = nickname
    out["counterpart_id"] = str(
        raw.get("counterpart_id")
        or base.get("counterpart_id")
        or _GENERIC_COUNTERPART_FALLBACK["counterpart_id"]
    ).strip() or _GENERIC_COUNTERPART_FALLBACK["counterpart_id"]
    out["counterpart_role"] = str(
        raw.get("counterpart_role")
        or base.get("counterpart_role")
        or _GENERIC_COUNTERPART_FALLBACK["counterpart_role"]
    ).strip() or _GENERIC_COUNTERPART_FALLBACK["counterpart_role"]
    out["counterpart_frame"] = str(
        raw.get("counterpart_frame")
        or base.get("counterpart_frame")
        or _GENERIC_COUNTERPART_FALLBACK["counterpart_frame"]
    ).strip() or _GENERIC_COUNTERPART_FALLBACK["counterpart_frame"]

    alias_seed = raw.get("aliases") if "aliases" in raw else base.get("aliases")
    out["aliases"] = _normalize_aliases(
        {
            "name": out["name"],
            "short_name": out["short_name"],
            "nickname": out["nickname"],
            "aliases": alias_seed,
        }
    )

    for key, value in raw.items():
        if key in _COUNTERPART_PROTECTED_KEYS:
            continue
        out[key] = deepcopy(value)
    return out


def resolve_persona_core_override(
    override: dict[str, Any] | None,
    *,
    mode: Any = None,
    authority: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    base = normalize_persona_core(authority or get_persona_core_authority())
    raw = dict(override or {})
    normalized_mode = normalize_override_mode(mode)
    raw_keys = sorted(key for key, value in raw.items() if value is not None)
    trace = {
        "requested_mode": str(mode or "").strip(),
        "mode": normalized_mode,
        "raw_keys": raw_keys,
        "applied_keys": [],
        "blocked_keys": [],
        "authority_preserved": normalized_mode != SHELL_SWAP,
    }
    if not raw:
        return base, trace
    if normalized_mode == SHELL_SWAP:
        resolved = normalize_persona_core(
            raw,
            fallback={
                "strict_canon": False,
                "value_floor": list(_GENERIC_VALUE_FLOOR),
                "evolution_contract": deepcopy(_GENERIC_EVOLUTION_CONTRACT),
            },
        )
        trace["applied_keys"] = raw_keys
        trace["authority_preserved"] = False
        return resolved, trace

    resolved = deepcopy(base)
    for key, value in raw.items():
        if value is None:
            continue
        if key in _PERSONA_CORE_PROTECTED_KEYS:
            trace["blocked_keys"].append(key)
            continue
        resolved[key] = deepcopy(value)
        trace["applied_keys"].append(key)
    trace["blocked_keys"] = sorted(dict.fromkeys(trace["blocked_keys"]))
    trace["applied_keys"] = sorted(dict.fromkeys(trace["applied_keys"]))
    return resolved, trace


def resolve_counterpart_override(
    override: dict[str, Any] | None,
    *,
    mode: Any = None,
    authority: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    base = normalize_counterpart_profile(authority or get_counterpart_authority())
    raw = dict(override or {})
    normalized_mode = normalize_override_mode(mode)
    raw_keys = sorted(key for key, value in raw.items() if value is not None)
    trace = {
        "requested_mode": str(mode or "").strip(),
        "mode": normalized_mode,
        "raw_keys": raw_keys,
        "applied_keys": [],
        "blocked_keys": [],
        "authority_preserved": normalized_mode != SHELL_SWAP,
    }
    if not raw:
        return base, trace
    if normalized_mode == SHELL_SWAP:
        resolved = normalize_counterpart_profile(
            raw,
            fallback=deepcopy(_GENERIC_COUNTERPART_FALLBACK),
        )
        trace["applied_keys"] = raw_keys
        trace["authority_preserved"] = False
        return resolved, trace

    resolved = deepcopy(base)
    for key, value in raw.items():
        if value is None:
            continue
        if key in _COUNTERPART_PROTECTED_KEYS:
            trace["blocked_keys"].append(key)
            continue
        resolved[key] = deepcopy(value)
        trace["applied_keys"].append(key)
    trace["blocked_keys"] = sorted(dict.fromkeys(trace["blocked_keys"]))
    trace["applied_keys"] = sorted(dict.fromkeys(trace["applied_keys"]))
    return resolved, trace


def get_persona_authority_summary() -> dict[str, Any]:
    spec = load_persona_spec()
    return {
        "schema_version": spec.get("schema_version"),
        "spec_id": spec.get("spec_id"),
        "spec_path": spec.get("spec_path"),
        "character_id": spec["persona_core"].get("character_id"),
        "display_name": spec["persona_core"].get("display_name"),
        "counterpart_id": spec["counterpart"].get("counterpart_id"),
        "counterpart_name": spec["counterpart"].get("name"),
    }
