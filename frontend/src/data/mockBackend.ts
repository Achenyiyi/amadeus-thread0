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
  threadInventory?: BackendEnvelopeFor<"thread_inventory">;
  runtimeLayout?: BackendEnvelopeFor<"runtime_layout">;
  environmentSummary?: BackendEnvelopeFor<"environment_summary">;
  persona: BackendEnvelopeFor<"persona_view">;
  worldline: BackendEnvelopeFor<"worldline_view">;
  bond: BackendEnvelopeFor<"bond_view">;
  sourcesView?: BackendEnvelopeFor<"sources_view">;
  appraisal?: BackendEnvelopeFor<"appraisal_view">;
  behaviorQueue?: BackendEnvelopeFor<"behavior_queue_view">;
  runtimeProductization?: BackendEnvelopeFor<"runtime_productization">;
  operatorConsoleRc?: BackendEnvelopeFor<"operator_console_rc">;
  desktopCapabilities?: BackendEnvelopeFor<"desktop_capabilities">;
  mediaSession?: BackendEnvelopeFor<"media_session">;
  currentCheckpoint?: BackendEnvelopeFor<"current_checkpoint">;
  checkpointHistory?: BackendEnvelopeFor<"checkpoint_history">;
}

export interface RuntimeSession {
  threadId: string;
  schemaVersion: string;
  transportMode: TransportMode;
  transcript: TranscriptEntry[];
  threadInventory?: BackendEnvelopeFor<"thread_inventory">;
  runtimeLayout?: BackendEnvelopeFor<"runtime_layout">;
  environmentSummary?: BackendEnvelopeFor<"environment_summary">;
  persona: BackendEnvelopeFor<"persona_view">;
  worldline: BackendEnvelopeFor<"worldline_view">;
  bond: BackendEnvelopeFor<"bond_view">;
  sourcesView?: BackendEnvelopeFor<"sources_view">;
  appraisal?: BackendEnvelopeFor<"appraisal_view">;
  behaviorQueue?: BackendEnvelopeFor<"behavior_queue_view">;
  runtimeProductization?: BackendEnvelopeFor<"runtime_productization">;
  operatorConsoleRc?: BackendEnvelopeFor<"operator_console_rc">;
  desktopCapabilities?: BackendEnvelopeFor<"desktop_capabilities">;
  mediaSession?: BackendEnvelopeFor<"media_session">;
  currentCheckpoint?: BackendEnvelopeFor<"current_checkpoint">;
  checkpointHistory?: BackendEnvelopeFor<"checkpoint_history">;
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
  ].sort((left, right) => right.envelope.generated_at - left.envelope.generated_at);

  return transcript;
}

function sortTranscriptDescending(transcript: TranscriptEntry[]): TranscriptEntry[] {
  return [...transcript].sort((left, right) => right.envelope.generated_at - left.envelope.generated_at);
}

function envelopeBase<K extends keyof import("../contracts/backend").BackendEnvelopeMap>(
  kind: K,
  source: BackendEnvelopeFor<"assistant_turn">,
) {
  return {
    schema_version: "backend.v1" as const,
    generated_at: source.generated_at,
    kind,
    thread_id: source.thread_id,
    meta: {
      source: "frontend_mock_default",
    },
  };
}

function defaultThreadInventory(
  source: BackendEnvelopeFor<"assistant_turn">,
): BackendEnvelopeFor<"thread_inventory"> {
  return {
    ...envelopeBase("thread_inventory", source),
    payload: {
      checkpoint_thread_ids: [source.thread_id],
      worldline_dir_ids: [source.thread_id],
      current_thread_id: source.thread_id,
    },
  };
}

function defaultRuntimeLayout(
  source: BackendEnvelopeFor<"assistant_turn">,
): BackendEnvelopeFor<"runtime_layout"> {
  return {
    ...envelopeBase("runtime_layout", source),
    payload: {
      repo_runtime: {
        status: "mock",
        source: "frontend fixture",
      },
      current_runtime: null,
    },
  };
}

