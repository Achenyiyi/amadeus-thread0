import { useEffect, useMemo, useState, type ReactNode } from "react";
import { MetricBar } from "./components/MetricBar";
import { SignalConstellation, type SignalMetric } from "./components/SignalConstellation";
import { InspectorTabs, type InspectorTabSpec } from "./components/InspectorTabs";
import type { BehaviorQueueItem, JsonRecord, SourceRef } from "./contracts/backend";
import type { MockSession, TranscriptEntry } from "./data/mockBackend";
import { createBackendClient } from "./runtime/backendClient";
import "./styles.css";

type InspectorTabId = "persona" | "worldline" | "bond" | "sources";
type FocusLens = "relation" | "behavior" | "continuity";
type Tone = "blue" | "signal" | "slate";

interface LensStat {
  label: string;
  value: string;
  detail: string;
  tone: Tone;
}

interface LensCopy {
  eyebrow: string;
  title: string;
  body: string;
  callout: string;
  stats: LensStat[];
}

interface TimelineEntry {
  id: string;
  kind: string;
  title: string;
  summary: string;
  meta: string;
  tone: Tone;
}

const stampFormatter = new Intl.DateTimeFormat(undefined, {
  hour: "2-digit",
  minute: "2-digit",
  month: "short",
  day: "2-digit",
});

const focusLenses: Array<{ id: FocusLens; label: string; description: string }> = [
  {
    id: "relation",
    label: "Relation",
    description: "Counterpart judgment, trust, and distance.",
  },
  {
    id: "behavior",
    label: "Behavior",
    description: "Final packet, motive, and response shape.",
  },
  {
    id: "continuity",
    label: "Continuity",
    description: "Memory, narrative traces, and delayed follow-through.",
  },
];

function formatStamp(epochSeconds: number) {
  return stampFormatter.format(new Date(epochSeconds * 1000));
}

function titleCase(value: string) {
  return value.replace(/_/g, " ").replace(/\b\w/g, (part) => part.toUpperCase());
}

function shortValue(value: unknown) {
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  if (typeof value === "string") {
    return value;
  }
  return JSON.stringify(value);
}

function formatPercent(value: number | undefined) {
  if (!Number.isFinite(value)) {
    return "0%";
  }
  return `${Math.round((value ?? 0) * 100)}%`;
}

function toRecordEntries(record: JsonRecord) {
  return Object.entries(record).filter(([, value]) => value !== null && value !== undefined && value !== "");
}

function timelineTone(kind: string): Tone {
  switch (kind) {
    case "Commitment":
    case "Counterpart Read":
      return "blue";
    case "Repair":
    case "Tension":
      return "signal";
    default:
      return "slate";
  }
}

function RecordGrid({ record }: { record: JsonRecord }) {
  const entries = toRecordEntries(record);

  if (!entries.length) {
    return <p className="empty-state">No packet fields available.</p>;
  }

  return (
    <div className="record-grid">
      {entries.map(([key, value]) => (
        <div key={key} className="record-grid__item">
          <span className="record-grid__label">{titleCase(key)}</span>
          <span className="record-grid__value">{shortValue(value)}</span>
        </div>
      ))}
    </div>
  );
}

function DetailCard({
  title,
  eyebrow,
  children,
}: {
  title: string;
  eyebrow?: string;
  children: ReactNode;
}) {
  return (
    <section className="detail-card">
      {eyebrow ? <p className="detail-card__eyebrow">{eyebrow}</p> : null}
      <h3 className="detail-card__title">{title}</h3>
      {children}
    </section>
  );
}

