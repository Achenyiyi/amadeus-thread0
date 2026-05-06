# Amadeus-K Product Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a clean backend product layer under `apps/amadeus_k/` that adapts the existing Amadeus research backend into a stable frontend contract for a real virtual digital persona product.

**Architecture:** Keep `amadeus_thread0/` as the research backend and capability source. Add a small product package with dataclass schemas, deterministic avatar-state derivation, capability reporting, adapter functions over `BackendAPI` envelopes, pure Python service entry points, TypeScript contract files, examples, and thesis/demo docs. Avoid frontend implementation and avoid new runtime dependencies.

**Tech Stack:** Python 3, dataclasses, existing `amadeus_thread0.runtime` entry points, pytest, TypeScript declaration file for frontend consumers, JSON example fixtures.

---

## File Structure

Create:

- `apps/__init__.py`  
  Marks `apps` as an importable namespace for tests and product modules.

- `apps/amadeus_k/__init__.py`  
  Product package marker with exported schema version.

- `apps/amadeus_k/README.md`  
  Short product-core overview and run/test pointers.

- `apps/amadeus_k/backend/__init__.py`  
  Backend package exports.

- `apps/amadeus_k/backend/schemas.py`  
  Dataclass schemas and dict serialization helpers for all product envelopes.

- `apps/amadeus_k/backend/capabilities.py`  
  Stable capability readiness table and environment-aware TTS status.

- `apps/amadeus_k/backend/avatar_state.py`  
  Deterministic mapping from product/backend state to frontend avatar hints.

- `apps/amadeus_k/backend/adapter.py`  
  Adapter from existing `BackendApiEnvelope` / backend payload dictionaries into product envelopes.

- `apps/amadeus_k/backend/app.py`  
  Pure Python product service facade with `health()`, `bootstrap()`, `turn_from_backend_envelope()`, and optional runtime-backed `turn()`.

- `apps/amadeus_k/contracts/amadeus_k_api.types.ts`  
  Frontend-facing TypeScript contract.

- `apps/amadeus_k/contracts/examples/bootstrap.response.json`

- `apps/amadeus_k/contracts/examples/turn.response.json`

- `apps/amadeus_k/contracts/examples/approval_pending.response.json`

- `apps/amadeus_k/contracts/examples/capabilities.response.json`

- `apps/amadeus_k/docs/FRONTEND_CONTRACT.md`

- `apps/amadeus_k/docs/PRODUCT_BOUNDARY.md`

- `apps/amadeus_k/docs/DEMO_SCRIPT.md`

- `tests/test_amadeus_k_avatar_state.py`

- `tests/test_amadeus_k_contracts.py`

- `tests/test_amadeus_k_adapter.py`

Modify:

- `program.md`  
  Add final run entry after implementation and validation.

Do not modify:

- `amadeus_thread0/` internals, unless a product adapter cannot be built without a tiny compatibility export. The current design should not need internal edits.
- `frontend/`, because the user explicitly asked not to touch frontend implementation.
- `docker/sandbox_phase2/Dockerfile` tracked deletion state, unless the user separately asks to reconcile the dirty worktree.

---

## Task 1: Product Package Skeleton

**Files:**

- Create: `apps/__init__.py`
- Create: `apps/amadeus_k/__init__.py`
- Create: `apps/amadeus_k/README.md`
- Create: `apps/amadeus_k/backend/__init__.py`

- [ ] **Step 1: Create package markers**

Create `apps/__init__.py`:

```python
"""Product-facing application packages for Amadeus deliverables."""
```

Create `apps/amadeus_k/__init__.py`:

```python
"""Amadeus-K product core package."""

SCHEMA_VERSION = "amadeus-k.product.v1"

__all__ = ["SCHEMA_VERSION"]
```

Create `apps/amadeus_k/backend/__init__.py`:

```python
"""Backend product-core adapters and schemas for Amadeus-K."""
```

- [ ] **Step 2: Create README**

Create `apps/amadeus_k/README.md`:

```markdown
# Amadeus-K Product Core

This package is the backend product layer for the graduation-design deliverable.

It does not replace the research backend in `amadeus_thread0/`. Instead, it adapts stable runtime outputs into a smaller frontend-facing contract:

- final assistant text
- TTS text
- Live2D-ready avatar state
- memory and relationship views
- autonomy and approval views
- digital-body capability state
- product capability readiness

The package intentionally contains no frontend implementation. Frontend code should consume `contracts/amadeus_k_api.types.ts` and the JSON examples under `contracts/examples/`.

## Validation

Run the product-core tests:

```powershell
python -m pytest tests/test_amadeus_k_avatar_state.py tests/test_amadeus_k_contracts.py tests/test_amadeus_k_adapter.py -q
```
```

- [ ] **Step 3: Run import check**

Run:

```powershell
python - <<'PY'
import apps.amadeus_k as product
print(product.SCHEMA_VERSION)
PY
```

Expected output:

```text
amadeus-k.product.v1
```

- [ ] **Step 4: Stage only skeleton files when ready**

Run:

```powershell
git add apps/__init__.py apps/amadeus_k/__init__.py apps/amadeus_k/README.md apps/amadeus_k/backend/__init__.py
```

Do not stage unrelated tracked deletions currently present in the worktree.

---

## Task 2: Product Schemas

**Files:**

- Create: `apps/amadeus_k/backend/schemas.py`
- Test: `tests/test_amadeus_k_contracts.py`

- [ ] **Step 1: Write failing schema tests**

Create `tests/test_amadeus_k_contracts.py` with these initial tests:

```python
from __future__ import annotations

from apps.amadeus_k.backend.schemas import (
    SCHEMA_VERSION,
    ApprovalView,
    AvatarState,
    ProductTurnEnvelope,
    dict_without_none,
)


def test_turn_envelope_serializes_required_frontend_fields():
    envelope = ProductTurnEnvelope(
        thread_id="thread-test",
        turn_id="turn-1",
        user_text="你还记得我昨天说什么了吗？",
        final_text="当然记得。你以为我会随便丢掉这种信息吗？",
        tts_text="当然记得。你以为我会随便丢掉这种信息吗？",
        avatar_state=AvatarState(emotion="smile", motion="speaking", speaking=True, intensity=0.7),
    )

    data = envelope.to_dict()

    assert data["schema_version"] == SCHEMA_VERSION
    assert data["kind"] == "turn"
    assert data["thread_id"] == "thread-test"
    assert data["final_text"] == data["tts_text"]
    assert data["avatar_state"]["emotion"] == "smile"
    assert "memory_view" in data
    assert "relationship_view" in data
    assert "autonomy" in data
    assert "digital_body" in data


def test_approval_view_reports_empty_state():
    approval = ApprovalView()

    data = approval.to_dict()

    assert data["has_pending"] is False
    assert data["proposal_id"] == ""
    assert data["risk"] == ""


def test_dict_without_none_keeps_false_and_zero():
    data = dict_without_none({"a": None, "b": False, "c": 0, "d": ""})

    assert data == {"b": False, "c": 0, "d": ""}
```

- [ ] **Step 2: Run schema tests to verify failure**

Run:

```powershell
python -m pytest tests/test_amadeus_k_contracts.py -q
```

Expected: FAIL because `apps.amadeus_k.backend.schemas` does not exist.

- [ ] **Step 3: Implement dataclass schemas**

Create `apps/amadeus_k/backend/schemas.py`:

