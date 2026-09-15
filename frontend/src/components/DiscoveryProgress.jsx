import { useEffect, useState } from "react";

const STEPS = [
  "Searching sources...",
  "Discovering companies...",
  "Analyzing relevance...",
  "Removing duplicates...",
  "Saving companies...",
];

export default function DiscoveryProgress() {
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setStepIndex((i) => Math.min(i + 1, STEPS.length - 1));
    }, 900);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex flex-col items-center justify-center gap-4 rounded-xl border border-base-700 bg-base-850 px-6 py-14 text-center">
      <div className="relative h-12 w-12">
        <div className="absolute inset-0 animate-spin rounded-full border-2 border-base-600 border-t-brand-500" />
      </div>
      <div>
        <p className="text-sm font-medium text-ink-100">{STEPS[stepIndex]}</p>
        <p className="mt-1 text-xs text-ink-700">This can take a few moments.</p>
      </div>
      <ul className="mt-2 flex flex-wrap items-center justify-center gap-2">
        {STEPS.map((step, i) => (
          <li
            key={step}
            className={`h-1.5 w-8 rounded-full transition-colors ${
              i <= stepIndex ? "bg-brand-500" : "bg-base-700"
            }`}
          />
        ))}
      </ul>
    </div>
  );
}
