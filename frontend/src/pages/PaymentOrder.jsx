import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import QRCode from "qrcode";
import { api, ApiError } from "../api/client";
import { useBilling } from "../context/BillingContext";
import Icon from "../components/marketing/Icon";
import OrderStatusBadge from "../components/OrderStatusBadge";
import { formatDate, formatDateTime, parseApiDate } from "../lib/dates";
import { checkoutPath } from "../lib/payments";

const primaryButton =
  "inline-flex items-center justify-center gap-2 rounded-md bg-brand-500 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60";
const card = "rounded-2xl border border-base-700 bg-base-850 p-6 shadow-sm";

function errorMessage(err, fallback) {
  return err instanceof ApiError ? err.message : fallback;
}

function useNow(active) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return undefined;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [active]);
  return now;
}

function CopyValue({ label, value }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div>
      <div className="text-xs font-medium text-ink-700">{label}</div>
      <div className="mt-1.5 flex items-center gap-2 rounded-lg border border-base-700 bg-base-900 px-3 py-2.5">
        <span className="min-w-0 flex-1 break-all font-mono text-sm font-semibold text-ink-100">
          {value}
        </span>
        <button
          type="button"
          onClick={copy}
          aria-label={`Copy ${label.toLowerCase()}`}
          className="inline-flex shrink-0 items-center gap-1 rounded-md border border-base-600 bg-base-850 px-2.5 py-1 text-xs font-semibold text-ink-300 hover:border-brand-500 hover:text-brand-600"
        >
          <Icon name={copied ? "check" : "copy"} className="h-3.5 w-3.5" />
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
    </div>
  );
}

function PaymentQr({ order }) {
  // Bitcoin wallets understand a BIP21 URI with the amount; TRON wallets take the address.
  const value =
    order.currency === "BTC"
      ? `bitcoin:${order.pay_address}?amount=${order.amount_crypto}`
      : order.pay_address;
  const [src, setSrc] = useState(null);

  useEffect(() => {
    let active = true;
    QRCode.toDataURL(value, { margin: 1, width: 220 })
      .then((url) => active && setSrc(url))
      .catch(() => active && setSrc(null));
    return () => {
      active = false;
    };
  }, [value]);

  if (!src) return null;
  return (
    <img
      src={src}
      width={220}
      height={220}
      alt={`QR code for the ${order.coin_name} payment address`}
      className="mx-auto rounded-lg border border-base-700"
    />
  );
}

