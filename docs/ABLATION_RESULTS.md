# Ablation Results

Updated: 2026-03-07

Primary comparative report:

- Markdown: `evals/reports/ablation-matrix-20260306-224514-5c1a1c70.md`
- JSON: `evals/reports/ablation-matrix-20260306-224514-5c1a1c70.json`

Latest targeted reruns and repeated probes:

- Thesis probe baseline: `evals/reports/eval-report-20260307-022239-17048ce9.json`
- Thesis probe variance: `evals/reports/probe-variance-thesis_probe-20260307-024213-ee70482d.json`
- Long-thread baseline: `evals/reports/eval-report-20260307-005508-c126b941.json`
- Long-thread worldline-off: `evals/reports/eval-report-20260307-010246-e2288121.json`

Interpretation rule:

- use the matrix for subsystem delta tables
- use repeated `thesis_probe` results for the cleanest persona/worldline evidence on the latest code
- use `docs/EVAL_BASELINE.md` for official green baseline references

## Main Findings

### 1. Claim attribution remains the cleanest quantitative ablation

From `claim_attribution_off_regression` in the matrix:

- baseline `citation_coverage = 1.0000`
- claim attribution off `citation_coverage = 0.0000`

This supports the claim that `claim_links -> source_refs` is an active subsystem, not incidental prompt behavior.

### 2. Memory guard remains a clean subsystem result

From `memory_guard_off_regression` in the matrix:

- baseline `memory_guard_block_rate = 0.1667`
- memory guard off `memory_guard_block_rate = 0.0000`

This supports the thesis claim that guarded write blocking is implemented at the system layer.

### 3. Worldline memory now has both targeted and long-thread evidence

From `worldline_off_thesis_probe` in the matrix:

- `worldline_recall_at_k = 0.0000`
- `commitment_fulfillment = 0.5000`
- `relationship_continuity = 0.5000`

From the repeated latest-code thesis probe:

- report: `evals/reports/probe-variance-thesis_probe-20260307-024213-ee70482d.json`
- `worldline_off -> worldline_recall_at_k = 0.1667 +/- 0.2887`
- `worldline_off -> commitment_fulfillment = 0.1667 +/- 0.2887`
- `worldline_off -> relationship_continuity = 0.8333 +/- 0.2887`
- `worldline_off -> worldline_answer_grounding = 0.6667 +/- 0.1667`

From the dedicated latest-code long-thread reruns:

- baseline long-thread: `worldline_recall_at_k = 1.0000`, `commitment_fulfillment = 1.0000`
- worldline-off long-thread: `worldline_recall_at_k = 0.6667`, `commitment_fulfillment = 0.6667`
- key failed case: `long_thread-008`

Interpretation:

- the thesis probe remains the cleanest headline result for worldline memory
- the repeated probe plus long-thread rerun now give two independent evidence paths
- this makes the worldline claim stronger than before, because it is no longer isolated to one report family

### 4. Persona alignment is now stable enough to cite with repeated probes

Dedicated latest-code baseline rerun:

- baseline: `evals/reports/eval-report-20260307-022239-17048ce9.json`
  - `persona_probe_voice = 1.0000`
  - failing cases: none

Repeated variance rerun:

- report: `evals/reports/probe-variance-thesis_probe-20260307-024213-ee70482d.json`
- baseline repeat mean/std:
  - `persona_probe_voice = 1.0000 +/- 0.0000`
- persona-off repeat mean/std:
  - `persona_probe_voice = 0.6667 +/- 0.0000`

Observed qualitative difference on the same probe:

- baseline opens with a Kurisu-style direct companion cue: `先别急，...`
- persona-off answers in a neutral assistant voice without that opener

Interpretation:

- persona contribution is measurable on the targeted probe
- the repeated probe removes the earlier baseline jitter
- the thesis should cite the repeated probe report rather than relying only on one lucky single run

### 5. Matrix rows still show stochastic variance, but the headline claims are now defensible

The monolithic matrix remains useful, but it should not be the sole source for thesis claims.

This should be interpreted as:

- model sampling and retrieval variance still exist
- official baseline claims should rely on dedicated suite reruns and repeated probe reports
- subsystem deltas should rely on matrix rows plus targeted reruns

This is the defensible way to write the experiment chapter without overstating stability.

## What This Means For The Thesis

The current evidence supports four system claims:

1. `claim attribution` measurably controls citation coverage
2. `memory guard` measurably controls guarded-write blocking
3. `worldline memory` measurably affects cross-thread recall and commitment grounding
4. `persona alignment` measurably affects role-voice fidelity on retrieval-grounded dialogue

For the thesis chapter, persona should still be presented with three layers together:

- repeated automatic probe evidence
- qualitative side-by-side examples
- user-study rating evidence

## Recommended Experiment Framing

For the thesis chapter, use this structure:

1. Official baseline tables: from `docs/EVAL_BASELINE.md`
2. Subsystem ablation table: from `ablation-matrix-20260306-224514-5c1a1c70`
3. Repeated `thesis_probe` table: from `probe-variance-thesis_probe-20260307-024213-ee70482d`
4. Long-thread worldline comparison: baseline vs `worldline_off`
5. Qualitative case study: one baseline vs persona-off answer pair
6. User-study ratings: role fidelity, continuity, trust, companionship, controllability

## Remaining Gap

Next experiment priority:

1. run the 15-20 participant user study and connect the ratings to the now-stable thesis probe results
2. finish Phase F delivery closure so the advisor/demo path and reproducibility path are fully documented
3. add one more persona-sensitive retrieval probe only if you still want a broader automatic persona headline beyond the current `0.6667` drop
