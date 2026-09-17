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
import { EMAIL_CHECK_STATUS, MAX_VERIFY_EMAILS } from "../lib/emailChecks";

const APP_PATH = "/verify-emails";

const SAMPLE_RESULTS = [
  ["a.haddad@gulfstar.example", "deliverable"],
  ["sales@nordicbunker.example", "risky"],
  ["p.raman@coastlinelube", "undeliverable"],
  ["orders@closed-refinery.example", "undeliverable"],
  ["c.wei@harborlpg.example", "deliverable"],
  ["info@slow-dns.example", "unknown"],
];

const FAQS = [
  {
    q: "How does the Email Verifier work?",
    a: "Every address is graded Deliverable, Undeliverable, Risky or Couldn't check. Format, throwaway domains and misspelled providers are decided immediately; then the domain's mail (MX) records are checked; then, where a verification provider is configured, the mail server is asked whether that specific mailbox exists.",
  },
  {
    q: "Does it send an email to the address?",
    a: "No. PetroLead never sends a message. A verification provider asks the receiving mail server whether the mailbox exists and hangs up without delivering anything — the person is never contacted and never sees a test email.",
  },
  {
    q: "Can it confirm a specific mailbox exists?",
    a: "With a verification provider configured, yes — that's what Deliverable means. Without one, only the domain is checked, and well-formed addresses are marked Risky rather than Deliverable, because a domain that accepts mail doesn't prove a particular mailbox does.",
  },
  {
    q: "Will verified addresses never bounce?",
    a: "Nothing can promise that, and any service claiming 100% is overselling. A mailbox can fill up, or be closed the day after it was checked. What verification does is remove the addresses that would certainly bounce and flag the ones that might, so what's left is far safer to send to.",
  },
  {
    q: "What does \"Couldn't check\" mean?",
    a: "The domain's mail servers couldn't be looked up at that moment — usually a temporary DNS problem. It isn't a sign the address is bad; try verifying it again later.",
  },
  {
    q: "How many addresses can I verify at once?",
    a: `Up to ${MAX_VERIFY_EMAILS} per check. Paste them one per line, or separated by commas or spaces — duplicates are removed automatically.`,
  },
  {
    q: "Can I copy the good addresses out?",
    a: "Yes. After a check, one click copies every address whose domain accepts mail, ready to paste into your outreach tool.",
  },
];

const STEPS = [
  {
    title: "Create your PetroLead account",
    body: "Sign up in under a minute and open Email Verifier.",
    link: { label: "Create your account", to: "/register" },
  },
  {
    title: "Paste your addresses",
    body: `Add up to ${MAX_VERIFY_EMAILS} emails — one per line, or separated by commas or spaces.`,
  },
  {
    title: "Verify",
    body: "PetroLead checks each address's format and whether its domain can receive mail.",
  },
  {
    title: "Copy the good ones",
    body: "Review the results and copy every address whose domain accepts mail in one click.",
  },
];