function AwaitingPayment({ order, onUpdated, onCancelled }) {
  const now = useNow(true);
  const expiresAt = parseApiDate(order.expires_at).getTime();
  const quoteExpired = order.status === "expired" || now >= expiresAt;
  const secondsLeft = Math.max(0, Math.floor((expiresAt - now) / 1000));

  const [txHash, setTxHash] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function markPaid(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onUpdated(await api.markOrderPaid(order.id, txHash.trim()));
    } catch (err) {
      setError(errorMessage(err, "Couldn't mark this order as paid."));
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    if (!window.confirm("Cancel this order? Don't cancel if you've already sent the payment.")) {
      return;
    }
    try {
      await api.cancelOrder(order.id);
      onCancelled();
    } catch (err) {
      setError(errorMessage(err, "Couldn't cancel this order."));
    }
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_18rem]">
      <section className={card}>
        <h2 className="text-base font-semibold text-ink-100">1. Send exactly this amount</h2>
        {quoteExpired ? (
          <p className="mt-2 rounded-lg border border-status-possible/30 bg-status-possible/10 px-3 py-2 text-sm text-status-possible">
            {order.usd_rate
              ? "This price quote has expired. If you haven't sent the payment yet, cancel and start a new order for an up-to-date amount. If you already sent it, enter the transaction ID below."
              : "This order has expired. If you already sent the payment, enter the transaction ID below."}
          </p>
        ) : (
          <p className="mt-2 text-sm text-ink-500">
            {order.usd_rate ? "Price held for " : "Mark this order paid within "}
            <strong className="font-semibold text-ink-100">
              {Math.floor(secondsLeft / 3600) > 0 && `${Math.floor(secondsLeft / 3600)}h `}
              {Math.floor((secondsLeft % 3600) / 60)}:{String(secondsLeft % 60).padStart(2, "0")}
            </strong>
            {order.usd_rate && (
              <span className="text-ink-700">
                {" "}
                · 1 {order.coin_symbol} = ${Number(order.usd_rate).toLocaleString()}
              </span>
            )}
          </p>
        )}

        <div className="mt-5 flex flex-col gap-4">
          <CopyValue label={`Amount (${order.coin_symbol})`} value={order.amount_crypto} />
          <CopyValue label={`${order.coin_name} address`} value={order.pay_address} />
        </div>

        <div className="mt-4 rounded-lg border border-status-danger/30 bg-status-danger/5 px-4 py-3 text-sm leading-relaxed text-status-danger">
          <strong className="font-semibold">Send on the {order.network} network only.</strong>{" "}
          Coins sent on any other network can&apos;t be recovered. Exchange withdrawal fees come
          on top — make sure the full amount arrives.
        </div>

        <h2 className="mt-8 text-base font-semibold text-ink-100">2. Tell us you&apos;ve paid</h2>
        <form onSubmit={markPaid} className="mt-3">
          <label htmlFor="tx-hash" className="text-sm font-medium text-ink-300">
            Transaction ID (TXID)
          </label>
          <input
            id="tx-hash"
            value={txHash}
            onChange={(e) => setTxHash(e.target.value)}
            required
            autoComplete="off"
            spellCheck={false}
            placeholder="The 64-character ID of your transaction"
            className="mt-1.5 w-full rounded-md border border-base-600 bg-base-850 px-3 py-2.5 font-mono text-sm text-ink-100 placeholder:font-sans placeholder:text-ink-700 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
          />
          <p className="mt-1.5 text-xs text-ink-700">
            You&apos;ll find it in your wallet, or in your exchange&apos;s withdrawal history, once
            the payment is sent.
          </p>
          {error && (
            <p role="alert" className="mt-3 text-sm text-status-danger">
              {error}
            </p>
          )}
          <div className="mt-5 flex flex-wrap items-center gap-5">
            <button type="submit" disabled={busy || !txHash.trim()} className={primaryButton}>
              {busy ? "Sending..." : "I have paid"}
            </button>
            <button
              type="button"
              onClick={cancel}
              className="text-sm font-semibold text-ink-500 hover:text-status-danger"
            >
              Cancel order
            </button>
          </div>
        </form>
      </section>

      <aside className={`${card} h-fit text-center`}>
        <PaymentQr order={order} />
        <p className="mt-3 text-xs text-ink-500">Scan with your wallet app</p>
      </aside>
    </div>
  );
}

