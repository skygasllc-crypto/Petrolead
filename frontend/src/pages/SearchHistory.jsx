import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import ErrorBanner from "../components/ErrorBanner";
import EmptyState from "../components/EmptyState";

const STATUS_STYLES = {
  completed: "bg-status-high/15 text-status-high border-status-high/30",
  running: "bg-status-possible/15 text-status-possible border-status-possible/30",
  pending: "bg-base-600/30 text-ink-300 border-base-600",
  failed: "bg-status-danger/15 text-status-danger border-status-danger/30",
};

export default function SearchHistory() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .listSearches({ page: 1, page_size: 50 })
      .then((res) => setItems(res.items))
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Failed to load search history."),
      )
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-100">Search History</h1>
        <p className="mt-1 text-sm text-ink-500">
          Every discovery job you've run, with its criteria and outcome.
        </p>
      </div>

      {error && <ErrorBanner message={error} />}

      {loading ? (
        <div className="rounded-xl border border-base-700 bg-base-850 px-6 py-16 text-center text-sm text-ink-500">
          Loading search history...
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          title="No searches yet"
          description="Run a discovery search to see it appear here."
        />
      ) : (
        <div className="flex flex-col gap-3">
          {items.map((search) => {
            // Only a scheduled run (Phase 10) auto-persists its results —
            // an interactive search is preview-only until the user clicks
            // "Save All", so its new/duplicate counts describe what would
            // happen on save, not what was actually saved. See
            // `discover_preview`'s docstring in app/services/company_service.py.
            const isScheduledRun = Boolean(search.saved_search_id);
            return (
              <div
                key={search.id}
                className="rounded-xl border border-base-700 bg-base-850 p-5"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2 text-sm text-ink-100">
                    {[search.region, search.country, search.city, search.industry]
                      .filter(Boolean)
                      .map((v) => (
                        <span
                          key={v}
                          className="rounded-full border border-base-600 px-2.5 py-0.5 text-xs text-ink-300"
                        >
                          {v}
                        </span>
                      ))}
                    {search.products?.map((p) => (
                      <span
                        key={p}
                        className="rounded-full border border-brass-500/30 bg-brass-500/10 px-2.5 py-0.5 text-xs text-brass-300"
                      >
                        {p}
                      </span>
                    ))}
                  </div>
                  <span
                    className={`rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize ${
                      STATUS_STYLES[search.status] || STATUS_STYLES.pending
                    }`}
                  >
                    {search.status}
                  </span>
                </div>

                <p className="mt-3 text-sm text-ink-500">
                  {search.status_message || "No summary available."}
                </p>

                <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-ink-700">
                  <span>{new Date(search.created_at).toLocaleString()}</span>
                  <span>{search.result_count} result(s)</span>
                  <span>
                    {search.new_company_count} {isScheduledRun ? "new" : "not yet saved"}
                  </span>
                  <span>
                    {search.duplicate_count}{" "}
                    {isScheduledRun ? "matched existing" : "already in your companies"}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
