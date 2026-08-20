import { useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";

function parseLine(line) {
  const trimmed = line.trim();
  if (!trimmed) return null;
  if (/^https?:\/\//i.test(trimmed)) {
    return { url: trimmed };
  }
  const [fullName, ...rest] = trimmed.split(",");
  const companyName = rest.join(",").trim();
  if (!fullName?.trim() || !companyName) return null;
  return { full_name: fullName.trim(), company_name: companyName };
}

export default function BulkContactLookup() {
  const [text, setText] = useState("");
  const [status, setStatus] = useState("idle"); // idle | loading | done | error
  const [error, setError] = useState(null);
  const [results, setResults] = useState([]);
  const [savedState, setSavedState] = useState({});

  async function handleSubmit(e) {
    e.preventDefault();
    const lines = text
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);
    const items = lines.map(parseLine).filter(Boolean);
    if (items.length === 0) return;

    setStatus("loading");
    setError(null);
    setResults([]);
    setSavedState({});
    try {
      const response = await api.bulkContactLookup(items);
      setResults(response.results);
      setStatus("done");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
      setStatus("error");
    }
  }

  async function handleSave(index) {
    const preview = results[index].preview;
    setSavedState((s) => ({ ...s, [index]: { status: "saving" } }));
    try {
      const saved = await api.saveCompany(preview);
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

  return (
    <section className="rounded-xl border border-base-700 bg-base-850 p-6">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-700">
        Bulk Contact Lookup
      </h2>
      <p className="mt-1 text-sm text-ink-500">
        Paste one person per line — a LinkedIn profile link (
        <code className="rounded bg-base-900 px-1">linkedin.com/in/...</code>), or{" "}
        <code className="rounded bg-base-900 px-1">Full Name, Company Name</code>. Up to 25 at
        once. Each line is looked up independently — one failing never affects the rest.
      </p>

      <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={5}
          placeholder={"https://linkedin.com/in/janedoe\nMichael Jones, Falcon Petroleum Trading"}
          className="w-full rounded-md border border-base-600 bg-base-800 px-3 py-2 font-mono text-sm text-ink-100 placeholder:text-ink-700 focus:border-brass-500 focus:outline-none"
        />
        <button
          type="submit"
          disabled={status === "loading"}
          className="self-start rounded-md bg-brass-500 px-5 py-2 text-sm font-semibold text-base-950 transition-colors hover:bg-brass-400 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {status === "loading" ? "Looking up..." : "Look Up All"}
        </button>
      </form>

      {status === "error" && (
        <div className="mt-4 rounded-lg border border-status-danger/30 bg-status-danger/10 px-4 py-3 text-sm text-status-danger">
          {error}
        </div>
      )}

      {status === "done" && results.length > 0 && (
        <div className="mt-4 flex flex-col gap-2">
          <div className="text-xs text-ink-700">
            {results.filter((r) => r.success).length} of {results.length} found
          </div>
          {results.map((result, index) => {
            const saveState = savedState[index] || { status: "idle" };
            return (
              <div
                key={index}
                className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-base-700 bg-base-800/60 px-4 py-3"
              >
                {result.success ? (
                  <>
                    <div>
                      <div className="text-sm font-medium text-ink-100">
                        {result.preview.contact_person_name || result.preview.company_name}
                        {result.preview.contact_person_title && (
                          <span className="font-normal text-ink-500">
                            {" "}
                            — {result.preview.contact_person_title}
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-ink-500">
                        {result.preview.company_name}
                        {result.preview.website &&
                          ` · ${result.preview.website.replace(/^https?:\/\//, "")}`}
                      </div>
                      {result.preview.emails.length > 0 ? (
                        <div className="mt-1 text-xs text-status-high">
                          {result.preview.emails[0].email}
                        </div>
                      ) : (
                        <div className="mt-1 text-xs text-ink-700">No email found</div>
                      )}
                    </div>
                    {saveState.status === "saved" ? (
                      <span className="rounded-full border border-status-high/30 bg-status-high/15 px-2.5 py-1 text-xs font-medium text-status-high">
                        Saved
                      </span>
                    ) : result.preview.already_saved ? (
                      <Link
                        to={`/companies/${result.preview.existing_company_id}`}
                        className="rounded-full border border-base-600 bg-base-800 px-2.5 py-1 text-xs font-medium text-ink-500 hover:text-ink-100"
                      >
                        Already saved
                      </Link>
                    ) : (
                      <button
                        type="button"
                        onClick={() => handleSave(index)}
                        disabled={saveState.status === "saving"}
                        className="rounded-md border border-brass-500/60 px-3 py-1.5 text-xs font-semibold text-brass-300 transition-colors hover:bg-brass-500/15 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {saveState.status === "saving" ? "Saving..." : "Save"}
                      </button>
                    )}
                  </>
                ) : (
                  <>
                    <div className="text-sm text-ink-500">
                      {result.input_url || `${result.input_full_name}, ${result.input_company_name}`}
                    </div>
                    <span className="text-xs text-status-danger">{result.error}</span>
                  </>
                )}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
