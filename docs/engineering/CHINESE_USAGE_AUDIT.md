# Chinese Usage Audit

This audit inventories where Chinese appears in the codebase, what each usage is doing, how model-switch-safe it is, and what should be preserved vs. replaced over time.

Audit date: `2026-03-28`

## Scope

- Runtime source scanned: `amadeus_thread0/**/*.py`
- Runtime source files with Chinese: `41`
- Runtime source Chinese-bearing lines: `3424`
- Runtime source Chinese-bearing chars: `61981`
- Eval authored files with Chinese: `16`
- Eval generated `_tmp` artifacts with Chinese: `1603`
- Test files with Chinese: `38`

Important split:

- `runtime source` matters for actual product behavior
- `tests/evals` matter for regression and measurement
- `evals/_tmp` is generated output, not authored logic

## Category Summary

### A. User-Facing UX / Admin / Operator Text

Primary purpose:

- CLI help text
- admin error messages
- audit recommendations
- comments/docstrings for operators

Files:

- `amadeus_thread0/cli.py`
- `amadeus_thread0/runtime/memory_admin.py`
- `amadeus_thread0/runtime/settings.py`
- `amadeus_thread0/runtime/tts_io.py`
- `amadeus_thread0/utils/runtime_audit.py`
- `amadeus_thread0/memory_store.py`

Why Chinese exists here:

- This repository is currently operated in Chinese.
- These strings are mainly for the human operator, not for persona control.
- In `memory_store.py`, some Chinese-looking tokens are mojibake-detection hints, not persona rules.

Does this category need Chinese:

- No. This is not a model constraint category.
- It only needs to match the operator language.

Model-switch robustness:

- High.
- Switching models does not materially affect this layer.

### B. Model-Visible Prompting / Context Narration / State Summaries

Primary purpose:

- inject persona-facing context
- summarize motive, rhythm, relationship, continuation, embodied state
- narrate internal continuity in natural language for the model

Files:

- `amadeus_thread0/evolution_engine/reconsolidation.py`
- `amadeus_thread0/graph_parts/autonomy_runtime.py`
- `amadeus_thread0/graph_parts/behavior_agenda.py`
- `amadeus_thread0/graph_parts/behavior_runtime.py`
- `amadeus_thread0/graph_parts/dialogue_guidance.py`
- `amadeus_thread0/graph_parts/implicit_idle.py`
- `amadeus_thread0/graph_parts/model_call_prepare.py`
- `amadeus_thread0/graph_parts/persona_runtime.py`
- `amadeus_thread0/graph_parts/prepare_turn_runtime.py`
- `amadeus_thread0/graph_parts/prompt_helpers.py`
- `amadeus_thread0/graph_parts/prompting.py`
- `amadeus_thread0/graph_parts/relational_runtime.py`
- `amadeus_thread0/graph_parts/runtime_prompting.py`
- `amadeus_thread0/graph_parts/semantic_narrative.py`
- `amadeus_thread0/graph_parts/turn_events.py`
- `amadeus_thread0/persona_authority.py`

Why Chinese exists here:

- The target interaction language is Chinese.
- These strings are often fed back into the model as context.
- Keeping dialogue context, relationship summaries, and behavior framing in the same language reduces translation drift and pragmatic mismatch.

Does this category need Chinese:

- Not strictly.
- But if the user-facing conversation is Chinese, using Chinese here is currently the most stable choice.
- If this layer stays as free-form natural-language context, it should usually stay in the same language as the conversation.

Model-switch robustness:

- Medium to high.
- Most Chinese-capable models can consume these summaries.
- But different models weight soft natural-language context differently, so exact behavior will vary.

### C. Chinese Input Routing / Appraisal Fallback / Lightweight Scene Detection

Primary purpose:

- detect `继续 / 换个话题 / 不是这一段` style routing cues
- detect low-confidence fallback signals such as coercion, apology, boundary testing, soft-support tone
- classify scene hints when the appraisal model is uncertain

Files:

- `amadeus_thread0/evolution_engine/policy.py`
- `amadeus_thread0/graph_parts/affect_dynamics.py`
- `amadeus_thread0/graph_parts/appraisal.py`
- `amadeus_thread0/graph_parts/counterpart_dynamics.py`
- `amadeus_thread0/runtime/session_orchestrator.py`

Why Chinese exists here:

- These detectors read Chinese user input directly.
- If you implement continuation or fallback logic as lexical matching, the lexical markers must be in the same language as the incoming utterance.

Does this category need Chinese:

- Only if this category remains lexical.
- The real requirement is `same language as observed text`, not “Chinese forever.”

Model-switch robustness:

- Mostly independent of model output.
- Still brittle to user paraphrase, slang drift, and multilingual mixing.
- Safer than output-side heuristics, but still not ideal long-term.

### D. Tool / Memory / Safety Free-Text Parsing

Primary purpose:

- parse natural-language tool requests
- detect memory-write instructions
- detect approval/upgrade requests
- block memory injection patterns

Files:

- `amadeus_thread0/config.py`
- `amadeus_thread0/graph_parts/tool_nodes.py`
- `amadeus_thread0/graph_parts/tooling.py`
- `amadeus_thread0/runtime/tool_approval.py`
- `amadeus_thread0/utils/tool_registry.py`
- `amadeus_thread0/utils/tools.py`

Why Chinese exists here:

- The user issues tool-related requests in Chinese.
- Safety-relevant or memory-relevant prompts can also be phrased in Chinese.
- If you parse free text directly, you need same-language lexical coverage.

Does this category need Chinese:

