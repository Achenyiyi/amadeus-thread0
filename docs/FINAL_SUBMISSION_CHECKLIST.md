# Final Submission Checklist

Updated: 2026-03-07

Use this checklist in the final 72 hours before submission or defense packaging. The rule is simple: do not trust memory, only trust checked items.

## A. Repository State

- `.env` is not staged
- real `data/` content is not staged
- `evals/reports/` contains the referenced canonical reports
- `user_study/raw/`, `user_study/results/`, and `user_study/packets/` are excluded from version control
- no temporary experiment directories remain
- `git status` is understood; nothing surprising is left unexplained

## B. Runtime Verification

- `python -m py_compile amadeus_thread0\*.py evals\*.py user_study\*.py` passes
- `python -m amadeus_thread0.cli` starts cleanly
- `/persona` works
- `/worldline` works
- `/bond` works
- `/sources` works
- no duplicate final output appears in a short manual chat

## C. Baseline Reports

- `regression_isolated` canonical report exists and is green
- `long_thread` canonical report exists and is green
- `experience_probe` canonical report exists and is green
- `thesis_probe` canonical report exists and is green
- backend reliability report exists and is green
- repeated probe variance report exists and matches the current cited numbers

## D. Documentation Consistency

- `README.md` lists the current official assets
- `docs/EVAL_BASELINE.md` references the latest canonical baseline
- `docs/ABLATION_RESULTS.md` matches the latest repeated probe interpretation
- `docs/ADVISOR_REPRO_RUNBOOK.md` reflects current commands
- `docs/DEMO_SCRIPT.md` matches the current CLI behavior
- `docs/DEFENSE_TALK_TRACK.md` matches the current thesis framing
- `docs/DEFENSE_QA_BANK.md` exists and is internally consistent
- `docs/THESIS_FIGURE_MAP.md` references real report files
- `docs/FINAL_DELIVERY_MANIFEST.md` covers all formal deliverables

## E. Thesis Experiment Assets

- one canonical baseline table source is fixed
- one subsystem ablation table source is fixed
- one repeated probe report is fixed
- one long-thread comparison pair is fixed
- one persona qualitative case pair is selected
- one worldline qualitative case pair is selected
- user-study protocol, legacy capability script, consent, checklist, and current daily/persona evaluation entry are all present

## F. User Study Readiness

- `python user_study\prepare_study_run.py --participants 16 --out-dir user_study\raw` works
- `python user_study\export_participant_packets.py --assignment user_study\raw\assignment.csv --out-dir user_study\packets` works
- participant packet output is readable
- operator schedule is generated
- questionnaire template is ready
- session log template is ready
- facilitator knows the A/B order rule

## G. Demo Readiness

- one stable `.env` is prepared for the demo machine
- network access to model APIs is confirmed
- if TTS is used, speaker output is confirmed
- if TTS is disabled, text-only fallback is confirmed
- the six demo scenarios are rehearsed in order
- one backup thread is prepared in case a live run drifts
- one backup report set is ready for offline explanation

## H. Defense Readiness

- one-minute opening can be delivered without notes
- four main contributions can be stated in under 30 seconds
- the difference between system contribution and prompt engineering can be answered directly
- the reason for choosing LangGraph can be answered directly
- the reason for not fine-tuning first can be answered directly
- current limitations can be stated honestly without sounding unprepared

## I. Packaging

- final code snapshot is committed locally
- remote backup exists
- key report files are duplicated to a safe archive location if needed
- thesis figures/tables source files are recorded
- no sensitive personal data is included in screenshots or reports

## J. Final Stop Rule

Before the final submission or defense package is frozen, confirm:

1. if a claim appears in slides or thesis text, there is a real report file behind it
2. if a demo step appears in the script, it has been rehearsed on the current code
3. if a metric appears in a table, its source report is named explicitly
4. if a limitation exists, it is acknowledged rather than hidden

If any one of these four fails, do not call the package final.
