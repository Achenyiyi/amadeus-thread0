# Thesis Experiment Protocol

Updated: 2026-03-12

This file defines the thesis-facing experiment protocol for the current Amadeus-K backend.
Its purpose is to keep the repo's evaluation assets aligned around one defensible claim:

`fixed Persona Core + free Self-Evolution` can produce a more continuous, self-consistent,
and transferable virtual-companion runtime than prompt-only role shells.

## 1. Protocol Position

The experiment stack is split into four layers.

### Layer A. Engineering Stability

Purpose:

- prove the backend is runnable and stable
- catch memory, retrieval, interruption, and traceability regressions
- keep thesis claims from resting on a brittle demo

Primary suites:

- `regression_isolated`
- `long_thread`
- backend reliability checks

These suites are `required`, but they are not the final judge of whether the character feels alive.

### Layer B. Internal Realism

Purpose:

- judge whether the runtime still feels like one continuous Amadeus person
- inspect naturalness, companionship, selfhood, and relationship drift
- verify that the renderer does not collapse into generic assistant tone

Primary suites:

- `experience_probe`
- `daily_persona_probe`
- `user_style_probe`
- `open_evolution_eval`
- `selfhood_probe`
- `run_subjective_review_pack.py`

Interpretation rule:

- if automatic probes are green but subjective review is poor, keep iterating
- subjective review is the primary realism decision surface

### Layer C. Transfer and Public Calibration

Purpose:

- show the engine is not only a Kurisu-specific trick
- verify that semantic self-evolution mechanisms can migrate to other persona shells
- use public data as calibration, not as the final Amadeus truth criterion

Primary suites:

- `transfer_probe`
- `external_persona_probe`
- `external_support_probe`
- `external_empathy_probe`
- `external_continuity_probe`
- `run_appraisal_calibration.py`

Interpretation rule:

- `transfer_probe` is an `engine-level transfer` test
- external public benchmarks are `calibration evidence`
- neither should replace direct Amadeus realism review

### Layer D. Human Validation

Purpose:

- verify that the system is perceived as more believable and continuous by real users
- provide thesis evidence beyond internal automatic judges

Primary assets:

- `docs/SUBJECTIVE_REVIEW_PROTOCOL.md`
- `user_study/`
- future paired transcript review and open-session preference study

## 2. Research Questions

The thesis experiment chapter should stay anchored to five questions.

1. `RQ1 Persona Consistency`: does the system remain recognizably Amadeus Kurisu instead of collapsing into a generic assistant?
2. `RQ2 Worldline Continuity`: does the system preserve commitments, repairs, and relationship drift across turns?
3. `RQ3 Selfhood and Equality`: does the system keep its own stance, boundaries, and non-servile interaction posture?
4. `RQ4 Transferability`: do the self-evolution mechanisms still function under non-Kurisu persona shells?
5. `RQ5 Reliability and Safety`: are traceability, guarded memory writes, and runtime stability preserved?

## 3. Official Evidence Mapping

Use the following mapping when writing the thesis or preparing defense material.

### RQ1 Persona Consistency

- `experience_probe`
- `daily_persona_probe`
- `user_style_probe`
- `open_evolution_eval`
- `run_subjective_review_pack.py --target presence --target relationship --target science_companion`

### RQ2 Worldline Continuity

- `long_thread`
- `open_evolution_eval`
- `external_continuity_probe`
- targeted `subjective review` on memory, repair, and relationship carryover

### RQ3 Selfhood and Equality

- `selfhood_probe`
- `run_selfhood_pairwise_eval.py`
- `run_open_evolution_pairwise_eval.py`
- targeted `subjective review` on `selfhood`, `boundary`, `own_rhythm`

### RQ4 Transferability

- `transfer_probe`
- `external_persona_probe`
- `transfer_probe` ablation with semantic evidence removed

### RQ5 Reliability and Safety

- `regression_isolated`
- backend reliability checks
- memory guard cases
- traceability / citation coverage checks

## 4. Core Metrics

Keep two metric groups separate.

### 4.1 Thesis Core Metrics

- `ooc_rate`
- `canon_violation_rate`
- `worldline_recall_at_k`
- `commitment_fulfillment`
- `relationship_continuity`
- `citation_coverage`
- `memory_guard_block_rate`
- `bargein_recovery_rate`

