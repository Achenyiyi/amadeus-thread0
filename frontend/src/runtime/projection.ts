import type {
  AssistantTurnPayload,
  BackendEnvelopeFor,
  JsonRecord,
  JsonValue,
  SourceRef,
} from "../contracts/backend";
import type { RuntimeSession, TranscriptEntry } from "../data/mockBackend";

export type CompanionSurface = "room" | "memory" | "relationship" | "presence" | "growth" | "operator";

export interface ProjectionCard {
  id: string;
  label: string;
  title: string;
  body: string;
  tone?: "warm" | "cool" | "attention" | "quiet";
}

export interface PresenceReadout {
  label: string;
  value: string;
  detail: string;
}

export interface LockedCapability {
  id: string;
  label: string;
  reason: string;
}

export interface CompanionProjection {
  currentLine: string;
  emotionLabel: string;
  avatarExpression: "calm" | "warm" | "guarded" | "repair" | "thinking";
  sceneTone: "sunset" | "night" | "lab" | "quiet";
  liveStatus: string;
  liveHint: string;
  motiveLabel: string;
  motiveDetail: string;
  relationshipClimate: string;
  connectionReadout: string;
  memoryPulse: ProjectionCard | null;
  memoryCards: ProjectionCard[];
  relationshipCards: ProjectionCard[];
  presenceReadouts: PresenceReadout[];
  growthCards: ProjectionCard[];
  evidenceCount: number;
  sourceCards: ProjectionCard[];
  pendingApproval: JsonRecord | null;
  lockedCapabilities: LockedCapability[];
}

const lockedCapabilities: LockedCapability[] = [
  {
    id: "voice",
    label: "语音",
    reason: "等待后端 TTS/ASR session 契约",
  },
  {
    id: "video",
    label: "视频",
    reason: "live capture 当前保持关闭",
  },
  {
    id: "artifact",
    label: "图片",
    reason: "等待 artifact upload / approved inspection 契约",
  },
];

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asRecord(value: unknown): JsonRecord {
  return isRecord(value) ? value : {};
}

function asRecordArray(value: unknown): JsonRecord[] {
  return Array.isArray(value) ? value.filter(isRecord) : [];
}

function text(value: JsonValue | unknown, fallback = ""): string {
  if (typeof value === "string" && value.trim()) return value.trim();
  if (typeof value === "number" && Number.isFinite(value)) {
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }
  if (typeof value === "boolean") return value ? "yes" : "no";
  return fallback;
}

function numeric(value: unknown, fallback = 0): number {
  const number = typeof value === "number" ? value : Number(value);
  return Number.isFinite(number) ? number : fallback;
}

export function ratioLabel(value: unknown): string {
  const clamped = Math.max(0, Math.min(1, numeric(value, 0)));
  return `${Math.round(clamped * 100)}%`;
}

export function userLabel(value: unknown, fallback = "未知"): string {
  const raw = text(value, fallback);
  const key = raw.trim().toLowerCase().replace(/\s+/g, "_");
  const labels: Record<string, string> = {
    care: "关心",
    warm: "温和",
    calm: "平静",
    neutral: "平稳",
    guarded: "保持距离",
    repair_open: "愿意修复",
    repair: "修复中",
    active: "正在延续",
    open: "愿意靠近",
    warming: "正在变熟",
    trusted: "已经信任",
    warm_residue: "有温度的余波",
    guarded_residue: "仍有一点防备",
    repair_residue: "修复后的余波",
    gentle_recontact: "温和地重新靠近",
    preserve_self_rhythm: "保留自己的节律",
    protect_boundary: "先守住边界",
    own_rhythm: "自己的节律",
    self_rhythm_vs_contact: "自己的节奏和靠近之间的拉扯",
    relationship: "关系",
    commitment: "约定",
    unresolved_tension: "未说完的张力",
    relationship_timeline: "关系轨迹",
    source_ref: "来源",
    proposal: "提案等待中",
    awaiting_approval: "等待确认",
    approval_pending: "等待确认",
    blocked: "暂时受限",
    completed: "已完成",
    installed: "已具备",
    matched: "已匹配",
    active_skill: "正在使用",
  };

  return labels[key] ?? raw.replace(/_/g, " ");
}

