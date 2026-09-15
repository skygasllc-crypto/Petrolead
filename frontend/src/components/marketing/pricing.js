// DRAFT pricing — Professional and Enterprise tiers mirror Skrapp's published
// prices (skrapp.io/pricing, checked September 2026); Basic is our own entry
// plan. Confirm before launch. None of these limits are enforced by the
// backend yet: there is no billing, subscription or credits system.

// Yearly billing takes 25% off the monthly price (rounded to the dollar).
export const YEARLY_DISCOUNT = 0.25;

// TODO: replace with a real, monitored sales address before launch.
export const SALES_EMAIL = "sales@petrolead.example";

export const PLANS = [
  {
    id: "basic",
    name: "Basic",
    tagline: "Everything you need to start prospecting.",
    tiers: [{ credits: 1000, monthly: 20, users: 1 }],
    outlined: true,
    cta: "Start with Basic",
    featuresHeading: "Basic includes:",
    features: [
      "Company Discovery",
      "LinkedIn Email Finder",
      "Name + company lookup",
      "Email validity labels",
      "Email Extractor",
      "Email Verifier",
      "Email Directory",
    ],
  },
  {
    id: "professional",
    name: "Professional",
    tagline: "For traders and sales teams ready to scale.",
    popular: true,
    tiers: [
      { credits: 2000, monthly: 39, users: 2 },
      { credits: 5000, monthly: 99, users: 5 },
      { credits: 10000, monthly: 129, users: 8 },
      { credits: 25000, monthly: 199, users: 8 },
    ],
    cta: "Start with Professional",
    featuresHeading: "Everything in Basic, plus:",
    features: [
      "Bulk Contact Lookup",
      "CSV & Excel export",
      "Advanced filters",
      "5 scheduled searches",
      "50 discovery searches/day",
    ],
  },
  {
    id: "enterprise",
    name: "Enterprise",
    tagline: "For teams prospecting at volume.",
    tiers: [
      { credits: 50000, monthly: 349, users: 15 },
      { credits: 100000, monthly: 599, users: 15 },
      { credits: 250000, monthly: 999, users: 30 },
      { credits: 500000, monthly: 1499, users: 30 },
    ],
    cta: "Get started with Enterprise",
    featuresHeading: "Everything in Professional, plus:",
    features: [
      "Unlimited scheduled searches",
      "250 discovery searches/day",
      "Team user management",
      "Priority support",
    ],
  },
];

// Comparison table rows. `values` are per plan, in PLANS order:
// true = included, false = not included, number/string = shown as-is.
// Rows with a `type` are read from each plan's currently selected tier.
export const COMPARISON = [
  {
    category: "Credits & users",
    rows: [
      { label: "Email credits", type: "credits" },
      { label: "Users", type: "users" },
      { label: "Only pay for emails that are found", values: [true, true, true] },
      { label: "Unused credits roll over", values: [true, true, true] },
    ],
  },
  {
    category: "Search capacity",
    rows: [
      { label: "Company discovery searches / day", values: [5, 50, 250] },
      { label: "Results per discovery search", values: [10, 50, 100] },
      { label: "People per bulk lookup", values: [false, 25, 25] },
      { label: "Scheduled searches", values: [false, 5, "Unlimited"] },
    ],
  },
  {
    category: "Core features",
    rows: [
      { label: "Company Discovery", values: [true, true, true] },
      { label: "LinkedIn Email Finder", values: [true, true, true] },
      { label: "Name + company lookup", values: [true, true, true] },
      { label: "Email Extractor (company websites)", values: [true, true, true] },
      { label: "Email Verifier (up to 50 per check)", values: [true, true, true] },
      { label: "Email validity labels", values: [true, true, true] },
      { label: "Lead scoring", values: [true, true, true] },
    ],
  },
  {
    category: "Lists & exports",
    rows: [
      { label: "Email Directory", values: [true, true, true] },
      { label: "Advanced filters", values: [false, true, true] },
      { label: "CSV & Excel export", values: [false, true, true] },
    ],
  },
  {
    category: "Team & support",
    rows: [
      { label: "Team user management", values: [false, false, true] },
      { label: "Priority support", values: [false, false, true] },
    ],
  },
];

export const PRICING_FAQS = [
  {
    q: "What are email credits?",
    a: "One credit is used each time PetroLead finds a business email for you — from a LinkedIn profile link, a name and company, or a line in a bulk lookup.",
  },
  {
    q: "When do I use credits?",
    a: "Only when an email is found. A lookup that comes back without a business email doesn't use a credit.",
  },
  {
    q: "Do unused credits roll over?",
    a: "Yes — on every plan, unused credits carry over to the next month while your subscription is active.",
  },
  {
    q: "How do team members share credits?",
    a: "Everyone on a plan draws from one shared pool of credits, so your team can prospect together without splitting allowances.",
  },
  {
    q: "What happens when I run out of credits?",
    a: "Email lookups pause until your credits renew, or you can move to a larger credit tier at any time. Your saved companies and emails stay available.",
  },
  {
    q: "Can I change plans at any time?",
    a: "Yes. Upgrade or downgrade whenever you like — a larger credit tier is available right away.",
  },
  {
    q: "Is there a long-term contract?",
    a: `No. Pay monthly, or pay yearly to save ${YEARLY_DISCOUNT * 100}%, and cancel any time.`,
  },
];
