import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { useBilling } from "../context/BillingContext";
import { REGIONS, INDUSTRIES, PRODUCTS, RESULT_LIMITS, COUNTRIES, ROLES } from "../lib/constants";
import DiscoveryProgress from "../components/DiscoveryProgress";
import PreviewResultsTable from "../components/PreviewResultsTable";
import ResultsToolbar from "../components/ResultsToolbar";
import ErrorBanner from "../components/ErrorBanner";

const INITIAL_FORM = {
  region: "",
  country: "",
  city: "",
  industry: "",
  role: "",
  products: [],
  keywords: "",
  limit: 25,
  includeSocialSearch: true,
  includeB2bDirectories: false,
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
  "w-full rounded-md border border-base-600 bg-base-800 px-3 py-2 text-sm text-ink-100 focus:border-brand-500 focus:outline-none";

export default function Discover() {
  const { refresh: refreshBilling } = useBilling();
  const [form, setForm] = useState(INITIAL_FORM);
  const [status, setStatus] = useState("idle"); // idle | loading | done | error
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const [search, setSearch] = useState("");
  const [minRelevance, setMinRelevance] = useState(0);

  // Keyed by index into result.companies. { status: idle|saving|saved|error, companyId, error }
  const [savedState, setSavedState] = useState({});
  const [savingAll, setSavingAll] = useState(false);

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
    setSavedState({});

    const payload = {
      region: form.region || null,
      country: form.country || null,
      city: form.city || null,
      industry: form.industry || null,
      role: form.role || null,
      products: form.products,
      keywords: form.keywords
        .split(",")
        .map((k) => k.trim())
        .filter(Boolean),
      limit: form.limit,
      include_social_search: form.includeSocialSearch,
      include_b2b_directories: form.includeB2bDirectories,
    };

    try {
      const response = await api.discover(payload);
      setResult(response);
      setStatus("done");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
      setStatus("error");
    }
    // A completed search counts against the plan's daily allowance and
    // spends a credit for every result that came with a business email.
    refreshBilling();
  }

  const filteredCompanies = useMemo(() => {
    if (!result) return [];
    const query = search.trim().toLowerCase();
    return result.companies
      .map((item, index) => ({ item, index }))
      .filter(({ item: c }) => {
        if (c.relevance_score < minRelevance) return false;
        if (!query) return true;
        const haystack = `${c.company_name} ${c.country || ""} ${c.city || ""} ${
          c.industry || ""
        } ${(c.products || []).join(" ")}`.toLowerCase();
        return haystack.includes(query);
      });
  }, [result, search, minRelevance]);

  const unsavedCount = useMemo(() => {
    if (!result) return 0;
    return result.companies.filter(
      (c, index) => !c.already_saved && savedState[index]?.status !== "saved",
    ).length;
  }, [result, savedState]);

  async function handleSaveOne(index) {
    const company = result.companies[index];
    setSavedState((s) => ({ ...s, [index]: { status: "saving" } }));
    try {
      const saved = await api.saveCompany(company);
      setSavedState((s) => ({ ...s, [index]: { status: "saved", companyId: saved.id } }));
    } catch (err) {
      setSavedState((s) => ({
        ...s,
        [index]: {
          status: "error",
          error: err instanceof ApiError ? err.message : "Could not save.",
        },
      }));
    }
  }

  async function handleSaveAll() {
    if (!result) return;
    const toSave = result.companies
      .map((c, index) => ({ c, index }))
      .filter(({ c, index }) => !c.already_saved && savedState[index]?.status !== "saved");
    if (toSave.length === 0) return;

    setSavingAll(true);
    setSavedState((s) => {
      const next = { ...s };
      toSave.forEach(({ index }) => {
        next[index] = { status: "saving" };
      });
      return next;
    });

    try {
      const response = await api.saveCompaniesBulk(toSave.map(({ c }) => c));
      setSavedState((s) => {
        const next = { ...s };
        toSave.forEach(({ index }, position) => {
          const saved = response.results[position];
          if (!saved) {
            next[index] = { status: "error", error: "Could not save." };
            return;
          }
          next[index] = { status: "saved", companyId: saved.id };
        });
        return next;
      });
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Could not save.";
      setSavedState((s) => {
        const next = { ...s };
        toSave.forEach(({ index }) => {
          next[index] = { status: "error", error: message };
        });
        return next;
      });
    } finally {
      setSavingAll(false);
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-100">Company Search</h1>
        <p className="mt-1 text-sm text-ink-500">
          Search public sources for petroleum, oil &amp; gas, and energy-trading companies
          matching your criteria.
        </p>
      </div>

      <Link
        to="/email-finder"
        className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-brand-100 bg-brand-50 px-5 py-4 text-sm transition-colors hover:border-brand-500"
      >
        <span>
          <span className="font-semibold text-ink-100">Looking for a specific person&apos;s email?</span>{" "}
          <span className="text-ink-500">
            Use Email Finder with a LinkedIn profile link, a name and company, or a company
            website.
          </span>
        </span>
        <span className="font-semibold text-brand-600">Open Email Finder →</span>
      </Link>

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

        {/* Combined with industry and products rather than replacing them,
            so "suppliers of diesel" can be asked for directly. */}
        <Field label="Looking for">
          <select
            className={selectClasses}
            value={form.role}
            onChange={(e) => update("role", e.target.value)}
          >
            <option value="">Anyone</option>
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {r}
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
                      ? "border-brand-500 bg-brand-500/15 text-brand-600"
                      : "border-base-600 text-ink-500 hover:border-base-400 hover:text-ink-100"
                  }`}
                >
                  {product}
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex flex-col gap-3 sm:col-span-2 lg:col-span-3">
          <span className="text-xs font-medium uppercase tracking-wide text-ink-700">
            Additional sources (Phase 5/6, partial — search-engine discovery only)
          </span>
          <label className="flex items-start gap-2.5 rounded-lg border border-base-700 bg-base-800/40 p-3 text-sm">
            <input
              type="checkbox"
              className="mt-0.5 accent-[var(--color-brand-500)]"
              checked={form.includeSocialSearch}
              onChange={(e) => update("includeSocialSearch", e.target.checked)}
            />
            <span>
              <span className="text-ink-100">Include social-platform search</span>
              <span className="block text-xs text-ink-700">
                Finds LinkedIn, Facebook and Instagram pages via search-engine{" "}
                <code className="rounded bg-base-900 px-1">site:</code> queries and keeps any
                email or phone shown in the search result — never logs into or scrapes those
                platforms. Adds extra search-provider calls.
              </span>
            </span>
          </label>
          <label className="flex items-start gap-2.5 rounded-lg border border-base-700 bg-base-800/40 p-3 text-sm">
            <input
              type="checkbox"
              className="mt-0.5 accent-[var(--color-brand-500)]"
              checked={form.includeB2bDirectories}
              onChange={(e) => update("includeB2bDirectories", e.target.checked)}
            />
            <span>
              <span className="text-ink-100">Include B2B directory listings</span>
              <span className="block text-xs text-ink-700">
                Finds listings on TradeKey, EC21, and similar directories the same way — via
                search results only, never by fetching the directory&apos;s own pages. Adds
                extra search-provider calls.
              </span>
            </span>
          </label>
        </div>

        <div className="sm:col-span-2 lg:col-span-3">
          <button
            type="submit"
            disabled={status === "loading"}
            className="inline-flex w-full items-center justify-center rounded-md bg-brand-500 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
          >
            {status === "loading" ? "Searching..." : "Search Companies"}
          </button>
          <p className="mt-2 text-xs text-ink-700">
            Uses one email credit for each result that comes with a business email. Results
            without one are free.
          </p>
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

          <div className="rounded-lg border border-brand-500/30 bg-brand-500/10 px-4 py-3 text-sm text-brand-600">
            <strong className="font-semibold">Nothing is saved yet.</strong> These results are a
            preview — click <strong>Save</strong> on a row, or <strong>Save All</strong> below, to
            add companies to your Companies list.
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="rounded-lg border border-base-700 bg-base-850 px-4 py-3">
              <div className="text-xs uppercase tracking-wide text-ink-700">Total found</div>
              <div className="text-xl font-semibold text-ink-100">{result.result_count}</div>
            </div>
            <div className="rounded-lg border border-base-700 bg-base-850 px-4 py-3">
              <div className="text-xs uppercase tracking-wide text-ink-700">Not yet saved</div>
              <div className="text-xl font-semibold text-status-high">
                {result.new_company_count}
              </div>
            </div>
            <div className="rounded-lg border border-base-700 bg-base-850 px-4 py-3">
              <div className="text-xs uppercase tracking-wide text-ink-700">
                Already in your companies
              </div>
              <div className="text-xl font-semibold text-ink-300">{result.duplicate_count}</div>
            </div>
          </div>

          <ResultsToolbar
            search={search}
            onSearchChange={setSearch}
            minRelevance={minRelevance}
            onMinRelevanceChange={setMinRelevance}
            total={filteredCompanies.length}
            extra={
              <button
                type="button"
                onClick={handleSaveAll}
                disabled={savingAll || unsavedCount === 0}
                className="rounded-md bg-brand-500 px-4 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {savingAll
                  ? "Saving..."
                  : unsavedCount === 0
                    ? "All saved"
                    : `Save All (${unsavedCount})`}
              </button>
            }
          />

          <PreviewResultsTable
            companies={filteredCompanies}
            savedState={savedState}
            onSave={handleSaveOne}
            emptyMessage="No companies match the current filters."
          />
        </div>
      )}
    </div>
  );
}