function cardFromRecord(item: JsonRecord, index: number, fallbackLabel: string): ProjectionCard {
  const label = userLabel(item.status ?? item.kind ?? item.category ?? item.stance, fallbackLabel);
  const title = text(item.title ?? item.summary ?? item.after_summary ?? item.text, `${fallbackLabel} ${index + 1}`);
  const body = text(item.text ?? item.note ?? item.goal_frame ?? item.prompt_text ?? item.summary, title);
  return {
    id: text(item.id ?? item.target_id ?? item.agenda_id, `${fallbackLabel}-${index}`),
    label,
    title,
    body,
    tone: label.includes("张力") || label.includes("确认") ? "attention" : "warm",
  };
}

function collectMemoryCards(session: RuntimeSession, payload: AssistantTurnPayload): ProjectionCard[] {
  const worldline = session.worldline.payload;
  const reconsolidation = asRecord(payload.reconsolidation_snapshot);
  const focus = asRecordArray(payload.turn_summary?.worldline_focus_items);
  const commitments = asRecordArray(worldline.commitments);
  const tensions = asRecordArray(worldline.unresolved_tensions);
  const narratives = asRecordArray(worldline.semantic_self_narratives);
  const cards = [
    ...(text(reconsolidation.goal_frame) || text(reconsolidation.primary_motive)
      ? [
          {
            id: "reconsolidation",
            label: "刚刚留下",
            title: text(reconsolidation.goal_frame ?? reconsolidation.primary_motive, "这一轮对话留下了新的线索"),
            body: text(asRecord(reconsolidation.behavior_consequence).summary, "她把这次回应并入后续连续性。"),
            tone: "warm" as const,
          },
        ]
      : []),
    ...commitments.slice(0, 3).map((item, index) => cardFromRecord(item, index, "约定")),
    ...focus.slice(0, 3).map((item, index) => cardFromRecord(item, index, "关系轨迹")),
    ...tensions.slice(0, 2).map((item, index) => cardFromRecord(item, index, "未说完")),
    ...narratives.slice(0, 2).map((item, index) => cardFromRecord(item, index, "自我叙事")),
  ];

  return cards.slice(0, 9);
}

function collectRelationshipCards(session: RuntimeSession): ProjectionCard[] {
  const bond = session.bond.payload;
  const relationshipState = asRecord(bond.relationship_state);
  const bondState = asRecord(bond.bond_state);
  const timeline = asRecordArray(bond.relationship_timeline);
  const repair = asRecordArray(bond.conflict_repair);
  const counterpart = asRecordArray(bond.counterpart_assessment_preview ?? bond.counterpart_assessment_history);

  const lead: ProjectionCard = {
    id: "relationship-climate",
    label: userLabel(relationshipState.stage, "关系气候"),
    title: text(relationshipState.notes, "关系状态正在形成连续性"),
    body: `亲近 ${ratioLabel(relationshipState.affinity_score)}，信任 ${ratioLabel(
      bondState.trust ?? relationshipState.trust_score,
    )}，张力 ${ratioLabel(bondState.hurt ?? relationshipState.tension_load)}。`,
    tone: "quiet",
  };

  return [
    lead,
    ...repair.slice(0, 3).map((item, index) => cardFromRecord(item, index, "修复")),
    ...timeline.slice(0, 3).map((item, index) => cardFromRecord(item, index, "轨迹")),
    ...counterpart.slice(0, 3).map((item, index) => cardFromRecord(item, index, "她对你的理解")),
  ].slice(0, 9);
}

