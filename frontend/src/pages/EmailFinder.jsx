import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { useBilling } from "../context/BillingContext";
import ValidityBadge from "../components/ValidityBadge";
import Icon from "../components/marketing/Icon";

const TABS = [
  { id: "linkedin", label: "LinkedIn profile", icon: "link" },
  { id: "name", label: "Name + company", icon: "user" },
  { id: "website", label: "Company website", icon: "globe" },
  { id: "bulk", label: "Bulk lookup", icon: "users" },
];

const MAX_BULK_ITEMS = 25; // matches MAX_BULK_LOOKUP_ITEMS in app/schemas.py

// Display names for the lowercase platform keys the API returns.
const PLATFORM_NAMES = {
  linkedin: "LinkedIn",
  facebook: "Facebook",
  twitter: "X (Twitter)",
  x: "X",
  instagram: "Instagram",
  youtube: "YouTube",
};
const LINKEDIN_PROFILE_RE = /linkedin\.com\/in\/[^/?#\s]+/i;

const inputClasses =
  "w-full rounded-md border border-base-600 bg-base-850 px-3 py-2.5 text-sm text-ink-100 placeholder:text-ink-700 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20";
const submitButton =
  "inline-flex shrink-0 items-center justify-center gap-2 rounded-md bg-brand-500 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60";

function errorMessage(err, fallback = "Something went wrong.") {
  return err instanceof ApiError ? err.message : fallback;
}

function withScheme(url) {
  return /^https?:\/\//i.test(url) ? url : `https://${url}`;
}

function useLookup() {
  const [state, setState] = useState({ status: "idle", attempt: 0 });
  const { refresh: refreshBilling } = useBilling();
  async function run(fn) {
    const attempt = state.attempt + 1;
    setState({ status: "loading", attempt });
    try {
      setState({ status: "done", attempt, result: await fn() });
    } catch (err) {
      setState({ status: "error", attempt, error: errorMessage(err) });
    }
    // A lookup that finds an email spends a credit — keep the header balance current.
    refreshBilling();
  }
  return [state, run];
}

function useSave() {
  const [state, setState] = useState({ status: "idle" });
  async function save(preview) {
    setState({ status: "saving" });
    try {
      const saved = await api.saveCompany(preview);
      setState({ status: "saved", companyId: saved.id });
    } catch (err) {
      setState({ status: "error", error: errorMessage(err, "Could not save.") });
    }
  }
  return [state, save];
}

function Initials({ name, className = "h-11 w-11 text-sm" }) {
  const initials = name
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  return (
    <span
      aria-hidden="true"
      className={`flex shrink-0 items-center justify-center rounded-full bg-brand-50 font-semibold text-brand-600 ${className}`}
    >
      {initials}
    </span>
  );
}

function SaveControl({ preview, state, onSave }) {
  if (state.status === "saved") {
    return (
      <Link
        to={`/companies/${state.companyId}`}
        className="rounded-full border border-status-high/30 bg-status-high/15 px-3 py-1 text-xs font-semibold text-status-high"
      >
        Saved — view company
      </Link>
    );
  }
  if (preview.already_saved) {
    return (
      <Link
        to={`/companies/${preview.existing_company_id}`}
        className="rounded-full border border-base-600 px-3 py-1 text-xs font-semibold text-ink-500 hover:text-ink-100"
      >
        Already in your companies
      </Link>
    );
  }
  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={() => onSave(preview)}
        disabled={state.status === "saving"}
        className="rounded-md border border-brand-500 px-4 py-1.5 text-xs font-semibold text-brand-600 transition-colors hover:bg-brand-50 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {state.status === "saving" ? "Saving..." : "Save to companies"}
      </button>
      {state.status === "error" && <span className="text-xs text-status-danger">{state.error}</span>}
    </div>
  );
}

function Detail({ label, children }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-medium text-ink-700">{label}</dt>
      <dd className="mt-1.5">{children}</dd>
    </div>
  );
}

function NotFound({ children = "None found" }) {
  return <span className="text-sm text-ink-700">{children}</span>;
}

