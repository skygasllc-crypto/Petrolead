export const REGIONS = [
  "Africa",
  "Asia",
  "Europe",
  "Middle East",
  "North America",
  "South America",
  "Central Asia",
  "Caucasus",
  "Other",
];

export const INDUSTRIES = [
  "Petroleum Trading",
  "Oil & Gas",
  "Fuel Supply",
  "Refinery",
  "Tank Storage",
  "Petroleum Logistics",
  "Bunkering",
  "Energy Trading",
  "Oil Terminal",
  "Distributor",
];

export const PRODUCTS = [
  "EN590",
  "Diesel",
  "Jet A1",
  "Fuel Oil",
  "Crude Oil",
  "LPG",
  "LNG",
  "Bitumen",
  "Gasoline",
  "Naphtha",
  "Petroleum Coke",
  "Other",
];

export const RESULT_LIMITS = [10, 25, 50, 100];

export const COUNTRIES = [
  "United Arab Emirates",
  "Saudi Arabia",
  "Qatar",
  "Kuwait",
  "Bahrain",
  "Oman",
  "Nigeria",
  "Angola",
  "Egypt",
  "Algeria",
  "Libya",
  "South Africa",
  "United States",
  "Canada",
  "Mexico",
  "Brazil",
  "Venezuela",
  "United Kingdom",
  "Netherlands",
  "Norway",
  "Russia",
  "Turkey",
  "China",
  "India",
  "Singapore",
  "Indonesia",
  "Malaysia",
  "South Korea",
  "Japan",
  "Australia",
  "Kazakhstan",
  "Azerbaijan",
  "Georgia",
];

export function relevanceTier(score) {
  if (score >= 80) return { label: "Highly Relevant", tone: "high" };
  if (score >= 60) return { label: "Relevant", tone: "relevant" };
  if (score >= 30) return { label: "Possible", tone: "possible" };
  return { label: "Low", tone: "low" };
}

const SOURCE_LABELS = {
  search: "Web Search",
  social: "Social Search",
  b2b_directory: "B2B Directory",
  website: "Website",
};

export function sourceLabel(source) {
  if (!source) return "—";
  const [prefix] = source.split(":");
  return SOURCE_LABELS[prefix] || prefix.replace(/_/g, " ");
}
