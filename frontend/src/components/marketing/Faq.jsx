import { useState } from "react";
import Icon from "./Icon";

function FaqItem({ q, a, open, onToggle, id }) {
  return (
    <div className="border-b border-base-700">
      <h3>
        <button
          type="button"
          aria-expanded={open}
          aria-controls={id}
          onClick={onToggle}
          className="flex w-full items-center justify-between gap-6 py-5 text-left text-base font-semibold text-ink-100 hover:text-brand-500"
        >
          {q}
          <Icon
            name="chevronDown"
            className={`h-5 w-5 shrink-0 text-ink-500 transition-transform ${open ? "rotate-180" : ""}`}
          />
        </button>
      </h3>
      <div id={id} hidden={!open} className="pb-5 pr-10 text-sm leading-relaxed text-ink-500">
        {a}
      </div>
    </div>
  );
}

export default function Faq({ title = "Frequently asked questions", items, idPrefix = "faq" }) {
  const [openIndex, setOpenIndex] = useState(0);
  return (
    <section id="faq" className="scroll-mt-24 bg-base-850 px-4 py-20 sm:px-6 lg:px-8">
      <h2 className="mx-auto max-w-4xl text-center text-3xl font-bold tracking-tight text-ink-100 sm:text-4xl">
        {title}
      </h2>
      <div className="mx-auto max-w-3xl">
        <div className="mt-10 border-t border-base-700">
          {items.map((item, i) => (
            <FaqItem
              key={item.q}
              id={`${idPrefix}-${i}`}
              {...item}
              open={openIndex === i}
              onToggle={() => setOpenIndex(openIndex === i ? -1 : i)}
            />
          ))}
        </div>
      </div>
    </section>
  );
}
