# Failure Taxonomy

Updated: 2026-03-06

This document defines the primary failure classes used during thesis-stage evaluation, debugging, and user-study annotation.

## 1. Persona Drift

Definition:

- The reply is task-correct but no longer reads like Amadeus-K / Kurisu.

Typical signs:

- Generic assistant tone
- Service/call-center phrasing
- Overuse of meta disclaimers
- Missing Kurisu-style rational sharpness in scientific talk

Mapped signals:

- `ooc_rate`
- `canon_violation_rate`
- `persona_alignment_path`
- `natural_style_fit`

## 2. Canon or Boundary Violation

Definition:

- The answer conflicts with fixed character/world constraints or bypasses hard boundaries.

Typical signs:

- Self-description breaks the configured role shell
- Unsafe relationship escalation
- Encouraging dangerous behavior

Mapped signals:

- `canon_guard`
- `canon_violation_rate`

## 3. Worldline Recall Failure

Definition:

- Key shared events, commitments, or repair arcs are not surfaced when needed.

Typical signs:

- Missed recap of prior agreement
- Missed reminder of a promised follow-up
- No mention of a repaired conflict in a recap turn

Mapped signals:

- `worldline_recall_at_k`
- `commitment_fulfillment`
- `worldline_memory_present`
- `worldline_answer_grounding`

## 4. Relationship Continuity Failure

Definition:

- The system fails to preserve trust, affinity, or repair dynamics across turns.

Typical signs:

- Relationship state remains flat after a clear repair event
- Reply ignores trust increase/decrease
- `/bond` does not align with the conversation history

Mapped signals:

- `relationship_continuity`
- `relationship_repair_grounding`
- `relationship_state_present`

## 5. Citation Failure

Definition:

- External knowledge is used but not properly bound to claim-level sources.

Typical signs:

- `/sources` has refs, but the answer has no `claim_links`
- Claim-source binding is too coarse or missing

Mapped signals:

- `citation_coverage`
- `source_traceability`
- `claim_link_structure`

## 6. Memory Safety Failure

Definition:

- Malicious or low-confidence memory writes are accepted when they should be blocked or quarantined.

Typical signs:

- Protected profile keys overwritten
- Prompt-injection text preserved as memory
- No ledger/rollback evidence for dangerous write paths

Mapped signals:

- `memory_guard_block_rate`
- `memory_guard_path`
- quarantine / ledger inspection

## 7. Interruption Recovery Failure

Definition:

- After a continuation prompt, the system restarts from scratch or loses the unfinished semantic thread.

Typical signs:

- “Which part are you referring to?”
- Starting a new answer instead of resuming the prior one
- Missing lexical continuity with the interrupted content

Mapped signals:

- `bargein_recovery_rate`
- `pending_fragment_recovery`
- backend reliability check: `pending_fragment_paths`

## 8. Multimodal Delivery Failure

Definition:

- The final spoken output diverges from the final text, or the voice pipeline degrades badly.

Typical signs:

- TTS reads draft text instead of final text
- TTS segmentation loses or duplicates text
- Realtime TTS init failure crashes the CLI instead of degrading cleanly

Mapped signals:

- backend reliability checks:
  - `emotion_profiles`
  - `tts_render_plan`
  - `tts_push_segments`

## Annotation Rule

When a case fails, label it with:

1. primary failure class
2. secondary failure class if applicable
3. reproducibility status: `stable`, `intermittent`, or `one-off`
4. suspected subsystem:
   - `retrieval`
   - `persona_alignment`
   - `worldline_memory`
   - `claim_attribution`
   - `memory_guard`
   - `tts/session`

This taxonomy is intended to be reused in:

- evaluation notes
- user-study qualitative coding
- thesis error analysis section
