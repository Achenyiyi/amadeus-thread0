import type { BackendEnvelopeFor, BackendKind } from "../contracts/backend";
import {
  createSessionSnapshotFromEnvelopes,
  loadMockSession,
  type RuntimeSession,
  type TranscriptEnvelope,
} from "../data/mockBackend";

export interface BackendClient {
  loadSessionSnapshot(): Promise<RuntimeSession>;
  loadCurrentTurn(): Promise<BackendEnvelopeFor<"assistant_turn">>;
  loadThreadInventory(): Promise<BackendEnvelopeFor<"thread_inventory">>;
  loadRuntimeLayout(): Promise<BackendEnvelopeFor<"runtime_layout">>;
  loadEnvironmentSummary(): Promise<BackendEnvelopeFor<"environment_summary">>;
  loadRuntimeProductization(): Promise<BackendEnvelopeFor<"runtime_productization">>;
  loadOperatorConsoleRc(): Promise<BackendEnvelopeFor<"operator_console_rc">>;
  loadPersona(): Promise<BackendEnvelopeFor<"persona_view">>;
  loadWorldline(): Promise<BackendEnvelopeFor<"worldline_view">>;
  loadBond(): Promise<BackendEnvelopeFor<"bond_view">>;
  loadSources(): Promise<BackendEnvelopeFor<"sources_view">>;
  loadAppraisal(): Promise<BackendEnvelopeFor<"appraisal_view">>;
  loadBehaviorQueue(): Promise<BackendEnvelopeFor<"behavior_queue_view">>;
  loadCurrentCheckpoint(): Promise<BackendEnvelopeFor<"current_checkpoint">>;
  loadCheckpointHistory(limit?: number): Promise<BackendEnvelopeFor<"checkpoint_history">>;
  sendMessage(message: string): Promise<BackendEnvelopeFor<"assistant_turn">>;
  loadDesktopCapabilities(): Promise<BackendEnvelopeFor<"desktop_capabilities">>;
  requestDesktopPermissions(body: DesktopPermissionRequest): Promise<BackendEnvelopeFor<"desktop_permission_state">>;
  loadCurrentMediaSession(): Promise<BackendEnvelopeFor<"media_session">>;
  startMediaSession(body: MediaSessionStartRequest): Promise<BackendEnvelopeFor<"media_session">>;
  stopMediaSession(body?: MediaSessionStopRequest): Promise<BackendEnvelopeFor<"media_session">>;
  submitMediaAudio(body: MediaAudioInputRequest): Promise<BackendEnvelopeFor<"media_turn">>;
  submitMediaVideoFrame(body: MediaVideoFrameRequest): Promise<BackendEnvelopeFor<"media_turn">>;
  synthesizeMediaTts(body: MediaTtsRequest): Promise<BackendEnvelopeFor<"media_tts">>;
  submitArtifact(body: ArtifactSubmitRequest): Promise<BackendEnvelopeFor<"artifact_submission">>;
  finalizeTurn(body: TurnFinalizeRequest): Promise<BackendEnvelopeFor<"assistant_turn">>;
  finalizeEventRound(body: EventRoundFinalizeRequest): Promise<BackendEnvelopeFor<"event_round">>;
}

export type BackendRoute =
  | "/api/thread-inventory"
  | "/api/runtime-layout"
  | "/api/environment-summary"
  | "/api/turns/current"
  | "/api/chat/send"
  | "/api/runtime-productization"
  | "/api/operator-console-rc"
  | "/api/persona-view"
  | "/api/worldline-view"
  | "/api/bond-view"
  | "/api/sources-view"
  | "/api/appraisal-view"
  | "/api/behavior-queue"
  | "/api/checkpoints/current"
  | "/api/checkpoints/history"
  | "/api/desktop/capabilities"
  | "/api/desktop/permissions/request"
  | "/api/media/session/current"
  | "/api/media/session/start"
  | "/api/media/session/stop"
  | "/api/media/audio/input"
  | "/api/media/video/frame"
  | "/api/media/tts/synthesize"
  | "/api/artifacts/submit"
  | "/api/turns/finalize"
  | "/api/event-rounds/finalize";

export interface BackendRouteRequestInit {
  method?: "GET" | "POST";
  body?: unknown;
  queryString?: string;
}

