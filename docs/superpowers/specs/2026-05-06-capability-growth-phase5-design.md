# Capability Growth Phase 5 Design

## Purpose

Represent repeated completed procedures as advisory workflow candidates without granting tools, installing skills, or mutating persona identity.

## WorkflowCandidate Contract

```python
{
    "workflow_id": "workflow-...",
    "origin_trace_ids": ["proc-1", "proc-2"],
    "capability_family": "workspace|sandbox|browser|skill|multimodal",
    "reuse_confidence": 0.0,
    "approval_requirements": ["external_mutation"],
    "blocked_surfaces": [],
    "recommended_next_action": "reuse|propose_skill|ask_operator|hold",
    "status": "candidate",
}
```

## Rules

- Workflow candidates live inside existing procedural/body continuity.
- They may bias planning only when current access/body state supports the same bounded family.
- They do not grant new tools.
- They do not install skills.
- They never become persona-core identity.

## Completion Gate

`python evals/run_capability_growth_phase5_audit.py` must report `capability_growth_phase5_ready`.
