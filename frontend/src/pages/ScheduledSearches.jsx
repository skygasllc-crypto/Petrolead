import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { REGIONS, INDUSTRIES, PRODUCTS, RESULT_LIMITS, COUNTRIES } from "../lib/constants";
import ErrorBanner from "../components/ErrorBanner";
import EmptyState from "../components/EmptyState";

const INITIAL_FORM = {
  name: "",
  region: "",
  country: "",
  city: "",
  industry: "",
  products: [],
  keywords: "",
  limit: 25,
  frequency: "daily",
};

const inputClasses =
  "w-full rounded-md border border-base-600 bg-base-800 px-3 py-2 text-sm text-ink-100 focus:border-brand-500 focus:outline-none";

function Field({ label, children }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-xs font-medium uppercase tracking-wide text-ink-700">{label}</span>
      {children}
    </label>
  );
}

export default function ScheduledSearches() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [form, setForm] = useState(INITIAL_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [runningNow, setRunningNow] = useState(false);
  const [runMessage, setRunMessage] = useState(null);

  function load() {
    setLoading(true);
    api
      .listSavedSearches()
      .then(setItems)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Failed to load scheduled searches."),
      )
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

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

  async function handleCreate(e) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.createSavedSearch({
        name: form.name,
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
        frequency: form.frequency,
      });
      setForm(INITIAL_FORM);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create scheduled search.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleToggle(id, isActive) {
    await api.setSavedSearchActive(id, isActive);
    load();
  }

  async function handleDelete(id) {
    await api.deleteSavedSearch(id);
    load();
  }

  async function handleRunDue() {
    setRunningNow(true);
    setRunMessage(null);
    try {
      const result = await api.runDueSavedSearches();
      setRunMessage(`Ran ${result.ran} due search${result.ran === 1 ? "" : "es"}.`);
      load();
    } catch (err) {
      setRunMessage(err instanceof ApiError ? err.message : "Failed to run due searches.");
    } finally {
      setRunningNow(false);
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink-100">
            Scheduled Searches
          </h1>
          <p className="mt-1 text-sm text-ink-500">
            Save a discovery search to run automatically on a schedule and surface new companies
            over time.
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <button
            type="button"
            onClick={handleRunDue}
            disabled={runningNow}
            className="rounded-md border border-base-600 px-4 py-2 text-sm font-medium text-ink-300 hover:border-brand-500 hover:text-brand-600 disabled:opacity-50"
          >
            {runningNow ? "Running..." : "Run due searches now"}
          </button>
          {runMessage && <span className="text-xs text-ink-500">{runMessage}</span>}
        </div>
      </div>

      <div className="rounded-lg border border-base-700 bg-base-850/60 px-4 py-3 text-xs text-ink-500">
        Scheduling requires a background worker (Celery + Redis) running continuously — see{" "}
        <code className="rounded bg-base-800 px-1 py-0.5">app/worker.py</code>. Without it, use
        &quot;Run due searches now&quot; to trigger due searches manually.
      </div>

      <form
        onSubmit={handleCreate}
        className="grid grid-cols-1 gap-5 rounded-xl border border-base-700 bg-base-850 p-6 sm:grid-cols-2 lg:grid-cols-3"
      >
        <Field label="Name">
          <input
            className={inputClasses}
            value={form.name}
            onChange={(e) => update("name", e.target.value)}
            placeholder="e.g. UAE diesel traders"
            required
          />
        </Field>

        <Field label="Frequency">
          <select
            className={inputClasses}
            value={form.frequency}
            onChange={(e) => update("frequency", e.target.value)}
          >
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
          </select>
        </Field>

        <Field label="Number of results">
          <select
            className={inputClasses}
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

        <Field label="Region">
          <select
            className={inputClasses}
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
            list="scheduled-countries"
            className={inputClasses}
            value={form.country}
            onChange={(e) => update("country", e.target.value)}
            placeholder="e.g. United Arab Emirates"
          />
          <datalist id="scheduled-countries">
            {COUNTRIES.map((c) => (
              <option key={c} value={c} />
            ))}
          </datalist>
        </Field>

        <Field label="Industry">
          <select
            className={inputClasses}
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

        <Field label="Keywords (comma-separated)">
          <input
            className={inputClasses}
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

        <div className="sm:col-span-2 lg:col-span-3">
          <button
            type="submit"
            disabled={submitting}
            className="inline-flex w-full items-center justify-center rounded-md bg-brand-500 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
          >
            {submitting ? "Saving..." : "Save Scheduled Search"}
          </button>
        </div>
      </form>

      {error && <ErrorBanner message={error} />}

      {loading ? (
        <div className="rounded-xl border border-base-700 bg-base-850 px-6 py-16 text-center text-sm text-ink-500">
          Loading scheduled searches...
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          title="No scheduled searches yet"
          description="Create one above to have PetroLead discover new companies automatically."
        />
      ) : (
        <div className="flex flex-col gap-3">
          {items.map((s) => (
            <div key={s.id} className="rounded-xl border border-base-700 bg-base-850 p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-ink-100">{s.name}</span>
                    <span className="rounded-full border border-base-600 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-ink-500">
                      {s.frequency}
                    </span>
                    <span
                      className={`rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${
                        s.is_active
                          ? "border-status-high/30 bg-status-high/15 text-status-high"
                          : "border-base-600 text-ink-700"
                      }`}
                    >
                      {s.is_active ? "Active" : "Paused"}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-ink-700">
                    {[s.region, s.country, s.city, s.industry].filter(Boolean).join(" · ") ||
                      "General search"}
                    {s.products.length > 0 && ` · ${s.products.join(", ")}`}
                  </p>
                  <p className="mt-1 text-xs text-ink-700">
                    Last run:{" "}
                    {s.last_run_at ? new Date(s.last_run_at).toLocaleString() : "never"} · Next
                    run: {s.next_run_at ? new Date(s.next_run_at).toLocaleString() : "—"}
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => handleToggle(s.id, !s.is_active)}
                    className="rounded-md border border-base-600 px-3 py-1.5 text-xs text-ink-300 hover:border-brand-500 hover:text-brand-600"
                  >
                    {s.is_active ? "Pause" : "Resume"}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(s.id)}
                    className="rounded-md border border-base-600 px-3 py-1.5 text-xs text-status-danger hover:border-status-danger"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
