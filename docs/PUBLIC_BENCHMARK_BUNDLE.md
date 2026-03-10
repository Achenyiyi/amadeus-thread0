# Public Benchmark Bundle

This project does not rely on a single "universal" dataset for virtual humans. The defensible approach is a benchmark bundle, with each public dataset covering a different failure mode.

## Included Datasets

1. `CharacterEval`
- Purpose: role-playing fidelity, in-character dialogue, out-of-character failure analysis.
- Why it matters here: closest public benchmark to "does this still sound like a specific character?"

2. `RoleBench`
- Purpose: broader role-playing evaluation and transfer-style role consistency checks.
- Why it matters here: supports the claim that the engine is not only a Kurisu-specific trick.

3. `ESConv`
- Purpose: emotional support dialogue and repair behavior.
- Why it matters here: useful for apology, companionship, rupture-repair, and soft support behaviors.

4. `EmpatheticDialogues`
- Purpose: emotionally grounded everyday dialogue.
- Why it matters here: useful for daily companion dialogue and affect-sensitive response style.

5. `GoEmotions`
- Purpose: emotion labels for appraisal-layer calibration.
- Why it matters here: useful for reducing pure keyword dependence in the self-evolution appraisal layer.

6. `MultiSessionChat`
- Purpose: multi-session continuity and long-horizon recall.
- Why it matters here: useful for long-thread continuity beyond one-off turns.

## Local Layout

Downloaded bundle root:

```text
third_party/benchmarks/
```

Each dataset gets its own subdirectory, plus:

```text
third_party/benchmarks/bundle_manifest.json
```

## Download Command

```powershell
python scripts\download_public_benchmark_bundle.py
```

Force refresh:

```powershell
python scripts\download_public_benchmark_bundle.py --refresh
```

## Recommended Use In This Project

For the current Amadeus-K stack, use the bundle in three layers:

1. `CharacterEval + RoleBench`
- For role/persona consistency evaluation and transfer validation.

2. `ESConv + EmpatheticDialogues`
- For companionship, apology, repair, and emotional support style analysis.

3. `GoEmotions + MultiSessionChat`
- For appraisal calibration and long-horizon continuity experiments.

## Current Integration Status

As of 2026-03-09:

1. `CharacterEval + RoleBench`
- Already wired into `external_persona_probe`
- Purpose: external role/persona calibration and transfer support evidence

2. `GoEmotions`
- Already wired into `evals/run_appraisal_calibration.py`
- Purpose: calibrate the `LLM Appraisal + Rule Fallback` layer
- Interpretation rule: use it as external calibration, not as the final Kurisu realism score

3. `ESConv`
- Already wired into `external_support_probe`
- Purpose: adapted companion/repair calibration under public support scenarios
- Integration note: use `situation` as the primary anchor and lightly rewrite raw prompts when the original dialogue opener is too noisy for character evaluation

4. `EmpatheticDialogues`
- Already wired into `external_empathy_probe`
- Purpose: adapted natural-empathy calibration for quiet, everyday vulnerable dialogue
- Integration note: use the `prompt` as the scene anchor and keep only a small number of representative contexts

5. `MultiSessionChat`
- Already wired into `external_continuity_probe`
- Purpose: adapted long-horizon continuity calibration under accumulated shared context
- Integration note: use multi-session carryover as a scaffold, not as a strict next-token imitation target

## Current Commands

```powershell
python evals\run_langsmith_evals.py --local-only --suite external_persona_probe
python evals\run_langsmith_evals.py --local-only --suite external_support_probe
python evals\run_langsmith_evals.py --local-only --suite external_empathy_probe
python evals\run_langsmith_evals.py --local-only --suite external_continuity_probe
python evals\run_appraisal_calibration.py --max-per-label 1
python evals\run_external_judge_sanity.py
python evals\run_external_pairwise_sanity.py
```

## Calibration Guardrails

The public benchmark layer is not trusted on raw suite scores alone.
It is now backed by two extra sanity passes:

1. `run_external_judge_sanity.py`
- single-answer negative controls
- verifies that obvious generic assistant / fake warmth / reset answers do not pass

2. `run_external_pairwise_sanity.py`
- pairwise preference sanity
- verifies that the judge prefers the stronger answer over the weaker one under the same scene, even when the answer order is swapped
