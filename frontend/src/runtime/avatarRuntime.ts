import type { CompanionProjection } from "./projection";

export type CompanionPhase =
  | "idle"
  | "composing"
  | "sending"
  | "awaiting_response"
  | "response_ready"
  | "displaying_line"
  | "memory_update_hint"
  | "listening"
  | "transcribing"
  | "speaking";

export const companionPhaseOptions: CompanionPhase[] = [
  "idle",
  "composing",
  "sending",
  "awaiting_response",
  "response_ready",
  "displaying_line",
  "memory_update_hint",
  "listening",
  "transcribing",
  "speaking",
];

export const avatarExpressionOptions: CompanionProjection["avatarExpression"][] = [
  "calm",
  "warm",
  "guarded",
  "repair",
  "thinking",
];

export const live2dMotionOptions = [
  "Idle:0",
  "Idle:1",
  "Idle:2",
  "TapBody:0",
  "TapBody:1",
  "TapBody:2",
  "TapBody:3",
  "TapBody:4",
] as const;

export interface CompanionPhaseCopy {
  label: string;
  detail: string;
}

export const companionPhaseCopy: Record<CompanionPhase, CompanionPhaseCopy> = {
  idle: {
    label: "PRESENCE IDLE",
    detail: "她保持在场，等待下一个完整回合。",
  },
  composing: {
    label: "USER COMPOSING",
    detail: "你的输入正在形成；还没有产生新的后端回合。",
  },
  sending: {
    label: "SENDING",
    detail: "消息正在进入 Amadeus-K 后端。",
  },
  awaiting_response: {
    label: "AWAITING COMPLETE TURN",
    detail: "等待 backend.v1 返回完整 assistant_turn，而不是前端伪造流式文本。",
  },
  response_ready: {
    label: "TURN READY",
    detail: "新的完整回合已经抵达，正在接入终端房间。",
  },
  displaying_line: {
    label: "DISPLAYING LINE",
    detail: "正在显现后端给出的回复文本。",
  },
  memory_update_hint: {
    label: "CONTINUITY READBACK",
    detail: "正在展开这一回合带回的连续性线索。",
  },
  listening: {
    label: "LISTENING",
    detail: "麦克风由你主动开启；音频只在当前桌面通话会话内提交。",
  },
  transcribing: {
    label: "TRANSCRIBING",
    detail: "音频片段正在交给后端媒体契约处理，结果仍会进入 canonical turn loop。",
  },
  speaking: {
    label: "SPEAKING",
    detail: "正在播放后端回复或保持文字降级，不由前端生成新语义。",
  },
};

export type AvatarRendererKind = "css_placeholder" | "live2d_ready" | "vrm_ready" | "sprite_sequence_ready";

export interface AvatarAssetManifest {
  id: string;
  label: string;
  renderer: AvatarRendererKind;
  source: string;
  expressions: Record<string, string>;
  motions: Record<string, string>;
  blendShapes: Record<string, string>;
  spriteSequences: Record<string, string>;
}

export interface AvatarRuntimeState {
  renderer: AvatarRendererKind;
  manifest: AvatarAssetManifest;
  expression: CompanionProjection["avatarExpression"];
  sceneTone: CompanionProjection["sceneTone"];
  phase: CompanionPhase;
  posture: "resting" | "listening" | "transmitting" | "receiving" | "speaking" | "reconsolidating";
  gaze: "toward_user" | "down_to_console" | "side_glance" | "soft_focus";
  motion: "idle_breathe" | "attentive_breathe" | "sync_pulse" | "arrival_focus" | "line_delivery" | "memory_afterglow";
  moodClass: string;
  expressionClass: string;
  phaseClass: string;
  placement: AvatarRuntimePlacement;
  runtimeRevision: number;
  dataBindings: {
    live2dExpression: string;
    live2dMotion: string;
    live2dMotionTarget: string;
    vrmBlendShape: string;
    spriteSequence: string;
  };
}

export interface AvatarRuntimePlacement {
  scaleMultiplier: number;
  offsetX: number;
  offsetY: number;
}

