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
  StatusPill,
  StepsSection,
} from "../components/marketing/ProductBlocks";

const APP_PATH = "/email-finder?tab=website";

const FAQS = [
  {
    q: "Which pages does the Email Extractor read?",
    a: "The company's homepage and its contact page, if it has one. It doesn't crawl the whole site, and it never fetches pages that need a login.",
  },
  {
    q: "Where on the page does it find emails?",
    a: "In email links (mailto:) and in the visible page text. Placeholder and tracking addresses — the kind website builders and analytics tools leave behind — are filtered out.",
  },
  {
    q: "Are the extracted emails verified?",
    a: "Each email is labeled with whether its domain is set up to receive mail. PetroLead never sends a message or contacts the mailbox to check it.",
  },
  {
    q: "Why didn't a website return any contacts?",
    a: "The site may not publish any, may build its pages with JavaScript that isn't in the page itself, or may block automated visits. Social-media company pages are login-gated and usually come back empty — use the company's own website.",
  },
  {
    q: "Does it find phone numbers too?",
    a: "Yes. Phone numbers from phone links and page text are normalized and checked for a valid format, and look-alike numbers such as years or reference codes are ignored.",
  },
  {
    q: "Can I save the company it finds?",
    a: "Yes. Save the result to your company list in one click. If you already have that company, PetroLead tells you instead of adding a duplicate.",
  },
];

const STEPS = [
  {
    title: "Create your PetroLead account",
    body: "Sign up in under a minute and open Email Finder.",
    link: { label: "Create your account", to: "/register" },
  },
  {
    title: "Choose Company website",
    body: "Switch to the Company website tab and paste the company's address — for example company-website.com.",
  },
  {
    title: "Extract contacts",
    body: "PetroLead reads the homepage and contact page and lists every business email, phone number and social profile.",
  },
  {
    title: "Save or export",
    body: "Save the company to your list, then export companies or emails to CSV or Excel.",
  },
];

