import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode, type RefObject } from "react";
import { AvatarRenderer } from "./components/AvatarRenderer";
import type { BackendEnvelopeFor, JsonRecord, MediaSessionPayload, MediaTurnPayload, MediaTtsPayload } from "./contracts/backend";
import {
  appendAssistantTurnToSession,
  transcriptEntryFromEnvelope,
  upsertAssistantTurnInSession,
  type RuntimeSession,
  type TranscriptEntry,
} from "./data/mockBackend";
import {
  avatarExpressionOptions,
  companionPhaseCopy,
  companionPhaseOptions,
  createAvatarRuntimeState,
  defaultAvatarPlacement,
  live2dMotionOptions,
  type AvatarRuntimeOverride,
  type AvatarRuntimeState,
  type CompanionPhase,
} from "./runtime/avatarRuntime";
import { createBackendClient } from "./runtime/backendClient";
import {
  createCompanionProjection,
  currentPayload,
  ratioLabel,
  userLabel,
  type CompanionProjection,
  type CompanionSurface,
  type ProjectionCard,
} from "./runtime/projection";
import "./styles.css";

interface LocalUserMessage {
  id: string;
  text: string;
  createdAt: number;
  assistantEntryId: string;
}

type MediaStatus = "idle" | "requesting" | "listening" | "transcribing" | "thinking" | "speaking" | "muted" | "error";

interface MediaRuntimeState {
  callActive: boolean;
  micMuted: boolean;
  cameraEnabled: boolean;
  status: MediaStatus;
  error: string;
  devices: MediaDeviceInfo[];
  capabilities?: BackendEnvelopeFor<"desktop_capabilities">;
  session?: BackendEnvelopeFor<"media_session">;
  latestMediaTurn?: BackendEnvelopeFor<"media_turn">;
  latestTts?: BackendEnvelopeFor<"media_tts">;
  latestArtifact?: BackendEnvelopeFor<"artifact_submission">;
  lastFrameAt: number;
  lastArtifactLabel: string;
}

const initialMediaRuntime: MediaRuntimeState = {
  callActive: false,
  micMuted: false,
  cameraEnabled: false,
  status: "idle",
  error: "",
  devices: [],
  lastFrameAt: 0,
  lastArtifactLabel: "",
};

interface AvatarInspectorState {
  expression: CompanionProjection["avatarExpression"] | "";
  phase: CompanionPhase | "";
  motionTarget: string;
  scaleMultiplier: number;
  offsetX: number;
  offsetY: number;
  revision: number;
}

const initialAvatarInspectorState: AvatarInspectorState = {
  expression: "",
  phase: "",
  motionTarget: "",
  scaleMultiplier: defaultAvatarPlacement.scaleMultiplier,
  offsetX: defaultAvatarPlacement.offsetX,
  offsetY: defaultAvatarPlacement.offsetY,
  revision: 0,
};

const surfaces: Array<{
  id: CompanionSurface;
  label: string;
  hint: string;
  glyph: string;
}> = [
  { id: "room", label: "对话", hint: "继续这一刻", glyph: "01" },
  { id: "memory", label: "记忆", hint: "她记得的事", glyph: "02" },
  { id: "relationship", label: "关系", hint: "你们的轨迹", glyph: "03" },
  { id: "presence", label: "状态", hint: "她此刻的内在", glyph: "04" },
  { id: "growth", label: "成长", hint: "能力和经历", glyph: "05" },
  { id: "operator", label: "运维", hint: "隐藏控制台", glyph: "OP" },
];

const formatter = new Intl.DateTimeFormat(undefined, {
  hour: "2-digit",
  minute: "2-digit",
  month: "short",
  day: "2-digit",
});

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asRecord(value: unknown): JsonRecord {
  return isRecord(value) ? value : {};
}

function text(value: unknown, fallback = "n/a"): string {
  if (typeof value === "string" && value.trim()) return value;
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(2);
  if (typeof value === "boolean") return value ? "yes" : "no";
  return fallback;
}

function stamp(epochSeconds: number) {
  return formatter.format(new Date(epochSeconds * 1000));
}

function summarizeValue(value: unknown, fallback = "n/a") {
  if (Array.isArray(value)) return `${value.length} items`;
  if (isRecord(value)) return `${Object.keys(value).length} fields`;
  return text(value, fallback);
}

function mediaStatusLabel(status: MediaStatus): string {
  const labels: Record<MediaStatus, string> = {
    idle: "READY",
    requesting: "REQUESTING",
    listening: "LISTENING",
    transcribing: "TRANSCRIBING",
    thinking: "THINKING",
    speaking: "SPEAKING",
    muted: "MUTED",
    error: "ERROR",
  };
  return labels[status];
}

function failureText(value: unknown, fallback = ""): string {
  if (Array.isArray(value)) return value.map((item) => String(item)).filter(Boolean).join(" / ");
  if (typeof value === "string") return value;
  return fallback;
}

async function sha256Hex(buffer: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  return `sha256:${Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("")}`;
}

async function blobToBase64(blob: Blob): Promise<string> {
  const buffer = await blob.arrayBuffer();
  let binary = "";
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000;
  for (let index = 0; index < bytes.length; index += chunkSize) {
    binary += String.fromCharCode(...bytes.slice(index, index + chunkSize));
  }
  return window.btoa(binary);
}

async function decodeAudioBlob(blob: Blob): Promise<AudioBuffer> {
  const AudioContextCtor = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AudioContextCtor) throw new Error("AudioContext unavailable");
  const context = new AudioContextCtor();
  try {
    return await context.decodeAudioData(await blob.arrayBuffer());
  } finally {
    await context.close();
  }
}

