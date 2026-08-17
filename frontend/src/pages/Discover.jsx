import { useMemo, useState } from "react";
import { api, ApiError } from "../api/client";
import { REGIONS, INDUSTRIES, PRODUCTS, RESULT_LIMITS, COUNTRIES } from "../lib/constants";
import DiscoveryProgress from "../components/DiscoveryProgress";
import CompanyTable from "../components/CompanyTable";
import ResultsToolbar from "../components/ResultsToolbar";
import ErrorBanner from "../components/ErrorBanner";

const INITIAL_FORM = {
  region: "",
  country: "",
  city: "",
  industry: "",
  products: [],
  keywords: "",
  limit: 25,
};

function Field({ label, children }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-xs font-medium uppercase tracking-wide text-ink-700">{label}</span>
      {children}
    </label>
  );
}

const selectClasses =
  "w-full rounded-md border border-base-600 bg-base-800 px-3 py-2 text-sm text-ink-100 focus:border-brass-500 focus:outline-none";

export default function Discover() {
  const [form, setForm] = useState(INITIAL_FORM);
  const [status, setStatus] = useState("idle"); // idle | loading | done | error
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const [search, setSearch] = useState("");
  const [minRelevance, setMinRelevance] = useState(0);

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  function toggleProduct(product) {
    setForm((f) => ({
      ...f,
      products: f.products.includes(product)
        ? f.products.filter((p) => p !== product)
        : [...f.products, product],
    }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setStatus("loading");
    setError(null);
    setResult(null);

    const payload = {
      region: form.region || null,
      country: form.country || null,
      city: form.city || null,
      industry: form.industry || null,
      products: form.products,
      keywords: form.keywords
        .split(",")
        .map((k) => k.trim())
        .filter(Boolean),
      limit: form.limit,
    };

    try {
      const response = await api.discover(payload);
      setResult(response);
      setStatus("done");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
      setStatus("error");
    }
  }

  const filteredCompanies = useMemo(() => {
    if (!result) return [];
    const query = search.trim().toLowerCase();
    return result.companies.filter((c) => {
      if (c.relevance_score < minRelevance) return false;
      if (!query) return true;
      const haystack = `${c.company_name} ${c.country || ""} ${c.city || ""} ${
        c.industry || ""
      } ${(c.products || []).join(" ")}`.toLowerCase();
      return haystack.includes(query);
    });
  }, [result, search, minRelevance]);

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-100">Discover Companies</h1>
        <p className="mt-1 text-sm text-ink-500">
          Search public sources for petroleum, oil &amp; gas, and energy-trading companies
          matching your criteria.
        </p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="grid grid-cols-1 gap-5 rounded-xl border border-base-700 bg-base-850 p-6 sm:grid-cols-2 lg:grid-cols-3"
      >
        <Field label="Region">
          <select
            className={selectClasses}
            value={form.region}
            onChange={(e) => update("region", e.target.value)}
          >
            <option value="">Any region</option>
            {REGIONS.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Country">
          <input
            list="countries"
            className={selectClasses}
            value={form.country}
            onChange={(e) => update("country", e.target.value)}
            placeholder="e.g. United Arab Emirates"
          />
          <datalist id="countries">
            {COUNTRIES.map((c) => (
              <option key={c} value={c} />
            ))}
          </datalist>
        </Field>

        <Field label="City (optional)">
          <input
            className={selectClasses}
            value={form.city}
            onChange={(e) => update("city", e.target.value)}
            placeholder="e.g. Dubai"
          />
        </Field>

        <Field label="Industry">
          <select
            className={selectClasses}
            value={form.industry}
            onChange={(e) => update("industry", e.target.value)}
          >
            <option value="">Any industry</option>
            {INDUSTRIES.map((i) => (
              <option key={i} value={i}>
                {i}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Number of results">
          <select
            className={selectClasses}
            value={form.limit}
            onChange={(e) => update("limit", Number(e.target.value))}
          >
            {RESULT_LIMITS.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Keywords (comma-separated)">
          <input
            className={selectClasses}
            value={form.keywords}
            onChange={(e) => update("keywords", e.target.value)}
            placeholder="diesel, fuel trading"
          />
        </Field>

        <div className="sm:col-span-2 lg:col-span-3">
          <span className="mb-2 block text-xs font-medium uppercase tracking-wide text-ink-700">
            Products
          </span>
          <div className="flex flex-wrap gap-2">
            {PRODUCTS.map((product) => {
              const active = form.products.includes(product);
              return (
                <button
                  type="button"
                  key={product}
                  onClick={() => toggleProduct(product)}
                  className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                    active
                      ? "border-brass-500 bg-brass-500/15 text-brass-300"
                      : "border-base-600 text-ink-500 hover:border-base-400 hover:text-ink-100"
                  }`}
                >
                  {product}
                </button>
              );
            })}
          </div>
        </div>

        <div className="sm:col-span-2 lg:col-span-3">
          <button
            type="submit"
            disabled={status === "loading"}
            className="inline-flex w-full items-center justify-center rounded-md bg-brass-500 px-6 py-3 text-sm font-semibold text-base-950 transition-colors hover:bg-brass-400 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
          >
            {status === "loading" ? "Discovering..." : "Discover Companies"}
          </button>
        </div>
      </form>

      {status === "loading" && <DiscoveryProgress />}

      {status === "error" && <ErrorBanner message={error} onRetry={handleSubmit} />}

      {status === "done" && result && (
        <div className="flex flex-col gap-4">
          {result.is_mock && (
            <div className="rounded-lg border border-status-possible/30 bg-status-possible/10 px-4 py-3 text-sm text-status-possible">
              <strong className="font-semibold">Mock data notice:</strong> No live search
              provider is configured (<code>SEARCH_PROVIDER=mock</code>). These results are
              clearly-labeled synthetic data for interface testing only — they are not real
              discovered companies. Configure a real provider in <code>.env</code> to discover
              actual companies.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="rounded-lg border border-base-700 bg-base-850 px-4 py-3">
              <div className="text-xs uppercase tracking-wide text-ink-700">Total found</div>
              <div className="text-xl font-semibold text-ink-100">{result.result_count}</div>
            </div>
            <div className="rounded-lg border border-base-700 bg-base-850 px-4 py-3">
              <div className="text-xs uppercase tracking-wide text-ink-700">New companies</div>
              <div className="text-xl font-semibold text-status-high">
                {result.new_company_count}
              </div>
            </div>
            <div className="rounded-lg border border-base-700 bg-base-850 px-4 py-3">
              <div className="text-xs uppercase tracking-wide text-ink-700">Matched existing</div>
              <div className="text-xl font-semibold text-ink-300">{result.duplicate_count}</div>
            </div>
          </div>

          <ResultsToolbar
            search={search}
            onSearchChange={setSearch}
            minRelevance={minRelevance}
            onMinRelevanceChange={setMinRelevance}
            total={filteredCompanies.length}
          />

          <CompanyTable
            companies={filteredCompanies}
            emptyMessage="No companies match the current filters."
          />
        </div>
      )}
    </div>
  );
}
