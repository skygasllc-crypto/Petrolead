import { useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";

function ValidityDot({ isValid }) {
  const color =
    isValid === true ? "bg-status-high" : isValid === false ? "bg-status-low" : "bg-base-600";
  const title = isValid === true ? "Verified" : isValid === false ? "Unverified" : "Check pending";
  return <span className={`inline-block h-1.5 w-1.5 rounded-full ${color}`} title={title} />;
}

export default function QuickUrlLookup() {
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState("idle"); // idle | loading | done | error
  const [error, setError] = useState(null);
  const [company, setCompany] = useState(null);

  // idle | saving | saved | error — separate from the lookup's own status
  const [saveStatus, setSaveStatus] = useState("idle");
  const [saveError, setSaveError] = useState(null);
  const [savedId, setSavedId] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!url.trim()) return;
    setStatus("loading");
    setError(null);
    setCompany(null);
    setSaveStatus("idle");
    setSaveError(null);
    setSavedId(null);
    try {
      const result = await api.discoverFromUrl(url.trim());
      setCompany(result);
      setStatus("done");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
      setStatus("error");
    }
  }

  async function handleSave() {
    if (!company) return;
    setSaveStatus("saving");
    setSaveError(null);
    try {
      const saved = await api.saveCompany(company);
      setSavedId(saved.id);
      setSaveStatus("saved");
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : "Could not save.");
      setSaveStatus("error");
    }
  }

  return (
    <section className="rounded-xl border border-base-700 bg-base-850 p-6">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-700">
        Quick Lookup: Paste a Link
      </h2>
      <p className="mt-1 text-sm text-ink-500">
        Paste a company website and PetroLead will fetch whatever contact page, social links,
        business emails, and phone numbers are publicly on it. A personal LinkedIn profile link
        (<code className="rounded bg-base-900 px-1">linkedin.com/in/...</code>) works too — that
        page itself is login-gated, so instead PetroLead looks up whatever public snippet a
        search engine has indexed for it (name, title, current company).
      </p>

      <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-2 sm:flex-row">
        <input
          type="url"
          required
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://example-petroleum.com"
          className="w-full rounded-md border border-base-600 bg-base-800 px-3 py-2 text-sm text-ink-100 placeholder:text-ink-700 focus:border-brass-500 focus:outline-none"
        />
        <button
          type="submit"
          disabled={status === "loading"}
          className="shrink-0 rounded-md bg-brass-500 px-5 py-2 text-sm font-semibold text-base-950 transition-colors hover:bg-brass-400 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {status === "loading" ? "Fetching..." : "Fetch Contact Info"}
        </button>
      </form>

      <p className="mt-2 text-xs text-ink-700">
        Company websites work best. Raw LinkedIn/Facebook <em>company</em> page links usually
        come back empty — those pages are login-gated and PetroLead never bypasses that. A
        LinkedIn <em>personal profile</em> link (<code className="rounded bg-base-900 px-1">
          /in/...
        </code>) only works if a public search snippet exists for it and mentions a company.
      </p>

      {status === "error" && (
        <div className="mt-4 rounded-lg border border-status-danger/30 bg-status-danger/10 px-4 py-3 text-sm text-status-danger">
          {error}
        </div>
      )}

      {status === "done" && company && (
        <div className="mt-4 rounded-lg border border-base-700 bg-base-800/60 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              {savedId ? (
                <Link
                  to={`/companies/${savedId}`}
                  className="font-medium text-ink-100 hover:text-brass-400"
                >
                  {company.company_name}
                </Link>
              ) : (
                <span className="font-medium text-ink-100">{company.company_name}</span>
              )}
              {company.website && (
                <a
                  href={company.website}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block truncate text-xs text-teal-400 hover:underline"
                >
                  {company.website}
                </a>
              )}
            </div>

            {saveStatus === "saved" ? (
              <span className="rounded-full border border-status-high/30 bg-status-high/15 px-2.5 py-0.5 text-[10px] font-medium text-status-high">
                Saved
              </span>
            ) : company.already_saved ? (
              <Link
                to={`/companies/${company.existing_company_id}`}
                className="rounded-full border border-base-600 bg-base-800 px-2.5 py-0.5 text-[10px] font-medium text-ink-500 hover:text-ink-100"
              >
                Already saved
              </Link>
            ) : (
              <div className="flex flex-col items-end gap-1">
                <button
                  type="button"
                  onClick={handleSave}
                  disabled={saveStatus === "saving"}
                  className="rounded-md bg-brass-500 px-4 py-1.5 text-xs font-semibold text-base-950 transition-colors hover:bg-brass-400 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {saveStatus === "saving" ? "Saving..." : "Save"}
                </button>
                {saveStatus === "error" && (
                  <span className="text-[10px] text-status-danger">{saveError}</span>
                )}
              </div>
            )}
          </div>

          {company.contact_person_name && (
            <div className="mt-3 rounded-lg border border-brass-500/30 bg-brass-500/10 px-3 py-2">
              <div className="text-xs text-ink-700">Contact person (from public LinkedIn snippet)</div>
              <div className="text-sm font-medium text-ink-100">
                {company.contact_person_name}
                {company.contact_person_title && (
                  <span className="font-normal text-ink-500"> — {company.contact_person_title}</span>
                )}
              </div>
            </div>
          )}

          <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <div className="text-xs text-ink-700">Contact page</div>
              {company.contact_page_url ? (
                <a
                  href={company.contact_page_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block truncate text-sm text-teal-400 hover:underline"
                >
                  {company.contact_page_url}
                </a>
              ) : (
                <div className="text-sm text-ink-700">None found</div>
              )}
            </div>
            <div>
              <div className="text-xs text-ink-700">Social profiles</div>
              {company.social_profiles.length === 0 ? (
                <div className="text-sm text-ink-700">None found</div>
              ) : (
                <ul className="mt-1 flex flex-col gap-1">
                  {company.social_profiles.map((s) => (
                    <li key={s.platform}>
                      <a
                        href={s.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm capitalize text-teal-400 hover:underline"
                      >
                        {s.platform}
                      </a>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div>
              <div className="text-xs text-ink-700">Emails</div>
              {company.emails.length === 0 ? (
                <div className="text-sm text-ink-700">None found</div>
              ) : (
                <ul className="mt-1 flex flex-col gap-1">
                  {company.emails.map((e) => (
                    <li key={e.email} className="flex items-center gap-1.5 text-sm text-ink-100">
                      <ValidityDot isValid={e.is_valid} />
                      {e.email}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div>
              <div className="text-xs text-ink-700">Phones</div>
              {company.phones.length === 0 ? (
                <div className="text-sm text-ink-700">None found</div>
              ) : (
                <ul className="mt-1 flex flex-col gap-1">
                  {company.phones.map((p) => (
                    <li key={p.phone} className="flex items-center gap-1.5 text-sm text-ink-100">
                      <ValidityDot isValid={p.is_valid} />
                      {p.phone}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