function encodeWavFromAudioBuffer(audioBuffer: AudioBuffer, targetSampleRate = 16000): Blob {
  const source = audioBuffer.getChannelData(0);
  const ratio = audioBuffer.sampleRate / targetSampleRate;
  const length = Math.max(1, Math.floor(source.length / ratio));
  const pcm = new Int16Array(length);
  for (let index = 0; index < length; index += 1) {
    const sample = source[Math.min(source.length - 1, Math.floor(index * ratio))] || 0;
    pcm[index] = Math.max(-1, Math.min(1, sample)) * 0x7fff;
  }
  const buffer = new ArrayBuffer(44 + pcm.length * 2);
  const view = new DataView(buffer);
  function writeString(offset: number, value: string) {
    for (let index = 0; index < value.length; index += 1) view.setUint8(offset + index, value.charCodeAt(index));
  }
  writeString(0, "RIFF");
  view.setUint32(4, 36 + pcm.length * 2, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, targetSampleRate, true);
  view.setUint32(28, targetSampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(36, "data");
  view.setUint32(40, pcm.length * 2, true);
  let offset = 44;
  for (let index = 0; index < pcm.length; index += 1) {
    view.setInt16(offset, pcm[index], true);
    offset += 2;
  }
  return new Blob([buffer], { type: "audio/wav" });
}

async function normalizeAudioForAsr(blob: Blob): Promise<{ blob: Blob; sampleRate: number; format: string }> {
  try {
    const audioBuffer = await decodeAudioBlob(blob);
    return {
      blob: encodeWavFromAudioBuffer(audioBuffer, 16000),
      sampleRate: 16000,
      format: "wav",
    };
  } catch {
    return {
      blob,
      sampleRate: 0,
      format: blob.type.includes("wav") ? "wav" : "",
    };
  }
}

function createFriendlyError(message: string) {
  if (!message) return "";
  return "连接失败。请确认 Amadeus-K 后端服务已启动，或在本地设置 VITE_AMADEUS_USE_MOCK=true 进入预览。";
}

function PanelHeader({
  eyebrow,
  title,
  children,
  action,
}: {
  eyebrow: string;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <header className="panel-header">
      <div>
        <span>{eyebrow}</span>
        <h2>{title}</h2>
        {children ? <p>{children}</p> : null}
      </div>
      {action ? <div className="panel-header__action">{action}</div> : null}
    </header>
  );
}

function TerminalButton({
  children,
  onClick,
  disabled = false,
  variant = "ghost",
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: "ghost" | "primary" | "quiet";
  type?: "button" | "submit";
}) {
  return (
    <button type={type} className={`terminal-button terminal-button--${variant}`} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  );
}

function ProjectionCards({
  cards,
  empty,
}: {
  cards: ProjectionCard[];
  empty: string;
}) {
  if (!cards.length) return <p className="empty-copy">{empty}</p>;

  return (
    <div className="projection-list">
      {cards.map((card) => (
        <article key={card.id} className={`projection-card projection-card--${card.tone ?? "quiet"}`}>
          <span>{card.label}</span>
          <strong>{card.title}</strong>
          <p>{card.body}</p>
        </article>
      ))}
    </div>
  );
}

function JsonPeek({ value, label }: { value: unknown; label: string }) {
  return (
    <details className="json-peek">
      <summary>{label}</summary>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}

function TopHud({
  session,
  projection,
  companionPhase,
  isRefreshing,
  refreshError,
  onRefresh,
}: {
  session: RuntimeSession;
  projection: CompanionProjection;
  companionPhase: CompanionPhase;
  isRefreshing: boolean;
  refreshError: string;
  onRefresh: () => void;
}) {
  const mode = session.transportMode === "route" ? "LIVE BACKEND" : "OFFLINE PREVIEW";
  const phaseCopy = companionPhaseCopy[companionPhase];
  return (
    <header className="top-hud">
      <div className="brand-lockup">
        <div className="brand-mark" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <div>
          <strong>AMADEUS-K</strong>
          <span>ALEPH TERMINAL ROOM</span>
        </div>
      </div>
      <div className="top-hud__center">
        <span>{session.threadId}</span>
        <span>{phaseCopy.label}</span>
        <span>{projection.relationshipClimate}</span>
      </div>
      <div className="connection-cluster">
        <span className={session.transportMode === "route" ? "is-live" : "is-mock"}>{mode}</span>
        <TerminalButton onClick={onRefresh} disabled={isRefreshing}>
          {isRefreshing ? "SYNC" : "REFRESH"}
        </TerminalButton>
        {refreshError ? <small>{createFriendlyError(refreshError)}</small> : null}
      </div>
    </header>
  );
}

function SideRail({
  activeSurface,
  debugEnabled,
  onSelect,
}: {
  activeSurface: CompanionSurface;
  debugEnabled: boolean;
  onSelect: (surface: CompanionSurface) => void;
}) {
  const visibleSurfaces = debugEnabled ? surfaces : surfaces.filter((surface) => surface.id !== "operator");

  return (
    <nav className="side-rail" aria-label="Amadeus companion surfaces">
      {visibleSurfaces.map((item) => (
        <button
          key={item.id}
          type="button"
          className={item.id === activeSurface ? "is-active" : ""}
          onClick={() => onSelect(item.id)}
        >
          <span>{item.glyph}</span>
          <strong>{item.label}</strong>
          <small>{item.hint}</small>
        </button>
      ))}
    </nav>
  );
}

function MediaControls({
  media,
  onStartCall,
  onStopCall,
  onToggleMic,
  onToggleCamera,
  onCaptureVoice,
  onSubmitArtifact,
}: {
  media: MediaRuntimeState;
  onStartCall: () => void;
  onStopCall: () => void;
  onToggleMic: () => void;
  onToggleCamera: () => void;
  onCaptureVoice: () => void;
  onSubmitArtifact: (file: File) => void;
}) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  return (
    <div className="media-controls" aria-label="desktop media controls">
      <button type="button" className={media.callActive ? "is-live" : ""} onClick={media.callActive ? onStopCall : onStartCall}>
        <span>{media.callActive ? "结束" : "通话"}</span>
        <small>{media.callActive ? "LIVE" : "CALL"}</small>
      </button>
      <button type="button" className={media.micMuted ? "is-muted" : ""} onClick={onToggleMic} disabled={!media.callActive}>
        <span>{media.micMuted ? "静音" : "麦克"}</span>
        <small>{media.micMuted ? "MUTED" : "MIC"}</small>
      </button>
      <button type="button" onClick={onCaptureVoice} disabled={!media.callActive || media.micMuted || media.status === "transcribing"}>
        <span>语音</span>
        <small>{media.status === "transcribing" ? "ASR" : "PUSH"}</small>
      </button>
      <button type="button" className={media.cameraEnabled ? "is-live" : ""} onClick={onToggleCamera} disabled={!media.callActive}>
        <span>{media.cameraEnabled ? "画面" : "视频"}</span>
        <small>{media.cameraEnabled ? "CAM" : "OFF"}</small>
      </button>
      <button type="button" onClick={() => fileInputRef.current?.click()}>
        <span>图片</span>
        <small>FILE</small>
      </button>
      <input
        ref={fileInputRef}
        className="media-file-input"
        type="file"
        accept="image/*"
        onChange={(event) => {
          const file = event.currentTarget.files?.[0];
          event.currentTarget.value = "";
          if (file) onSubmitArtifact(file);
        }}
      />
    </div>
  );
}

function AvatarStage({
  projection,
  avatar,
}: {
  projection: CompanionProjection;
  avatar: AvatarRuntimeState;
}) {
  const phaseCopy = companionPhaseCopy[avatar.phase];
  return (
    <section
      className={`avatar-stage ${avatar.moodClass} ${avatar.expressionClass} ${avatar.phaseClass} posture-${avatar.posture} gaze-${avatar.gaze} motion-${avatar.motion}`}
      aria-label="Amadeus avatar stage"
      data-avatar-renderer={avatar.renderer}
      data-live2d-expression={avatar.dataBindings.live2dExpression}
      data-live2d-motion={avatar.dataBindings.live2dMotion}
      data-vrm-blend-shape={avatar.dataBindings.vrmBlendShape}
      data-sprite-sequence={avatar.dataBindings.spriteSequence}
    >
      <div className="room-backdrop" aria-hidden="true">
        <div className="room-backdrop__sun" />
        <div className="room-backdrop__window" />
        <div className="room-backdrop__city" />
        <div className="room-backdrop__floor" />
      </div>
      <div className="avatar-halo" aria-hidden="true" />
      <AvatarRenderer avatar={avatar} />
      <div className="scanline scanline-left" aria-hidden="true" />
      <div className="scanline scanline-right" aria-hidden="true" />
      <div className="stage-readout">
        <span>{phaseCopy.label}</span>
        <strong>{projection.emotionLabel}</strong>
        <p>{avatar.phase === "idle" ? projection.liveHint : phaseCopy.detail}</p>
      </div>
    </section>
  );
}

function AvatarInspector({
  avatar,
  state,
  onUpdate,
  onReset,
}: {
  avatar: AvatarRuntimeState;
  state: AvatarInspectorState;
  onUpdate: (patch: Partial<AvatarInspectorState>, replayMotion?: boolean) => void;
  onReset: () => void;
}) {
  const expressionLabel = avatar.manifest.expressions[avatar.dataBindings.live2dExpression] ?? "n/a";
  const mappedMotion = avatar.manifest.motions[avatar.dataBindings.live2dMotion] ?? "n/a";
  const motionLabel = avatar.dataBindings.live2dMotionTarget || mappedMotion;
  const hasOverride = Boolean(
    state.expression ||
      state.phase ||
      state.motionTarget ||
      state.scaleMultiplier !== defaultAvatarPlacement.scaleMultiplier ||
      state.offsetX !== defaultAvatarPlacement.offsetX ||
      state.offsetY !== defaultAvatarPlacement.offsetY,
  );

  return (
    <aside className="avatar-inspector" aria-label="Avatar runtime inspector">
      <header className="avatar-inspector__header">
        <div>
          <span>DEBUG ONLY</span>
          <strong>Avatar Runtime</strong>
        </div>
        <button type="button" onClick={onReset} disabled={!hasOverride}>
          RESET
        </button>
      </header>

      <div className="avatar-inspector__readout">
        <span>{avatar.manifest.label}</span>
        <small>EXPR {expressionLabel}</small>
        <small>MOTION {motionLabel}</small>
      </div>

      <section className="avatar-inspector__group">
        <span>Expression</span>
        <div className="avatar-inspector__buttons avatar-inspector__buttons--compact">
          <button type="button" className={!state.expression ? "is-active" : ""} onClick={() => onUpdate({ expression: "" })}>
            backend
          </button>
          {avatarExpressionOptions.map((option) => (
            <button
              key={option}
              type="button"
              className={state.expression === option ? "is-active" : ""}
              onClick={() => onUpdate({ expression: option })}
            >
              {option}
            </button>
          ))}
        </div>
      </section>

      <section className="avatar-inspector__group">
        <span>Phase</span>
        <div className="avatar-inspector__buttons">
          <button type="button" className={!state.phase ? "is-active" : ""} onClick={() => onUpdate({ phase: "" })}>
            backend
          </button>
          {companionPhaseOptions.map((option) => (
            <button
              key={option}
              type="button"
              className={state.phase === option ? "is-active" : ""}
              onClick={() => onUpdate({ phase: option }, true)}
            >
              {companionPhaseCopy[option].label}
            </button>
          ))}
        </div>
      </section>

      <section className="avatar-inspector__group">
        <label htmlFor="avatar-motion-select">Direct motion</label>
        <div className="avatar-inspector__motion-row">
          <select
            id="avatar-motion-select"
            value={state.motionTarget}
            onChange={(event) => onUpdate({ motionTarget: event.target.value }, true)}
          >
            <option value="">phase mapped</option>
            {live2dMotionOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
          <button type="button" onClick={() => onUpdate({}, true)}>
            PLAY
          </button>
        </div>
      </section>

      <section className="avatar-inspector__group">
        <div className="avatar-inspector__slider">
          <label htmlFor="avatar-scale">Scale</label>
          <output>{state.scaleMultiplier.toFixed(2)}</output>
          <input
            id="avatar-scale"
            type="range"
            min="0.74"
            max="1.46"
            step="0.01"
            value={state.scaleMultiplier}
            onChange={(event) => onUpdate({ scaleMultiplier: Number(event.target.value) })}
          />
        </div>
        <div className="avatar-inspector__slider">
          <label htmlFor="avatar-offset-x">Offset X</label>
          <output>{state.offsetX}px</output>
          <input
            id="avatar-offset-x"
            type="range"
            min="-220"
            max="220"
            step="1"
            value={state.offsetX}
            onChange={(event) => onUpdate({ offsetX: Number(event.target.value) })}
          />
        </div>
        <div className="avatar-inspector__slider">
          <label htmlFor="avatar-offset-y">Offset Y</label>
          <output>{state.offsetY}px</output>
          <input
            id="avatar-offset-y"
            type="range"
            min="-220"
            max="220"
            step="1"
            value={state.offsetY}
            onChange={(event) => onUpdate({ offsetY: Number(event.target.value) })}
          />
        </div>
      </section>
    </aside>
  );
}

function DialogueConsole({
  session,
  selectedEntry,
  projection,
  localUserMessages,
  draftMessage,
  sendError,
  isSending,
  companionPhase,
  media,
  videoRef,
  onDropArtifact,
  onDraftChange,
  onSubmit,
  onSelectTurn,
}: {
  session: RuntimeSession;
  selectedEntry: TranscriptEntry;
  projection: CompanionProjection;
  localUserMessages: LocalUserMessage[];
  draftMessage: string;
  sendError: string;
  isSending: boolean;
  companionPhase: CompanionPhase;
  media: MediaRuntimeState;
  videoRef: RefObject<HTMLVideoElement | null>;
  onDropArtifact: (file: File) => void;
  onDraftChange: (value: string) => void;
  onSubmit: () => void;
  onSelectTurn: (id: string) => void;
}) {
  const linkedUserMessage = localUserMessages.find((message) => message.assistantEntryId === selectedEntry.id);
  const canSend = session.transportMode === "route" && draftMessage.trim().length > 0 && !isSending;
  const phaseCopy = companionPhaseCopy[companionPhase];
  const showPhaseReadback = companionPhase !== "idle" || isSending;
  const showMemoryPulse = Boolean(projection.memoryPulse) && companionPhase !== "sending" && companionPhase !== "awaiting_response";

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit();
  }

  return (
    <section
      className={`dialogue-console media-${media.status}`}
      aria-label="Current dialogue"
      onDragOver={(event) => {
        event.preventDefault();
      }}
      onDrop={(event) => {
        event.preventDefault();
        const file = Array.from(event.dataTransfer.files).find((item) => item.type.startsWith("image/"));
        if (file) onDropArtifact(file);
      }}
    >
      <div className="dialogue-console__header">
        <span>DIALOGUE</span>
        <small>{stamp(selectedEntry.envelope.generated_at)}</small>
      </div>
      {showPhaseReadback ? (
        <div className="phase-readback" role="status" aria-live="polite">
          <span>{phaseCopy.label}</span>
          <p>{phaseCopy.detail}</p>
        </div>
      ) : null}
      {linkedUserMessage ? (
        <article className="user-line">
          <span>你</span>
          <p>{linkedUserMessage.text}</p>
        </article>
      ) : null}
      <article className="amadeus-line">
        <span>Amadeus-K</span>
        <p>{projection.currentLine}</p>
      </article>
      {showMemoryPulse && projection.memoryPulse ? (
        <div className="memory-pulse">
          <span>{projection.memoryPulse.label}</span>
          <p>{projection.memoryPulse.title}</p>
        </div>
      ) : null}
      <div className="media-readback" role="status" aria-live="polite">
        <div>
          <span>MEDIA</span>
          <strong>{media.callActive ? "通话中" : "房间模式"}</strong>
          <p>
            {mediaStatusLabel(media.status)}
            {media.session?.payload.status ? ` / ${media.session.payload.status}` : ""}
            {media.latestMediaTurn?.payload.status ? ` / ${media.latestMediaTurn.payload.status}` : ""}
          </p>
        </div>
        {media.cameraEnabled ? (
          <div className="camera-preview">
            <video ref={videoRef} muted playsInline />
            <small>Camera On</small>
          </div>
        ) : null}
      </div>
      {media.latestArtifact ? (
        <div className="artifact-chip">
          <span>她收到的材料</span>
          <strong>{text(asRecord(media.latestArtifact.payload.artifact).label, media.lastArtifactLabel || "image")}</strong>
          <small>{text(media.latestArtifact.payload.status, "accepted")}</small>
        </div>
      ) : null}
      <form className="composer" onSubmit={handleSubmit}>
        <textarea
          value={draftMessage}
          onChange={(event) => onDraftChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              onSubmit();
            }
          }}
          placeholder={session.transportMode === "route" ? "对她说点什么..." : "离线预览模式不能发送真实消息"}
          rows={2}
          disabled={isSending}
          aria-label="Message Amadeus-K"
        />
        <TerminalButton type="submit" variant="primary" disabled={!canSend}>
          {isSending ? "WAIT" : "SEND"}
        </TerminalButton>
      </form>
      {sendError ? <p className="composer-error">发送失败，草稿已保留。{text(sendError, "")}</p> : null}
      {media.error ? <p className="composer-error">媒体链路：{media.error}</p> : null}
      <details className="turn-history">
        <summary>最近回合</summary>
        <div>
          {session.transcript.slice(0, 6).map((entry) => {
            const payload = currentPayload(entry);
            return (
              <button
                key={entry.id}
                type="button"
                className={entry.id === selectedEntry.id ? "is-active" : ""}
                onClick={() => onSelectTurn(entry.id)}
              >
                <span>{entry.envelope.kind}</span>
                <strong>{payload.final_text}</strong>
              </button>
            );
          })}
        </div>
      </details>
    </section>
  );
}

