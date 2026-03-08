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
