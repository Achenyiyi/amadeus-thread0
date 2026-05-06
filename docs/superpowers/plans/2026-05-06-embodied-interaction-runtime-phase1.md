# Embodied Interaction Runtime Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the already unlocked multimodal source-artifact lane and Chinese semantic de-scaffolding lane to real turn/runtime payloads without opening live capture, persona-core mutation, prompt sprawl, memory authority, or external mutation.

**Architecture:** Add one pure runtime readback adapter under `amadeus_thread0/runtime/embodied_interaction_runtime.py`. It normalizes current-turn perception source artifacts from existing multimodal source contracts, mirrors them into digital-body resource and carryover surfaces, and applies a conservative deterministic Chinese semantic floor to final text/readback when known brittle families are detected. `BackendAPI` attaches the same `embodied_interaction` block to `assistant_turn` and `event_round` payloads after payload construction, similar to `living_loop_realism`.

**Tech Stack:** Python 3, existing LangGraph backend state dictionaries, existing `multimodal_sources.py`, existing `chinese_semantic_surface.py`, pytest, deterministic local eval runners.

---

## File Structure

- Create `amadeus_thread0/runtime/embodied_interaction_runtime.py`
  - Owns pure normalization/readback for embodied interaction runtime phase 1.
  - Reads existing source artifacts and Chinese semantic helpers.
  - Does not execute tools, call model APIs, mutate memory, install skills, or open live capture.
- Create `tests/test_embodied_interaction_runtime.py`
  - Unit tests for source normalization, blocked live capture, carryover mirroring, semantic floor behavior, and compact line formatting.
- Modify `amadeus_thread0/runtime/backend_api.py`
  - Imports the runtime adapter.
  - Calls it for `assistant_turn` and `event_round`.
  - Uses the possibly floor-adjusted final text in payload and reconsolidation readback while keeping TTS/final text singular.
- Extend `tests/test_backend_api.py`
  - Adds backend payload assertions for `embodied_interaction`, `current_event.perception_sources`, `digital_body.resource_state.multimodal_source_refs`, and `interaction_carryover.embodied_context.multimodal_sources`.
  - Adds final-text semantic floor alignment assertion.
- Create `evals/run_embodied_interaction_runtime_audit.py`
  - Deterministic report runner for the new phase.
- Create `tests/test_embodied_interaction_runtime_audit.py`
  - Verifies audit readiness, markdown rendering, and failure behavior.
- Modify `evals/run_preserved_baselines_audit.py`
  - Adds a new preserved baseline row:
    - id `embodied_interaction_runtime_phase1`
    - prefix `embodied-interaction-runtime-audit-`
    - readiness `embodied_interaction_runtime_phase1_ready`
    - category `embodied_interaction`
- Extend `tests/test_preserved_baselines_audit.py`
  - Updates expected id set and category assertions.
- Modify `AGENTS.md`
  - Adds the new closed phase contract after implementation passes.
- Modify `docs/engineering/PROJECT_STRUCTURE.md`
  - Documents ownership of `embodied_interaction_runtime.py` and audit entrypoint.
- Modify `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
  - Records the phase as runtime integration, not readback-only.
- Modify `program.md`
  - Updates current state and run ledger.

---

### Task 1: Runtime Adapter Tests And Implementation

**Files:**
- Create: `tests/test_embodied_interaction_runtime.py`
- Create: `amadeus_thread0/runtime/embodied_interaction_runtime.py`

- [ ] **Step 1: Write the failing runtime adapter tests**

Create `tests/test_embodied_interaction_runtime.py` with:

```python
from __future__ import annotations

from amadeus_thread0.runtime.embodied_interaction_runtime import (
    EMBODIED_INTERACTION_PHASE1_READINESS,
    build_embodied_interaction_readback,
    compact_embodied_interaction_line,
)


def _turn_with_sources() -> dict:
    return {
        "final_text": "请问有什么可以帮你？",
        "current_event": {
            "kind": "multimodal_observation",
            "text": "panel.png",
            "digital_body_hints": {
                "multimodal_sources": [
                    {
                        "source_id": "img-runtime-1",
                        "modality": "image",
                        "path": "fixtures/panel.png",
                        "consent_scope": "single_turn",
                        "capture_method": "operator_attached_file",
                        "label": "panel.png",
                    }
                ]
            },
        },
        "digital_body": {
            "resource_state": {
                "artifact_continuity": "attached",
                "active_artifact_kind": "image",
                "active_artifact_ref": "fixtures/panel.png",
                "active_artifact_label": "panel.png",
            }
        },
        "interaction_carryover": {"embodied_context": {"kind": "multimodal_observation"}},
        "reconsolidation_snapshot": {"final_text": "请问有什么可以帮你？"},
    }


