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