function RoomSurface({
  projection,
  session,
  selectedEntry,
  localUserMessages,
  draftMessage,
  sendError,
  isSending,
  companionPhase,
  media,
  videoRef,
  onDropArtifact,
  onDraftChange,
  onSubmit,
  onSelectTurn,
}: {
  projection: CompanionProjection;
  session: RuntimeSession;
  selectedEntry: TranscriptEntry;
  localUserMessages: LocalUserMessage[];
  draftMessage: string;
  sendError: string;
  isSending: boolean;
  companionPhase: CompanionPhase;
  media: MediaRuntimeState;
  videoRef: RefObject<HTMLVideoElement | null>;
  onDropArtifact: (file: File) => void;
  onDraftChange: (value: string) => void;
  onSubmit: () => void;
  onSelectTurn: (id: string) => void;
}) {
  const phaseCopy = companionPhaseCopy[companionPhase];
  return (
    <div className="room-surface">
      <div className="presence-strip">
        <div className="phase-tile">
          <span>回合节律</span>
          <strong>{phaseCopy.label}</strong>
        </div>
        {projection.presenceReadouts.slice(0, 3).map((readout) => (
          <div key={readout.label}>
            <span>{readout.label}</span>
            <strong>{readout.value}</strong>
          </div>
        ))}
      </div>
      {projection.pendingApproval ? (
        <section className="approval-readback">
          <span>只读待确认</span>
          <p>{text(asRecord(projection.pendingApproval.execution_preview).summary ?? projection.pendingApproval.expected_effect, "有一个后端 action packet 正在等待确认。")}</p>
        </section>
      ) : null}
      <DialogueConsole
        session={session}
        selectedEntry={selectedEntry}
        projection={projection}
        localUserMessages={localUserMessages}
        draftMessage={draftMessage}
        sendError={sendError}
        isSending={isSending}
        companionPhase={companionPhase}
        media={media}
        videoRef={videoRef}
        onDropArtifact={onDropArtifact}
        onDraftChange={onDraftChange}
        onSubmit={onSubmit}
        onSelectTurn={onSelectTurn}
      />
    </div>
  );
}