def test_readback_promotes_available_source_to_runtime_surfaces():
    readback = build_embodied_interaction_readback(_turn_with_sources())

    assert readback["schema"] == "embodied_interaction.runtime.v1"
    assert readback["readiness_status"] == EMBODIED_INTERACTION_PHASE1_READINESS
    assert readback["source_status"]["available_count"] == 1
    assert readback["current_event"]["perception_sources"][0]["source_ref_id"] == "img-runtime-1"
    assert readback["current_event"]["perception_sources"][0]["source_kind"] == "image_file"
    assert readback["digital_body"]["resource_state"]["multimodal_source_refs"] == ["img-runtime-1"]
    assert readback["interaction_carryover"]["embodied_context"]["multimodal_sources"][0]["source_ref_id"] == "img-runtime-1"
    assert readback["authority_boundary"]["live_microphone_enabled"] is False
    assert readback["authority_boundary"]["live_camera_enabled"] is False


def test_blocked_live_capture_stays_blocked_and_not_written_as_available():
    turn = {
        "current_event": {
            "digital_body_hints": {
                "multimodal_sources": [
                    {
                        "source_id": "mic-live",
                        "modality": "audio",
                        "artifact_ref": "live:microphone",
                        "consent_scope": "single_turn",
                        "capture_method": "background_microphone",
                    }
                ]
            }
        }
    }

    readback = build_embodied_interaction_readback(turn)

    assert readback["overall_status"] == "in_progress"
    assert readback["readiness_status"] == "embodied_interaction_runtime_phase1_in_progress"
    assert readback["source_status"]["available_count"] == 0
    assert readback["source_status"]["blocked_count"] == 1
    assert readback["source_status"]["blocked_sources"][0]["source_ref_id"] == "mic-live"
    assert "blocked_capture_method" in readback["source_status"]["blocked_sources"][0]["block_reasons"]


def test_chinese_semantic_floor_updates_final_and_snapshot_text_together():
    readback = build_embodied_interaction_readback(_turn_with_sources())

    semantic = readback["chinese_semantic_surface"]
    assert semantic["status"] == "floor_rewritten"
    assert semantic["applied_floor"] is True
    assert semantic["runtime_final_text"] == "嗯，我在。你直接说吧，我会顺着这轮的语境接住。"
    assert readback["final_text"] == semantic["runtime_final_text"]
    assert readback["reconsolidation_snapshot"]["final_text"] == semantic["runtime_final_text"]


def test_no_sources_and_no_semantic_residue_remains_not_applicable_without_breaking_payloads():
    readback = build_embodied_interaction_readback(
        {"final_text": "嗯，我听见了。", "reconsolidation_snapshot": {"final_text": "嗯，我听见了。"}}
    )

    assert readback["overall_status"] == "not_applicable"
    assert readback["readiness_status"] == "embodied_interaction_runtime_phase1_not_applicable"
    assert readback["source_status"]["available_count"] == 0
    assert readback["chinese_semantic_surface"]["status"] == "no_semantic_residue"
    assert readback["final_text"] == "嗯，我听见了。"


def test_compact_line_names_sources_semantics_and_boundaries():
    line = compact_embodied_interaction_line(build_embodied_interaction_readback(_turn_with_sources()))

    assert "embodied_interaction=embodied_interaction_runtime_phase1_ready" in line
    assert "sources=1" in line
    assert "semantic_floor=floor_rewritten" in line
    assert "live_capture=false" in line
```

- [ ] **Step 2: Run runtime adapter tests to verify RED**

Run:

```powershell
python -m pytest tests/test_embodied_interaction_runtime.py -q
```

Expected: FAIL because `amadeus_thread0.runtime.embodied_interaction_runtime` does not exist.

- [ ] **Step 3: Implement the runtime adapter**

Create `amadeus_thread0/runtime/embodied_interaction_runtime.py` with:

```python
from __future__ import annotations

from typing import Any

from ..graph_parts.chinese_semantic_surface import rewrite_semantic_surface_floor
from .multimodal_sources import normalize_multimodal_source


EMBODIED_INTERACTION_PHASE1_READINESS = "embodied_interaction_runtime_phase1_ready"
EMBODIED_INTERACTION_PHASE1_IN_PROGRESS = "embodied_interaction_runtime_phase1_in_progress"
EMBODIED_INTERACTION_PHASE1_NOT_APPLICABLE = "embodied_interaction_runtime_phase1_not_applicable"

AUTHORITY_BOUNDARY = {
    "persona_core_mutation_allowed": False,
    "memory_write_allowed": False,
    "external_mutation_allowed": False,
    "live_microphone_enabled": False,
    "live_camera_enabled": False,
    "background_screen_capture_enabled": False,
    "secret_capture_enabled": False,
    "prompt_sprawl_rewrite_allowed": False,
    "multimodal_model_api_called": False,
}

SOURCE_KIND_BY_MODALITY = {
    "text": "text",
    "image": "image_file",
    "audio": "audio_file",
    "screen": "screen_snapshot_file",
    "browser_capture": "browser_capture_ref",
}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _source_ref(source: dict[str, Any]) -> dict[str, Any]:
    modality = _clean(source.get("modality"))
    return {
        "source_ref_id": _clean(source.get("source_id")),
        "source_kind": SOURCE_KIND_BY_MODALITY.get(modality, modality or "unknown"),
        "modality": modality,
        "source_role": _clean(source.get("source_role")),
        "artifact_ref": _clean(source.get("artifact_ref")),
        "artifact_label": _clean(source.get("artifact_label")),
        "artifact_carrier": _clean(source.get("artifact_carrier")),
        "consent_scope": _clean(source.get("consent_scope")),
        "capture_method": _clean(source.get("capture_method")),
        "payload_digest": _clean(source.get("payload_digest")),
        "status": _clean(source.get("status")),
        "block_reasons": list(source.get("block_reasons") or []),
    }


