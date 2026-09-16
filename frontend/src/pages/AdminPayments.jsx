import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import OrderStatusBadge from "../components/OrderStatusBadge";
import { formatDateTime } from "../lib/dates";
import { PAYMENTS_CHANGED_EVENT } from "../lib/payments";

const FILTERS = [
  { id: "submitted", label: "Waiting for confirmation" },
  { id: "", label: "All payments" },
];

function Detail({ label, children }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-medium text-ink-700">{label}</dt>
      <dd className="mt-1 text-sm text-ink-100">{children}</dd>
    </div>
  );
}

function PaymentCard({ order, busy, onConfirm, onReject }) {
  const [rejecting, setRejecting] = useState(false);
  const [note, setNote] = useState("");
  const [txHash, setTxHash] = useState("");
  const explorerName = order.explorer_url ? new URL(order.explorer_url).hostname : null;

  return (
    <li className="rounded-2xl border border-base-700 bg-base-850 p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-base font-semibold text-ink-100">
            {order.customer_email}{" "}
            <span className="font-mono text-sm font-medium text-ink-500">{order.reference}</span>
          </div>
          <div className="text-xs text-ink-500">
            {order.submitted_at
              ? `Marked paid ${formatDateTime(order.submitted_at)}`
              : `Created ${formatDateTime(order.created_at)}`}
          </div>
        </div>
        <OrderStatusBadge status={order.status} />
      </div>

      <dl className="mt-4 grid grid-cols-1 gap-4 border-t border-base-700 pt-4 sm:grid-cols-2 lg:grid-cols-4">
        <Detail label="Plan">
          {order.plan_name} · {order.credits_per_month.toLocaleString()} credits/mo ·{" "}
          {order.billing_period === "yearly" ? "12 months" : "1 month"}
        </Detail>
        <Detail label="Amount due">
          <span className="font-semibold">
            {order.amount_crypto} {order.coin_symbol}
          </span>{" "}
          <span className="text-ink-500">(${order.amount_usd})</span>
          <span className="block text-xs text-ink-700">{order.network} network</span>
        </Detail>
        <Detail label="Should arrive at">
          <span className="break-all font-mono text-xs">{order.pay_address}</span>
        </Detail>
        <Detail label="Transaction ID">
          {order.tx_hash ? (
            <>
              <span className="block break-all font-mono text-xs">{order.tx_hash}</span>
              <a
                href={order.explorer_url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-1 inline-block text-xs font-semibold text-brand-600 hover:underline"
              >
                Check on {explorerName} ↗
              </a>
            </>
          ) : (
            <span className="text-ink-700">
              Not given — match by amount and time on the address above
            </span>
          )}
        </Detail>
      </dl>

      {order.paid_after_quote_expired && (
        <p className="mt-4 rounded-lg border border-status-possible/30 bg-status-possible/10 px-3 py-2 text-sm text-status-possible">
          The price quote had expired before this was marked paid — check the full amount
          arrived.
        </p>
      )}
      {order.admin_note && order.status !== "submitted" && (
        <p className="mt-4 text-sm text-ink-500">Note: {order.admin_note}</p>
      )}

      {order.status === "submitted" && (
        <div className="mt-5 border-t border-base-700 pt-4">
          <p className="text-xs leading-relaxed text-ink-700">
            Check on the block explorer that at least{" "}
            <strong className="font-semibold text-ink-300">
              {order.amount_crypto} {order.coin_symbol}
            </strong>{" "}
            arrived at the address above on the {order.network} network, around the time this was
            marked paid, before confirming.
          </p>
          {!order.tx_hash && !rejecting && (
            <input
              value={txHash}
              onChange={(e) => setTxHash(e.target.value)}
              aria-label={`Transaction ID for ${order.reference} (optional)`}
              placeholder="Transaction ID you matched (optional)"
              className="mt-3 w-full max-w-md rounded-md border border-base-600 bg-base-850 px-3 py-2 font-mono text-xs text-ink-100 placeholder:font-sans placeholder:text-ink-700 focus:border-brand-500 focus:outline-none"
            />
          )}
          {rejecting ? (
            <form
              className="mt-3 flex flex-col gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                onReject(order, note.trim());
              }}
            >
              <label htmlFor={`note-${order.id}`} className="text-sm font-medium text-ink-300">
                Why are you rejecting it? The customer will see this.
              </label>
              <textarea
                id={`note-${order.id}`}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={2}
                required
                placeholder="e.g. No payment arrived at our address for this transaction ID."
                className="w-full rounded-md border border-base-600 bg-base-850 px-3 py-2 text-sm text-ink-100 focus:border-brand-500 focus:outline-none"
              />
              <div className="flex gap-2">
                <button
                  type="submit"
                  disabled={busy || !note.trim()}
                  className="rounded-md bg-status-danger px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
                >
                  Reject payment
                </button>
                <button
                  type="button"
                  onClick={() => setRejecting(false)}
                  className="px-3 text-sm font-semibold text-ink-500 hover:text-ink-100"
                >
                  Back
                </button>
              </div>
            </form>
          ) : (
            <div className="mt-3 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => onConfirm(order, txHash.trim())}
                disabled={busy}
                className="rounded-md bg-status-high px-5 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-60"
              >
                {busy ? "Working..." : "Confirm payment"}
              </button>
              <button
                type="button"
                onClick={() => setRejecting(true)}
                disabled={busy}
                className="rounded-md border border-status-danger/50 px-5 py-2 text-sm font-semibold text-status-danger hover:bg-status-danger/10 disabled:opacity-60"
              >
                Reject
              </button>
            </div>
          )}
        </div>
      )}
    </li>
  );
}