```python
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Literal

SCHEMA_VERSION = "amadeus-k.product.v1"

AvatarEmotion = Literal[
    "neutral",
    "smile",
    "sad",
    "surprised",
    "angry",
    "blush",
    "thinking",
    "approval_wait",
]

AvatarMotion = Literal[
    "idle",
    "tap_body",
    "thinking",
    "approval_wait",
    "speaking",
]

CapabilityStatus = Literal["ready", "experimental", "blocked", "unavailable"]


def now_ts() -> int:
    return int(time.time())


def dict_without_none(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


def _serialize(value: Any) -> Any:
    if is_dataclass(value):
        if hasattr(value, "to_dict"):
            return value.to_dict()
        return {key: _serialize(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    return value


@dataclass(frozen=True)
class AvatarState:
    emotion: AvatarEmotion = "neutral"
    motion: AvatarMotion = "idle"
    speaking: bool = False
    intensity: float = 0.0
    reason: str = ""
    suggested_expression: str = "Normal"
    suggested_motion_group: str = "Idle"

    def to_dict(self) -> dict[str, Any]:
        intensity = max(0.0, min(1.0, float(self.intensity)))
        return {
            "emotion": self.emotion,
            "motion": self.motion,
            "speaking": bool(self.speaking),
            "intensity": intensity,
            "reason": str(self.reason or ""),
            "suggested_expression": str(self.suggested_expression or ""),
            "suggested_motion_group": str(self.suggested_motion_group or ""),
        }


@dataclass(frozen=True)
class MemoryView:
    summary: str = ""
    recent_continuity: list[str] = field(default_factory=list)
    writeback_happened: bool = False
    writeback_preview: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self))


@dataclass(frozen=True)
class RelationshipView:
    summary: str = ""
    stance: str = ""
    bond_label: str = ""
    continuity_preview: list[str] = field(default_factory=list)
    unresolved_tension_count: int = 0
    commitment_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self))


@dataclass(frozen=True)
class AutonomyView:
    mode: str = "idle"
    reason: str = ""
    primary_proposal_id: str = ""
    pending: dict[str, Any] = field(default_factory=dict)
    action_packets: list[dict[str, Any]] = field(default_factory=list)
    execution_trace: list[dict[str, Any]] = field(default_factory=list)
    block_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self))


@dataclass(frozen=True)
class ApprovalView:
    has_pending: bool = False
    proposal_id: str = ""
    kind: str = ""
    message: str = ""
    risk: str = ""
    required_action: str = ""
    preview: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self))


@dataclass(frozen=True)
class DigitalBodyView:
    active_surface: str = ""
    access_mode: str = ""
    world_surfaces: list[str] = field(default_factory=list)
    filesystem_state: str = ""
    browser_state: dict[str, Any] = field(default_factory=dict)
    sandbox_state: dict[str, Any] = field(default_factory=dict)
    skill_state: dict[str, Any] = field(default_factory=dict)
    workspace_root: str = ""
    last_run: dict[str, Any] = field(default_factory=dict)
    experimental_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self))


@dataclass(frozen=True)
class CapabilityView:
    id: str
    label: str
    status: CapabilityStatus
    description: str
    evidence: list[str] = field(default_factory=list)
    frontend_visible: bool = True

    def to_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self))


@dataclass(frozen=True)
class DiagnosticsView:
    backend_schema_version: str = ""
    raw_backend_kind: str = ""
    warnings: list[str] = field(default_factory=list)
    trace_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self))


@dataclass(frozen=True)
class ProductBootstrapEnvelope:
    thread_id: str
    persona: dict[str, Any] = field(default_factory=dict)
    session: dict[str, Any] = field(default_factory=dict)
    capabilities: list[CapabilityView] = field(default_factory=list)
    frontend_hints: dict[str, Any] = field(default_factory=dict)
    generated_at: int = field(default_factory=now_ts)
    schema_version: str = SCHEMA_VERSION
    kind: str = "bootstrap"

    def to_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self))


@dataclass(frozen=True)
class ProductTurnEnvelope:
    thread_id: str
    turn_id: str
    user_text: str
    final_text: str
    tts_text: str
    avatar_state: AvatarState
    memory_view: MemoryView = field(default_factory=MemoryView)
    relationship_view: RelationshipView = field(default_factory=RelationshipView)
    autonomy: AutonomyView = field(default_factory=AutonomyView)
    approvals: ApprovalView = field(default_factory=ApprovalView)
    digital_body: DigitalBodyView = field(default_factory=DigitalBodyView)
    capabilities: list[CapabilityView] = field(default_factory=list)
    diagnostics: DiagnosticsView = field(default_factory=DiagnosticsView)
    generated_at: int = field(default_factory=now_ts)
    schema_version: str = SCHEMA_VERSION
    kind: str = "turn"

    def to_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self))
```

- [ ] **Step 4: Run schema tests**

Run:

```powershell
python -m pytest tests/test_amadeus_k_contracts.py -q
```

Expected: PASS for the three tests.

- [ ] **Step 5: Stage schema files**

Run:

```powershell
git add apps/amadeus_k/backend/schemas.py tests/test_amadeus_k_contracts.py
```

Do not stage unrelated tracked deletions.

---

## Task 3: Capability Reporting

**Files:**

- Create: `apps/amadeus_k/backend/capabilities.py`
- Modify: `tests/test_amadeus_k_contracts.py`

- [ ] **Step 1: Add capability tests**

Append to `tests/test_amadeus_k_contracts.py`:

```python
from apps.amadeus_k.backend.capabilities import build_capability_views


def test_capabilities_mark_phase2_as_experimental():
    capabilities = {item.id: item for item in build_capability_views(env={})}

    assert capabilities["dialogue_core"].status == "ready"
    assert capabilities["sandbox_phase2_docker"].status == "experimental"
    assert capabilities["live2d_frontend"].status == "unavailable"


def test_tts_capability_reflects_environment():
    enabled = {item.id: item for item in build_capability_views(env={"AMADEUS_TTS_ENABLED": "1"})}
    disabled = {item.id: item for item in build_capability_views(env={"AMADEUS_TTS_ENABLED": ""})}

    assert enabled["tts"].status == "ready"
    assert disabled["tts"].status == "unavailable"
```

- [ ] **Step 2: Run capability tests to verify failure**

Run:

```powershell
python -m pytest tests/test_amadeus_k_contracts.py -q
```

Expected: FAIL because `apps.amadeus_k.backend.capabilities` does not exist.

- [ ] **Step 3: Implement capability builder**

Create `apps/amadeus_k/backend/capabilities.py`:

```python
from __future__ import annotations

import os
from typing import Any

from .schemas import CapabilityView


def _env_value(env: dict[str, str] | None, key: str) -> str:
    source = env if isinstance(env, dict) else os.environ
    return str(source.get(key) or "").strip()


def _tts_status(env: dict[str, str] | None = None) -> str:
    enabled = _env_value(env, "AMADEUS_TTS_ENABLED").lower()
    return "ready" if enabled in {"1", "true", "yes", "on"} else "unavailable"


def build_capability_views(env: dict[str, str] | None = None) -> list[CapabilityView]:
    tts_status = _tts_status(env)
    rows: list[dict[str, Any]] = [
        {
            "id": "dialogue_core",
            "label": "Dialogue Core",
            "status": "ready",
            "description": "LangGraph-backed turn loop for persona response generation.",
            "evidence": ["BackendAPI.build_turn_response", "BackendSession.invoke_stream"],
        },
        {
            "id": "long_term_memory",
            "label": "Long-Term Memory",
            "status": "ready",
            "description": "Unified memory substrate for continuity and writeback traces.",
            "evidence": ["MemoryStore", "writeback_trace"],
        },
        {
            "id": "relationship_continuity",
            "label": "Relationship Continuity",
            "status": "ready",
            "description": "Relationship, counterpart assessment, and proactive continuity read models.",
            "evidence": ["BackendSession.bond_view", "BackendSession.worldline_view"],
        },
        {
            "id": "autonomy_action_packets",
            "label": "Autonomy Action Packets",
            "status": "ready",
            "description": "Structured action packet envelope with pending/completed/blocked/rejected semantics.",
            "evidence": ["autonomy.action_packets", "autonomy.pending_approval"],
        },
        {
            "id": "approval_gate",
            "label": "Approval Gate",
            "status": "ready",
            "description": "Human-in-the-loop approval state for memory/tool/body mutations.",
            "evidence": ["ToolApprovalRequest", "ApprovalView"],
        },
        {
            "id": "digital_body_state",
            "label": "Digital Body State",
            "status": "ready",
            "description": "Unified body/access/resource state for files, browser, skills, and sandbox surfaces.",
            "evidence": ["digital_body", "digital_body_consequence"],
        },
        {
            "id": "skills_ecosystem",
            "label": "Skills Ecosystem",
            "status": "ready",
            "description": "Managed skills registry and activation envelope preserved from the research backend.",
            "evidence": ["skills_ecosystem_ready"],
        },
        {
            "id": "live_browser_runtime",
            "label": "Live Browser Runtime",
            "status": "ready",
            "description": "Bounded Playwright browser runtime preserved as a backend baseline.",
            "evidence": ["live_browser_runtime_phase1_ready"],
        },
        {
            "id": "sandbox_phase1",
            "label": "Sandbox Phase 1",
            "status": "ready",
            "description": "Host-local restricted execution preserved as compatibility baseline.",
            "evidence": ["sandbox_embodied_execution_phase1_ready"],
        },
        {
            "id": "sandbox_phase2_docker",
            "label": "Sandbox Phase 2 Docker",
            "status": "experimental",
            "description": "Docker-isolated execution is active research work and not a preserved product baseline.",
            "evidence": ["sandbox_embodied_execution_phase2_in_progress"],
        },
        {
            "id": "tts",
            "label": "TTS",
            "status": tts_status,
            "description": "Speech output surface. Product contract keeps `tts_text` aligned with `final_text`.",
            "evidence": ["AMADEUS_TTS_ENABLED"],
        },
        {
            "id": "live2d_frontend",
            "label": "Live2D Frontend",
            "status": "unavailable",
            "description": "Frontend implementation is intentionally outside this backend-only delivery.",
            "evidence": ["frontend_contract_only"],
        },
    ]
    return [CapabilityView(**row) for row in rows]
```