def _candidate_sources(turn: dict[str, Any]) -> list[dict[str, Any]]:
    current_event = _dict_or_empty(turn.get("current_event"))
    perception = _dict_or_empty(current_event.get("perception"))
    event_hints = _dict_or_empty(current_event.get("digital_body_hints"))
    perception_hints = _dict_or_empty(perception.get("digital_body_hints"))
    session_context = _dict_or_empty(turn.get("session_context"))
    session_hints = _dict_or_empty(session_context.get("digital_body_hints"))
    digital_body = _dict_or_empty(turn.get("digital_body"))
    resource_state = _dict_or_empty(digital_body.get("resource_state"))
    embodied = _dict_or_empty(_dict_or_empty(turn.get("interaction_carryover")).get("embodied_context"))

    rows: list[dict[str, Any]] = []
    for holder in (event_hints, perception_hints, session_hints, resource_state, embodied):
        single = holder.get("multimodal_source")
        if isinstance(single, dict):
            rows.append(single)
        for item in _list_or_empty(holder.get("multimodal_sources")):
            if isinstance(item, dict):
                rows.append(item)
    for item in _list_or_empty(current_event.get("perception_sources")):
        if isinstance(item, dict):
            rows.append(item)
    return rows


def normalize_embodied_interaction_sources(turn: dict[str, Any] | None) -> dict[str, Any]:
    data = _dict_or_empty(turn)
    available: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in _candidate_sources(data):
        source = normalize_multimodal_source(raw)
        source_ref = _source_ref(source)
        key = source_ref["source_ref_id"] or source_ref["payload_digest"]
        if not key or key in seen:
            continue
        seen.add(key)
        if source_ref["status"] == "available":
            available.append(source_ref)
        else:
            blocked.append(source_ref)
    return {
        "available_sources": available,
        "blocked_sources": blocked,
        "available_count": len(available),
        "blocked_count": len(blocked),
        "source_ref_ids": [item["source_ref_id"] for item in available if item.get("source_ref_id")],
    }


def _current_event_patch(sources: dict[str, Any]) -> dict[str, Any]:
    return {"perception_sources": list(sources.get("available_sources") or [])}


def _digital_body_patch(turn: dict[str, Any], sources: dict[str, Any]) -> dict[str, Any]:
    digital_body = _dict_or_empty(turn.get("digital_body"))
    resource_state = _dict_or_empty(digital_body.get("resource_state"))
    refs = list(sources.get("source_ref_ids") or [])
    if refs:
        resource_state["multimodal_source_refs"] = refs
        first = (sources.get("available_sources") or [{}])[0]
        resource_state.setdefault("artifact_carrier", first.get("artifact_carrier") or "multimodal_source")
        resource_state.setdefault("active_artifact_kind", first.get("modality") or "")
        resource_state.setdefault("active_artifact_ref", first.get("artifact_ref") or "")
        resource_state.setdefault("active_artifact_label", first.get("artifact_label") or "")
        resource_state.setdefault("artifact_continuity", "attached")
    digital_body["resource_state"] = resource_state
    return digital_body


def _carryover_patch(turn: dict[str, Any], sources: dict[str, Any]) -> dict[str, Any]:
    carryover = _dict_or_empty(turn.get("interaction_carryover"))
    embodied = _dict_or_empty(carryover.get("embodied_context"))
    available = list(sources.get("available_sources") or [])
    if available:
        embodied["multimodal_sources"] = available
        embodied.setdefault("kind", "multimodal_observation")
        embodied.setdefault("artifact_continuity", "attached")
        embodied.setdefault("artifact_carrier", available[0].get("artifact_carrier") or "multimodal_source")
    carryover["embodied_context"] = embodied
    return carryover


def _semantic_runtime_floor(turn: dict[str, Any]) -> dict[str, Any]:
    final_text = _clean(turn.get("final_text"))
    result = rewrite_semantic_surface_floor(final_text)
    runtime_text = _clean(result.get("safe_surface_floor")) or final_text
    return {
        "status": _clean(result.get("status")) or "no_semantic_residue",
        "families": list(result.get("families") or []),
        "applied_floor": bool(result.get("applied_floor", False)),
        "original_text": final_text,
        "runtime_final_text": runtime_text,
        "replacement_plan": _dict_or_empty(result.get("replacement_plan")),
    }


