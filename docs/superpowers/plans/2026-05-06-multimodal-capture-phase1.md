# Multimodal Capture Phase 1 Plan

## Goal

Implement consent-bound multimodal source artifacts and carry them through perception and digital-body hints without opening live capture.

## Tasks

- Add `amadeus_thread0/runtime/multimodal_sources.py`.
- Normalize phase-1 source artifacts with consent, digest, status, and blocked capture reasons.
- Build `multimodal_observation` perception events with `digital_body_hints`.
- Extend perception/body tests for `artifact_carrier=multimodal_source`.
- Add deterministic smokes and an audit runner.

## Validation

- `python -m pytest tests/test_multimodal_sources.py tests/test_perception_event_contract.py tests/test_digital_body_runtime.py -q`
- `python -m pytest tests/test_multimodal_capture_audit.py -q`
- `python evals/run_multimodal_capture_smokes.py --run-tag phase1-dev`
- `python evals/run_multimodal_capture_audit.py --run-tag phase1-dev`
