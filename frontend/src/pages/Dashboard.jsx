import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import StatCard from "../components/StatCard";
import RelevanceBadge from "../components/RelevanceBadge";
import EmptyState from "../components/EmptyState";

export default function Dashboard() {
  const [companyTotal, setCompanyTotal] = useState(null);
  const [highlyRelevantTotal, setHighlyRelevantTotal] = useState(null);
  const [searchTotal, setSearchTotal] = useState(null);
  const [recentCompanies, setRecentCompanies] = useState([]);
  const [recentSearches, setRecentSearches] = useState([]);

  useEffect(() => {
    api.listCompanies({ page: 1, page_size: 5 }).then((res) => {
      setCompanyTotal(res.total);
      setRecentCompanies(res.items);
    });
    api.listCompanies({ page: 1, page_size: 1, min_relevance: 80 }).then((res) => {
      setHighlyRelevantTotal(res.total);
    });
    api.listSearches({ page: 1, page_size: 5 }).then((res) => {
      setSearchTotal(res.total);
      setRecentSearches(res.items);
    });
  }, []);

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink-100">Dashboard</h1>
          <p className="mt-1 text-sm text-ink-500">
            Your petroleum &amp; energy lead discovery activity at a glance.
          </p>
        </div>
        <Link
          to="/discover"
          className="inline-flex items-center rounded-md bg-brass-500 px-5 py-2.5 text-sm font-semibold text-base-950 hover:bg-brass-400"
        >
          Discover Companies
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          label="Companies discovered"
          value={companyTotal ?? "—"}
          hint="Deduplicated, across all searches"
        />
        <StatCard
          label="Highly relevant"
          value={highlyRelevantTotal ?? "—"}
          hint="Relevance score ≥ 80"
          accent
        />
        <StatCard label="Searches run" value={searchTotal ?? "—"} hint="Total discovery jobs" />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <section className="rounded-xl border border-base-700 bg-base-850 p-6">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-700">
              Recently discovered
            </h2>
            <Link to="/companies" className="text-xs text-brass-400 hover:underline">
              View all
            </Link>
          </div>
          {recentCompanies.length === 0 ? (
            <EmptyState
              title="No companies yet"
              description="Run your first discovery search to get started."
            />
          ) : (
            <ul className="flex flex-col divide-y divide-base-800">
              {recentCompanies.map((c) => (
                <li key={c.id} className="flex items-center justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <Link
                      to={`/companies/${c.id}`}
                      className="truncate text-sm font-medium text-ink-100 hover:text-brass-400"
                    >
                      {c.company_name}
                    </Link>
                    <p className="truncate text-xs text-ink-700">
                      {[c.city, c.country].filter(Boolean).join(", ") || "Location unknown"}
                    </p>
                  </div>
                  <RelevanceBadge score={c.relevance_score} />
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded-xl border border-base-700 bg-base-850 p-6">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-700">
              Recent searches
            </h2>
            <Link to="/searches" className="text-xs text-brass-400 hover:underline">
              View all
            </Link>
          </div>
          {recentSearches.length === 0 ? (
            <EmptyState
              title="No searches yet"
              description="Your discovery jobs will appear here."
            />
          ) : (
            <ul className="flex flex-col divide-y divide-base-800">
              {recentSearches.map((s) => (
                <li key={s.id} className="py-3">
                  <div className="flex items-center justify-between gap-3">
                    <span className="truncate text-sm text-ink-100">
                      {[s.region, s.country, s.industry].filter(Boolean).join(" · ") ||
                        "General search"}
                    </span>
                    <span className="shrink-0 text-xs capitalize text-ink-500">{s.status}</span>
                  </div>
                  <p className="mt-0.5 text-xs text-ink-700">
                    {new Date(s.created_at).toLocaleString()}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
