# Chinese Semantic De-Scaffolding Phase 1 Plan

## Goal

Replace brittle audit-only Chinese phrase checks with semantic family diagnostics before runtime reply rewrites.

## Tasks

- Add `amadeus_thread0/graph_parts/chinese_semantic_surface.py`.
- Extend the Chinese surface audit with semantic family detection.
- Preserve `legacy_readiness_status` for existing post-baseline closure compatibility.
- Add tests for meaning-based detection beyond exact legacy phrases.

## Validation

- `python -m pytest tests/test_chinese_surface_de_scaffold_audit.py -q`
- `python evals/run_chinese_surface_de_scaffold_audit.py --run-tag semantic-phase1`
