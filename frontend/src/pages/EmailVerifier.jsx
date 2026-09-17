import { useMemo, useState } from "react";
import { api, ApiError } from "../api/client";
import EmailCheckBadge from "../components/EmailCheckBadge";
import Icon from "../components/marketing/Icon";
import {
  EMAIL_CHECK_REASON,
  EMAIL_CHECK_STATUS,
  MAX_VERIFY_EMAILS,
  SAFE_TO_SEND,
} from "../lib/emailChecks";

function parseEmails(text) {
  return text
    .split(/[\s,;]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function SummaryTile({ label, value, tone }) {
  return (
    <div className="rounded-xl border border-base-700 bg-base-850 px-4 py-3">
      <div className="text-xs font-medium text-ink-700">{label}</div>
      <div className={`mt-1 text-2xl font-bold ${tone}`}>{value}</div>
    </div>
  );
}

export default function EmailVerifier() {
  const [text, setText] = useState("");
  const [status, setStatus] = useState("idle"); // idle | loading | done | error
  const [error, setError] = useState(null);
  const [response, setResponse] = useState(null);
  const [copyState, setCopyState] = useState("idle"); // idle | copied | failed

  const emails = useMemo(() => parseEmails(text), [text]);
  const tooMany = emails.length > MAX_VERIFY_EMAILS;

  async function handleSubmit(e) {
    e.preventDefault();
    if (emails.length === 0 || tooMany) return;
    setStatus("loading");
    setError(null);
    setCopyState("idle");
    try {
      setResponse(await api.verifyEmails(emails));
      setStatus("done");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
      setStatus("error");
    }
  }

  // Only addresses confirmed deliverable are worth copying out — the point
  // of verifying is to leave the rest behind.
  const validEmails = response
    ? response.results.filter((r) => r.status === SAFE_TO_SEND)
    : [];

  async function handleCopyValid() {
    try {
      await navigator.clipboard.writeText(validEmails.map((r) => r.email).join("\n"));
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-100">Email Verifier</h1>
        <p className="mt-1 text-sm text-ink-500">
          Check that email addresses are correctly formatted and that their domains can receive
          mail — up to {MAX_VERIFY_EMAILS} at a time.
        </p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="rounded-2xl border border-base-700 bg-base-850 p-5 shadow-sm sm:p-6"
      >
        <label htmlFor="verify-emails" className="text-sm font-semibold text-ink-100">
          Email addresses
        </label>
        <p className="mt-1 text-xs text-ink-500">
          One per line, or separated by commas or spaces.
        </p>
        <textarea
          id="verify-emails"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={8}
          placeholder={"jane.doe@company.com\nsales@company.com"}
          className="mt-3 w-full rounded-md border border-base-600 bg-base-850 px-3 py-2.5 font-mono text-sm text-ink-100 placeholder:text-ink-700 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
        />
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <span className={`text-xs ${tooMany ? "font-semibold text-status-danger" : "text-ink-500"}`}>
            {emails.length} of {MAX_VERIFY_EMAILS} addresses
            {tooMany && ` — remove ${emails.length - MAX_VERIFY_EMAILS} to continue`}
          </span>
          <button
            type="submit"
            disabled={status === "loading" || emails.length === 0 || tooMany}
            className="inline-flex items-center gap-2 rounded-md bg-brand-500 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Icon name="shieldCheck" className="h-4 w-4" />
            {status === "loading" ? "Verifying..." : "Verify emails"}
          </button>
        </div>
      </form>

      {status === "error" && (
        <div
          role="alert"
          className="rounded-lg border border-status-danger/30 bg-status-danger/10 px-4 py-3 text-sm text-status-danger"
        >
          {error}
        </div>
      )}

      {status === "done" && response && (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <SummaryTile label="Deliverable" value={response.deliverable_count} tone="text-status-high" />
            <SummaryTile
              label="Undeliverable"
              value={response.undeliverable_count}
              tone="text-status-danger"
            />
            <SummaryTile label="Risky" value={response.risky_count} tone="text-status-possible" />
            <SummaryTile label="Couldn't check" value={response.unknown_count} tone="text-ink-300" />
          </div>

          {!response.mailbox_checks_available && (
            <p className="rounded-lg border border-status-possible/30 bg-status-possible/10 px-4 py-3 text-sm leading-relaxed text-status-possible">
              No verification provider is configured, so only each domain was checked — not
              whether the individual mailbox exists. That&apos;s why well-formed addresses come
              back <strong className="font-semibold">Risky</strong> rather than Deliverable. Set{" "}
              <code className="rounded bg-base-800 px-1 py-0.5 text-xs">EMAIL_VERIFY_PROVIDER</code>{" "}
              to get mailbox-level verdicts.
            </p>
          )}

          <div className="overflow-hidden rounded-2xl border border-base-700 bg-base-850 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-base-700 px-5 py-3">
              <span className="text-sm font-semibold text-ink-100">
                {response.results.length} {response.results.length === 1 ? "address" : "addresses"} checked
              </span>
              <div className="flex items-center gap-3">
                {copyState === "copied" && (
                  <span className="text-xs font-medium text-status-high" role="status">
                    Copied {validEmails.length} addresses
                  </span>
                )}
                {copyState === "failed" && (
                  <span className="text-xs font-medium text-status-danger" role="status">
                    Couldn&apos;t copy — select them manually
                  </span>
                )}
                <button
                  type="button"
                  onClick={handleCopyValid}
                  disabled={validEmails.length === 0}
                  className="inline-flex items-center gap-1.5 rounded-md border border-base-600 px-3 py-1.5 text-xs font-semibold text-ink-300 hover:border-brand-500 hover:text-brand-600 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Icon name="copy" className="h-3.5 w-3.5" />
                  Copy deliverable addresses
                </button>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[36rem] text-left text-sm">
                <thead className="bg-base-900 text-xs uppercase tracking-wide text-ink-700">
                  <tr>
                    <th className="px-5 py-2.5 font-medium">Email</th>
                    <th className="px-3 py-2.5 font-medium">Result</th>
                    <th className="px-5 py-2.5 font-medium">What it means</th>
                  </tr>
                </thead>
                <tbody>
                  {response.results.map((r) => (
                    <tr key={r.email} className="border-t border-base-700">
                      <td className="px-5 py-3 font-medium text-ink-100">{r.email}</td>
                      <td className="px-3 py-3">
                        <EmailCheckBadge status={r.status} />
                      </td>
                      <td className="px-5 py-3 text-ink-500">
                        {/* The reason is the useful part — why it will bounce,
                            not just that it might. */}
                        {EMAIL_CHECK_REASON[r.reason] ?? EMAIL_CHECK_STATUS[r.status].description}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <p className="text-xs leading-relaxed text-ink-700">
            These checks confirm an address is well-formed and that its domain can receive mail.
            They never contact the mailbox, so they can&apos;t confirm that a specific person&apos;s
            mailbox exists.
          </p>
        </div>
      )}
    </div>
  );
}
