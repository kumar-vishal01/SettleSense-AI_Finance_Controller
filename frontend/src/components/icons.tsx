// Minimal inline icon set (no icon dependency). Every icon is decorative
// (aria-hidden) — labels next to them carry the meaning.
const PATHS: Record<string, string> = {
  check: "M20 6 9 17l-5-5",
  alert: "M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z",
  clock: "M12 6v6l4 2m6-2a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z",
  eye: "M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Zm10 3a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z",
  diff: "M12 3v18M5 8h7M5 8 3 8m17 8h-7m7 0-2 0M8 5 8 11M16 13l0 6",
  bank: "M3 21h18M4 10h16M12 3 3 8h18l-9-5Zm0 8v7m-4 0v-7m8 7v-7",
  chart: "M3 3v18h18M7 15v3m4-8v8m4-12v12m4-6v6",
  spark: "m12 3 1.9 5.8a2 2 0 0 0 1.3 1.3L21 12l-5.8 1.9a2 2 0 0 0-1.3 1.3L12 21l-1.9-5.8a2 2 0 0 0-1.3-1.3L3 12l5.8-1.9a2 2 0 0 0 1.3-1.3L12 3Z",
  copy: "M9 9h10v10H9zM5 15V5h10",
  upload: "M12 16V4m0 0L8 8m4-4 4 4M4 20h16",
  search: "m20 20-4.5-4.5M17 11a6 6 0 1 1-12 0 6 6 0 0 1 12 0Z",
  x: "M6 6l12 12M18 6 6 18",
  chevron: "m9 6 6 6-6 6",
  layers: "m12 3 9 5-9 5-9-5 9-5Zm9 9-9 5-9-5m18 4-9 5-9-5",
  pulse: "M3 12h4l3-8 4 16 3-8h4",
  doc: "M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Zm0 0v5h5",
  arrowright: "M4 12h16m0 0-6-6m6 6-6 6",
};

export function Icon({ name, className = "h-4 w-4" }: { name: string; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d={PATHS[name] ?? PATHS.check} />
    </svg>
  );
}
