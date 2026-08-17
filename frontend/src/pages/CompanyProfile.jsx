import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import RelevanceBadge from "../components/RelevanceBadge";
import ErrorBanner from "../components/ErrorBanner";

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
        <Link to="/companies" className="text-sm text-brass-400 hover:underline">
          ← Back to companies
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link to="/companies" className="text-sm text-ink-500 hover:text-brass-400">
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
                      <span className="font-medium capitalize text-ink-100">
                        {s.source.replace(/^search:/, "").replace(/_/g, " ")}
                      </span>
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

          <FutureSection title="Contacts" />
          <FutureSection title="Emails" />
          <FutureSection title="Phone Numbers" />
          <FutureSection title="Social Profiles" />
          <FutureSection title="Verification" />
          <FutureSection title="Lead Score" />
        </div>
      </div>
    </div>
  );
}