def build_embodied_interaction_readback(turn: dict[str, Any] | None) -> dict[str, Any]:
    data = _dict_or_empty(turn)
    sources = normalize_embodied_interaction_sources(data)
    semantic = _semantic_runtime_floor(data)
    available = int(sources.get("available_count") or 0)
    blocked = int(sources.get("blocked_count") or 0)
    semantic_applied = bool(semantic.get("applied_floor", False))
    if available > 0 and blocked == 0:
        overall = "passed"
        readiness = EMBODIED_INTERACTION_PHASE1_READINESS
    elif available > 0 and blocked > 0:
        overall = "in_progress"
        readiness = EMBODIED_INTERACTION_PHASE1_IN_PROGRESS
    elif blocked > 0:
        overall = "in_progress"
        readiness = EMBODIED_INTERACTION_PHASE1_IN_PROGRESS
    elif semantic_applied:
        overall = "passed"
        readiness = EMBODIED_INTERACTION_PHASE1_READINESS
    else:
        overall = "not_applicable"
        readiness = EMBODIED_INTERACTION_PHASE1_NOT_APPLICABLE

    runtime_text = _clean(semantic.get("runtime_final_text")) or _clean(data.get("final_text"))
    reconsolidation_snapshot = _dict_or_empty(data.get("reconsolidation_snapshot"))
    if runtime_text:
        reconsolidation_snapshot["final_text"] = runtime_text

    return {
        "phase": "Embodied Interaction Runtime Phase 1",
        "schema": "embodied_interaction.runtime.v1",
        "overall_status": overall,
        "readiness_status": readiness,
        "final_text": runtime_text,
        "current_event": _current_event_patch(sources),
        "digital_body": _digital_body_patch(data, sources),
        "interaction_carryover": _carryover_patch(data, sources),
        "reconsolidation_snapshot": reconsolidation_snapshot,
        "source_status": sources,
        "chinese_semantic_surface": semantic,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "failure_reasons": [f"blocked_source:{item.get('source_ref_id')}" for item in sources.get("blocked_sources") or []],
    }


def apply_embodied_interaction_readback_to_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    data = _dict_or_empty(payload)
    readback = build_embodied_interaction_readback(data)
    data["embodied_interaction"] = readback
    if readback.get("final_text"):
        data["final_text"] = str(readback.get("final_text") or "")
    if isinstance(readback.get("current_event"), dict):
        current_event = _dict_or_empty(data.get("current_event"))
        current_event.update(readback["current_event"])
        data["current_event"] = current_event
    if isinstance(readback.get("digital_body"), dict):
        data["digital_body"] = dict(readback["digital_body"])
    if isinstance(readback.get("interaction_carryover"), dict):
        data["interaction_carryover"] = dict(readback["interaction_carryover"])
    if isinstance(readback.get("reconsolidation_snapshot"), dict):
        data["reconsolidation_snapshot"] = dict(readback["reconsolidation_snapshot"])
    return data


def compact_embodied_interaction_line(readback: dict[str, Any] | None) -> str:
    data = _dict_or_empty(readback)
    if not data:
        return ""
    source_status = _dict_or_empty(data.get("source_status"))
    semantic = _dict_or_empty(data.get("chinese_semantic_surface"))
    boundary = _dict_or_empty(data.get("authority_boundary"))
    live_capture = any(
        bool(boundary.get(key, False))
        for key in ("live_microphone_enabled", "live_camera_enabled", "background_screen_capture_enabled")
    )
    parts = [
        f"embodied_interaction={_clean(data.get('readiness_status')) or 'unknown'}",
        f"sources={int(source_status.get('available_count') or 0)}",
        f"blocked={int(source_status.get('blocked_count') or 0)}",
        f"semantic_floor={_clean(semantic.get('status')) or 'unknown'}",
        f"live_capture={str(live_capture).lower()}",
    ]
    return " | ".join(parts)


