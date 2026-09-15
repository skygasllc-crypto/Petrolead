// Shared "verified / unverified / check pending" pill for an is_valid
// tri-state (true/false/null), used for both emails and phone numbers.
export default function ValidityBadge({ isValid }) {
  if (isValid === true) {
    return (
      <span className="rounded-full border border-status-high/30 bg-status-high/15 px-2 py-0.5 text-[10px] font-medium text-status-high">
        Verified
      </span>
    );
  }
  if (isValid === false) {
    return (
      <span className="rounded-full border border-status-low/30 bg-status-low/15 px-2 py-0.5 text-[10px] font-medium text-status-low">
        Unverified
      </span>
    );
  }
  return (
    <span className="rounded-full border border-base-600 px-2 py-0.5 text-[10px] font-medium text-ink-700">
      Check pending
    </span>
  );
}
