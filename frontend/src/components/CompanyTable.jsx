import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import RelevanceBadge from "./RelevanceBadge";

const COLUMNS = [
  { key: "company_name", label: "Company", sortable: true },
  { key: "location", label: "Location", sortable: false },
  { key: "industry", label: "Industry", sortable: true },
  { key: "products", label: "Products", sortable: false },
  { key: "website", label: "Website", sortable: false },
  { key: "source", label: "Source", sortable: true },
  { key: "relevance_score", label: "Relevance", sortable: true },
  { key: "lead_score", label: "Lead Score", sortable: true },
];

function locationOf(company) {
  return [company.city, company.country].filter(Boolean).join(", ") || "—";
}

function sourceLabel(source) {
  if (!source) return "—";
  return source.replace(/^search:/, "").replace(/_/g, " ");
}

export default function CompanyTable({ companies, emptyMessage = "No companies found." }) {
  const [sortKey, setSortKey] = useState("relevance_score");
  const [sortDir, setSortDir] = useState("desc");

  const sorted = useMemo(() => {
    const list = [...companies];
    list.sort((a, b) => {
      let av = a[sortKey];
      let bv = b[sortKey];
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
      <table className="w-full min-w-[860px] border-collapse text-sm">
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
                      <span className="text-brass-400">{sortDir === "asc" ? "↑" : "↓"}</span>
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
          {sorted.map((company) => (
            <tr
              key={company.id}
              className="border-b border-base-800 last:border-0 hover:bg-base-800/50"
            >
              <td className="px-4 py-3">
                <Link
                  to={`/companies/${company.id}`}
                  className="font-medium text-ink-100 hover:text-brass-400"
                >
                  {company.company_name}
                </Link>
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
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