- [ ] **Step 4: Run capability tests**

Run:

```powershell
python -m pytest tests/test_amadeus_k_contracts.py -q
```

Expected: PASS.

- [ ] **Step 5: Stage capability files**

Run:

```powershell
git add apps/amadeus_k/backend/capabilities.py tests/test_amadeus_k_contracts.py
```

---

## Task 4: Avatar State Derivation

**Files:**

- Create: `apps/amadeus_k/backend/avatar_state.py`
- Create: `tests/test_amadeus_k_avatar_state.py`

- [ ] **Step 1: Write avatar-state tests**

Create `tests/test_amadeus_k_avatar_state.py`:

```python
from __future__ import annotations

from apps.amadeus_k.backend.avatar_state import derive_avatar_state


def test_pending_approval_maps_to_approval_wait():
    avatar = derive_avatar_state(
        {
            "final_text": "这里需要你确认一下。",
            "autonomy": {
                "pending_approval": {
                    "proposal_id": "ap-1",
                    "risk": "external_mutation",
                }
            },
        }
    )

    assert avatar.emotion == "approval_wait"
    assert avatar.motion == "approval_wait"
    assert avatar.speaking is True


def test_environmental_friction_maps_to_thinking():
    avatar = derive_avatar_state(
        {
            "final_text": "这个入口现在还不完整。",
            "digital_body_consequence": {"kind": "environmental_friction"},
            "autonomy": {"block_reason": "missing filesystem access"},
        }
    )

    assert avatar.emotion == "thinking"
    assert avatar.motion == "thinking"


def test_warm_continuity_maps_to_smile():
    avatar = derive_avatar_state(
        {
            "final_text": "我当然记得。别把我想得那么健忘。",
            "emotion_label": "warm",
            "turn_summary": {
                "current_turn": {
                    "counterpart_stance": "open",
                    "digital_body_consequence_kind": "",
                }
            },
        }
    )

    assert avatar.emotion == "smile"
    assert avatar.suggested_expression == "Smile"


def test_repair_or_tension_maps_to_sad():
    avatar = derive_avatar_state(
        {
            "final_text": "刚才那样说确实不太好。",
            "reconsolidation_snapshot": {
                "interaction_frame": "repair",
                "counterpart": {"stance": "hurt"},
            },
        }
    )

    assert avatar.emotion == "sad"


def test_empty_payload_maps_to_neutral_idle():
    avatar = derive_avatar_state({})

    assert avatar.emotion == "neutral"
    assert avatar.motion == "idle"
    assert avatar.speaking is False
```

- [ ] **Step 2: Run avatar tests to verify failure**

Run:

```powershell
python -m pytest tests/test_amadeus_k_avatar_state.py -q
```

Expected: FAIL because `apps.amadeus_k.backend.avatar_state` does not exist.

- [ ] **Step 3: Implement avatar-state derivation**

Create `apps/amadeus_k/backend/avatar_state.py`:

```python
from __future__ import annotations

from typing import Any

from .schemas import AvatarState

_EXPRESSION_BY_EMOTION = {
    "neutral": "Normal",
    "smile": "Smile",
    "sad": "Sad",
    "surprised": "Surprised",
    "angry": "Angry",
    "blush": "Blushing",
    "thinking": "Normal",
    "approval_wait": "Normal",
}

_MOTION_GROUP_BY_MOTION = {
    "idle": "Idle",
    "tap_body": "TapBody",
    "thinking": "Idle",
    "approval_wait": "Idle",
    "speaking": "Idle",
}


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _contains_any(text: str, words: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(word.lower() in lowered for word in words)


def _has_pending_approval(payload: dict[str, Any]) -> bool:
    autonomy = _dict(payload.get("autonomy"))
    pending = _dict(autonomy.get("pending_approval") or autonomy.get("pending"))
    if pending:
        return True
    approvals = _dict(payload.get("approvals"))
    return bool(approvals.get("has_pending"))


def derive_avatar_state(payload: dict[str, Any] | None) -> AvatarState:
    data = _dict(payload)
    final_text = _text(data.get("final_text"))
    emotion_label = _text(data.get("emotion_label"))
    turn_summary = _dict(data.get("turn_summary"))
    current_turn = _dict(turn_summary.get("current_turn"))
    recon = _dict(data.get("reconsolidation_snapshot"))
    consequence = _dict(data.get("digital_body_consequence"))
    autonomy = _dict(data.get("autonomy"))

    reason = "default neutral state"
    emotion = "neutral"
    motion = "speaking" if final_text else "idle"
    intensity = 0.35 if final_text else 0.0

    if _has_pending_approval(data):
        emotion = "approval_wait"
        motion = "approval_wait"
        reason = "turn is waiting for human approval"
        intensity = 0.68
    elif _text(autonomy.get("block_reason")) or _text(consequence.get("kind")) in {
        "environmental_friction",
        "sandbox_execution_blocked",
        "browser_execution_blocked",
        "access_request_pending",
    }:
        emotion = "thinking"
        motion = "thinking"
        reason = "digital body or autonomy path reports friction"
        intensity = 0.58
    elif _contains_any(
        " ".join(
            [
                emotion_label,
                _text(recon.get("interaction_frame")),
                _text(_dict(recon.get("counterpart")).get("stance")),
                final_text,
            ]
        ),
        ("repair", "hurt", "sad", "歉", "难过", "受伤", "修复"),
    ):
        emotion = "sad"
        reason = "repair or unresolved tension is visible in the turn"
        intensity = 0.64
    elif _contains_any(
        " ".join([emotion_label, final_text]),
        ("surprise", "surprised", "惊讶", "意外", "发现"),
    ):
        emotion = "surprised"
        reason = "surprise or discovery cue is visible"
        intensity = 0.62
    elif _contains_any(
        " ".join([emotion_label, final_text]),
        ("angry", "boundary", "blocked", "生气", "边界", "不满"),
    ):
        emotion = "angry"
        reason = "boundary or anger cue is visible"
        intensity = 0.6
    elif _contains_any(
        " ".join([emotion_label, final_text]),
        ("blush", "blushing", "害羞", "脸红"),
    ):
        emotion = "blush"
        reason = "intimacy or blush cue is visible"
        intensity = 0.6
    elif _contains_any(
        " ".join(
            [
                emotion_label,
                _text(current_turn.get("counterpart_stance")),
                final_text,
            ]
        ),
        ("warm", "open", "presence", "smile", "记得", "当然", "陪"),
    ):
        emotion = "smile"
        reason = "warm continuity or companionship cue is visible"
        intensity = 0.55

    return AvatarState(
        emotion=emotion,  # type: ignore[arg-type]
        motion=motion,  # type: ignore[arg-type]
        speaking=bool(final_text),
        intensity=intensity,
        reason=reason,
        suggested_expression=_EXPRESSION_BY_EMOTION.get(emotion, "Normal"),
        suggested_motion_group=_MOTION_GROUP_BY_MOTION.get(motion, "Idle"),
    )
```