export default function AdminPayments() {
  const [filter, setFilter] = useState("submitted");
  const [orders, setOrders] = useState([]);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    setStatus("loading");
    try {
      setOrders(await api.adminListPayments(filter || undefined));
      setStatus("done");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load payments.");
      setStatus("error");
    }
  }, [filter]);

  useEffect(() => {
    load();
  }, [load]);

  async function review(order, action) {
    setBusyId(order.id);
    setError(null);
    try {
      await action();
      window.dispatchEvent(new Event(PAYMENTS_CHANGED_EVENT));
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't update this payment.");
    } finally {
      setBusyId(null);
    }
  }

  function confirmPayment(order, txHash) {
    const ok = window.confirm(
      `Confirm ${order.amount_crypto} ${order.coin_symbol} from ${order.customer_email} ` +
        `(${order.reference})?\n\n` +
        "Only confirm after checking on the explorer that at least this amount arrived at " +
        `${order.pay_address}. This activates their ${order.plan_name} plan.`,
    );
    if (ok) review(order, () => api.confirmPayment(order.id, { txHash }));
  }

  function rejectPayment(order, note) {
    review(order, () => api.rejectPayment(order.id, note));
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-100">Payments</h1>
        <p className="mt-1 text-sm text-ink-500">
          Customers who clicked &quot;I have paid&quot;. Check each transaction on the block
          explorer, then confirm it to activate their plan — or reject it with a note.
        </p>
      </div>

      <div role="tablist" aria-label="Payment filter" className="flex gap-1 border-b border-base-700">
        {FILTERS.map((option) => (
          <button
            key={option.id || "all"}
            type="button"
            role="tab"
            aria-selected={filter === option.id}
            onClick={() => setFilter(option.id)}
            className={`-mb-px border-b-2 px-4 py-2.5 text-sm font-semibold ${
              filter === option.id
                ? "border-brand-500 text-brand-600"
                : "border-transparent text-ink-500 hover:text-ink-100"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      {error && (
        <div
          role="alert"
          className="rounded-lg border border-status-danger/30 bg-status-danger/10 px-4 py-3 text-sm text-status-danger"
        >
          {error}
        </div>
      )}

      {status === "loading" && <div className="text-sm text-ink-500">Loading...</div>}

      {status === "done" && orders.length === 0 && (
        <div className="rounded-2xl border border-dashed border-base-600 px-6 py-10 text-center text-sm text-ink-500">
          {filter === "submitted" ? "No payments are waiting for confirmation." : "No payments yet."}
        </div>
      )}

      {status === "done" && orders.length > 0 && (
        <ul className="flex flex-col gap-4">
          {orders.map((order) => (
            <PaymentCard
              key={order.id}
              order={order}
              busy={busyId === order.id}
              onConfirm={confirmPayment}
              onReject={rejectPayment}
            />
          ))}
        </ul>
      )}
    </div>
  );
}
