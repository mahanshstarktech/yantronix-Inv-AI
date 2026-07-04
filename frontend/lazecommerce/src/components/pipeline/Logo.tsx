export function Logo({ className = "" }: { className?: string }) {
  return (
    <span
      className={
        "inline-flex items-baseline font-bold tracking-tight select-none " +
        className
      }
    >
      <span className="text-white">Laz</span>
      <span className="text-accent-primary drop-shadow-[0_0_12px_color-mix(in_oklab,var(--accent-primary)_55%,transparent)]">
        E
      </span>
      <span className="text-white">Commerce</span>
    </span>
  );
}