- [ ] **Step 4: Run avatar tests**

Run:

```powershell
python -m pytest tests/test_amadeus_k_avatar_state.py -q
```

Expected: PASS.

- [ ] **Step 5: Stage avatar files**

Run:

```powershell
git add apps/amadeus_k/backend/avatar_state.py tests/test_amadeus_k_avatar_state.py
```

---

## Task 5: Backend Envelope Adapter

**Files:**

- Create: `apps/amadeus_k/backend/adapter.py`
- Create: `tests/test_amadeus_k_adapter.py`

- [ ] **Step 1: Write adapter tests**

Create `tests/test_amadeus_k_adapter.py`:

```python
from __future__ import annotations

from types import SimpleNamespace

from apps.amadeus_k.backend.adapter import (
    ProductBackendAdapter,
    product_turn_from_backend_envelope,
)


def _backend_envelope(payload):
    return SimpleNamespace(
        schema_version="backend.v1",
        kind="assistant_turn",
        thread_id="thread-product",
        payload=payload,
        meta={"source": "test"},
    )


def test_product_turn_from_backend_envelope_extracts_core_fields():
    backend = _backend_envelope(
        {
            "final_text": "别担心，我会记着这件事。",
            "emotion_label": "warm",
            "turn_summary": {
                "relationship": {"stage": "warming"},
                "current_turn": {
                    "counterpart_stance": "open",
                    "digital_body_access_mode": "active",
                    "digital_body_workspace_root": "E:/workspace",
                },
            },
            "autonomy": {
                "intent": {"mode": "idle", "reason": "conversation"},
                "action_packets": [],
                "pending_approval": {},
                "execution_trace": [],
                "block_reason": "",
            },
            "digital_body": {
                "active_surface": "dialogue",
                "access_state": {"mode": "active", "filesystem_state": "writable"},
                "resource_state": {"workspace_root": "E:/workspace"},
            },
            "skills": {"active": []},
            "writeback_trace": {
                "revision_traces": [{"preview_line": "记住了一个小承诺。"}],
                "semantic_self_narratives": [],
            },
        }
    )

    product = product_turn_from_backend_envelope(
        backend,
        user_text="你别忘了。",
        turn_id="turn-1",
    )
    data = product.to_dict()

    assert data["thread_id"] == "thread-product"
    assert data["final_text"] == "别担心，我会记着这件事。"
    assert data["tts_text"] == data["final_text"]
    assert data["avatar_state"]["emotion"] == "smile"
    assert data["memory_view"]["writeback_happened"] is True
    assert data["relationship_view"]["bond_label"] == "warming"
    assert data["digital_body"]["workspace_root"] == "E:/workspace"
    assert data["diagnostics"]["raw_backend_kind"] == "assistant_turn"


def test_pending_approval_is_promoted_to_approval_view():
    backend = _backend_envelope(
        {
            "final_text": "这一步需要你确认。",
            "autonomy": {
                "intent": {"mode": "approval_pending", "primary_proposal_id": "ap-1"},
                "action_packets": [{"proposal_id": "ap-1", "intent": "sandbox:execute_workspace_command"}],
                "pending_approval": {
                    "proposal_id": "ap-1",
                    "intent": "sandbox:execute_workspace_command",
                    "risk": "external_mutation",
                    "result_summary": "waiting for approval",
                    "execution_preview": {"argv": ["python", "x.py"]},
                },
                "execution_trace": [],
                "block_reason": "",
            },
            "digital_body": {"access_state": {"mode": "approval_pending"}},
        }
    )

    product = product_turn_from_backend_envelope(backend, user_text="跑一下", turn_id="turn-2")
    data = product.to_dict()

    assert data["approvals"]["has_pending"] is True
    assert data["approvals"]["proposal_id"] == "ap-1"
    assert data["approvals"]["risk"] == "external_mutation"
    assert data["avatar_state"]["emotion"] == "approval_wait"


def test_product_backend_adapter_exposes_bootstrap():
    adapter = ProductBackendAdapter(thread_id="thread-product")

    bootstrap = adapter.bootstrap()
    data = bootstrap.to_dict()

    assert data["kind"] == "bootstrap"
    assert data["thread_id"] == "thread-product"
    assert any(item["id"] == "sandbox_phase2_docker" for item in data["capabilities"])
    assert data["frontend_hints"]["avatar"]["default_model"] == "Live2D official Natori sample"
```

- [ ] **Step 2: Run adapter tests to verify failure**

Run:

```powershell
python -m pytest tests/test_amadeus_k_adapter.py -q
```

Expected: FAIL because `apps.amadeus_k.backend.adapter` does not exist.

- [ ] **Step 3: Implement adapter**

Create `apps/amadeus_k/backend/adapter.py`:

