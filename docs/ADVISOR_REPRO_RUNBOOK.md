# Advisor Repro Runbook

Updated: 2026-05-07

This runbook is the shortest path for an advisor, reviewer, or demo operator to verify the current technical-preview backend.

## Goal

Verify six things in order:

1. the CLI starts cleanly
2. the Technical Preview RC evidence gate is reproducible
3. the Operator Console RC readback gate is reproducible
4. the official baseline reports are reproducible
5. the thesis probe variance report is reproducible
6. the live demo script can be followed without improvisation

## Environment

- Python environment with project dependencies installed
- `.env` populated with the required model and speech keys
- Current working directory: project root

Recommended runtime flags:

```powershell
$env:LANGSMITH_TRACING='false'
$env:LANGCHAIN_TRACING_V2='false'
$env:AMADEUS_TTS_ENABLED='0'
```

If a speech demo is required later, switch `AMADEUS_TTS_ENABLED` back to `1` only after the baseline runs are done.

## Step 1. CLI Smoke

```powershell
python -m amadeus_thread0.cli
```

Check:

- startup banner renders correctly
- `/persona`, `/worldline`, `/bond`, `/sources` are accepted
- no duplicated final output

Exit after one short exchange.

## Step 2. Technical Preview RC Evidence

Run:

```powershell
python evals\run_runtime_productization_phase3_audit.py
python evals\run_technical_preview_rc_phase1_audit.py --run-tag advisor-repro
python evals\run_operator_console_rc_phase1_audit.py --run-tag advisor-repro
python evals\run_preserved_baselines_audit.py --reports-dir evals\reports
```

Check:

- `technical-preview-rc-phase1-audit-*.json` reports `overall_status=passed`
- readiness is `technical_preview_rc_phase1_ready`
- `operator-console-rc-phase1-audit-*.json` reports `operator_console_rc_phase1_ready`
- operator console mode is `readback_only`
- the embedded runtime status line reports `next_specs=0`
- blocked authority remains closed for live capture, external executor auto-enablement, automatic dynamic skill registry writes, and multimodal model auto-calls

If this step fails because a source report is missing, stop and preserve the failing RC report. Do not treat a missing report as runtime readiness.

## Step 3. Official Baseline Reproduction

Run:

```powershell
python evals\run_langsmith_evals.py --local-only --suite regression_isolated
python evals\run_langsmith_evals.py --local-only --suite long_thread
python evals\run_langsmith_evals.py --local-only --suite experience_probe
python evals\run_langsmith_evals.py --local-only --suite thesis_probe
python evals\run_backend_reliability_checks.py
```

Check against [EVAL_BASELINE.md](/E:/桌面/amadeus-thread0/docs/EVAL_BASELINE.md):

- `regression_isolated`: green
- `long_thread`: green
- `experience_probe`: green
- `thesis_probe`: green
- backend reliability checks: green

If one suite fails, stop and record the failing report path before any retry.

## Step 4. Probe Variance Reproduction

Run:

```powershell
python evals\run_probe_variance.py --suite thesis_probe --repeats 3 --fresh
```

Expected headline pattern:

- `baseline -> persona_probe_voice = 1.0000 +/- 0.0000`
- `persona_off -> persona_probe_voice = 0.6667 +/- 0.0000`
- `worldline_off -> worldline_recall_at_k` clearly below baseline

Canonical reference:

- [probe-variance-thesis_probe-20260307-024213-ee70482d.md](/E:/桌面/amadeus-thread0/evals/reports/probe-variance-thesis_probe-20260307-024213-ee70482d.md)

## Step 5. Live Demo Path

Follow [DEMO_SCRIPT.md](/E:/桌面/amadeus-thread0/docs/DEMO_SCRIPT.md) in this order:

1. scientific QA + persona consistency
2. worldline commitment
3. conflict repair + relationship evolution
4. source-traceable retrieval
5. interruption recovery
6. memory guard interception

Do not skip directly to the knowledge demo; the intended presentation logic is:

`像人 -> 连续 -> 可信 -> 稳定 -> 可控`

## Step 6. Artifact Capture

During an advisor/demo run, archive these paths:

- latest eval markdown/json reports in `evals/reports/`
- latest `technical-preview-rc-phase1-audit-*.json` and `.md`
- current `.env.example`
- [EVAL_BASELINE.md](/E:/桌面/amadeus-thread0/docs/EVAL_BASELINE.md)
- [ABLATION_RESULTS.md](/E:/桌面/amadeus-thread0/docs/ABLATION_RESULTS.md)
- [DEMO_SCRIPT.md](/E:/桌面/amadeus-thread0/docs/DEMO_SCRIPT.md)
- [TECHNICAL_PREVIEW_CHECKLIST.md](/E:/桌面/amadeus-thread0/docs/TECHNICAL_PREVIEW_CHECKLIST.md)
- user-study packet in `user_study/`

## Failure Handling

If the run breaks:

1. keep the generated failing report
2. record whether the failure is `baseline drift`, `tool/retrieval drift`, `worldline miss`, `persona miss`, or `environment issue`
3. do not overwrite the failing artifact with a retry until the failure has been summarized

Use [FAILURE_TAXONOMY.md](/E:/桌面/amadeus-thread0/docs/FAILURE_TAXONOMY.md) for labels.

## Exit Condition

The project is ready for an advisor or committee demo when:

- all baseline suites are green
- the Technical Preview RC audit reports `technical_preview_rc_phase1_ready`
- the repeated probe report is reproducible
- the demo script runs without ad-hoc prompt engineering
- the user-study packet is ready for participant execution