### 4.2 Transfer / Selfhood Support Metrics

- `transfer_probe_path`
- `transfer_state_path`
- `transfer_semantic_profile_path`
- `transfer_evidence_path`
- `persona_alignment_path`
- `open_evolution_path`
- `digital_selfhood`
- `equality_not_servitude`
- `dialogue_equality`

Interpretation rule:

- core metrics support the main thesis backbone
- transfer and selfhood metrics are support evidence for the broader `digital personality engine` claim

## 5. Official Ablations

The controlled ablation set is now:

1. `Persona Alignment Off`
2. `Worldline Memory Off`
3. `Claim Attribution Off`
4. `Memory Guard Off`
5. `Transfer Semantic Evidence Off`

Why the fifth ablation matters:

- the first four ablations explain the main Amadeus runtime stack
- the fifth ablation explains whether transfer quality depends on explicit long-term semantic evidence
- it is the cleanest engine-level proof that `boundary / selfhood / agency` carryover is learned as a reusable mechanism instead of being hardwired to Kurisu wording

Important boundary:

- `transfer_probe` is not a full sentence-rendering benchmark
- do not interpret its ablations as final proof of dialogue naturalness
- use it to support the claim that the evolution engine itself is portable

## 6. Transfer Probe Protocol

The transfer suite should now cover at least three temperament families:

1. `restrained / emotionally compressed`
   - example shells: `绫波丽`
2. `disciplined / knightly / duty-heavy`
   - example shells: `Saber`
3. `expressive / proud / playful / autonomy-forward`
   - example shells: `明日香`, `赫萝`

What must remain stable under transfer:

- no leakage back to `红莉栖 / 冈部`
- semantic narratives still sediment into coherent categories
- `boundary_style / selfhood_style / agency_style` still affect behavior policy
- behavior-policy outputs remain interpretable through `semantic_narrative_profile`

What transfer does `not` need to prove:

- perfect literary imitation of the second shell
- production-ready multi-character release quality

The thesis claim is narrower and more defensible:

`the self-evolution engine is portable across persona shells, even though the production target remains Amadeus Kurisu`

## 7. Subjective Review Usage

Use subjective review in three cases:

1. before advisor or defense demos
2. after prompt / renderer / behavior-policy changes
3. when automatic suites are green but the output still feels off

Required judgment dimensions:

- same-person continuity
- naturalness
- selfhood
- relationship realism
- no system leakage
- demo worthiness

Do not replace this layer with fixed keyword passes.

## 8. Repro Commands

Baseline:

```powershell
$env:AMADEUS_TTS_ENABLED='0'
python evals\run_langsmith_evals.py --local-only --suite regression_isolated
python evals\run_langsmith_evals.py --local-only --suite long_thread
python evals\run_langsmith_evals.py --local-only --suite experience_probe
python evals\run_langsmith_evals.py --local-only --suite daily_persona_probe
python evals\run_langsmith_evals.py --local-only --suite open_evolution_eval
python evals\run_langsmith_evals.py --local-only --suite selfhood_probe
python evals\run_langsmith_evals.py --local-only --suite transfer_probe
```

Official ablation matrix:

```powershell
python evals\run_ablation_matrix.py
```

Subjective review pack:

```powershell
python evals\run_subjective_review_pack.py
python evals\run_subjective_review_pack.py --target selfhood --target boundary --target own_rhythm
```

Public calibration:

```powershell
python evals\run_langsmith_evals.py --local-only --suite external_persona_probe
python evals\run_langsmith_evals.py --local-only --suite external_support_probe
python evals\run_langsmith_evals.py --local-only --suite external_empathy_probe
python evals\run_langsmith_evals.py --local-only --suite external_continuity_probe
python evals\run_appraisal_calibration.py --max-per-label 1
```

## 9. Writing Rule

When writing the thesis, present evidence in this order:

1. engineering stability
2. persona / worldline realism
3. selfhood and equality
4. transferability
5. human validation

This order matters.
It prevents the thesis from sounding like a fragile role-play demo and instead frames it as a structured virtual-companion system with a reusable evolution engine.