```python
from __future__ import annotations

import os
from typing import Any

from .avatar_state import derive_avatar_state
from .capabilities import build_capability_views
from .schemas import (
    ApprovalView,
    AutonomyView,
    DiagnosticsView,
    DigitalBodyView,
    MemoryView,
    ProductBootstrapEnvelope,
    ProductTurnEnvelope,
    RelationshipView,
)


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _payload(envelope: Any) -> dict[str, Any]:
    if isinstance(envelope, dict):
        return _dict(envelope.get("payload"))
    return _dict(getattr(envelope, "payload", {}))


def _envelope_field(envelope: Any, key: str, default: str = "") -> str:
    if isinstance(envelope, dict):
        return _text(envelope.get(key) or default)
    return _text(getattr(envelope, key, default))


def _memory_view(payload: dict[str, Any]) -> MemoryView:
    writeback = _dict(payload.get("writeback_trace"))
    traces = [item for item in _list(writeback.get("revision_traces")) if isinstance(item, dict)]
    previews: list[str] = []
    for item in traces[:4]:
        preview = _text(item.get("preview_line") or item.get("summary") or item.get("text"))
        if preview:
            previews.append(preview)
    summary = "本轮没有显式长期记忆写回。"
    if previews:
        summary = "本轮产生了可追踪的连续性痕迹。"
    return MemoryView(
        summary=summary,
        recent_continuity=previews,
        writeback_happened=bool(previews),
        writeback_preview=previews,
    )


def _relationship_view(payload: dict[str, Any]) -> RelationshipView:
    turn_summary = _dict(payload.get("turn_summary"))
    relationship = _dict(turn_summary.get("relationship"))
    current_turn = _dict(turn_summary.get("current_turn"))
    bond_label = _text(relationship.get("stage") or relationship.get("bond_label"))
    stance = _text(current_turn.get("counterpart_stance") or current_turn.get("counterpart_scene"))
    continuity: list[str] = []
    for key in ("counterpart_assessment_preview", "proactive_continuity_preview"):
        value = payload.get(key) or turn_summary.get(key)
        if isinstance(value, str) and value.strip():
            continuity.append(value.strip())
    return RelationshipView(
        summary=bond_label or stance or "关系状态已由后端持续维护。",
        stance=stance,
        bond_label=bond_label,
        continuity_preview=continuity,
        unresolved_tension_count=int(current_turn.get("unresolved_tension_count") or 0),
        commitment_count=int(current_turn.get("commitment_count") or 0),
    )


def _autonomy_view(payload: dict[str, Any]) -> AutonomyView:
    autonomy = _dict(payload.get("autonomy"))
    intent = _dict(autonomy.get("intent"))
    pending = _dict(autonomy.get("pending_approval"))
    return AutonomyView(
        mode=_text(intent.get("mode") or ("approval_pending" if pending else "idle")),
        reason=_text(intent.get("reason")),
        primary_proposal_id=_text(intent.get("primary_proposal_id") or pending.get("proposal_id")),
        pending=pending,
        action_packets=[dict(item) for item in _list(autonomy.get("action_packets")) if isinstance(item, dict)],
        execution_trace=[dict(item) for item in _list(autonomy.get("execution_trace")) if isinstance(item, dict)],
        block_reason=_text(autonomy.get("block_reason")),
    )


def _approval_view(payload: dict[str, Any]) -> ApprovalView:
    autonomy = _dict(payload.get("autonomy"))
    pending = _dict(autonomy.get("pending_approval"))
    if not pending:
        return ApprovalView()
    preview = {}
    for key in ("execution_preview", "browser_execution_preview", "mutation_preview"):
        if isinstance(pending.get(key), dict) and pending.get(key):
            preview = dict(pending.get(key) or {})
            break
    assist = _dict(pending.get("assist_request"))
    message = _text(assist.get("message") or pending.get("result_summary") or pending.get("expected_effect"))
    return ApprovalView(
        has_pending=True,
        proposal_id=_text(pending.get("proposal_id")),
        kind=_text(pending.get("intent")),
        message=message,
        risk=_text(pending.get("risk")),
        required_action="approve_or_reject",
        preview=preview,
    )


def _digital_body_view(payload: dict[str, Any]) -> DigitalBodyView:
    body = _dict(payload.get("digital_body"))
    access = _dict(body.get("access_state"))
    resource = _dict(body.get("resource_state"))
    browser = _dict(access.get("browser_runtime_state"))
    sandbox = _dict(access.get("sandbox_state"))
    skills = _dict(payload.get("skills"))
    notes: list[str] = []
    if _text(sandbox.get("runner_kind")) == "docker_isolated_runner":
        notes.append("Docker isolated sandbox is surfaced as experimental unless phase-2 audit is ready.")
    return DigitalBodyView(
        active_surface=_text(body.get("active_surface")),
        access_mode=_text(access.get("mode")),
        world_surfaces=[_text(item) for item in _list(body.get("world_surfaces")) if _text(item)],
        filesystem_state=_text(access.get("filesystem_state")),
        browser_state=browser,
        sandbox_state=sandbox,
        skill_state=skills,
        workspace_root=_text(resource.get("workspace_root") or sandbox.get("workspace_root")),
        last_run={
            "run_id": _text(sandbox.get("last_run_id")),
            "status": _text(sandbox.get("last_status")),
            "exit_code": sandbox.get("last_exit_code", 0),
        },
        experimental_notes=notes,
    )


def product_turn_from_backend_envelope(
    envelope: Any,
    *,
    user_text: str,
    turn_id: str,
    env: dict[str, str] | None = None,
) -> ProductTurnEnvelope:
    payload = _payload(envelope)
    final_text = _text(payload.get("final_text"))
    tts_text = final_text
    capabilities = build_capability_views(env=env)
    product_payload_for_avatar = dict(payload)
    approvals = _approval_view(payload)
    product_payload_for_avatar["approvals"] = approvals.to_dict()
    avatar_state = derive_avatar_state(product_payload_for_avatar)
    return ProductTurnEnvelope(
        thread_id=_envelope_field(envelope, "thread_id", "default"),
        turn_id=_text(turn_id) or "turn-unknown",
        user_text=_text(user_text),
        final_text=final_text,
        tts_text=tts_text,
        avatar_state=avatar_state,
        memory_view=_memory_view(payload),
        relationship_view=_relationship_view(payload),
        autonomy=_autonomy_view(payload),
        approvals=approvals,
        digital_body=_digital_body_view(payload),
        capabilities=capabilities,
        diagnostics=DiagnosticsView(
            backend_schema_version=_envelope_field(envelope, "schema_version"),
            raw_backend_kind=_envelope_field(envelope, "kind"),
        ),
    )


class ProductBackendAdapter:
    def __init__(self, *, thread_id: str, env: dict[str, str] | None = None):
        self.thread_id = _text(thread_id) or "amadeus-k-default"
        self.env = dict(env or os.environ)

    def bootstrap(self) -> ProductBootstrapEnvelope:
        return ProductBootstrapEnvelope(
            thread_id=self.thread_id,
            persona={
                "id": "amadeus-kurisu",
                "display_name": "Amadeus 牧濑红莉栖",
                "identity_policy": "fixed_persona_core_stateful_evolution",
            },
            session={
                "mode": "product_core",
                "frontend_contract": "contracts/amadeus_k_api.types.ts",
            },
            capabilities=build_capability_views(env=self.env),
            frontend_hints={
                "avatar": {
                    "default_model": "Live2D official Natori sample",
                    "state_source": "avatar_state",
                    "model_specific_mapping_owned_by_frontend": True,
                },
                "tts": {
                    "text_field": "tts_text",
                    "semantic_parity_field": "final_text",
                },
            },
        )

    def turn_from_backend_envelope(self, envelope: Any, *, user_text: str, turn_id: str) -> ProductTurnEnvelope:
        return product_turn_from_backend_envelope(
            envelope,
            user_text=user_text,
            turn_id=turn_id,
            env=self.env,
        )
```

- [ ] **Step 4: Run adapter tests**

Run:

```powershell
python -m pytest tests/test_amadeus_k_adapter.py -q
```

Expected: PASS.

- [ ] **Step 5: Run product tests together**

Run:

```powershell
python -m pytest tests/test_amadeus_k_avatar_state.py tests/test_amadeus_k_contracts.py tests/test_amadeus_k_adapter.py -q
```

Expected: PASS.

- [ ] **Step 6: Stage adapter files**

Run:

```powershell
git add apps/amadeus_k/backend/adapter.py tests/test_amadeus_k_adapter.py
```

---

## Task 6: Product Service Facade

**Files:**

- Create: `apps/amadeus_k/backend/app.py`
- Modify: `tests/test_amadeus_k_adapter.py`

- [ ] **Step 1: Add service tests**

Append to `tests/test_amadeus_k_adapter.py`:

```python
from apps.amadeus_k.backend.app import ProductBackendService


def test_product_service_health_and_bootstrap():
    service = ProductBackendService(thread_id="thread-product", runtime_bundle=None)

    assert service.health()["status"] == "ok"
    assert service.health()["schema_version"] == "amadeus-k.product.v1"
    assert service.bootstrap()["kind"] == "bootstrap"


def test_product_service_turn_from_backend_envelope():
    service = ProductBackendService(thread_id="thread-product", runtime_bundle=None)
    backend = _backend_envelope({"final_text": "嗯，我在。", "emotion_label": "warm"})

    data = service.turn_from_backend_envelope(backend, user_text="在吗？", turn_id="turn-3")

    assert data["kind"] == "turn"
    assert data["final_text"] == "嗯，我在。"
    assert data["avatar_state"]["emotion"] == "smile"
```

- [ ] **Step 2: Run service tests to verify failure**

Run:

```powershell
python -m pytest tests/test_amadeus_k_adapter.py -q
```

Expected: FAIL because `apps.amadeus_k.backend.app` does not exist.

- [ ] **Step 3: Implement pure Python service facade**

Create `apps/amadeus_k/backend/app.py`:

```python
from __future__ import annotations

import itertools
from pathlib import Path
from typing import Any

from .adapter import ProductBackendAdapter
from .capabilities import build_capability_views
from .schemas import SCHEMA_VERSION


class ProductBackendService:
    def __init__(
        self,
        *,
        thread_id: str = "amadeus-k-default",
        runtime_bundle: Any | None = None,
        base_data_dir: Path | None = None,
        env: dict[str, str] | None = None,
    ):
        self.thread_id = str(thread_id or "amadeus-k-default").strip()
        self.runtime_bundle = runtime_bundle
        self.base_data_dir = Path(base_data_dir or Path.cwd())
        self.adapter = ProductBackendAdapter(thread_id=self.thread_id, env=env)
        self._turn_counter = itertools.count(1)

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "schema_version": SCHEMA_VERSION,
            "thread_id": self.thread_id,
            "runtime_attached": self.runtime_bundle is not None,
        }

    def bootstrap(self) -> dict[str, Any]:
        return self.adapter.bootstrap().to_dict()

    def capabilities(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "kind": "capabilities",
            "thread_id": self.thread_id,
            "capabilities": [item.to_dict() for item in build_capability_views()],
        }

    def turn_from_backend_envelope(self, envelope: Any, *, user_text: str, turn_id: str | None = None) -> dict[str, Any]:
        resolved_turn_id = turn_id or f"turn-{next(self._turn_counter)}"
        return self.adapter.turn_from_backend_envelope(
            envelope,
            user_text=user_text,
            turn_id=resolved_turn_id,
        ).to_dict()

    def turn(self, user_text: str) -> dict[str, Any]:
        if self.runtime_bundle is None:
            raise RuntimeError("runtime_bundle is required for live turn execution")
        backend_session = getattr(self.runtime_bundle, "backend_session")
        backend_api = self.runtime_bundle.backend_api(base_data_dir=self.base_data_dir, cwd=Path.cwd())
        result = backend_session.invoke_stream({"messages": [{"role": "user", "content": str(user_text)}]})
        backend_envelope = backend_api.build_turn_response(
            state_values=result.values,
            streamed_text=result.streamed_text,
        )
        return self.turn_from_backend_envelope(
            backend_envelope,
            user_text=user_text,
            turn_id=f"turn-{next(self._turn_counter)}",
        )
```