function defaultEnvironmentSummary(
  source: BackendEnvelopeFor<"assistant_turn">,
): BackendEnvelopeFor<"environment_summary"> {
  return {
    ...envelopeBase("environment_summary", source),
    payload: {
      cwd: "mock",
      model_provider: "mock",
      model_name: "mock",
      model_base_url: "(mock)",
      runtime_mode: "mock",
      eval_mode: "0",
      user_facing_mode: "1",
      cli_show_turn_summary: "0",
      tts_enabled: "0",
      tts_backend: "",
      tts_ref_audio: "",
      tts_model: "",
      dashscope_api_key_set: false,
    },
  };
}

function defaultSourcesView(
  source: BackendEnvelopeFor<"assistant_turn">,
): BackendEnvelopeFor<"sources_view"> {
  return {
    ...envelopeBase("sources_view", source),
    payload: {
      sources: source.payload.sources ?? [],
      claim_links: source.payload.claim_links ?? [],
    },
  };
}

function defaultAppraisal(
  source: BackendEnvelopeFor<"assistant_turn">,
): BackendEnvelopeFor<"appraisal_view"> {
  return {
    ...envelopeBase("appraisal_view", source),
    payload: {
      turn_appraisal: source.payload.turn_appraisal ?? {},
    },
  };
}

function defaultBehaviorQueue(
  source: BackendEnvelopeFor<"assistant_turn">,
  persona: BackendEnvelopeFor<"persona_view">,
): BackendEnvelopeFor<"behavior_queue_view"> {
  return {
    ...envelopeBase("behavior_queue_view", source),
    payload: {
      behavior_queue: persona.payload.behavior_queue ?? [],
      behavior_queue_summary: persona.payload.behavior_queue_summary ?? [],
      autonomy: persona.payload.autonomy ?? source.payload.autonomy,
    },
  };
}

function defaultRuntimeProductization(
  source: BackendEnvelopeFor<"assistant_turn">,
): BackendEnvelopeFor<"runtime_productization"> {
  return {
    ...envelopeBase("runtime_productization", source),
    payload: {
      schema: "runtime_productization.v1",
      readiness_status: "mock_only",
      console_health: {
        status: "fixture",
      },
      route_inventory: {
        routes: [],
      },
      lanes: {
        ready: [],
        blocked: [],
      },
    },
  };
}

function defaultOperatorConsoleRc(
  source: BackendEnvelopeFor<"assistant_turn">,
): BackendEnvelopeFor<"operator_console_rc"> {
  return {
    ...envelopeBase("operator_console_rc", source),
    payload: {
      schema: "operator_console_rc.v1",
      overall_status: "mock_only",
      readiness_status: "mock_only",
      console_mode: "read_only",
      release_posture: "fixture",
      route_inventory: {
        routes: [],
      },
      authority_boundary: {
        write_routes: ["POST /api/chat/send"],
        blocked: [
          "approval",
          "checkpoint_restore",
          "live_capture",
          "skill_registry_mutation",
          "persona_mutation",
        ],
      },
      next_actions: [],
      failure_reasons: [],
    },
  };
}

function defaultCurrentCheckpoint(
  source: BackendEnvelopeFor<"assistant_turn">,
): BackendEnvelopeFor<"current_checkpoint"> {
  return {
    ...envelopeBase("current_checkpoint", source),
    payload: {
      thread_id: source.thread_id,
      checkpoint_id: null,
    },
  };
}

function desktopAuthorityBoundary(active = false) {
  return {
    schema: "desktop_live_capture.v1",
    live_capture_policy: "explicit_desktop_user_consent_only",
    live_capture_enabled: active,
    live_capture_auto_enabled: false,
    background_capture_allowed: false,
    frontend_semantics_owner: false,
    model_api_auto_call_allowed: false,
    memory_write_allowed_from_frontend: false,
    persona_core_mutation_allowed: false,
  };
}