export interface BackendRouteTransport {
  request(route: BackendRoute, init?: BackendRouteRequestInit): Promise<{ status: number; body: unknown }>;
}

export interface BackendClientOptions {
  transport?: BackendRouteTransport;
  seedTranscript?: TranscriptEnvelope[];
}

export interface TurnFinalizeRequest {
  state_values?: Record<string, unknown>;
  streamed_text?: string;
  meta?: Record<string, unknown>;
}

export interface EventRoundFinalizeRequest {
  state_values?: Record<string, unknown>;
  final_text?: string;
  meta?: Record<string, unknown>;
}

export interface DesktopPermissionRequest {
  permissions: string[];
  source?: string;
}

export interface MediaSessionStartRequest {
  consent: boolean;
  requested_permissions?: string[];
  mode?: string;
  mic_muted?: boolean;
}

export interface MediaSessionStopRequest {
  reason?: string;
}

export interface MediaAudioInputRequest {
  consent: boolean;
  transcript?: string;
  duration_ms?: number;
  audio_digest?: string;
  audio_base64?: string;
  audio_format?: string;
  sample_rate_hz?: number;
  mime_type?: string;
  source?: string;
}

export interface MediaVideoFrameRequest {
  consent: boolean;
  frame_digest: string;
  width?: number;
  height?: number;
  captured_at?: number;
  caption?: string;
}

export interface MediaTtsRequest {
  text: string;
  emotion_label?: string;
}

