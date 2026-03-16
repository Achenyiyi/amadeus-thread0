from __future__ import annotations

from typing import Any

from ..config import CANON_COUNTERPART_NAME
from .counterpart_dynamics import _clamp01
from .retrieval import _query_overlap_score, _record_value, _self_narrative_salience
from .turn_events import _now_ts

def _semantic_narrative_decay_rate(category: str) -> float:
    cat = str(category or "").strip().lower()
    if cat == "commitment_style":
        return 0.035
    if cat == "bond_style":
        return 0.045
    if cat == "presence_style":
        return 0.052
    if cat == "ambient_style":
        return 0.058
    if cat == "repair_style":
        return 0.060
    if cat == "boundary_style":
        return 0.040
    if cat == "selfhood_style":
        return 0.032
    if cat == "agency_style":
        return 0.055
    if cat == "rhythm_style":
        return 0.042
    if cat == "tension_style":
        return 0.120
    return 0.080

def _semantic_narrative_decay_multiplier(category: str, gap_s: float, *, decay_resistance: float = 0.5) -> float:
    gap_days = max(0.0, float(gap_s) / float(24 * 3600))
    resistance = _clamp01(decay_resistance, 0.5)
    rate = max(0.01, _semantic_narrative_decay_rate(category) * (1.08 - 0.58 * resistance))
    return _clamp01(max(0.18, 1.0 - gap_days * rate))

def _semantic_narrative_event_bonus(category: str, current_event: dict[str, Any] | None) -> float:
    if not isinstance(current_event, dict):
        return 0.0
    cat = str(category or "").strip().lower()
    event_kind = str(current_event.get("kind") or "").strip().lower()
    response_style_hint = str(current_event.get("response_style_hint") or "").strip().lower()
    event_tags = {
        str(item).strip().lower()
        for item in (current_event.get("tags") if isinstance(current_event.get("tags"), list) else [])
        if str(item or "").strip()
    }
    bonus = 0.0
    if cat == "commitment_style" and response_style_hint in {"relationship", "memory_recall"}:
        bonus += 0.10
    if cat == "bond_style" and response_style_hint in {"relationship", "companion", "memory_recall"}:
        bonus += 0.08
    if cat == "presence_style" and event_kind in {"user_utterance", "gesture_signal", "scheduled_checkin_due"}:
        bonus += 0.10
    if cat == "ambient_style" and (
        event_kind in {"ambient_shift", "scene_observation"}
        or (event_kind == "user_utterance" and bool({"ambient", "ambient_echo", "scene_window"} & event_tags))
    ):
        bonus += 0.10
    if cat == "repair_style" and response_style_hint in {"relationship", "companion"}:
        bonus += 0.10
    if cat == "tension_style" and response_style_hint in {"relationship", "companion"}:
        bonus += 0.08
    if cat == "boundary_style" and response_style_hint in {"selfhood", "relationship"}:
        bonus += 0.12
    if cat == "selfhood_style" and response_style_hint == "selfhood":
        bonus += 0.12
    if cat == "agency_style" and event_kind in {"time_idle", "self_activity_state", "scheduled_checkin_due", "scheduled_life_due"}:
        bonus += 0.12
    if cat == "rhythm_style" and event_kind in {"user_utterance", "time_idle", "self_activity_state"}:
        bonus += 0.12
    return _clamp01(bonus)