function defaultDesktopPermissions() {
  return {
    microphone: { status: "not_requested", system_grant: "unknown", requested_at: 0 },
    camera: { status: "not_requested", system_grant: "unknown", requested_at: 0 },
    artifact: { status: "not_requested", system_grant: "unknown", requested_at: 0 },
  };
}

function defaultMediaSession(
  source: BackendEnvelopeFor<"assistant_turn">,
): BackendEnvelopeFor<"media_session"> {
  return {
    ...envelopeBase("media_session", source),
    payload: {
      schema: "media_session.v1",
      status: "stopped",
      active: false,
      session_id: "",
      permissions: defaultDesktopPermissions(),
      latest_media_turn: {},
      latest_artifact: {},
      authority_boundary: desktopAuthorityBoundary(false),
    },
  };
}

function defaultDesktopCapabilities(
  source: BackendEnvelopeFor<"assistant_turn">,
  mediaSession: BackendEnvelopeFor<"media_session">,
): BackendEnvelopeFor<"desktop_capabilities"> {
  return {
    ...envelopeBase("desktop_capabilities", source),
    payload: {
      schema: "desktop_live_capture.v1",
      thread_id: source.thread_id,
      desktop_target: "windows_private_alpha",
      capture_policy: {
        microphone: "explicit_user_toggle",
        camera: "explicit_user_toggle",
        screen: "not_enabled",
        background_capture: "blocked",
      },
      providers: {
        asr: {
          provider: "dashscope_priority",
          status: "mock_provider_not_bound",
          api_key_set: false,
        },
        tts: {
          provider: "dashscope_realtime",
          status: "mock_not_configured",
          api_key_set: false,
        },
        vision: {
          provider: "explicit_provider_required",
          status: "readback_only_no_auto_model_call",
        },
      },
      device_enumeration: {
        owner: "electron_renderer",
        system_grant_source: "desktop_os_prompt",
      },
      permissions: {
        schema: "desktop_permission_state.v1",
        permissions: defaultDesktopPermissions(),
        authority_boundary: desktopAuthorityBoundary(false),
      },
      media_session: mediaSession.payload,
      authority_boundary: desktopAuthorityBoundary(false),
      routes: {
        read: ["/api/desktop/capabilities", "/api/media/session/current"],
        control: [
          "/api/desktop/permissions/request",
          "/api/media/session/start",
          "/api/media/session/stop",
          "/api/media/audio/input",
          "/api/media/video/frame",
          "/api/media/tts/synthesize",
          "/api/artifacts/submit",
        ],
      },
    },
  };
}

function defaultCheckpointHistory(
  source: BackendEnvelopeFor<"assistant_turn">,
): BackendEnvelopeFor<"checkpoint_history"> {
  return {
    ...envelopeBase("checkpoint_history", source),
    payload: {
      thread_id: source.thread_id,
      limit: 10,
      total: 0,
      rows: [],
    },
  };
}

export function transcriptEntryFromEnvelope(envelope: TranscriptEnvelope): TranscriptEntry {
  return {
    id: `${envelope.kind}-${envelope.generated_at}-${Math.random().toString(36).slice(2, 8)}`,
    envelope,
  };
}

export function appendAssistantTurnToSession(
  session: RuntimeSession,
  assistantTurnEnvelope: BackendEnvelopeFor<"assistant_turn">,
  entry: TranscriptEntry = transcriptEntryFromEnvelope(assistantTurnEnvelope),
): RuntimeSession {
  const transcript = sortTranscriptDescending([...session.transcript, entry]);
  const sourcesView = defaultSourcesView(assistantTurnEnvelope);
  const appraisal = defaultAppraisal(assistantTurnEnvelope);
  return {
    ...session,
    threadId: assistantTurnEnvelope.thread_id,
    schemaVersion: assistantTurnEnvelope.schema_version,
    transportMode: "route",
    transcript,
    sourcesView,
    appraisal,
    sources: sourcesView.payload.sources ?? session.sources,
    claimLinks: sourcesView.payload.claim_links ?? session.claimLinks,
  };
}