function MemorySurface({ projection }: { projection: CompanionProjection }) {
  return (
    <section className="content-surface">
      <PanelHeader eyebrow="SHARED MEMORY" title="她记得的事">
        这些卡片来自 worldline、reconsolidation 和长期叙事，不由前端自行总结。
      </PanelHeader>
      <ProjectionCards cards={projection.memoryCards} empty="还没有可展示的共同记忆。" />
    </section>
  );
}

function RelationshipSurface({ projection }: { projection: CompanionProjection }) {
  return (
    <section className="content-surface">
      <PanelHeader eyebrow="RELATIONSHIP" title="你们之间的变化">
        不做廉价好感度条，只把后端关系状态翻译成可读的关系气候。
      </PanelHeader>
      <ProjectionCards cards={projection.relationshipCards} empty="还没有可展示的关系轨迹。" />
    </section>
  );
}

function PresenceSurface({
  projection,
  selectedEntry,
  media,
}: {
  projection: CompanionProjection;
  selectedEntry: TranscriptEntry;
  media: MediaRuntimeState;
}) {
  const payload = currentPayload(selectedEntry);
  const sessionPayload = media.session?.payload as MediaSessionPayload | undefined;
  const mediaTurnPayload = media.latestMediaTurn?.payload as MediaTurnPayload | undefined;
  const ttsPayload = media.latestTts?.payload as MediaTtsPayload | undefined;
  return (
    <section className="content-surface">
      <PanelHeader eyebrow="PRESENCE" title="她此刻的内在状态">
        这里呈现情绪、动机、边界和数字身体状态。原始 readback 默认折叠。
      </PanelHeader>
      <div className="presence-readout-grid">
        {projection.presenceReadouts.map((readout) => (
          <article key={readout.label}>
            <span>{readout.label}</span>
            <strong>{readout.value}</strong>
            <p>{readout.detail}</p>
          </article>
        ))}
        <article>
          <span>媒体会话</span>
          <strong>{sessionPayload?.active ? "显式开启" : "未开启"}</strong>
          <p>{sessionPayload?.capture_policy ?? "桌面 live capture 只在用户主动开启的会话内生效。"}</p>
        </article>
        <article>
          <span>摄像头</span>
          <strong>{media.cameraEnabled ? "Camera On" : "Camera Off"}</strong>
          <p>{text(asRecord(mediaTurnPayload?.vision).status, "没有后台采集；视频帧只作为后端 readback 输入。")}</p>
        </article>
        <article>
          <span>语音</span>
          <strong>{mediaStatusLabel(media.status)}</strong>
          <p>{text(asRecord(mediaTurnPayload?.asr).status ?? ttsPayload?.status, "ASR/TTS 失败时保持文字降级。")}</p>
        </article>
      </div>
      <JsonPeek
        label="living_loop_realism / embodied_interaction / media"
        value={{
          living_loop_realism: payload.living_loop_realism,
          embodied_interaction: payload.embodied_interaction,
          turn_appraisal: payload.turn_appraisal,
          media_session: sessionPayload,
          latest_media_turn: mediaTurnPayload,
          latest_tts: ttsPayload,
        }}
      />
    </section>
  );
}

function GrowthSurface({ projection }: { projection: CompanionProjection }) {
  return (
    <section className="content-surface">
      <PanelHeader eyebrow="GROWTH" title="她正在形成的能力">
        技能和多模态经历作为数字身体能力资产展示，不写入 persona core。
      </PanelHeader>
      <ProjectionCards cards={projection.growthCards} empty="当前没有可展示的成长事件。" />
    </section>
  );
}

