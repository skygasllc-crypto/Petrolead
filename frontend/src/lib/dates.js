// The API sends UTC timestamps without a zone suffix.
export function parseApiDate(value) {
  return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`);
}

export function formatDate(value) {
  return parseApiDate(value).toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export function formatDateTime(value) {
  return parseApiDate(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}
