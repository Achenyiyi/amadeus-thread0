import assistantTurnJson from "../mocks/assistant_turn.json";
import bondViewJson from "../mocks/bond_view.json";
import eventRoundJson from "../mocks/event_round.json";
import personaViewJson from "../mocks/persona_view.json";
import worldlineViewJson from "../mocks/worldline_view.json";
import type { BackendEnvelopeFor, ClaimLink, SourceRef } from "../contracts/backend";

export type TransportMode = "mock" | "route";

export type TranscriptEnvelope =
  | BackendEnvelopeFor<"assistant_turn">
  | BackendEnvelopeFor<"event_round">;

export interface TranscriptEntry {
  id: string;
  envelope: TranscriptEnvelope;
}

export interface SessionEnvelopeSet {
  assistantTurn: BackendEnvelopeFor<"assistant_turn">;
  eventRound?: BackendEnvelopeFor<"event_round">;
  persona: BackendEnvelopeFor<"persona_view">;
  worldline: BackendEnvelopeFor<"worldline_view">;
  bond: BackendEnvelopeFor<"bond_view">;
  sourcesView?: BackendEnvelopeFor<"sources_view">;
  runtimeProductization?: BackendEnvelopeFor<"runtime_productization">;
}

export interface RuntimeSession {
  threadId: string;
  schemaVersion: string;
  transportMode: TransportMode;
  transcript: TranscriptEntry[];
  persona: BackendEnvelopeFor<"persona_view">;
  worldline: BackendEnvelopeFor<"worldline_view">;
  bond: BackendEnvelopeFor<"bond_view">;
  runtimeProductization?: BackendEnvelopeFor<"runtime_productization">;
  sources: SourceRef[];
  claimLinks: ClaimLink[];
}

export type MockSession = RuntimeSession;

const assistantTurn = assistantTurnJson as BackendEnvelopeFor<"assistant_turn">;
const eventRound = eventRoundJson as BackendEnvelopeFor<"event_round">;
const personaView = personaViewJson as BackendEnvelopeFor<"persona_view">;
const worldlineView = worldlineViewJson as BackendEnvelopeFor<"worldline_view">;
const bondView = bondViewJson as BackendEnvelopeFor<"bond_view">;

function buildTranscript(
  assistantTurnEnvelope: BackendEnvelopeFor<"assistant_turn">,
  eventRoundEnvelope?: BackendEnvelopeFor<"event_round">,
): TranscriptEntry[] {
  const transcript: TranscriptEntry[] = [
    { id: `${assistantTurnEnvelope.kind}-${assistantTurnEnvelope.generated_at}`, envelope: assistantTurnEnvelope },
    ...(eventRoundEnvelope
      ? [{ id: `${eventRoundEnvelope.kind}-${eventRoundEnvelope.generated_at}`, envelope: eventRoundEnvelope }]
      : []),
  ].sort((left, right) => left.envelope.generated_at - right.envelope.generated_at);

  return transcript;
}

export function createSessionSnapshotFromEnvelopes(
  envelopes: SessionEnvelopeSet,
  transportMode: TransportMode,
): RuntimeSession {
  const transcript = buildTranscript(envelopes.assistantTurn, envelopes.eventRound);
  const sources = envelopes.sourcesView?.payload.sources ?? envelopes.assistantTurn.payload.sources;
  const claimLinks = envelopes.sourcesView?.payload.claim_links ?? envelopes.assistantTurn.payload.claim_links;

  return {
    threadId: envelopes.assistantTurn.thread_id,
    schemaVersion: envelopes.assistantTurn.schema_version,
    transportMode,
    transcript,
    persona: envelopes.persona,
    worldline: envelopes.worldline,
    bond: envelopes.bond,
    runtimeProductization: envelopes.runtimeProductization,
    sources: sources as SourceRef[],
    claimLinks: claimLinks as ClaimLink[],
  };
}

export async function loadMockSession(): Promise<MockSession> {
  return createSessionSnapshotFromEnvelopes(
    {
      assistantTurn,
      eventRound,
      persona: personaView,
      worldline: worldlineView,
      bond: bondView,
    },
    "mock",
  );
}
