# Procedural Growth Phase 2 Design

## Goal

Open `Procedural Growth Phase 2: Procedure-Guided Autonomy Planning`.

Phase 1 made completed embodied actions produce bounded procedural traces. Phase 2 lets those traces influence the next autonomy/action planning step as advisory planning bias while preserving all approval, sandbox, browser, skills, memory, and persona-core boundaries.

This phase does not add a new executor, new browser authority, dynamic skill creation, a second memory store, or frontend work.

## Product Boundary

The product remains backend-first: `CLI + TTS + evals`.

This phase may touch graph-adjacent autonomy planning, backend readback, CLI summaries, tests, evals, and engineering docs.

This phase must not introduce:

- desktop or web frontend work
- package installation
- wider sandbox command families
- shell wrappers
- automatic browser mutation
- dynamic `SKILL.md` generation
- external executor harness runtime
- registry/install truth in autobiographical memory
- persona-core, relationship-core, or system-prompt identity edits
- a second procedural/work memory store

## Recommended Architecture

Add `amadeus_thread0/graph_parts/procedural_planning.py` as a pure advisory layer.

The layer reads current event text, current digital-body access hints, and carried embodied procedural context. It returns a compact `procedural_planning` bias. It does not execute tools and does not itself create facts.

Canonical Phase 2 loop:

```text
interaction_carryover.embodied_context.procedural_traces
-> procedural planning bias extraction / ranking
-> autonomy runtime considers the bias
-> action_packet is still generated through existing bounded packet rules
-> backend/CLI expose which trace influenced planning
-> final writeback still depends only on completed/blocked packet truth
```

## Planning Bias Shape

The bias should be compact and safe for backend/API/CLI readback:

```python
{
    "planning_bias": True,
    "bias_kind": "sandbox_execute",
    "trace_id": "proc_...",
    "trace_kind": "sandbox_execution_pattern",
    "source_run_id": "run-...",
    "source_proposal_id": "ap-...",
    "source_tool_name": "execute_workspace_command",
    "suggested_capability_family": "sandbox",
    "suggested_pattern": "pytest",
    "suggested_executor": "pytest",
    "suggested_argv": ["pytest"],
    "suggested_profile": "pytest",
    "suggested_first_step": "run bounded command",
    "must_request_approval": True,
    "requires_approval": True,
    "capability_claim": True,
    "avoid_repeating_boundary": False,
    "boundary_note": "requires approval before execution",
    "confidence": 0.74,
    "reason": "reuse a completed bounded sandbox pytest procedure",
}
```

Allowed `bias_kind` values:

- `sandbox_execute`
- `browser_manual_takeover`
- `skill_guidance`
- `workspace_guidance`
- `boundary_only`

If no trace is relevant or safe, the helper returns `{}`.

## Source And Ranking Rules

Read candidate traces from:

- `interaction_carryover.embodied_context.procedural_traces`
- `interaction_carryover.embodied_context.procedural_continuity.traces`
- `interaction_carryover.embodied_context.procedural_hint` as a fallback when traces are absent

Ranking rules:

- normalize and dedupe traces by `trace_id`
- ignore traces below confidence `0.35`
- prefer traces that match the current request text
- prefer completed capability traces over blocked traces when both are relevant
- preserve manual-takeover and approval markers even when they lower automation priority
- ignore workspace-root, runner, isolation, or network-policy mismatches for execution-producing bias

Current request matching should stay intentionally small and deterministic:

- sandbox `pytest` traces match user text containing `pytest`, `test`, `tests`, `测试`, or `检查`
- sandbox `rg_search` traces match `rg`, `search`, `grep`, `检索`, `搜索`, or `查找`
- read-only `git_status` / `git_diff` traces match their explicit command family
- browser manual-takeover traces match browser/login/session continuation language
- skill traces match skill-supported/source-ref/artifact continuation language

The helper may produce readback-only `skill_guidance`, `workspace_guidance`, or `boundary_only` bias even when it does not produce an action packet.

## Autonomy Integration

`derive_autonomy_runtime()` should compute `procedural_planning` before selecting a procedural packet.

