import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { REGIONS, INDUSTRIES } from "../lib/constants";
import CompanyTable from "../components/CompanyTable";
import ResultsToolbar from "../components/ResultsToolbar";
import ErrorBanner from "../components/ErrorBanner";

const PAGE_SIZE = 25;

export default function Companies() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [search, setSearch] = useState("");
  const [minRelevance, setMinRelevance] = useState(0);
  const [region, setRegion] = useState("");
  const [industry, setIndustry] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    api
      .listCompanies({
        page,
        page_size: PAGE_SIZE,
        search: search || undefined,
        min_relevance: minRelevance || undefined,
        region: region || undefined,
        industry: industry || undefined,
      })
      .then((res) => {
        if (cancelled) return;
        setItems(res.items);
        setTotal(res.total);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Failed to load companies.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [page, search, minRelevance, region, industry]);

  useEffect(() => {
    setPage(1);
  }, [search, minRelevance, region, industry]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-100">Companies</h1>
        <p className="mt-1 text-sm text-ink-500">
          All companies discovered and deduplicated so far, across every search.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <select
          value={region}
          onChange={(e) => setRegion(e.target.value)}
          className="rounded-md border border-base-600 bg-base-800 px-3 py-2 text-sm text-ink-100 focus:border-brass-500 focus:outline-none"
        >
          <option value="">All regions</option>
          {REGIONS.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
        <select
          value={industry}
          onChange={(e) => setIndustry(e.target.value)}
          className="rounded-md border border-base-600 bg-base-800 px-3 py-2 text-sm text-ink-100 focus:border-brass-500 focus:outline-none"
        >
          <option value="">All industries</option>
          {INDUSTRIES.map((i) => (
            <option key={i} value={i}>
              {i}
            </option>
          ))}
        </select>
      </div>

      <ResultsToolbar
        search={search}
        onSearchChange={setSearch}
        minRelevance={minRelevance}
        onMinRelevanceChange={setMinRelevance}
        total={total}
      />

      {error && <ErrorBanner message={error} onRetry={() => setPage((p) => p)} />}

      {loading ? (
        <div className="rounded-xl border border-base-700 bg-base-850 px-6 py-16 text-center text-sm text-ink-500">
          Loading companies...
        </div>
      ) : (
        <CompanyTable
          companies={items}
          emptyMessage="No companies yet. Run a discovery search to populate this list."
        />
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
            className="rounded-md border border-base-600 px-3 py-1.5 text-sm text-ink-300 disabled:opacity-40"
          >
            Previous
          </button>
          <span className="text-sm text-ink-500">
            Page {page} of {totalPages}
          </span>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
            className="rounded-md border border-base-600 px-3 py-1.5 text-sm text-ink-300 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
