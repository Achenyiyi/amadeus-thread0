# Capability Growth Phase 5 Plan

## Goal

Add advisory workflow candidates over completed procedural traces.

## Tasks

- Add `amadeus_thread0/graph_parts/capability_growth.py`.
- Derive workflow candidates from repeated completed traces.
- Return blocked candidates when no completed evidence exists.
- Convert candidates to planning bias without claiming capability authority.
- Add smokes and an audit runner.

## Validation

- `python -m pytest tests/test_capability_growth_phase5.py tests/test_capability_growth_phase5_audit.py -q`
- `python evals/run_capability_growth_phase5_smokes.py --run-tag phase5-dev`
- `python evals/run_capability_growth_phase5_audit.py --run-tag phase5-dev`
