import type { CSSProperties } from "react";

export interface SignalMetric {
  label: string;
  value: number;
  tone?: "blue" | "signal" | "slate";
}

const toneMap: Record<NonNullable<SignalMetric["tone"]>, string> = {
  blue: "#2067c5",
  signal: "#c56545",
  slate: "#5f6d7a",
};

function clampMetric(value: number) {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.min(1, value));
}

export function SignalConstellation({
  metrics,
  centerLabel,
  centerValue,
  caption,
}: {
  metrics: SignalMetric[];
  centerLabel: string;
  centerValue: number;
  caption: string;
}) {
  const safeCenter = clampMetric(centerValue);

  return (
    <div className="constellation-shell">
      <div className="constellation-board" aria-hidden="true">
        <div className="constellation-board__ring constellation-board__ring--outer" />
        <div className="constellation-board__ring constellation-board__ring--middle" />
        <div className="constellation-board__ring constellation-board__ring--inner" />

        {metrics.map((metric, index) => {
          const safeValue = clampMetric(metric.value);
          const angle = -90 + (360 / Math.max(metrics.length, 1)) * index;
          const radians = (angle * Math.PI) / 180;
          const radius = 21 + safeValue * 18;
          const left = 50 + Math.cos(radians) * radius;
          const top = 50 + Math.sin(radians) * radius;
          const tone = metric.tone ?? "blue";
          const color = toneMap[tone];
          const spokeStyle = {
            width: `${radius}%`,
            transform: `translateY(-50%) rotate(${angle}deg)`,
            "--signal-color": color,
          } as CSSProperties;
          const nodeStyle = {
            left: `${left}%`,
            top: `${top}%`,
            "--signal-color": color,
          } as CSSProperties;

          return (
            <div key={metric.label}>
              <div className="constellation-board__spoke" style={spokeStyle} />
              <div className="constellation-board__node" style={nodeStyle}>
                <span className="constellation-board__dot" />
                <span className="constellation-board__node-label">{metric.label}</span>
                <span className="constellation-board__node-value">{Math.round(safeValue * 100)}%</span>
              </div>
            </div>
          );
        })}

        <div className="constellation-board__core">
          <span className="constellation-board__core-label">{centerLabel}</span>
          <strong>{Math.round(safeCenter * 100)}%</strong>
        </div>
      </div>

      <div className="constellation-shell__caption">
        <p>{caption}</p>
      </div>
    </div>
  );
}
