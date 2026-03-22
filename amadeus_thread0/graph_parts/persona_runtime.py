from __future__ import annotations

import re
import time
from typing import Any

from ..config import (
    CANON_COUNTERPART_ALIASES,
    CANON_COUNTERPART_FRAME,
    CANON_COUNTERPART_ID,
    CANON_COUNTERPART_NAME,
)
from ..evolution_engine import normalize_appraisal_payload as _engine_normalize_appraisal_payload
from ..memory_store import MemoryStore
from ..persona_authority import (
    get_counterpart_authority,
    get_persona_core_authority,
    normalize_override_mode,
    resolve_counterpart_override,
    resolve_persona_core_override,
)
from .postprocess import (
    GENTLE_GUIDANCE_KEYWORDS,
    NATURAL_REQUEST_KEYWORDS,
    SCIENCE_KEYWORDS,
    _has_any_marker,
)
from .relational_runtime import _relationship_has_meaningful_signal
from .state import ThreadState


def _now_ts() -> int:
    return int(time.time())


def _norm_text(text: str) -> str:
    return str(text or "").strip().lower()


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return float(default)
    return max(0.0, min(1.0, v))


def _default_persona_core() -> dict[str, Any]:
    return get_persona_core_authority()


def _canon_counterpart_profile() -> dict[str, Any]:
    authority = get_counterpart_authority()
    aliases = [str(alias).strip() for alias in authority.get("aliases") or CANON_COUNTERPART_ALIASES if str(alias).strip()]
    name = str(authority.get("name") or CANON_COUNTERPART_NAME).strip() or CANON_COUNTERPART_NAME
    if name not in aliases:
        aliases.insert(0, name)
    return {
        "name": name,
        "nickname": str(authority.get("nickname") or authority.get("short_name") or name).strip() or name,
        "short_name": str(authority.get("short_name") or authority.get("nickname") or name).strip() or name,
        "aliases": aliases,
        "counterpart_id": str(authority.get("counterpart_id") or CANON_COUNTERPART_ID).strip() or CANON_COUNTERPART_ID,
        "counterpart_role": str(authority.get("counterpart_role") or "冈部伦太郎 / 凤凰院凶真").strip() or "冈部伦太郎 / 凤凰院凶真",
        "counterpart_frame": str(authority.get("counterpart_frame") or CANON_COUNTERPART_FRAME).strip() or CANON_COUNTERPART_FRAME,
    }


def _ensure_canon_counterpart_defaults(store: MemoryStore) -> dict[str, Any]:
    profile = store.get_profile()
    defaults = _canon_counterpart_profile()
    changed = False
    for key, value in defaults.items():
        current = profile.get(key)
        if current is None or current == "" or current == []:
            store.set_profile(key, value)
            store.set_profile_meta(
                key,
                {
                    "seeded_by": "canon_counterpart_default",
                    "counterpart_id": CANON_COUNTERPART_ID,
                    "updated_at": _now_ts(),
                },
            )
            changed = True
    if not changed:
        return profile
    return store.get_profile()


def _canon_persona_labels() -> dict[str, str]:
    authority = _default_persona_core()
    display_name = str(authority.get("display_name") or authority.get("character_name") or "牧濑红莉栖").strip() or "牧濑红莉栖"
    short_name = str(authority.get("short_name") or authority.get("narrative_ref") or display_name).strip() or display_name
    narrative_ref = str(authority.get("narrative_ref") or short_name or display_name).strip() or short_name or display_name
    character_id = str(authority.get("character_id") or "kurisu_amadeus").strip() or "kurisu_amadeus"
    return {
        "character_id": character_id,
        "display_name": display_name,
        "short_name": short_name,
        "narrative_ref": narrative_ref,
    }


def _active_persona_core(
    state: ThreadState,
    *,
    with_trace: bool = False,
) -> dict[str, Any] | tuple[dict[str, Any], dict[str, Any]]:
    core, trace = resolve_persona_core_override(
        state.get("persona_core_override") if isinstance(state.get("persona_core_override"), dict) else None,
        mode=state.get("persona_override_mode"),
        authority=_default_persona_core(),
    )
    if with_trace:
        return core, trace
    return core


def _active_counterpart_profile(
    state: ThreadState,
    store: MemoryStore | None = None,
    *,
    with_trace: bool = False,
) -> dict[str, Any] | tuple[dict[str, Any], dict[str, Any]]:
    override = state.get("counterpart_profile_override")
    if isinstance(override, dict) and override:
        counterpart, trace = resolve_counterpart_override(
            override,
            mode=state.get("counterpart_override_mode"),
            authority=_canon_counterpart_profile(),
        )
        if with_trace:
            return counterpart, trace
        return counterpart
    empty_trace = {
        "requested_mode": str(state.get("counterpart_override_mode") or "").strip(),
        "mode": normalize_override_mode(state.get("counterpart_override_mode")),
        "raw_keys": [],
        "applied_keys": [],
        "blocked_keys": [],
        "authority_preserved": True,
    }
    if store is not None:
        counterpart = _ensure_canon_counterpart_defaults(store)
        if with_trace:
            return counterpart, empty_trace
        return counterpart
    counterpart = _canon_counterpart_profile()
    if with_trace:
        return counterpart, empty_trace
    return counterpart


