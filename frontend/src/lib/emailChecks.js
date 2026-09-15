// Email Verifier statuses returned by POST /api/emails/verify.
// Matches MAX_VERIFY_EMAILS in app/schemas.py.
export const MAX_VERIFY_EMAILS = 50;

export const EMAIL_CHECK_STATUS = {
  valid: {
    label: "Domain accepts mail",
    classes: "border-status-high/30 bg-status-high/10 text-status-high",
    description: "Correctly formatted, and the domain is set up to receive email.",
  },
  no_mail_server: {
    label: "No mail server",
    classes: "border-status-danger/30 bg-status-danger/10 text-status-danger",
    description: "The domain has no mail servers, so email sent to it will bounce.",
  },
  invalid_format: {
    label: "Invalid format",
    classes: "border-status-danger/30 bg-status-danger/10 text-status-danger",
    description: "This isn't a correctly formatted email address.",
  },
  unknown: {
    label: "Couldn't check",
    classes: "border-status-possible/30 bg-status-possible/10 text-status-possible",
    description: "The domain's mail servers couldn't be checked right now — try again later.",
  },
};