function Notice({ icon, tone, title, children }) {
  return (
    <section className={card}>
      <div className="flex items-start gap-4">
        <span
          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${tone}`}
          aria-hidden="true"
        >
          <Icon name={icon} className="h-5 w-5" />
        </span>
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-ink-100">{title}</h2>
          <div className="mt-1 text-sm leading-relaxed text-ink-500">{children}</div>
        </div>
      </div>
    </section>
  );
}

function TransactionLink({ order }) {
  if (!order.tx_hash) return null;
  return (
    <p className="mt-3 break-all font-mono text-xs text-ink-700">
      TXID {order.tx_hash} ·{" "}
      <a
        href={order.explorer_url}
        target="_blank"
        rel="noopener noreferrer"
        className="font-sans font-semibold text-brand-600 hover:underline"
      >
        View on explorer
      </a>
    </p>
  );
}

export default function PaymentOrder() {
  const { orderId } = useParams();
  const navigate = useNavigate();
  const { billing, refresh: refreshBilling } = useBilling();
  const [order, setOrder] = useState(null);
  const [loadError, setLoadError] = useState(null);

  const load = useCallback(async () => {
    try {
      const next = await api.getOrder(orderId);
      setOrder(next);
      if (next.status === "confirmed") refreshBilling();
    } catch (err) {
      setLoadError(errorMessage(err, "Couldn't load this order."));
    }
  }, [orderId, refreshBilling]);

  useEffect(() => {
    load();
  }, [load]);

  // While a payment waits for an admin, check back so the page updates on its own.
  useEffect(() => {
    if (order?.status !== "submitted") return undefined;
    const timer = setInterval(load, 30000);
    return () => clearInterval(timer);
  }, [order?.status, load]);

  if (loadError) {
    return (
      <div
        role="alert"
        className="rounded-lg border border-status-danger/30 bg-status-danger/10 px-4 py-3 text-sm text-status-danger"
      >
        {loadError}
      </div>
    );
  }
  if (!order) return <div className="text-sm text-ink-500">Loading...</div>;

  const again = checkoutPath(order.plan, order.credits_per_month, order.billing_period);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/billing" className="text-sm font-semibold text-brand-600 hover:text-brand-700">
            ← Plan &amp; credits
          </Link>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-ink-100">
            Pay for {order.plan_name}
          </h1>
          <p className="mt-1 text-sm text-ink-500">
            {order.credits_per_month.toLocaleString()} credits/month ·{" "}
            {order.billing_period === "yearly" ? "12 months" : "1 month"} · ${order.amount_usd}
          </p>
        </div>
        <OrderStatusBadge status={order.status} />
      </div>

      {(order.status === "awaiting_payment" || order.status === "expired") && (
        <AwaitingPayment order={order} onUpdated={setOrder} onCancelled={() => navigate("/billing")} />
      )}

      {order.status === "submitted" && (
        <Notice
          icon="clock"
          tone="bg-status-possible/10 text-status-possible"
          title="Thanks — we're checking your payment"
        >
          <p>
            We&apos;ve been notified. Your plan starts as soon as the transaction is confirmed —
            this page updates on its own.
          </p>
          <TransactionLink order={order} />
        </Notice>
      )}

      {order.status === "confirmed" && (
        <Notice icon="check" tone="bg-status-high/15 text-status-high" title="Payment confirmed">
          <p>
            Your {order.plan_name} plan is active
            {billing?.paid_until ? ` until ${formatDate(billing.paid_until)}` : ""}.
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            <Link to="/email-finder" className={primaryButton}>
              Start finding emails
            </Link>
            <Link
              to="/billing"
              className="inline-flex items-center rounded-md border border-base-600 px-5 py-2.5 text-sm font-semibold text-ink-300 hover:border-brand-500 hover:text-brand-600"
            >
              View your plan
            </Link>
          </div>
          <TransactionLink order={order} />
        </Notice>
      )}

      {order.status === "rejected" && (
        <Notice
          icon="close"
          tone="bg-status-danger/10 text-status-danger"
          title="We couldn't confirm this payment"
        >
          {order.admin_note && (
            <p className="rounded-lg border border-base-700 bg-base-900 px-3 py-2 text-ink-300">
              {order.admin_note}
            </p>
          )}
          <p className="mt-3">
            Reviewed {order.reviewed_at ? formatDateTime(order.reviewed_at) : ""}. If you think
            this is a mistake, reply to us with your transaction ID, or start a new order.
          </p>
          <Link to={again} className={`${primaryButton} mt-4`}>
            Start a new order
          </Link>
          <TransactionLink order={order} />
        </Notice>
      )}

      {order.status === "cancelled" && (
        <Notice icon="close" tone="bg-base-800 text-ink-500" title="This order was cancelled">
          <Link to={again} className={`${primaryButton} mt-3`}>
            Start a new order
          </Link>
        </Notice>
      )}
    </div>
  );
}
