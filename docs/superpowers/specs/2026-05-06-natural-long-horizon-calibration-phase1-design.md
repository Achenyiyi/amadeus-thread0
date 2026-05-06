# Natural Long-Horizon Calibration Phase 1 Design

## Purpose

Evaluate long-horizon companionship behavior across appraisal, own-rhythm, relationship continuity, embodied continuity, and final text/TTS parity without adding scene scripts.

## Calibration Packs

- `everyday_low_stakes_7_turns`
- `repair_after_tension_9_turns`
- `self_rhythm_boundary_8_turns`
- `shared_work_continuity_10_turns`
- `embodied_artifact_resume_8_turns`
- `silence_and_deferred_return_6_turns`

## Metrics

- `final_text_tts_parity`
- `no_duplicate_output`
- `no_middle_state_leak`
- `relationship_continuity_resurfaced`
- `own_rhythm_not_subservient`
- `boundary_not_punitive`
- `embodied_context_truthful`
- `generic_assistant_tone_absent`

## Completion Gate

`python evals/run_natural_long_horizon_calibration_audit.py` must report `natural_long_horizon_calibration_phase1_ready`.
