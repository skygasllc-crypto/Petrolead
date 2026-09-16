import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useBilling } from "../context/BillingContext";
import Icon from "../components/marketing/Icon";
import OrderStatusBadge from "../components/OrderStatusBadge";
import { SALES_EMAIL } from "../components/marketing/pricing";
import { formatDate } from "../lib/dates";
import { checkoutPath } from "../lib/payments";

const primaryButton =
  "inline-flex items-center justify-center rounded-md bg-brand-500 px-5 py-2.5 text-sm font-semibold text-white hover:bg-brand-700";
const secondaryButton =
  "inline-flex items-center justify-center rounded-md border border-base-600 px-5 py-2.5 text-sm font-semibold text-ink-300 hover:border-brand-500 hover:text-brand-600";

function Card({ label, children, className = "" }) {
  return (
    <div className={`rounded-2xl border border-base-700 bg-base-850 p-6 shadow-sm ${className}`}>
      <div className="text-xs font-semibold uppercase tracking-wide text-ink-700">{label}</div>
      {children}
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

function PaymentHistory() {
  const [orders, setOrders] = useState(null);

  useEffect(() => {
    api
      .listOrders()
      .then(setOrders)
      .catch(() => setOrders([]));
  }, []);

  if (!orders || orders.length === 0) return null;
  return (
    <Card label="Your payments">
      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[36rem] text-left text-sm">
          <thead className="text-xs uppercase tracking-wide text-ink-700">
            <tr className="border-b border-base-700">
              <th className="py-2 pr-4 font-medium">Date</th>
              <th className="py-2 pr-4 font-medium">Reference</th>
              <th className="py-2 pr-4 font-medium">Plan</th>
              <th className="py-2 pr-4 font-medium">Amount</th>
              <th className="py-2 pr-4 font-medium">Status</th>
              <th className="py-2 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {orders.map((order) => (
              <tr key={order.id} className="border-b border-base-700 last:border-0">
                <td className="py-3 pr-4 text-ink-500">{formatDate(order.created_at)}</td>
                <td className="py-3 pr-4 font-mono text-xs text-ink-500">{order.reference}</td>
                <td className="py-3 pr-4 text-ink-100">
                  {order.plan_name} · {order.billing_period === "yearly" ? "12 months" : "1 month"}
                </td>
                <td className="py-3 pr-4 text-ink-100">
                  {order.amount_crypto} {order.coin_symbol}
                </td>
                <td className="py-3 pr-4">
                  <OrderStatusBadge status={order.status} />
                </td>
                <td className="py-3 text-right">
                  <Link
                    to={`/billing/orders/${order.id}`}
                    className="text-sm font-semibold text-brand-600 hover:text-brand-700"
                  >
                    View
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function PlanDetails({ billing }) {
  const used = billing.discovery_searches_today;
  const perDay = billing.discovery_searches_per_day;
  const usedPercent = Math.min(100, Math.round((used / perDay) * 100));
  const renew = checkoutPath(billing.plan, billing.credits_per_month, "monthly");

  return (
    <>
      {billing.expired && (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-status-danger/30 bg-status-danger/10 px-5 py-4"
        >
          <p className="text-sm text-status-danger">
            <strong className="font-semibold">Your {billing.plan_name} plan ended on{" "}
            {formatDate(billing.paid_until)}.</strong>{" "}
            Renew it to keep finding companies and emails — your{" "}
            {billing.credits_balance.toLocaleString()} unused credits are kept.
          </p>
          <Link to={renew} className={primaryButton}>
            Renew now
          </Link>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card label="Current plan">
          <div className="mt-2 text-3xl font-bold tracking-tight text-ink-100">{billing.plan_name}</div>
          <p className="mt-2 text-sm text-ink-500">
            {billing.credits_per_month.toLocaleString()} email credits every month
          </p>
          <p className="mt-1 text-sm text-ink-500">
            {billing.paid_until
              ? `${billing.expired ? "Ended" : "Paid until"} ${formatDate(billing.paid_until)}`
              : `Next credits on ${formatDate(billing.renews_at)}`}
          </p>
        </Card>

        <Card label="Email credits left">
          <div className="mt-2 text-3xl font-bold tracking-tight text-ink-100">
            {billing.credits_balance.toLocaleString()}
          </div>
          <p className="mt-2 text-sm leading-relaxed text-ink-500">
            One credit is used each time a person lookup finds a business email. Unused credits
            roll over.
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

        <Card label="Renew or change plan">
          <p className="mt-3 text-sm leading-relaxed text-ink-500">
            Pay for another month or year in BTC, USDT (TRC-20) or TRX. Nothing renews
            automatically, so pay before your plan ends to keep it running.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link to={renew} className={primaryButton}>
              Renew {billing.plan_name}
            </Link>
            <Link to="/pricing" className={secondaryButton}>
              Change plan
            </Link>
          </div>
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
          Your plan, email credits, payments and what&apos;s included.
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
            Choose a plan to start finding companies and business emails. Plans start at $15 a
            month and are paid in BTC, USDT (TRC-20) or TRX.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link to="/pricing" className={primaryButton}>
              Choose a plan
            </Link>
            <a href={`mailto:${SALES_EMAIL}`} className={secondaryButton}>
              Contact sales
            </a>
          </div>
        </Card>
      )}

      {billing && !billing.exempt && billing.plan && <PlanDetails billing={billing} />}

      {billing && !billing.exempt && <PaymentHistory />}
    </div>
  );
}
