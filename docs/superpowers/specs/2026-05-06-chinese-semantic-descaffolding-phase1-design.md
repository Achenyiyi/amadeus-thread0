# Chinese Semantic De-Scaffolding Phase 1 Design

## Purpose

Add audit-backed semantic diagnostics for brittle Chinese surface families before any broad runtime rewrite.

## Families

- `teacherly_scold`
- `meta_persona_proof`
- `generic_assistant_tone`
- `hardline_autonomy_overreach`
- `scene_script_residue`
- `taskization_of_daily_chat`
- `repair_scorekeeping`
- `boundary_threat_excess`

## Contract

The semantic classifier identifies behavior families by meaning patterns, not only exact legacy phrases. Candidate replacement semantics describe what the family should become without rewriting persona core.

## Explicit Blocks

- prompt sprawl rewrite
- persona-core redefinition
- ad hoc reply-tone micro-polish outside the phase audit

## Completion Gate

`python evals/run_chinese_surface_de_scaffold_audit.py` must report `chinese_semantic_descaffolding_phase1_ready` while preserving legacy readiness compatibility for post-baseline tracking.
