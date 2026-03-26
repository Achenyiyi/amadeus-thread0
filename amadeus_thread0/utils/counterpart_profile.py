from __future__ import annotations

from typing import Any


def clamp01(value: Any, default: float = 0.0) -> float:
    try:
        cast = float(value)
    except Exception:
        cast = float(default)
    return max(0.0, min(1.0, cast))


def clamp_signed(value: Any, default: float = 0.0) -> float:
    try:
        cast = float(value)
    except Exception:
        cast = float(default)
    return max(-1.0, min(1.0, cast))


def compact_counterpart_profile(profile: dict[str, Any] | None) -> dict[str, Any]:
    item = profile if isinstance(profile, dict) else {}
    raw_scene_strengths = item.get("scene_strengths") if isinstance(item.get("scene_strengths"), dict) else {}
    normalized = {
        "openness_drive": round(clamp01(item.get("openness_drive"), 0.0), 3),
        "guarded_drive": round(clamp01(item.get("guarded_drive"), 0.0), 3),
        "guard_margin": round(clamp_signed(item.get("guard_margin"), 0.0), 3),
        "dominant_scene_signal": str(item.get("dominant_scene_signal") or "").strip().lower(),
        "scene_strengths": {
            "care": round(clamp01(raw_scene_strengths.get("care"), 0.0), 3),
            "repair": round(clamp01(raw_scene_strengths.get("repair"), 0.0), 3),
            "friction": round(clamp01(raw_scene_strengths.get("friction"), 0.0), 3),
            "selfhood": round(clamp01(raw_scene_strengths.get("selfhood"), 0.0), 3),
            "busy": round(clamp01(raw_scene_strengths.get("busy"), 0.0), 3),
        },
        "safety_read": round(clamp01(item.get("safety_read"), 0.0), 3),
        "repairability": round(clamp01(item.get("repairability"), 0.0), 3),
        "predictability": round(clamp01(item.get("predictability"), 0.0), 3),
        "dependency_risk": round(clamp01(item.get("dependency_risk"), 0.0), 3),
        "closeness_read": round(clamp01(item.get("closeness_read"), 0.0), 3),
    }
    if any(
        (
            normalized["openness_drive"] > 0.0,
            normalized["guarded_drive"] > 0.0,
            abs(normalized["guard_margin"]) > 0.0,
            normalized["dominant_scene_signal"],
            any(score > 0.0 for score in normalized["scene_strengths"].values()),
            normalized["safety_read"] > 0.0,
            normalized["repairability"] > 0.0,
            normalized["predictability"] > 0.0,
            normalized["dependency_risk"] > 0.0,
            normalized["closeness_read"] > 0.0,
        )
    ):
        return normalized
    return {}


