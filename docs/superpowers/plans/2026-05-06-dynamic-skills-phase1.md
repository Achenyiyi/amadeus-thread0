# Dynamic Skills Phase 1 Plan

## Goal

Implement proposal-only skill candidate formation from completed procedural traces.

## Tasks

- Add `amadeus_thread0/runtime/dynamic_skill_candidates.py`.
- Require completed procedural evidence before any candidate can be proposed.
- Generate draft `SKILL.md` content, source evidence refs, sandbox profiles, and hash.
- Expose approval payload helpers without mutating the registry.
- Add deterministic smokes and an audit runner.

## Validation

- `python -m pytest tests/test_dynamic_skill_candidates.py -q`
- `python -m pytest tests/test_dynamic_skills_audit.py -q`
- `python evals/run_dynamic_skills_smokes.py --run-tag phase1-dev`
- `python evals/run_dynamic_skills_audit.py --run-tag phase1-dev`
