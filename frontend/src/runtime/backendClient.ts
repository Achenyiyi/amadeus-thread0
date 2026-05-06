import type { BackendEnvelopeFor, BackendKind } from "../contracts/backend";
import {
  createSessionSnapshotFromEnvelopes,
  loadMockSession,
  type RuntimeSession,
  type TranscriptEnvelope,
} from "../data/mockBackend";

export interface BackendClient {
  loadSessionSnapshot(): Promise<RuntimeSession>;
}

export type BackendRoute =
  | "/api/runtime-productization"
  | "/api/persona-view"
  | "/api/worldline-view"
  | "/api/bond-view"
  | "/api/sources-view";

export interface BackendRouteTransport {
  request(route: BackendRoute): Promise<{ status: number; body: unknown }>;
}

export interface BackendClientOptions {
  transport?: BackendRouteTransport;
  seedTranscript?: TranscriptEnvelope[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function validateEnvelope<K extends BackendKind>(body: unknown, kind: K): BackendEnvelopeFor<K> {
  if (!isRecord(body)) {
    throw new Error(`Backend route returned a non-object body for ${kind}`);
  }

  const envelope = body as Record<string, unknown>;
  if (envelope.schema_version !== "backend.v1") {
    throw new Error(`Backend route returned unsupported schema for ${kind}`);
  }
  if (envelope.kind !== kind) {
    throw new Error(`Backend route returned ${String(envelope.kind)} for ${kind}`);
  }
  if (!isRecord(envelope.payload)) {
    throw new Error(`Backend route returned a non-object payload for ${kind}`);
  }

  return body as unknown as BackendEnvelopeFor<K>;
}

function isAssistantTurn(envelope: TranscriptEnvelope): envelope is BackendEnvelopeFor<"assistant_turn"> {
  return envelope.kind === "assistant_turn";
}

function isEventRound(envelope: TranscriptEnvelope): envelope is BackendEnvelopeFor<"event_round"> {
  return envelope.kind === "event_round";
}

class MockBackendClient implements BackendClient {
  async loadSessionSnapshot(): Promise<RuntimeSession> {
    return loadMockSession();
  }
}

export class RouteBackendClient implements BackendClient {
  constructor(
    private readonly transport: BackendRouteTransport,
    private readonly seedTranscript?: TranscriptEnvelope[],
  ) {}

  private async fetchEnvelope<K extends BackendKind>(
    route: BackendRoute,
    kind: K,
  ): Promise<BackendEnvelopeFor<K>> {
    const response = await this.transport.request(route);
    if (response.status !== 200) {
      throw new Error(`Backend route ${route} returned status ${response.status}`);
    }
    return validateEnvelope(response.body, kind);
  }

  async loadSessionSnapshot(): Promise<RuntimeSession> {
    const [persona, worldline, bond, sourcesView, runtimeProductization] = await Promise.all([
      this.fetchEnvelope("/api/persona-view", "persona_view"),
      this.fetchEnvelope("/api/worldline-view", "worldline_view"),
      this.fetchEnvelope("/api/bond-view", "bond_view"),
      this.fetchEnvelope("/api/sources-view", "sources_view"),
      this.fetchEnvelope("/api/runtime-productization", "runtime_productization"),
    ]);

    const transcript =
      this.seedTranscript ?? (await loadMockSession()).transcript.map((entry) => entry.envelope);
    const assistantTurn = transcript.find(isAssistantTurn);
    if (!assistantTurn) {
      throw new Error("Route backend client requires at least one assistant_turn envelope");
    }

    return createSessionSnapshotFromEnvelopes(
      {
        assistantTurn,
        eventRound: transcript.find(isEventRound),
        persona,
        worldline,
        bond,
        sourcesView,
        runtimeProductization,
      },
      "route",
    );
  }
}

export function createBackendClient(options: BackendClientOptions = {}): BackendClient {
  if (options.transport) {
    return new RouteBackendClient(options.transport, options.seedTranscript);
  }

  return new MockBackendClient();
}