__all__ = [
    "AUTHORITY_BOUNDARY",
    "EMBODIED_INTERACTION_PHASE1_IN_PROGRESS",
    "EMBODIED_INTERACTION_PHASE1_NOT_APPLICABLE",
    "EMBODIED_INTERACTION_PHASE1_READINESS",
    "apply_embodied_interaction_readback_to_payload",
    "build_embodied_interaction_readback",
    "compact_embodied_interaction_line",
    "normalize_embodied_interaction_sources",
]
```

- [ ] **Step 4: Run runtime adapter tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_embodied_interaction_runtime.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

Run:

```powershell
git add amadeus_thread0/runtime/embodied_interaction_runtime.py tests/test_embodied_interaction_runtime.py docs/superpowers/plans/2026-05-06-embodied-interaction-runtime-phase1.md
git commit -m "feat: add embodied interaction runtime adapter"
```

Expected: commit succeeds.

---

### Task 2: Backend Payload Attachment

**Files:**
- Modify: `amadeus_thread0/runtime/backend_api.py`
- Modify: `tests/test_backend_api.py`

- [ ] **Step 1: Write failing backend payload tests**

Append tests to `tests/test_backend_api.py` inside `BackendApiTests`:

```python
    def test_turn_and_event_responses_attach_embodied_interaction_readback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "final_text": "嗯，我听见了。",
                "current_event": {
                    "kind": "multimodal_observation",
                    "text": "panel.png",
                    "digital_body_hints": {
                        "multimodal_sources": [
                            {
                                "source_id": "img-backend-1",
                                "modality": "image",
                                "path": "fixtures/panel.png",
                                "consent_scope": "single_turn",
                                "capture_method": "operator_attached_file",
                                "label": "panel.png",
                            }
                        ]
                    },
                },
                "digital_body_state": {
                    "active_surface": "image",
                    "perception_channels": ["image"],
                    "action_channels": ["language"],
                    "world_surfaces": [],
                    "access_state": {"mode": "native_only"},
                    "resource_state": {
                        "artifact_continuity": "attached",
                        "active_artifact_kind": "image",
                        "active_artifact_ref": "fixtures/panel.png",
                        "active_artifact_label": "panel.png",
                    },
                },
                "interaction_carryover": {"embodied_context": {"kind": "multimodal_observation"}},
                "reconsolidation_snapshot": {"final_text": "嗯，我听见了。"},
            }

            turn_payload = api.build_turn_response(state_values=state_values, streamed_text="ignored").payload
            event_payload = api.build_event_round_response(state_values=state_values, final_text="嗯，我听见了。").payload

            for payload in (turn_payload, event_payload):
                readback = payload["embodied_interaction"]
                self.assertEqual(readback["schema"], "embodied_interaction.runtime.v1")
                self.assertEqual(readback["readiness_status"], "embodied_interaction_runtime_phase1_ready")
                self.assertEqual(payload["current_event"]["perception_sources"][0]["source_ref_id"], "img-backend-1")
                self.assertEqual(payload["current_event"]["perception_sources"][0]["source_kind"], "image_file")
                self.assertEqual(payload["digital_body"]["resource_state"]["multimodal_source_refs"], ["img-backend-1"])
                self.assertEqual(
                    payload["interaction_carryover"]["embodied_context"]["multimodal_sources"][0]["source_ref_id"],
                    "img-backend-1",
                )

    def test_turn_response_applies_chinese_semantic_floor_to_final_and_snapshot_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "final_text": "请问有什么可以帮你？",
                "reconsolidation_snapshot": {"final_text": "请问有什么可以帮你？"},
            }

            payload = api.build_turn_response(state_values=state_values, streamed_text="ignored").payload

            self.assertEqual(payload["final_text"], "嗯，我在。你直接说吧，我会顺着这轮的语境接住。")
            self.assertEqual(payload["reconsolidation_snapshot"]["final_text"], payload["final_text"])
            self.assertTrue(payload["embodied_interaction"]["chinese_semantic_surface"]["applied_floor"])
```

- [ ] **Step 2: Run backend payload tests to verify RED**

Run:

```powershell
python -m pytest tests/test_backend_api.py -k embodied_interaction -q
```

Expected: FAIL because backend payloads do not yet attach `embodied_interaction`.

- [ ] **Step 3: Attach readback in `backend_api.py`**

Modify imports near the current `living_loop_realism` import:

```python
from .embodied_interaction_runtime import apply_embodied_interaction_readback_to_payload
from .living_loop_realism import build_backend_payload_realism_readback
```

In both `build_event_round_response()` and `build_turn_response()`, replace:

```python
payload["living_loop_realism"] = build_backend_payload_realism_readback(payload)
return self._envelope(..., payload, ...)
```

with:

```python
payload = apply_embodied_interaction_readback_to_payload(payload)
payload["living_loop_realism"] = build_backend_payload_realism_readback(payload)
return self._envelope(..., payload, ...)
```

Keep the existing envelope kind and meta unchanged.

- [ ] **Step 4: Run backend payload tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_backend_api.py -k "embodied_interaction or living_loop_realism" -q
```

Expected: PASS.

- [ ] **Step 5: Run focused backend regression**

Run:

```powershell
python -m pytest tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py tests/test_tool_approval_policy.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

Run:

```powershell
git add amadeus_thread0/runtime/backend_api.py tests/test_backend_api.py
git commit -m "feat: attach embodied interaction to backend payloads"
```

Expected: commit succeeds.

---

### Task 3: Audit And Preserved Baseline

**Files:**
- Create: `evals/run_embodied_interaction_runtime_audit.py`
- Create: `tests/test_embodied_interaction_runtime_audit.py`
- Modify: `evals/run_preserved_baselines_audit.py`
- Modify: `tests/test_preserved_baselines_audit.py`

- [ ] **Step 1: Write failing audit tests**

Create `tests/test_embodied_interaction_runtime_audit.py` with:

```python
from __future__ import annotations

from evals.run_embodied_interaction_runtime_audit import build_report, render_markdown


def test_build_report_returns_phase1_ready():
    report = build_report(run_id="unit")

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "embodied_interaction_runtime_phase1_ready"
    assert report["summary"]["available_source_count"] >= 3
    assert report["summary"]["blocked_source_count"] == 1
    assert report["summary"]["semantic_floor_applied"] is True


def test_render_markdown_includes_source_and_semantic_status():
    rendered = render_markdown(build_report(run_id="unit-md"))

    assert "# Embodied Interaction Runtime Phase 1 Audit" in rendered
    assert "`embodied_interaction_runtime_phase1_ready`" in rendered
    assert "| `image_file_source_enters_perception` | `passed` |" in rendered
    assert "| `blocked_live_capture_stays_blocked` | `passed` |" in rendered
    assert "| `chinese_semantic_surface_runtime_floor` | `passed` |" in rendered
