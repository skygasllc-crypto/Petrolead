// Building blocks shared by the public product pages (LinkedIn Email Finder,
// Company Search, Email Extractor, Email Verifier).
import { Link } from "react-router-dom";
import Icon from "./Icon";
import SiteHeader, { primaryButton, secondaryButton } from "./SiteHeader";
import SiteFooter from "./SiteFooter";
import useAppPath from "./useAppPath";
import { useAuth } from "../../context/AuthContext";
import { EMAIL_CHECK_STATUS } from "../../lib/emailChecks";

const PILL_STYLES = {
  verified: ["Verified", "border-status-high/30 bg-status-high/10 text-status-high"],
  unverified: ["Unverified", "border-status-low/30 bg-status-low/10 text-status-low"],
  pending: ["Check pending", "border-status-possible/30 bg-status-possible/10 text-status-possible"],
  ...Object.fromEntries(
    Object.entries(EMAIL_CHECK_STATUS).map(([status, { label, classes }]) => [status, [label, classes]]),
  ),
};

export function MarketingPage({ children }) {
  return (
    <div className="relative min-h-screen bg-base-850">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-[52rem] bg-gradient-to-b from-brand-50 to-transparent"
      />
      <SiteHeader />
      <main className="relative">{children}</main>
      <SiteFooter />
    </div>
  );
}

export function ProductHero({ title, description, ctaLabel, ctaIcon, appPath, note, disclaimer, mock }) {
  const to = useAppPath(appPath);
  return (
    <section className="mx-auto grid max-w-7xl grid-cols-1 items-center gap-12 px-4 pb-24 pt-16 sm:px-6 sm:pt-20 lg:grid-cols-2 lg:px-8">
      <div>
        <h1 className="text-5xl font-bold tracking-tight text-ink-100 sm:text-6xl">{title}</h1>
        <p className="mt-6 max-w-xl text-xl leading-relaxed text-ink-500">{description}</p>
        <div className="mt-8">
          <Link to={to} className={`${primaryButton} px-7 py-3.5 text-base`}>
            {ctaIcon && <Icon name={ctaIcon} className="h-5 w-5" />}
            {ctaLabel}
          </Link>
        </div>
        {note && (
          <p className="mt-5 flex items-center gap-2 text-sm font-medium text-ink-500">
            <Icon name="check" className="h-4 w-4 text-status-high" />
            {note}
          </p>
        )}
        {disclaimer && (
          <p className="mt-8 max-w-md text-xs leading-relaxed text-ink-700">{disclaimer}</p>
        )}
      </div>
      {mock}
    </section>
  );
}

export function BrowserFrame({ url, children, className = "" }) {
  return (
    <div
      aria-hidden="true"
      className={`overflow-hidden rounded-2xl border border-base-700 bg-base-850 shadow-xl ${className}`}
    >
      <div className="flex items-center gap-3 border-b border-base-700 bg-base-800 px-4 py-2.5">
        <div className="flex gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-base-600" />
          <span className="h-2.5 w-2.5 rounded-full bg-base-600" />
          <span className="h-2.5 w-2.5 rounded-full bg-base-600" />
        </div>
        <div className="flex min-w-0 flex-1 items-center gap-2 rounded-md border border-base-700 bg-base-850 px-3 py-1 text-[11px] text-ink-500">
          <Icon name="lock" className="h-3 w-3 shrink-0" />
          <span className="truncate">{url}</span>
        </div>
      </div>
      {children}
    </div>
  );
}

export function Initials({ name, className = "h-7 w-7 text-[10px]" }) {
  const initials = name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2);
  return (
    <span
      className={`flex shrink-0 items-center justify-center rounded-full bg-brand-50 font-semibold text-brand-600 ${className}`}
    >
      {initials}
    </span>
  );
}

export function StatusPill({ status }) {
  const [label, classes] = PILL_STYLES[status];
  return (
    <span
      className={`inline-flex whitespace-nowrap rounded-full border px-2 py-0.5 text-[10px] font-semibold ${classes}`}
    >
      {label}
    </span>
  );
}

export function CheckList({ items }) {
  return (
    <ul className="mt-6 flex flex-col gap-3">
      {items.map((item) => (
        <li key={item} className="flex gap-3 text-base leading-relaxed text-ink-300">
          <Icon name="check" className="mt-1 h-4 w-4 shrink-0 text-status-high" />
          {item}
        </li>
      ))}
    </ul>
  );
}

export function FeatureCta({ appPath, label, variant = "primary", secondary }) {
  const to = useAppPath(appPath);
  return (
    <div className="mt-8 flex flex-wrap items-center gap-6">
      <Link
        to={to}
        className={variant === "soft" ? `${secondaryButton} bg-brand-50` : primaryButton}
      >
        {label}
      </Link>
      {secondary && (
        <a
          href={secondary.href}
          className="inline-flex items-center gap-1 text-sm font-semibold text-brand-600 hover:text-brand-700"
        >
          {secondary.label} <Icon name="arrowRight" className="h-4 w-4" />
        </a>
      )}
    </div>
  );
}

export function FeaturePanel({ children }) {
  return (
    <section className="px-4 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl rounded-[2rem] border border-base-700 bg-base-900 px-6 py-16 sm:px-12">
        {children}
      </div>
    </section>
  );
}

export function FeatureBlock({ id, title, subtitle, children, mock, reverse = false }) {
  return (
    <div id={id} className="scroll-mt-28">
      <h2 className="text-center text-3xl font-bold tracking-tight text-ink-100 sm:text-4xl">
        {title}
      </h2>
      {subtitle && (
        <h3 className="mt-4 text-center text-lg font-semibold text-ink-300">{subtitle}</h3>
      )}
      <div className="mt-12 grid grid-cols-1 items-center gap-12 lg:grid-cols-2">
        <div className={reverse ? "lg:order-2" : ""}>{children}</div>
        <div className={reverse ? "lg:order-1" : ""}>{mock}</div>
      </div>
    </div>
  );
}

export function FeatureText({ children }) {
  return <p className="mt-4 text-base leading-8 text-ink-300 first:mt-0">{children}</p>;
}

export function Divider() {
  return (
    <div className="mx-auto my-20 h-px max-w-md bg-gradient-to-r from-transparent via-brand-100 to-transparent" />
  );
}

export function StepsSection({ title, subtitle, steps }) {
  const { user } = useAuth();
  return (
    <section id="how-it-works" className="scroll-mt-28 px-4 pt-24 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl rounded-[2rem] border border-base-700 bg-base-900 px-6 py-16 sm:px-12">
        <h2 className="text-center text-3xl font-bold tracking-tight text-ink-100 sm:text-4xl">
          {title}
        </h2>
        <p className="mt-4 text-center text-ink-500">{subtitle}</p>
        <ol className="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((step, i) => (
            <li key={step.title} className="rounded-2xl border border-base-700 bg-base-850 p-7">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-500 text-sm font-semibold text-white">
                {i + 1}
              </span>
              <h3 className="mt-6 text-lg font-semibold leading-snug text-ink-100">
                {step.title}
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-ink-500">{step.body}</p>
              {step.link && !user && (
                <Link
                  to={step.link.to}
                  className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-brand-600 hover:text-brand-700"
                >
                  {step.link.label} <Icon name="arrowRight" className="h-4 w-4" />
                </Link>
              )}
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