function ExternalLink({ href }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="block truncate text-sm font-medium text-brand-600 hover:underline"
    >
      {href.replace(/^https?:\/\//, "")}
    </a>
  );
}

function EmailList({ emails }) {
  if (emails.length === 0) return <NotFound>No email found</NotFound>;
  return (
    <ul className="flex flex-col gap-2">
      {emails.map((e) => (
        <li key={e.email} className="flex flex-wrap items-center gap-2 text-sm font-medium text-ink-100">
          <a href={`mailto:${e.email}`} className="break-all hover:text-brand-600">
            {e.email}
          </a>
          <ValidityBadge isValid={e.is_valid} />
        </li>
      ))}
    </ul>
  );
}

function MockNotice({ preview }) {
  if (!preview.is_mock) return null;
  return (
    <p className="mt-4 rounded-md border border-status-possible/30 bg-status-possible/10 px-3 py-2 text-xs text-status-possible">
      Sample data — no live search provider is configured, so this isn&apos;t a real contact.
    </p>
  );
}

function PersonResult({ preview }) {
  const [saveState, save] = useSave();
  const name = preview.contact_person_name || preview.company_name;
  return (
    <div className="rounded-xl border border-base-700 bg-base-850 p-5 shadow-sm">
      <div className="flex flex-wrap items-center gap-4">
        <Initials name={name} />
        <div className="min-w-0 flex-1">
          <div className="text-base font-semibold text-ink-100">{name}</div>
          <div className="truncate text-sm text-ink-500">
            {preview.contact_person_title
              ? `${preview.contact_person_title} at ${preview.company_name}`
              : preview.company_name}
          </div>
        </div>
        <SaveControl preview={preview} state={saveState} onSave={save} />
      </div>
      <dl className="mt-5 grid grid-cols-1 gap-4 border-t border-base-700 pt-5 sm:grid-cols-2">
        <Detail label="Business email">
          <EmailList emails={preview.emails} />
        </Detail>
        <Detail label="Company website">
          {preview.website ? <ExternalLink href={preview.website} /> : <NotFound>Not found</NotFound>}
        </Detail>
      </dl>
      <MockNotice preview={preview} />
    </div>
  );
}

function CompanyResult({ preview }) {
  const [saveState, save] = useSave();
  return (
    <div className="rounded-xl border border-base-700 bg-base-850 p-5 shadow-sm">
      <div className="flex flex-wrap items-center gap-4">
        <span
          aria-hidden="true"
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600"
        >
          <Icon name="building" className="h-5 w-5" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-base font-semibold text-ink-100">{preview.company_name}</div>
          {preview.website && <ExternalLink href={preview.website} />}
        </div>
        <SaveControl preview={preview} state={saveState} onSave={save} />
      </div>
      <dl className="mt-5 grid grid-cols-1 gap-5 border-t border-base-700 pt-5 sm:grid-cols-2">
        <Detail label={`Emails (${preview.emails.length})`}>
          <EmailList emails={preview.emails} />
        </Detail>
        <Detail label={`Phone numbers (${preview.phones.length})`}>
          {preview.phones.length === 0 ? (
            <NotFound />
          ) : (
            <ul className="flex flex-col gap-2">
              {preview.phones.map((p) => (
                <li key={p.phone} className="flex flex-wrap items-center gap-2 text-sm font-medium text-ink-100">
                  <a href={`tel:${p.phone}`} className="hover:text-brand-600">
                    {p.phone}
                  </a>
                  <ValidityBadge isValid={p.is_valid} />
                </li>
              ))}
            </ul>
          )}
        </Detail>
        <Detail label="Contact page">
          {preview.contact_page_url ? <ExternalLink href={preview.contact_page_url} /> : <NotFound />}
        </Detail>
        <Detail label="Social profiles">
          {preview.social_profiles.length === 0 ? (
            <NotFound />
          ) : (
            <div className="flex flex-wrap gap-2">
              {preview.social_profiles.map((s) => (
                <a
                  key={s.platform}
                  href={s.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-full border border-base-600 px-2.5 py-0.5 text-xs font-medium text-ink-300 hover:border-brand-500 hover:text-brand-600"
                >
                  {PLATFORM_NAMES[s.platform] ?? s.platform}
                </a>
              ))}
            </div>
          )}
        </Detail>
      </dl>
      <MockNotice preview={preview} />
    </div>
  );
}

function LookupOutcome({ lookup, render }) {
  if (lookup.status === "loading") {
    return (
      <div
        role="status"
        className="mt-6 flex items-center gap-3 rounded-xl border border-base-700 bg-base-900 p-5 text-sm text-ink-500"
      >
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
        Looking this up — this can take a few seconds…
      </div>
    );
  }
  if (lookup.status === "error") {
    return (
      <div
        role="alert"
        className="mt-6 rounded-lg border border-status-danger/30 bg-status-danger/10 px-4 py-3 text-sm text-status-danger"
      >
        {lookup.error}
      </div>
    );
  }
  if (lookup.status === "done") {
    // Keyed by attempt so a new lookup resets the result card's save state.
    return (
      <div key={lookup.attempt} className="mt-6">
        {render(lookup.result)}
      </div>
    );
  }
  return null;
}

function HelpText({ children }) {
  return <p className="mt-2 text-xs leading-relaxed text-ink-700">{children}</p>;
}

function LinkedInPanel() {
  const [url, setUrl] = useState("");
  const [hint, setHint] = useState(null);
  const [lookup, run] = useLookup();

  function handleSubmit(e) {
    e.preventDefault();
    const value = url.trim();
    if (!LINKEDIN_PROFILE_RE.test(value)) {
      setHint("Paste a LinkedIn profile link — it looks like linkedin.com/in/their-name.");
      return;
    }
    setHint(null);
    run(() => api.discoverFromUrl(withScheme(value)));
  }

  return (
    <>
      <form onSubmit={handleSubmit} className="flex flex-col gap-2 sm:flex-row">
        <label htmlFor="linkedin-url" className="sr-only">
          LinkedIn profile link
        </label>
        <div className="relative flex-1">
          <Icon
            name="link"
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-700"
          />
          <input
            id="linkedin-url"
            type="text"
            inputMode="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="linkedin.com/in/their-name"
            className={`${inputClasses} pl-9`}
          />
        </div>
        <button type="submit" disabled={lookup.status === "loading"} className={submitButton}>
          {lookup.status === "loading" ? "Finding..." : "Find email"}
        </button>
      </form>
      {hint && (
        <p role="alert" className="mt-2 text-sm text-status-danger">
          {hint}
        </p>
      )}
      <HelpText>
        PetroLead reads the profile&apos;s public search listing — it never logs into LinkedIn —
        and only returns the contact when a business email is found.
      </HelpText>
      <LookupOutcome lookup={lookup} render={(preview) => <PersonResult preview={preview} />} />
    </>
  );
}

function NamePanel() {
  const [fullName, setFullName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [lookup, run] = useLookup();

  function handleSubmit(e) {
    e.preventDefault();
    run(async () => {
      const { results } = await api.bulkContactLookup([
        { full_name: fullName.trim(), company_name: companyName.trim() },
      ]);
      const [result] = results;
      if (!result.success) throw new ApiError(result.error || "No business email found.", 422);
      return result.preview;
    });
  }

  return (
    <>
      <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_1fr_auto]">
        <label className="flex flex-col gap-1">
          <span className="sr-only">Full name</span>
          <input
            required
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Full name — e.g. Michael Jones"
            className={inputClasses}
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="sr-only">Company name</span>
          <input
            required
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            placeholder="Company — e.g. Falcon Petroleum Trading"
            className={inputClasses}
          />
        </label>
        <button type="submit" disabled={lookup.status === "loading"} className={submitButton}>
          {lookup.status === "loading" ? "Finding..." : "Find email"}
        </button>
      </form>
      <HelpText>
        PetroLead finds the company&apos;s official website from real search results, then looks
        up a confident business email for the person.
      </HelpText>
      <LookupOutcome lookup={lookup} render={(preview) => <PersonResult preview={preview} />} />
    </>
  );
}

function WebsitePanel() {
  const [url, setUrl] = useState("");
  const [lookup, run] = useLookup();

  function handleSubmit(e) {
    e.preventDefault();
    const value = url.trim();
    if (!value) return;
    run(() => api.discoverFromUrl(withScheme(value)));
  }

  return (
    <>
      <form onSubmit={handleSubmit} className="flex flex-col gap-2 sm:flex-row">
        <label htmlFor="website-url" className="sr-only">
          Company website
        </label>
        <div className="relative flex-1">
          <Icon
            name="globe"
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-700"
          />
          <input
            id="website-url"
            type="text"
            inputMode="url"
            required
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="company-website.com"
            className={`${inputClasses} pl-9`}
          />
        </div>
        <button type="submit" disabled={lookup.status === "loading"} className={submitButton}>
          {lookup.status === "loading" ? "Extracting..." : "Extract contacts"}
        </button>
      </form>
      <HelpText>
        Reads the company&apos;s homepage and contact page for published business emails, phone
        numbers and social profiles. Social-media company pages are login-gated and usually
        come back empty — use the company&apos;s own website.
      </HelpText>
      <LookupOutcome
        lookup={lookup}
        render={(preview) =>
          preview.contact_person_name ? (
            <PersonResult preview={preview} />
          ) : (
            <CompanyResult preview={preview} />
          )
        }
      />
    </>
  );
}

function parseBulkLine(line) {
  if (/^https?:\/\//i.test(line) || LINKEDIN_PROFILE_RE.test(line)) {
    return { url: withScheme(line) };
  }
  const [fullName, ...rest] = line.split(",");
  const companyName = rest.join(",").trim();
  if (!fullName.trim() || !companyName) return null;
  return { full_name: fullName.trim(), company_name: companyName };
}

function BulkRow({ result }) {
  const [saveState, save] = useSave();
  if (!result.success) {
    return (
      <li className="rounded-lg border border-status-danger/30 bg-status-danger/5 px-4 py-3">
        <div className="truncate text-sm font-medium text-ink-300">
          {result.input_url || `${result.input_full_name}, ${result.input_company_name}`}
        </div>
        <div className="mt-0.5 text-xs text-status-danger">{result.error}</div>
      </li>
    );
  }
  const { preview } = result;
  const name = preview.contact_person_name || preview.company_name;
  return (
    <li className="flex flex-wrap items-center gap-3 rounded-lg border border-base-700 bg-base-850 px-4 py-3">
      <Initials name={name} className="h-9 w-9 text-xs" />
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-semibold text-ink-100">
          {name}
          {preview.contact_person_title && (
            <span className="font-normal text-ink-500"> — {preview.contact_person_title}</span>
          )}
        </div>
        <div className="truncate text-xs text-ink-500">{preview.company_name}</div>
        {preview.emails[0] ? (
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs font-medium text-ink-100">
            {preview.emails[0].email}
            <ValidityBadge isValid={preview.emails[0].is_valid} />
          </div>
        ) : (
          <div className="mt-1 text-xs text-ink-700">No email found</div>
        )}
      </div>
      <SaveControl preview={preview} state={saveState} onSave={save} />
    </li>
  );
}

function BulkPanel() {
  const [text, setText] = useState("");
  const [lookup, run] = useLookup();

  const lines = text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
  const items = lines.map(parseBulkLine).filter(Boolean);
  const skipped = lines.length - items.length;
  const tooMany = items.length > MAX_BULK_ITEMS;

  function handleSubmit(e) {
    e.preventDefault();
    if (items.length === 0 || tooMany) return;
    run(async () => (await api.bulkContactLookup(items)).results);
  }

  return (
    <>
      <form onSubmit={handleSubmit}>
        <label htmlFor="bulk-lines" className="text-sm font-semibold text-ink-100">
          People to look up
        </label>
        <p className="mt-1 text-xs text-ink-500">
          One per line — a LinkedIn profile link, or <code className="rounded bg-base-900 px-1">Full Name, Company Name</code>.
        </p>
        <textarea
          id="bulk-lines"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={7}
          placeholder={"linkedin.com/in/janedoe\nMichael Jones, Falcon Petroleum Trading"}
          className={`${inputClasses} mt-3 font-mono`}
        />
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <span className={`text-xs ${tooMany ? "font-semibold text-status-danger" : "text-ink-500"}`}>
            {items.length} of {MAX_BULK_ITEMS} people
            {skipped > 0 && ` · ${skipped} line${skipped === 1 ? "" : "s"} not recognized`}
          </span>
          <button
            type="submit"
            disabled={lookup.status === "loading" || items.length === 0 || tooMany}
            className={submitButton}
          >
            {lookup.status === "loading" ? "Looking up..." : "Look up all"}
          </button>
        </div>
      </form>
      <LookupOutcome
        lookup={lookup}
        render={(results) => (
          <div>
            <div className="text-sm font-semibold text-ink-100">
              {results.filter((r) => r.success).length} of {results.length} found
            </div>
            <ul className="mt-3 flex flex-col gap-2">
              {results.map((result, index) => (
                <BulkRow key={index} result={result} />
              ))}
            </ul>
          </div>
        )}
      />
    </>
  );
}

const PANELS = { linkedin: LinkedInPanel, name: NamePanel, website: WebsitePanel, bulk: BulkPanel };

export default function EmailFinder() {
  const [params, setParams] = useSearchParams();
  const requested = params.get("tab");
  const active = PANELS[requested] ? requested : "linkedin";
  const Panel = PANELS[active];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-100">Email Finder</h1>
        <p className="mt-1 text-sm text-ink-500">
          Find a person&apos;s business email from their LinkedIn profile or their name and
          company — or pull every contact a company website publishes.
        </p>
      </div>

      <div className="rounded-2xl border border-base-700 bg-base-850 shadow-sm">
        <div
          role="tablist"
          aria-label="Lookup type"
          className="flex gap-1 overflow-x-auto border-b border-base-700 px-3 pt-2"
        >
          {TABS.map((tab) => (
            <button
              key={tab.id}
              id={`tab-${tab.id}`}
              type="button"
              role="tab"
              aria-selected={active === tab.id}
              aria-controls="email-finder-panel"
              onClick={() => setParams({ tab: tab.id }, { replace: true })}
              className={`-mb-px inline-flex items-center gap-2 whitespace-nowrap border-b-2 px-4 py-3 text-sm font-semibold transition-colors ${
                active === tab.id
                  ? "border-brand-500 text-brand-600"
                  : "border-transparent text-ink-500 hover:text-ink-100"
              }`}
            >
              <Icon name={tab.icon} className="h-4 w-4" />
              {tab.label}
            </button>
          ))}
        </div>
        <div
          id="email-finder-panel"
          role="tabpanel"
          aria-labelledby={`tab-${active}`}
          className="p-5 sm:p-6"
        >
          <Panel key={active} />
        </div>
      </div>
    </div>
  );
}
