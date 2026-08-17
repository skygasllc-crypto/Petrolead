export default function Logo({ className = "" }) {
  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <svg viewBox="0 0 32 32" className="h-8 w-8 shrink-0">
        <rect width="32" height="32" rx="7" fill="var(--color-base-800)" />
        <path
          d="M16 5c-4.5 6-7.5 10.2-7.5 14.2C8.5 23.9 11.9 27 16 27s7.5-3.1 7.5-7.8C23.5 15.2 20.5 11 16 5z"
          fill="var(--color-brass-500)"
        />
        <path
          d="M16 13c-1.9 2.7-3.1 4.5-3.1 6.4a3.1 3.1 0 1 0 6.2 0c0-1.9-1.2-3.7-3.1-6.4z"
          fill="var(--color-base-800)"
        />
      </svg>
      <div className="leading-tight">
        <div className="font-semibold tracking-tight text-ink-100">PetroLead</div>
        <div className="text-[10px] font-medium uppercase tracking-widest text-ink-700">
          Energy Intelligence
        </div>
      </div>
    </div>
  );
}