function JsonDump({ value, label }: { value: unknown; label: string }) {
  return (
    <details className="json-dump">
      <summary>{label}</summary>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}

function QueueList({ items }: { items: BehaviorQueueItem[] }) {
  if (!items.length) {
    return <p className="empty-state">No queued proactive items.</p>;
  }

  return (
    <div className="stack-list">
      {items.map((item, index) => (
        <article key={item.agenda_id ?? `${item.kind}-${index}`} className="stack-item">
          <div className="stack-item__topline">
            <strong>{titleCase(item.kind ?? "pending item")}</strong>
            <span>{item.status ?? "pending"}</span>
          </div>
          <p>{item.note ?? "No note attached."}</p>
          <div className="chip-row">
            {item.target ? <span className="chip chip--quiet">Target {item.target}</span> : null}
            {typeof item.scheduled_after_min === "number" ? (
              <span className="chip chip--quiet">T+{item.scheduled_after_min}m</span>
            ) : null}
            {item.relationship_weather ? (
              <span className="chip chip--quiet">{item.relationship_weather}</span>
            ) : null}
          </div>
        </article>
      ))}
    </div>
  );
}

function SourcesList({ sources }: { sources: SourceRef[] }) {
  if (!sources.length) {
    return <p className="empty-state">No source refs on this turn.</p>;
  }

  return (
    <div className="stack-list">
      {sources.map((source, index) => (
        <article key={`${source.id ?? index}`} className="stack-item stack-item--source">
          <div className="stack-item__topline">
            <strong>{source.title ?? `Source ${index + 1}`}</strong>
            <span>{source.tool_name ?? "tool"}</span>
          </div>
          {source.query ? <p>{source.query}</p> : null}
          {source.url ? (
            <a href={source.url} target="_blank" rel="noreferrer" className="inline-link">
              {source.url}
            </a>
          ) : (
            <span className="inline-meta">No URL on record.</span>
          )}
        </article>
      ))}
    </div>
  );
}

function SpotlightStat({ stat }: { stat: LensStat }) {
  return (
    <article className={`spotlight-stat spotlight-stat--${stat.tone}`}>
      <p className="spotlight-stat__label">{stat.label}</p>
      <strong className="spotlight-stat__value">{stat.value}</strong>
      <p className="spotlight-stat__detail">{stat.detail}</p>
    </article>
  );
}

function StorylineCard({ item }: { item: TimelineEntry }) {
  return (
    <article className={`storyline-card storyline-card--${item.tone}`} role="listitem">
      <div className="storyline-card__topline">
        <span className={`chip chip--${item.tone === "slate" ? "quiet" : item.tone}`}>{item.kind}</span>
        <span className="inline-meta">{item.meta}</span>
      </div>
      <h3>{item.title}</h3>
      <p>{item.summary}</p>
    </article>
  );
}

function TranscriptCard({
  entry,
  selected,
  onSelect,
}: {
  entry: TranscriptEntry;
  selected: boolean;
  onSelect: () => void;
}) {
  const payload = entry.envelope.payload;
  const isAssistant = entry.envelope.kind === "assistant_turn";

  return (
    <button
      type="button"
      className={`transcript-card${selected ? " is-selected" : ""}`}
      onClick={onSelect}
      aria-pressed={selected}
      aria-label={`${entry.envelope.kind} at ${formatStamp(entry.envelope.generated_at)}`}
    >
      <div className="transcript-card__topline">
        <span className={`chip ${isAssistant ? "chip--accent" : "chip--signal"}`}>{entry.envelope.kind}</span>
        <span className="inline-meta">{formatStamp(entry.envelope.generated_at)}</span>
      </div>
      <p className="transcript-card__quote">{payload.final_text}</p>
      <p className="transcript-card__meta">{payload.behavior_plan.goal_frame ?? "No goal frame attached."}</p>
      <div className="chip-row">
        <span className="chip chip--quiet">Emotion {payload.emotion_label}</span>
        {payload.behavior_action.primary_motive ? (
          <span className="chip chip--quiet">Motive {payload.behavior_action.primary_motive}</span>
        ) : null}
        {payload.behavior_plan.kind ? <span className="chip chip--quiet">Plan {payload.behavior_plan.kind}</span> : null}
      </div>
    </button>
  );
}
function App() {
  const [session, setSession] = useState<MockSession | null>(null);
  const [selectedTurnId, setSelectedTurnId] = useState<string>("");
  const [activeTab, setActiveTab] = useState<InspectorTabId>("persona");
  const [activeLens, setActiveLens] = useState<FocusLens>("relation");

  useEffect(() => {
    let cancelled = false;
    const client = createBackendClient();

    client.loadSessionSnapshot().then((data) => {
      if (cancelled) {
        return;
      }

      setSession(data);
      setSelectedTurnId(data.transcript[0]?.id ?? "");
    });

    return () => {
      cancelled = true;
    };
  }, []);

  const selectedEntry = useMemo(() => {
    if (!session) {
      return null;
    }
    return session.transcript.find((entry) => entry.id === selectedTurnId) ?? session.transcript[0] ?? null;
  }, [selectedTurnId, session]);

  if (!session || !selectedEntry) {
    return (
      <div className="loading-shell">
        <div className="loading-shell__panel">
          <p className="detail-card__eyebrow">AMADEUS OBSERVATORY</p>
          <h1>Loading mock continuity shell</h1>
          <p>Preparing transcript, worldline, and relational envelopes for the design surface.</p>
        </div>
      </div>
    );
  }

  const selectedPayload = selectedEntry.envelope.payload;
  const selectedSummary = selectedPayload.turn_summary;
  const relationshipState = session.bond.payload.relationship_state as {
    stage: string;
    notes: string;
    affinity_score: number;
    trust_score: number;
  };
  const bondState = session.bond.payload.bond_state as {
    trust: number;
    closeness: number;
    hurt: number;
  };
  const continuity = session.persona.payload.evolution_summary.continuity_vector;
  const worldDynamics = session.persona.payload.evolution_summary.world_dynamics;
  const currentTurn = selectedSummary.current_turn;
  const counterpartPreview = (session.bond.payload.counterpart_assessment_preview[0] ?? {}) as {
    summary?: string;
    scene?: string;
    respect_level?: number;
    reciprocity?: number;
    boundary_pressure?: number;
    reliability_read?: number;
  };
  const proactivePreview = (session.bond.payload.proactive_continuity_preview[0] ?? {}) as {
    summary?: string;
    own_rhythm_bias?: number;
    carryover_strength?: number;
    recontact_cooldown?: number;
    hold_count?: number;
  };
  const latestCommitment = (session.worldline.payload.commitments[0] ?? {}) as {
    text?: string;
    status?: string;
  };
  const latestNarrative = (session.worldline.payload.semantic_self_narratives[0] ?? {}) as {
    text?: string;
    category?: string;
  };

  const lensCopy: Record<FocusLens, LensCopy> = {
    relation: {
      eyebrow: "counterpart judgment",
      title: "Peer tension, trust, and distance stay visible in the same frame.",
      body:
        counterpartPreview.summary ??
        "The interface keeps mutual reading visible instead of flattening the scene into generic friendliness.",
      callout: relationshipState.notes,
      stats: [
        {
          label: "Respect",
          value: formatPercent(counterpartPreview.respect_level),
          detail: `Scene ${counterpartPreview.scene ?? "unknown"}`,
          tone: "blue",
        },
        {
          label: "Reciprocity",
          value: formatPercent(counterpartPreview.reciprocity),
          detail: "Mutual movement instead of command-response.",
          tone: "signal",
        },
        {
          label: "Boundary pressure",
          value: formatPercent(counterpartPreview.boundary_pressure),
          detail: "Low pressure keeps the opening real.",
          tone: "slate",
        },
      ],
    },
    behavior: {
      eyebrow: "final behavior packet",
      title: "One selected turn can read like a scene, a motive packet, and a consequence trace at once.",
      body: selectedPayload.behavior_plan.goal_frame ?? "The current packet exposes the reason behind the response.",
      callout: selectedSummary.current_turn.behavior_consequence_summary,
      stats: [
        {
          label: "Interaction mode",
          value: titleCase(selectedPayload.behavior_action.interaction_mode ?? "unknown"),
          detail: `Action ${selectedPayload.behavior_action.action_target ?? "none"}`,
          tone: "blue",
        },
        {
          label: "Primary motive",
          value: titleCase(selectedPayload.behavior_action.primary_motive ?? "unset"),
          detail: titleCase(selectedPayload.behavior_action.motive_tension ?? "no tension"),
          tone: "signal",
        },
        {
          label: "Carryover",
          value: formatPercent(Number(selectedPayload.interaction_carryover.strength ?? 0)),
          detail: titleCase(String(selectedPayload.interaction_carryover.carryover_mode ?? "none")),
          tone: "slate",
        },
      ],
    },
    continuity: {
      eyebrow: "worldline residue",
      title: "Memory is not a sidebar here. It shapes what survives the current scene.",
      body:
        latestNarrative.text ??
        selectedSummary.worldline_focus_preview[0] ??
        "The interface keeps narrative and behavioral residue in view.",
      callout: proactivePreview.summary ?? "A queued continuity trace remains available for later turns.",
      stats: [
        {
          label: "Commitment",
          value: titleCase(latestCommitment.status ?? "open"),
          detail: latestCommitment.text ?? "No active commitment recorded.",
          tone: "blue",
        },
        {
          label: "Own rhythm bias",
          value: formatPercent(proactivePreview.own_rhythm_bias),
          detail: `Hold count ${String(proactivePreview.hold_count ?? 0)}`,
          tone: "signal",
        },
        {
          label: "Recontact cooldown",
          value: formatPercent(proactivePreview.recontact_cooldown),
          detail: "Continuity can wait instead of forcing itself forward.",
          tone: "slate",
        },
      ],
    },
  };

  const continuityNotes = [
    selectedSummary.worldline_focus_preview[0],
    selectedSummary.semantic_continuity.summary_lines[0],
    selectedSummary.identity_continuity.identity_lines[0],
  ].filter(Boolean) as string[];

  const signalMetrics: SignalMetric[] = [
    { label: "Trust", value: bondState.trust, tone: "blue" },
    { label: "Closeness", value: bondState.closeness, tone: "signal" },
    { label: "Bond depth", value: worldDynamics.bond_depth, tone: "blue" },
    { label: "Agency", value: worldDynamics.agency_load, tone: "slate" },
    { label: "Presence", value: continuity.presence.semantic, tone: "blue" },
    { label: "Rhythm", value: continuity.rhythm.world, tone: "signal" },
  ];
  const signalCore =
    signalMetrics.reduce((total, metric) => total + metric.value, 0) / Math.max(signalMetrics.length, 1);

  const storyline = useMemo<TimelineEntry[]>(() => {
    const eventEntries = session.worldline.payload.worldline_events.map((item, index) => ({
      id: `event-${String(item.id ?? index)}`,
      kind: "Worldline",
      title: "Recorded event",
      summary: String(item.summary ?? "No event summary."),
      meta: formatStamp(Number(item.created_at ?? selectedEntry.envelope.generated_at)),
      tone: timelineTone("Worldline"),
    }));
    const commitmentEntries = session.worldline.payload.commitments.map((item, index) => ({
      id: `commitment-${String(item.id ?? index)}`,
      kind: "Commitment",
      title: String(item.status ?? "Open commitment"),
      summary: String(item.text ?? item.summary ?? "No commitment text."),
      meta: "Long horizon",
      tone: timelineTone("Commitment"),
    }));
    const repairEntries = session.worldline.payload.conflict_repair.map((item, index) => ({
      id: `repair-${String(item.id ?? index)}`,
      kind: "Repair",
      title: "Conflict repair",
      summary: String(item.summary ?? "No repair summary."),
      meta: "Recovered",
      tone: timelineTone("Repair"),
    }));
    const tensionEntries = session.worldline.payload.unresolved_tensions.map((item, index) => ({
      id: `tension-${String(item.id ?? index)}`,
      kind: "Tension",
      title: "Unresolved residue",
      summary: String(item.summary ?? "No unresolved tension summary."),
      meta: "Still active",
      tone: timelineTone("Tension"),
    }));
    const assessmentEntries = session.worldline.payload.counterpart_assessment_preview.slice(0, 1).map((item, index) => ({
      id: `assessment-${String(item.id ?? index)}`,
      kind: "Counterpart Read",
      title: String(item.scene ?? "relationship scene"),
      summary: String(item.summary ?? "No assessment summary."),
      meta: `Respect ${formatPercent(Number(item.respect_level ?? 0))}`,
      tone: timelineTone("Counterpart Read"),
    }));
    const continuityEntries = session.worldline.payload.proactive_continuity_preview.slice(0, 1).map((item, index) => ({
      id: `continuity-${String(item.id ?? index)}`,
      kind: "Own Rhythm",
      title: String(item.kind ?? "continuity trace"),
      summary: String(item.summary ?? "No continuity summary."),
      meta: `Bias ${formatPercent(Number(item.own_rhythm_bias ?? 0))}`,
      tone: timelineTone("Own Rhythm"),
    }));

    return [
      ...eventEntries,
      ...commitmentEntries,
      ...repairEntries,
      ...tensionEntries,
      ...assessmentEntries,
      ...continuityEntries,
    ].slice(0, 8);
  }, [selectedEntry.envelope.generated_at, session]);
  const tabs: InspectorTabSpec<InspectorTabId>[] = [
    {
      id: "persona",
      label: "Persona",
      content: (
        <div className="panel-stack">
          <DetailCard title="Current stance" eyebrow="Fixed core, evolving state">
            <p className="support-copy">{relationshipState.notes}</p>
            <div className="chip-row">
              <span className="chip chip--accent">Stage {relationshipState.stage}</span>
              <span className="chip chip--quiet">
                Affinity {Math.round(relationshipState.affinity_score * 100)}%
              </span>
              <span className="chip chip--quiet">Trust {Math.round(relationshipState.trust_score * 100)}%</span>
            </div>
          </DetailCard>

          <DetailCard title="Continuity vector" eyebrow="Semantic + world traces">
            <div className="metric-grid">
              <MetricBar label="Presence semantic" value={continuity.presence.semantic} tone="blue" />
              <MetricBar label="Presence world" value={continuity.presence.world} tone="slate" />
              <MetricBar label="Ambient semantic" value={continuity.ambient.semantic} tone="blue" />
              <MetricBar label="Ambient world" value={continuity.ambient.world} tone="slate" />
              <MetricBar label="Rhythm semantic" value={continuity.rhythm.semantic} tone="signal" />
              <MetricBar label="Rhythm world" value={continuity.rhythm.world} tone="signal" />
            </div>
          </DetailCard>

          <DetailCard title="World dynamics" eyebrow="Appraisal pressure map">
            <div className="metric-grid">
              <MetricBar label="Bond depth" value={worldDynamics.bond_depth} tone="blue" />
              <MetricBar label="Selfhood load" value={worldDynamics.selfhood_load} tone="signal" />
              <MetricBar label="Agency load" value={worldDynamics.agency_load} tone="signal" />
              <MetricBar label="Memory gravity" value={worldDynamics.memory_gravity} tone="slate" />
              <MetricBar label="Companionship pull" value={worldDynamics.companionship_pull} tone="blue" />
              <MetricBar label="Task pull" value={worldDynamics.task_pull} tone="slate" />
            </div>
          </DetailCard>

          <DetailCard title="Identity continuity" eyebrow="Long-horizon self narrative">
            <ul className="bullet-list">
              {session.persona.payload.evolution_summary.identity_continuity.identity_lines.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            <div className="stack-list compact-stack">
              {session.persona.payload.evolution_summary.identity_continuity.long_term_self_narratives.map((item) => (
                <article key={`${item.category}-${item.text}`} className="stack-item">
                  <div className="stack-item__topline">
                    <strong>{titleCase(item.category)}</strong>
                    <span>{item.horizon_tag}</span>
                  </div>
                  <p>{item.text}</p>
                </article>
              ))}
            </div>
          </DetailCard>

          <DetailCard title="Behavior packet" eyebrow="Final action + queued continuity">
            <RecordGrid record={session.persona.payload.behavior_action} />
            <QueueList items={session.persona.payload.behavior_queue_summary} />
          </DetailCard>

          <JsonDump value={session.persona.payload} label="Raw persona payload" />
        </div>
      ),
    },
    {
      id: "worldline",
      label: "Worldline",
      count: session.worldline.payload.worldline_events.length,
      content: (
        <div className="panel-stack">
          <DetailCard title="Worldline focus" eyebrow="Continuity replay">
            <ul className="bullet-list">
              {session.worldline.payload.worldline_summary.worldline_focus_preview.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </DetailCard>

          <DetailCard title="Events and commitments" eyebrow="What should remain true later">
            <div className="stack-list compact-stack">
              {session.worldline.payload.worldline_events.map((item) => (
                <article key={`event-${String(item.id)}`} className="stack-item">
                  <div className="stack-item__topline">
                    <strong>Worldline event</strong>
                    <span>{formatStamp(Number(item.created_at ?? selectedEntry.envelope.generated_at))}</span>
                  </div>
                  <p>{String(item.summary ?? "No summary")}</p>
                </article>
              ))}
              {session.worldline.payload.commitments.map((item) => (
                <article key={`commit-${String(item.id)}`} className="stack-item">
                  <div className="stack-item__topline">
                    <strong>Commitment</strong>
                    <span>{String(item.status ?? "open")}</span>
                  </div>
                  <p>{String(item.text ?? item.summary ?? "No commitment text")}</p>
                </article>
              ))}
            </div>
          </DetailCard>

          <DetailCard title="Repair and unresolved tension" eyebrow="Relational residue">
            <div className="stack-list compact-stack">
              {session.worldline.payload.conflict_repair.map((item) => (
                <article key={`repair-${String(item.id)}`} className="stack-item">
                  <div className="stack-item__topline">
                    <strong>Conflict repair</strong>
                  </div>
                  <p>{String(item.summary ?? "No repair summary")}</p>
                </article>
              ))}
              {session.worldline.payload.unresolved_tensions.map((item) => (
                <article key={`tension-${String(item.id)}`} className="stack-item">
                  <div className="stack-item__topline">
                    <strong>Unresolved tension</strong>
                  </div>
                  <p>{String(item.summary ?? "No tension summary")}</p>
                </article>
              ))}
            </div>
          </DetailCard>

          <DetailCard title="Self narratives" eyebrow="Reactivated semantic traces">
            <div className="stack-list compact-stack">
              {session.worldline.payload.semantic_self_narratives.map((item) => (
                <article key={`narrative-${String(item.id)}`} className="stack-item">
                  <div className="stack-item__topline">
                    <strong>{titleCase(String(item.category ?? "narrative"))}</strong>
                  </div>
                  <p>{String(item.text ?? "No narrative text")}</p>
                </article>
              ))}
            </div>
          </DetailCard>

          <JsonDump value={session.worldline.payload} label="Raw worldline payload" />
        </div>
      ),
    },
    {
      id: "bond",
      label: "Bond",
      content: (
        <div className="panel-stack">
          <DetailCard title="Relationship state" eyebrow="Derived bond surface">
            <div className="metric-grid">
              <MetricBar label="Trust" value={Number(bondState.trust ?? 0)} tone="blue" />
              <MetricBar label="Closeness" value={Number(bondState.closeness ?? 0)} tone="signal" />
              <MetricBar label="Hurt" value={Number(bondState.hurt ?? 0)} tone="slate" />
            </div>
            <p className="support-copy">{relationshipState.notes}</p>
          </DetailCard>

          <DetailCard title="Timeline deltas" eyebrow="How the relation moved">
            <div className="stack-list compact-stack">
              {session.bond.payload.relationship_timeline.map((item) => (
                <article key={`timeline-${String(item.id)}`} className="stack-item">
                  <div className="stack-item__topline">
                    <strong>{String(item.summary ?? "Timeline event")}</strong>
                    <span>
                      dA {shortValue(item.affinity_delta)} / dT {shortValue(item.trust_delta)}
                    </span>
                  </div>
                </article>
              ))}
            </div>
          </DetailCard>

          <DetailCard title="Counterpart assessment" eyebrow="How the system reads Okabe now">
            <div className="stack-list compact-stack">
              {session.bond.payload.counterpart_assessment_preview.map((item) => (
                <article key={`assessment-${String(item.id)}`} className="stack-item">
                  <div className="stack-item__topline">
                    <strong>{String(item.summary ?? "Assessment")}</strong>
                    <span>{String(item.scene ?? "scene")}</span>
                  </div>
                  <div className="chip-row">
                    <span className="chip chip--quiet">
                      Respect {Math.round(Number(item.respect_level ?? 0) * 100)}%
                    </span>
                    <span className="chip chip--quiet">
                      Reciprocity {Math.round(Number(item.reciprocity ?? 0) * 100)}%
                    </span>
                    <span className="chip chip--quiet">
                      Boundary {Math.round(Number(item.boundary_pressure ?? 0) * 100)}%
                    </span>
                  </div>
                </article>
              ))}
            </div>
          </DetailCard>

          <DetailCard title="Proactive continuity" eyebrow="Own-rhythm traces">
            <div className="stack-list compact-stack">
              {session.bond.payload.proactive_continuity_preview.map((item) => (
                <article key={`continuity-${String(item.id)}`} className="stack-item">
                  <div className="stack-item__topline">
                    <strong>{String(item.kind ?? "continuity trace")}</strong>
                    <span>{String(item.trace_family ?? "trace")}</span>
                  </div>
                  <p>{String(item.summary ?? "No summary")}</p>
                  <div className="chip-row">
                    <span className="chip chip--quiet">
                      Momentum {Math.round(Number(item.self_activity_momentum ?? 0) * 100)}%
                    </span>
                    <span className="chip chip--quiet">
                      Own rhythm {Math.round(Number(item.own_rhythm_bias ?? 0) * 100)}%
                    </span>
                  </div>
                </article>
              ))}
            </div>
          </DetailCard>

          <JsonDump value={session.bond.payload} label="Raw bond payload" />
        </div>
      ),
    },
    {
      id: "sources",
      label: "Sources",
      count: session.sources.length,
      content: (
        <div className="panel-stack">
          <DetailCard title="Current-turn sources" eyebrow="Claim attribution surface">
            <SourcesList sources={session.sources} />
          </DetailCard>

          <DetailCard title="Claim links" eyebrow="Excerpt to source mapping">
            <div className="stack-list compact-stack">
              {session.claimLinks.length ? (
                session.claimLinks.map((claim, index) => (
                  <article key={`claim-${index}`} className="stack-item">
                    <div className="stack-item__topline">
                      <strong>{claim.claim_excerpt ?? `Claim ${index + 1}`}</strong>
                      <span>{Array.isArray(claim.source_ids) ? claim.source_ids.join(", ") : "no ids"}</span>
                    </div>
                  </article>
                ))
              ) : (
                <p className="empty-state">No claim links on this packet.</p>
              )}
            </div>
          </DetailCard>

          <JsonDump value={{ sources: session.sources, claimLinks: session.claimLinks }} label="Raw source packet" />
        </div>
      ),
    },
  ];

  return (
    <div className="shell">
      <a className="skip-link" href="#workspace">
        Skip to workspace
      </a>

      <header className="topbar">
        <div className="brand-lockup brand-lockup--wide">
          <div className="brand-mark" aria-hidden="true">
            <span />
            <span />
          </div>
          <div>
            <span className="brand-lockup__kicker">mock continuity observatory</span>
            <span className="brand-lockup__title">Amadeus Interface</span>
          </div>
        </div>
        <div className="chip-row topbar__chips">
          <span className="chip chip--quiet">Schema {session.schemaVersion}</span>
          <span className="chip chip--quiet">Thread {session.threadId}</span>
          <span className="chip chip--quiet">Mock transport</span>
        </div>
      </header>

      <section className="hero-grid">
        <article className="panel hero-card hero-card--manifesto">
          <p className="hero-card__eyebrow">{lensCopy[activeLens].eyebrow}</p>
          <h1>{lensCopy[activeLens].title}</h1>
          <p className="hero-card__lede">{lensCopy[activeLens].body}</p>
          <div className="lens-switcher" role="toolbar" aria-label="Focus lens selector">
            {focusLenses.map((lens) => {
              const selected = lens.id === activeLens;

              return (
                <button
                  key={lens.id}
                  type="button"
                  className={`lens-switcher__button${selected ? " is-active" : ""}`}
                  aria-pressed={selected}
                  onClick={() => setActiveLens(lens.id)}
                >
                  <span className="lens-switcher__label">{lens.label}</span>
                  <span className="lens-switcher__detail">{lens.description}</span>
                </button>
              );
            })}
          </div>
          <div className="chip-row">
            <span className="chip chip--accent">Stage {relationshipState.stage}</span>
            <span className="chip chip--quiet">Scene {currentTurn.counterpart_scene}</span>
            <span className="chip chip--quiet">Behavior {currentTurn.behavior_mode}</span>
          </div>
        </article>

        <article className="panel hero-card hero-card--quote">
          <div className="hero-card__header">
            <p className="hero-card__eyebrow">selected final utterance</p>
            <span className="inline-meta">{selectedEntry.envelope.kind}</span>
          </div>
          <p className="hero-quote">{selectedPayload.final_text}</p>
          <p className="hero-quote__support">{lensCopy[activeLens].callout}</p>
          <div className="note-cluster">
            {continuityNotes.map((note) => (
              <article key={note} className="note-chip-card">
                <span className="note-chip-card__label">Continuity note</span>
                <p>{note}</p>
              </article>
            ))}
          </div>
        </article>

        <article className="panel hero-card hero-card--signal">
          <div className="hero-card__header">
            <div>
              <p className="hero-card__eyebrow">signal constellation</p>
              <h2 className="hero-card__subheading">Live relational observatory</h2>
            </div>
            <span className="inline-meta">Selected turn {formatStamp(selectedEntry.envelope.generated_at)}</span>
          </div>
          <SignalConstellation
            metrics={signalMetrics}
            centerLabel="Coherence"
            centerValue={signalCore}
            caption="A single scene should expose trust, rhythm, agency, and presence at once."
          />
        </article>
      </section>

      <section className="spotlight-grid" aria-label="Active lens summary">
        {lensCopy[activeLens].stats.map((stat) => (
          <SpotlightStat key={stat.label} stat={stat} />
        ))}
      </section>

      <main id="workspace" className="workspace">
        <section className="workspace__column workspace__column--transcript">
          <div className="panel panel--section">
            <div className="panel__header">
              <div>
                <p className="panel__eyebrow">conversation rail</p>
                <h2>Transcript scenes</h2>
              </div>
              <p className="panel__meta">Choose a scene to reframe the whole observatory around its final packet.</p>
            </div>
            <div className="transcript-list transcript-list--rail">
              {session.transcript.map((entry) => (
                <TranscriptCard
                  key={entry.id}
                  entry={entry}
                  selected={entry.id === selectedEntry.id}
                  onSelect={() => setSelectedTurnId(entry.id)}
                />
              ))}
            </div>
          </div>

          <div className="panel panel--section">
            <div className="panel__header panel__header--compact">
              <div>
                <p className="panel__eyebrow">selected scene residue</p>
                <h2>Scene fingerprint</h2>
              </div>
              <p className="panel__meta">The chosen turn should already explain what it changed.</p>
            </div>
            <div className="fingerprint-grid">
              <DetailCard title="Current turn" eyebrow="Appraisal shell">
                <RecordGrid record={selectedSummary.current_turn as unknown as JsonRecord} />
              </DetailCard>
              <DetailCard title="Event residue" eyebrow="What lingers">
                <RecordGrid record={selectedSummary.event_residue as unknown as JsonRecord} />
              </DetailCard>
            </div>
          </div>
        </section>

        <section className="workspace__column workspace__column--focus">
          <div className="panel panel--section panel--statement">
            <div className="panel__header panel__header--compact">
              <div>
                <p className="panel__eyebrow">lens statement</p>
                <h2>Why this scene matters</h2>
              </div>
              <p className="panel__meta">Mock-only for now. The layout is being tuned before live transport arrives.</p>
            </div>
            <div className="statement-band">
              <div className="statement-band__primary">
                <span className="statement-band__label">Goal frame</span>
                <p>{selectedPayload.behavior_plan.goal_frame ?? "No goal frame attached."}</p>
              </div>
              <div className="statement-band__secondary">
                <div>
                  <span className="statement-band__label">Weather</span>
                  <strong>{titleCase(currentTurn.behavior_weather)}</strong>
                </div>
                <div>
                  <span className="statement-band__label">Consequence</span>
                  <strong>{titleCase(currentTurn.behavior_consequence_kind)}</strong>
                </div>
              </div>
            </div>
          </div>

          <div className="panel panel--section panel--packet">
            <div className="panel__header panel__header--compact">
              <div>
                <p className="panel__eyebrow">final-turn packet</p>
                <h2>Behavior, carryover, reconsolidation</h2>
              </div>
              <p className="panel__meta">Render and voice only `payload.final_text`.</p>
            </div>
            <div className="packet-grid">
              <DetailCard title="Behavior action" eyebrow="What the scene decided to do">
                <RecordGrid record={selectedPayload.behavior_action} />
              </DetailCard>
              <DetailCard title="Behavior plan" eyebrow="Why the action landed that way">
                <RecordGrid record={selectedPayload.behavior_plan} />
              </DetailCard>
              <DetailCard title="Interaction carryover" eyebrow="What remains active after response">
                <RecordGrid record={selectedPayload.interaction_carryover} />
              </DetailCard>
              <DetailCard title="Reconsolidation snapshot" eyebrow="What gets written back later">
                <RecordGrid record={selectedPayload.reconsolidation_snapshot} />
              </DetailCard>
            </div>
            {"pending_utterance_fragment" in selectedPayload && selectedPayload.pending_utterance_fragment ? (
              <div className="single-card">
                <DetailCard title="Pending utterance fragment" eyebrow="Resume protocol">
                  <p className="support-copy">{selectedPayload.pending_utterance_fragment}</p>
                </DetailCard>
              </div>
            ) : null}
            <div className="single-card">
              <JsonDump value={selectedPayload} label="Raw selected payload" />
            </div>
          </div>

          <div className="panel panel--section panel--storyline">
            <div className="panel__header panel__header--compact">
              <div>
                <p className="panel__eyebrow">worldline ribbon</p>
                <h2>Continuity cards</h2>
              </div>
              <p className="panel__meta">Events, repairs, commitments, and own-rhythm traces in one horizontal strip.</p>
            </div>
            <div className="storyline-strip" role="list" aria-label="Worldline continuity cards">
              {storyline.map((item) => (
                <StorylineCard key={item.id} item={item} />
              ))}
            </div>
          </div>

          <div className="panel panel--section">
            <div className="panel__header panel__header--compact">
              <div>
                <p className="panel__eyebrow">write surface placeholder</p>
                <h2>Composer staging area</h2>
              </div>
              <p className="panel__meta">Kept disabled until the mock-first design pass is finished.</p>
            </div>
            <div className="composer-shell composer-shell--enhanced">
              <label className="composer-shell__label" htmlFor="composer-box">
                Future frontend writer surface
              </label>
              <textarea
                id="composer-box"
                className="composer-shell__input"
                placeholder="The live adapter will end on one assistant_turn envelope, not a second frontend schema."
                disabled
              />
              <div className="composer-shell__actions">
                <button type="button" className="ghost-button" disabled>
                  Queue event round
                </button>
                <button type="button" className="primary-button" disabled>
                  Send turn
                </button>
              </div>
            </div>
          </div>
        </section>

        <aside className="workspace__column workspace__column--inspector">
          <div className="panel panel--sticky panel--section">
            <div className="panel__header panel__header--compact">
              <div>
                <p className="panel__eyebrow">inspector rail</p>
                <h2>Persona, worldline, bond, sources</h2>
              </div>
              <p className="panel__meta">Dense readback stays visible, but it no longer dominates the page mood.</p>
            </div>
            <div className="inspector-summary-band">
              <article className="inspector-summary-band__card">
                <span className="inspector-summary-band__label">Emotion</span>
                <strong>{selectedPayload.emotion_label}</strong>
              </article>
              <article className="inspector-summary-band__card">
                <span className="inspector-summary-band__label">Trust</span>
                <strong>{formatPercent(bondState.trust)}</strong>
              </article>
              <article className="inspector-summary-band__card">
                <span className="inspector-summary-band__label">Queue</span>
                <strong>{session.persona.payload.behavior_queue_summary.length}</strong>
              </article>
            </div>
            <InspectorTabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />
          </div>
        </aside>
      </main>
    </div>
  );
}

export default App;
