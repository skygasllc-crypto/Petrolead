import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { PLANS, SALES_EMAIL, YEARLY_DISCOUNT } from "../components/marketing/pricing";

const TIER_OPTIONS = PLANS.flatMap((plan) =>
  plan.tiers.map((tier) => ({ key: `${plan.id}:${tier.credits}`, plan, tier })),
);
const DEFAULT_OPTION = TIER_OPTIONS.find((option) => option.plan.popular) ?? TIER_OPTIONS[0];

// Same calculation as the server (app/services/plans.py::price_usd), which
// sets the amount actually charged.
function periodTotal(tier, period) {
  if (period === "monthly") return tier.monthly;
  return Math.round(tier.monthly * (1 - YEARLY_DISCOUNT)) * 12;
}

function SummaryRow({ label, value }) {
  return (
    <div className="flex items-center justify-between gap-4 py-1.5 text-sm">
      <dt className="text-ink-500">{label}</dt>
      <dd className="font-semibold text-ink-100">{value}</dd>
    </div>
  );
}

function CoinOption({ method, checked, onSelect }) {
  return (
    <label
      className={`flex cursor-pointer items-start gap-3 rounded-xl border p-4 transition-colors ${
        checked ? "border-brand-500 bg-brand-50" : "border-base-700 bg-base-850 hover:border-base-400"
      }`}
    >
      <input
        type="radio"
        name="currency"
        value={method.currency}
        checked={checked}
        onChange={() => onSelect(method.currency)}
        className="mt-1 accent-[var(--color-brand-500)]"
      />
      <span>
        <span className="block text-sm font-semibold text-ink-100">{method.name}</span>
        <span className="block text-xs text-ink-500">{method.network} network</span>
      </span>
    </label>
  );
}

export default function Checkout() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const selected =
    TIER_OPTIONS.find((option) => option.key === `${params.get("plan")}:${params.get("credits")}`) ??
    DEFAULT_OPTION;
  const period = params.get("period") === "monthly" ? "monthly" : "yearly";

  const [methods, setMethods] = useState(null);
  const [currency, setCurrency] = useState(null);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api
      .paymentMethods()
      .then((list) => {
        setMethods(list);
        setCurrency((current) => current ?? list[0]?.currency ?? null);
      })
      .catch((err) => {
        setMethods([]);
        setError(err instanceof ApiError ? err.message : "Couldn't load payment methods.");
      });
  }, []);

  function choose(changes) {
    setParams(
      { plan: selected.plan.id, credits: String(selected.tier.credits), period, ...changes },
      { replace: true },
    );
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!currency) return;
    setSubmitting(true);
    setError(null);
    try {
      const order = await api.createOrder({
        plan: selected.plan.id,
        credits_per_month: selected.tier.credits,
        billing_period: period,
        currency,
      });
      navigate(`/billing/orders/${order.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't start this payment.");
      setSubmitting(false);
    }
  }

  const total = periodTotal(selected.tier, period);
  const card = "rounded-2xl border border-base-700 bg-base-850 p-6 shadow-sm";

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-100">Checkout</h1>
        <p className="mt-1 text-sm text-ink-500">
          Pay for your plan in Bitcoin, Tether (USDT on TRON) or TRX. Nothing renews
          automatically — you pay again when you want more time.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_22rem]">
        <div className="flex flex-col gap-6">
          <section className={card}>
            <h2 className="text-sm font-semibold text-ink-100">1. Choose your plan</h2>
            <label className="mt-4 block">
              <span className="sr-only">Plan and credits</span>
              <select
                value={selected.key}
                onChange={(e) => {
                  const [plan, credits] = e.target.value.split(":");
                  choose({ plan, credits });
                }}
                className="w-full rounded-md border border-base-600 bg-base-850 px-3 py-2.5 text-sm text-ink-100 focus:border-brand-500 focus:outline-none"
              >
                {PLANS.map((plan) => (
                  <optgroup key={plan.id} label={plan.name}>
                    {plan.tiers.map((tier) => (
                      <option key={tier.credits} value={`${plan.id}:${tier.credits}`}>
                        {plan.name} — {tier.credits.toLocaleString()} credits/month
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </label>
            <div
              role="group"
              aria-label="Billing period"
              className="mt-4 inline-flex rounded-full border border-base-700 bg-base-900 p-1"
            >
              {["monthly", "yearly"].map((option) => (
                <button
                  key={option}
                  type="button"
                  aria-pressed={period === option}
                  onClick={() => choose({ period: option })}
                  className={`rounded-full px-4 py-1.5 text-sm font-semibold transition-colors ${
                    period === option ? "bg-brand-500 text-white" : "text-ink-500 hover:text-ink-100"
                  }`}
                >
                  {option === "monthly" ? "1 month" : `12 months — save ${YEARLY_DISCOUNT * 100}%`}
                </button>
              ))}
            </div>
          </section>

          <section className={card}>
            <h2 className="text-sm font-semibold text-ink-100">2. Choose how to pay</h2>
            {methods === null && <p className="mt-4 text-sm text-ink-500">Loading...</p>}
            {methods?.length === 0 && !error && (
              <p className="mt-4 text-sm text-ink-500">
                Crypto payments aren&apos;t set up yet.{" "}
                <a href={`mailto:${SALES_EMAIL}`} className="font-semibold text-brand-600">
                  Contact sales
                </a>{" "}
                to arrange your plan.
              </p>
            )}
            {methods?.length > 0 && (
              <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
                {methods.map((method) => (
                  <CoinOption
                    key={method.currency}
                    method={method}
                    checked={currency === method.currency}
                    onSelect={setCurrency}
                  />
                ))}
              </div>
            )}
            <p className="mt-4 text-xs leading-relaxed text-ink-700">
              USDT is priced 1:1 with the US dollar. BTC and TRX amounts use the current market
              price, held for a limited time shown on the next step.
            </p>
          </section>
        </div>

        <aside className={`${card} h-fit`}>
          <h2 className="text-sm font-semibold text-ink-100">Order summary</h2>
          <dl className="mt-3">
            <SummaryRow label="Plan" value={selected.plan.name} />
            <SummaryRow
              label="Email credits"
              value={`${selected.tier.credits.toLocaleString()} / month`}
            />
            <SummaryRow label="Users" value={selected.tier.users} />
            <SummaryRow label="Covers" value={period === "monthly" ? "1 month" : "12 months"} />
          </dl>
          <div className="mt-3 flex items-baseline justify-between border-t border-base-700 pt-4">
            <span className="text-sm font-semibold text-ink-300">Total</span>
            <span className="text-2xl font-bold text-ink-100">${total.toLocaleString()}</span>
          </div>
          {error && (
            <div
              role="alert"
              className="mt-4 rounded-lg border border-status-danger/30 bg-status-danger/10 px-3 py-2 text-sm text-status-danger"
            >
              {error}
            </div>
          )}
          <button
            type="submit"
            disabled={submitting || !currency}
            className="mt-5 inline-flex w-full items-center justify-center rounded-md bg-brand-500 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? "Preparing..." : "Continue to payment"}
          </button>
          <p className="mt-3 text-xs leading-relaxed text-ink-700">
            Your plan starts as soon as we confirm the transaction.{" "}
            <Link to="/pricing" className="font-semibold text-brand-600">
              Compare plans
            </Link>
          </p>
        </aside>
      </form>
    </div>
  );
}
