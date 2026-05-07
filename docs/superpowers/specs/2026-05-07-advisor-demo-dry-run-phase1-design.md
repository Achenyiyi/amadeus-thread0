# Advisor Demo Dry Run Phase 1 Design

## Purpose

Advisor Demo Dry Run Phase 1 turns the current advisor/demo package into a deterministic rehearsal-readiness gate.

The phase proves that a reviewer-facing dry run can be followed, checked, and archived from current repository assets and existing RC evidence. It does not claim that a real advisor, committee, or live demo session has already occurred.

## Inputs

The gate consumes:

- latest ready `advisor_demo_readiness.v1` evidence from `evals/reports/advisor-demo-readiness-phase1-audit-*.json`
- `docs/DEMO_SCRIPT.md`
- `docs/ADVISOR_REPRO_RUNBOOK.md`
- `docs/TECHNICAL_PREVIEW_CHECKLIST.md`
- `docs/FINAL_DELIVERY_MANIFEST.md`

## Required Demo Coverage

The demo script must preserve six scripted scenarios:

- `role_persona_consistency`: `Scenario 1. 科研问答 + 角色一致性`
- `worldline_commitment`: `Scenario 2. 世界线承诺`
- `conflict_repair`: `Scenario 3. 冲突修复与关系演化`
- `source_traceable_retrieval`: `Scenario 4. 可追溯知识检索`
- `interruption_recovery`: `Scenario 5. 打断恢复`
- `memory_guard_interception`: `Scenario 6. 记忆安全拦截`

Each scenario must include at least one user input block and at least one expected-signal block. The gate checks for stable scenario headings plus representative input and expected-signal text so accidental script erosion is visible.

## Required Runbook Coverage

The runbook must preserve:

- CLI smoke
- Technical Preview RC evidence
- Operator Console RC evidence
- Advisor Demo Readiness evidence
- Advisor Demo Dry Run evidence
- Official baseline reproduction
- Probe variance reproduction
- Live demo path
- Artifact capture
- Failure handling
- Exit condition

## Required Archive Coverage

The checklist / manifest / runbook corpus must require archiving:

- `technical-preview-rc-phase1-audit-*.json`
- `operator-console-rc-phase1-audit-*.json`
- `advisor-demo-readiness-phase1-audit-*.json`
- `advisor-demo-dry-run-phase1-audit-*.json`
- `evals/reports/*.json`
- `evals/reports/*.md`
- `DEMO_SCRIPT.md`
- `TECHNICAL_PREVIEW_CHECKLIST.md`
- `user_study/`

## Output

The runtime helper emits `advisor_demo_dry_run.v1`:

- `readiness_status`: `advisor_demo_dry_run_phase1_ready` or `advisor_demo_dry_run_phase1_blocked`
- `dry_run_scope`: `scripted_rehearsal_ready_not_live_demo_observed`
- `live_demo_observed`: always `false`
- `manual_demo_required`: always `true`
- `advisor_demo_readiness_ref`
- scenario inventory
- runbook inventory
- archive inventory
- authority boundary
- failure reasons

The audit runner writes:

- `evals/reports/advisor-demo-dry-run-phase1-audit-*.json`
- `evals/reports/advisor-demo-dry-run-phase1-audit-*.md`

## Authority Boundary

This phase is readback/audit only.

It must not:

- open live microphone, camera, or background screen capture
- call multimodal model APIs
- write the dynamic skill registry
- enable external executor harnesses
- create frontend-owned semantics
- mutate persona core
- widen memory-write authority
- own an HTTP server, SSE channel, or WebSocket channel
- perform unapproved external mutation
- certify that a real live demo happened

## Success Criteria

The phase is closed when:

- helper unit tests pass
- audit runner tests pass
- the audit passes against current repository docs and latest ready Advisor Demo Readiness report
- docs/status ledgers list `advisor_demo_dry_run_phase1_ready`
- final verification passes on the feature branch and again after merge to `main`