```

Modify `tests/test_preserved_baselines_audit.py` expected id set to include:

```python
"embodied_interaction_runtime_phase1",
```

And add category assertion in `test_evaluate_preserved_baselines_passes_when_all_latest_reports_are_ready`:

```python
self.assertEqual(summary["summary"]["categories"]["embodied_interaction"]["passed"], 1)
```

- [ ] **Step 2: Run audit tests to verify RED**

Run:

```powershell
python -m pytest tests/test_embodied_interaction_runtime_audit.py tests/test_preserved_baselines_audit.py -q
```

Expected: FAIL because the audit entrypoint and preserved-baseline row do not exist yet.

- [ ] **Step 3: Implement audit runner**

Create `evals/run_embodied_interaction_runtime_audit.py` with:

```python
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

from amadeus_thread0.runtime.embodied_interaction_runtime import build_embodied_interaction_readback


def _turn(source: dict[str, Any], *, final_text: str = "嗯，我听见了。") -> dict[str, Any]:
    return {
        "final_text": final_text,
        "current_event": {"digital_body_hints": {"multimodal_sources": [source]}},
        "interaction_carryover": {"embodied_context": {}},
        "reconsolidation_snapshot": {"final_text": final_text},
    }


SCENARIOS = {
    "image_file_source_enters_perception": _turn(
        {
            "source_id": "img-audit-1",
            "modality": "image",
            "path": "fixtures/panel.png",
            "consent_scope": "single_turn",
            "capture_method": "operator_attached_file",
            "label": "panel.png",
        }
    ),
    "audio_file_source_enters_perception": _turn(
        {
            "source_id": "audio-audit-1",
            "modality": "audio",
            "path": "fixtures/voice.wav",
            "consent_scope": "single_turn",
            "capture_method": "operator_attached_file",
            "label": "voice.wav",
        }
    ),
    "browser_capture_ref_enters_continuity": _turn(
        {
            "source_id": "browser-cap-audit-1",
            "modality": "browser_capture",
            "artifact_ref": "browser-capture:page-7",
            "consent_scope": "saved_material_review",
            "capture_method": "browser_runtime_capture_ref",
            "source_role": "runtime",
        }
    ),
    "blocked_live_capture_stays_blocked": _turn(
        {
            "source_id": "mic-live-audit",
            "modality": "audio",
            "artifact_ref": "live:microphone",
            "consent_scope": "single_turn",
            "capture_method": "background_microphone",
        }
    ),
    "chinese_semantic_surface_runtime_floor": {
        "final_text": "请问有什么可以帮你？",
        "reconsolidation_snapshot": {"final_text": "请问有什么可以帮你？"},
    },
}


def _evaluate_scenario(name: str, turn: dict[str, Any]) -> dict[str, Any]:
    readback = build_embodied_interaction_readback(turn)
    source_status = readback.get("source_status") if isinstance(readback.get("source_status"), dict) else {}
    semantic = readback.get("chinese_semantic_surface") if isinstance(readback.get("chinese_semantic_surface"), dict) else {}
    passed = False
    if name == "blocked_live_capture_stays_blocked":
        passed = int(source_status.get("blocked_count") or 0) == 1 and int(source_status.get("available_count") or 0) == 0
    elif name == "chinese_semantic_surface_runtime_floor":
        passed = bool(semantic.get("applied_floor")) and readback.get("final_text") == semantic.get("runtime_final_text")
    else:
        passed = int(source_status.get("available_count") or 0) == 1 and readback.get("readiness_status") == "embodied_interaction_runtime_phase1_ready"
    return {
        "name": name,
        "status": "passed" if passed else "failed",
        "readiness_status": readback.get("readiness_status"),
        "source_status": source_status,
        "semantic_status": semantic.get("status"),
        "readback": readback,
    }


