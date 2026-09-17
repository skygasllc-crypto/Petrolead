import { useState } from "react";
import { api, ApiError } from "../api/client";
import { useAuth } from "../context/AuthContext";

const inputClass =
  "mt-1.5 w-full rounded-md border border-base-600 bg-base-850 px-3 py-2.5 text-sm text-ink-100 placeholder:text-ink-700 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20";

function Field({ id, label, value, onChange, autoComplete }) {
  return (
    <div>
      <label htmlFor={id} className="text-sm font-medium text-ink-300">
        {label}
      </label>
      <input
        id={id}
        type="password"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        required
        className={inputClass}
      />
    </div>
  );
}

function AccountSecurity() {
  const { applyAuthResult } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(null);

  function fail(err, fallback) {
    setError(err instanceof ApiError ? err.message : fallback);
  }

  async function changePassword(e) {
    e.preventDefault();
    setError(null);
    setDone(null);
    if (next !== confirm) {
      setError("The two new passwords don't match.");
      return;
    }
    if (next.length < 8) {
      setError("Use at least 8 characters for the new password.");
      return;
    }
    setBusy("password");
    try {
      // The response carries a new token; storing it keeps this tab signed in.
      applyAuthResult(await api.changePassword(current, next));
      setCurrent("");
      setNext("");
      setConfirm("");
      setDone("Password changed. Every other device has been signed out.");
    } catch (err) {
      fail(err, "Couldn't change your password.");
    } finally {
      setBusy(null);
    }
  }

  async function signOutOthers() {
    setError(null);
    setDone(null);
    setBusy("revoke");
    try {
      applyAuthResult(await api.revokeSessions());
      setDone("Signed out everywhere else. This device is still signed in.");
    } catch (err) {
      fail(err, "Couldn't sign out your other devices.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="rounded-xl border border-base-700 bg-base-850 p-6">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-700">
        Account Security
      </h2>

      {error && (
        <p role="alert" className="mt-3 text-sm text-status-danger">
          {error}
        </p>
      )}
      {done && <p className="mt-3 text-sm text-status-high">{done}</p>}

      <form onSubmit={changePassword} className="mt-4 flex max-w-md flex-col gap-4">
        <Field
          id="current-password"
          label="Current password"
          value={current}
          onChange={setCurrent}
          autoComplete="current-password"
        />
        <Field
          id="new-password"
          label="New password"
          value={next}
          onChange={setNext}
          autoComplete="new-password"
        />
        <Field
          id="confirm-password"
          label="Confirm new password"
          value={confirm}
          onChange={setConfirm}
          autoComplete="new-password"
        />
        <div>
          <button
            type="submit"
            disabled={busy !== null}
            className="inline-flex items-center justify-center rounded-md bg-brand-500 px-5 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
          >
            {busy === "password" ? "Changing..." : "Change password"}
          </button>
          <p className="mt-2 text-xs text-ink-700">
            Changing your password signs out every other device.
          </p>
        </div>
      </form>

      <div className="mt-6 border-t border-base-700 pt-5">
        <h3 className="text-sm font-medium text-ink-300">Signed in somewhere you shouldn&apos;t be?</h3>
        <p className="mt-1 max-w-xl text-sm leading-relaxed text-ink-500">
          Sign out every other browser and device immediately. Sessions last a week otherwise,
          so do this if you&apos;ve used a shared computer or think someone else has your login.
          This device stays signed in.
        </p>
        <button
          type="button"
          onClick={signOutOthers}
          disabled={busy !== null}
          className="mt-3 inline-flex items-center justify-center rounded-md border border-base-600 px-5 py-2.5 text-sm font-semibold text-ink-300 hover:border-brand-500 hover:text-brand-600 disabled:opacity-60"
        >
          {busy === "revoke" ? "Signing out..." : "Sign out other devices"}
        </button>
      </div>
    </section>
  );
}

const ROADMAP = [
  { phase: 2, title: "Website & business contact discovery", status: "done" },
  { phase: 3, title: "Business email extraction & validation", status: "done" },
  { phase: 4, title: "Business telephone extraction & validation", status: "done" },
  {
    phase: 5,
    title: "Social/company profile discovery via permitted sources",
    status: "partial",
  },
  { phase: 6, title: "B2B source connectors", status: "partial" },
  { phase: 7, title: "Lead scoring", status: "done" },
  { phase: 8, title: "Excel / CSV export", status: "done" },
  { phase: 9, title: "Advanced search & filtering", status: "done" },
  { phase: 10, title: "Automated lead monitoring & scheduled searches", status: "done" },
];

const STATUS_LABEL = {
  done: "Implemented",
  partial: "Partial — search-based only",
};

const STATUS_STYLE = {
  done: "border-status-high/30 bg-status-high/15 text-status-high",
  partial: "border-status-possible/30 bg-status-possible/15 text-status-possible",
};

export default function Settings() {
  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-100">Settings</h1>
        <p className="mt-1 text-sm text-ink-500">
          Search-provider and platform configuration for PetroLead.
        </p>
      </div>

      <AccountSecurity />

      <section className="rounded-xl border border-base-700 bg-base-850 p-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-700">
          Search Provider
        </h2>
        <p className="mt-2 text-sm text-ink-500">
          PetroLead discovers companies through a pluggable search-provider abstraction,
          configured entirely via environment variables in the backend&apos;s{" "}
          <code className="rounded bg-base-800 px-1 py-0.5 text-xs">.env</code> file — never
          hard-coded. Set <code className="rounded bg-base-800 px-1 py-0.5 text-xs">
            SEARCH_PROVIDER
          </code>{" "}
          to one of the following:
        </p>
        <ul className="mt-4 flex flex-col gap-3">
          <li className="rounded-lg border border-base-700 bg-base-800/60 p-4">
            <div className="font-medium text-ink-100">mock</div>
            <p className="mt-1 text-xs text-ink-500">
              No API key required. Returns clearly-labeled synthetic results for interface
              testing. This is the default.
            </p>
          </li>
          <li className="rounded-lg border border-base-700 bg-base-800/60 p-4">
            <div className="font-medium text-ink-100">google_cse</div>
            <p className="mt-1 text-xs text-ink-500">
              Google Programmable Search Engine. Requires{" "}
              <code className="rounded bg-base-900 px-1 py-0.5">GOOGLE_CSE_API_KEY</code> and{" "}
              <code className="rounded bg-base-900 px-1 py-0.5">GOOGLE_CSE_ENGINE_ID</code>.
            </p>
          </li>
          <li className="rounded-lg border border-base-700 bg-base-800/60 p-4">
            <div className="font-medium text-ink-100">bing</div>
            <p className="mt-1 text-xs text-ink-500">
              Bing Web Search API (Azure). Requires{" "}
              <code className="rounded bg-base-900 px-1 py-0.5">BING_SEARCH_API_KEY</code>.
            </p>
          </li>
          <li className="rounded-lg border border-base-700 bg-base-800/60 p-4">
            <div className="font-medium text-ink-100">serpapi</div>
            <p className="mt-1 text-xs text-ink-500">
              SerpApi. Requires{" "}
              <code className="rounded bg-base-900 px-1 py-0.5">SERPAPI_API_KEY</code>.
            </p>
          </li>
        </ul>
      </section>

      <section className="rounded-xl border border-base-700 bg-base-850 p-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-700">
          Data Collection Policy
        </h2>
        <p className="mt-2 text-sm text-ink-500">
          PetroLead only discovers companies from legitimate public/business information. It
          never bypasses logins, CAPTCHAs, or anti-bot protections, and never scrapes private
          profiles or personal data. Social-network integrations (LinkedIn, Facebook, Instagram)
          will only ever use compliant, official APIs or explicitly permitted public data — see
          the roadmap below.
        </p>
      </section>

      <section className="rounded-xl border border-base-700 bg-base-850 p-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-700">
          Product Roadmap
        </h2>
        <ol className="mt-4 flex flex-col gap-2">
          {ROADMAP.map((item) => (
            <li
              key={item.phase}
              className="flex items-center gap-3 rounded-lg border border-base-800 px-4 py-2.5"
            >
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-base-700 text-xs font-semibold text-ink-300">
                {item.phase}
              </span>
              <span className="flex-1 text-sm text-ink-300">{item.title}</span>
              <span
                className={`rounded-full border px-2.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${STATUS_STYLE[item.status]}`}
              >
                {STATUS_LABEL[item.status]}
              </span>
            </li>
          ))}
        </ol>
        <p className="mt-4 text-xs text-ink-700">
          Phases 5 and 6 are partially implemented: the &quot;Company Search&quot; form has
          opt-in checkboxes that find LinkedIn/Facebook company pages and B2B-directory listings
          through your configured search provider&apos;s <code className="rounded bg-base-800 px-1 py-0.5">
            site:
          </code>{" "}
          operator — never by logging into or scraping those platforms/directories directly. What
          remains blocked is a full integration: an approved LinkedIn/social platform API
          partnership for richer data, and reviewed terms-of-service access to fetch individual
          B2B directory listing pages. Neither is something this app can obtain on its own.
        </p>
      </section>
    </div>
  );
}
