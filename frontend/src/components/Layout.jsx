import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import Logo from "./Logo";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { BillingProvider, useBilling } from "../context/BillingContext";
import { PAYMENTS_CHANGED_EVENT } from "../lib/payments";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard", end: true },
  { to: "/discover", label: "Company Search" },
  { to: "/email-finder", label: "Email Finder" },
  { to: "/verify-emails", label: "Email Verifier" },
  { to: "/companies", label: "Companies" },
  { to: "/emails", label: "Emails" },
  { to: "/searches", label: "History" },
  { to: "/scheduled", label: "Scheduled" },
  { to: "/billing", label: "Plan & Credits" },
  { to: "/settings", label: "Settings" },
];

function NavItem({ to, label, end, badge }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `inline-flex items-center whitespace-nowrap rounded-md px-3 py-2 text-sm font-medium transition-colors ${
          isActive
            ? "bg-brand-50 text-brand-600"
            : "text-ink-500 hover:bg-base-900 hover:text-ink-100"
        }`
      }
    >
      {label}
      {badge > 0 && (
        <span className="ml-1.5 rounded-full bg-status-danger px-1.5 py-0.5 text-[10px] font-bold leading-none text-white">
          {badge}
          <span className="sr-only"> waiting</span>
        </span>
      )}
    </NavLink>
  );
}

/** How many payments are waiting for an admin — checked every minute, and
 * right after an admin confirms or rejects one. */
function usePendingPayments(enabled) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!enabled) return undefined;
    let active = true;
    const load = () =>
      api
        .adminPendingPaymentsCount()
        .then((result) => active && setCount(result.count))
        .catch(() => {});
    load();
    const timer = setInterval(load, 60000);
    window.addEventListener(PAYMENTS_CHANGED_EVENT, load);
    return () => {
      active = false;
      clearInterval(timer);
      window.removeEventListener(PAYMENTS_CHANGED_EVENT, load);
    };
  }, [enabled]);

  return count;
}

function CreditsBadge() {
  const { billing } = useBilling();
  if (!billing || billing.exempt) return null;
  const warning = !billing.plan || billing.expired;
  return (
    <Link
      to="/billing"
      className={`hidden items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold sm:inline-flex ${
        warning
          ? "border-status-possible/30 bg-status-possible/10 text-status-possible"
          : "border-brand-100 bg-brand-50 text-brand-600 hover:border-brand-500"
      }`}
    >
      {!billing.plan && "No plan — choose one"}
      {billing.plan && billing.expired && `${billing.plan_name} ended — renew`}
      {billing.plan && !billing.expired && (
        <>
          <span>{billing.plan_name}</span>
          <span aria-hidden="true" className="h-3 w-px bg-brand-100" />
          <span>{billing.credits_balance.toLocaleString()} credits</span>
        </>
      )}
    </Link>
  );
}

function AppShell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const pendingPayments = usePendingPayments(Boolean(user?.is_admin));

  const navItems = user?.is_admin
    ? [
        ...NAV_ITEMS,
        { to: "/admin/payments", label: "Payments", badge: pendingPayments },
        { to: "/admin/users", label: "Users" },
      ]
    : NAV_ITEMS;

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="min-h-screen bg-base-900">
      <header className="sticky top-0 z-30 border-b border-base-700 bg-base-850/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-6 px-4 sm:px-6 lg:px-8">
          <Link to="/dashboard" aria-label="Dashboard">
            <Logo />
          </Link>
          <div className="flex items-center gap-3">
            <CreditsBadge />
            <span className="hidden max-w-[12rem] truncate text-sm text-ink-500 md:inline">
              {user?.full_name || user?.email}
            </span>
            <button
              type="button"
              onClick={handleLogout}
              className="rounded-md border border-base-600 px-3 py-1.5 text-xs font-semibold text-ink-300 hover:border-status-danger hover:text-status-danger"
            >
              Log out
            </button>
          </div>
        </div>
        <nav
          aria-label="App"
          className="mx-auto flex max-w-7xl items-center gap-1 overflow-x-auto border-t border-base-700 px-4 py-2 sm:px-6 lg:px-8"
        >
          {navItems.map((item) => (
            <NavItem key={item.to} {...item} />
          ))}
        </nav>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <Outlet />
      </main>

      <footer className="border-t border-base-700 bg-base-850">
        <p className="mx-auto max-w-7xl px-4 py-6 text-xs text-ink-700 sm:px-6 lg:px-8">
          © {new Date().getFullYear()} PetroLead — B2B lead intelligence for the petroleum &amp;
          energy trade.
        </p>
      </footer>
    </div>
  );
}

export default function Layout() {
  return (
    <BillingProvider>
      <AppShell />
    </BillingProvider>
  );
}
