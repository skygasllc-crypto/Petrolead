// Shared copy for the public marketing pages (landing + product pages).

export const PRODUCTS = [
  {
    icon: "building",
    title: "Company Search",
    description: "Find petroleum and energy companies by region, product and activity.",
    to: "/company-search",
  },
  {
    icon: "link",
    title: "LinkedIn Email Finder",
    description: "Paste a profile link and get the person's business email.",
    to: "/linkedin-email-finder",
  },
  {
    icon: "users",
    title: "Bulk Contact Lookup",
    description: "Look up to 25 people at once by profile link or name and company.",
    to: "/linkedin-email-finder#bulk",
  },
  {
    icon: "globe",
    title: "Email Extractor",
    description: "Pull every business email and phone number a company website publishes.",
    to: "/email-extractor",
  },
  {
    icon: "shieldCheck",
    title: "Email Verifier",
    description: "Check addresses are well-formed and their domains can receive mail.",
    to: "/email-verifier",
  },
  {
    icon: "envelope",
    title: "Email Directory",
    description: "Every email you've found, with validity status, in one searchable list.",
    to: "/#features",
  },
  {
    icon: "chart",
    title: "Lead Scoring",
    description: "Every company gets a 0–100 score so the best leads rise to the top.",
    to: "/company-search#lead-scoring",
  },
  {
    icon: "clock",
    title: "Scheduled Searches",
    description: "Save a search and PetroLead reruns it to catch new companies.",
    to: "/company-search#monitoring",
  },
];

export const STATS = [
  { value: "Email-first", label: "Only contacts with a found email" },
  { value: "0–100", label: "Lead score on every company" },
  { value: "CSV · Excel", label: "Export any filtered list" },
  { value: "Automatic", label: "Scheduled searches rerun on their own" },
];
