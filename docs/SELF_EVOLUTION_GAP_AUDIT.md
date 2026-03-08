# Self-Evolution Engine Gap Audit

## Verdict

Current Amadeus-K already contains the beginnings of a self-evolution system, but it is not yet a cleanly separated general-purpose engine.

The strongest parts today are:

- Persona anchoring
- Worldline memory structure
- continuity-oriented retrieval

The weakest parts today are:

- explicit bond dynamics
- allostasis / internal need regulation
- reconsolidation as an explicit update path
- policy derivation as an explicit runtime layer

## Current Mapping

### Persona Core

Status: `partially implemented, strong`

Current evidence:

- [graph.py:1639](/E:/桌面/amadeus-thread0/amadeus_thread0/graph.py#L1639)
- [graph.py:1946](/E:/桌面/amadeus-thread0/amadeus_thread0/graph.py#L1946)
- [graph.py:2140](/E:/桌面/amadeus-thread0/amadeus_thread0/graph.py#L2140)

Notes:

- counterpart anchoring is explicit
- canon shell is explicit
- still prompt-heavy instead of schema-heavy

### Affect Engine

Status: `implemented as v0`

Current evidence:

- [graph.py:1320](/E:/桌面/amadeus-thread0/amadeus_thread0/graph.py#L1320)
- [graph.py:1335](/E:/桌面/amadeus-thread0/amadeus_thread0/graph.py#L1335)

What exists:

- emotion labels
- valence/arousal
- linger
- apology-sensitive decay

What is missing:

- recovery rate as explicit state
- volatility as explicit state
- multi-cause appraisal
- co-regulation dynamics

### Bond Engine

Status: `coarse heuristic`

Current evidence:

- [memory_store.py:787](/E:/桌面/amadeus-thread0/amadeus_thread0/memory_store.py#L787)
- [memory_store.py:1039](/E:/桌面/amadeus-thread0/amadeus_thread0/memory_store.py#L1039)

What exists:

- `stage`
- `affinity_score`
- `trust_score`

What is missing:

- hurt
- irritation
- engagement drive
- repair confidence
- withdrawal / re-approach modeling

### Allostasis Engine

Status: `missing`

What is missing:

- safety regulation
- closeness need
- competence need
- autonomy need
- cognitive budget

This is the main reason the current system still feels reactive rather than alive.

### Worldline-Reconsolidation Engine

Status: `worldline strong, reconsolidation weak`

Current evidence:

- [memory_store.py:929](/E:/桌面/amadeus-thread0/amadeus_thread0/memory_store.py#L929)
- [memory_store.py:959](/E:/桌面/amadeus-thread0/amadeus_thread0/memory_store.py#L959)
- [memory_store.py:985](/E:/桌面/amadeus-thread0/amadeus_thread0/memory_store.py#L985)
- [memory_store.py:1520](/E:/桌面/amadeus-thread0/amadeus_thread0/memory_store.py#L1520)
- [graph.py:1407](/E:/桌面/amadeus-thread0/amadeus_thread0/graph.py#L1407)

What exists:

- identity facts
- shared events
- conflict repair
- worldline events
- relationship timeline
- commitments
- reflections

What is missing:

- explicit unresolved tensions
- semantic self-narratives
- explicit reactivation/compare/revise trace
- a stable revision policy instead of mostly additive storage

### Behavior Policy Engine

Status: `implicit only`

Current evidence:

- [graph.py:1639](/E:/桌面/amadeus-thread0/amadeus_thread0/graph.py#L1639)
- [graph.py:1946](/E:/桌面/amadeus-thread0/amadeus_thread0/graph.py#L1946)

What exists:

- prompt-level steering through emotion hint
- tsundere intensity
- response style hint

What is missing:

- explicit `warmth / sharpness / initiative / disclosure / withdrawal` state
- separation between policy derivation and language rendering

## Engineering Priority

### Priority P0

- freeze schema v1
- add explicit `bond_state`
- add explicit `allostasis_state`
- add explicit `behavior_policy`

### Priority P1

- connect memory updates to reconsolidation traces
- add unresolved tension tracking
- make apology produce partial bond repair, not only emotion decay

### Priority P2

- add transfer test with a second character shell
- prove the engine is reusable rather than Kurisu-specific

Status update:

- `transfer_probe_second_persona` has been added to backend reliability checks
- semantic narratives are now rendered through actor/counterpart labels instead of hardcoded Kurisu/Okabe text
- what remains is broader product-level transfer, not structural transfer only

## Short Summary

Current code already proves the thesis direction.

It does not yet prove that the project has a complete general digital persona evolution engine.

To cross that line, the next milestone is not more prompt tuning. It is explicit state separation.
