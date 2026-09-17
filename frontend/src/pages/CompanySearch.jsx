import Icon from "../components/marketing/Icon";
import StatsBand from "../components/marketing/StatsBand";
import Faq from "../components/marketing/Faq";
import FinalCta from "../components/marketing/FinalCta";
import {
  BrowserFrame,
  CheckList,
  Divider,
  FeatureBlock,
  FeatureCta,
  FeaturePanel,
  FeatureText,
  MarketingPage,
  ProductHero,
  StepsSection,
} from "../components/marketing/ProductBlocks";
import { SAMPLE_COMPANIES } from "../components/marketing/sampleData";

const APP_PATH = "/discover";

const FAQS = [
  {
    q: "Where does PetroLead find companies?",
    a: "From search-engine results for your filters, companies' own public websites and contact pages, and — if you turn them on — public search listings for LinkedIn and Facebook company pages and B2B directories such as TradeKey and EC21. PetroLead never logs into or scrapes those platforms.",
  },
  {
    q: "Is anything saved automatically?",
    a: "No. A search shows a preview first. Nothing joins your company list until you click Save on a company, or Save All.",
  },
  {
    q: "What happens with companies I've already saved?",
    a: "PetroLead matches every result against your saved companies and marks the ones you already have, so you never end up with duplicates.",
  },
  {
    q: "What is the lead score?",
    a: "Every company gets a relevance rating and a 0–100 lead score, so the strongest leads rise to the top of your list and you can filter out the rest.",
  },
  {
    q: "Can I export the companies I find?",
    a: "Yes. Export your companies — or just their emails — as CSV or Excel, filtered by country, industry, lead score, email availability and more.",
  },
  {
    q: "How do scheduled searches work?",
    a: "Save any search and choose to rerun it daily or weekly. Each run looks for companies you haven't found before, so your pipeline keeps growing without starting over.",
  },
];

const STEPS = [
  {
    title: "Create your PetroLead account",
    body: "Sign up in under a minute and open Company Search.",
    link: { label: "Create your account", to: "/register" },
  },
  {
    title: "Choose your filters",
    body: "Pick a region, country, industry and the products you trade — diesel, jet fuel, LPG, lubricants and more.",
  },
  {
    title: "Review the results",
    body: "Preview every company with its website, contacts and lead score before anything is saved.",
  },
  {
    title: "Save, export or schedule",
    body: "Save the companies you want, export them to CSV or Excel, or schedule the search to rerun.",
  },
];

