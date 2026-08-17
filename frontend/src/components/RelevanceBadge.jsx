import { relevanceTier } from "../lib/constants";

const TONE_STYLES = {
  high: "bg-status-high/15 text-status-high border-status-high/30",
  relevant: "bg-status-relevant/15 text-status-relevant border-status-relevant/30",
  possible: "bg-status-possible/15 text-status-possible border-status-possible/30",
  low: "bg-status-low/15 text-status-low border-status-low/30",
};

export default function RelevanceBadge({ score, size = "sm" }) {
  const { label, tone } = relevanceTier(score);
  const padding = size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1 text-sm";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-medium ${padding} ${TONE_STYLES[tone]}`}
      title={`${label} — ${score}/100`}
    >
      <span className="tabular-nums">{score}%</span>
      <span className="hidden sm:inline">· {label}</span>
    </span>
  );
}
