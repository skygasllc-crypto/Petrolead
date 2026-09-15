import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import Icon from "../components/marketing/Icon";
import SiteHeader, { primaryButton, secondaryButton } from "../components/marketing/SiteHeader";
import SiteFooter from "../components/marketing/SiteFooter";
import StatsBand from "../components/marketing/StatsBand";
import Faq from "../components/marketing/Faq";
import FinalCta from "../components/marketing/FinalCta";
import { PRODUCTS } from "../components/marketing/content";

const SECTORS = [
  "Refineries",
  "Fuel & oil traders",
  "Lubricant distributors",
  "Shipping & bunkering",
  "LPG & natural gas",
  "Oilfield services",
];

const FAQS = [
  {
    q: "What is PetroLead?",
    a: "PetroLead is a B2B lead platform for the petroleum and energy trade. It finds companies — refiners, fuel traders, distributors, shipping and bunkering firms — and the business contacts you need to reach them.",
  },
  {
    q: "How does PetroLead find email addresses?",
    a: "It reads companies' own public websites and contact pages, uses search-engine results, and for named people queries a business email-finder service. It never logs into or scrapes login-gated sites such as LinkedIn.",
  },
  {
    q: "How accurate are the emails?",
    a: "Every email is checked and labeled with its validity, so you can see which addresses are verified before you reach out. Person lookups only return a result when a business email was actually found.",
  },
  {
    q: "What data do I get besides emails?",
    a: "Company name, website and description, country and industry, phone numbers, contact pages, social profiles, a relevance rating and a 0–100 lead score.",
  },
  {
    q: "Can I export my leads?",
    a: "Yes. Export companies or emails as CSV or Excel, filtered by country, industry, lead score, email availability and more.",
  },
  {
    q: "Can PetroLead watch for new leads automatically?",
    a: "Yes. Save any search and schedule it — PetroLead reruns it and shows you the companies it hasn't found before.",
  },
  {
    q: "Is it legal to contact these leads?",
    a: "PetroLead only collects business contact information that companies publish publicly. You're responsible for reaching out in line with the laws that apply to you, such as GDPR and anti-spam rules.",
  },
];

function Hero() {
  const { user } = useAuth();
  return (
    <section>
      <div className="mx-auto max-w-4xl px-4 pb-20 pt-16 text-center sm:px-6 sm:pt-24 lg:px-8">
        <h1 className="text-4xl font-extrabold tracking-tight text-ink-100 sm:text-6xl">
          Find energy buyers.
          <span className="block text-brand-500">Close more deals.</span>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-ink-500">
          Discover petroleum and energy companies, find the decision-makers behind them, and get
          their verified business emails — all in one place.
        </p>
        <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Link
            to={user ? "/dashboard" : "/register"}
            className={`${primaryButton} px-7 py-3.5 text-base`}
          >
            {user ? "Go to dashboard" : "Create your account"}
          </Link>
          {!user && (
            <Link to="/login" className={`${secondaryButton} px-7 py-3.5 text-base`}>
              Log in
            </Link>
          )}
        </div>

        <p className="mt-14 text-sm font-medium text-ink-700">
          Built for teams across the energy trade
        </p>
        <ul className="mx-auto mt-5 flex max-w-3xl flex-wrap justify-center gap-x-8 gap-y-3">
          {SECTORS.map((s) => (
            <li key={s} className="text-base font-semibold text-ink-500">
              {s}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function Features() {
  return (
    <section id="features" className="scroll-mt-24 bg-base-900 py-20">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <h2 className="text-center text-3xl font-bold tracking-tight text-ink-100 sm:text-4xl">
          Everything you need to reach the right buyer.
        </h2>
        <p className="mx-auto mt-4 max-w-2xl text-center text-ink-500">
          From finding the company to finding the person&apos;s email — without leaving PetroLead.
        </p>
        <div className="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {PRODUCTS.map((p) => (
            <div
              key={p.title}
              className="flex flex-col rounded-2xl border border-base-700 bg-base-850 p-6 shadow-sm transition-shadow hover:shadow-md"
            >
              <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-500">
                <Icon name={p.icon} className="h-6 w-6" />
              </span>
              <h3 className="mt-5 text-lg font-semibold text-ink-100">{p.title}</h3>
              <p className="mt-2 flex-1 text-sm leading-relaxed text-ink-500">{p.description}</p>
              {!p.to.startsWith("/#") && (
                <Link
                  to={p.to}
                  className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-brand-600 hover:text-brand-700"
                >
                  Learn more <Icon name="arrowRight" className="h-4 w-4" />
                </Link>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export default function Landing() {
  return (
    <div className="relative min-h-screen bg-base-850">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-[46rem] bg-gradient-to-b from-brand-50 to-transparent"
      />
      <SiteHeader />
      <main className="relative">
        <Hero />
        <StatsBand />
        <Features />
        <Faq items={FAQS} />
        <FinalCta
          title="Start building your energy lead list today"
          points={["Company discovery", "Verified business emails", "CSV & Excel export"]}
        />
      </main>
      <SiteFooter />
    </div>
  );
}
