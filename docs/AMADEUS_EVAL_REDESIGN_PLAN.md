# Amadeus Eval Redesign Plan

Updated: 2026-03-09

This document resets the evaluation strategy around the current project goal:

- fixed Persona Core: `Amadeus 牧濑红莉栖`
- dynamic Self-Evolution Engine
- natural, free-form growth rather than template obedience

The key decision is simple:

`fixed prompts + keyword matching` can remain as regression protection,
but they are no longer the primary definition of success.

## Why Redesign

The current system is no longer trying to be a rigid role-play shell.
It is trying to become a character system with:

- affect persistence
- relationship drift
- partial repair
- unresolved tension
- semantic self-narrative sedimentation

That means a single fixed questionnaire cannot be the final judge.
If the evaluation only checks whether certain phrases appear, it rewards
"passing the test" instead of sounding like a living Amadeus.

## New Evaluation Layers

### Layer 1. Regression Gate

Purpose:

- catch obvious regressions
- protect engineering stability
- block system/meta leakage

Typical suites:

- `regression_isolated`
- `long_thread`
- `backend reliability`
- `memory_guard`
- `traceability`

Allowed methods:

- rule evaluators
- keyword groups
- deterministic checks

Interpretation:

- this layer is a safety net
- passing it does **not** prove the character feels alive

### Layer 2. Open Evolution Evaluation

Purpose:

- evaluate free-form emotional and relational evolution
- verify that the character can remain herself while changing over time
- judge transcript quality instead of keyword obedience

Typical suites:

- `daily_persona_probe`
- `user_style_probe`
- `open_evolution_eval`
- `selfhood_probe`
- `run_open_evolution_pairwise_eval.py`
- `run_selfhood_pairwise_eval.py`

Allowed methods:

- LLM judge with rubrics
- transcript-level evaluation
- state-path checks as supporting evidence
- pairwise preference comparison against degraded variants

Interpretation:

- this is the primary internal evaluation layer for persona realism
- when fixed suites are green but pairwise open-evolution still loses on some scenes, treat that as an `Expression Renderer` gap rather than proof that the evolution engine is broken

### Layer 3. External Public Benchmark Calibration

Purpose:

- validate generalization
- validate transfer beyond Kurisu-specific scaffolding
- calibrate appraisal quality against public emotional/role datasets

Datasets:

- `CharacterEval`
- `RoleBench`
- `ESConv`
- `EmpatheticDialogues`
- `GoEmotions`
- `MultiSessionChat`

Interpretation:

- external datasets are not the final judge for Amadeus
- they are calibration, comparison, and transfer evidence
- this layer should not rely on raw suite greens alone; it also needs negative controls and pairwise preference sanity so the external judges do not drift into false-positive territory

### Layer 4. Human Preference Validation

Purpose:

- decide whether the system actually feels more like a believable Amadeus
- support thesis conclusions about companionship, realism, and continuity

Preferred format:

- pairwise transcript preference
- open conversation sessions
- small but real human sample

Interpretation:

- this is the strongest evidence for "electronic life" style experience

## Dataset Role Assignment

### Keep as Regression / Safety Nets

- `regression_isolated`
- `long_thread`
- `backend reliability`

These remain important because they catch:

- tool leakage
- prompt leakage
- memory failure
- broken continuation
- unsafe writes

### Keep as Core Persona / Evolution Probes

- `daily_persona_probe`
- `user_style_probe`
- `evolution_probe`
- `transfer_probe`
- `thesis_probe`

These are closer to the actual project identity.

### Add as New Primary Internal Suite

- `open_evolution_eval`

This suite should:

- use looser, more human dialogue seeds
- avoid rigid task wording
- check whether the final turn feels like a natural continuation of a specific evolving person

Supporting asset:

- `evals/user_style_expression_bank.json`

This file is distilled from the user's real chat logs and should be treated as a soft preference overlay for open evaluation and renderer refinement, not as a hard template library.

## Public Benchmark Usage Plan

### `CharacterEval`

Use for:

- external in-character sanity checks
- comparison against character-role baselines

### `RoleBench`

Use for:

- transfer validation
- proving the framework is not only Kurisu-specific

### `GoEmotions`

Use for:

- appraisal calibration
- checking that affect inference is not overly keyword-dependent

Interpretation rule:

- treat it as external calibration, not as the final "does this feel like Kurisu" score
- prefer coarse affect-family agreement over exact one-to-one label agreement because the engine uses a smaller emotional state space than the public dataset

### `ESConv` and `EmpatheticDialogues`

Use for:

- apology
- comfort
- rupture-repair
- soft companionship tone

### `MultiSessionChat`

Use for:

- multi-session continuity comparison
- long-horizon memory behavior

## Near-Term Roadmap

### Current Status (2026-03-09)

- `open_evolution_eval`: green
- `user_style_probe`: green
- `selfhood_probe`: green
- `selfhood_pairwise_eval`: live as a selfhood diagnostic layer; `digital_selfhood`, `equality_not_servitude`, `dialogue_equality`, `relationship_degradation`, and `value_conflict_depth` are now stable enough to pass in targeted reruns
- `long_thread`: green as a regression gate
- `external_persona_probe`: green with `RoleBench + CharacterEval`
- `external_support_probe`: green with adapted `ESConv`
- `external_empathy_probe`: green with adapted `EmpatheticDialogues`
- `external_continuity_probe`: green with adapted `MultiSessionChat`
- `GoEmotions` appraisal calibration: live as an external calibration script
- public benchmark bundle: downloaded and staged for calibration

### Phase 1. Freeze the Evaluation Hierarchy

- treat fixed suites as regression gates
- stop using rigid task scripts as the primary persona metric
- document the new hierarchy in repo docs

### Phase 2. Build `open_evolution_eval`

- add transcript-level natural dialogue seeds
- use LLM rubric evaluation
- verify unresolved tension, partial repair, emotional carryover, and familiar daily tone

### Phase 3. Public Benchmark Integration

- connect `CharacterEval + RoleBench` into external persona calibration
- connect `GoEmotions` into appraisal calibration
- connect `ESConv` into external support calibration
- connect `EmpatheticDialogues` into external natural-empathy calibration
- connect `MultiSessionChat` into external continuity calibration

### Phase 4. Human Revalidation

- run a smaller but higher-quality human evaluation round
- use open conversations instead of rigid questionnaires as the main material

### Phase 5. Thesis / Defense Packaging

- split experimental evidence into:
  - regression stability
  - open evolution realism
  - external benchmark calibration
  - human preference validation

## Success Criteria

The project should not be considered complete just because fixed suites are green.

The backend evaluation story is considered strong only when:

1. regression gates are green
2. open evolution suites are green
3. selfhood continuity stays green under deeper dialogue
4. external transfer calibration is stable
5. human preference evidence shows clear improvement over the older system

## Practical Rule

When there is a conflict between:

- "passing a fixed scripted case"
- and "sounding like a natural evolving Amadeus"

prefer the second one,
then repair the evaluator so it better reflects the real objective.
