import { EMAIL_CHECK_STATUS } from "../lib/emailChecks";

// Pill for an Email Verifier status (valid / no_mail_server / invalid_format / unknown).
export default function EmailCheckBadge({ status }) {
  const { label, classes } = EMAIL_CHECK_STATUS[status];
  return (
    <span
      className={`inline-flex whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] font-semibold ${classes}`}
    >
      {label}
    </span>
  );
}