function OperatorSurface({
  session,
  selectedEntry,
  debugJson,
  debugResult,
  debugError,
  isDebugSubmitting,
  debugEnabled,
  onDebugJsonChange,
  onFinalizeTurn,
  onFinalizeEventRound,
}: {
  session: RuntimeSession;
  selectedEntry: TranscriptEntry;
  debugJson: string;
  debugResult: unknown;
  debugError: string;
  isDebugSubmitting: boolean;
  debugEnabled: boolean;
  onDebugJsonChange: (value: string) => void;
  onFinalizeTurn: () => void;
  onFinalizeEventRound: () => void;
}) {
  const payload = currentPayload(selectedEntry);
  const operator = asRecord(session.operatorConsoleRc?.payload);
  const runtime = asRecord(session.runtimeProductization?.payload);
  const routeInventory = asRecord(operator.route_inventory ?? runtime.route_inventory);
  const authority = asRecord(operator.authority_boundary ?? runtime.authority_boundary);
  const rows: Array<[string, unknown]> = [
    ["schema", session.schemaVersion],
    ["thread", session.threadId],
    ["mode", session.transportMode],
    ["operator", operator.readiness_status ?? runtime.readiness_status],
    ["routes", routeInventory.route_count ?? summarizeValue(routeInventory)],
    ["pending", payload.autonomy?.pending_approval ? "readback only" : "none"],
  ];

  return (
    <section className="content-surface operator-surface">
      <PanelHeader eyebrow="OPERATOR REALITY" title="只读控制台">
        这里保留评审和验收所需的后端证据，默认不暴露给普通用户。
      </PanelHeader>
      <div className="operator-grid">
        {rows.map(([label, value]) => (
          <article key={label}>
            <span>{label}</span>
            <strong>{summarizeValue(value)}</strong>
          </article>
        ))}
      </div>
      <div className="operator-columns">
        <JsonPeek label="Authority boundary" value={authority} />
        <JsonPeek label="Route inventory" value={routeInventory} />
        <JsonPeek label="Operator readback" value={payload.operator_readback} />
        <JsonPeek label="Raw archive envelopes" value={{ current: session.currentCheckpoint, history: session.checkpointHistory }} />
        <JsonPeek label="Runtime productization" value={session.runtimeProductization?.payload} />
        <JsonPeek label="Operator console RC" value={session.operatorConsoleRc?.payload} />
        <JsonPeek label="Living loop realism" value={payload.living_loop_realism} />
        <JsonPeek label="Embodied interaction" value={payload.embodied_interaction} />
      </div>
      {debugEnabled ? (
        <section className="debug-editor">
          <h3>Debug finalize preview</h3>
          <textarea value={debugJson} onChange={(event) => onDebugJsonChange(event.target.value)} rows={8} aria-label="Debug JSON input" />
          <div className="debug-actions">
            <TerminalButton onClick={onFinalizeTurn} disabled={isDebugSubmitting} variant="primary">
              POST /api/turns/finalize
            </TerminalButton>
            <TerminalButton onClick={onFinalizeEventRound} disabled={isDebugSubmitting}>
              POST /api/event-rounds/finalize
            </TerminalButton>
          </div>
          {debugError ? <p className="composer-error">{debugError}</p> : null}
          {debugResult !== null ? <JsonPeek value={debugResult} label="Finalize response" /> : null}
        </section>
      ) : (
        <p className="empty-copy">设置 VITE_AMADEUS_DEBUG=true 后显示 finalize 调试工具。</p>
      )}
    </section>
  );
}

function EvidenceRibbon({ projection }: { projection: CompanionProjection }) {
  return (
    <aside className="evidence-ribbon" aria-label="Backend evidence ribbon">
      <span>EVIDENCE</span>
      <strong>{projection.evidenceCount}</strong>
      <p>来源线索</p>
      {projection.sourceCards.slice(0, 3).map((card) => (
        <small key={card.id}>{card.title}</small>
      ))}
    </aside>
  );
}

function BootScreen({
  error,
  isRefreshing,
  onRetry,
}: {
  error?: string;
  isRefreshing?: boolean;
  onRetry?: () => void;
}) {
  return (
    <main className="boot-screen">
      <section className={error ? "boot-card boot-card--error" : "boot-card"}>
        <span>AMADEUS-K</span>
        <strong>{error ? "未连接到后端" : "正在进入终端房间"}</strong>
        <p>{error ? createFriendlyError(error) : "读取最近一次回复、关系状态和长期记忆。"}</p>
        {error && onRetry ? (
          <TerminalButton onClick={onRetry} disabled={isRefreshing} variant="primary">
            {isRefreshing ? "RETRYING" : "RETRY"}
          </TerminalButton>
        ) : null}
      </section>
    </main>
  );
}

