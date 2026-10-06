import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import StatCard from "../components/StatCard";

function n(value) {
  return (value ?? 0).toLocaleString();
}

export default function AdminDirectory() {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [starting, setStarting] = useState(false);

  async function load() {
    setError(null);
    try {
      setStats(await api.adminDirectory());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load the directory.");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function startCrawl() {
    setStarting(true);
    setError(null);
    try {
      const result = await api.adminStartCrawl();
      setNotice(result.detail);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start the crawler.");
    } finally {
      setStarting(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink-100">Contact directory</h1>
          <p className="mt-1 max-w-2xl text-sm text-ink-500">
            Every email any search has found, shared across all accounts and checked before any
            paid lookup. The crawler reads queued company websites twice an hour to grow it
            between searches.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={load}
            className="rounded-md border border-base-600 px-3 py-2 text-sm font-semibold text-ink-300 transition-colors hover:border-brand-500 hover:text-brand-600"
          >
            Refresh
          </button>
          <button
            type="button"
            onClick={startCrawl}
            disabled={starting}
            className="rounded-md bg-brand-500 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {starting ? "Starting..." : "Crawl now"}
          </button>
        </div>
      </div>

      {error && (
        <div
          role="alert"
          className="rounded-lg border border-status-danger/30 bg-status-danger/10 px-4 py-3 text-sm text-status-danger"
        >
          {error}
        </div>
      )}
      {notice && (
        <div className="rounded-lg border border-status-high/30 bg-status-high/10 px-4 py-3 text-sm text-ink-300">
          {notice}
        </div>
      )}

      {!stats && !error && <div className="text-sm text-ink-500">Loading...</div>}

      {stats && (
        <>
          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-700">
              Contacts
            </h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard label="Emails" value={n(stats.contacts)} accent />
              <StatCard
                label="With a name"
                value={n(stats.named_contacts)}
                hint="Linked to a specific person"
              />
              <StatCard
                label="Confirmed"
                value={n(stats.confirmed_contacts)}
                hint="Mailbox checked and accepted"
              />
              <StatCard
                label="Companies"
                value={n(stats.company_domains)}
                hint={`${n(stats.domains_with_known_format)} with a known email format`}
              />
            </div>
          </section>

          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-700">
              Crawler
            </h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard label="Sites queued" value={n(stats.sites_queued)} />
              <StatCard label="Due now" value={n(stats.sites_due)} />
              <StatCard label="Read in last 24h" value={n(stats.sites_crawled_last_24h)} />
              <StatCard
                label="Seed searches"
                value={`${n(stats.seed_searches_run)} / ${n(stats.seed_searches_total)}`}
                hint="Countries and activities covered so far"
              />
            </div>
          </section>
        </>
      )}
    </div>
  );
}