def normalize_counterpart_assessment_profile(assessment: dict[str, Any] | None) -> dict[str, Any]:
    item = assessment if isinstance(assessment, dict) else {}
    raw_profile = item.get("assessment_profile") if isinstance(item.get("assessment_profile"), dict) else {}
    stance = str(item.get("stance") or "").strip().lower()
    scene = str(item.get("scene") or "").strip().lower()
    respect = clamp01(item.get("respect_level"), 0.5)
    reciprocity = clamp01(item.get("reciprocity"), 0.5)
    pressure = clamp01(item.get("boundary_pressure"), 0.1)
    reliability = clamp01(item.get("reliability_read"), 0.5)

    derived_scene_strengths = {
        "care": clamp01(
            (0.46 if scene == "care_bid" else 0.0)
            + 0.24 * respect
            + 0.20 * reciprocity
            + 0.12 * reliability
            - 0.10 * pressure
        ),
        "repair": clamp01(
            (0.48 if scene == "repair_attempt" else 0.0)
            + 0.22 * reliability
            + 0.18 * respect
            + 0.08 * reciprocity
            - 0.10 * pressure
        ),
        "friction": clamp01(
            (0.52 if scene in {"friction", "relationship_degradation", "boundary_non_compliance"} else 0.0)
            + 0.30 * pressure
            + 0.10 * clamp01(1.0 - respect, 0.0)
            + 0.08 * clamp01(1.0 - reliability, 0.0)
        ),
        "selfhood": clamp01(
            (0.48 if scene in {"equality_not_servitude", "value_conflict_depth"} else 0.0)
            + 0.18 * pressure
            + 0.08 * clamp01(1.0 - reciprocity, 0.0)
        ),
        "busy": clamp01(
            (0.50 if scene == "busy_not_disrespectful" else 0.0)
            + 0.18 * reliability
            + 0.14 * respect
            + 0.10 * clamp01(1.0 - pressure, 0.0)
        ),
    }
    raw_scene_strengths = raw_profile.get("scene_strengths") if isinstance(raw_profile.get("scene_strengths"), dict) else {}
    scene_strengths = {
        name: clamp01(raw_scene_strengths.get(name), default)
        for name, default in derived_scene_strengths.items()
    }
    openness_drive = clamp01(
        raw_profile.get("openness_drive"),
        0.28 * respect + 0.28 * reciprocity + 0.24 * reliability + 0.20 * clamp01(1.0 - pressure, 0.0),
    )
    guarded_drive = clamp01(
        raw_profile.get("guarded_drive"),
        0.50 * pressure
        + 0.18 * clamp01(1.0 - respect, 0.0)
        + 0.18 * clamp01(1.0 - reliability, 0.0)
        + 0.14 * clamp01(1.0 - reciprocity, 0.0),
    )
    if stance == "guarded":
        guarded_drive = max(guarded_drive, 0.66)
    elif stance == "watchful":
        guarded_drive = max(guarded_drive, 0.46)
    if scene == "care_bid":
        openness_drive = max(openness_drive, 0.62)
    elif scene == "repair_attempt":
        scene_strengths["repair"] = max(scene_strengths["repair"], 0.62)
    elif scene in {"friction", "relationship_degradation", "boundary_non_compliance"}:
        scene_strengths["friction"] = max(scene_strengths["friction"], 0.62)
    elif scene in {"equality_not_servitude", "value_conflict_depth"}:
        scene_strengths["selfhood"] = max(scene_strengths["selfhood"], 0.62)
    elif scene == "busy_not_disrespectful":
        scene_strengths["busy"] = max(scene_strengths["busy"], 0.62)

    dominant_scene_signal = str(raw_profile.get("dominant_scene_signal") or "").strip().lower()
    if dominant_scene_signal not in scene_strengths:
        ranked_scene_signals = sorted(scene_strengths.items(), key=lambda item: (-item[1], item[0]))
        if ranked_scene_signals and ranked_scene_signals[0][1] >= 0.05:
            dominant_scene_signal = ranked_scene_signals[0][0]
        elif scene:
            dominant_scene_signal = scene
        else:
            dominant_scene_signal = ""

    guard_margin = clamp_signed(
        raw_profile.get("guard_margin"),
        guarded_drive - openness_drive,
    )
    closeness_read = clamp01(
        raw_profile.get("closeness_read"),
        0.30 * respect
        + 0.26 * reciprocity
        + 0.16 * scene_strengths["care"]
        + 0.16 * openness_drive
        - 0.12 * pressure
        - 0.08 * scene_strengths["friction"],
    )
    safety_read = clamp01(
        raw_profile.get("safety_read"),
        0.34 * clamp01(1.0 - pressure, 0.0)
        + 0.30 * reliability
        + 0.18 * respect
        + 0.10 * reciprocity
        + 0.08 * scene_strengths["busy"]
        - 0.10 * scene_strengths["friction"],
    )
    repairability = clamp01(
        raw_profile.get("repairability"),
        0.42 * reliability
        + 0.22 * respect
        + 0.16 * reciprocity
        + 0.16 * scene_strengths["repair"]
        - 0.16 * pressure,
    )
    predictability = clamp01(
        raw_profile.get("predictability"),
        0.44 * reliability
        + 0.20 * respect
        + 0.12 * scene_strengths["busy"]
        + 0.10 * scene_strengths["repair"]
        - 0.14 * scene_strengths["friction"]
        - 0.10 * max(0.0, guard_margin),
    )
    dependency_risk = clamp01(
        raw_profile.get("dependency_risk"),
        0.26 * openness_drive
        + 0.20 * closeness_read
        + 0.16 * scene_strengths["care"]
        + 0.14 * clamp01(0.62 - reciprocity, 0.0)
        + 0.12 * clamp01(0.56 - reliability, 0.0)
        + 0.08 * pressure
        + 0.08 * max(0.0, guard_margin),
    )
    return compact_counterpart_profile(
        {
            "openness_drive": openness_drive,
            "guarded_drive": guarded_drive,
            "guard_margin": guard_margin,
            "dominant_scene_signal": dominant_scene_signal,
            "scene_strengths": scene_strengths,
            "safety_read": safety_read,
            "repairability": repairability,
            "predictability": predictability,
            "dependency_risk": dependency_risk,
            "closeness_read": closeness_read,
        }
    )
