# Dynamic Skills Phase 1 Design

## Purpose

Allow completed procedural evidence to produce registry-backed skill candidates without installing, enabling, or executing generated skills automatically.

## SkillCandidate Contract

```python
{
    "candidate_id": "skill-candidate-...",
    "origin": "procedural_trace|operator_request|source_ref_review",
    "skill_id": "workspace-regression-triage",
    "draft_skill_md": "...",
    "source_evidence_refs": ["..."],
    "requested_permissions": [],
    "sandbox_profiles": ["docker_local_isolated"],
    "hash": "...",
    "status": "proposed",
    "requires_approval": True,
}
```

## Explicit Blocks

- auto-install
- auto-enable
- persona-core patching
- registry write without approval
- host-side executable generation outside the registry candidate area

## Completion Gate

`python evals/run_dynamic_skills_audit.py` must report `dynamic_skills_phase1_ready`.
