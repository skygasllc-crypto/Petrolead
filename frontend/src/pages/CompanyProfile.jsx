import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import RelevanceBadge from "../components/RelevanceBadge";
import ErrorBanner from "../components/ErrorBanner";
import ValidityBadge from "../components/ValidityBadge";
import { sourceLabel } from "../lib/constants";

function Section({ title, children }) {
  return (
    <section className="rounded-xl border border-base-700 bg-base-850 p-6">
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-ink-700">{title}</h2>
      {children}
    </section>
  );
}

function TagList({ items, empty = "None recorded." }) {
  if (!items || items.length === 0) {
    return <p className="text-sm text-ink-700">{empty}</p>;
  }
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <span
          key={item}
          className="rounded-full border border-base-600 px-3 py-1 text-xs text-ink-300"
        >
          {item}
        </span>
      ))}
    </div>
  );
}

const PLATFORM_LABELS = {
  linkedin: "LinkedIn",
  facebook: "Facebook",
  twitter: "X / Twitter",
  instagram: "Instagram",
  youtube: "YouTube",
};

function ScoreBar({ label, value, max }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div>
      <div className="flex items-center justify-between text-xs">
        <span className="text-ink-500">{label}</span>
        <span className="tabular-nums text-ink-300">
          {value}/{max}
        </span>
      </div>
      <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-base-700">
        <div className="h-full rounded-full bg-brand-500" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function FutureSection({ title }) {
  return (
    <section className="rounded-xl border border-dashed border-base-600 bg-base-850/40 p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-700">{title}</h2>
        <span className="rounded-full border border-base-600 px-2.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-ink-700">
          Coming in a later phase
        </span>
      </div>
      <p className="mt-3 text-sm text-ink-700">
        This section is part of the PetroLead roadmap and is not implemented in Phase 1.
      </p>
    </section>
  );
}

export default function CompanyProfile() {
  const { id } = useParams();
  const [company, setCompany] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .getCompany(id)
      .then((data) => !cancelled && setCompany(data))
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          setError("This company could not be found.");
        } else {
          setError("Failed to load this company.");
        }
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (loading) {
    return <div className="py-16 text-center text-sm text-ink-500">Loading company...</div>;
  }

  if (error) {
    return (
      <div className="flex flex-col gap-4">
        <ErrorBanner message={error} />
        <Link to="/companies" className="text-sm text-brand-600 hover:underline">
          ← Back to companies
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link to="/companies" className="text-sm text-ink-500 hover:text-brand-600">
          ← Back to companies
        </Link>
        <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-ink-100">
              {company.company_name}
            </h1>
            <p className="mt-1 text-sm text-ink-500">
              {[company.city, company.country, company.region].filter(Boolean).join(", ") ||
                "Location unknown"}
            </p>
            {company.exported_at && (
              <span
                className="mt-2 inline-block rounded-full border border-status-relevant/30 bg-status-relevant/15 px-2.5 py-0.5 text-[10px] font-medium text-status-relevant"
                title={new Date(company.exported_at).toLocaleString()}
              >
                Exported {new Date(company.exported_at).toLocaleDateString()}
              </span>
            )}
          </div>
          <RelevanceBadge score={company.relevance_score} size="lg" />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="flex flex-col gap-6 lg:col-span-2">
          <Section title="Overview">
            <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <dt className="text-xs text-ink-700">Industry</dt>
                <dd className="text-sm text-ink-100">{company.industry || "Unclassified"}</dd>
              </div>
              <div>
                <dt className="text-xs text-ink-700">Website</dt>
                <dd className="text-sm">
                  {company.website ? (
                    <a
                      href={company.website}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-teal-400 hover:underline"
                    >
                      {company.website}
                    </a>
                  ) : (
                    <span className="text-ink-700">Not available</span>
                  )}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-ink-700">Discovered</dt>
                <dd className="text-sm text-ink-100">
                  {new Date(company.discovered_at).toLocaleString()}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-ink-700">Last updated</dt>
                <dd className="text-sm text-ink-100">
                  {new Date(company.updated_at).toLocaleString()}
                </dd>
              </div>
            </dl>
            {company.description && (
              <div className="mt-4">
                <dt className="text-xs text-ink-700">Description</dt>
                <dd className="mt-1 text-sm leading-relaxed text-ink-300">
                  {company.description}
                </dd>
              </div>
            )}
          </Section>

          <Section title="Petroleum Activities">
            <TagList items={company.activities} empty="No specific activities recorded." />
          </Section>

          <Section title="Products">
            <TagList items={company.products} empty="No specific products recorded." />
          </Section>

          <Section title="Discovery Sources">
            {company.sources.length === 0 ? (
              <p className="text-sm text-ink-700">No source records.</p>
            ) : (
              <ul className="flex flex-col divide-y divide-base-800">
                {company.sources.map((s, i) => (
                  <li key={i} className="flex flex-col gap-1 py-3 first:pt-0 last:pb-0">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-medium text-ink-100">{sourceLabel(s.source)}</span>
                      <span className="text-xs text-ink-700">
                        {new Date(s.discovered_at).toLocaleDateString()}
                      </span>
                    </div>
                    {s.source_url && (
                      <a
                        href={s.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="truncate text-xs text-teal-400 hover:underline"
                      >
                        {s.source_url}
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </div>

        <div className="flex flex-col gap-6">
          <Section title="Keywords">
            <TagList items={company.keywords} empty="No keywords recorded." />
          </Section>

          {company.contact?.contact_person_name && (
            <Section title="Contact Person">
              <p className="text-sm font-medium text-ink-100">
                {company.contact.contact_person_name}
                {company.contact.contact_person_title && (
                  <span className="font-normal text-ink-500">
                    {" "}
                    — {company.contact.contact_person_title}
                  </span>
                )}
              </p>
            </Section>
          )}

          <Section title="Contact Page">
            {company.contact?.contact_page_url ? (
              <a
                href={company.contact.contact_page_url}
                target="_blank"
                rel="noopener noreferrer"
                className="break-all text-sm text-teal-400 hover:underline"
              >
                {company.contact.contact_page_url}
              </a>
            ) : (
              <p className="text-sm text-ink-700">
                No contact page found on the company&apos;s website.
              </p>
            )}
          </Section>

          <Section title="Social Profiles">
            {company.social_profiles.length === 0 ? (
              <p className="text-sm text-ink-700">
                No social profiles found on the company&apos;s website.
              </p>
            ) : (
              <ul className="flex flex-col gap-2">
                {company.social_profiles.map((s) => (
                  <li key={s.platform}>
                    <a
                      href={s.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center justify-between gap-2 rounded-lg border border-base-700 bg-base-800/60 px-3 py-2 text-sm hover:border-brand-500"
                    >
                      <span className="font-medium text-ink-100">
                        {PLATFORM_LABELS[s.platform] || s.platform}
                      </span>
                      <span className="truncate text-xs text-teal-400">{s.url}</span>
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section title="Emails">
            {company.emails.length === 0 ? (
              <p className="text-sm text-ink-700">
                No email addresses found on the company&apos;s website.
              </p>
            ) : (
              <ul className="flex flex-col gap-2">
                {company.emails.map((e) => (
                  <li
                    key={e.email}
                    className="flex items-center justify-between gap-2 rounded-lg border border-base-700 bg-base-800/60 px-3 py-2 text-sm"
                  >
                    <a
                      href={`mailto:${e.email}`}
                      className="truncate text-ink-100 hover:text-brand-600"
                    >
                      {e.email}
                    </a>
                    <ValidityBadge isValid={e.is_valid} />
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section title="Phone Numbers">
            {company.phones.length === 0 ? (
              <p className="text-sm text-ink-700">
                No phone numbers found on the company&apos;s website.
              </p>
            ) : (
              <ul className="flex flex-col gap-2">
                {company.phones.map((p) => (
                  <li
                    key={p.phone}
                    className="flex items-center justify-between gap-2 rounded-lg border border-base-700 bg-base-800/60 px-3 py-2 text-sm"
                  >
                    <a href={`tel:${p.phone}`} className="text-ink-100 hover:text-brand-600">
                      {p.phone}
                    </a>
                    <ValidityBadge isValid={p.is_valid} />
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section title="Lead Score">
            {company.lead_score_breakdown ? (
              <div className="flex flex-col gap-4">
                <div className="text-3xl font-semibold tabular-nums text-brand-600">
                  {company.lead_score_breakdown.score}
                  <span className="text-base text-ink-700">/100</span>
                </div>
                <div className="flex flex-col gap-3">
                  <ScoreBar
                    label="Petroleum relevance"
                    value={company.lead_score_breakdown.relevance_component}
                    max={50}
                  />
                  <ScoreBar
                    label="Contact completeness"
                    value={company.lead_score_breakdown.contact_completeness_component}
                    max={20}
                  />
                  <ScoreBar
                    label="Verified email"
                    value={company.lead_score_breakdown.verified_email_component}
                    max={15}
                  />
                  <ScoreBar
                    label="Verified phone"
                    value={company.lead_score_breakdown.verified_phone_component}
                    max={15}
                  />
                </div>
              </div>
            ) : (
              <p className="text-sm text-ink-700">Not yet scored.</p>
            )}
          </Section>

          <FutureSection title="Verification" />
        </div>
      </div>
    </div>
  );
}