function ExtractorMock() {
  const emails = [
    ["info@gulfstar.example", "verified"],
    ["sales@gulfstar.example", "verified"],
    ["procurement@gulfstar.example", "verified"],
  ];
  return (
    <BrowserFrame url="app.petrolead.example/email-finder?tab=website">
      <div className="p-5">
        <div className="flex gap-4 border-b border-base-700 text-[11px] font-semibold">
          <span className="pb-2 text-ink-500">LinkedIn profile</span>
          <span className="pb-2 text-ink-500">Name + company</span>
          <span className="-mb-px border-b-2 border-brand-500 pb-2 text-brand-600">Company website</span>
        </div>
        <div className="mt-4 flex gap-2">
          <div className="flex min-w-0 flex-1 items-center gap-2 rounded-md border border-brand-500 bg-base-850 px-3 py-2 text-xs text-ink-100">
            <Icon name="globe" className="h-3.5 w-3.5 shrink-0 text-ink-700" />
            <span className="truncate">gulfstar.example</span>
          </div>
          <span className="whitespace-nowrap rounded-md bg-brand-500 px-3 py-2 text-xs font-semibold text-white">
            Extract contacts
          </span>
        </div>
        <div className="mt-4 rounded-xl border border-base-700 bg-base-900 p-4">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-50 text-brand-600">
              <Icon name="building" className="h-4 w-4" />
            </span>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-semibold text-ink-100">Gulfstar Refining</div>
              <div className="text-xs text-brand-600">gulfstar.example</div>
            </div>
            <span className="rounded-md border border-brand-500/60 px-3 py-1 text-xs font-semibold text-brand-600">
              Save
            </span>
          </div>
          <div className="mt-4 grid grid-cols-1 gap-4 border-t border-base-700 pt-4 text-xs sm:grid-cols-2">
            <div>
              <div className="text-ink-700">Emails (3)</div>
              <ul className="mt-1.5 flex flex-col gap-1.5">
                {emails.map(([email, status]) => (
                  <li key={email} className="flex flex-wrap items-center gap-1.5 font-medium text-ink-100">
                    {email} <StatusPill status={status} />
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <div className="text-ink-700">Phone numbers (2)</div>
              <ul className="mt-1.5 flex flex-col gap-1.5 font-medium text-ink-100">
                <li>+971 4 555 0142</li>
                <li>+971 4 555 0199</li>
              </ul>
              <div className="mt-3 text-ink-700">Social profiles</div>
              <div className="mt-1.5 flex gap-1.5">
                {["LinkedIn", "Facebook"].map((p) => (
                  <span key={p} className="rounded-full border border-base-600 px-2 py-0.5 text-ink-300">
                    {p}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </BrowserFrame>
  );
}

function SourcesMock() {
  const pages = [
    ["Homepage", "gulfstar.example"],
    ["Contact page", "gulfstar.example/contact-us"],
  ];
  const found = [
    ["sales@gulfstar.example", "Email link"],
    ["procurement@gulfstar.example", "Page text"],
    ["info@gulfstar.example", "Email link"],
  ];
  return (
    <BrowserFrame url="app.petrolead.example/email-finder?tab=website">
      <div className="p-5 text-xs">
        <div className="font-semibold uppercase tracking-wide text-ink-700">Pages read</div>
        <ul className="mt-2 flex flex-col gap-2">
          {pages.map(([label, url]) => (
            <li key={label} className="flex items-center gap-3 rounded-lg border border-base-700 bg-base-900 px-3 py-2">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-status-high text-white">
                <Icon name="check" className="h-3 w-3" />
              </span>
              <span className="text-ink-500">{label}</span>
              <span className="ml-auto truncate font-medium text-ink-100">{url}</span>
            </li>
          ))}
        </ul>
        <div className="mt-5 font-semibold uppercase tracking-wide text-ink-700">Business emails found</div>
        <ul className="mt-2 flex flex-col gap-2">
          {found.map(([email, source]) => (
            <li key={email} className="flex items-center justify-between gap-3 rounded-lg border border-base-700 bg-base-850 px-3 py-2">
              <span className="truncate font-medium text-ink-100">{email}</span>
              <span className="whitespace-nowrap rounded-full bg-brand-50 px-2 py-0.5 text-[10px] font-semibold text-brand-600">
                {source}
              </span>
            </li>
          ))}
        </ul>
        <div className="mt-4 rounded-lg border border-dashed border-base-600 px-3 py-2 text-ink-500">
          2 placeholder and tracking addresses ignored
        </div>
      </div>
    </BrowserFrame>
  );
}

function PhonesMock() {
  const numbers = [
    ["+971 4 555 0142", "Phone link", true],
    ["04 555 0199", "Page text · normalized to +971 4 555 0199", true],
    ["1998", "Page text · a year, not a phone number", false],
  ];
  return (
    <BrowserFrame url="app.petrolead.example/email-finder?tab=website">
      <div className="p-5">
        <div className="text-xs font-semibold uppercase tracking-wide text-ink-700">Phone numbers</div>
        <ul className="mt-3 flex flex-col gap-2.5">
          {numbers.map(([number, detail, kept]) => (
            <li
              key={number}
              className={`flex items-center gap-3 rounded-lg border px-3 py-3 ${
                kept ? "border-base-700 bg-base-900" : "border-dashed border-base-600 bg-base-850 opacity-70"
              }`}
            >
              <span
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
                  kept ? "bg-brand-50 text-brand-500" : "bg-base-800 text-ink-700"
                }`}
              >
                <Icon name="phone" className="h-4 w-4" />
              </span>
              <span className="min-w-0 flex-1">
                <span className={`block text-sm font-semibold ${kept ? "text-ink-100" : "text-ink-500 line-through"}`}>
                  {number}
                </span>
                <span className="block truncate text-[11px] text-ink-500">{detail}</span>
              </span>
              {kept ? (
                <span className="whitespace-nowrap rounded-full border border-status-high/30 bg-status-high/10 px-2 py-0.5 text-[10px] font-semibold text-status-high">
                  Valid format
                </span>
              ) : (
                <span className="whitespace-nowrap rounded-full border border-base-600 px-2 py-0.5 text-[10px] font-semibold text-ink-500">
                  Ignored
                </span>
              )}
            </li>
          ))}
        </ul>
      </div>
    </BrowserFrame>
  );
}

export default function EmailExtractor() {
  return (
    <MarketingPage>
      <ProductHero
        title="Email Extractor"
        description="Paste a company's website and pull every business email, phone number, contact page and social profile it publishes — in seconds."
        ctaLabel="Extract contacts"
        ctaIcon="globe"
        appPath={APP_PATH}
        note="Reads public pages only — never logs in anywhere"
        mock={<ExtractorMock />}
      />

      <FeaturePanel>
        <FeatureBlock title="Pull contacts straight from a company's website" mock={<SourcesMock />}>
          <FeatureText>
            Paste a company&apos;s address and PetroLead reads its homepage and contact page for
            the business emails it publishes — from email links and from the page text itself.
          </FeatureText>
          <FeatureText>
            Placeholder and tracking addresses left behind by website builders and analytics
            tools are filtered out, so you only see real contact addresses.
          </FeatureText>
          <CheckList
            items={[
              "Homepage and contact page read automatically",
              "Emails from links and page text, deduplicated",
              "Each email labeled with whether its domain accepts mail",
            ]}
          />
          <FeatureCta
            appPath={APP_PATH}
            label="Try the extractor"
            secondary={{ href: "#how-it-works", label: "See how it works" }}
          />
        </FeatureBlock>

        <Divider />

        <FeatureBlock title="Phone numbers you can actually dial" mock={<PhonesMock />} reverse>
          <FeatureText>
            Websites are full of numbers that aren&apos;t phone numbers — founding years, build
            numbers, reference codes. PetroLead normalizes real phone numbers and checks their
            format, and leaves the look-alikes out.
          </FeatureText>
          <CheckList
            items={[
              "Numbers from phone links and page text",
              "Normalized to international format where possible",
              "Years and reference codes never mistaken for phones",
            ]}
          />
          <FeatureCta appPath={APP_PATH} label="Extract contacts" variant="soft" />
        </FeatureBlock>

        <Divider />

        <FeatureBlock
          title="From website to lead list in one click"
          subtitle="Save companies, skip duplicates, export anytime"
          mock={<ExtractorMock />}
        >
          <FeatureText>
            Save the company to your PetroLead list with its emails, phones, contact page and
            social profiles attached. Already have it? PetroLead points you to the existing
            record instead of creating a duplicate.
          </FeatureText>
          <CheckList
            items={[
              "Social profiles linked from the site included",
              "Duplicate companies detected before you save",
              "Export companies or emails to CSV or Excel",
            ]}
          />
          <FeatureCta appPath={APP_PATH} label="Start extracting" />
        </FeatureBlock>
      </FeaturePanel>

      <StepsSection
        title="How to extract emails from a website"
        subtitle="Here's how to use PetroLead's Email Extractor in four steps."
        steps={STEPS}
      />
      <StatsBand />
      <Faq title="Popular questions about Email Extractor" items={FAQS} idPrefix="ex-faq" />
      <FinalCta
        title="Start extracting business contacts today"
        points={["Paste a website", "Emails, phones and socials", "CSV & Excel export"]}
        appPath={APP_PATH}
      />
    </MarketingPage>
  );
}
