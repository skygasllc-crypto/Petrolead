import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { COUNTRIES, INDUSTRIES } from "../lib/constants";
import ErrorBanner from "../components/ErrorBanner";
import EmptyState from "../components/EmptyState";

const PAGE_SIZE = 25;

const selectClasses =
  "rounded-md border border-base-600 bg-base-800 px-3 py-2 text-sm text-ink-100 focus:border-brass-500 focus:outline-none";

function VerifiedBadge({ isValid }) {
  if (isValid === true) {
    return (
      <span className="rounded-full border border-status-high/30 bg-status-high/15 px-2 py-0.5 text-[10px] font-medium text-status-high">
        Verified
      </span>
    );
  }
  if (isValid === false) {
    return (
      <span className="rounded-full border border-status-low/30 bg-status-low/15 px-2 py-0.5 text-[10px] font-medium text-status-low">
        Unverified
      </span>
    );
  }
  return (
    <span className="rounded-full border border-base-600 px-2 py-0.5 text-[10px] font-medium text-ink-700">
      Check pending
    </span>
  );
}

export default function Emails() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [search, setSearch] = useState("");
  const [isValid, setIsValid] = useState("");
  const [country, setCountry] = useState("");
  const [industry, setIndustry] = useState("");
  const [hasExported, setHasExported] = useState("");

  const filters = {
    search: search || undefined,
    is_valid: isValid === "" ? undefined : isValid === "true",
    country: country || undefined,
    industry: industry || undefined,
    has_exported: hasExported === "" ? undefined : hasExported === "true",
  };
  const filterKey = JSON.stringify(filters);

  function refetch() {
    setLoading(true);
    setError(null);
    return api
      .listEmails({ page, page_size: PAGE_SIZE, ...filters })
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
      })
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "Failed to load emails.");
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .listEmails({ page, page_size: PAGE_SIZE, ...filters })
      .then((res) => {
        if (cancelled) return;
        setItems(res.items);
        setTotal(res.total);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Failed to load emails.");
      })
      .finally(() => !cancelled && setLoading(false));
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
    await api.exportEmails({ format, ...filters });
    // Exporting stamps exported_at server-side — refresh so the badge
    // (and an active has_exported filter) reflect it immediately.
    refetch();
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink-100">Emails</h1>
          <p className="mt-1 text-sm text-ink-500">
            Every business email address discovered so far, across all companies, in one place.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => handleExport("csv")}
            className="rounded-md border border-base-600 px-4 py-2 text-sm font-medium text-ink-300 hover:border-brass-500 hover:text-brass-400"
          >
            Export CSV
          </button>
          <button
            type="button"
            onClick={() => handleExport("xlsx")}
            className="rounded-md border border-base-600 px-4 py-2 text-sm font-medium text-ink-300 hover:border-brass-500 hover:text-brass-400"
          >
            Export Excel
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search emails..."
          className="w-full max-w-xs rounded-md border border-base-600 bg-base-800 px-3 py-2 text-sm text-ink-100 placeholder:text-ink-700 focus:border-brass-500 focus:outline-none"
        />
        <select value={isValid} onChange={(e) => setIsValid(e.target.value)} className={selectClasses}>
          <option value="">Any verification status</option>
          <option value="true">Verified only</option>
          <option value="false">Unverified only</option>
        </select>
        <select
          value={country}
          onChange={(e) => setCountry(e.target.value)}
          className={selectClasses}
        >
          <option value="">All countries</option>
          {COUNTRIES.map((c) => (
            <option key={c} value={c}>
              {c}
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
        <select
          value={hasExported}
          onChange={(e) => setHasExported(e.target.value)}
          className={selectClasses}
        >
          <option value="">Any export status</option>
          <option value="false">Not yet exported</option>
          <option value="true">Already exported</option>
        </select>
        <span className="text-xs text-ink-700">{total} email{total === 1 ? "" : "s"}</span>
      </div>

      {error && <ErrorBanner message={error} onRetry={() => setPage((p) => p)} />}

      {loading ? (
        <div className="rounded-xl border border-base-700 bg-base-850 px-6 py-16 text-center text-sm text-ink-500">
          Loading emails...
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          title="No emails found"
          description="Run a discovery search — any business emails found on a company's own website will appear here."
        />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-base-700 bg-base-850">
          <table className="w-full min-w-[760px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-base-700 text-left text-xs uppercase tracking-wide text-ink-700">
                <th className="px-4 py-3 font-medium">Email</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Company</th>
                <th className="px-4 py-3 font-medium">Country</th>
                <th className="px-4 py-3 font-medium">Industry</th>
              </tr>
            </thead>
            <tbody>
              {items.map((e) => (
                <tr
                  key={`${e.company_id}-${e.email}`}
                  className="border-b border-base-800 last:border-0 hover:bg-base-800/50"
                >
                  <td className="px-4 py-3">
                    <a
                      href={`mailto:${e.email}`}
                      className="font-medium text-ink-100 hover:text-brass-400"
                    >
                      {e.email}
                    </a>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      <VerifiedBadge isValid={e.is_valid} />
                      {e.exported_at && (
                        <span
                          className="rounded-full border border-status-relevant/30 bg-status-relevant/15 px-1.5 py-0.5 text-[10px] font-medium text-status-relevant"
                          title={`Exported ${new Date(e.exported_at).toLocaleString()}`}
                        >
                          Exported
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      to={`/companies/${e.company_id}`}
                      className="text-ink-300 hover:text-brass-400"
                    >
                      {e.company_name}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-ink-500">{e.company_country || "—"}</td>
                  <td className="px-4 py-3 text-ink-500">{e.company_industry || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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
