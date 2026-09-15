import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { REGIONS, INDUSTRIES, PRODUCTS } from "../lib/constants";
import CompanyTable from "../components/CompanyTable";
import ResultsToolbar from "../components/ResultsToolbar";
import ErrorBanner from "../components/ErrorBanner";

const PAGE_SIZE = 25;

const selectClasses =
  "rounded-md border border-base-600 bg-base-800 px-3 py-2 text-sm text-ink-100 focus:border-brand-500 focus:outline-none";

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
  const [product, setProduct] = useState("");
  const [hasEmail, setHasEmail] = useState("");
  const [hasPhone, setHasPhone] = useState("");
  const [hasExported, setHasExported] = useState("");
  const [minLeadScore, setMinLeadScore] = useState(0);

  const filters = {
    search: search || undefined,
    min_relevance: minRelevance || undefined,
    region: region || undefined,
    industry: industry || undefined,
    product: product || undefined,
    has_email: hasEmail === "" ? undefined : hasEmail === "true",
    has_phone: hasPhone === "" ? undefined : hasPhone === "true",
    has_exported: hasExported === "" ? undefined : hasExported === "true",
    min_lead_score: minLeadScore || undefined,
  };
  const filterKey = JSON.stringify(filters);

  function refetch() {
    setLoading(true);
    setError(null);
    return api
      .listCompanies({ page, page_size: PAGE_SIZE, ...filters })
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
      })
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "Failed to load companies.");
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    api
      .listCompanies({ page, page_size: PAGE_SIZE, ...filters })
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, filterKey]);

  useEffect(() => {
    setPage(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterKey]);

  async function handleExport(format) {
    await api.exportCompanies({ format, ...filters });
    // Exporting stamps exported_at server-side — refresh so the "Exported"
    // badge (and an active has_exported filter) reflect it immediately.
    refetch();
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink-100">Companies</h1>
          <p className="mt-1 text-sm text-ink-500">
            All companies discovered and deduplicated so far, across every search.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => handleExport("csv")}
            className="rounded-md border border-base-600 px-4 py-2 text-sm font-medium text-ink-300 hover:border-brand-500 hover:text-brand-600"
          >
            Export CSV
          </button>
          <button
            type="button"
            onClick={() => handleExport("xlsx")}
            className="rounded-md border border-base-600 px-4 py-2 text-sm font-medium text-ink-300 hover:border-brand-500 hover:text-brand-600"
          >
            Export Excel
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <select value={region} onChange={(e) => setRegion(e.target.value)} className={selectClasses}>
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
          className={selectClasses}
        >
          <option value="">All industries</option>
          {INDUSTRIES.map((i) => (
            <option key={i} value={i}>
              {i}
            </option>
          ))}
        </select>
        <select value={product} onChange={(e) => setProduct(e.target.value)} className={selectClasses}>
          <option value="">All products</option>
          {PRODUCTS.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <select
          value={hasEmail}
          onChange={(e) => setHasEmail(e.target.value)}
          className={selectClasses}
        >
          <option value="">Any email status</option>
          <option value="true">Has email</option>
          <option value="false">No email found</option>
        </select>
        <select
          value={hasPhone}
          onChange={(e) => setHasPhone(e.target.value)}
          className={selectClasses}
        >
          <option value="">Any phone status</option>
          <option value="true">Has phone</option>
          <option value="false">No phone found</option>
        </select>
        <select
          value={hasExported}
          onChange={(e) => setHasExported(e.target.value)}
          className={selectClasses}
        >
          <option value="">Any export status</option>
          <option value="false">Not yet exported</option>
          <option value="true">Already exported</option>
        </select>
        <label className="flex items-center gap-2 text-xs text-ink-500">
          Min lead score
          <input
            type="range"
            min="0"
            max="100"
            step="5"
            value={minLeadScore}
            onChange={(e) => setMinLeadScore(Number(e.target.value))}
            className="w-28 accent-[var(--color-brand-500)]"
          />
          <span className="w-8 tabular-nums text-ink-300">{minLeadScore}</span>
        </label>
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
          emptyMessage="No companies match the current filters."
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
