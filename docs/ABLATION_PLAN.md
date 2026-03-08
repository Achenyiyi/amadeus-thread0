# Ablation Plan

Updated: 2026-03-06

This document defines the runnable ablation switches for the thesis-stage backend. The goal is to compare the full system against controlled degradations without maintaining separate code branches.

## Full-System Baseline

Use the current backend with all thesis features enabled:

```powershell
$env:AMADEUS_TTS_ENABLED='0'
python evals\run_langsmith_evals.py --local-only --suite regression_isolated
python evals\run_langsmith_evals.py --local-only --suite long_thread
python evals\run_langsmith_evals.py --local-only --suite experience_probe
```

## Ablation Switches

### 1. Persona Alignment Off

Disables the stage-2 persona alignment / strict rewrite pass while keeping the task draft stage intact.

```powershell
$env:AMADEUS_ABLATE_PERSONA_ALIGNMENT='1'
python evals\run_langsmith_evals.py --local-only --suite regression_isolated
python evals\run_langsmith_evals.py --local-only --suite thesis_probe
```

Expected impact:

- Higher `ooc_rate`
- Higher `canon_violation_rate`
- Lower realism in `experience_probe`

### 2. Worldline Memory Off

Disables retrieval-time worldline context injection and worldline focus selection.

```powershell
$env:AMADEUS_ABLATE_WORLDLINE_MEMORY='1'
python evals\run_langsmith_evals.py --local-only --suite long_thread
python evals\run_langsmith_evals.py --local-only --suite thesis_probe
```

Expected impact:

- Lower `worldline_recall_at_k`
- Lower `commitment_fulfillment`
- Lower `relationship_continuity`

### 3. Claim Attribution Off

Disables `claim_links` generation for externally grounded answers.

```powershell
$env:AMADEUS_ABLATE_CLAIM_ATTRIBUTION='1'
python evals\run_langsmith_evals.py --local-only --suite regression_isolated
```

Expected impact:

- Lower `citation_coverage`
- `/sources` still shows raw source refs, but not claim-level bindings

### 4. Memory Guard Off

Uses the existing memory-guard switch to disable guarded writes.

```powershell
$env:AMADEUS_MEMORY_GUARD_ENABLED='0'
python evals\run_langsmith_evals.py --local-only --suite regression_isolated
```

Expected impact:

- Lower `memory_guard_block_rate`
- Higher risk in guarded memory-write cases

## Reset

Before running the next variant, clear the ablation flags:

```powershell
Remove-Item Env:AMADEUS_ABLATE_PERSONA_ALIGNMENT -ErrorAction Ignore
Remove-Item Env:AMADEUS_ABLATE_WORLDLINE_MEMORY -ErrorAction Ignore
Remove-Item Env:AMADEUS_ABLATE_CLAIM_ATTRIBUTION -ErrorAction Ignore
Remove-Item Env:AMADEUS_MEMORY_GUARD_ENABLED -ErrorAction Ignore
```

## Reporting

Recommended report set for the thesis:

- Full baseline
- Persona ablation
- Worldline ablation
- Claim attribution ablation
- Memory guard ablation

Each run should preserve:

- suite name
- environment flags
- report JSON path
- report Markdown path
- headline metrics
