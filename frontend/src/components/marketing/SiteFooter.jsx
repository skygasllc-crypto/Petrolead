import { Link } from "react-router-dom";
import Logo from "../Logo";
import { PRODUCTS } from "./content";

const COLUMNS = [
  { title: "Product", links: PRODUCTS.map((p) => ({ label: p.title, to: p.to })) },
  {
    title: "Account",
    links: [
      { label: "Log in", to: "/login" },
      { label: "Sign up", to: "/register" },
    ],
  },
  {
    title: "Resources",
    links: [
      { label: "Pricing", to: "/pricing" },
      { label: "FAQ", to: "/#faq" },
    ],
  },
  {
    title: "Legal",
    links: [
      { label: "Terms of Service", to: "/terms" },
      { label: "Privacy Policy", to: "/privacy" },
    ],
  },
];

export default function SiteFooter() {
  return (
    <footer className="border-t border-base-700 bg-base-900">
      <div className="mx-auto grid max-w-7xl gap-10 px-4 py-14 sm:px-6 md:grid-cols-5 lg:px-8">
        <div className="md:col-span-2">
          <Logo />
          <p className="mt-4 max-w-xs text-sm leading-relaxed text-ink-500">
            Company discovery and verified business emails for the petroleum and energy trade.
          </p>
        </div>
        {COLUMNS.map((col) => (
          <div key={col.title}>
            <h3 className="text-sm font-semibold text-ink-100">{col.title}</h3>
            <ul className="mt-4 flex flex-col gap-2.5">
              {col.links.map((l) => (
                <li key={l.label}>
                  <Link to={l.to} className="text-sm text-ink-500 hover:text-brand-500">
                    {l.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="border-t border-base-700">
        <p className="mx-auto max-w-7xl px-4 py-6 text-xs text-ink-700 sm:px-6 lg:px-8">
          © {new Date().getFullYear()} PetroLead. All rights reserved.
        </p>
      </div>
    </footer>
  );
}