function App() {
  const [client] = useState(() => createBackendClient());
  const [session, setSession] = useState<RuntimeSession | null>(null);
  const [selectedTurnId, setSelectedTurnId] = useState("");
  const [activeSurface, setActiveSurface] = useState<CompanionSurface>("room");
  const [draftMessage, setDraftMessage] = useState("");
  const [sendError, setSendError] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [companionPhase, setCompanionPhase] = useState<CompanionPhase>("idle");
  const [loadError, setLoadError] = useState("");
  const [refreshError, setRefreshError] = useState("");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [localUserMessages, setLocalUserMessages] = useState<LocalUserMessage[]>([]);
  const [debugJson, setDebugJson] = useState('{\n  "state_values": {},\n  "meta": {\n    "client": "frontend_debug"\n  }\n}');
  const [debugResult, setDebugResult] = useState<unknown>(null);
  const [debugError, setDebugError] = useState("");
  const [isDebugSubmitting, setIsDebugSubmitting] = useState(false);
  const [avatarInspectorState, setAvatarInspectorState] = useState<AvatarInspectorState>(initialAvatarInspectorState);
  const [media, setMedia] = useState<MediaRuntimeState>(initialMediaRuntime);
  const debugEnabled = String(import.meta.env.VITE_AMADEUS_DEBUG ?? "").toLowerCase() === "true";
  const initialLoadPromise = useRef<Promise<RuntimeSession> | null>(null);
  const phaseTimers = useRef<Array<ReturnType<typeof window.setTimeout>>>([]);
  const phaseSequence = useRef(0);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const frameTimerRef = useRef<ReturnType<typeof window.setInterval> | null>(null);

  function clearPhaseTimers() {
    phaseTimers.current.forEach((timer) => window.clearTimeout(timer));
    phaseTimers.current = [];
  }

  function schedulePhase(sequenceId: number, phase: CompanionPhase, delay: number) {
    const timer = window.setTimeout(() => {
      if (phaseSequence.current === sequenceId) setCompanionPhase(phase);
    }, delay);
    phaseTimers.current.push(timer);
  }

  function settlePhaseFromDraft(value = draftMessage) {
    if (isSending) return;
    clearPhaseTimers();
    phaseSequence.current += 1;
    setCompanionPhase(value.trim().length ? "composing" : "idle");
  }

  function clearFrameTimer() {
    if (frameTimerRef.current) {
      window.clearInterval(frameTimerRef.current);
      frameTimerRef.current = null;
    }
  }

  function stopLocalMediaTracks() {
    clearFrameTimer();
    mediaRecorderRef.current?.stop();
    mediaRecorderRef.current = null;
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    mediaStreamRef.current = null;
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  }

  async function refreshDesktopMediaState() {
    try {
      const [capabilities, mediaSession] = await Promise.all([
        client.loadDesktopCapabilities(),
        client.loadCurrentMediaSession(),
      ]);
      setMedia((current) => ({
        ...current,
        capabilities,
        session: mediaSession,
        callActive: Boolean(mediaSession.payload.active),
        error: "",
      }));
    } catch (error: unknown) {
      setMedia((current) => ({
        ...current,
        error: error instanceof Error ? error.message : String(error),
      }));
    }
  }

  async function enrichDebugSnapshot(snapshot: RuntimeSession) {
    const [
      threadInventory,
      runtimeLayout,
      environmentSummary,
      appraisal,
      runtimeProductization,
      operatorConsoleRc,
      currentCheckpoint,
      checkpointHistory,
    ] = await Promise.all([
      client.loadThreadInventory(),
      client.loadRuntimeLayout(),
      client.loadEnvironmentSummary(),
      client.loadAppraisal(),
      client.loadRuntimeProductization(),
      client.loadOperatorConsoleRc(),
      client.loadCurrentCheckpoint(),
      client.loadCheckpointHistory(10),
    ]);

    return {
      ...snapshot,
      threadInventory,
      runtimeLayout,
      environmentSummary,
      appraisal,
      runtimeProductization,
      operatorConsoleRc,
      currentCheckpoint,
      checkpointHistory,
    };
  }

  function applySnapshot(snapshot: RuntimeSession) {
    setSession(snapshot);
    setSelectedTurnId(snapshot.transcript[0]?.id ?? "");
    setLoadError("");
    setRefreshError("");
  }

  async function loadSnapshot() {
    setIsRefreshing(true);
    setRefreshError("");
    try {
      const snapshot = await client.loadSessionSnapshot();
      applySnapshot(debugEnabled ? await enrichDebugSnapshot(snapshot) : snapshot);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      setLoadError(message);
      setRefreshError(message);
    } finally {
      setIsRefreshing(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    window.amadeusDesktop?.startBackend().catch(() => undefined);
    if (!initialLoadPromise.current) {
      initialLoadPromise.current = client
        .loadSessionSnapshot()
        .then((snapshot) => (debugEnabled ? enrichDebugSnapshot(snapshot) : snapshot));
    }

    setIsRefreshing(true);
    initialLoadPromise.current
      .then((snapshot) => {
        if (!cancelled) applySnapshot(snapshot);
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : String(error);
          setLoadError(message);
          setRefreshError(message);
        }
      })
      .finally(() => {
        if (!cancelled) setIsRefreshing(false);
      });

    return () => {
      cancelled = true;
    };
  }, [client, debugEnabled]);

  useEffect(() => {
    void refreshDesktopMediaState();
  }, [client]);

  useEffect(() => {
    return () => {
      clearPhaseTimers();
      stopLocalMediaTracks();
      if (audioRef.current) audioRef.current.pause();
    };
  }, []);

  const selectedEntry = useMemo(() => {
    if (!session) return null;
    return session.transcript.find((entry) => entry.id === selectedTurnId) ?? session.transcript[0] ?? null;
  }, [selectedTurnId, session]);

  const projection = useMemo(() => {
    if (!session || !selectedEntry) return null;
    return createCompanionProjection(session, selectedEntry);
  }, [selectedEntry, session]);

  const avatarOverride = useMemo<AvatarRuntimeOverride | undefined>(() => {
    if (!debugEnabled) return undefined;
    return {
      expression: avatarInspectorState.expression || undefined,
      phase: avatarInspectorState.phase || undefined,
      live2dMotionTarget: avatarInspectorState.motionTarget || undefined,
      placement: {
        scaleMultiplier: avatarInspectorState.scaleMultiplier,
        offsetX: avatarInspectorState.offsetX,
        offsetY: avatarInspectorState.offsetY,
      },
      runtimeRevision: avatarInspectorState.revision,
    };
  }, [
    avatarInspectorState.expression,
    avatarInspectorState.offsetX,
    avatarInspectorState.offsetY,
    avatarInspectorState.motionTarget,
    avatarInspectorState.phase,
    avatarInspectorState.revision,
    avatarInspectorState.scaleMultiplier,
    debugEnabled,
  ]);

  const avatar = useMemo(() => {
    if (!projection) return null;
    return createAvatarRuntimeState(projection, companionPhase, avatarOverride);
  }, [avatarOverride, companionPhase, projection]);

  function updateAvatarInspector(patch: Partial<AvatarInspectorState>, replayMotion = false) {
    setAvatarInspectorState((current) => ({
      ...current,
      ...patch,
      revision: replayMotion ? current.revision + 1 : current.revision,
    }));
  }

  function resetAvatarInspector() {
    setAvatarInspectorState((current) => ({
      ...initialAvatarInspectorState,
      revision: current.revision + 1,
    }));
  }

  function appendTurnEnvelope(envelope: BackendEnvelopeFor<"assistant_turn">, userMessage?: string) {
    const entry = transcriptEntryFromEnvelope(envelope);
    setSession((current) => {
      if (!current) return current;
      return appendAssistantTurnToSession(current, envelope, entry);
    });
    if (userMessage) {
      setLocalUserMessages((current) => [
        ...current,
        {
          id: `user-${Date.now()}`,
          text: userMessage,
          createdAt: Date.now() / 1000,
          assistantEntryId: entry.id,
        },
      ]);
    }
    setSelectedTurnId(entry.id);
  }

  function handleDraftMessageChange(value: string) {
    setDraftMessage(value);
    if (!isSending) {
      setSendError("");
      settlePhaseFromDraft(value);
    }
  }

  async function handleSendMessage() {
    const message = draftMessage.trim();
    if (!message || isSending) return;
    if (session?.transportMode !== "route") {
      setSendError("offline");
      setCompanionPhase("composing");
      return;
    }

    const sequenceId = phaseSequence.current + 1;
    phaseSequence.current = sequenceId;
    clearPhaseTimers();
    setIsSending(true);
    setCompanionPhase("sending");
    setSendError("");
    schedulePhase(sequenceId, "awaiting_response", 240);
    try {
      const envelope = await client.sendMessage(message);
      clearPhaseTimers();
      phaseSequence.current = sequenceId + 1;
      appendTurnEnvelope(envelope, message);
      setDraftMessage("");
      setActiveSurface("room");
      setCompanionPhase("response_ready");
      schedulePhase(phaseSequence.current, "displaying_line", 260);
      schedulePhase(phaseSequence.current, "memory_update_hint", 1450);
      schedulePhase(phaseSequence.current, "idle", 3200);
      void playAssistantTts(envelope);
    } catch (error: unknown) {
      clearPhaseTimers();
      phaseSequence.current += 1;
      setSendError(error instanceof Error ? error.message : String(error));
      setCompanionPhase("composing");
    } finally {
      setIsSending(false);
    }
  }

  async function playAssistantTts(envelope: BackendEnvelopeFor<"assistant_turn">) {
    const line = String(envelope.payload.final_text || "").trim();
    if (!line) return;
    try {
      const ttsEnvelope = await client.synthesizeMediaTts({
        text: line,
        emotion_label: envelope.payload.emotion_label,
      });
      setMedia((current) => ({
        ...current,
        latestTts: ttsEnvelope,
        status: ttsEnvelope.payload.status === "synthesized" ? "speaking" : current.status,
        error:
          ttsEnvelope.payload.status === "synthesized"
            ? ""
            : failureText(ttsEnvelope.payload.failure_reasons, "TTS 降级为文字。"),
      }));
      const audioUrl = text(asRecord(ttsEnvelope.payload.audio).url, "");
      const audioBase64 = text(asRecord(ttsEnvelope.payload.audio).base64, "");
      if (ttsEnvelope.payload.status === "synthesized" && (audioBase64 || audioUrl)) {
        const base = String(import.meta.env.VITE_AMADEUS_API_BASE ?? window.amadeusDesktop?.backendBase ?? "");
        const resolvedUrl = audioBase64
          ? `data:audio/wav;base64,${audioBase64}`
          : audioUrl.startsWith("http")
            ? audioUrl
            : `${base.replace(/\/$/, "")}${audioUrl}`;
        const audio = new Audio(resolvedUrl);
        audioRef.current = audio;
        setCompanionPhase("speaking");
        audio.onended = () => {
          setMedia((current) => ({ ...current, status: current.callActive ? "listening" : "idle" }));
          setCompanionPhase("idle");
        };
        await audio.play();
      }
    } catch (error: unknown) {
      setMedia((current) => ({
        ...current,
        error: `TTS 降级为文字：${error instanceof Error ? error.message : String(error)}`,
      }));
    }
  }

  function parseDebugBody() {
    const parsed = JSON.parse(debugJson) as unknown;
    if (!isRecord(parsed)) throw new Error("Debug body must be a JSON object.");
    return parsed;
  }

  async function handleFinalizeTurn() {
    setIsDebugSubmitting(true);
    setDebugError("");
    try {
      const parsed = parseDebugBody();
      const envelope = await client.finalizeTurn({
        state_values: asRecord(parsed.state_values),
        streamed_text: typeof parsed.streamed_text === "string" ? parsed.streamed_text : undefined,
        meta: asRecord(parsed.meta),
      });
      setDebugResult(envelope);
      appendTurnEnvelope(envelope);
    } catch (error: unknown) {
      setDebugError(error instanceof Error ? error.message : String(error));
    } finally {
      setIsDebugSubmitting(false);
    }
  }

  async function handleFinalizeEventRound() {
    setIsDebugSubmitting(true);
    setDebugError("");
    try {
      const parsed = parseDebugBody();
      const envelope = await client.finalizeEventRound({
        state_values: asRecord(parsed.state_values),
        final_text: typeof parsed.final_text === "string" ? parsed.final_text : undefined,
        meta: asRecord(parsed.meta),
      });
      const entry = transcriptEntryFromEnvelope(envelope);
      setDebugResult(envelope);
      setSession((current) =>
        current
          ? {
              ...current,
              transcript: [entry, ...current.transcript].sort((left, right) => right.envelope.generated_at - left.envelope.generated_at),
            }
          : current,
      );
      setSelectedTurnId(entry.id);
    } catch (error: unknown) {
      setDebugError(error instanceof Error ? error.message : String(error));
    } finally {
      setIsDebugSubmitting(false);
    }
  }

  async function captureAndSubmitFrame(source: "interval" | "snapshot" = "interval") {
    const video = videoRef.current;
    if (!video || !media.cameraEnabled || !media.callActive || video.videoWidth <= 0 || video.videoHeight <= 0) return;
    const canvas = document.createElement("canvas");
    const width = Math.min(640, video.videoWidth);
    const height = Math.max(1, Math.round((video.videoHeight / video.videoWidth) * width));
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) return;
    context.drawImage(video, 0, 0, width, height);
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.78));
    if (!blob) return;
    const buffer = await blob.arrayBuffer();
    const digest = await sha256Hex(buffer);
    const envelope = await client.submitMediaVideoFrame({
      consent: true,
      frame_digest: digest,
      width,
      height,
      captured_at: Math.floor(Date.now() / 1000),
      caption: source === "snapshot" ? "user_triggered_camera_snapshot" : "low_frequency_camera_frame",
    });
    setMedia((current) => ({
      ...current,
      latestMediaTurn: envelope,
      lastFrameAt: Date.now(),
      status: current.callActive ? "listening" : "idle",
      error: failureText(envelope.payload.failure_reasons, ""),
    }));
  }

  function startLowFrequencyFrameLoop() {
    clearFrameTimer();
    frameTimerRef.current = window.setInterval(() => {
      void captureAndSubmitFrame("interval");
    }, 5000);
  }

  async function handleStartCall() {
    if (media.callActive) return;
    setMedia((current) => ({ ...current, status: "requesting", error: "" }));
    try {
      window.amadeusDesktop?.startCall().catch(() => undefined);
      await client.requestDesktopPermissions({
        permissions: ["microphone", "camera"],
        source: "desktop_user_action",
      });
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: true });
      mediaStreamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play().catch(() => undefined);
      }
      const devices = await navigator.mediaDevices.enumerateDevices().catch(() => []);
      const mediaSession = await client.startMediaSession({
        consent: true,
        requested_permissions: ["microphone", "camera"],
        mode: "human_ai_av_call",
        mic_muted: false,
      });
      setMedia((current) => ({
        ...current,
        callActive: Boolean(mediaSession.payload.active),
        micMuted: false,
        cameraEnabled: true,
        status: "listening",
        devices,
        session: mediaSession,
        error: failureText(mediaSession.payload.failure_reasons, ""),
      }));
      setCompanionPhase("listening");
      startLowFrequencyFrameLoop();
      window.amadeusDesktop?.setCameraEnabled(true).catch(() => undefined);
      window.amadeusDesktop?.setMicMuted(false).catch(() => undefined);
    } catch (error: unknown) {
      stopLocalMediaTracks();
      setMedia((current) => ({
        ...current,
        callActive: false,
        cameraEnabled: false,
        status: "error",
        error: error instanceof Error ? error.message : String(error),
      }));
      setCompanionPhase("idle");
    }
  }

  async function handleStopCall() {
    stopLocalMediaTracks();
    window.amadeusDesktop?.stopCall().catch(() => undefined);
    try {
      const mediaSession = await client.stopMediaSession({ reason: "user_stopped" });
      setMedia((current) => ({
        ...current,
        callActive: false,
        cameraEnabled: false,
        micMuted: false,
        status: "idle",
        session: mediaSession,
        error: "",
      }));
    } catch (error: unknown) {
      setMedia((current) => ({
        ...current,
        callActive: false,
        cameraEnabled: false,
        status: "error",
        error: error instanceof Error ? error.message : String(error),
      }));
    }
    setCompanionPhase("idle");
  }

