from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


def clamp01(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return max(0.0, min(1.0, float(default)))


def clamp_signed(value: Any, low: float = -1.0, high: float = 1.0, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except Exception:
        numeric = float(default)
    return max(float(low), min(float(high), numeric))


def blend(prev: float, target: float, weight: float) -> float:
    return round((1.0 - weight) * clamp01(prev, prev) + weight * clamp01(target, target), 3)


@dataclass
class WorldModelState:
    relationship_maturity: float = 0.5
    bond_depth: float = 0.0
    tension_load: float = 0.0
    repair_load: float = 0.0
    boundary_load: float = 0.0
    selfhood_load: float = 0.0
    agency_load: float = 0.0
    memory_gravity: float = 0.0
    lineage_gravity: float = 0.0
    contact_lineage: float = 0.0
    repair_lineage: float = 0.0
    boundary_lineage: float = 0.0
    selfhood_lineage: float = 0.0
    agency_lineage: float = 0.0
    task_pull: float = 0.0
    companionship_pull: float = 0.0
    presence_residue: float = 0.0
    ambient_resonance: float = 0.0
    self_activity_momentum: float = 0.0
    updated_at: int = 0

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "WorldModelState":
        data = raw if isinstance(raw, dict) else {}
        return cls(
            relationship_maturity=clamp01(data.get("relationship_maturity"), 0.5),
            bond_depth=clamp01(data.get("bond_depth"), 0.0),
            tension_load=clamp01(data.get("tension_load"), 0.0),
            repair_load=clamp01(data.get("repair_load"), 0.0),
            boundary_load=clamp01(data.get("boundary_load"), 0.0),
            selfhood_load=clamp01(data.get("selfhood_load"), 0.0),
            agency_load=clamp01(data.get("agency_load"), 0.0),
            memory_gravity=clamp01(data.get("memory_gravity"), 0.0),
            lineage_gravity=clamp01(data.get("lineage_gravity"), 0.0),
            contact_lineage=clamp01(data.get("contact_lineage"), 0.0),
            repair_lineage=clamp01(data.get("repair_lineage"), 0.0),
            boundary_lineage=clamp01(data.get("boundary_lineage"), 0.0),
            selfhood_lineage=clamp01(data.get("selfhood_lineage"), 0.0),
            agency_lineage=clamp01(data.get("agency_lineage"), 0.0),
            task_pull=clamp01(data.get("task_pull"), 0.0),
            companionship_pull=clamp01(data.get("companionship_pull"), 0.0),
            presence_residue=clamp01(data.get("presence_residue"), 0.0),
            ambient_resonance=clamp01(data.get("ambient_resonance"), 0.0),
            self_activity_momentum=clamp01(data.get("self_activity_momentum"), 0.0),
            updated_at=int(data.get("updated_at") or 0),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvolutionLatentState:
    affect_resonance: float = 0.5
    trust_reservoir: float = 0.5
    attachment_pull: float = 0.5
    self_coherence: float = 0.72
    agency_pressure: float = 0.28
    reflection_drive: float = 0.35
    cognitive_stride: float = 0.58
    expression_freedom: float = 0.62
    updated_at: int = 0
    version: int = 1

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "EvolutionLatentState":
        data = raw if isinstance(raw, dict) else {}
        return cls(
            affect_resonance=clamp01(data.get("affect_resonance"), 0.5),
            trust_reservoir=clamp01(data.get("trust_reservoir"), 0.5),
            attachment_pull=clamp01(data.get("attachment_pull"), 0.5),
            self_coherence=clamp01(data.get("self_coherence"), 0.72),
            agency_pressure=clamp01(data.get("agency_pressure"), 0.28),
            reflection_drive=clamp01(data.get("reflection_drive"), 0.35),
            cognitive_stride=clamp01(data.get("cognitive_stride"), 0.58),
            expression_freedom=clamp01(data.get("expression_freedom"), 0.62),
            updated_at=int(data.get("updated_at") or 0),
            version=max(1, int(data.get("version") or 1)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
