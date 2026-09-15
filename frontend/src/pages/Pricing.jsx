import { Fragment, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import Icon from "../components/marketing/Icon";
import SiteHeader, { primaryButton, secondaryButton } from "../components/marketing/SiteHeader";
import SiteFooter from "../components/marketing/SiteFooter";
import Faq from "../components/marketing/Faq";
import {
  COMPARISON,
  PLANS,
  PRICING_FAQS,
  SALES_EMAIL,
  YEARLY_DISCOUNT,
} from "../components/marketing/pricing";

const formatNumber = (n) => n.toLocaleString("en-US");

function shortCredits(n) {
  return n >= 1000 ? `${n / 1000}K` : String(n);
}

function priceFor(tier, yearly) {
  return yearly ? Math.round(tier.monthly * (1 - YEARLY_DISCOUNT)) : tier.monthly;
}

function BillingToggle({ yearly, onChange }) {
  const option = (active) =>
    `rounded-full px-5 py-2 text-sm font-semibold transition-colors ${
      active ? "bg-brand-500 text-white shadow-sm" : "text-ink-500 hover:text-ink-100"
    }`;
  return (
    <div className="flex items-center justify-center gap-3">
      <div className="inline-flex rounded-full border border-base-700 bg-base-900 p-1">
        <button
          type="button"
          aria-pressed={!yearly}
          onClick={() => onChange(false)}
          className={option(!yearly)}
        >
          Monthly
        </button>
        <button
          type="button"
          aria-pressed={yearly}
          onClick={() => onChange(true)}
          className={option(yearly)}
        >
          Yearly
        </button>
      </div>
      <span className="rounded-full bg-status-high/10 px-2.5 py-1 text-xs font-semibold text-status-high">
        Save {YEARLY_DISCOUNT * 100}%
      </span>
    </div>
  );
}

function TierSelector({ plan, value, onChange }) {
  const last = plan.tiers.length - 1;
  const position = (i) => `${(i / last) * 100}%`;
  return (
    <div className="mt-6">
      <div
        role="radiogroup"
        aria-label={`${plan.name} credits per month`}
        className="relative mx-2 h-4"
      >
        <div className="absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 rounded-full bg-base-700" />
        <div
          className="absolute left-0 top-1/2 h-1 -translate-y-1/2 rounded-full bg-brand-500"
          style={{ width: position(value) }}
        />
        {plan.tiers.map((t, i) => (
          <button
            key={t.credits}
            type="button"
            role="radio"
            aria-checked={i === value}
            aria-label={`${formatNumber(t.credits)} credits`}
            onClick={() => onChange(i)}
            style={{ left: position(i) }}
            className={`absolute top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 transition-all ${
              i === value
                ? "h-4 w-4 border-brand-500 bg-brand-500 ring-4 ring-brand-500/20"
                : i < value
                  ? "h-2.5 w-2.5 border-brand-500 bg-brand-500"
                  : "h-2.5 w-2.5 border-base-600 bg-base-850 hover:border-brand-500"
            }`}
          />
        ))}
      </div>
      <div className="mt-2.5 flex justify-between text-xs">
        {plan.tiers.map((t, i) => (
          <span
            key={t.credits}
            className={i === value ? "font-bold text-ink-100" : "font-medium text-ink-500"}
          >
            {shortCredits(t.credits)}
          </span>
        ))}
      </div>
    </div>
  );
}

const PLAN_TOP_BG = {
  basic: "bg-base-900",
  professional: "bg-status-high/5",
  enterprise: "bg-brand-50",
};

function PlanCard({ plan, tierIndex, onTierChange, yearly }) {
  const { user } = useAuth();
  const tier = plan.tiers[tierIndex];
  const price = priceFor(tier, yearly);

  return (
    <div
      className={`relative flex flex-col rounded-2xl bg-base-850 ${
        plan.popular ? "border-2 border-brand-500 shadow-lg" : "border border-base-700"
      }`}
    >
      {plan.popular && (
        <span className="absolute -top-3 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full bg-brand-500 px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-white">
          Most popular
        </span>
      )}

      <div className={`rounded-t-2xl px-7 pb-6 pt-8 ${PLAN_TOP_BG[plan.id]}`}>
        <h2 className="text-2xl font-bold tracking-tight text-ink-100">{plan.name}</h2>
        <p className="mt-2 text-sm text-ink-500">{plan.tagline}</p>
        {plan.tiers.length > 1 ? (
          <TierSelector plan={plan} value={tierIndex} onChange={onTierChange} />
        ) : (
          <div className="h-[3.875rem]" aria-hidden="true" />
        )}
      </div>

      <div className="flex flex-1 flex-col px-7 pb-8 pt-6">
        <div className="flex min-h-[3rem] flex-wrap items-baseline gap-x-2 gap-y-1">
          <span className="text-4xl font-extrabold tracking-tight text-ink-100">
            ${formatNumber(price)}
          </span>
          {yearly && (
            <span className="text-lg font-medium text-ink-700 line-through">
              ${formatNumber(tier.monthly)}
            </span>
          )}
          <span className="text-sm text-ink-500">/month</span>
          {yearly && (
            <span className="rounded-full border border-base-700 bg-base-900 px-2 py-0.5 text-xs font-medium text-ink-500">
              Billed annually
            </span>
          )}
        </div>

        <div className="mt-5 flex items-center justify-between rounded-xl bg-base-900 px-4 py-3 text-sm">
          <span>
            <strong className="font-bold text-ink-100">{formatNumber(tier.credits)}</strong>{" "}
            <span className="text-ink-500">credits/mo</span>
          </span>
          <span className="h-5 w-px bg-base-700" aria-hidden="true" />
          <span>
            <strong className="font-bold text-ink-100">{tier.users}</strong>{" "}
            <span className="text-ink-500">{tier.users === 1 ? "user" : "users"}</span>
          </span>
        </div>

        <div className="mt-4 flex min-h-5 flex-wrap items-center justify-between gap-2 text-xs text-ink-500">
          <span className="flex items-center gap-1.5">
            <Icon name="check" className="h-3.5 w-3.5 text-status-high" />
            Pay only for found emails
          </span>
          <span className="flex items-center gap-1.5">
            <Icon name="check" className="h-3.5 w-3.5 text-status-high" />
            Credits roll over
          </span>
        </div>

        <Link
          to={user ? "/dashboard" : "/register"}
          className={`mt-6 w-full py-3 ${
            plan.outlined ? `${secondaryButton} border-brand-500` : primaryButton
          }`}
        >
          {plan.cta}
        </Link>

        <p className="mt-7 text-xs font-semibold uppercase tracking-wide text-ink-700">
          {plan.featuresHeading}
        </p>
        <ul className="mt-3 flex flex-1 flex-col gap-2.5">
          {plan.features.map((f) => (
            <li key={f} className="flex items-center gap-2.5 text-sm text-ink-300">
              <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-status-high/15 text-status-high">
                <Icon name="check" className="h-3 w-3" />
              </span>
              {f}
            </li>
          ))}
        </ul>

        <a
          href="#compare"
          className="mt-6 inline-flex items-center gap-1 text-sm font-semibold text-brand-600 hover:text-brand-700"
        >
          See all features <Icon name="chevronDown" className="h-4 w-4" />
        </a>
      </div>
    </div>
  );
}

function ComparisonCell({ value }) {
  if (value === true) {
    return (
      <>
        <Icon name="check" className="mx-auto h-5 w-5 text-status-high" />
        <span className="sr-only">Included</span>
      </>
    );
  }
  if (value === false) {
    return (
      <>
        <span aria-hidden="true" className="text-base-500">
          —
        </span>
        <span className="sr-only">Not included</span>
      </>
    );
  }
  return (
    <span className="font-semibold text-ink-100">
      {typeof value === "number" ? formatNumber(value) : value}
    </span>
  );
}

function ComparisonTable({ tierIndexes, onTierChange }) {
  // Rows with a `type` depend on the tier currently selected for each plan.
  function tierValue(type, plan, p) {
    const tier = plan.tiers[tierIndexes[p]];
    return type === "credits" ? `${formatNumber(tier.credits)} / month` : tier.users;
  }

  return (
    <section id="compare" className="scroll-mt-28 px-4 py-20 sm:px-6 lg:px-8">
      <h2 className="text-center text-3xl font-bold tracking-tight text-ink-100 sm:text-4xl">
        Compare plans in detail
      </h2>
      {/* `relative` makes this scroll box the containing block for the table's
          absolutely positioned sr-only labels — otherwise they escape the
          horizontal scroll and widen the whole page on phones. */}
      <div className="relative mx-auto mt-12 max-w-6xl overflow-x-auto">
        <table className="w-full min-w-[40rem] border-collapse text-sm">
          <thead>
            <tr>
              <th className="w-2/5 p-4 text-left">
                <span className="sr-only">Feature</span>
              </th>
              {PLANS.map((plan, p) => (
                <th key={plan.id} scope="col" className="p-4 text-center align-bottom font-normal">
                  {plan.popular && (
                    <span className="mb-2 inline-block rounded-full border border-brand-100 bg-brand-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-brand-600">
                      Most popular
                    </span>
                  )}
                  <div className="text-lg font-semibold text-ink-100">{plan.name}</div>
                  {plan.tiers.length > 1 ? (
                    <select
                      aria-label={`${plan.name} credits per month`}
                      value={tierIndexes[p]}
                      onChange={(e) => onTierChange(p, Number(e.target.value))}
                      className="mt-3 rounded-full border border-brand-100 bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-500"
                    >
                      {plan.tiers.map((t, i) => (
                        <option key={t.credits} value={i}>
                          {shortCredits(t.credits)} credits
                        </option>
                      ))}
                    </select>
                  ) : (
                    <div className="mt-3 h-[1.625rem]" aria-hidden="true" />
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {COMPARISON.map((group) => (
              <Fragment key={group.category}>
                <tr className="bg-base-900">
                  <th
                    colSpan={PLANS.length + 1}
                    scope="colgroup"
                    className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-ink-500"
                  >
                    {group.category}
                  </th>
                </tr>
                {group.rows.map((row, r) => (
                  <tr key={row.label} className={r % 2 === 1 ? "bg-base-900/50" : ""}>
                    <th scope="row" className="px-4 py-3.5 text-left font-normal text-ink-300">
                      {row.label}
                    </th>
                    {PLANS.map((plan, p) => (
                      <td key={plan.id} className="px-4 py-3.5 text-center">
                        <ComparisonCell
                          value={row.type ? tierValue(row.type, plan, p) : row.values[p]}
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function Pricing() {
  const [yearly, setYearly] = useState(true);
  const [tierIndexes, setTierIndexes] = useState(() => PLANS.map(() => 0));

  function setTier(planIndex, tierIndex) {
    setTierIndexes((prev) => prev.map((v, i) => (i === planIndex ? tierIndex : v)));
  }

  return (
    <div className="relative min-h-screen bg-base-850">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-[32rem] bg-gradient-to-b from-brand-50 to-transparent"
      />
      <SiteHeader />

      <main className="relative">
        <section className="px-4 pb-12 pt-16 text-center sm:px-6 sm:pt-20 lg:px-8">
          <h1 className="text-4xl font-bold tracking-tight text-ink-100 sm:text-5xl">
            Simple pricing that grows with your pipeline
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-lg text-ink-500">
            Plans start at ${priceFor(PLANS[0].tiers[0], true)} a month. Upgrade when you&apos;re
            ready — and only use credits when an email is found.
          </p>
          <div className="mt-10">
            <BillingToggle yearly={yearly} onChange={setYearly} />
          </div>
        </section>

        <section className="px-4 sm:px-6 lg:px-8">
          <div className="mx-auto grid max-w-6xl grid-cols-1 gap-8 pt-4 lg:grid-cols-3 lg:gap-6">
            {PLANS.map((plan, p) => (
              <PlanCard
                key={plan.id}
                plan={plan}
                tierIndex={tierIndexes[p]}
                onTierChange={(i) => setTier(p, i)}
                yearly={yearly}
              />
            ))}
          </div>
        </section>

        <ComparisonTable tierIndexes={tierIndexes} onTierChange={setTier} />

        <Faq title="Pricing questions" items={PRICING_FAQS} idPrefix="pricing-faq" />

        <section className="px-4 pb-20 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-7xl rounded-[2rem] border border-base-700 bg-gradient-to-br from-base-900 via-base-850 to-brand-50 px-6 py-16 text-center">
            <h2 className="text-3xl font-bold tracking-tight text-ink-100 sm:text-4xl">
              Need a custom plan?
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-ink-500">
              For larger teams or higher volumes, we&apos;ll put together a plan around your
              credit and seat needs.
            </p>
            <a href={`mailto:${SALES_EMAIL}`} className={`${primaryButton} mt-8`}>
              Contact sales
            </a>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}