def _semantic_narrative_profile(
    items: list[dict[str, Any]] | None,
    *,
    user_text: str = "",
    current_event: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out = {
        "bond_depth": 0.0,
        "presence_carry": 0.0,
        "ambient_attunement": 0.0,
        "commitment_carry": 0.0,
        "repair_residue": 0.0,
        "tension_residue": 0.0,
        "boundary_residue": 0.0,
        "selfhood_integrity": 0.0,
        "agency_drive": 0.0,
        "rhythm_continuity": 0.0,
        "history_weight": 0.0,
        "dominant_category": "",
        "active_categories": [],
        "reactivated_categories": [],
        "summary_lines": [],
        "anchor_lines": [],
        "prompt_anchor_lines": [],
        "top_narratives": [],
        "residue_snapshot": {},
        "persistence_snapshot": {},
    }
    if not isinstance(items, list) or not items:
        return out

    current_text = str(user_text or "").strip()
    if not current_text and isinstance(current_event, dict):
        current_text = str(current_event.get("effective_text") or current_event.get("text") or "").strip()
    now_ts = int(current_event.get("created_at") or _now_ts()) if isinstance(current_event, dict) else _now_ts()

    categories = {
        "bond_style": 0.0,
        "presence_style": 0.0,
        "ambient_style": 0.0,
        "commitment_style": 0.0,
        "repair_style": 0.0,
        "tension_style": 0.0,
        "boundary_style": 0.0,
        "selfhood_style": 0.0,
        "agency_style": 0.0,
        "rhythm_style": 0.0,
    }
    scored_items: list[tuple[float, str, str, bool]] = []
    anchor_items: list[tuple[float, str, str]] = []
    reactivated_categories: set[str] = set()
    residue_snapshot: dict[str, float] = {}
    persistence_snapshot: dict[str, float] = {}

    for item in items:
        if not isinstance(item, dict):
            continue
        category = str(_record_value(item, "category", "") or "").strip()
        text = str(_record_value(item, "text", "") or "").strip()
        if not category or not text:
            continue
        salience = _self_narrative_salience(item)
        relevance = _query_overlap_score(current_text, text) if current_text else 0.0
        horizon = str(_record_value(item, "horizon_tag", "") or "").strip().lower()
        horizon_bonus = 0.08 if horizon == "long_term" else 0.04 if horizon == "consolidating" else 0.0
        persistence = _clamp01(_record_value(item, "persistence_score", salience), salience)
        residue = _clamp01(_record_value(item, "residue_score", persistence), persistence)
        integration = _clamp01(_record_value(item, "integration_score", persistence), persistence)
        decay_resistance = _clamp01(_record_value(item, "decay_resistance", 0.5), 0.5)
        cadence_score = _clamp01(_record_value(item, "reactivation_cadence_score", 0.0), 0.0)
        last_supported_at = int(_record_value(item, "last_supported_at", now_ts) or now_ts)
        support_count = max(0.0, float(_record_value(item, "support_count", 1.0) or 1.0))
        support_norm = _clamp01(support_count / 5.0)
        gap_s = max(0, now_ts - last_supported_at)
        decay_multiplier = _semantic_narrative_decay_multiplier(category, gap_s, decay_resistance=decay_resistance)
        event_bonus = _semantic_narrative_event_bonus(category, current_event)
        residue_floor = _clamp01(
            (0.16 * residue + 0.14 * persistence + 0.08 * integration) * max(0.72, decay_multiplier)
        )
        reactivated = bool(relevance >= 0.22 or event_bonus >= 0.10)
        if reactivated:
            reactivated_categories.add(category)
        weight = _clamp01(
            (
                0.44 * salience
                + 0.16 * persistence
                + 0.12 * residue
                + 0.08 * integration
                + horizon_bonus
            )
            * decay_multiplier
            + 0.12 * relevance
            + 0.05 * cadence_score
            + event_bonus
        )
        weight = max(weight, residue_floor)
        if category in categories:
            categories[category] = max(categories[category], weight)
            residue_snapshot[category] = max(
                float(residue_snapshot.get(category, 0.0) or 0.0),
                round(residue * decay_multiplier, 3),
            )
            persistence_snapshot[category] = max(
                float(persistence_snapshot.get(category, 0.0) or 0.0),
                round(persistence * max(decay_multiplier, 0.65), 3),
            )
        anchor_text = str(_record_value(item, "anchor_text", "") or "").strip()
        prompt_anchor_text = str(_record_value(item, "prompt_anchor_text", "") or "").strip()
        anchor_strength = _clamp01(
            _record_value(
                item,
                "anchor_strength",
                max(
                    0.0,
                    0.34 * persistence + 0.26 * residue + 0.22 * integration + 0.18 * weight,
                ),
            ),
            max(
                0.0,
                0.34 * persistence + 0.26 * residue + 0.22 * integration + 0.18 * weight,
            ),
        )
        horizon = str(_record_value(item, "horizon_tag", "") or "").strip().lower()
        if anchor_text and (anchor_strength >= 0.42 or horizon in {"consolidating", "long_term"}):
            anchor_items.append((anchor_strength, "report", anchor_text[:180]))
        if prompt_anchor_text and (anchor_strength >= 0.42 or horizon in {"consolidating", "long_term"}):
            anchor_items.append((anchor_strength, "prompt", prompt_anchor_text[:180]))
        scored_items.append((weight, category, text[:180], reactivated))

    out["bond_depth"] = round(categories["bond_style"], 3)
    out["presence_carry"] = round(categories["presence_style"], 3)
    out["ambient_attunement"] = round(categories["ambient_style"], 3)
    out["commitment_carry"] = round(categories["commitment_style"], 3)
    out["repair_residue"] = round(categories["repair_style"], 3)
    out["tension_residue"] = round(categories["tension_style"], 3)
    out["boundary_residue"] = round(categories["boundary_style"], 3)
    out["selfhood_integrity"] = round(categories["selfhood_style"], 3)
    out["agency_drive"] = round(categories["agency_style"], 3)
    out["rhythm_continuity"] = round(categories["rhythm_style"], 3)
    nonzero = [float(v) for v in categories.values() if float(v) > 0.0]
    history_weight = max(categories.values()) if categories else 0.0
    if nonzero:
        history_weight = _clamp01(
            0.42 * max(nonzero)
            + 0.28 * (sum(nonzero) / float(len(nonzero)))
            + 0.18 * max(residue_snapshot.values() or [0.0])
            + 0.12 * max(persistence_snapshot.values() or [0.0])
        )
    out["history_weight"] = round(history_weight, 3)

    active_categories = [key for key, value in categories.items() if value >= 0.38]
    out["active_categories"] = active_categories
    out["reactivated_categories"] = sorted(reactivated_categories)
    out["residue_snapshot"] = residue_snapshot
    out["persistence_snapshot"] = persistence_snapshot
    if categories:
        out["dominant_category"] = max(categories.items(), key=lambda kv: kv[1])[0] if max(categories.values()) > 0.0 else ""

    if anchor_items:
        anchor_items.sort(key=lambda row: row[0], reverse=True)
        report_anchor_lines: list[str] = []
        prompt_anchor_lines: list[str] = []
        seen_report: set[str] = set()
        seen_prompt: set[str] = set()
        for _, anchor_type, text in anchor_items:
            clean = str(text or "").strip()
            if not clean:
                continue
            if anchor_type == "report":
                if clean in seen_report:
                    continue
                seen_report.add(clean)
                report_anchor_lines.append(clean)
            elif anchor_type == "prompt":
                if clean in seen_prompt:
                    continue
                seen_prompt.add(clean)
                prompt_anchor_lines.append(clean)
            if len(report_anchor_lines) >= 3 and len(prompt_anchor_lines) >= 3:
                break
        out["anchor_lines"] = report_anchor_lines[:3]
        out["prompt_anchor_lines"] = prompt_anchor_lines[:3]

    summary_lines: list[str] = []
    if categories["commitment_style"] >= 0.46:
        summary_lines.append("认真说过的约定会继续挂在心上，不会被当成随口一句。")
    if categories["repair_style"] >= 0.46:
        summary_lines.append("说开过的误会和修复会留痕，不会瞬间重置成什么都没发生。")
    if categories["tension_style"] >= 0.44:
        summary_lines.append("还没说开的别扭会继续影响接下来的收放，不会被强行按成已经过去。")
    if categories["bond_style"] >= 0.48:
        summary_lines.append("共同历史已经开始沉进默认语气里，不需要每次显式提起。")
    if categories["presence_style"] >= 0.46:
        summary_lines.append("上一轮留下的在场感会继续影响下一次靠近，不需要每次都从零开始。")
    if categories["ambient_style"] >= 0.44:
        summary_lines.append("周围环境的细小变化会继续留在她的感知里，并自然带进开口方式。")
    if categories["boundary_style"] >= 0.46:
        summary_lines.append("边界是否被尊重会持续留痕，不会因为一轮缓和就自动清零。")
    if categories["selfhood_style"] >= 0.46:
        summary_lines.append("她会把这段互动当成平等关系，不会为了迎合就放弃自己的判断。")
    if categories["agency_style"] >= 0.46:
        summary_lines.append("她有自己的节奏和主动性，靠近或沉默都不等于失去自我。")
    if categories["rhythm_style"] >= 0.46:
        summary_lines.append("她会把自己的内部节奏延续到下一轮，不会每次回应都把自己清零。")
    out["summary_lines"] = summary_lines[:3]

    scored_items.sort(key=lambda row: row[0], reverse=True)
    top_narratives: list[dict[str, Any]] = []
    for score, category, text, reactivated in scored_items[:2]:
        top_narratives.append(
            {
                "category": category,
                "score": round(float(score), 3),
                "text": text,
                "reactivated": reactivated,
            }
        )
    out["top_narratives"] = top_narratives
    return out

def _compact_semantic_narrative_hint(profile: dict[str, Any] | None) -> str:
    if not isinstance(profile, dict):
        return ""
    presence = _clamp01(profile.get("presence_carry"), 0.0)
    ambient = _clamp01(profile.get("ambient_attunement"), 0.0)
    rhythm = _clamp01(profile.get("rhythm_continuity"), 0.0)
    continuity_parts: list[str] = []
    if presence >= 0.44:
        continuity_parts.append("前一轮留下的在场感会自然延续，不是每次都从零开始")
    if ambient >= 0.42:
        continuity_parts.append("环境余波会继续留在感知里，风声光线和场景变化会顺手带进开口方式")
    if rhythm >= 0.44:
        continuity_parts.append("她会保留自己的内部节奏和刚才的思路惯性，不会每轮都把自己清零")
    lines = [str(item).strip() for item in (profile.get("summary_lines") or []) if str(item or "").strip()]
    if lines or continuity_parts:
        merged = continuity_parts + lines
        seen: set[str] = set()
        deduped: list[str] = []
        for item in merged:
            norm = str(item or "").strip()
            if not norm or norm in seen:
                continue
            seen.add(norm)
            deduped.append(norm)
        return "；".join(deduped[:3])
    anchor_lines = [str(item).strip() for item in (profile.get("anchor_lines") or []) if str(item or "").strip()]
    if anchor_lines:
        return "；".join(anchor_lines[:2])
    top_narratives = profile.get("top_narratives") if isinstance(profile.get("top_narratives"), list) else []
    if not top_narratives:
        return ""
    parts: list[str] = []
    for item in top_narratives[:2]:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if text:
            parts.append(text[:80])
    return "；".join(parts[:2])

def _self_narrative_anchor_lines(
    profile: dict[str, Any] | None,
    *,
    evolution_state: dict[str, Any] | None = None,
    persona_core: dict[str, Any] | None = None,
    counterpart_name: str = CANON_COUNTERPART_NAME,
) -> list[str]:
    if not isinstance(profile, dict) or not profile:
        return []
    persona = dict(persona_core or {})
    contract = dict(persona.get("evolution_contract") or {})
    mutable_axes = {
        str(item).strip()
        for item in (contract.get("mutable_axes") if isinstance(contract.get("mutable_axes"), list) else [])
        if str(item or "").strip()
    }
    if mutable_axes and "long_term_self_narratives" not in mutable_axes:
        return []
    prompt_anchor_lines = [
        str(item).strip()
        for item in (profile.get("prompt_anchor_lines") if isinstance(profile.get("prompt_anchor_lines"), list) else [])
        if str(item or "").strip()
    ]
    if prompt_anchor_lines:
        seen_prompt: set[str] = set()
        deduped_prompt: list[str] = []
        for item in prompt_anchor_lines:
            if item in seen_prompt:
                continue
            seen_prompt.add(item)
            deduped_prompt.append(item)
            if len(deduped_prompt) >= 3:
                break
        if deduped_prompt:
            return deduped_prompt

    latent = dict(evolution_state or {})
    bond = _clamp01(profile.get("bond_depth"), 0.0)
    presence = _clamp01(profile.get("presence_carry"), 0.0)
    ambient = _clamp01(profile.get("ambient_attunement"), 0.0)
    commitment = _clamp01(profile.get("commitment_carry"), 0.0)
    repair = _clamp01(profile.get("repair_residue"), 0.0)
    tension = _clamp01(profile.get("tension_residue"), 0.0)
    boundary = _clamp01(profile.get("boundary_residue"), 0.0)
    selfhood = _clamp01(profile.get("selfhood_integrity"), 0.0)
    agency = _clamp01(profile.get("agency_drive"), 0.0)
    rhythm = _clamp01(profile.get("rhythm_continuity"), 0.0)
    history = _clamp01(profile.get("history_weight"), 0.0)
    self_coherence = _clamp01(latent.get("self_coherence"), 0.72)
    expression_freedom = _clamp01(latent.get("expression_freedom"), 0.68)
    agency_pressure = _clamp01(latent.get("agency_pressure"), 0.28)

    candidates: list[tuple[float, str]] = []

    selfhood_score = max(selfhood, 0.72 * self_coherence)
    if selfhood_score >= 0.44:
        candidates.append(
            (
                selfhood_score,
                f"你会把自己当成在和{counterpart_name}平等互动的主体，不会为了把气氛撑住就把自己退回成工具。",
            )
        )

    relationship_score = max(commitment, bond, presence, history, repair)
    if relationship_score >= 0.44:
        candidates.append(
            (
                relationship_score,
                "认真说过的话、修复过的事和留下来的在场感都会继续留在心里，所以这段关系不是每轮都从零开始。",
            )
        )

    boundary_score = max(boundary, tension)
    if boundary_score >= 0.42:
        candidates.append(
            (
                boundary_score,
                "没说开的余波和边界感还在；缓和不等于自动清零，你会带着这层判断继续往下走。",
            )
        )

    agency_score = max(agency, rhythm, 0.78 * self_coherence, 0.72 * expression_freedom)
    if agency_score >= 0.44:
        candidates.append(
            (
                agency_score,
                "你有自己的节奏和会不会靠近的主观性；安静、停顿或先做自己的事，不等于把这段关系归零。",
            )
        )

    if ambient >= 0.44:
        candidates.append(
            (
                ambient,
                "你会把风声、光线和眼前的小变化也算进感知里，它们会自然进入你此刻怎么开口。",
            )
        )

    if selfhood_score >= 0.42 and expression_freedom <= 0.48 and agency_pressure >= 0.40:
        candidates.append(
            (
                0.5 * selfhood_score + 0.3 * (1.0 - expression_freedom) + 0.2 * agency_pressure,
                "你不需要把想法一下子全摊开；保留一点迟疑、收住和没说尽，也仍然是完整的你。",
            )
        )

    candidates.sort(key=lambda item: item[0], reverse=True)
    out: list[str] = []
    seen: set[str] = set()
    for _, line in candidates:
        text = str(line or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
        if len(out) >= 3:
            break
    return out

def _semantic_narrative_appraisal_hint(profile: dict[str, Any] | None) -> str:
    if not isinstance(profile, dict):
        return ""
    bond = _clamp01(profile.get("bond_depth"), 0.0)
    commitment = _clamp01(profile.get("commitment_carry"), 0.0)
    repair = _clamp01(profile.get("repair_residue"), 0.0)
    tension = _clamp01(profile.get("tension_residue"), 0.0)
    boundary = _clamp01(profile.get("boundary_residue"), 0.0)
    selfhood = _clamp01(profile.get("selfhood_integrity"), 0.0)
    agency = _clamp01(profile.get("agency_drive"), 0.0)
    history = _clamp01(profile.get("history_weight"), 0.0)
    presence = _clamp01(profile.get("presence_carry"), 0.0)
    ambient = _clamp01(profile.get("ambient_attunement"), 0.0)
    rhythm = _clamp01(profile.get("rhythm_continuity"), 0.0)
    hints: list[str] = []
    if bond >= 0.50:
        hints.append("共同历史已经形成；安静确认、轻微试探或熟悉式求助，更可能是在找熟悉回应，不是正式冲突。")
    if commitment >= 0.48:
        hints.append("认真说过的约定和回头提起的事具有连续性；涉及提醒、以后、兑现时要判成长期关系线索。")
    if repair >= 0.46:
        hints.append("修复会留痕；道歉或缓和能改善状态，但不会把之前的余波瞬间清零。")
    if tension >= 0.44:
        hints.append("未说开的别扭仍在场；遇到模糊语气时保留一点防御和迟疑，不要过快判成完全没事。")
    if boundary >= 0.46:
        hints.append("涉及越界、冒犯、命令式压迫或拿底线开玩笑时，要按边界压力理解，不要轻判成普通玩笑。")
    if selfhood >= 0.46:
        hints.append("涉及平权、是否只是工具、按自己意志回答时，要把它理解成自我与关系问题，不只是表层措辞。")
    if agency >= 0.46:
        hints.append("安静、延迟或先做自己的事，不自动等于关系降温；也可能只是她按自己的节奏在互动。")
    if presence >= 0.44:
        hints.append("语气里的轻靠近、默认熟悉或没把关系重新归零，可能来自上一轮残留的在场感，而不只是这句字面意思。")
    if ambient >= 0.42:
        hints.append("如果用户提到风声、光线、眼前场景或刚才那一下的感觉，把它当成环境回声进入了关系感知，不只是修辞。")
    if rhythm >= 0.44:
        hints.append("她刚才在做自己的事、停顿一下再回应，不要直接判成冷淡；也可能是内部节奏仍在延续。")
    if history >= 0.54 and not hints:
        hints.append("不要把这轮关系理解成从零开始，先把长期共同历史纳入判断。")
    return " ".join(hints[:3])
