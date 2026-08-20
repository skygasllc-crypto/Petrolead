import { NavLink, Outlet, useNavigate } from "react-router-dom";
import Logo from "./Logo";
import { useAuth } from "../context/AuthContext";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/discover", label: "Discover Companies" },
  { to: "/companies", label: "Companies" },
  { to: "/emails", label: "Emails" },
  { to: "/searches", label: "Search History" },
  { to: "/scheduled", label: "Scheduled Searches" },
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
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const navItems = user?.is_admin
    ? [...NAV_ITEMS, { to: "/admin/users", label: "Users" }]
    : NAV_ITEMS;

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="min-h-screen bg-base-900">
      <header className="sticky top-0 z-30 border-b border-base-700 bg-base-900/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-6 px-4 sm:px-6 lg:px-8">
          <Logo />
          <nav className="hidden items-center gap-1 md:flex">
            {navItems.map((item) => (
              <NavItem key={item.to} {...item} />
            ))}
          </nav>
          <div className="flex items-center gap-3">
            <span className="hidden max-w-[12rem] truncate text-sm text-ink-500 sm:inline">
              {user?.full_name || user?.email}
            </span>
            <button
              type="button"
              onClick={handleLogout}
              className="rounded-md border border-base-600 px-3 py-1.5 text-xs font-medium text-ink-300 hover:border-status-danger hover:text-status-danger"
            >
              Log out
            </button>
          </div>
        </div>
        <nav className="flex items-center gap-1 overflow-x-auto border-t border-base-800 px-4 py-2 md:hidden">
          {navItems.map((item) => (
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
