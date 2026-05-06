# Natural Long-Horizon Calibration Phase 1 Plan

## Goal

Add deterministic offline calibration coverage for the preserved lifeform loop without live model calls.

## Tasks

- Add `evals/long_horizon_calibration_bank.json`.
- Add calibration smoke/audit runners.
- Fail on duplicate output, middle-state leak, punitive boundary, generic assistant tone, embodied untruth, or text/TTS drift flags.
- Keep calibration evaluation offline and deterministic.

## Validation

- `python -m pytest tests/test_natural_long_horizon_calibration_audit.py -q`
- `python evals/run_natural_long_horizon_calibration_smokes.py --run-tag phase1-dev`
- `python evals/run_natural_long_horizon_calibration_audit.py --run-tag phase1-dev`