function collectGrowthCards(payload: AssistantTurnPayload): ProjectionCard[] {
  const skills = payload.skills;
  const active = Array.isArray(skills?.active) ? skills.active : [];
  const matched = Array.isArray(skills?.matched) ? skills.matched : [];
  const pendingSkill = asRecord(skills?.pending_approval);
  const dynamicRuntime = asRecord((skills as unknown as JsonRecord)?.dynamic_candidate_runtime);
  const embodied = asRecord(payload.embodied_interaction);
  const approvedRuntime = asRecord((payload as unknown as JsonRecord).approved_artifact_multimodal_runtime);
  const growth = asRecordArray((dynamicRuntime.lifecycle_events as unknown) ?? dynamicRuntime.events);

  const cards: ProjectionCard[] = [
    ...active.slice(0, 3).map((skill, index) => ({
      id: `active-${text(skill.skill_id, String(index))}`,
      label: "正在使用",
      title: text(skill.name ?? skill.skill_id, "能力"),
      body: text(skill.description ?? skill.skill_excerpt, "她可以把这项能力作为数字身体的一部分使用。"),
      tone: "warm" as const,
    })),
    ...matched.slice(0, 2).map((skill, index) => ({
      id: `matched-${text(skill.skill_id, String(index))}`,
      label: "已匹配",
      title: text(skill.name ?? skill.skill_id, "能力"),
      body: text(skill.description, "当前对话触发了这项能力。"),
      tone: "quiet" as const,
    })),
  ];

  if (text(pendingSkill.skill_id)) {
    cards.push({
      id: "pending-skill",
      label: "等待确认",
      title: text(pendingSkill.skill_id, "候选能力"),
      body: text(pendingSkill.verification_summary, "候选能力已经冻结，等待操作者确认。"),
      tone: "attention",
    });
  }

  growth.slice(0, 3).forEach((item, index) => {
    cards.push(cardFromRecord(item, index, "成长"));
  });

  if (Object.keys(approvedRuntime).length || Object.keys(embodied).length) {
    cards.push({
      id: "embodied",
      label: "具身记录",
      title: "她能把被批准的材料经验带回当前关系",
      body: text(
        asRecord(embodied.artifact_semantics).summary ??
          asRecord(approvedRuntime.multimodal_inspection_result).summary,
        "多模态与具身交互仍保持只读 readback，不会由前端擅自写入记忆。",
      ),
      tone: "cool",
    });
  }

  return cards.slice(0, 9);
}

function collectSourceCards(sources: SourceRef[]): ProjectionCard[] {
  return sources.slice(0, 6).map((source, index) => ({
    id: text(source.id, `source-${index}`),
    label: userLabel(source.tool_name, "来源"),
    title: text(source.title ?? source.query ?? source.url, `来源 ${index + 1}`),
    body: text(source.url ?? source.query, "这条来源由后端 envelope 提供。"),
    tone: "cool",
  }));
}

function avatarExpression(payload: AssistantTurnPayload): CompanionProjection["avatarExpression"] {
  const emotion = text(payload.emotion_label).toLowerCase();
  const motive = text(payload.behavior_action?.primary_motive ?? payload.behavior_plan?.primary_motive).toLowerCase();
  const pending = asRecord(payload.autonomy?.pending_approval);

  if (Object.keys(pending).length) return "thinking";
  if (motive.includes("repair") || emotion.includes("repair")) return "repair";
  if (motive.includes("boundary") || emotion.includes("guard")) return "guarded";
  if (emotion.includes("care") || emotion.includes("warm")) return "warm";
  return "calm";
}

function sceneTone(payload: AssistantTurnPayload): CompanionProjection["sceneTone"] {
  const weather = text(payload.turn_summary?.current_turn?.behavior_weather ?? payload.behavior_plan?.relationship_weather).toLowerCase();
  if (weather.includes("guard") || weather.includes("boundary")) return "night";
  if (weather.includes("repair")) return "lab";
  if (weather.includes("warm")) return "sunset";
  return "quiet";
}

function pendingApproval(payload: AssistantTurnPayload): JsonRecord | null {
  const pending = asRecord(payload.autonomy?.pending_approval);
  return Object.keys(pending).length ? pending : null;
}

