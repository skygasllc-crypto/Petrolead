import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import Logo from "../Logo";
import Icon from "./Icon";
import { PRODUCTS } from "./content";
import { useAuth } from "../../context/AuthContext";

export const primaryButton =
  "inline-flex items-center justify-center gap-2 rounded-md bg-brand-500 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500";

export const secondaryButton =
  "inline-flex items-center justify-center gap-2 rounded-md border border-base-600 bg-base-850 px-5 py-2.5 text-sm font-semibold text-brand-600 transition-colors hover:border-brand-500";

function useDismiss(open, setOpen) {
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    function onPointer(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    function onKey(e) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, setOpen]);
  return ref;
}

const navLink = "rounded-md px-3 py-2 text-sm font-medium text-ink-300 hover:text-brand-500";

export default function SiteHeader() {
  const { user } = useAuth();
  const [productOpen, setProductOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const productRef = useDismiss(productOpen, setProductOpen);

  return (
    <header className="sticky top-0 z-40 px-3 pt-3 sm:px-6 sm:pt-4">
      <div className="mx-auto max-w-7xl rounded-2xl border border-base-700 bg-base-850/95 shadow-sm backdrop-blur">
        <div className="flex h-16 items-center justify-between gap-6 px-4 sm:px-6">
          <Link to="/" aria-label="PetroLead home">
            <Logo />
          </Link>

          <nav className="hidden items-center gap-2 md:flex" aria-label="Main">
            <div className="relative" ref={productRef}>
              <button
                type="button"
                aria-expanded={productOpen}
                onClick={() => setProductOpen((o) => !o)}
                className={`${navLink} inline-flex items-center gap-1`}
              >
                Product
                <Icon
                  name="chevronDown"
                  className={`h-4 w-4 transition-transform ${productOpen ? "rotate-180" : ""}`}
                />
              </button>
              {productOpen && (
                <div className="absolute left-1/2 top-full mt-3 w-[36rem] -translate-x-1/2 rounded-xl border border-base-700 bg-base-850 p-3 shadow-xl">
                  <div className="grid grid-cols-2 gap-1">
                    {PRODUCTS.map((p) => (
                      <Link
                        key={p.title}
                        to={p.to}
                        onClick={() => setProductOpen(false)}
                        className="flex gap-3 rounded-lg p-3 hover:bg-brand-50"
                      >
                        <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-500">
                          <Icon name={p.icon} />
                        </span>
                        <span>
                          <span className="block text-sm font-semibold text-ink-100">
                            {p.title}
                          </span>
                          <span className="mt-0.5 block text-xs leading-relaxed text-ink-500">
                            {p.description}
                          </span>
                        </span>
                      </Link>
                    ))}
                  </div>
                </div>
              )}
            </div>
            <Link to="/#features" className={navLink}>
              Features
            </Link>
            <Link to="/pricing" className={navLink}>
              Pricing
            </Link>
          </nav>

          <div className="hidden items-center gap-3 md:flex">
            {user ? (
              <Link to="/dashboard" className={primaryButton}>
                Go to dashboard
              </Link>
            ) : (
              <>
                <Link to="/login" className={`${secondaryButton} px-4 py-2`}>
                  Log in
                </Link>
                <Link to="/register" className={`${primaryButton} px-4 py-2`}>
                  Sign up
                </Link>
              </>
            )}
          </div>

          <button
            type="button"
            className="rounded-md p-2 text-ink-300 md:hidden"
            aria-expanded={mobileOpen}
            aria-label={mobileOpen ? "Close menu" : "Open menu"}
            onClick={() => setMobileOpen((o) => !o)}
          >
            <Icon name={mobileOpen ? "close" : "menu"} className="h-6 w-6" />
          </button>
        </div>

        {mobileOpen && (
          <div className="border-t border-base-700 px-4 pb-4 md:hidden">
            <div className="flex flex-col py-2">
              {PRODUCTS.map((p) => (
                <Link
                  key={p.title}
                  to={p.to}
                  onClick={() => setMobileOpen(false)}
                  className="flex items-center gap-3 rounded-md px-2 py-2.5 text-sm font-medium text-ink-300"
                >
                  <Icon name={p.icon} className="h-5 w-5 text-brand-500" />
                  {p.title}
                </Link>
              ))}
              <Link
                to="/pricing"
                onClick={() => setMobileOpen(false)}
                className="rounded-md px-2 py-2.5 text-sm font-medium text-ink-300"
              >
                Pricing
              </Link>
            </div>
            {user ? (
              <Link to="/dashboard" className={`${primaryButton} w-full`}>
                Go to dashboard
              </Link>
            ) : (
              <div className="grid grid-cols-2 gap-3">
                <Link to="/login" className={secondaryButton}>
                  Log in
                </Link>
                <Link to="/register" className={primaryButton}>
                  Sign up
                </Link>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
