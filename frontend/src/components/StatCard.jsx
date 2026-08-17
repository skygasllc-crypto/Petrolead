export default function StatCard({ label, value, hint, accent = false }) {
  return (
    <div className="rounded-xl border border-base-700 bg-base-850 p-5">
      <div className="text-xs font-medium uppercase tracking-wide text-ink-700">{label}</div>
      <div
        className={`mt-2 text-3xl font-semibold tabular-nums ${
          accent ? "text-brass-400" : "text-ink-100"
        }`}
      >
        {value}
      </div>
      {hint && <div className="mt-1 text-xs text-ink-500">{hint}</div>}
    </div>
  );
}