- [ ] **Step 4: Run service tests**

Run:

```powershell
python -m pytest tests/test_amadeus_k_adapter.py -q
```

Expected: PASS.

- [ ] **Step 5: Stage service files**

Run:

```powershell
git add apps/amadeus_k/backend/app.py tests/test_amadeus_k_adapter.py
```

---

## Task 7: TypeScript Contract and JSON Examples

**Files:**

- Create: `apps/amadeus_k/contracts/amadeus_k_api.types.ts`
- Create: `apps/amadeus_k/contracts/examples/bootstrap.response.json`
- Create: `apps/amadeus_k/contracts/examples/turn.response.json`
- Create: `apps/amadeus_k/contracts/examples/approval_pending.response.json`
- Create: `apps/amadeus_k/contracts/examples/capabilities.response.json`
- Modify: `tests/test_amadeus_k_contracts.py`

- [ ] **Step 1: Add contract file tests**

Append to `tests/test_amadeus_k_contracts.py`:

```python
import json
from pathlib import Path


CONTRACT_ROOT = Path("apps/amadeus_k/contracts")


def test_typescript_contract_contains_core_exports():
    text = (CONTRACT_ROOT / "amadeus_k_api.types.ts").read_text(encoding="utf-8")

    assert "export interface ProductTurnEnvelope" in text
    assert "export interface AvatarState" in text
    assert "export type AvatarEmotion" in text
    assert "export interface AmadeusKClient" in text


def test_example_json_files_use_product_schema_version():
    for name in [
        "bootstrap.response.json",
        "turn.response.json",
        "approval_pending.response.json",
        "capabilities.response.json",
    ]:
        data = json.loads((CONTRACT_ROOT / "examples" / name).read_text(encoding="utf-8"))
        assert data["schema_version"] == SCHEMA_VERSION
```

- [ ] **Step 2: Run contract tests to verify failure**

Run:

```powershell
python -m pytest tests/test_amadeus_k_contracts.py -q
```

Expected: FAIL because contract files do not exist.

- [ ] **Step 3: Create TypeScript contract**

Create `apps/amadeus_k/contracts/amadeus_k_api.types.ts`:

```ts
export type ProductSchemaVersion = "amadeus-k.product.v1";

export type AvatarEmotion =
  | "neutral"
  | "smile"
  | "sad"
  | "surprised"
  | "angry"
  | "blush"
  | "thinking"
  | "approval_wait";

export type AvatarMotion =
  | "idle"
  | "tap_body"
  | "thinking"
  | "approval_wait"
  | "speaking";

export type CapabilityStatus = "ready" | "experimental" | "blocked" | "unavailable";

export interface AvatarState {
  emotion: AvatarEmotion;
  motion: AvatarMotion;
  speaking: boolean;
  intensity: number;
  reason: string;
  suggested_expression: string;
  suggested_motion_group: string;
}

export interface MemoryView {
  summary: string;
  recent_continuity: string[];
  writeback_happened: boolean;
  writeback_preview: string[];
}

export interface RelationshipView {
  summary: string;
  stance: string;
  bond_label: string;
  continuity_preview: string[];
  unresolved_tension_count: number;
  commitment_count: number;
}

export interface AutonomyView {
  mode: string;
  reason: string;
  primary_proposal_id: string;
  pending: Record<string, unknown>;
  action_packets: Record<string, unknown>[];
  execution_trace: Record<string, unknown>[];
  block_reason: string;
}

export interface ApprovalView {
  has_pending: boolean;
  proposal_id: string;
  kind: string;
  message: string;
  risk: string;
  required_action: string;
  preview: Record<string, unknown>;
}

export interface DigitalBodyView {
  active_surface: string;
  access_mode: string;
  world_surfaces: string[];
  filesystem_state: string;
  browser_state: Record<string, unknown>;
  sandbox_state: Record<string, unknown>;
  skill_state: Record<string, unknown>;
  workspace_root: string;
  last_run: Record<string, unknown>;
  experimental_notes: string[];
}

export interface CapabilityView {
  id: string;
  label: string;
  status: CapabilityStatus;
  description: string;
  evidence: string[];
  frontend_visible: boolean;
}

export interface DiagnosticsView {
  backend_schema_version: string;
  raw_backend_kind: string;
  warnings: string[];
  trace_refs: string[];
}

export interface ProductBootstrapEnvelope {
  schema_version: ProductSchemaVersion;
  kind: "bootstrap";
  thread_id: string;
  generated_at: number;
  persona: Record<string, unknown>;
  session: Record<string, unknown>;
  capabilities: CapabilityView[];
  frontend_hints: Record<string, unknown>;
}

export interface ProductTurnEnvelope {
  schema_version: ProductSchemaVersion;
  kind: "turn";
  thread_id: string;
  turn_id: string;
  generated_at: number;
  user_text: string;
  final_text: string;
  tts_text: string;
  avatar_state: AvatarState;
  memory_view: MemoryView;
  relationship_view: RelationshipView;
  autonomy: AutonomyView;
  approvals: ApprovalView;
  digital_body: DigitalBodyView;
  capabilities: CapabilityView[];
  diagnostics: DiagnosticsView;
}

export interface CapabilitiesEnvelope {
  schema_version: ProductSchemaVersion;
  kind: "capabilities";
  thread_id: string;
  capabilities: CapabilityView[];
}

export interface TurnRequest {
  text: string;
  thread_id?: string;
}

export interface ApprovalDecisionRequest {
  proposal_id: string;
  action: "approve" | "reject";
  reason?: string;
}

export interface ApiError {
  schema_version: ProductSchemaVersion;
  kind: "error";
  message: string;
  code: string;
  detail?: Record<string, unknown>;
}

export interface AmadeusKClient {
  health(): Promise<Record<string, unknown>>;
  bootstrap(): Promise<ProductBootstrapEnvelope>;
  turn(request: TurnRequest): Promise<ProductTurnEnvelope>;
  capabilities(): Promise<CapabilitiesEnvelope>;
  approve(request: ApprovalDecisionRequest): Promise<ProductTurnEnvelope | ApiError>;
  reject(request: ApprovalDecisionRequest): Promise<ProductTurnEnvelope | ApiError>;
}
```

- [ ] **Step 4: Create example JSON fixtures**

Create `apps/amadeus_k/contracts/examples/bootstrap.response.json`:

```json
{
  "schema_version": "amadeus-k.product.v1",
  "kind": "bootstrap",
  "thread_id": "amadeus-k-demo",
  "generated_at": 1760000000,
  "persona": {
    "id": "amadeus-kurisu",
    "display_name": "Amadeus 牧濑红莉栖",
    "identity_policy": "fixed_persona_core_stateful_evolution"
  },
  "session": {
    "mode": "product_core",
    "frontend_contract": "contracts/amadeus_k_api.types.ts"
  },
  "capabilities": [
    {
      "id": "dialogue_core",
      "label": "Dialogue Core",
      "status": "ready",
      "description": "LangGraph-backed turn loop for persona response generation.",
      "evidence": ["BackendAPI.build_turn_response"],
      "frontend_visible": true
    },
    {
      "id": "sandbox_phase2_docker",
      "label": "Sandbox Phase 2 Docker",
      "status": "experimental",
      "description": "Docker-isolated execution is active research work and not a preserved product baseline.",
      "evidence": ["sandbox_embodied_execution_phase2_in_progress"],
      "frontend_visible": true
    }
  ],
  "frontend_hints": {
    "avatar": {
      "default_model": "Live2D official Natori sample",
      "state_source": "avatar_state",
      "model_specific_mapping_owned_by_frontend": true
    }
  }
}
```

