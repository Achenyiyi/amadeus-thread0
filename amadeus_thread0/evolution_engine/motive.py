from __future__ import annotations

from typing import Any

from .schemas import clamp01


def semantic_motive_vector(profile: dict[str, Any] | None) -> dict[str, Any]:
    narrative = dict(profile or {})
    motive_snapshot = narrative.get("motive_snapshot") if isinstance(narrative.get("motive_snapshot"), dict) else {}
    residue_snapshot = narrative.get("residue_snapshot") if isinstance(narrative.get("residue_snapshot"), dict) else {}
    persistence_snapshot = narrative.get("persistence_snapshot") if isinstance(narrative.get("persistence_snapshot"), dict) else {}
    axis_values = {
        "bond_style": max(
            clamp01(narrative.get("bond_depth"), 0.0),
            clamp01(residue_snapshot.get("bond_style"), 0.0),
            0.72 * clamp01(persistence_snapshot.get("bond_style"), 0.0),
        ),
        "boundary_style": max(
            clamp01(narrative.get("boundary_residue"), 0.0),
            clamp01(residue_snapshot.get("boundary_style"), 0.0),
            0.72 * clamp01(persistence_snapshot.get("boundary_style"), 0.0),
        ),
        "commitment_style": max(
            clamp01(narrative.get("commitment_carry"), 0.0),
            clamp01(residue_snapshot.get("commitment_style"), 0.0),
            0.72 * clamp01(persistence_snapshot.get("commitment_style"), 0.0),
        ),
        "selfhood_style": max(
            clamp01(narrative.get("selfhood_integrity"), 0.0),
            clamp01(residue_snapshot.get("selfhood_style"), 0.0),
            0.72 * clamp01(persistence_snapshot.get("selfhood_style"), 0.0),
        ),
        "agency_style": max(
            clamp01(narrative.get("agency_drive"), 0.0),
            clamp01(residue_snapshot.get("agency_style"), 0.0),
            0.72 * clamp01(persistence_snapshot.get("agency_style"), 0.0),
        ),
        "presence_style": max(
            clamp01(narrative.get("presence_carry"), 0.0),
            clamp01(residue_snapshot.get("presence_style"), 0.0),
            0.72 * clamp01(persistence_snapshot.get("presence_style"), 0.0),
        ),
        "ambient_style": max(
            clamp01(narrative.get("ambient_attunement"), 0.0),
            clamp01(residue_snapshot.get("ambient_style"), 0.0),
            0.72 * clamp01(persistence_snapshot.get("ambient_style"), 0.0),
        ),
        "repair_style": max(
            clamp01(narrative.get("repair_residue"), 0.0),
            clamp01(residue_snapshot.get("repair_style"), 0.0),
            0.72 * clamp01(persistence_snapshot.get("repair_style"), 0.0),
        ),
        "rhythm_style": max(
            clamp01(narrative.get("rhythm_continuity"), 0.0),
            clamp01(residue_snapshot.get("rhythm_style"), 0.0),
            0.72 * clamp01(persistence_snapshot.get("rhythm_style"), 0.0),
        ),
        "tension_style": max(
            clamp01(narrative.get("tension_residue"), 0.0),
            clamp01(residue_snapshot.get("tension_style"), 0.0),
            0.72 * clamp01(persistence_snapshot.get("tension_style"), 0.0),
        ),
    }
    vector = {
        "boundary_pull": 0.0,
        "self_rhythm_pull": 0.0,
        "continuity_pull": 0.0,
        "memory_pull": 0.0,
        "support_pull": 0.0,
        "shared_window_pull": 0.0,
        "dominant_primary_motive": "",
        "dominant_primary_category": "",
        "dominant_primary_strength": 0.0,
        "dominant_goal_frame": "",
        "dominant_motive_tension": "",
        "dominant_tension_category": "",
        "dominant_tension_strength": 0.0,
    }
    motive_rankings: list[tuple[float, str, str, str]] = []
    tension_rankings: list[tuple[float, str, str]] = []

    for category, raw in motive_snapshot.items():
        if not isinstance(raw, dict):
            continue
        category_key = str(category or "").strip()
        strength = clamp01(axis_values.get(category_key, 0.0), 0.0)
        if strength <= 0.0:
            continue
        primary_motive = str(raw.get("primary_motive") or "").strip().lower()
        motive_tension = str(raw.get("motive_tension") or "").strip().lower()
        goal_frame_examples = [
            str(item).strip()
            for item in (raw.get("goal_frame_examples") or [])
            if str(item or "").strip()
        ]
        if primary_motive:
            motive_rankings.append((strength, primary_motive, category_key, goal_frame_examples[0] if goal_frame_examples else ""))
        if motive_tension:
            tension_rankings.append((strength, motive_tension, category_key))

        if primary_motive == "protect_boundary":
            vector["boundary_pull"] = max(float(vector["boundary_pull"]), 1.00 * strength)
        elif primary_motive == "preserve_self_rhythm":
            vector["self_rhythm_pull"] = max(float(vector["self_rhythm_pull"]), 0.96 * strength)
        elif primary_motive == "gentle_recontact":
            vector["continuity_pull"] = max(float(vector["continuity_pull"]), 0.80 * strength)
            vector["self_rhythm_pull"] = max(float(vector["self_rhythm_pull"]), 0.28 * strength)
        elif primary_motive == "confirm_presence":
            vector["continuity_pull"] = max(float(vector["continuity_pull"]), 0.60 * strength)
            vector["support_pull"] = max(float(vector["support_pull"]), 0.52 * strength)
        elif primary_motive == "support_without_pressure":
            vector["support_pull"] = max(float(vector["support_pull"]), 0.90 * strength)
            vector["continuity_pull"] = max(float(vector["continuity_pull"]), 0.38 * strength)
        elif primary_motive == "honor_continuity":
            vector["continuity_pull"] = max(float(vector["continuity_pull"]), 0.92 * strength)
            vector["self_rhythm_pull"] = max(float(vector["self_rhythm_pull"]), 0.34 * strength)
            vector["memory_pull"] = max(float(vector["memory_pull"]), 0.42 * strength)
        elif primary_motive == "reconnect_shared_history":
            vector["continuity_pull"] = max(float(vector["continuity_pull"]), 0.82 * strength)
            vector["memory_pull"] = max(float(vector["memory_pull"]), 0.88 * strength)
        elif primary_motive == "open_shared_window":
            vector["shared_window_pull"] = max(float(vector["shared_window_pull"]), 0.86 * strength)
            vector["continuity_pull"] = max(float(vector["continuity_pull"]), 0.34 * strength)
        elif primary_motive == "maintain_natural_contact":
            vector["continuity_pull"] = max(float(vector["continuity_pull"]), 0.34 * strength)

        if motive_tension == "self_rhythm_vs_contact":
            vector["self_rhythm_pull"] = max(float(vector["self_rhythm_pull"]), 0.40 * strength)
        elif motive_tension == "boundary_vs_closeness":
            vector["boundary_pull"] = max(float(vector["boundary_pull"]), 0.42 * strength)
        elif motive_tension == "past_vs_present":
            vector["memory_pull"] = max(float(vector["memory_pull"]), 0.42 * strength)
            vector["continuity_pull"] = max(float(vector["continuity_pull"]), 0.24 * strength)
        elif motive_tension == "space_vs_contact":
            vector["continuity_pull"] = max(float(vector["continuity_pull"]), 0.28 * strength)
        elif motive_tension == "care_vs_guard":
            vector["support_pull"] = max(float(vector["support_pull"]), 0.34 * strength)

    for key in ("boundary_pull", "self_rhythm_pull", "continuity_pull", "memory_pull", "support_pull", "shared_window_pull"):
        vector[key] = round(clamp01(vector[key], 0.0), 3)

    if motive_rankings:
        primary_strength, primary_motive, primary_category, primary_goal_frame = max(motive_rankings, key=lambda item: item[0])
        vector["dominant_primary_motive"] = primary_motive
        vector["dominant_primary_category"] = primary_category
        vector["dominant_primary_strength"] = round(clamp01(primary_strength, 0.0), 3)
        vector["dominant_goal_frame"] = primary_goal_frame
    if tension_rankings:
        tension_strength, motive_tension, tension_category = max(tension_rankings, key=lambda item: item[0])
        vector["dominant_motive_tension"] = motive_tension
        vector["dominant_tension_category"] = tension_category
        vector["dominant_tension_strength"] = round(clamp01(tension_strength, 0.0), 3)
    return vector