function ScorePill({ score }) {
  const tone =
    score >= 80
      ? "border-status-high/30 bg-status-high/10 text-status-high"
      : score >= 65
        ? "border-brand-100 bg-brand-50 text-brand-600"
        : "border-status-possible/30 bg-status-possible/10 text-status-possible";
  return (
    <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold ${tone}`}>
      {score}
    </span>
  );
}

function ResultsMock() {
  return (
    <BrowserFrame url="app.petrolead.org/discover">
      <div className="p-4">
        <div className="flex flex-wrap items-center gap-2">
          {["Middle East", "Refining & trading", "Diesel", "Jet A-1"].map((f) => (
            <span
              key={f}
              className="rounded-full border border-brand-100 bg-brand-50 px-2.5 py-1 text-[11px] font-semibold text-brand-600"
            >
              {f}
            </span>
          ))}
          <span className="ml-auto rounded-md bg-brand-500 px-3 py-1.5 text-[11px] font-semibold text-white">
            Search
          </span>
        </div>
        <div className="mt-3 text-[11px] text-ink-700">
          {SAMPLE_COMPANIES.length} companies found · nothing saved yet
        </div>
      </div>
      <table className="w-full table-fixed text-left text-[11px]">
        <colgroup>
          <col />
          <col className="w-[30%]" />
          <col className="w-16" />
          <col className="w-16" />
        </colgroup>
        <thead className="border-y border-base-700 text-[10px] uppercase tracking-wide text-ink-700">
          <tr>
            <th className="px-4 py-2 font-medium">Company</th>
            <th className="px-2 py-2 font-medium">Country</th>
            <th className="px-2 py-2 font-medium">Score</th>
            <th className="px-4 py-2 font-medium">Emails</th>
          </tr>
        </thead>
        <tbody>
          {SAMPLE_COMPANIES.map((c) => (
            <tr key={c.name} className="border-b border-base-700 last:border-0">
              <td className="overflow-hidden px-4 py-2.5">
                <span className="block truncate font-semibold text-ink-100">{c.name}</span>
                <span className="block truncate text-[10px] text-ink-700">{c.products}</span>
              </td>
              <td className="truncate px-2 py-2.5 text-ink-500">{c.country}</td>
              <td className="px-2 py-2.5">
                <ScorePill score={c.score} />
              </td>
              <td className="px-4 py-2.5 font-medium text-ink-300">{c.emails}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </BrowserFrame>
  );
}

function FakeSelect({ label, value }) {
  return (
    <div>
      <div className="text-[10px] font-semibold uppercase tracking-wide text-ink-700">{label}</div>
      <div className="mt-1 flex items-center justify-between rounded-md border border-base-600 bg-base-850 px-3 py-2 text-xs text-ink-100">
        <span className="truncate">{value}</span>
        <Icon name="chevronDown" className="h-3.5 w-3.5 shrink-0 text-ink-700" />
      </div>
    </div>
  );
}

function FiltersMock() {
  const products = [
    ["Diesel", true],
    ["Jet A-1", true],
    ["LPG", false],
    ["Base oils", false],
    ["Bitumen", false],
  ];
  const sources = [
    ["Include social-platform search", true],
    ["Include B2B directory listings", true],
  ];
  return (
    <BrowserFrame url="app.petrolead.org/discover">
      <div className="grid grid-cols-2 gap-3 p-5">
        <FakeSelect label="Region" value="Middle East" />
        <FakeSelect label="Country" value="United Arab Emirates" />
        <FakeSelect label="Industry" value="Refining & trading" />
        <FakeSelect label="Results" value="50" />
        <div className="col-span-2">
          <div className="text-[10px] font-semibold uppercase tracking-wide text-ink-700">Products</div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {products.map(([p, on]) => (
              <span
                key={p}
                className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${
                  on ? "border-brand-500 bg-brand-50 text-brand-600" : "border-base-600 text-ink-500"
                }`}
              >
                {p}
              </span>
            ))}
          </div>
        </div>
        <div className="col-span-2 flex flex-col gap-2">
          {sources.map(([label, on]) => (
            <div
              key={label}
              className="flex items-center gap-2 rounded-md border border-base-700 bg-base-900 px-3 py-2 text-[11px] text-ink-300"
            >
              <span
                className={`flex h-3.5 w-3.5 items-center justify-center rounded-sm ${
                  on ? "bg-brand-500 text-white" : "border border-base-600"
                }`}
              >
                {on && <Icon name="check" className="h-2.5 w-2.5" />}
              </span>
              {label}
            </div>
          ))}
        </div>
      </div>
    </BrowserFrame>
  );
}

function LeadScoreMock() {
  const checks = [
    ["Company website", "gulfstar.example"],
    ["Contact page", "gulfstar.example/contact"],
    ["Business emails", "3 found"],
    ["Phone numbers", "2 found"],
  ];
  return (
    <BrowserFrame url="app.petrolead.org/companies/gulfstar-refining">
      <div className="p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-base font-semibold text-ink-100">Gulfstar Refining</div>
            <div className="text-xs text-ink-500">United Arab Emirates · Diesel, Jet A-1</div>
          </div>
          <span className="whitespace-nowrap rounded-full border border-status-high/30 bg-status-high/10 px-2.5 py-1 text-[11px] font-semibold text-status-high">
            High relevance
          </span>
        </div>
        <div className="mt-5 rounded-xl border border-base-700 bg-base-900 p-4">
          <div className="flex items-baseline justify-between">
            <span className="text-xs font-semibold text-ink-700">Lead score</span>
            <span className="text-2xl font-extrabold text-ink-100">
              92<span className="text-sm font-medium text-ink-700">/100</span>
            </span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-base-700">
            <div className="h-full w-[92%] rounded-full bg-status-high" />
          </div>
        </div>
        <ul className="mt-4 flex flex-col gap-2.5">
          {checks.map(([label, value]) => (
            <li key={label} className="flex items-center gap-3 text-xs">
              <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-status-high text-white">
                <Icon name="check" className="h-3 w-3" />
              </span>
              <span className="text-ink-500">{label}</span>
              <span className="ml-auto truncate font-medium text-ink-100">{value}</span>
            </li>
          ))}
        </ul>
      </div>
    </BrowserFrame>
  );
}