function VerifierMock({ rows = SAMPLE_RESULTS }) {
  return (
    <BrowserFrame url="app.petrolead.org/verify-emails">
      <div className="p-5">
        <div className="text-xs font-semibold uppercase tracking-wide text-ink-700">Email addresses</div>
        <div className="mt-2 rounded-md border border-brand-500 bg-base-850 px-3 py-2 font-mono text-[11px] leading-6 text-ink-300">
          {rows.slice(0, 3).map(([email]) => (
            <div key={email} className="truncate">
              {email}
            </div>
          ))}
          <div className="text-ink-700">…</div>
        </div>
        <div className="mt-3 flex items-center justify-between">
          <span className="text-[11px] text-ink-500">
            {rows.length} of {MAX_VERIFY_EMAILS} addresses
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-md bg-brand-500 px-3 py-1.5 text-[11px] font-semibold text-white">
            <Icon name="shieldCheck" className="h-3.5 w-3.5" /> Verify emails
          </span>
        </div>
      </div>
      <table className="w-full table-fixed text-left text-[11px]">
        <colgroup>
          <col />
          <col className="w-[10.5rem]" />
        </colgroup>
        <thead className="border-y border-base-700 bg-base-900 text-[10px] uppercase tracking-wide text-ink-700">
          <tr>
            <th className="px-5 py-2 font-medium">Email</th>
            <th className="px-3 py-2 font-medium">Result</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([email, status]) => (
            <tr key={email} className="border-b border-base-700 last:border-0">
              <td className="truncate px-5 py-2.5 font-medium text-ink-100">{email}</td>
              <td className="px-3 py-2.5">
                <StatusPill status={status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </BrowserFrame>
  );
}

function StatusLegendMock() {
  return (
    <BrowserFrame url="app.petrolead.org/verify-emails">
      <ul className="flex flex-col gap-3 p-5">
        {Object.entries(EMAIL_CHECK_STATUS).map(([status, { description }]) => (
          <li key={status} className="rounded-xl border border-base-700 bg-base-900 p-4">
            <StatusPill status={status} />
            <p className="mt-2 text-xs leading-relaxed text-ink-500">{description}</p>
          </li>
        ))}
      </ul>
    </BrowserFrame>
  );
}

function BulkSummaryMock() {
  const tiles = [
    ["Deliverable", 41, "text-status-high"],
    ["Undeliverable", 7, "text-status-danger"],
    ["Risky", 2, "text-status-possible"],
  ];
  return (
    <BrowserFrame url="app.petrolead.org/verify-emails">
      <div className="p-5">
        <div className="grid grid-cols-3 gap-2">
          {tiles.map(([label, value, tone]) => (
            <div key={label} className="rounded-xl border border-base-700 bg-base-850 px-3 py-3">
              <div className="text-[10px] font-medium leading-tight text-ink-700">{label}</div>
              <div className={`mt-1 text-xl font-bold ${tone}`}>{value}</div>
            </div>
          ))}
        </div>
        <div className="mt-4 flex items-center justify-between rounded-xl border border-base-700 bg-base-900 px-4 py-3">
          <span className="text-xs font-semibold text-ink-100">500 addresses checked</span>
          <span className="inline-flex items-center gap-1.5 rounded-md border border-base-600 bg-base-850 px-3 py-1.5 text-[11px] font-semibold text-ink-300">
            <Icon name="copy" className="h-3.5 w-3.5" /> Copy deliverable addresses
          </span>
        </div>
        <div className="mt-3 text-center text-[11px] font-medium text-status-high">
          Copied 41 addresses
        </div>
      </div>
    </BrowserFrame>
  );
}

export default function EmailVerifierProduct() {
  return (
    <MarketingPage>
      <ProductHero
        title="Email Verifier"
        description={`Check that email addresses are correctly formatted and that their domains can receive mail — one at a time or ${MAX_VERIFY_EMAILS} at once.`}
        ctaLabel="Verify emails"
        ctaIcon="shieldCheck"
        appPath={APP_PATH}
        note="Never sends an email or contacts the mailbox"
        mock={<VerifierMock />}
      />

      <FeaturePanel>
        <FeatureBlock title="Catch bad addresses before you hit send" mock={<VerifierMock rows={SAMPLE_RESULTS.slice(2, 6)} />}>
          <FeatureText>
            Typos, made-up addresses and domains that shut down years ago all bounce — and too
            many bounces hurt your sender reputation. The Email Verifier flags them before they
            reach your outreach list.
          </FeatureText>
          <CheckList
            items={[
              "Format check catches typos and incomplete addresses",
              "Mail-server check catches dead and misspelled domains",
              "Clear result and explanation for every address",
            ]}
          />
          <FeatureCta
            appPath={APP_PATH}
            label="Verify an email"
            secondary={{ href: "#how-it-works", label: "See how it works" }}
          />
        </FeatureBlock>

        <Divider />

        <FeatureBlock title="Know exactly what each result means" mock={<StatusLegendMock />} reverse>
          <FeatureText>
            No vague scores. Every address is graded on one question — will this bounce? — and
            each result says why, so you know whether you&apos;re looking at a typo, a dead
            domain or a shared inbox.
          </FeatureText>
          <CheckList
            items={[
              "Deliverable, Undeliverable, Risky or Couldn't check — plus the reason",
              "Only Deliverable addresses are copied and exported",
              "Temporary DNS problems never reported as undeliverable",
            ]}
          />
          <FeatureCta appPath={APP_PATH} label="Try the verifier" variant="soft" />
        </FeatureBlock>

        <Divider />

        <FeatureBlock
          title={`Verify up to ${MAX_VERIFY_EMAILS} emails at once`}
          subtitle="Clean a whole list in a single check"
          mock={<BulkSummaryMock />}
        >
          <FeatureText>
            Paste a list straight from a spreadsheet — one per line, or separated by commas or
            spaces. PetroLead removes duplicates, checks every address in one pass and gives you
            a summary of the results.
          </FeatureText>
          <CheckList
            items={[
              "Paste addresses in any common format",
              "Duplicates removed automatically",
              "Copy every good address in one click",
            ]}
          />
          <FeatureCta appPath={APP_PATH} label="Clean your list" />
        </FeatureBlock>
      </FeaturePanel>

      <StepsSection
        title="How to verify email addresses"
        subtitle="Here's how to use PetroLead's Email Verifier in four steps."
        steps={STEPS}
      />
      <StatsBand />
      <Faq title="Popular questions about Email Verifier" items={FAQS} idPrefix="ev-faq" />
      <FinalCta
        title="Start verifying email addresses today"
        points={[`Up to ${MAX_VERIFY_EMAILS} at once`, "Plain-language results", "No mailbox probing"]}
        appPath={APP_PATH}
      />
    </MarketingPage>
  );
}
