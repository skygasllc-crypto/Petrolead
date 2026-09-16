import { MarketingPage } from "./ProductBlocks";

/* Shared shell for the Terms and Privacy pages: one column of prose, sized
   for reading rather than for the marketing grid. */

export function LegalPage({ title, updated, intro, children }) {
  return (
    <MarketingPage>
      <article className="mx-auto max-w-3xl px-4 pb-24 pt-16 sm:px-6 lg:px-8">
        <h1 className="text-4xl font-bold tracking-tight text-ink-100 sm:text-5xl">{title}</h1>
        <p className="mt-4 text-sm text-ink-700">Last updated: {updated}</p>
        {intro && <p className="mt-6 text-lg leading-relaxed text-ink-500">{intro}</p>}
        <div className="mt-10 flex flex-col gap-10">{children}</div>
      </article>
    </MarketingPage>
  );
}

export function Section({ title, children }) {
  return (
    <section>
      <h2 className="text-xl font-semibold tracking-tight text-ink-100">{title}</h2>
      <div className="mt-3 flex flex-col gap-3 text-sm leading-relaxed text-ink-500">
        {children}
      </div>
    </section>
  );
}

export function List({ items }) {
  return (
    <ul className="flex list-disc flex-col gap-2 pl-5 marker:text-ink-700">
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  );
}

/** A value the operator must replace before publishing — visibly unfinished
    on purpose, so a placeholder can't quietly ship as a real term. */
export function Fill({ children }) {
  return (
    <mark className="rounded bg-status-possible/20 px-1 font-semibold text-status-possible">
      [{children}]
    </mark>
  );
}
