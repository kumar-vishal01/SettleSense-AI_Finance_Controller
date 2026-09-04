import { useEffect, useRef, useState, type ReactNode } from "react";
import { ApiError } from "../api";
import { Icon } from "./icons";

/* ---------------- primitives ---------------- */

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 text-ink-muted text-body" role="status" aria-live="polite">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-primary/30 border-t-primary" />
      {label}
    </div>
  );
}

export function EngineStatus({ health }: { health: "checking" | "up" | "down" }) {
  const label = health === "up" ? "Engine online" : health === "down" ? "Engine unavailable" : "Checking engine";
  const tone = health === "up" ? "text-fin-600" : health === "down" ? "text-risk-600" : "text-ink-muted";
  return <span className={`inline-flex items-center gap-2 text-[13px] font-semibold ${tone}`} role="status">
    <span className="h-2 w-2 rounded-full bg-current" aria-hidden="true" />{label}
  </span>;
}

export function BatchContext({ batchId, records, lastReconciled }: {
  batchId: string; records: number | null; lastReconciled: string | null;
}) {
  return <div className="flex min-w-0 items-center gap-3 border-l border-line pl-4 text-[13px] leading-tight text-ink-2">
    <div className="min-w-0" title={batchId}>
      <p className="text-[11px] uppercase tracking-[0.08em] text-ink-subtle">Batch</p>
      <p className="truncate font-semibold text-ink">synthetic-v2</p>
    </div>
    <span className="h-7 w-px bg-line" aria-hidden="true" />
    <div className="whitespace-nowrap"><span className="font-semibold text-ink">{records ?? "—"} records</span><span className="mx-1.5 text-ink-subtle">•</span><span>Last reconciled {lastReconciled ?? "—"}</span></div>
  </div>;
}

export function AlertBanner({ children }: { children: ReactNode }) {
  return <div className="flex items-center gap-2.5 rounded-lg border border-brand-500/15 bg-brand-100/55 px-3.5 py-2.5 text-sm text-ink-2" role="note">
    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-500/12 text-brand-600"><Icon name="info" className="h-3 w-3" /></span>{children}
  </div>;
}

export function Skeleton({ className = "h-4 w-full" }: { className?: string }) {
  return <div className={`bg-gradient-to-r from-surface-alt via-surface to-surface-alt animate-shimmer ${className}`} aria-hidden="true" />;
}

export function SkeletonTable({ rows = 8, cols = 6 }: { rows?: number; cols?: number }) {
  return (
    <div className="space-y-2" role="status" aria-label="Loading table data">
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex gap-2">
          {Array.from({ length: cols }).map((_, c) => (
            <Skeleton key={c} className={`h-8 ${c === 0 ? "w-28" : "flex-1"}`} />
          ))}
        </div>
      ))}
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="card border-2 border-dashed border-border-hairline p-10 text-center animate-fade-up">
      <p className="font-medium text-ink">{title}</p>
      {hint && <p className="mt-1 text-body text-ink-muted">{hint}</p>}
    </div>
  );
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  const apiErr = error instanceof ApiError ? error : null;
  return (
    <div className="card border-2 border-primary/20 bg-primary/5 p-4 text-body text-primary animate-fade-up"
      role="alert">
      <p className="font-semibold flex items-center gap-2"><Icon name="alert" /> Something went wrong</p>
      <p className="mt-1">
        {apiErr ? `[${apiErr.code}] ${apiErr.message}`
          : "Unexpected error — is the backend running on port 8000?"}
      </p>
      {retry && (
        <button onClick={retry}
          className="mt-3 rounded border border-risk-600/40 bg-white px-3 py-1 font-medium hover:bg-white/70">
          Retry
        </button>
      )}
    </div>
  );
}