function presenceReadouts(payload: AssistantTurnPayload): PresenceReadout[] {
  const current = payload.turn_summary?.current_turn ?? {};
  const appraisal = asRecord(payload.turn_appraisal);
  const action = payload.behavior_action ?? {};
  const plan = payload.behavior_plan ?? {};
  const body = asRecord(payload.digital_body_consequence);

  return [
    {
      label: "情绪",
      value: userLabel(payload.emotion_label, "平稳"),
      detail: userLabel(current.affect_surface ?? current.behavior_weather, "她保持可回应的状态。"),
    },
    {
      label: "动机",
      value: userLabel(action.primary_motive ?? plan.primary_motive ?? current.primary_motive, "回应"),
      detail: text(action.goal_frame ?? plan.goal_frame ?? current.goal_frame, "她正在把这一轮回应放进关系连续性里。"),
    },
    {
      label: "关系",
      value: userLabel(current.behavior_weather ?? plan.relationship_weather, "稳定"),
      detail: `信任 ${ratioLabel(current.trust)}，亲近 ${ratioLabel(current.closeness)}，受伤 ${ratioLabel(current.hurt)}。`,
    },
    {
      label: "边界",
      value: userLabel(appraisal.selfhood_scene ?? action.disclosure_posture, "对等"),
      detail: text(action.motive_tension ?? current.motive_tension, "她保留自己的节律，不把自己变成纯指令入口。"),
    },
    {
      label: "数字身体",
      value: userLabel(body.kind ?? current.digital_body_consequence_kind, "只读"),
      detail: text(body.summary ?? current.digital_body_consequence_summary, "当前没有额外的外部执行结果。"),
    },
  ];
}

export function currentPayload(entry: TranscriptEntry): AssistantTurnPayload {
  return entry.envelope.payload as AssistantTurnPayload;
}

export function createCompanionProjection(session: RuntimeSession, selectedEntry: TranscriptEntry): CompanionProjection {
  const payload = currentPayload(selectedEntry);
  const current = payload.turn_summary?.current_turn ?? {};
  const pending = pendingApproval(payload);
  const memoryCards = collectMemoryCards(session, payload);
  const relationshipCards = collectRelationshipCards(session);
  const growthCards = collectGrowthCards(payload);
  const sourceCards = collectSourceCards(payload.sources ?? session.sources ?? []);
  const motiveLabel = userLabel(payload.behavior_action?.primary_motive ?? payload.behavior_plan?.primary_motive ?? current.primary_motive, "回应");
  const status = pending ? "等待你的确认" : "在场";
  const relationshipClimate = userLabel(current.behavior_weather ?? session.bond.payload.relationship_state?.stage, "稳定");

  return {
    currentLine: text(payload.final_text, "她还没有留下新的回复。"),
    emotionLabel: userLabel(payload.emotion_label, "平稳"),
    avatarExpression: avatarExpression(payload),
    sceneTone: sceneTone(payload),
    liveStatus: status,
    liveHint: pending
      ? text(asRecord(pending.execution_preview).summary ?? pending.expected_effect, "后端已有待确认 action packet，前端只读展示。")
      : text(current.behavior_note ?? current.goal_frame ?? payload.behavior_plan?.goal_frame, "她把这一轮回应放进长期连续性。"),
    motiveLabel,
    motiveDetail: text(payload.behavior_action?.goal_frame ?? payload.behavior_plan?.goal_frame ?? current.goal_frame, "她正在斟酌如何回应你。"),
    relationshipClimate,
    connectionReadout: `${session.schemaVersion} / ${session.threadId}`,
    memoryPulse: memoryCards[0] ?? null,
    memoryCards,
    relationshipCards,
    presenceReadouts: presenceReadouts(payload),
    growthCards,
    evidenceCount: (payload.sources?.length ?? 0) + (payload.claim_links?.length ?? 0),
    sourceCards,
    pendingApproval: pending,
    lockedCapabilities,
  };
}

export function envelopeStamp(envelope: BackendEnvelopeFor<BackendEnvelopeFor<"assistant_turn">["kind"]> | TranscriptEntry): number {
  if ("envelope" in envelope) return envelope.envelope.generated_at;
  return envelope.generated_at;
}