export function upsertAssistantTurnInSession(
  session: RuntimeSession,
  assistantTurnEnvelope: BackendEnvelopeFor<"assistant_turn">,
  entry: TranscriptEntry = transcriptEntryFromEnvelope(assistantTurnEnvelope),
): RuntimeSession {
  const latestIndex = session.transcript.findIndex((entry) => entry.envelope.kind === "assistant_turn");
  const existingIndex = session.transcript.findIndex(
    (entry) =>
      entry.envelope.kind === "assistant_turn" &&
      entry.envelope.generated_at === assistantTurnEnvelope.generated_at &&
      entry.envelope.thread_id === assistantTurnEnvelope.thread_id,
  );

  const transcript = [...session.transcript];
  if (existingIndex >= 0) {
    transcript[existingIndex] = entry;
  } else if (latestIndex >= 0 && assistantTurnEnvelope.generated_at <= transcript[latestIndex].envelope.generated_at) {
    transcript[latestIndex] = entry;
  } else {
    transcript.push(entry);
  }

  const sourcesView = defaultSourcesView(assistantTurnEnvelope);
  const appraisal = defaultAppraisal(assistantTurnEnvelope);

  return {
    ...session,
    threadId: assistantTurnEnvelope.thread_id,
    schemaVersion: assistantTurnEnvelope.schema_version,
    transportMode: session.transportMode,
    transcript: sortTranscriptDescending(transcript),
    sourcesView,
    appraisal,
    sources: sourcesView.payload.sources ?? session.sources,
    claimLinks: sourcesView.payload.claim_links ?? session.claimLinks,
  };
}

export function createSessionSnapshotFromEnvelopes(
  envelopes: SessionEnvelopeSet,
  transportMode: TransportMode,
): RuntimeSession {
  const transcript = buildTranscript(envelopes.assistantTurn, envelopes.eventRound);
  const threadInventory = envelopes.threadInventory ?? defaultThreadInventory(envelopes.assistantTurn);
  const runtimeLayout = envelopes.runtimeLayout ?? defaultRuntimeLayout(envelopes.assistantTurn);
  const environmentSummary = envelopes.environmentSummary ?? defaultEnvironmentSummary(envelopes.assistantTurn);
  const sourcesView = envelopes.sourcesView ?? defaultSourcesView(envelopes.assistantTurn);
  const appraisal = envelopes.appraisal ?? defaultAppraisal(envelopes.assistantTurn);
  const behaviorQueue = envelopes.behaviorQueue ?? defaultBehaviorQueue(envelopes.assistantTurn, envelopes.persona);
  const runtimeProductization = envelopes.runtimeProductization ?? defaultRuntimeProductization(envelopes.assistantTurn);
  const operatorConsoleRc = envelopes.operatorConsoleRc ?? defaultOperatorConsoleRc(envelopes.assistantTurn);
  const currentCheckpoint = envelopes.currentCheckpoint ?? defaultCurrentCheckpoint(envelopes.assistantTurn);
  const mediaSession = envelopes.mediaSession ?? defaultMediaSession(envelopes.assistantTurn);
  const desktopCapabilities = envelopes.desktopCapabilities ?? defaultDesktopCapabilities(envelopes.assistantTurn, mediaSession);
  const checkpointHistory = envelopes.checkpointHistory ?? defaultCheckpointHistory(envelopes.assistantTurn);
  const sources = sourcesView.payload.sources ?? envelopes.assistantTurn.payload.sources;
  const claimLinks = sourcesView.payload.claim_links ?? envelopes.assistantTurn.payload.claim_links;

  return {
    threadId: envelopes.assistantTurn.thread_id,
    schemaVersion: envelopes.assistantTurn.schema_version,
    transportMode,
    transcript,
    threadInventory,
    runtimeLayout,
    environmentSummary,
    persona: envelopes.persona,
    worldline: envelopes.worldline,
    bond: envelopes.bond,
    sourcesView,
    appraisal,
    behaviorQueue,
    runtimeProductization,
    operatorConsoleRc,
    desktopCapabilities,
    mediaSession,
    currentCheckpoint,
    checkpointHistory,
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
