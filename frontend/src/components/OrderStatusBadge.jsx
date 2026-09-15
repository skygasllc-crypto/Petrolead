import { ORDER_STATUS } from "../lib/payments";

export default function OrderStatusBadge({ status }) {
  const { label, classes } = ORDER_STATUS[status] ?? { label: status, classes: "border-base-600" };
  return (
    <span
      className={`inline-flex whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-semibold ${classes}`}
    >
      {label}
    </span>
  );
}