function handleToggleMic() {
    const nextMuted = !media.micMuted;
    mediaStreamRef.current?.getAudioTracks().forEach((track) => {
      track.enabled = !nextMuted;
    });
    setMedia((current) => ({
      ...current,
      micMuted: nextMuted,
      status: nextMuted ? "muted" : current.callActive ? "listening" : "idle",
    }));
    window.amadeusDesktop?.setMicMuted(nextMuted).catch(() => undefined);
  }

  async function handleToggleCamera() {
    if (!media.callActive) return;
    if (media.cameraEnabled) {
      clearFrameTimer();
      mediaStreamRef.current?.getVideoTracks().forEach((track) => track.stop());
      if (videoRef.current) videoRef.current.srcObject = null;
      setMedia((current) => ({ ...current, cameraEnabled: false, status: current.callActive ? "listening" : "idle" }));
      window.amadeusDesktop?.setCameraEnabled(false).catch(() => undefined);
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      const current = mediaStreamRef.current;
      if (current) {
        stream.getVideoTracks().forEach((track) => current.addTrack(track));
      } else {
        mediaStreamRef.current = stream;
      }
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStreamRef.current;
        await videoRef.current.play().catch(() => undefined);
      }
      setMedia((state) => ({ ...state, cameraEnabled: true, status: "listening", error: "" }));
      startLowFrequencyFrameLoop();
      await captureAndSubmitFrame("snapshot");
      window.amadeusDesktop?.setCameraEnabled(true).catch(() => undefined);
    } catch (error: unknown) {
      setMedia((current) => ({ ...current, status: "error", error: error instanceof Error ? error.message : String(error) }));
    }
  }

  async function handleCaptureVoice() {
    if (!media.callActive || media.micMuted || !mediaStreamRef.current) return;
    if (!window.MediaRecorder) {
      setMedia((current) => ({ ...current, status: "error", error: "当前浏览器内核不支持 MediaRecorder。" }));
      return;
    }
    try {
      setMedia((current) => ({ ...current, status: "listening", error: "" }));
      setCompanionPhase("listening");
      const stream = new MediaStream(mediaStreamRef.current.getAudioTracks());
      const chunks: Blob[] = [];
      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunks.push(event.data);
      };
      const stopped = new Promise<Blob>((resolve, reject) => {
        recorder.onerror = () => reject(new Error("录音失败"));
        recorder.onstop = () => resolve(new Blob(chunks, { type: recorder.mimeType || "audio/webm" }));
      });
      recorder.start();
      window.setTimeout(() => {
        if (recorder.state !== "inactive") recorder.stop();
      }, 3200);
      const rawBlob = await stopped;
      setMedia((current) => ({ ...current, status: "transcribing" }));
      setCompanionPhase("transcribing");
      const normalized = await normalizeAudioForAsr(rawBlob);
      const buffer = await normalized.blob.arrayBuffer();
      const digest = await sha256Hex(buffer);
      const envelope = await client.submitMediaAudio({
        consent: true,
        duration_ms: 3200,
        audio_digest: digest,
        audio_base64: await blobToBase64(normalized.blob),
        audio_format: normalized.format,
        sample_rate_hz: normalized.sampleRate,
        mime_type: normalized.blob.type || "audio/wav",
        source: "desktop_microphone_user_consented",
      });
      setMedia((current) => ({
        ...current,
        latestMediaTurn: envelope,
        status: envelope.payload.status === "transcript_ready" ? "thinking" : "error",
        error: failureText(envelope.payload.failure_reasons, ""),
      }));
      const assistantTurn = asRecord(envelope.payload.assistant_turn) as unknown as BackendEnvelopeFor<"assistant_turn">;
      if (envelope.payload.status === "transcript_ready" && assistantTurn?.kind === "assistant_turn") {
        clearPhaseTimers();
        phaseSequence.current += 1;
        appendTurnEnvelope(assistantTurn, text(asRecord(envelope.payload.asr).transcript, "语音输入"));
        setCompanionPhase("response_ready");
        schedulePhase(phaseSequence.current, "displaying_line", 260);
        schedulePhase(phaseSequence.current, "memory_update_hint", 1450);
        schedulePhase(phaseSequence.current, "idle", 3200);
        void playAssistantTts(assistantTurn);
      } else {
        setCompanionPhase("idle");
      }
    } catch (error: unknown) {
      setMedia((current) => ({
        ...current,
        status: "error",
        error: error instanceof Error ? error.message : String(error),
      }));
      setCompanionPhase("idle");
    }
  }

  async function handleSubmitArtifact(file: File, captureMethod = "user_selected_file") {
    try {
      const buffer = await file.arrayBuffer();
      const digest = await sha256Hex(buffer);
      const envelope = await client.submitArtifact({
        consent: true,
        modality: file.type.startsWith("image/") ? "image" : "file",
        content_digest: digest,
        filename: file.name,
        label: file.name,
        mime_type: file.type,
        size_bytes: file.size,
        capture_method: captureMethod,
      });
      setMedia((current) => ({
        ...current,
        latestArtifact: envelope,
        lastArtifactLabel: file.name,
        error: failureText(envelope.payload.failure_reasons, ""),
      }));
      setActiveSurface("room");
    } catch (error: unknown) {
      setMedia((current) => ({
        ...current,
        status: "error",
        error: error instanceof Error ? error.message : String(error),
      }));
    }
  }

  async function refreshCurrentTurn() {
    if (!session) return;
    setIsRefreshing(true);
    setRefreshError("");
    try {
      const envelope = await client.loadCurrentTurn();
      const entry = transcriptEntryFromEnvelope(envelope);
      setSession((current) => (current ? upsertAssistantTurnInSession(current, envelope, entry) : current));
      setSelectedTurnId(entry.id);
    } catch (error: unknown) {
      setRefreshError(error instanceof Error ? error.message : String(error));
    } finally {
      setIsRefreshing(false);
    }
  }

  async function refreshSurface(surface: CompanionSurface) {
    if (surface === "room") {
      await refreshCurrentTurn();
      return;
    }

    setIsRefreshing(true);
    setRefreshError("");
    try {
      if (surface === "memory") {
        const worldline = await client.loadWorldline();
        setSession((current) => (current ? { ...current, worldline } : current));
      } else if (surface === "relationship") {
        const bond = await client.loadBond();
        setSession((current) => (current ? { ...current, bond } : current));
      } else if (surface === "presence") {
        const persona = await client.loadPersona();
        const behaviorQueue = await client.loadBehaviorQueue();
        setSession((current) => (current ? { ...current, persona, behaviorQueue } : current));
      } else if (surface === "growth") {
        const behaviorQueue = await client.loadBehaviorQueue();
        setSession((current) => (current ? { ...current, behaviorQueue } : current));
      } else if (surface === "operator") {
        const runtimeProductization = await client.loadRuntimeProductization();
        const operatorConsoleRc = await client.loadOperatorConsoleRc();
        const currentCheckpoint = await client.loadCurrentCheckpoint();
        const checkpointHistory = await client.loadCheckpointHistory(20);
        setSession((current) =>
          current
            ? {
                ...current,
                runtimeProductization,
                operatorConsoleRc,
                currentCheckpoint,
                checkpointHistory,
              }
            : current,
        );
      }
    } catch (error: unknown) {
      setRefreshError(error instanceof Error ? error.message : String(error));
    } finally {
      setIsRefreshing(false);
    }
  }

  if (loadError && !session) {
    return <BootScreen error={loadError} isRefreshing={isRefreshing} onRetry={() => void loadSnapshot()} />;
  }

  if (!session || !selectedEntry || !projection || !avatar) {
    return <BootScreen />;
  }

  const payload = currentPayload(selectedEntry);
  const summary = payload.turn_summary?.current_turn ?? {};

  return (
    <main className={`terminal-room-shell surface-${activeSurface} tone-${projection.sceneTone} phase-${companionPhase}`}>
      <TopHud
        session={session}
        projection={projection}
        companionPhase={companionPhase}
        isRefreshing={isRefreshing}
        refreshError={refreshError}
        onRefresh={() => void refreshSurface(activeSurface)}
      />
      <SideRail activeSurface={activeSurface} debugEnabled={debugEnabled} onSelect={setActiveSurface} />
      <AvatarStage projection={projection} avatar={avatar} />
      {debugEnabled ? (
        <AvatarInspector avatar={avatar} state={avatarInspectorState} onUpdate={updateAvatarInspector} onReset={resetAvatarInspector} />
      ) : null}
      <EvidenceRibbon projection={projection} />

      <section className="bottom-control">
        <div className="relationship-meter" aria-label="relationship continuity meters">
          <span>TRUST {ratioLabel(summary.trust)}</span>
          <span>CLOSE {ratioLabel(summary.closeness)}</span>
          <span>RHYTHM {ratioLabel(summary.carryover_strength)}</span>
        </div>
        <MediaControls
          media={media}
          onStartCall={() => void handleStartCall()}
          onStopCall={() => void handleStopCall()}
          onToggleMic={handleToggleMic}
          onToggleCamera={() => void handleToggleCamera()}
          onCaptureVoice={() => void handleCaptureVoice()}
          onSubmitArtifact={(file) => void handleSubmitArtifact(file)}
        />
      </section>

      <section className="surface-frame">
        {activeSurface === "room" ? (
          <RoomSurface
            projection={projection}
            session={session}
            selectedEntry={selectedEntry}
            localUserMessages={localUserMessages}
            draftMessage={draftMessage}
            sendError={sendError}
            isSending={isSending}
            companionPhase={companionPhase}
            media={media}
            videoRef={videoRef}
            onDropArtifact={(file) => void handleSubmitArtifact(file)}
            onDraftChange={handleDraftMessageChange}
            onSubmit={() => void handleSendMessage()}
            onSelectTurn={setSelectedTurnId}
          />
        ) : null}
        {activeSurface === "memory" ? <MemorySurface projection={projection} /> : null}
        {activeSurface === "relationship" ? <RelationshipSurface projection={projection} /> : null}
        {activeSurface === "presence" ? <PresenceSurface projection={projection} selectedEntry={selectedEntry} media={media} /> : null}
        {activeSurface === "growth" ? <GrowthSurface projection={projection} /> : null}
        {activeSurface === "operator" ? (
          <OperatorSurface
            session={session}
            selectedEntry={selectedEntry}
            debugJson={debugJson}
            debugResult={debugResult}
            debugError={debugError}
            isDebugSubmitting={isDebugSubmitting}
            debugEnabled={debugEnabled}
            onDebugJsonChange={setDebugJson}
            onFinalizeTurn={() => void handleFinalizeTurn()}
            onFinalizeEventRound={() => void handleFinalizeEventRound()}
          />
        ) : null}
      </section>

      <div className="micro-readout" aria-hidden="true">
        <span>{userLabel(summary.primary_motive, projection.motiveLabel)}</span>
        <span>{text(summary.goal_frame, projection.motiveDetail)}</span>
      </div>
    </main>
  );
}

export default App;