export interface ArtifactSubmitRequest {
  consent: boolean;
  modality: string;
  content_digest: string;
  label?: string;
  filename?: string;
  mime_type?: string;
  size_bytes?: number;
  capture_method?: string;
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

function isEventRound(envelope: TranscriptEnvelope): envelope is BackendEnvelopeFor<"event_round"> {
  return envelope.kind === "event_round";
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function nowSeconds(): number {
  return Math.floor(Date.now() / 1000);
}

function createMockEnvelope<K extends BackendKind>(
  kind: K,
  threadId: string,
  payload: BackendEnvelopeFor<K>["payload"],
): BackendEnvelopeFor<K> {
  return {
    schema_version: "backend.v1",
    generated_at: nowSeconds(),
    kind,
    thread_id: threadId,
    payload,
    meta: {
      source: "frontend_mock_desktop_media",
    },
  } as BackendEnvelopeFor<K>;
}

function mockAuthorityBoundary(active = false) {
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

function mockPermissions(status = "not_requested") {
  return {
    microphone: { status, system_grant: "unknown", requested_at: status === "not_requested" ? 0 : nowSeconds() },
    camera: { status, system_grant: "unknown", requested_at: status === "not_requested" ? 0 : nowSeconds() },
    artifact: { status, system_grant: "unknown", requested_at: status === "not_requested" ? 0 : nowSeconds() },
  };
}

class MockBackendClient implements BackendClient {
  private mediaSession: BackendEnvelopeFor<"media_session">["payload"] = {
    schema: "media_session.v1",
    status: "stopped",
    active: false,
    session_id: "",
    permissions: mockPermissions(),
    latest_media_turn: {},
    latest_artifact: {},
    authority_boundary: mockAuthorityBoundary(false),
  };

  async loadSessionSnapshot(): Promise<RuntimeSession> {
    return loadMockSession();
  }

  async loadCurrentTurn(): Promise<BackendEnvelopeFor<"assistant_turn">> {
    const snapshot = await loadMockSession();
    const current = snapshot.transcript.find((entry) => entry.envelope.kind === "assistant_turn");
    if (!current) {
      throw new Error("Mock session does not include an assistant_turn envelope.");
    }
    return current.envelope as BackendEnvelopeFor<"assistant_turn">;
  }

  async loadThreadInventory(): Promise<BackendEnvelopeFor<"thread_inventory">> {
    return (await loadMockSession()).threadInventory as BackendEnvelopeFor<"thread_inventory">;
  }

  async loadRuntimeLayout(): Promise<BackendEnvelopeFor<"runtime_layout">> {
    return (await loadMockSession()).runtimeLayout as BackendEnvelopeFor<"runtime_layout">;
  }

  async loadEnvironmentSummary(): Promise<BackendEnvelopeFor<"environment_summary">> {
    return (await loadMockSession()).environmentSummary as BackendEnvelopeFor<"environment_summary">;
  }

  async loadRuntimeProductization(): Promise<BackendEnvelopeFor<"runtime_productization">> {
    return (await loadMockSession()).runtimeProductization as BackendEnvelopeFor<"runtime_productization">;
  }

  async loadOperatorConsoleRc(): Promise<BackendEnvelopeFor<"operator_console_rc">> {
    return (await loadMockSession()).operatorConsoleRc as BackendEnvelopeFor<"operator_console_rc">;
  }

  async loadPersona(): Promise<BackendEnvelopeFor<"persona_view">> {
    return (await loadMockSession()).persona;
  }

  async loadWorldline(): Promise<BackendEnvelopeFor<"worldline_view">> {
    return (await loadMockSession()).worldline;
  }

  async loadBond(): Promise<BackendEnvelopeFor<"bond_view">> {
    return (await loadMockSession()).bond;
  }

  async loadSources(): Promise<BackendEnvelopeFor<"sources_view">> {
    return (await loadMockSession()).sourcesView as BackendEnvelopeFor<"sources_view">;
  }

  async loadAppraisal(): Promise<BackendEnvelopeFor<"appraisal_view">> {
    return (await loadMockSession()).appraisal as BackendEnvelopeFor<"appraisal_view">;
  }

  async loadBehaviorQueue(): Promise<BackendEnvelopeFor<"behavior_queue_view">> {
    return (await loadMockSession()).behaviorQueue as BackendEnvelopeFor<"behavior_queue_view">;
  }

  async loadCurrentCheckpoint(): Promise<BackendEnvelopeFor<"current_checkpoint">> {
    return (await loadMockSession()).currentCheckpoint as BackendEnvelopeFor<"current_checkpoint">;
  }

  async loadCheckpointHistory(): Promise<BackendEnvelopeFor<"checkpoint_history">> {
    return (await loadMockSession()).checkpointHistory as BackendEnvelopeFor<"checkpoint_history">;
  }

  async sendMessage(): Promise<never> {
    throw new Error("Chat send requires a live backend route. Start the backend server instead of VITE_AMADEUS_USE_MOCK.");
  }

  async loadDesktopCapabilities(): Promise<BackendEnvelopeFor<"desktop_capabilities">> {
    const snapshot = await loadMockSession();
    return createMockEnvelope("desktop_capabilities", snapshot.threadId, {
      schema: "desktop_live_capture.v1",
      thread_id: snapshot.threadId,
      desktop_target: "windows_private_alpha",
      capture_policy: {
        microphone: "explicit_user_toggle",
        camera: "explicit_user_toggle",
        background_capture: "blocked",
      },
      providers: {
        asr: { provider: "dashscope_priority", status: "mock_provider_not_bound", api_key_set: false },
        tts: { provider: "dashscope_realtime", status: "mock_not_configured", api_key_set: false },
        vision: { provider: "explicit_provider_required", status: "readback_only_no_auto_model_call" },
      },
      device_enumeration: {
        owner: "electron_renderer",
        system_grant_source: "desktop_os_prompt",
      },
      permissions: {
        schema: "desktop_permission_state.v1",
        permissions: mockPermissions(),
        authority_boundary: mockAuthorityBoundary(false),
      },
      media_session: this.mediaSession,
      authority_boundary: mockAuthorityBoundary(false),
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
    });
  }

  async requestDesktopPermissions(body: DesktopPermissionRequest): Promise<BackendEnvelopeFor<"desktop_permission_state">> {
    const snapshot = await loadMockSession();
    const requested = (body.permissions ?? []).filter(Boolean);
    return createMockEnvelope("desktop_permission_state", snapshot.threadId, {
      schema: "desktop_permission_state.v1",
      permissions: mockPermissions("requested"),
      requested,
      rejected: [],
      status: requested.length ? "requested" : "blocked",
      failure_reasons: requested.length ? [] : ["no_supported_permissions_requested"],
      authority_boundary: mockAuthorityBoundary(false),
    });
  }

  async loadCurrentMediaSession(): Promise<BackendEnvelopeFor<"media_session">> {
    const snapshot = await loadMockSession();
    return createMockEnvelope("media_session", snapshot.threadId, this.mediaSession);
  }

  async startMediaSession(body: MediaSessionStartRequest): Promise<BackendEnvelopeFor<"media_session">> {
    const snapshot = await loadMockSession();
    if (!body.consent) {
      this.mediaSession = {
        schema: "media_session.v1",
        status: "blocked",
        active: false,
        session_id: "",
        failure_reasons: ["explicit_user_consent_required"],
        authority_boundary: mockAuthorityBoundary(false),
      };
    } else {
      const requested = body.requested_permissions ?? ["microphone", "camera"];
      this.mediaSession = {
        schema: "media_session.v1",
        status: "active",
        active: true,
        session_id: `mock-media-${nowSeconds()}`,
        mode: body.mode ?? "human_ai_av_call",
        started_at: nowSeconds(),
        stopped_at: 0,
        requested_permissions: requested,
        capture_policy: "explicit_desktop_user_consent_only",
        audio: {
          enabled: requested.includes("microphone"),
          muted: Boolean(body.mic_muted),
          provider: "dashscope_priority",
          asr_status: "mock_provider_not_bound",
        },
        video: {
          enabled: requested.includes("camera"),
          frame_rate_policy: "low_frequency_or_user_snapshot",
          vision_status: "readback_only_no_auto_model_call",
        },
        permissions: mockPermissions("requested"),
        latest_media_turn: {},
        latest_artifact: {},
        authority_boundary: mockAuthorityBoundary(true),
      };
    }
    return createMockEnvelope("media_session", snapshot.threadId, this.mediaSession);
  }

  async stopMediaSession(body: MediaSessionStopRequest = {}): Promise<BackendEnvelopeFor<"media_session">> {
    const snapshot = await loadMockSession();
    this.mediaSession = {
      ...this.mediaSession,
      status: "stopped",
      active: false,
      stopped_at: nowSeconds(),
      stop_reason: body.reason ?? "user_stopped",
      authority_boundary: mockAuthorityBoundary(false),
    };
    return createMockEnvelope("media_session", snapshot.threadId, this.mediaSession);
  }

  async submitMediaAudio(body: MediaAudioInputRequest): Promise<BackendEnvelopeFor<"media_turn">> {
    const snapshot = await loadMockSession();
    const payload: BackendEnvelopeFor<"media_turn">["payload"] = {
      schema: "media_turn.v1",
      status: this.mediaSession.active && body.consent && body.transcript ? "transcript_ready" : "blocked",
      modality: "audio",
      media_session_id: String(this.mediaSession.session_id ?? ""),
      audio: {
        duration_ms: body.duration_ms ?? 0,
        audio_digest: body.audio_digest ?? "",
        mime_type: body.mime_type ?? "audio/webm",
      },
      asr: {
        provider: "dashscope_priority",
        status: body.transcript ? "provided_transcript" : "asr_provider_not_connected",
        transcript: body.transcript ?? "",
      },
      chat_dispatch: {
        allowed: Boolean(body.transcript),
        route_equivalent: "/api/chat/send",
      },
      failure_reasons: body.transcript ? [] : ["asr_provider_not_connected"],
      authority_boundary: mockAuthorityBoundary(Boolean(this.mediaSession.active)),
    };
    this.mediaSession = { ...this.mediaSession, latest_media_turn: payload };
    return createMockEnvelope("media_turn", snapshot.threadId, payload);
  }

  async submitMediaVideoFrame(body: MediaVideoFrameRequest): Promise<BackendEnvelopeFor<"media_turn">> {
    const snapshot = await loadMockSession();
    const active = Boolean(this.mediaSession.active);
    const payload: BackendEnvelopeFor<"media_turn">["payload"] = {
      schema: "media_turn.v1",
      status: active && body.consent ? "accepted_readback_only" : "blocked",
      modality: "video",
      media_session_id: String(this.mediaSession.session_id ?? ""),
      frame: {
        frame_digest: body.frame_digest,
        width: body.width ?? 0,
        height: body.height ?? 0,
        captured_at: body.captured_at ?? nowSeconds(),
        caption: body.caption ?? "",
      },
      vision: {
        provider: "explicit_provider_required",
        model_api_called: false,
        status: active && body.consent ? "metadata_accepted_no_auto_model_call" : "blocked",
      },
      perception_readback: {
        source: "desktop_camera_user_consented",
        writeback_ready: false,
      },
      failure_reasons: active && body.consent ? [] : ["active_media_session_required"],
      authority_boundary: mockAuthorityBoundary(active),
    };
    this.mediaSession = { ...this.mediaSession, latest_media_turn: payload };
    return createMockEnvelope("media_turn", snapshot.threadId, payload);
  }

  async synthesizeMediaTts(body: MediaTtsRequest): Promise<BackendEnvelopeFor<"media_tts">> {
    const snapshot = await loadMockSession();
    return createMockEnvelope("media_tts", snapshot.threadId, {
      schema: "media_tts.v1",
      status: "blocked",
      provider: "dashscope_realtime",
      emotion_label: body.emotion_label ?? "neutral",
      text: body.text,
      render_plan: {
        final_text: body.text,
        segment_count: body.text ? 1 : 0,
      },
      audio: {
        mime_type: "audio/wav",
        sample_rate_hz: 24000,
        url: "",
        path: "",
        duration_ms: 0,
        bytes: 0,
      },
      failure_reasons: ["mock_tts_provider_not_bound"],
      authority_boundary: mockAuthorityBoundary(Boolean(this.mediaSession.active)),
    });
  }

  async submitArtifact(body: ArtifactSubmitRequest): Promise<BackendEnvelopeFor<"artifact_submission">> {
    const snapshot = await loadMockSession();
    const accepted = Boolean(body.consent && body.content_digest && body.modality);
    const payload: BackendEnvelopeFor<"artifact_submission">["payload"] = {
      schema: "artifact_submission.v1",
      status: accepted ? "accepted" : "blocked",
      artifact: {
        artifact_id: `mock-artifact-${String(body.content_digest || Date.now()).slice(0, 12)}`,
        label: body.label ?? body.filename ?? "artifact",
        modality: body.modality,
        content_digest: body.content_digest,
        mime_type: body.mime_type ?? "",
        size_bytes: body.size_bytes ?? 0,
        capture_method: body.capture_method ?? "user_selected_file",
      },
      source_ref: {
        id: `mock-artifact-${String(body.content_digest || Date.now()).slice(0, 12)}`,
        tool_name: "desktop_artifact_submit",
        title: body.label ?? body.filename ?? "artifact",
        query: body.modality,
      },
      inspection: {
        status: "available_for_explicit_inspection",
        auto_execute: false,
        model_api_call_planned: false,
        live_capture_used: body.capture_method === "camera_snapshot",
      },
      failure_reasons: accepted ? [] : ["explicit_user_consent_required_or_missing_digest"],
      authority_boundary: mockAuthorityBoundary(Boolean(this.mediaSession.active)),
    };
    this.mediaSession = { ...this.mediaSession, latest_artifact: payload };
    return createMockEnvelope("artifact_submission", snapshot.threadId, payload);
  }

  async finalizeTurn(): Promise<never> {
    throw new Error("Finalize routes require a live backend route.");
  }

  async finalizeEventRound(): Promise<never> {
    throw new Error("Finalize routes require a live backend route.");
  }
}

class FetchRouteTransport implements BackendRouteTransport {
  private readonly apiBase: string;

  constructor(apiBase: string = "") {
    this.apiBase = apiBase.replace(/\/$/, "");
  }

  async request(route: BackendRoute, init: BackendRouteRequestInit = {}): Promise<{ status: number; body: unknown }> {
    const method = init.method ?? "GET";
    const headers: Record<string, string> = {
      Accept: "application/json",
    };
    const hasBody = init.body !== undefined;
    if (hasBody) {
      headers["Content-Type"] = "application/json";
    }

    const query = init.queryString ? `?${init.queryString.replace(/^\?/, "")}` : "";
    const response = await fetch(`${this.apiBase}${route}${query}`, {
      method,
      headers,
      body: hasBody ? JSON.stringify(init.body) : undefined,
    });

    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = {
        error: {
          code: "NON_JSON_RESPONSE",
          path: route,
          status: response.status,
        },
      };
    }

    return { status: response.status, body };
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

  private async requestEnvelopeWithRetry<K extends BackendKind>(
    route: BackendRoute,
    kind: K,
    init?: BackendRouteRequestInit,
  ): Promise<BackendEnvelopeFor<K>> {
    let lastError: unknown;
    for (let attempt = 0; attempt < 3; attempt += 1) {
      try {
        if (init) {
          const response = await this.transport.request(route, init);
          if (response.status !== 200) {
            throw new Error(`Backend route ${route} returned status ${response.status}`);
          }
          return validateEnvelope(response.body, kind);
        }
        return await this.fetchEnvelope(route, kind);
      } catch (error: unknown) {
        lastError = error;
        if (attempt < 2) {
          await sleep(220 + attempt * 420);
        }
      }
    }
    throw lastError instanceof Error ? lastError : new Error(String(lastError));
  }

  async sendMessage(message: string): Promise<BackendEnvelopeFor<"assistant_turn">> {
    const trimmed = message.trim();
    if (!trimmed) {
      throw new Error("Message is empty");
    }
    const response = await this.transport.request("/api/chat/send", {
      method: "POST",
      body: {
        message: trimmed,
        meta: {
          client: "frontend_runtime_shell",
        },
      },
    });
    if (response.status !== 200) {
      const details = isRecord(response.body) && isRecord(response.body.error)
        ? String(response.body.error.code ?? response.status)
        : String(response.status);
      throw new Error(`Backend chat route returned ${details}`);
    }
    return validateEnvelope(response.body, "assistant_turn");
  }

  async loadDesktopCapabilities(): Promise<BackendEnvelopeFor<"desktop_capabilities">> {
    return this.requestEnvelopeWithRetry("/api/desktop/capabilities", "desktop_capabilities");
  }

  async requestDesktopPermissions(body: DesktopPermissionRequest): Promise<BackendEnvelopeFor<"desktop_permission_state">> {
    return this.requestEnvelopeWithRetry("/api/desktop/permissions/request", "desktop_permission_state", {
      method: "POST",
      body,
    });
  }

  async loadCurrentMediaSession(): Promise<BackendEnvelopeFor<"media_session">> {
    return this.requestEnvelopeWithRetry("/api/media/session/current", "media_session");
  }

  async startMediaSession(body: MediaSessionStartRequest): Promise<BackendEnvelopeFor<"media_session">> {
    return this.requestEnvelopeWithRetry("/api/media/session/start", "media_session", {
      method: "POST",
      body,
    });
  }

  async stopMediaSession(body: MediaSessionStopRequest = {}): Promise<BackendEnvelopeFor<"media_session">> {
    return this.requestEnvelopeWithRetry("/api/media/session/stop", "media_session", {
      method: "POST",
      body,
    });
  }

  async submitMediaAudio(body: MediaAudioInputRequest): Promise<BackendEnvelopeFor<"media_turn">> {
    return this.requestEnvelopeWithRetry("/api/media/audio/input", "media_turn", {
      method: "POST",
      body,
    });
  }

  async submitMediaVideoFrame(body: MediaVideoFrameRequest): Promise<BackendEnvelopeFor<"media_turn">> {
    return this.requestEnvelopeWithRetry("/api/media/video/frame", "media_turn", {
      method: "POST",
      body,
    });
  }

  async synthesizeMediaTts(body: MediaTtsRequest): Promise<BackendEnvelopeFor<"media_tts">> {
    return this.requestEnvelopeWithRetry("/api/media/tts/synthesize", "media_tts", {
      method: "POST",
      body,
    });
  }

  async submitArtifact(body: ArtifactSubmitRequest): Promise<BackendEnvelopeFor<"artifact_submission">> {
    return this.requestEnvelopeWithRetry("/api/artifacts/submit", "artifact_submission", {
      method: "POST",
      body,
    });
  }

  async loadCurrentTurn(): Promise<BackendEnvelopeFor<"assistant_turn">> {
    return this.requestEnvelopeWithRetry("/api/turns/current", "assistant_turn");
  }

  async loadThreadInventory(): Promise<BackendEnvelopeFor<"thread_inventory">> {
    return this.requestEnvelopeWithRetry("/api/thread-inventory", "thread_inventory");
  }

  async loadRuntimeLayout(): Promise<BackendEnvelopeFor<"runtime_layout">> {
    return this.requestEnvelopeWithRetry("/api/runtime-layout", "runtime_layout");
  }

  async loadEnvironmentSummary(): Promise<BackendEnvelopeFor<"environment_summary">> {
    return this.requestEnvelopeWithRetry("/api/environment-summary", "environment_summary");
  }

  async loadRuntimeProductization(): Promise<BackendEnvelopeFor<"runtime_productization">> {
    return this.requestEnvelopeWithRetry("/api/runtime-productization", "runtime_productization");
  }

  async loadOperatorConsoleRc(): Promise<BackendEnvelopeFor<"operator_console_rc">> {
    return this.requestEnvelopeWithRetry("/api/operator-console-rc", "operator_console_rc");
  }

  async loadPersona(): Promise<BackendEnvelopeFor<"persona_view">> {
    return this.requestEnvelopeWithRetry("/api/persona-view", "persona_view");
  }

  async loadWorldline(): Promise<BackendEnvelopeFor<"worldline_view">> {
    return this.requestEnvelopeWithRetry("/api/worldline-view", "worldline_view");
  }

  async loadBond(): Promise<BackendEnvelopeFor<"bond_view">> {
    return this.requestEnvelopeWithRetry("/api/bond-view", "bond_view");
  }

  async loadSources(): Promise<BackendEnvelopeFor<"sources_view">> {
    return this.requestEnvelopeWithRetry("/api/sources-view", "sources_view");
  }

  async loadAppraisal(): Promise<BackendEnvelopeFor<"appraisal_view">> {
    return this.requestEnvelopeWithRetry("/api/appraisal-view", "appraisal_view");
  }

  async loadBehaviorQueue(): Promise<BackendEnvelopeFor<"behavior_queue_view">> {
    return this.requestEnvelopeWithRetry("/api/behavior-queue", "behavior_queue_view");
  }

  async loadCurrentCheckpoint(): Promise<BackendEnvelopeFor<"current_checkpoint">> {
    return this.requestEnvelopeWithRetry("/api/checkpoints/current", "current_checkpoint");
  }

  async loadCheckpointHistory(limit = 10): Promise<BackendEnvelopeFor<"checkpoint_history">> {
    const clamped = Math.max(1, Math.min(100, Math.round(Number(limit) || 10)));
    return this.requestEnvelopeWithRetry("/api/checkpoints/history", "checkpoint_history", {
      queryString: `limit=${encodeURIComponent(String(clamped))}`,
    });
  }

  async finalizeTurn(body: TurnFinalizeRequest): Promise<BackendEnvelopeFor<"assistant_turn">> {
    const response = await this.transport.request("/api/turns/finalize", {
      method: "POST",
      body,
    });
    if (response.status !== 200) {
      throw new Error(`Backend turn finalize route returned status ${response.status}`);
    }
    return validateEnvelope(response.body, "assistant_turn");
  }

  async finalizeEventRound(body: EventRoundFinalizeRequest): Promise<BackendEnvelopeFor<"event_round">> {
    const response = await this.transport.request("/api/event-rounds/finalize", {
      method: "POST",
      body,
    });
    if (response.status !== 200) {
      throw new Error(`Backend event finalize route returned status ${response.status}`);
    }
    return validateEnvelope(response.body, "event_round");
  }

  async loadSessionSnapshot(): Promise<RuntimeSession> {
    const assistantTurn = await this.loadCurrentTurn();
    const persona = await this.loadPersona();
    const worldline = await this.loadWorldline();
    const bond = await this.loadBond();
    const sourcesView = await this.loadSources();
    const behaviorQueue = await this.loadBehaviorQueue();

    const seededEventRound = this.seedTranscript?.find(isEventRound);

    return createSessionSnapshotFromEnvelopes(
      {
        assistantTurn,
        eventRound: seededEventRound,
        persona,
        worldline,
        bond,
        sourcesView,
        behaviorQueue,
      },
      "route",
    );
  }
}

export function createBackendClient(options: BackendClientOptions = {}): BackendClient {
  if (options.transport) {
    return new RouteBackendClient(options.transport, options.seedTranscript);
  }

  const forceMock = String(import.meta.env.VITE_AMADEUS_USE_MOCK ?? "").toLowerCase() === "true";
  if (forceMock) {
    return new MockBackendClient();
  }

  const desktopBase = typeof window !== "undefined" ? String(window.amadeusDesktop?.backendBase ?? "") : "";
  const apiBase = String(import.meta.env.VITE_AMADEUS_API_BASE ?? desktopBase);
  return new RouteBackendClient(new FetchRouteTransport(apiBase), options.seedTranscript);
}