export function Section({ title, children, note, actions }: {
  title: string; children: ReactNode; note?: string; actions?: ReactNode;
}) {
  return (
    <section className="card">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2 border-b border-line pb-3">
        <div className="flex items-baseline gap-2">
          <h2 className="text-[17px] font-semibold text-ink">{title}</h2>
          {note && <p className="text-xs text-ink-2">{note}</p>}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}

/* ---------------- count-up metric card ---------------- */

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined"
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function useCountUp(target: number, active: boolean, durationMs = 600): number {
  const [value, setValue] = useState(active ? 0 : target);
  const raf = useRef<number>(0);
  useEffect(() => {
    if (!active || prefersReducedMotion()) { setValue(target); return; }
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs);
      const eased = 1 - Math.pow(1 - t, 3); // ease-out
      setValue(target * eased);
      if (t < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [target, active, durationMs]);
  return value;
}

export function MetricCard({ label, value, sub, tone = "neutral", icon, tip,
  countUp = false, suffix = "" }: {
  label: string; value: string; sub?: string;
  tone?: "neutral" | "good" | "warn" | "bad" | "brand"; icon?: string;
  tip?: string; countUp?: boolean; suffix?: string;
}) {
  const numeric = countUp ? Number(value.replace(/[^\d.-]/g, "")) : NaN;
  const animated = useCountUp(
    Number.isFinite(numeric) ? numeric : 0, countUp);
  const tones: Record<string, string> = {
    neutral: "border-border-hairline bg-surface-alt/50",
    good: "border-primary/25 bg-primary/8",
    warn: "border-primary/25 bg-primary/8",
    bad: "border-primary/25 bg-primary/8",
    brand: "border-primary/25 bg-primary/8",
  };
  const iconTones: Record<string, string> = {
    neutral: "text-ink-muted bg-surface",
    good: "text-primary bg-primary/12",
    warn: "text-primary bg-primary/12",
    bad: "text-primary bg-primary/12",
    brand: "text-primary bg-primary/12",
  };
  const display = countUp && Number.isFinite(numeric)
    ? `${value.startsWith("₹") ? "₹" : ""}${Math.round(animated).toLocaleString("en-IN")}${suffix}`
    : value;
  return (
    <div className={`card border p-4 animate-fade-up ${tones[tone]}`}
      title={tip} aria-label={tip ? `${label}: ${tip}` : undefined}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-label-caps text-ink-muted">{label}</p>
        {icon && (
          <span className={`rounded-sm p-1.5 ${iconTones[tone]}`} aria-hidden="true">
            <Icon name={icon} className="h-3.5 w-3.5" />
          </span>
        )}
      </div>
      <p className="mt-1.5 text-title-xl font-semibold leading-tight tabular-nums text-ink">
        {display}
      </p>
      {sub && <p className="mt-1 text-caption text-ink-muted">{sub}</p>}
    </div>
  );
}

/* ---------------- badges ---------------- */

export const STATUS_META: Record<string, { label: string; icon: string; cls: string }> = {
  FULLY_RECONCILED: { label: "Matched", icon: "check", cls: "bg-fin-100 text-fin-600 border-fin-600/25" },
  MISSING_IN_SETTLEMENT: { label: "Settlement missing", icon: "alert", cls: "bg-risk-100 text-risk-600 border-risk-600/25" },
  MISSING_BANK_CREDIT: { label: "Bank credit missing", icon: "bank", cls: "bg-risk-100 text-risk-600 border-risk-600/25" },
  AMOUNT_MISMATCH: { label: "Amount mismatch", icon: "diff", cls: "bg-risk-100 text-risk-600 border-risk-600/25" },
  DUPLICATE: { label: "Duplicate", icon: "layers", cls: "bg-warn-100 text-warn-600 border-warn-600/25" },
  TIMING_DELAY: { label: "Timing delay", icon: "clock", cls: "bg-warn-100 text-warn-600 border-warn-600/25" },
  NEEDS_HUMAN_REVIEW: { label: "Needs review", icon: "eye", cls: "bg-warn-100 text-warn-600 border-warn-600/25" },
};

export function StatusBadge({ status }: { status: string }) {
  const meta = STATUS_META[status] ?? { label: status, icon: "check",
    cls: "bg-muted text-ink-2 border-line" };
  return (
    <span className={`inline-flex items-center gap-1 rounded-sm border px-2 py-0.5 text-caption font-semibold ${meta.cls}`}>
      <Icon name={meta.icon} className="h-3 w-3" />
      {meta.label}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: string }) {
  const cls: Record<string, string> = {
    high: "bg-risk-100 text-risk-600 border-risk-600/25",
    medium: "bg-warn-100 text-warn-600 border-warn-600/25",
    low: "bg-surface-alt text-ink-muted border-border-hairline",
    none: "bg-surface-alt text-ink-muted border-border-hairline",
  };
  return (
    <span className={`inline-block rounded-sm border px-1.5 py-0.5 text-label-caps ${cls[severity] ?? cls.none}`}>
      {severity}
    </span>
  );
}

export function ConfidenceBadge({ value }: { value: number }) {
  const tone = value >= 0.95 ? "text-primary" : value >= 0.8 ? "text-primary" : "text-primary/75";
  return (
    <span className={`inline-flex items-center gap-1 text-caption font-medium tabular-nums ${tone}`}
      title="Engine confidence from the evidence chain">
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden="true" />
      {value.toFixed(2)}
    </span>
  );
}

export function EvidenceChip({ id }: { id: string }) {
  return (
    <span className="inline-block rounded-sm border border-border-hairline bg-surface-alt px-2 py-0.5 font-mono text-caption text-ink-muted"
      title="Evidence record ID">
      {id}
    </span>
  );
}

/* ---------------- drawer, toast, stepper, pager ---------------- */

export function Drawer({ open, title, onClose, children }: {
  open: boolean; title: string; onClose: () => void; children: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 flex justify-end" role="dialog" aria-modal="true" aria-label={title}>
      <div className="absolute inset-0 bg-navy-950/30" onClick={onClose} aria-hidden="true" />
      <div className="drawer-panel relative h-full w-[min(100vw,520px)] max-w-none overflow-y-auto border-l border-border-hairline bg-surface p-5 shadow-card sm:p-7">
        <div className="sticky top-0 z-10 -mx-5 -mt-5 mb-5 flex items-center justify-between border-b border-border-hairline bg-surface/95 px-5 py-4 backdrop-blur sm:-mx-7 sm:-mt-7 sm:px-7">
          <h3 className="text-lg font-semibold text-ink">{title}</h3>
          <button onClick={onClose} aria-label="Close detail panel"
            className="rounded-sm p-1.5 text-ink-muted hover:bg-surface-alt transition">
            <Icon name="x" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export type ToastMsg = { id: number; text: string; tone: "good" | "bad" | "info" };

export function Toasts({ items, onDismiss }: { items: ToastMsg[]; onDismiss: (id: number) => void }) {
  return (
    <div className="fixed bottom-4 right-4 z-50 space-y-2" role="region" aria-label="Notifications">
      {items.map(t => (
        <div key={t.id}
          className={`animate-fade-up flex items-center gap-2 rounded-sm border px-3 py-2 text-body shadow-card ${
            t.tone === "good" ? "border-primary/40 bg-primary/8 text-primary"
            : t.tone === "bad" ? "border-primary/40 bg-primary/8 text-primary"
            : "border-border-hairline bg-surface-alt text-ink-muted"}`}
          role={t.tone === "bad" ? "alert" : "status"}>
          <Icon name={t.tone === "good" ? "check" : t.tone === "bad" ? "alert" : "pulse"} />
          {t.text}
          <button onClick={() => onDismiss(t.id)} aria-label="Dismiss notification"
            className="ml-2 opacity-60 hover:opacity-100"><Icon name="x" className="h-3.5 w-3.5" /></button>
        </div>
      ))}
    </div>
  );
}

export function ProgressStepper({ steps, current }: { steps: string[]; current: number }) {
  return (
    <ol className="flex flex-wrap items-center gap-1 text-caption" aria-label="Progress">
      {steps.map((step, i) => {
        const state = i < current ? "done" : i === current ? "active" : "todo";
        return (
          <li key={step} className="flex items-center gap-1"
            aria-current={state === "active" ? "step" : undefined}>
            <span className={`flex h-5 w-5 items-center justify-center rounded-full border text-caption font-semibold
              ${state === "done" ? "border-primary bg-primary text-surface"
                : state === "active" ? "border-primary bg-primary/12 text-primary"
                : "border-border-hairline bg-surface text-ink-muted"}`}>
              {state === "done" ? "✓" : i + 1}
            </span>
            <span className={state === "todo" ? "text-ink-muted" : "font-medium text-ink"}>{step}</span>
            {i < steps.length - 1 && <span className="mx-1 h-px w-4 bg-border-hairline" aria-hidden="true" />}
          </li>
        );
      })}
    </ol>
  );
}

export function Pager({ page, totalPages, onPage }: {
  page: number; totalPages: number; onPage: (p: number) => void;
}) {
  if (totalPages <= 1) return null;
  return (
    <div className="mt-3 flex items-center gap-2 text-body">
      <button disabled={page <= 1} onClick={() => onPage(page - 1)}
        className="rounded-sm border border-border-hairline px-2.5 py-1 disabled:opacity-40 hover:bg-surface-alt transition" aria-label="Previous page">
        ← Prev
      </button>
      <span aria-live="polite">Page {page} of {totalPages}</span>
      <button disabled={page >= totalPages} onClick={() => onPage(page + 1)}
        className="rounded-sm border border-border-hairline px-2.5 py-1 disabled:opacity-40 hover:bg-surface-alt transition" aria-label="Next page">
        Next →
      </button>
    </div>
  );
}

export function ValidationList({ errors }: {
  errors: { file: string; row_number: number; field: string; message: string }[];
}) {
  if (!errors.length) return null;
  return (
    <div className="mt-3 card border-2 border-primary/20 bg-primary/5 p-3 text-body animate-fade-up">
      <p className="font-semibold text-primary">
        {errors.length} row(s) skipped — shown, never hidden
      </p>
      <ul className="mt-2 space-y-1">
        {errors.map((e, i) => (
          <li key={i} className="font-mono text-caption text-ink-muted">
            {e.file} · row {e.row_number} · {e.field}: {e.message}
          </li>
        ))}
      </ul>
    </div>
  );
}