- Only if tool invocation and approval intent continue to be inferred from free text.
- If tool use is fully structured, this category can shrink sharply.

Model-switch robustness:

- Medium.
- User-side phrases stay fairly stable.
- But model-generated phrasing around tool or memory requests can vary.

### E. Output Surface Detection / Rewrite / Postprocess Filtering

Primary purpose:

- detect assistant-meta tone
- detect technical self-activity leakage
- detect stagey or template-like Chinese output
- down-rank or rewrite awkward Chinese replies

Files:

- `amadeus_thread0/graph_parts/generation_profile.py`
- `amadeus_thread0/graph_parts/guards.py`
- `amadeus_thread0/graph_parts/postprocess.py`
- `amadeus_thread0/graph_parts/rewrite.py`
- `amadeus_thread0/graph_parts/response_finalize.py`

Why Chinese exists here:

- These functions inspect generated Chinese text directly.
- If the bad output pattern is expressed in Chinese, the detector must match Chinese surface forms.

Does this category need Chinese:

- Yes, if you continue to use surface regex/phrase detectors.
- But this is the least future-proof category and the first one that should be replaced by learned or structured methods.

Model-switch robustness:

- Low.
- This category is the most model-specific.
- When the base model changes, failure modes and stylistic artifacts often change first, making this layer stale quickly.

### F. Memory Extraction / Continuity Trace Heuristics

Primary purpose:

- detect repair residue, commitments, future anchors, unresolved tension, continuity traces
- help decide what enters long-term memory or relationship carryover

Files:

- `amadeus_thread0/graph_parts/memory_evolution.py`
- `amadeus_thread0/graph_parts/relational_carryover.py`
- `amadeus_thread0/graph_parts/retrieval.py`

Why Chinese exists here:

- The source dialogue being summarized is Chinese.
- If commitment or residue extraction uses markers, those markers must match the language of the dialogue.

Does this category need Chinese:

- Only if memory extraction remains marker-based.
- If extraction becomes structured and semantic, Chinese lexical lists are no longer required as the primary mechanism.

Model-switch robustness:

- Medium.
- Better than output-surface heuristics, worse than explicit structured extraction.

## What Actually Uses Chinese as a Real Constraint

Strictly speaking, not every Chinese string here is a `constraint`.

Real constraint-heavy categories are:

- Category C: input lexical routing / fallback
- Category D: free-text tool and safety parsing
- Category E: output surface filtering
- Category F: memory extraction markers

Categories A and B mostly use Chinese because the product language is Chinese, not because they are hard-coded behavior controllers.

## Portability by Category

- Most portable:
  - Category A
  - Category B
- Medium portability:
  - Category C
  - Category D
  - Category F
- Least portable:
  - Category E

## Source of Current Concentration

The heaviest Chinese-bearing runtime files are:

- `amadeus_thread0/graph_parts/postprocess.py` -> `1412` lines
- `amadeus_thread0/graph_parts/memory_evolution.py` -> `342` lines
- `amadeus_thread0/graph_parts/rewrite.py` -> `294` lines
- `amadeus_thread0/graph_parts/behavior_runtime.py` -> `143` lines
- `amadeus_thread0/cli.py` -> `114` lines
- `amadeus_thread0/graph_parts/runtime_prompting.py` -> `108` lines
- `amadeus_thread0/graph_parts/prompting.py` -> `96` lines
- `amadeus_thread0/utils/tools.py` -> `92` lines

This matters because:

- `postprocess.py` and `rewrite.py` are the most model-sensitive Chinese-heuristic zone
- `memory_evolution.py` is the largest Chinese-marker memory zone
- `behavior_runtime.py` and prompting files are Chinese because the system currently narrates internal state to the model in Chinese

## Tests and Evals

Authored evaluation and test code also uses Chinese heavily.

Why:

- The product target is Chinese long-term companionship.
- Persona realism, repair behavior, support behavior, and naturalness are being measured in Chinese.

Eval/test split:

- authored eval files with Chinese: `16`
- generated eval `_tmp` artifacts with Chinese: `1603`
- test files with Chinese: `38`

These are not runtime constraints in themselves.

## Bottom-Line Engineering Recommendation

- Preserve Category A as-is.
- Preserve Category B for now, but gradually compress it into more structured state packets.
- Keep only the minimum viable subset of Category C and D needed for routing, approval, and safety.
- Reduce Category E first.
- Replace Category F with semantic extraction as soon as a reliable structured extractor is in place.

## Deferred Replacement Direction

This audit does **not** change the current mainline phase.

Current decision:

- mainline remains `digital body / access / resource` buildout
- Chinese-heavy lexical cleanup is recorded as a `future enablement direction`
- the replacement mechanism is intentionally left undecided until that phase is opened explicitly

When that phase starts, the working replacement candidates are:

1. `Structured state extractors`
   - replace marker-heavy memory / appraisal heuristics with schema-first extraction
2. `Small semantic classifiers`
   - for example SetFit-style scene / residue / tone classification instead of phrase lists
3. `CrossEncoder semantic scorers or rerankers`
   - score candidate replies or residue interpretations semantically instead of with regex-heavy Chinese surface matching
4. `Preference optimization / DPO-style tuning`
   - shift naturalness and persona-surface quality away from postprocess regex repair
5. `PEFT / LoRA / QLoRA-style role tuning`
   - only after the runtime contract is stable enough that model tuning is solving the right problem

Selection rule for later:

- start from the least invasive mechanism that removes the most brittle lexical Chinese dependency
- prioritize Category E first, then Category F
- keep only the minimum safety / routing / approval lexical rules that still serve auditability and boundary enforcement