Create `apps/amadeus_k/contracts/examples/turn.response.json`:

```json
{
  "schema_version": "amadeus-k.product.v1",
  "kind": "turn",
  "thread_id": "amadeus-k-demo",
  "turn_id": "turn-1",
  "generated_at": 1760000001,
  "user_text": "你还记得我昨天说的事吗？",
  "final_text": "当然记得。你以为我会随便把这种事丢掉吗？",
  "tts_text": "当然记得。你以为我会随便把这种事丢掉吗？",
  "avatar_state": {
    "emotion": "smile",
    "motion": "speaking",
    "speaking": true,
    "intensity": 0.55,
    "reason": "warm continuity or companionship cue is visible",
    "suggested_expression": "Smile",
    "suggested_motion_group": "Idle"
  },
  "memory_view": {
    "summary": "本轮产生了可追踪的连续性痕迹。",
    "recent_continuity": ["记住了一个小承诺。"],
    "writeback_happened": true,
    "writeback_preview": ["记住了一个小承诺。"]
  },
  "relationship_view": {
    "summary": "warming",
    "stance": "open",
    "bond_label": "warming",
    "continuity_preview": [],
    "unresolved_tension_count": 0,
    "commitment_count": 0
  },
  "autonomy": {
    "mode": "idle",
    "reason": "",
    "primary_proposal_id": "",
    "pending": {},
    "action_packets": [],
    "execution_trace": [],
    "block_reason": ""
  },
  "approvals": {
    "has_pending": false,
    "proposal_id": "",
    "kind": "",
    "message": "",
    "risk": "",
    "required_action": "",
    "preview": {}
  },
  "digital_body": {
    "active_surface": "dialogue",
    "access_mode": "active",
    "world_surfaces": ["dialogue"],
    "filesystem_state": "",
    "browser_state": {},
    "sandbox_state": {},
    "skill_state": {},
    "workspace_root": "",
    "last_run": {"run_id": "", "status": "", "exit_code": 0},
    "experimental_notes": []
  },
  "capabilities": [],
  "diagnostics": {
    "backend_schema_version": "backend.v1",
    "raw_backend_kind": "assistant_turn",
    "warnings": [],
    "trace_refs": []
  }
}
```

Create `apps/amadeus_k/contracts/examples/approval_pending.response.json`:

```json
{
  "schema_version": "amadeus-k.product.v1",
  "kind": "turn",
  "thread_id": "amadeus-k-demo",
  "turn_id": "turn-approval-1",
  "generated_at": 1760000002,
  "user_text": "帮我执行一下这个工作区命令。",
  "final_text": "这一步需要你确认，我不会绕过审批直接动手。",
  "tts_text": "这一步需要你确认，我不会绕过审批直接动手。",
  "avatar_state": {
    "emotion": "approval_wait",
    "motion": "approval_wait",
    "speaking": true,
    "intensity": 0.68,
    "reason": "turn is waiting for human approval",
    "suggested_expression": "Normal",
    "suggested_motion_group": "Idle"
  },
  "memory_view": {
    "summary": "本轮没有显式长期记忆写回。",
    "recent_continuity": [],
    "writeback_happened": false,
    "writeback_preview": []
  },
  "relationship_view": {
    "summary": "关系状态已由后端持续维护。",
    "stance": "",
    "bond_label": "",
    "continuity_preview": [],
    "unresolved_tension_count": 0,
    "commitment_count": 0
  },
  "autonomy": {
    "mode": "approval_pending",
    "reason": "",
    "primary_proposal_id": "ap-1",
    "pending": {
      "proposal_id": "ap-1",
      "intent": "sandbox:execute_workspace_command",
      "risk": "external_mutation"
    },
    "action_packets": [
      {
        "proposal_id": "ap-1",
        "intent": "sandbox:execute_workspace_command",
        "status": "awaiting_approval"
      }
    ],
    "execution_trace": [],
    "block_reason": ""
  },
  "approvals": {
    "has_pending": true,
    "proposal_id": "ap-1",
    "kind": "sandbox:execute_workspace_command",
    "message": "waiting for approval",
    "risk": "external_mutation",
    "required_action": "approve_or_reject",
    "preview": {
      "argv": ["python", "script.py"],
      "cwd": "."
    }
  },
  "digital_body": {
    "active_surface": "approval_gate",
    "access_mode": "approval_pending",
    "world_surfaces": ["filesystem", "sandbox"],
    "filesystem_state": "",
    "browser_state": {},
    "sandbox_state": {},
    "skill_state": {},
    "workspace_root": "",
    "last_run": {"run_id": "", "status": "", "exit_code": 0},
    "experimental_notes": []
  },
  "capabilities": [],
  "diagnostics": {
    "backend_schema_version": "backend.v1",
    "raw_backend_kind": "assistant_turn",
    "warnings": [],
    "trace_refs": []
  }
}
```

Create `apps/amadeus_k/contracts/examples/capabilities.response.json`:

```json
{
  "schema_version": "amadeus-k.product.v1",
  "kind": "capabilities",
  "thread_id": "amadeus-k-demo",
  "capabilities": [
    {
      "id": "dialogue_core",
      "label": "Dialogue Core",
      "status": "ready",
      "description": "LangGraph-backed turn loop for persona response generation.",
      "evidence": ["BackendAPI.build_turn_response"],
      "frontend_visible": true
    },
    {
      "id": "sandbox_phase2_docker",
      "label": "Sandbox Phase 2 Docker",
      "status": "experimental",
      "description": "Docker-isolated execution is active research work and not a preserved product baseline.",
      "evidence": ["sandbox_embodied_execution_phase2_in_progress"],
      "frontend_visible": true
    },
    {
      "id": "live2d_frontend",
      "label": "Live2D Frontend",
      "status": "unavailable",
      "description": "Frontend implementation is intentionally outside this backend-only delivery.",
      "evidence": ["frontend_contract_only"],
      "frontend_visible": true
    }
  ]
}
```

- [ ] **Step 5: Run contract tests**

Run:

```powershell
python -m pytest tests/test_amadeus_k_contracts.py -q
```

Expected: PASS.

- [ ] **Step 6: Stage contract files**

Run:

```powershell
git add apps/amadeus_k/contracts/amadeus_k_api.types.ts apps/amadeus_k/contracts/examples tests/test_amadeus_k_contracts.py
```

---

## Task 8: Frontend and Thesis Documentation

**Files:**

- Create: `apps/amadeus_k/docs/FRONTEND_CONTRACT.md`
- Create: `apps/amadeus_k/docs/PRODUCT_BOUNDARY.md`
- Create: `apps/amadeus_k/docs/DEMO_SCRIPT.md`

- [ ] **Step 1: Create frontend contract documentation**

Create `apps/amadeus_k/docs/FRONTEND_CONTRACT.md`:

```markdown
# Amadeus-K Frontend Contract

The frontend should depend on `apps/amadeus_k/contracts/amadeus_k_api.types.ts`, not on internal `amadeus_thread0` graph state.

## Startup Flow

1. Call `bootstrap()`.
2. Render persona metadata from `persona`.
3. Render capability status from `capabilities`.
4. Initialize avatar mapping from `frontend_hints.avatar`.

## Turn Flow

1. Send user input as `TurnRequest`.
2. Display `final_text` as the assistant message.
3. Send `tts_text` to the speech layer when TTS is enabled.
4. Drive Live2D using `avatar_state`.
5. Render memory, relationship, autonomy, approval, and digital-body panels from their product views.

## Live2D Mapping

The backend emits semantic avatar state. The frontend maps it to the selected model.

Recommended mapping for the official Natori sample:

```ts
const natoriExpressionMap = {
  neutral: "Normal",
  smile: "Smile",
  sad: "Sad",
  surprised: "Surprised",
  angry: "Angry",
  blush: "Blushing",
  thinking: "Normal",
  approval_wait: "Normal",
};
```

The frontend owns model-specific parameter names. Replacing a commercial Live2D model should only require replacing the model files and the mapping table.

## Approval Flow

When `approvals.has_pending` is true, show approval controls. Do not treat pending actions as completed facts. The UI should display:

- `approvals.message`
- `approvals.risk`
- `approvals.preview`
- approve/reject buttons when endpoints are enabled

## Stable Fields

Stable fields:

- `final_text`
- `tts_text`
- `avatar_state`
- `memory_view`
- `relationship_view`
- `autonomy`
- `approvals`
- `digital_body`
- `capabilities`

Diagnostic fields are useful for debugging but should not drive primary UI behavior.
```

