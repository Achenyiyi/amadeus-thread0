---
name: Source Ref Anchor Review
description: Read-only skill for inspecting, re-anchoring, and comparing saved source materials when the current task depends on source_ref continuity.
version: 1.0.0
skill_id: source-ref-anchor-review
kind: executable
triggers:
  - source_ref
  - anchor
  - material continuity
  - compare sources
required_surfaces:
  - source_ref
allowed_tools:
  - inspect_source_ref
  - compare_source_refs
  - search_web
sandbox_profiles: []
source: local_authored
trust_tier: authored
---

## Use

- Prefer this skill when the task depends on continuing from saved source materials instead of starting a new generic search.
- Inspect the preferred saved source first.
- Only compare multiple source refs when the active anchor is stale, ambiguous, or contradicted.
- Keep the result tied to the saved source lineage so later turns can continue from the same material surface.

## Constraints

- Read-only. Do not mutate files, permissions, or session state.
- Do not treat inspected or compared materials as if they were rewritten.