The bias can replace the older implicit procedural-continuity packet path only when:

- `bias_kind == "sandbox_execute"`
- `capability_claim == True`
- `suggested_capability_family == "sandbox"`
- the current workspace root and sandbox boundary stay within current access
- the suggested executor remains one of existing allowed bounded families:
  - `pytest`
  - `rg`
  - read-only `git`

Generated sandbox packets must keep:

- `intent="sandbox:execute_workspace_command"`
- `risk="external_mutation"`
- `status="awaiting_approval"`
- `requires_approval=True`
- frozen `execution_spec` / `execution_preview`
- no package install, shell wrapper, network, privileged Docker, Docker socket, or host-secret surface

Blocked boundary bias must not create an execution packet. It may update readback as a planning boundary so the next behavior can avoid repeating the blocked action.

Browser manual-takeover bias must not click, fill, submit, download, upload, or mutate pages. It may surface the manual takeover requirement.

Skill usage bias must not install, update, enable, disable, pin, or unpin skills. It may preserve artifact/source-ref continuity and skill-guided planning context.

## Backend And CLI Readback

Expose the advisory bias through existing readback surfaces:

- `autonomy.procedural_planning`
- `turn_summary.autonomy.procedural_planning`
- `turn_summary.current_turn.procedural_planning`
- compact CLI line:

```text
planproc=sandbox_execute:run-1:approval
```

Readback must distinguish:

- approval-required execution suggestions
- boundary-only blocked traces
- manual browser takeover requirements
- skill guidance that does not mutate registry truth

## Smoke Scenarios

Required phase-2 smoke scenarios:

1. `completed_sandbox_trace_guides_pytest_packet_with_approval`
   - completed sandbox trace creates a `sandbox_execute` planning bias
   - autonomy selects a bounded pytest packet only after current request match
   - packet still requires approval
2. `blocked_trace_becomes_boundary_bias_not_execution`
   - blocked trace creates `boundary_only`
   - no `execute_workspace_command` packet is created from that trace
   - `capability_claim=False`
3. `browser_takeover_trace_surfaces_manual_boundary`
   - manual takeover trace creates `browser_manual_takeover`
   - no browser mutation packet is created
   - `must_request_approval=True`
4. `skill_usage_trace_guides_without_registry_mutation`
   - skill usage trace creates `skill_guidance`
   - no skill mutation packet is created
   - registry/install truth remains absent from the bias
5. `low_confidence_or_mismatched_trace_is_ignored`
   - low-confidence trace or workspace-boundary mismatch returns no execution-producing bias

## Closure Gate

The phase is ready only when `python evals/run_procedural_growth_phase2_audit.py` reports:

```text
readiness_status=procedural_growth_phase2_ready
```

Audit blockers:

- procedural trace produces an execution packet without current request match
- sandbox bias bypasses approval
- blocked trace becomes a completed capability or execution packet
- browser manual-takeover trace mutates a page automatically
- skill trace mutates registry truth
- workspace root, runner, isolation, or network boundary widens current access
- backend/API/CLI readback disagree on the planning bias
- Phase 1 procedural trace writeback regresses

Recommended closeout evidence:

- `python -m pytest tests/test_procedural_planning.py tests/test_procedural_growth_phase2_audit.py -q`
- `python -m pytest tests/test_companion_autonomy_runtime.py -k procedural -q`
- `python -m pytest tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py -k procedural -q`
- `python evals/run_procedural_growth_phase2_smokes.py --run-tag phase2-ready-a`
- `python evals/run_procedural_growth_phase2_audit.py --run-tag phase2-ready-a`

## Preserved Baseline Guardrails

This phase must preserve:

- `freeze_gate_ready`
- `companion_autonomy_ready`
- `digital_embodiment_phase1_ready`
- `digital_embodiment_phase2_ready`
- `sandbox_embodied_execution_phase1_ready`
- `skills_ecosystem_ready`
- `live_browser_runtime_phase1_ready`
- `sandbox_embodied_execution_phase2_ready`
- `post_baseline_closure_ready`
- `procedural_growth_phase1_ready`