export interface AvatarRuntimeOverride {
  expression?: CompanionProjection["avatarExpression"];
  phase?: CompanionPhase;
  live2dMotionTarget?: string;
  placement?: Partial<AvatarRuntimePlacement>;
  runtimeRevision?: number;
}

export const defaultAvatarPlacement: AvatarRuntimePlacement = {
  scaleMultiplier: 1,
  offsetX: 0,
  offsetY: 0,
};

export const cssPlaceholderManifest: AvatarAssetManifest = {
  id: "amadeus-css-placeholder",
  label: "CSS Placeholder Avatar",
  renderer: "css_placeholder",
  source: "frontend-css",
  expressions: {
    calm: "expression-calm",
    soft_smile: "expression-warm",
    guarded: "expression-guarded",
    repair_open: "expression-repair",
    thinking: "expression-thinking",
  },
  motions: {
    idle_breathe: "motion-idle_breathe",
    listen_shift: "motion-attentive_breathe",
    terminal_sync: "motion-sync_pulse",
    await_turn: "motion-sync_pulse",
    turn_arrival: "motion-arrival_focus",
    speak_line: "motion-line_delivery",
    memory_afterglow: "motion-memory_afterglow",
  },
  blendShapes: {
    neutral: "expression-calm",
    joy_soft: "expression-warm",
    serious: "expression-guarded",
    concern: "expression-repair",
    look_down: "expression-thinking",
  },
  spriteSequences: {
    idle_loop: "motion-idle_breathe",
    listen_loop: "motion-attentive_breathe",
    sync_loop: "motion-sync_pulse",
    await_loop: "motion-sync_pulse",
    turn_arrival: "motion-arrival_focus",
    speak_line: "motion-line_delivery",
    memory_afterglow: "motion-memory_afterglow",
  },
};

export const live2dManifestTemplate: AvatarAssetManifest = {
  id: "natori-live2d-sample",
  label: "Natori Live2D Sample",
  renderer: "live2d_ready",
  source: "/assets/avatars/live2d/natori/Natori.model3.json",
  expressions: {
    calm: "Normal",
    soft_smile: "Smile",
    guarded: "Angry",
    repair_open: "Sad",
    thinking: "Surprised",
  },
  motions: {
    idle_breathe: "Idle:0",
    listen_shift: "Idle:1",
    terminal_sync: "Idle:2",
    await_turn: "TapBody:0",
    turn_arrival: "TapBody:1",
    speak_line: "TapBody:2",
    memory_afterglow: "TapBody:3",
  },
  blendShapes: {},
  spriteSequences: {},
};

export const vrmManifestTemplate: AvatarAssetManifest = {
  id: "amadeus-vrm-template",
  label: "VRM Manifest Template",
  renderer: "vrm_ready",
  source: "/assets/avatars/amadeus/vrm/amadeus.vrm",
  expressions: {},
  motions: {
    idle_breathe: "animation/idle_breathe.vrma",
    listen_shift: "animation/listen_shift.vrma",
    terminal_sync: "animation/terminal_sync.vrma",
    await_turn: "animation/await_turn.vrma",
    turn_arrival: "animation/turn_arrival.vrma",
    speak_line: "animation/speak_line.vrma",
    memory_afterglow: "animation/memory_afterglow.vrma",
  },
  blendShapes: {
    neutral: "neutral",
    joy_soft: "happy",
    serious: "serious",
    concern: "sad",
    look_down: "neutral",
  },
  spriteSequences: {},
};

export const spriteSequenceManifestTemplate: AvatarAssetManifest = {
  id: "amadeus-sprite-sequence-template",
  label: "Sprite Sequence Manifest Template",
  renderer: "sprite_sequence_ready",
  source: "/assets/avatars/amadeus/sprites",
  expressions: {},
  motions: {},
  blendShapes: {},
  spriteSequences: {
    idle_loop: "idle/manifest.json",
    listen_loop: "listen/manifest.json",
    sync_loop: "sync/manifest.json",
    await_loop: "await/manifest.json",
    turn_arrival: "arrival/manifest.json",
    speak_line: "speak/manifest.json",
    memory_afterglow: "memory/manifest.json",
  },
};

const expressionBindings: Record<
  CompanionProjection["avatarExpression"],
  {
    live2dExpression: string;
    vrmBlendShape: string;
  }
