import { NavLink, Outlet } from "react-router-dom";
import Logo from "./Logo";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/discover", label: "Discover Companies" },
  { to: "/companies", label: "Companies" },
  { to: "/searches", label: "Search History" },
  { to: "/settings", label: "Settings" },
];

function NavItem({ to, label, end }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `rounded-md px-3 py-2 text-sm font-medium transition-colors ${
          isActive
            ? "bg-base-800 text-brass-400"
            : "text-ink-500 hover:bg-base-800/60 hover:text-ink-100"
        }`
      }
    >
      {label}
    </NavLink>
  );
}

export default function Layout() {
  return (
    <div className="min-h-screen bg-base-900">
      <header className="sticky top-0 z-30 border-b border-base-700 bg-base-900/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-6 px-4 sm:px-6 lg:px-8">
          <Logo />
          <nav className="hidden items-center gap-1 md:flex">
            {NAV_ITEMS.map((item) => (
              <NavItem key={item.to} {...item} />
            ))}
          </nav>
          <div className="flex items-center gap-3">
            <span className="hidden rounded-full border border-base-600 px-3 py-1 text-xs font-medium text-ink-500 sm:inline">
              Phase 1 · Company Discovery
            </span>
          </div>
        </div>
        <nav className="flex items-center gap-1 overflow-x-auto border-t border-base-800 px-4 py-2 md:hidden">
          {NAV_ITEMS.map((item) => (
            <NavItem key={item.to} {...item} />
          ))}
        </nav>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <Outlet />
      </main>

      <footer className="mx-auto max-w-7xl px-4 py-8 text-xs text-ink-700 sm:px-6 lg:px-8">
        PetroLead — petroleum &amp; energy B2B lead intelligence platform. Phase 1: Company
        Discovery.
      </footer>
    </div>
  );
}
