import { useEffect } from "react";
import { Link } from "react-router-dom";
import { useBilling } from "../context/BillingContext";
import Icon from "../components/marketing/Icon";
import { SALES_EMAIL } from "../components/marketing/pricing";

function formatDate(value) {
  // The API sends UTC timestamps without a zone suffix.
  const date = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`);
  return date.toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
}

function Card({ label, children }) {
  return (
    <div className="rounded-2xl border border-base-700 bg-base-850 p-6 shadow-sm">
      <div className="text-xs font-semibold uppercase tracking-wide text-ink-700">{label}</div>
      {children}
    </div>
  );
}

function ContactActions() {
  return (
    <div className="mt-5 flex flex-wrap gap-3">
      <Link
        to="/pricing"
        className="inline-flex items-center justify-center rounded-md bg-brand-500 px-5 py-2.5 text-sm font-semibold text-white hover:bg-brand-700"
      >
        Compare plans
      </Link>
      <a
        href={`mailto:${SALES_EMAIL}`}
        className="inline-flex items-center justify-center rounded-md border border-base-600 px-5 py-2.5 text-sm font-semibold text-ink-300 hover:border-brand-500 hover:text-brand-600"
      >
        Contact sales
      </a>
    </div>
  );
}

function Included({ ok, children }) {
  return (
    <li className="flex items-center gap-2.5 text-sm">
      <span
        className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full ${
          ok ? "bg-status-high/15 text-status-high" : "bg-base-800 text-ink-700"
        }`}
      >
        <Icon name={ok ? "check" : "close"} className="h-3 w-3" />
      </span>
      <span className={ok ? "text-ink-300" : "text-ink-700"}>{children}</span>
    </li>
  );
}

function PlanDetails({ billing }) {
  const used = billing.discovery_searches_today;
  const perDay = billing.discovery_searches_per_day;
  const usedPercent = Math.min(100, Math.round((used / perDay) * 100));

  return (
    <>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card label="Current plan">
          <div className="mt-2 text-3xl font-bold tracking-tight text-ink-100">{billing.plan_name}</div>
          <p className="mt-2 text-sm text-ink-500">
            {billing.credits_per_month.toLocaleString()} email credits every month
          </p>
          <p className="mt-1 text-sm text-ink-500">Next credits on {formatDate(billing.renews_at)}</p>
        </Card>

        <Card label="Email credits left">
          <div className="mt-2 text-3xl font-bold tracking-tight text-ink-100">
            {billing.credits_balance.toLocaleString()}
          </div>
          <p className="mt-2 text-sm leading-relaxed text-ink-500">
            One credit is used each time a person lookup finds a business email. Unused credits
            roll over to next month.
          </p>
        </Card>

        <Card label="Company searches today">
          <div className="mt-2 text-3xl font-bold tracking-tight text-ink-100">
            {used} <span className="text-lg font-medium text-ink-700">of {perDay}</span>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-base-700">
            <div
              className={`h-full rounded-full ${usedPercent >= 100 ? "bg-status-danger" : "bg-brand-500"}`}
              style={{ width: `${usedPercent}%` }}
            />
          </div>
          <p className="mt-2 text-sm text-ink-500">Resets at midnight UTC.</p>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card label="Included in your plan">
          <ul className="mt-4 flex flex-col gap-3">
            <Included ok>LinkedIn Email Finder and name + company lookup</Included>
            <Included ok>Email Extractor and Email Verifier — no credits used</Included>
            <Included ok>Up to {billing.max_results_per_search} results per company search</Included>
            <Included ok={billing.bulk_lookup}>Bulk lookup (up to 25 people at once)</Included>
            <Included ok={billing.export}>CSV &amp; Excel export</Included>
            <Included ok={billing.scheduled_searches !== 0}>
              {billing.scheduled_searches === null
                ? "Unlimited scheduled searches"
                : billing.scheduled_searches
                  ? `Up to ${billing.scheduled_searches} scheduled searches`
                  : "Scheduled searches"}
            </Included>
          </ul>
        </Card>

        <Card label="Need more?">
          <p className="mt-3 text-sm leading-relaxed text-ink-500">
            Online checkout isn&apos;t available yet. To change your plan or add credits, get in
            touch and we&apos;ll update your account.
          </p>
          <ContactActions />
        </Card>
      </div>
    </>
  );
}

export default function Billing() {
  const { billing, refresh } = useBilling();

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-100">Plan &amp; credits</h1>
        <p className="mt-1 text-sm text-ink-500">
          Your plan, email credits and what&apos;s included.
        </p>
      </div>

      {!billing && <div className="text-sm text-ink-500">Loading...</div>}

      {billing?.exempt && (
        <Card label="Unlimited access">
          <p className="mt-3 text-sm leading-relaxed text-ink-500">
            Your account isn&apos;t limited by a plan — admins can use every tool without spending
            credits.
          </p>
        </Card>
      )}

      {billing && !billing.exempt && !billing.plan && (
        <Card label="No active plan">
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-ink-500">
            Choose a plan to start finding companies and business emails. Plans start with 1,000
            email credits a month.
          </p>
          <ContactActions />
        </Card>
      )}

      {billing && !billing.exempt && billing.plan && <PlanDetails billing={billing} />}
    </div>
  );
}