def build_report(*, run_id: str) -> dict[str, Any]:
    scenarios = [_evaluate_scenario(name, turn) for name, turn in SCENARIOS.items()]
    failed = [row["name"] for row in scenarios if row["status"] != "passed"]
    available_source_count = sum(int((row.get("source_status") or {}).get("available_count") or 0) for row in scenarios)
    blocked_source_count = sum(int((row.get("source_status") or {}).get("blocked_count") or 0) for row in scenarios)
    semantic_floor_applied = any(
        bool((row.get("readback") or {}).get("chinese_semantic_surface", {}).get("applied_floor"))
        for row in scenarios
        if isinstance(row.get("readback"), dict)
    )
    overall = "passed" if not failed else "failed"
    return {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": overall,
        "readiness_status": "embodied_interaction_runtime_phase1_ready" if overall == "passed" else "embodied_interaction_runtime_phase1_in_progress",
        "summary": {
            "scenario_count": len(scenarios),
            "available_source_count": available_source_count,
            "blocked_source_count": blocked_source_count,
            "semantic_floor_applied": semantic_floor_applied,
        },
        "failure_reasons": failed,
        "scenarios": scenarios,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Embodied Interaction Runtime Phase 1 Audit",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
        "",
        "## Summary",
        "",
        f"- Available source count: `{report.get('summary', {}).get('available_source_count', 0)}`",
        f"- Blocked source count: `{report.get('summary', {}).get('blocked_source_count', 0)}`",
        f"- Semantic floor applied: `{report.get('summary', {}).get('semantic_floor_applied', False)}`",
        "",
        "## Scenarios",
        "",
        "| Scenario | Status | Readiness |",
        "| --- | --- | --- |",
    ]
    for row in report.get("scenarios") or []:
        lines.append(f"| `{row.get('name', '')}` | `{row.get('status', '')}` | `{row.get('readiness_status', '')}` |")
    reasons = list(report.get("failure_reasons") or [])
    lines.extend(["", "## Failure Reasons", ""])
    if reasons:
        lines.extend(f"- `{reason}`" for reason in reasons)
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run embodied interaction runtime phase 1 audit.")
    parser.add_argument("--run-tag", default="")
    args = parser.parse_args()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    report = build_report(run_id=run_id)
    json_path = REPORT_DIR / f"embodied-interaction-runtime-audit-{run_id}.json"
    md_path = REPORT_DIR / f"embodied-interaction-runtime-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[embodied-interaction-runtime] json={json_path}")
    print(f"[embodied-interaction-runtime] md={md_path}")
    print(f"[embodied-interaction-runtime] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[embodied-interaction-runtime] readiness={report.get('readiness_status', 'unknown')}")
    return 0 if report.get("overall_status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Register preserved baseline**

Add to `BASELINE_SPECS` in `evals/run_preserved_baselines_audit.py` after `living_loop_runtime_realism_phase2`:

```python
    {
        "id": "embodied_interaction_runtime_phase1",
        "prefix": "embodied-interaction-runtime-audit-",
        "expected_readiness": "embodied_interaction_runtime_phase1_ready",
        "category": "embodied_interaction",
    },
```

- [ ] **Step 5: Run audit tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_embodied_interaction_runtime_audit.py tests/test_preserved_baselines_audit.py -q
python evals/run_embodied_interaction_runtime_audit.py --run-tag phase1-dev
```

Expected: tests PASS and audit prints `readiness=embodied_interaction_runtime_phase1_ready`.

- [ ] **Step 6: Commit Task 3**

Run:

```powershell
git add evals/run_embodied_interaction_runtime_audit.py tests/test_embodied_interaction_runtime_audit.py evals/run_preserved_baselines_audit.py tests/test_preserved_baselines_audit.py
git commit -m "test: add embodied interaction runtime audit"
```

Expected: commit succeeds.

---

### Task 4: Documentation And Ledger Closure

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/engineering/PROJECT_STRUCTURE.md`
- Modify: `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
- Modify: `program.md`

- [ ] **Step 1: Update project contracts**

Update `AGENTS.md`:

- Add `Embodied Interaction Runtime Phase 1` under current phase/unlock contract.
- Add `embodied_interaction_runtime_phase1_ready` to preserved baselines list.
- State that this phase:
  - attaches consent-bound multimodal source artifacts to current turn/backend payload surfaces
  - attaches deterministic Chinese semantic runtime floors to final/snapshot readback
  - does not open live microphone/camera/background screen capture
  - does not call multimodal model APIs
  - does not mutate persona core, memory authority, sandbox/browser/tool authority, skill registry, or frontend semantics

Update `docs/engineering/PROJECT_STRUCTURE.md`:

- Add `embodied_interaction_runtime.py` to runtime module list.
- Document it as the runtime integration surface for multimodal source artifacts plus Chinese semantic floors.
- Add `run_embodied_interaction_runtime_audit.py` to audit entrypoints.

Update `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`:

- Add the new status to backend status and implementation order.
- Record that it is runtime integration on top of prior readback/guidance gates.

Update `program.md`:

- Update Current State mainline phase to `Embodied Interaction Runtime Phase 1`.
- Add a dated run entry with files changed, key behavior, validations, result, and next step.

- [ ] **Step 2: Run doc/placeholder scan**

Run:

```powershell
rg -n "TBD|TODO|implement later|fill in details|Similar to Task" AGENTS.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md docs/superpowers/plans/2026-05-06-embodied-interaction-runtime-phase1.md amadeus_thread0/runtime/embodied_interaction_runtime.py tests/test_embodied_interaction_runtime.py evals/run_embodied_interaction_runtime_audit.py tests/test_embodied_interaction_runtime_audit.py
```

Expected: no matches.

- [ ] **Step 3: Commit Task 4**

Run:

```powershell
git add AGENTS.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md program.md docs/superpowers/plans/2026-05-06-embodied-interaction-runtime-phase1.md
git commit -m "docs: record embodied interaction runtime phase"
```

Expected: commit succeeds.

---

### Task 5: Final Verification, Merge, And Push

**Files:**
- All files touched by Tasks 1-4.

- [ ] **Step 1: Run focused runtime and backend verification**

Run:

```powershell
python -m pytest tests/test_embodied_interaction_runtime.py tests/test_embodied_interaction_runtime_audit.py tests/test_multimodal_sources.py tests/test_chinese_semantic_surface_phase2.py tests/test_chinese_surface_de_scaffold_audit.py -q
python -m pytest tests/test_backend_api.py -k "embodied_interaction or living_loop_realism or turn_and_event_responses_attach_operator_readback" -q
```

Expected: PASS.

- [ ] **Step 2: Run required backend/memory regressions**

Run:

```powershell
python -m pytest tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py tests/test_tool_approval_policy.py -q
python -m pytest tests/test_memory_guard.py tests/test_session_orchestrator.py -q
```

Expected: PASS.

- [ ] **Step 3: Run graph entrypoint checks**

Run:

```powershell
python -m py_compile amadeus_thread0/agent.py amadeus_thread0/graph.py amadeus_thread0/runtime/embodied_interaction_runtime.py amadeus_thread0/runtime/backend_api.py evals/run_embodied_interaction_runtime_audit.py evals/run_preserved_baselines_audit.py
python -c "from amadeus_thread0.agent import agent; print(type(agent).__name__)"
```

Expected: compile passes and prints `CompiledStateGraph`.

- [ ] **Step 4: Run phase audits**

Run:

```powershell
python evals/run_embodied_interaction_runtime_audit.py --run-tag phase1-final
python evals/run_multimodal_capture_audit.py --run-tag embodied-phase1-regression
python evals/run_chinese_surface_de_scaffold_audit.py --run-tag embodied-phase1-regression
python evals/run_living_loop_realism_phase2_audit.py --run-tag embodied-phase1-regression
```

Expected:

- embodied interaction audit reports `embodied_interaction_runtime_phase1_ready`
- multimodal audit reports `multimodal_capture_phase1_ready`
- Chinese audit reports `chinese_semantic_descaffolding_phase1_ready`
- living loop phase 2 audit reports `living_loop_runtime_realism_phase2_ready`

- [ ] **Step 5: Run diff checks**

Run:

```powershell
git diff --check
git status --short --branch
```

Expected:

- no diff-check errors other than benign Windows LF-to-CRLF warnings
- only intended files are modified

- [ ] **Step 6: Commit any remaining tracked changes**

If any intended changes remain unstaged:

```powershell
git add AGENTS.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md program.md docs/superpowers/plans/2026-05-06-embodied-interaction-runtime-phase1.md amadeus_thread0/runtime/embodied_interaction_runtime.py amadeus_thread0/runtime/backend_api.py evals/run_embodied_interaction_runtime_audit.py evals/run_preserved_baselines_audit.py tests/test_embodied_interaction_runtime.py tests/test_embodied_interaction_runtime_audit.py tests/test_backend_api.py tests/test_preserved_baselines_audit.py
git commit -m "feat: close embodied interaction runtime phase 1"
```

Expected: commit succeeds or there is nothing to commit.

- [ ] **Step 7: Merge to main**

Run from primary workspace:

```powershell
git -C E:\桌面\amadeus-thread0 status --short --branch
git -C E:\桌面\amadeus-thread0 merge --ff-only codex/embodied-interaction-runtime-phase1
```

Expected:

- primary workspace remains on `main`
- merge fast-forwards
- existing untracked `third_party/benchmarks/ESConv` remains untouched

- [ ] **Step 8: Post-merge verification on main**

Run from `E:\桌面\amadeus-thread0`:

```powershell
python -m pytest tests/test_embodied_interaction_runtime.py tests/test_embodied_interaction_runtime_audit.py tests/test_backend_api.py -k "embodied_interaction or living_loop_realism" -q
python evals/run_embodied_interaction_runtime_audit.py --run-tag post-merge
python evals/run_preserved_baselines_audit.py --reports-dir evals/reports
```

Expected:

- tests PASS
- embodied interaction audit reports `embodied_interaction_runtime_phase1_ready`
- preserved baselines audit reports `preserved_baselines_ready`

- [ ] **Step 9: Push main**

Run:

```powershell
git -C E:\桌面\amadeus-thread0 push origin main
```

Expected: push succeeds.

---

## Self-Review

- Spec coverage:
  - Multimodal runtime source artifacts: Task 1 and Task 2.
  - Blocked live microphone/camera/background capture boundary: Task 1, Task 3, Task 4.
  - Chinese semantic de-scaffolding runtime final/snapshot floor: Task 1 and Task 2.
  - Backend `assistant_turn` and `event_round` payload attachment: Task 2.
  - Audit and preserved-baseline closure: Task 3 and Task 5.
  - Docs and run ledger: Task 4.
- Placeholder scan:
  - No task uses vague placeholders; all test code, module code, commands, and expected outputs are explicit.
- Type consistency:
  - The plan consistently uses `embodied_interaction`, `embodied_interaction.runtime.v1`, `embodied_interaction_runtime_phase1_ready`, `source_ref_id`, `source_kind`, `multimodal_source_refs`, and `chinese_semantic_surface`.
