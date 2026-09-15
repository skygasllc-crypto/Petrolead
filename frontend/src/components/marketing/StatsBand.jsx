import { STATS } from "./content";

export default function StatsBand({ title = "Accurate contacts. Built for energy trade." }) {
  return (
    <section className="bg-base-850 px-4 py-20 sm:px-6 lg:px-8">
      <h2 className="text-center text-3xl font-bold tracking-tight text-ink-100 sm:text-4xl">
        {title}
      </h2>
      <dl className="mx-auto mt-12 grid max-w-7xl grid-cols-1 gap-y-10 rounded-[2rem] border border-base-700 bg-gradient-to-br from-base-900 via-base-850 to-brand-50 px-6 py-12 sm:grid-cols-2 lg:grid-cols-4">
        {STATS.map((s) => (
          <div
            key={s.value}
            className="flex flex-col-reverse items-center justify-end px-4 text-center"
          >
            <dt className="mt-2 text-sm leading-relaxed text-ink-500">{s.label}</dt>
            <dd className="text-3xl font-extrabold tracking-tight text-ink-100 sm:text-4xl">
              {s.value}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
