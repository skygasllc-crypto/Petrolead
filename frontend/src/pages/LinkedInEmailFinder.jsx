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
  Initials,
  MarketingPage,
  ProductHero,
  StatusPill,
  StepsSection,
} from "../components/marketing/ProductBlocks";
import { SAMPLE_CONTACTS } from "../components/marketing/sampleData";

const APP_PATH = "/email-finder";

const FAQS = [
  {
    q: "How do I find someone's email from their LinkedIn profile?",
    a: "Copy the link to their profile (it looks like linkedin.com/in/their-name) and paste it into Email Finder. PetroLead identifies the person and their employer, finds the company's website and looks up their business email.",
  },
  {
    q: "Does PetroLead log into or scrape LinkedIn?",
    a: "No. PetroLead never opens LinkedIn pages or uses a LinkedIn account. It works only from what search engines publicly list for a profile — the person's name, headline and employer.",
  },
  {
    q: "Why didn't a profile return an email?",
    a: "An email can't always be found — the profile's public listing may not name a current employer, the company's website may not be locatable, or there may be no confident match. You still get the person's name, title and profile link, and no credit is spent. If you know where they work, try the lookup by name and company instead.",
  },
  {
    q: "Can I find LinkedIn emails in bulk?",
    a: "Yes. Bulk lookup takes up to 25 lines at a time — any mix of profile links and \"Full Name, Company Name\" lines. Each line is looked up independently, so one miss never stops the rest.",
  },
  {
    q: "How accurate are the emails?",
    a: "Every email PetroLead returns is labeled Verified, Unverified or Check pending, so you know which addresses are safe to use before you reach out. Lookups that don't find a business email return nothing rather than a guess.",
  },
  {
    q: "Does LinkedIn show email addresses?",
    a: "Only to a person's 1st-degree connections, and only if that person has chosen to share it. For everyone else you need a business email finder like PetroLead.",
  },
  {
    q: "Can I save and export the contacts I find?",
    a: "Yes. Save any result to your company list in one click, then export companies or emails as CSV or Excel.",
  },
  {
    q: "Is it legal to find emails from LinkedIn profiles?",
    a: "PetroLead only uses publicly available business information and never bypasses LinkedIn's login. You're responsible for contacting people in line with the laws that apply to you, such as GDPR and anti-spam rules.",
  },
];

const STEPS = [
  {
    title: "Create your PetroLead account",
    body: "Sign up in under a minute — no browser extension to install.",
    link: { label: "Create your account", to: "/register" },
  },
  {
    title: "Copy a LinkedIn profile link",
    body: "Open the person's profile and copy the address from your browser — it looks like linkedin.com/in/their-name.",
  },
  {
    title: "Paste it into Email Finder",
    body: "Paste the link and click Find email. PetroLead returns the person's name, title, company and business email.",
  },
  {
    title: "Save or export your results",
    body: "Save the contact to your company list, then export your list to CSV or Excel whenever you're ready.",
  },
];

