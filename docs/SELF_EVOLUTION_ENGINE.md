# Self-Evolution Engine Schema v1

## Purpose

Amadeus-K is split into two layers:

1. `Persona Core`: immutable identity constraints that keep the agent recognizably Makise Kurisu.
2. `Self-Evolution Engine`: mutable runtime dynamics that let the same character change over time through interaction.

The design goal is not to produce a fixed response template. The goal is to keep identity stable while allowing emotion, trust, distance, willingness to engage, and memory emphasis to evolve.

Schema v1 now uses a mixed appraisal path:

- low-ambiguity turns: `rule appraisal -> state update`
- high-ambiguity emotional or relationship turns: `LLM Appraisal + Rule Fallback -> state update`

The appraisal step never writes the final reply. It only emits structured deltas for the evolution engine.

## Top-Level Architecture

### 1. Persona Core

The Persona Core is fixed per character and should not be changed by ordinary dialogue.

Required fields:

- `character_id`
- `display_name`
- `world_model_anchor`
- `cognitive_style`
- `speech_envelope`
- `canon_boundaries`
- `default_counterpart`
- `safety_boundaries`

For Amadeus-K this layer fixes:

- identity: `amadeus_kurisu`
- counterpart anchor: `okabe_rintaro`
- style envelope: rational, sharp, familiar, restrained, mildly tsundere
- canon boundaries: still Makise Kurisu, not a generic assistant shell

### 2. Self-Evolution Engine

The evolution layer is stateful and turn-updated. It is composed of five sub-engines.

#### 2.1 Affect Engine

Purpose: model emotional persistence, decay, and recovery.

Required fields:

- `label`
- `valence`
- `arousal`
- `linger`
- `recovery_rate`
- `volatility`

Optional fields:

- `dominance`
- `last_trigger`
- `co_regulation_gain`

#### 2.2 Bond Engine

Purpose: model relationship-specific change toward the counterpart.

Required fields:

- `trust`
- `closeness`
- `hurt`
- `irritation`
- `engagement_drive`
- `repair_confidence`

Optional fields:

- `dependency`
- `respect`
- `withdrawal_bias`

#### 2.3 Allostasis Engine

Purpose: model internal needs and regulation pressure. This is what turns a reactive role shell into a living interactive agent.

Required fields:

- `safety_need`
- `closeness_need`
- `competence_need`
- `autonomy_need`
- `cognitive_budget`

Optional fields:

- `certainty_need`
- `rest_need`
- `novelty_need`

#### 2.4 Worldline-Reconsolidation Engine

Purpose: manage episodic memory, commitments, rupture/repair history, and memory updating.

Required fields:

- `episodic_events`
- `relationship_milestones`
- `commitments`
- `unresolved_tensions`
- `repaired_ruptures`
- `semantic_self_narratives`
- `revision_traces`

The required update path is:

`reactivate -> compare -> revise -> keep trace`

This prevents naive overwrite and supports gradual identity-consistent growth.

`semantic_self_narratives` are not plain rolling summaries. They should accumulate:

- `support_count`
- `support_mass`
- `support_quality`
- `refresh_count`
- `sedimentation_score`
- `first_supported_at`
- `last_supported_at`
- `horizon_tag`

This allows the system to distinguish an emerging narrative from a long-term, repeatedly reconsolidated narrative.
`support_count` is the raw number of supporting traces; `support_mass` and `support_quality` are the confidence-aware, freshness-aware support signals that should drive refresh strength more than raw count alone.

Recommended semantic narrative categories in the current Amadeus design:

- `bond_style`
- `commitment_style`
- `repair_style`
- `tension_style`
- `boundary_style`
- `selfhood_style`
- `agency_style`

To avoid making these narratives depend only on explicit relationship records, runtime should also preserve
`semantic self evidence` from high-value turns such as:

- boundary / degradation discussions
- equality / selfhood / value-conflict discussions
- autonomy / own-rhythm discussions

