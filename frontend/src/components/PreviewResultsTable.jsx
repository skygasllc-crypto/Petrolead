import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import RelevanceBadge from "./RelevanceBadge";
import { sourceLabel } from "../lib/constants";

const COLUMNS = [
  { key: "company_name", label: "Company", sortable: true },
  { key: "location", label: "Location", sortable: false },
  { key: "industry", label: "Industry", sortable: true },
  { key: "products", label: "Products", sortable: false },
  { key: "website", label: "Website", sortable: false },
  { key: "source", label: "Source", sortable: true },
  { key: "relevance_score", label: "Relevance", sortable: true },
  { key: "lead_score", label: "Lead Score", sortable: true },
  { key: "save", label: "", sortable: false },
];

function locationOf(company) {
  return [company.city, company.country].filter(Boolean).join(", ") || "—";
}

/** Discover-results table for UNSAVED previews. Nothing here is a database
 * row yet — each has a per-row Save button instead of a link, unless it's
 * already saved (either from a prior save this session, or the backend
 * flagging it as a match to an existing company). */
export default function PreviewResultsTable({
  companies,
  savedState,
  onSave,
  emptyMessage = "No companies found.",
}) {
  const [sortKey, setSortKey] = useState("relevance_score");
  const [sortDir, setSortDir] = useState("desc");

  const sorted = useMemo(() => {
    const list = [...companies];
    list.sort((a, b) => {
      let av = a.item[sortKey];
      let bv = b.item[sortKey];
      if (sortKey === "company_name" || sortKey === "industry" || sortKey === "source") {
        av = (av || "").toString().toLowerCase();
        bv = (bv || "").toString().toLowerCase();
      }
      if (av < bv) return sortDir === "asc" ? -1 : 1;
      if (av > bv) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
    return list;
  }, [companies, sortKey, sortDir]);

  function toggleSort(key) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  if (companies.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-base-600 bg-base-850/50 px-6 py-16 text-center text-sm text-ink-500">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-base-700 bg-base-850">
      <table className="w-full min-w-[940px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-base-700 text-left text-xs uppercase tracking-wide text-ink-700">
            {COLUMNS.map((col) => (
              <th key={col.key} className="px-4 py-3 font-medium">
                {col.sortable ? (
                  <button
                    type="button"
                    onClick={() => toggleSort(col.key)}
                    className="inline-flex items-center gap-1 hover:text-ink-100"
                  >
                    {col.label}
                    {sortKey === col.key && (
                      <span className="text-brand-600">{sortDir === "asc" ? "↑" : "↓"}</span>
                    )}
                  </button>
                ) : (
                  col.label
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map(({ index, item: company }) => {
            const state = savedState[index] || { status: "idle" };
            return (
              <tr
                key={index}
                className="border-b border-base-800 last:border-0 hover:bg-base-800/50"
              >
                <td className="px-4 py-3">
                  {state.companyId ? (
                    <Link
                      to={`/companies/${state.companyId}`}
                      className="font-medium text-ink-100 hover:text-brand-600"
                    >
                      {company.company_name}
                    </Link>
                  ) : (
                    <span className="font-medium text-ink-100">{company.company_name}</span>
                  )}
                </td>
                <td className="px-4 py-3 text-ink-500">{locationOf(company)}</td>
                <td className="px-4 py-3 text-ink-500">{company.industry || "—"}</td>
                <td className="px-4 py-3 text-ink-500">
                  {company.products && company.products.length > 0
                    ? company.products.join(", ")
                    : "—"}
                </td>
                <td className="px-4 py-3">
                  {company.website ? (
                    <a
                      href={company.website}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-teal-400 hover:underline"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {company.website.replace(/^https?:\/\//, "")}
                    </a>
                  ) : (
                    <span className="text-ink-700">—</span>
                  )}
                </td>
                <td className="px-4 py-3 capitalize text-ink-500">
                  {sourceLabel(company.source)}
                </td>
                <td className="px-4 py-3">
                  <RelevanceBadge score={company.relevance_score} />
                </td>
                <td className="px-4 py-3 tabular-nums text-ink-300">
                  {company.lead_score ?? "—"}
                </td>
                <td className="px-4 py-3">
                  {state.status === "saved" ? (
                    <span className="inline-flex items-center gap-1 rounded-full border border-status-high/30 bg-status-high/15 px-2.5 py-1 text-xs font-medium text-status-high">
                      Saved
                    </span>
                  ) : company.already_saved && state.status !== "error" ? (
                    <span className="inline-flex items-center gap-1 rounded-full border border-base-600 bg-base-800 px-2.5 py-1 text-xs font-medium text-ink-500">
                      Already saved
                    </span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => onSave(index)}
                      disabled={state.status === "saving"}
                      className="rounded-md border border-brand-500/60 px-3 py-1 text-xs font-semibold text-brand-600 transition-colors hover:bg-brand-500/15 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {state.status === "saving" ? "Saving..." : "Save"}
                    </button>
                  )}
                  {state.status === "error" && (
                    <div className="mt-1 text-[10px] text-status-danger">{state.error}</div>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
