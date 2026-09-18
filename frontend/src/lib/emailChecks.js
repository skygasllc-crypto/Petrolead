// Email Verifier results from POST /api/emails/verify.
// Matches MAX_VERIFY_EMAILS and the status/reason values in app/schemas.py.
export const MAX_VERIFY_EMAILS = 500;

// Only this status is safe to send to. "risky" is not a milder "deliverable":
// it means we could not establish that the mailbox exists.
export const SAFE_TO_SEND = "deliverable";

// Reasons that mean "shared inbox, not a person". A confirmed one is
// deliverable — it won't bounce — but it's still worth showing apart from a
// named person's address, so the two reasons share one marker.
export const SHARED_INBOX_REASONS = new Set(["role_account", "role_confirmed"]);

export const EMAIL_CHECK_STATUS = {
  deliverable: {
    label: "Deliverable",
    classes: "border-status-high/30 bg-status-high/10 text-status-high",
    description: "The mailbox accepted mail when we checked.",
  },
  undeliverable: {
    label: "Undeliverable",
    classes: "border-status-danger/30 bg-status-danger/10 text-status-danger",
    description: "This will bounce. Remove it before sending.",
  },
  risky: {
    label: "Risky",
    classes: "border-status-possible/30 bg-status-possible/10 text-status-possible",
    description: "It may bounce — we couldn't confirm the mailbox itself.",
  },
  unknown: {
    label: "Couldn't check",
    classes: "border-base-600 bg-base-800 text-ink-300",
    description: "The check couldn't complete — try these again later.",
  },
};

// Why an address got its status. Shown instead of the generic description
// when we know something more specific.
export const EMAIL_CHECK_REASON = {
  mailbox_confirmed: "The mail server accepted this specific mailbox.",
  invalid_format: "This isn't a correctly formatted email address.",
  no_mail_server: "The domain has no mail servers, so mail to it bounces.",
  disposable_domain: "A throwaway mailbox provider — mail here goes nowhere useful.",
  typo_suspected: "The domain looks like a misspelling of a common provider.",
  mailbox_not_found: "The mail server said this mailbox doesn't exist.",
  catch_all: "The domain accepts every address, so this one can't be confirmed.",
  role_account: "A shared inbox (info@, sales@) — the mailbox itself wasn't checked.",
  role_confirmed: "A shared inbox (info@, sales@). The mail server accepted it.",
  domain_only: "The domain accepts mail, but the mailbox itself wasn't checked.",
  dns_error: "The domain's mail servers couldn't be reached right now.",
  provider_error: "The verification service couldn't be reached right now.",
};