function ContactsTableMock() {
  return (
    <BrowserFrame url="app.petrolead.org/emails">
      <div className="flex">
        <div className="hidden w-44 shrink-0 border-r border-base-700 p-3 sm:block">
          <div className="text-[11px] font-semibold text-ink-700">Lists</div>
          <div className="mt-3 rounded-md bg-brand-500 px-2 py-1.5 text-center text-[11px] font-semibold text-white">
            + New search
          </div>
          {["All contacts", "Refinery buyers", "Bunker suppliers", "Lubricant distributors"].map(
            (l, i) => (
              <div
                key={l}
                className={`mt-1.5 rounded-md px-2 py-1.5 text-[11px] ${
                  i === 0 ? "bg-brand-50 font-semibold text-brand-600" : "text-ink-500"
                }`}
              >
                {l}
              </div>
            ),
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="border-b border-base-700 px-4 py-2.5 text-[11px] font-semibold text-ink-100">
            All contacts{" "}
            <span className="font-normal text-ink-700">({SAMPLE_CONTACTS.length} results)</span>
          </div>
          {/* Fixed layout so long emails truncate instead of pushing Status off the edge. */}
          <table className="w-full table-fixed text-left text-[11px]">
            <colgroup>
              <col />
              <col className="w-[36%]" />
              <col className="w-[6.75rem]" />
            </colgroup>
            <thead className="text-[10px] uppercase tracking-wide text-ink-700">
              <tr className="border-b border-base-700">
                <th className="px-3 py-2 font-medium sm:px-4">Name</th>
                <th className="px-2 py-2 font-medium">Email</th>
                <th className="px-3 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {SAMPLE_CONTACTS.map(([name, company, email, status]) => (
                <tr key={email} className="border-b border-base-700 last:border-0">
                  <td className="overflow-hidden px-3 py-2 sm:px-4">
                    <span className="flex items-center gap-2">
                      <Initials name={name} className="h-6 w-6 text-[9px]" />
                      <span className="min-w-0">
                        <span className="block truncate font-medium text-ink-100">{name}</span>
                        <span className="block truncate text-[10px] text-ink-700">{company}</span>
                      </span>
                    </span>
                  </td>
                  <td className="truncate px-2 py-2 text-ink-300">{email}</td>
                  <td className="px-3 py-2">
                    <StatusPill status={status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </BrowserFrame>
  );
}

function QuickLookupMock() {
  const [name, company, email, status, title] = SAMPLE_CONTACTS[0];
  return (
    <BrowserFrame url="app.petrolead.org/email-finder">
      <div className="p-5">
        <div className="text-xs font-semibold uppercase tracking-wide text-ink-700">
          LinkedIn profile
        </div>
        <div className="mt-3 flex gap-2">
          <div className="flex min-w-0 flex-1 items-center gap-2 rounded-md border border-brand-500 bg-base-850 px-3 py-2 text-xs text-ink-100">
            <Icon name="link" className="h-3.5 w-3.5 shrink-0 text-ink-700" />
            <span className="truncate">linkedin.com/in/amira-haddad</span>
          </div>
          <span className="rounded-md bg-brand-500 px-3 py-2 text-xs font-semibold text-white">
            Find email
          </span>
        </div>
        <div className="mt-4 rounded-xl border border-base-700 bg-base-900 p-4">
          <div className="flex items-center gap-3">
            <Initials name={name} className="h-10 w-10 text-xs" />
            <div className="min-w-0">
              <div className="text-sm font-semibold text-ink-100">{name}</div>
              <div className="truncate text-xs text-ink-500">
                {title} at {company}
              </div>
            </div>
            <span className="ml-auto rounded-md border border-brand-500/60 px-3 py-1 text-xs font-semibold text-brand-600">
              Save
            </span>
          </div>
          <dl className="mt-4 grid grid-cols-1 gap-3 border-t border-base-700 pt-4 text-xs sm:grid-cols-2">
            <div>
              <dt className="text-ink-700">Business email</dt>
              <dd className="mt-1 flex flex-wrap items-center gap-2 font-medium text-ink-100">
                {email} <StatusPill status={status} />
              </dd>
            </div>
            <div>
              <dt className="text-ink-700">Company website</dt>
              <dd className="mt-1 font-medium text-brand-600">gulfstar.example</dd>
            </div>
            <div>
              <dt className="text-ink-700">Company</dt>
              <dd className="mt-1 font-medium text-ink-100">{company}</dd>
            </div>
            <div>
              <dt className="text-ink-700">Source</dt>
              <dd className="mt-1 font-medium text-ink-100">Public search listing</dd>
            </div>
          </dl>
        </div>
      </div>
    </BrowserFrame>
  );
}

function BulkLookupMock() {
  const rows = SAMPLE_CONTACTS.slice(1, 4);
  return (
    <BrowserFrame url="app.petrolead.org/email-finder?tab=bulk">
      <div className="p-5">
        <div className="text-xs font-semibold uppercase tracking-wide text-ink-700">Bulk lookup</div>
        <div className="mt-3 rounded-md border border-base-600 bg-base-850 px-3 py-2 font-mono text-[11px] leading-6 text-ink-300">
          <div>linkedin.com/in/lars-johansen</div>
          <div>Priya Raman, Coastline Lubricants</div>
          <div>linkedin.com/in/diego-morales</div>
          <div>linkedin.com/in/j-smith-energy</div>
        </div>
        <div className="mt-4 text-[11px] text-ink-700">3 of 4 found</div>
        <div className="mt-2 flex flex-col gap-2">
          {rows.map(([name, company, email, status]) => (
            <div
              key={email}
              className="flex items-center gap-3 rounded-lg border border-base-700 bg-base-900 px-3 py-2.5"
            >
              <Initials name={name} />
              <div className="min-w-0 flex-1">
                <div className="truncate text-xs font-semibold text-ink-100">
                  {name} <span className="font-normal text-ink-500">· {company}</span>
                </div>
                <div className="truncate text-[11px] text-status-high">{email}</div>
              </div>
              <StatusPill status={status} />
            </div>
          ))}
          <div className="rounded-lg border border-status-danger/30 bg-status-danger/5 px-3 py-2.5 text-[11px]">
            <span className="text-ink-500">linkedin.com/in/j-smith-energy</span>
            <span className="mt-0.5 block text-status-danger">No business email found — skipped</span>
          </div>
        </div>
      </div>
    </BrowserFrame>
  );
}

function NameCompanyMock() {
  const [name, company, email, status, title] = SAMPLE_CONTACTS[6];
  const steps = [
    ["Company identified", company],
    ["Official website found", "rhinepetro.example"],
    ["Business email found", email],
  ];
  return (
    <BrowserFrame url="app.petrolead.org/email-finder?tab=name">
      <div className="p-5">
        <div className="text-xs font-semibold uppercase tracking-wide text-ink-700">
          Name + company
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <div className="truncate rounded-md border border-brand-500 bg-base-850 px-3 py-2 text-xs text-ink-100">
            {name}
          </div>
          <div className="truncate rounded-md border border-brand-500 bg-base-850 px-3 py-2 text-xs text-ink-100">
            {company}
          </div>
        </div>
        <ol className="mt-4 flex flex-col gap-3">
          {steps.map(([label, value]) => (
            <li key={label} className="flex items-start gap-3">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-status-high text-white">
                <Icon name="check" className="h-3 w-3" />
              </span>
              <span className="min-w-0 text-xs">
                <span className="block text-ink-700">{label}</span>
                <span className="block truncate font-medium text-ink-100">{value}</span>
              </span>
            </li>
          ))}
        </ol>
        <div className="mt-5 flex items-center gap-3 rounded-xl border border-base-700 bg-base-900 p-3">
          <Initials name={name} className="h-9 w-9 text-xs" />
          <div className="min-w-0 flex-1">
            <div className="text-xs font-semibold text-ink-100">{name}</div>
            <div className="truncate text-[11px] text-ink-500">{title}</div>
          </div>
          <StatusPill status={status} />
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-md border border-base-600 px-3 py-1.5 text-xs font-semibold text-ink-300">
            <Icon name="download" className="h-3.5 w-3.5" /> Export CSV
          </span>
          <span className="rounded-md bg-brand-500 px-3 py-1.5 text-xs font-semibold text-white">
            Save contact
          </span>
        </div>
      </div>
    </BrowserFrame>
  );
}

export default function LinkedInEmailFinder() {
  return (
    <MarketingPage>
      <ProductHero
        title="LinkedIn Email Finder"
        description="Paste any LinkedIn profile link and get that person's verified business email in seconds. Built for the petroleum and energy trade."
        ctaLabel="Start finding emails"
        ctaIcon="link"
        appPath={APP_PATH}
        note="Nothing to install — works from a profile link"
        disclaimer="PetroLead is not affiliated with, endorsed by, or sponsored by LinkedIn or Microsoft. LinkedIn is a registered trademark of LinkedIn Corporation."
        mock={<ContactsTableMock />}
      />

      <FeaturePanel>
        <FeatureBlock
          title="The LinkedIn email finder for individual profiles"
          mock={<QuickLookupMock />}
        >
          <FeatureText>
            Copy a LinkedIn profile link, paste it into PetroLead and get the person&apos;s
            business email. PetroLead identifies their name, title and employer from the
            profile&apos;s public search listing, finds the company&apos;s official website, and
            looks up a confident business email for them — without ever logging into LinkedIn.
          </FeatureText>
          <CheckList
            items={[
              "Name, title and company identified from the public profile listing",
              "Every email labeled Verified, Unverified or Check pending",
              "A credit is spent only when a business email is actually found",
            ]}
          />
          <FeatureCta
            appPath={`${APP_PATH}?tab=linkedin`}
            label="Try it now"
            secondary={{ href: "#how-it-works", label: "Learn how to use it" }}
          />
        </FeatureBlock>

        <Divider />

        <FeatureBlock id="bulk" title="LinkedIn email lookup in bulk" mock={<BulkLookupMock />} reverse>
          <FeatureText>
            Have a list of prospects? Paste up to 25 profile links — or &quot;Full Name, Company
            Name&quot; lines — and PetroLead looks every one up in a single pass. Each line is
            handled independently, so one profile without an email never holds up the rest.
          </FeatureText>
          <CheckList
            items={[
              "Mix profile links and name-and-company lines in one list",
              "Clear reason shown for every contact that was skipped",
              "Save found contacts to your company list in one click",
            ]}
          />
          <FeatureCta appPath={`${APP_PATH}?tab=bulk`} label="See how it's done" variant="soft" />
        </FeatureBlock>

        <Divider />

        <FeatureBlock
          title="Know the name, not the profile?"
          subtitle="Find business emails from a person's name and company"
          mock={<NameCompanyMock />}
        >
          <FeatureText>
            Not every prospect is a click away on LinkedIn. Enter a person&apos;s full name and
            the company they work for, and PetroLead finds the company&apos;s official website
            and looks up their business email — the same way it does for a profile link.
          </FeatureText>
          <FeatureText>
            Every contact you save joins your PetroLead company list, complete with lead score,
            so your outreach list stays organized as it grows.
          </FeatureText>
          <CheckList
            items={[
              "Works from just a full name and company",
              "Company website found from real search results — never guessed",
              "Export contacts to CSV or Excel whenever you need them",
            ]}
          />
          <FeatureCta appPath={`${APP_PATH}?tab=name`} label="Start finding emails" />
        </FeatureBlock>
      </FeaturePanel>

      <StepsSection
        title="How to find someone's email on LinkedIn"
        subtitle="Here's how to use PetroLead's LinkedIn email finder in four steps."
        steps={STEPS}
      />
      <StatsBand />
      <Faq title="Popular questions about LinkedIn Email Finder" items={FAQS} idPrefix="li-faq" />
      <FinalCta
        title="Start finding LinkedIn emails today"
        points={["Paste a profile link", "Every email labeled with its validity", "CSV & Excel export"]}
        appPath={APP_PATH}
      />
    </MarketingPage>
  );
}
