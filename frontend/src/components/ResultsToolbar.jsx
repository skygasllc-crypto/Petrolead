export default function ResultsToolbar({
  search,
  onSearchChange,
  minRelevance,
  onMinRelevanceChange,
  total,
  extra,
}) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-1 flex-col gap-3 sm:flex-row sm:items-center">
        <input
          type="text"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search within results..."
          className="w-full max-w-xs rounded-md border border-base-600 bg-base-800 px-3 py-2 text-sm text-ink-100 placeholder:text-ink-700 focus:border-brand-500 focus:outline-none"
        />
        <label className="flex items-center gap-2 text-xs text-ink-500">
          Min relevance
          <input
            type="range"
            min="0"
            max="100"
            step="5"
            value={minRelevance}
            onChange={(e) => onMinRelevanceChange(Number(e.target.value))}
            className="w-32 accent-[var(--color-brand-500)]"
          />
          <span className="w-9 tabular-nums text-ink-300">{minRelevance}%</span>
        </label>
      </div>
      <div className="flex items-center gap-3">
        {extra}
        {typeof total === "number" && (
          <span className="text-xs text-ink-700">{total} result{total === 1 ? "" : "s"}</span>
        )}
      </div>
    </div>
  );
}