> = {
  calm: {
    live2dExpression: "calm",
    vrmBlendShape: "neutral",
  },
  warm: {
    live2dExpression: "soft_smile",
    vrmBlendShape: "joy_soft",
  },
  guarded: {
    live2dExpression: "guarded",
    vrmBlendShape: "serious",
  },
  repair: {
    live2dExpression: "repair_open",
    vrmBlendShape: "concern",
  },
  thinking: {
    live2dExpression: "thinking",
    vrmBlendShape: "look_down",
  },
};

const phaseMotionBindings: Record<
  CompanionPhase,
  {
    posture: AvatarRuntimeState["posture"];
    gaze: AvatarRuntimeState["gaze"];
    motion: AvatarRuntimeState["motion"];
    live2dMotion: string;
    spriteSequence: string;
  }
> = {
  idle: {
    posture: "resting",
    gaze: "toward_user",
    motion: "idle_breathe",
    live2dMotion: "idle_breathe",
    spriteSequence: "idle_loop",
  },
  composing: {
    posture: "listening",
    gaze: "soft_focus",
    motion: "attentive_breathe",
    live2dMotion: "listen_shift",
    spriteSequence: "listen_loop",
  },
  sending: {
    posture: "transmitting",
    gaze: "down_to_console",
    motion: "sync_pulse",
    live2dMotion: "terminal_sync",
    spriteSequence: "sync_loop",
  },
  awaiting_response: {
    posture: "receiving",
    gaze: "down_to_console",
    motion: "sync_pulse",
    live2dMotion: "await_turn",
    spriteSequence: "await_loop",
  },
  response_ready: {
    posture: "speaking",
    gaze: "toward_user",
    motion: "arrival_focus",
    live2dMotion: "turn_arrival",
    spriteSequence: "turn_arrival",
  },
  displaying_line: {
    posture: "speaking",
    gaze: "toward_user",
    motion: "line_delivery",
    live2dMotion: "speak_line",
    spriteSequence: "speak_line",
  },
  memory_update_hint: {
    posture: "reconsolidating",
    gaze: "side_glance",
    motion: "memory_afterglow",
    live2dMotion: "memory_afterglow",
    spriteSequence: "memory_afterglow",
  },
  listening: {
    posture: "listening",
    gaze: "toward_user",
    motion: "attentive_breathe",
    live2dMotion: "listen_shift",
    spriteSequence: "listen_loop",
  },
  transcribing: {
    posture: "receiving",
    gaze: "down_to_console",
    motion: "sync_pulse",
    live2dMotion: "await_turn",
    spriteSequence: "await_loop",
  },
  speaking: {
    posture: "speaking",
    gaze: "toward_user",
    motion: "line_delivery",
    live2dMotion: "speak_line",
    spriteSequence: "speak_line",
  },
};

export function createAvatarRuntimeState(
  projection: CompanionProjection,
  phase: CompanionPhase,
  override: AvatarRuntimeOverride = {},
): AvatarRuntimeState {
  const effectiveExpression = override.expression ?? projection.avatarExpression;
  const effectivePhase = override.phase ?? phase;
  const expression = expressionBindings[effectiveExpression];
  const motion = phaseMotionBindings[effectivePhase];
  const placement = {
    ...defaultAvatarPlacement,
    ...override.placement,
  };

  return {
    renderer: "live2d_ready",
    manifest: live2dManifestTemplate,
    expression: effectiveExpression,
    sceneTone: projection.sceneTone,
    phase: effectivePhase,
    posture: motion.posture,
    gaze: motion.gaze,
    motion: motion.motion,
    moodClass: `tone-${projection.sceneTone}`,
    expressionClass: `expression-${effectiveExpression}`,
    phaseClass: `phase-${effectivePhase}`,
    placement,
    runtimeRevision: override.runtimeRevision ?? 0,
    dataBindings: {
      live2dExpression: expression.live2dExpression,
      live2dMotion: motion.live2dMotion,
      live2dMotionTarget: override.live2dMotionTarget ?? "",
      vrmBlendShape: expression.vrmBlendShape,
      spriteSequence: motion.spriteSequence,
    },
  };
}
