// Crypto payment order statuses returned by the API (app/services/payment_service.py).
export const ORDER_STATUS = {
  awaiting_payment: {
    label: "Awaiting payment",
    classes: "border-brand-100 bg-brand-50 text-brand-600",
  },
  submitted: {
    label: "Waiting for confirmation",
    classes: "border-status-possible/30 bg-status-possible/10 text-status-possible",
  },
  confirmed: {
    label: "Confirmed",
    classes: "border-status-high/30 bg-status-high/10 text-status-high",
  },
  rejected: {
    label: "Rejected",
    classes: "border-status-danger/30 bg-status-danger/10 text-status-danger",
  },
  cancelled: { label: "Cancelled", classes: "border-base-600 text-ink-500" },
  expired: { label: "Quote expired", classes: "border-base-600 text-ink-500" },
};

// Fired after an admin confirms or rejects a payment, so the menu badge updates.
export const PAYMENTS_CHANGED_EVENT = "petrolead:payments-changed";

export function checkoutPath(plan, credits, period) {
  return `/checkout?plan=${plan}&credits=${credits}&period=${period}`;
}