function ScheduleMock() {
  const searches = [
    ["Diesel buyers — Middle East", "Weekly", "4 new companies", true],
    ["Bunker suppliers — Northern Europe", "Daily", "1 new company", true],
    ["LPG importers — Southeast Asia", "Weekly", "No new companies", false],
  ];
  return (
    <BrowserFrame url="app.petrolead.org/scheduled">
      <div className="p-5">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wide text-ink-700">
            Scheduled searches
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-md border border-base-600 px-3 py-1.5 text-[11px] font-semibold text-ink-300">
            <Icon name="download" className="h-3.5 w-3.5" /> Export CSV
          </span>
        </div>
        <ul className="mt-4 flex flex-col gap-2.5">
          {searches.map(([name, frequency, result, hasNew]) => (
            <li
              key={name}
              className="flex items-center gap-3 rounded-lg border border-base-700 bg-base-900 px-3 py-3"
            >
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-500">
                <Icon name="clock" className="h-4 w-4" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-xs font-semibold text-ink-100">{name}</span>
                <span className="block text-[11px] text-ink-500">Runs {frequency.toLowerCase()}</span>
              </span>
              <span
                className={`whitespace-nowrap rounded-full border px-2 py-0.5 text-[10px] font-semibold ${
                  hasNew
                    ? "border-status-high/30 bg-status-high/10 text-status-high"
                    : "border-base-600 text-ink-500"
                }`}
              >
                {result}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </BrowserFrame>
  );
}

export default function CompanySearch() {
  return (
    <MarketingPage>
      <ProductHero
        title="Company Search"
        description="Find petroleum and energy companies by region, country, industry and product — with their websites, business emails and phone numbers in one place."
        ctaLabel="Search companies"
        ctaIcon="search"
        appPath={APP_PATH}
        note="Preview every result before anything is saved"
        mock={<ResultsMock />}
      />

      <FeaturePanel>
        <FeatureBlock
          title="Search the energy trade by what companies actually do"
          mock={<FiltersMock />}
        >
          <FeatureText>
            Filter by region, country and city, by industry, and by the products a company
            trades — diesel, jet fuel, LPG, base oils and more. Add your own keywords to narrow
            things down further.
          </FeatureText>
          <FeatureText>
            PetroLead searches public sources for matching companies, then reads each
            company&apos;s own website for its contact page, business emails and phone numbers.
          </FeatureText>
          <CheckList
            items={[
              "Filters built for petroleum and energy products",
              "Optional LinkedIn, Facebook and B2B directory listings via public search",
              "Already-saved companies flagged, so you never add duplicates",
            ]}
          />
          <FeatureCta
            appPath={APP_PATH}
            label="Start a search"
            secondary={{ href: "#how-it-works", label: "See how it works" }}
          />
        </FeatureBlock>

        <Divider />

        <FeatureBlock
          id="lead-scoring"
          title="Every company scored 0–100"
          mock={<LeadScoreMock />}
          reverse
        >
          <FeatureText>
            Stop guessing which companies to call first. Each result comes with a relevance
            rating and a lead score from 0 to 100, so the strongest prospects rise to the top of
            your list.
          </FeatureText>
          <CheckList
            items={[
              "Relevance rating on every company",
              "Filter your list by minimum lead score",
              "See website, contact page, emails and phones at a glance",
            ]}
          />
          <FeatureCta appPath="/companies" label="View your companies" variant="soft" />
        </FeatureBlock>

        <Divider />

        <FeatureBlock
          id="monitoring"
          title="Save a search. Catch new companies automatically."
          subtitle="Scheduled searches keep your pipeline growing"
          mock={<ScheduleMock />}
        >
          <FeatureText>
            Markets move. Save any search and PetroLead reruns it daily or weekly, looking for
            companies you haven&apos;t found before — so new buyers and suppliers come to you.
          </FeatureText>
          <CheckList
            items={[
              "Rerun any search daily or weekly",
              "Only companies you haven't seen before are added",
              "Export companies or emails to CSV or Excel at any time",
            ]}
          />
          <FeatureCta appPath="/scheduled" label="Schedule a search" />
        </FeatureBlock>
      </FeaturePanel>

      <StepsSection
        title="How to find energy companies with PetroLead"
        subtitle="From filters to a saved, scored lead list in four steps."
        steps={STEPS}
      />
      <StatsBand />
      <Faq title="Popular questions about Company Search" items={FAQS} idPrefix="cs-faq" />
      <FinalCta
        title="Start building your company list today"
        points={["Energy-specific filters", "0–100 lead scores", "CSV & Excel export"]}
        appPath={APP_PATH}
      />
    </MarketingPage>
  );
}
