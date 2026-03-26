import type { CSSProperties } from "react";

interface MetricBarProps {
  label: string;
  value: number;
  tone?: "blue" | "signal" | "slate";
  detail?: string;
}

const toneMap: Record<NonNullable<MetricBarProps["tone"]>, string> = {
  blue: "linear-gradient(90deg, #215eb5 0%, #5d95e7 100%)",
  signal: "linear-gradient(90deg, #b44c31 0%, #da8e70 100%)",
  slate: "linear-gradient(90deg, #334155 0%, #7b8798 100%)",
};

export function MetricBar({ label, value, tone = "blue", detail }: MetricBarProps) {
  const safeValue = Number.isFinite(value) ? Math.max(0, Math.min(1, value)) : 0;
  const percentage = Math.round(safeValue * 100);
  const barStyle = {
    "--metric-fill": toneMap[tone],
    "--metric-width": `${percentage}%`,
  } as CSSProperties;

  return (
    <div className="metric-bar" style={barStyle}>
      <div className="metric-bar__row">
        <span>{label}</span>
        <span>{percentage}%</span>
      </div>
      <div
        className="metric-bar__track"
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percentage}
      >
        <div className="metric-bar__fill" />
      </div>
      {detail ? <p className="metric-bar__detail">{detail}</p> : null}
    </div>
  );
}