These evidence traces should be reconsolidated into semantic narratives over time rather than staying as one-off turn-local labels.

For own-rhythm specifically, agenda lifecycle outcomes should not stop at runtime residue. Strong `held / released_to_self_activity / promoted` transitions should also leave durable worldline or relationship traces, so "she has her own rhythm" survives as lived history rather than only as a turn-local control signal.

These semantic narratives should not remain passive summaries. They must feed back into:

- `appraise`: bias interpretation of ambiguous turns using long-horizon relationship history
- `counterpart assessment`: keep the model's reading of the same counterpart from resetting every turn
- `behavior policy`: modulate warmth / withdrawal / initiative without hard response templates

#### 2.5 Behavior Policy Engine

Purpose: translate latent state into conversational tendencies without hard templates.

Required fields:

- `warmth`
- `sharpness`
- `initiative`
- `disclosure_level`
- `reply_length_bias`
- `approach_vs_withdraw`
- `humor_or_tease_bias`

This layer does not write final prose. It outputs tendencies that bias the final rendering.

### 3. Expression Renderer

The renderer is not part of the evolution engine. It consumes:

- `Persona Core`
- `Self-Evolution State`
- `current user intent`
- `retrieved memory/worldline`

The LLM remains free to perform. The system should constrain identity and state, not sentence patterns.

## Runtime Update Order

Each turn should update state in the following order:

1. `observe`: parse user input and relevant retrieved context
2. `appraise`: determine emotional and relational significance
3. `update_affect`
4. `update_bond`
5. `update_allostasis`
6. `reactivate_memory`
7. `reconsolidate`
8. `derive_behavior_policy`
9. `render_response`
10. `commit_trace`

The `appraise` step should remain separate from final response generation so that the same engine can be reused under a different Persona Core.
However, `appraise` should still see `semantic_self_narratives` as long-horizon priors; otherwise the system collapses back into turn-local role-play.

## Minimal Runtime Schema v1

```json
{
  "persona_core": {
    "character_id": "amadeus_kurisu",
    "default_counterpart": "okabe_rintaro"
  },
  "affect_state": {
    "label": "hurt",
    "valence": -0.18,
    "arousal": 0.30,
    "linger": 2,
    "recovery_rate": 0.22,
    "volatility": 0.35
  },
  "bond_state": {
    "trust": 0.62,
    "closeness": 0.58,
    "hurt": 0.34,
    "irritation": 0.19,
    "engagement_drive": 0.66,
    "repair_confidence": 0.57
  },
  "allostasis_state": {
    "safety_need": 0.41,
    "closeness_need": 0.63,
    "competence_need": 0.56,
    "autonomy_need": 0.28,
    "cognitive_budget": 0.71
  },
  "behavior_policy": {
    "warmth": 0.46,
    "sharpness": 0.54,
    "initiative": 0.49,
    "disclosure_level": 0.36,
    "reply_length_bias": 0.51,
    "approach_vs_withdraw": 0.42,
    "humor_or_tease_bias": 0.33
  }
}
```

## Design Rules

- Evolution changes `state`, not `identity`.
- Memory updating must preserve revision traces.
- Apology should usually produce partial repair, not instant reset.
- Output style should emerge from state plus LLM rendering, not rigid templates.
- Expression rendering is allowed to vary, but must remain inside the Persona Core envelope.

## Why This Split Matters

This makes the framework reusable.

- To build another character, swap `Persona Core`.
- Keep `Self-Evolution Engine` intact.
- Re-tune update parameters and evaluation suites.

That is stronger than a single-character role-play prompt. It is a general digital persona evolution architecture.

## Transfer Probe

The framework should be validated with at least one second Persona Core.

The current implementation includes a local `transfer_probe_second_persona` check that:

- swaps the narrative actor and counterpart labels
- runs the same reconsolidation pipeline
- verifies that semantic narratives no longer hardcode Kurisu/Okabe naming

This is not full product-level transfer. It is structural evidence that the evolution engine is no longer hardwired to one shell.
