import assistantTurnJson from "../mocks/assistant_turn.json";
import bondViewJson from "../mocks/bond_view.json";
import eventRoundJson from "../mocks/event_round.json";
import personaViewJson from "../mocks/persona_view.json";
import worldlineViewJson from "../mocks/worldline_view.json";
import type { BackendEnvelopeFor, ClaimLink, SourceRef } from "../contracts/backend";

export type TranscriptEnvelope =
  | BackendEnvelopeFor<"assistant_turn">
  | BackendEnvelopeFor<"event_round">;

export interface TranscriptEntry {
  id: string;
  envelope: TranscriptEnvelope;
}

export interface MockSession {
  threadId: string;
  schemaVersion: string;
  transcript: TranscriptEntry[];
  persona: BackendEnvelopeFor<"persona_view">;
  worldline: BackendEnvelopeFor<"worldline_view">;
  bond: BackendEnvelopeFor<"bond_view">;
  sources: SourceRef[];
  claimLinks: ClaimLink[];
}

const assistantTurn = assistantTurnJson as BackendEnvelopeFor<"assistant_turn">;
const eventRound = eventRoundJson as BackendEnvelopeFor<"event_round">;
const personaView = personaViewJson as BackendEnvelopeFor<"persona_view">;
const worldlineView = worldlineViewJson as BackendEnvelopeFor<"worldline_view">;
const bondView = bondViewJson as BackendEnvelopeFor<"bond_view">;

export async function loadMockSession(): Promise<MockSession> {
  const transcript: TranscriptEntry[] = [
    { id: `${assistantTurn.kind}-${assistantTurn.generated_at}`, envelope: assistantTurn },
    { id: `${eventRound.kind}-${eventRound.generated_at}`, envelope: eventRound },
  ].sort((left, right) => left.envelope.generated_at - right.envelope.generated_at);

  return {
    threadId: assistantTurn.thread_id,
    schemaVersion: assistantTurn.schema_version,
    transcript,
    persona: personaView,
    worldline: worldlineView,
    bond: bondView,
    sources: assistantTurn.payload.sources,
    claimLinks: assistantTurn.payload.claim_links,
  };
}