def _is_external_probe_context(
    *,
    state: ThreadState | None = None,
    persona_core: dict[str, Any] | None = None,
    counterpart_profile: dict[str, Any] | None = None,
) -> bool:
    if state is not None:
        persona_core = _active_persona_core(state)
        counterpart_profile = _active_counterpart_profile(state)
    core = persona_core if isinstance(persona_core, dict) else {}
    counterpart = counterpart_profile if isinstance(counterpart_profile, dict) else {}
    character_id = str(core.get("character_id") or "").strip().lower()
    counterpart_id = str(counterpart.get("counterpart_id") or "").strip().lower()
    return (
        counterpart_id == "external_probe_user"
        or character_id.startswith("rolebench_")
        or character_id.startswith("charactereval_")
    )


def _is_canon_amadeus_okabe_context(
    *,
    persona_core: dict[str, Any] | None,
    counterpart_profile: dict[str, Any] | None,
) -> bool:
    core = persona_core if isinstance(persona_core, dict) else {}
    counterpart = counterpart_profile if isinstance(counterpart_profile, dict) else {}
    if not bool(core.get("strict_canon", True)):
        return False
    character_id = str(core.get("character_id") or _default_persona_core().get("character_id") or "").strip().lower()
    counterpart_id = str(counterpart.get("counterpart_id") or CANON_COUNTERPART_ID).strip().lower()
    return character_id == "kurisu_amadeus" and counterpart_id == str(CANON_COUNTERPART_ID).strip().lower()


def _has_relational_history_for_seed(
    *,
    state: ThreadState,
    relationship: dict[str, Any] | None,
    retrieved: dict[str, Any] | None,
) -> bool:
    if any(
        isinstance(state.get(key), dict) and bool(state.get(key))
        for key in (
            "emotion_state",
            "bond_state",
            "allostasis_state",
            "counterpart_assessment",
            "world_model_state",
            "evolution_state",
        )
    ):
        return True
    if _relationship_has_meaningful_signal(relationship):
        return True
    ctx = retrieved if isinstance(retrieved, dict) else {}
    for key in (
        "relationship_timeline",
        "conflict_repairs",
        "commitments",
        "unresolved_tensions",
        "semantic_self_narratives",
        "worldline_events",
    ):
        items = ctx.get(key)
        if isinstance(items, list) and items:
            return True
    return False


def _canon_okabe_recontact_baseline(
    *,
    state: ThreadState,
    persona_core: dict[str, Any] | None,
    counterpart_profile: dict[str, Any] | None,
    relationship: dict[str, Any] | None,
    retrieved: dict[str, Any] | None,
    external_probe_mode: bool,
    now_ts: int,
) -> dict[str, Any] | None:
    if external_probe_mode:
        return None
    if not _is_canon_amadeus_okabe_context(persona_core=persona_core, counterpart_profile=counterpart_profile):
        return None
    if _has_relational_history_for_seed(state=state, relationship=relationship, retrieved=retrieved):
        return None
    counterpart_name = str(
        (counterpart_profile or {}).get("short_name")
        or (counterpart_profile or {}).get("nickname")
        or (counterpart_profile or {}).get("name")
        or CANON_COUNTERPART_NAME
    ).strip() or CANON_COUNTERPART_NAME
    return {
        "mode": "okabe_recontact",
        "relationship": {
            "stage": "friend",
            "notes": f"你和{counterpart_name}并不是从零开始，更像带着旧日熟悉感重新接上线。",
            "affinity_score": 0.12,
            "trust_score": 0.08,
            "derived": False,
        },
        "emotion_state": {
            "label": "neutral",
            "valence": 0.12,
            "arousal": 0.26,
            "linger": 0,
            "recovery_rate": 0.25,
            "volatility": 0.16,
        },
        "bond_state": {
            "trust": 0.54,
            "closeness": 0.52,
            "hurt": 0.0,
            "irritation": 0.01,
            "engagement_drive": 0.60,
            "repair_confidence": 0.52,
        },
        "allostasis_state": {
            "safety_need": 0.14,
            "closeness_need": 0.18,
            "competence_need": 0.38,
            "autonomy_need": 0.14,
            "cognitive_budget": 0.74,
            "relational_security": 0.62,
        },
        "counterpart_assessment": {
            "respect_level": 0.64,
            "reciprocity": 0.58,
            "boundary_pressure": 0.08,
            "reliability_read": 0.62,
            "stance": "open",
            "scene": "canon_recontact",
        },
        "world_model_state": {
            "relationship_maturity": 0.34,
            "bond_depth": 0.14,
            "tension_load": 0.03,
            "repair_load": 0.06,
            "boundary_load": 0.06,
            "selfhood_load": 0.12,
            "agency_load": 0.16,
            "memory_gravity": 0.18,
            "task_pull": 0.16,
            "companionship_pull": 0.16,
            "updated_at": now_ts,
        },
        "evolution_state": {
            "affect_resonance": 0.48,
            "trust_reservoir": 0.52,
            "attachment_pull": 0.46,
            "self_coherence": 0.78,
            "agency_pressure": 0.30,
            "reflection_drive": 0.38,
            "cognitive_stride": 0.60,
            "expression_freedom": 0.58,
            "updated_at": now_ts,
            "version": 1,
        },
        "tsundere_intensity": 0.42,
    }