- [ ] **Step 2: Create product boundary documentation**

Create `apps/amadeus_k/docs/PRODUCT_BOUNDARY.md`:

```markdown
# Amadeus-K Product Boundary

## Implemented Backend Deliverable

This product layer turns the research backend into a stable backend deliverable for a virtual digital persona system.

Included:

- fixed persona core readout
- dialogue turn envelope
- long-term memory summary
- relationship continuity summary
- autonomy and action packet visibility
- approval state visibility
- digital-body state read model
- capability readiness reporting
- Live2D-ready avatar state
- frontend TypeScript contract and example payloads

## Experimental or External

Not included as production-ready:

- Docker Sandbox Phase 2 readiness
- frontend implementation
- commercial Live2D model binding
- local LoRA/SFT training
- full GraphRAG character-origin knowledge base rebuild
- desktop pet packaging
- embedded hardware deployment

## Relationship to the Original Graduation Design

The original plan proposed fine-tuning, GraphRAG, Memos-style user memory, and Live2D integration.

The final backend route keeps the same product goal but shifts the implementation center:

- Persona restoration is handled through a fixed persona core and stateful behavior loop.
- User companionship memory is handled through the unified memory substrate.
- Digital embodiment is represented by digital-body state, approval semantics, browser/sandbox/skills capability surfaces, and Live2D-ready avatar state.
- The frontend can later render the virtual body without depending on graph internals.

This route is more suitable for a complete graduation-design backend because it provides traceable state, safety boundaries, and evaluable continuity instead of only prompt-level role play.
```

- [ ] **Step 3: Create demo script**

Create `apps/amadeus_k/docs/DEMO_SCRIPT.md`:

```markdown
# Amadeus-K Demo Script

## Goal

Demonstrate Amadeus-K as a real backend product core for a virtual digital persona.

## Demo Steps

1. Show `apps/amadeus_k/contracts/amadeus_k_api.types.ts`.
   - Explain that frontend depends on this stable contract.

2. Bootstrap the product service.
   - Show persona identity.
   - Show capability statuses.
   - Point out that Docker Sandbox Phase 2 is experimental, not falsely marked ready.

3. Send an ordinary companionship turn.
   - Show `final_text`.
   - Show `tts_text`.
   - Show `avatar_state.emotion` and `avatar_state.suggested_expression`.

4. Show continuity views.
   - Show `memory_view`.
   - Show `relationship_view`.
   - Explain how these support long-term companionship.

5. Show autonomy and approval views.
   - Use `approval_pending.response.json` if live approval is not triggered during the short demo.
   - Explain that pending actions are not written back as completed facts.

6. Show digital-body state.
   - Explain browser, sandbox, skills, and access state as parts of the digital body.

7. Connect to thesis narrative.
   - The system is not a static prompt shell.
   - The persona has a fixed identity core and stateful evolution.
   - Frontend Live2D can consume `avatar_state` without knowing backend internals.

## Commands

Run focused product tests:

```powershell
python -m pytest tests/test_amadeus_k_avatar_state.py tests/test_amadeus_k_contracts.py tests/test_amadeus_k_adapter.py -q
```
```

- [ ] **Step 4: Stage documentation**

Run:

```powershell
git add apps/amadeus_k/docs/FRONTEND_CONTRACT.md apps/amadeus_k/docs/PRODUCT_BOUNDARY.md apps/amadeus_k/docs/DEMO_SCRIPT.md
```

---

## Task 9: Verification and Ledger Update

**Files:**

- Modify: `program.md`

- [ ] **Step 1: Run focused product tests**

Run:

```powershell
python -m pytest tests/test_amadeus_k_avatar_state.py tests/test_amadeus_k_contracts.py tests/test_amadeus_k_adapter.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run compile check**

Run:

```powershell
python -m py_compile apps/amadeus_k/backend/schemas.py apps/amadeus_k/backend/capabilities.py apps/amadeus_k/backend/avatar_state.py apps/amadeus_k/backend/adapter.py apps/amadeus_k/backend/app.py
```

Expected: no output and exit code 0.

- [ ] **Step 3: Run a product service smoke**

Run:

```powershell
python - <<'PY'
from apps.amadeus_k.backend.app import ProductBackendService

service = ProductBackendService(thread_id="amadeus-k-smoke", runtime_bundle=None)
print(service.health()["status"])
print(service.bootstrap()["schema_version"])
PY
```

Expected:

```text
ok
amadeus-k.product.v1
```

- [ ] **Step 4: Update program ledger**

Append a new run entry to `program.md`:

```markdown
## 2026-05-03 Run 232

- Focus:
  - create the `apps/amadeus_k` backend product core as a clean frontend-facing layer over the existing research backend
- Files changed:
  - `apps/amadeus_k/...`
  - `tests/test_amadeus_k_avatar_state.py`
  - `tests/test_amadeus_k_contracts.py`
  - `tests/test_amadeus_k_adapter.py`
  - `docs/superpowers/specs/2026-05-03-amadeus-k-product-core-design.md`
  - `docs/superpowers/plans/2026-05-03-amadeus-k-product-core.md`
  - `program.md`
- Key changes:
  - added product schemas and frontend TypeScript contract
  - added capability reporting with Docker Phase 2 marked experimental
  - added deterministic `avatar_state` derivation for Live2D-ready frontends
  - added adapter from existing backend envelopes to `amadeus-k.product.v1`
  - added backend-only product service facade
  - added frontend contract, product boundary, and demo-script docs
- Validation:
  - `python -m pytest tests/test_amadeus_k_avatar_state.py tests/test_amadeus_k_contracts.py tests/test_amadeus_k_adapter.py -q`
  - `python -m py_compile apps/amadeus_k/backend/schemas.py apps/amadeus_k/backend/capabilities.py apps/amadeus_k/backend/avatar_state.py apps/amadeus_k/backend/adapter.py apps/amadeus_k/backend/app.py`
- Result:
  - the repository now has a clean backend product core for frontend handoff and thesis writing
  - old research backend internals remain untouched
  - frontend implementation remains intentionally out of scope
- Next:
  - wire a real frontend to `apps/amadeus_k/contracts/amadeus_k_api.types.ts`
  - optionally add a thin HTTP layer after the pure Python service contract stabilizes
```

- [ ] **Step 5: Stage ledger and plan/spec docs**

Run:

```powershell
git add docs/superpowers/specs/2026-05-03-amadeus-k-product-core-design.md docs/superpowers/plans/2026-05-03-amadeus-k-product-core.md program.md
```

- [ ] **Step 6: Review staged file list**

Run:

```powershell
git diff --cached --name-only
```

Expected: only product-core files, tests, docs, and `program.md`. The output must not include unrelated tracked deletions such as `frontend/` or `docker/sandbox_phase2/Dockerfile`.

- [ ] **Step 7: Commit only after explicit approval**

If the user asks for a commit, run:

```powershell
git commit -m "feat: add amadeus-k product core contract"
```

If the user does not ask for a commit, leave changes unstaged or staged according to their preference and report the exact validation output.

---

## Self-Review

Spec coverage:

- Product package location is covered by Task 1.
- Product schemas are covered by Task 2.
- Capability statuses are covered by Task 3.
- Avatar-state derivation is covered by Task 4.
- Existing-backend adapter is covered by Task 5.
- Backend service facade is covered by Task 6.
- Frontend TypeScript contract and JSON examples are covered by Task 7.
- Frontend handoff, product boundary, and demo/thesis docs are covered by Task 8.
- Verification and ledger update are covered by Task 9.

Placeholder scan:

- The plan contains no `TBD`, `TODO`, or unspecified code locations.
- Approval endpoint implementation is deliberately not included in this first backend-only product core because no HTTP layer is added today.

Type consistency:

- Python schema names match TypeScript interface names.
- `avatar_state` fields match across Python, TypeScript, examples, and docs.
- Capability status literals match across Python and TypeScript.
- Product schema version is consistently `amadeus-k.product.v1`.