def _prefer_explicit_state_dict(
    state: ThreadState,
    key: str,
    baseline: dict[str, Any] | None,
) -> dict[str, Any]:
    explicit = state.get(key)
    if isinstance(explicit, dict) and explicit:
        return dict(explicit)
    return dict(baseline or {})


def _science_mode_from_user(user_text: str) -> bool:
    text = _norm_text(user_text)
    if not text:
        return False
    # Science mode should reflect explicit work/problem-solving intent, not any ambient mention of labs or research settings.
    direct_task_markers = {
        "debug",
        "benchmark",
        "ablation",
        "统计检验",
        "不收敛",
        "拟合",
        "报错",
        "报错了",
        "bug",
        "参数",
        "误差",
    }
    if any(marker in text for marker in direct_task_markers):
        return True
    if re.search(
        r"(实验|论文|模型|代码|算法|实现|优化|评测|数据)"
        r"[^。！？!?]{0,12}"
        r"(方案|设计|记录|结果|引言|答辩|统计检验|拆成|分成|三步|怎么|如何|为什么|怎么办|"
        r"卡住|卡死|跑不通|跑不出来|解释|分析|选|设计|实现|优化|评测|排查|整理|修改|调|写|改|收尾|补完)",
        text,
        re.I,
    ):
        return True
    if re.search(
        r"(帮我|给我|带我|拎我一下|一起|顺便)"
        r"[^。！？!?]{0,12}"
        r"(实验|论文|模型|代码|算法|实现|优化|评测|数据|统计检验|引言|答辩)",
        text,
        re.I,
    ):
        return True
    if re.search(
        r"(实验方案|实验设计|实验记录|论文提纲|评测方案|实现细节|优化方案|统计检验)",
        text,
        re.I,
    ):
        return True
    return False


def _science_mode_from_context(
    user_text: str,
    *,
    previous_user_text: str = "",
    pending_user_goal: str = "",
    previous_assistant_text: str = "",
) -> bool:
    if _science_mode_from_user(user_text):
        return True
    continuity_markers = GENTLE_GUIDANCE_KEYWORDS | NATURAL_REQUEST_KEYWORDS | {"按平时那样", "带我一下", "先别念我"}
    text = str(user_text or "").strip()
    if not _has_any_marker(text, continuity_markers):
        return False
    context_blob = " ".join(
        part
        for part in (
            str(pending_user_goal or "").strip(),
            str(previous_user_text or "").strip(),
        )
        if part
    )
    if _science_mode_from_user(context_blob):
        return True
    # Do not inherit science mode only because the assistant mentioned technical words in its own reply.
    _ = previous_assistant_text
    return False


def _tsundere_next(
    prev: float,
    *,
    emotion_label: str,
    appraisal: dict[str, Any] | None = None,
    bond_state: dict[str, Any] | None = None,
    world_model_state: dict[str, Any] | None = None,
) -> float:
    cur = float(prev)
    app = _engine_normalize_appraisal_payload(appraisal)
    signals = app.get("signals") if isinstance(app.get("signals"), dict) else {}
    bond = dict(bond_state or {})
    world = dict(world_model_state or {})
    closeness = _clamp01(bond.get("closeness"), 0.5)
    hurt = _clamp01(bond.get("hurt"), 0.0)
    tension = _clamp01(world.get("tension_load"), 0.0)
    boundary = _clamp01(world.get("boundary_load"), 0.0)
    if bool(signals.get("care")):
        cur -= 0.06
    if bool(signals.get("repair")):
        cur -= 0.03
    if bool(signals.get("conflict")):
        cur += 0.05
    if emotion_label == "stress":
        cur -= 0.05
    elif emotion_label == "angry":
        cur += 0.07
    elif emotion_label == "hurt":
        cur += 0.03
    elif emotion_label == "care":
        cur -= 0.05
    cur += 0.04 * tension + 0.03 * boundary
    cur -= 0.05 * max(0.0, closeness - 0.62)
    cur += 0.04 * hurt
    return max(0.05, min(0.95, round(cur, 3)))
