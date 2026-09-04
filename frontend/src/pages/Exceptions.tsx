import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Paginated, ResultItem } from "../types";
import {
  ConfidenceBadge, EmptyState, ErrorState, Section, SeverityBadge, SkeletonTable,
  StatusBadge, EvidenceChip, Spinner,
} from "../components/ui";
import { Icon } from "../components/icons";
import { AmountBreakdown } from "../components/breakdown";
import { rupees } from "../format";

const STATUSES = ["", "MISSING_IN_SETTLEMENT", "MISSING_BANK_CREDIT", "AMOUNT_MISMATCH",
  "DUPLICATE", "TIMING_DELAY", "NEEDS_HUMAN_REVIEW"];

export default function Exceptions({ batchId }: { batchId: string }) {
  const [data, setData] = useState<Paginated<ResultItem> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [status, setStatus] = useState("");
  const [severity, setSeverity] = useState("");
  const [onlyHigh, setOnlyHigh] = useState(false);
  const [selected, setSelected] = useState<ResultItem | null>(null);
  const [detail, setDetail] = useState<import("../types").TraceData | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  function load() {
    setLoading(true); setError(null);
    api.exceptions(batchId, 1, status || undefined)
      .then(setData).catch(e => setError(e)).finally(() => setLoading(false));
  }
  useEffect(load, [batchId, status]);

  const items = useMemo(() => data?.items ?? [], [data]);
  const filtered = useMemo(() => items
    .filter(r => (!severity || r.severity === severity) && (!onlyHigh || r.severity === "high"))
    .sort((a, b) => Math.abs(b.variance_paise ?? b.expected_amount_paise ?? 0)
                    - Math.abs(a.variance_paise ?? a.expected_amount_paise ?? 0)),
    [items, severity, onlyHigh]);
  const exposure = filtered.reduce(
    (s, r) => s + Math.abs(r.variance_paise ?? r.expected_amount_paise ?? 0), 0);
  const highCount = filtered.filter(r => r.severity === "high").length;

  function openDetail(r: ResultItem) {
    setSelected(r); setDetail(null); setDetailLoading(true);
    api.trace(r.payment_id, batchId)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setDetailLoading(false));
  }

  return (
    <>
      <Section title="Exceptions requiring attention"
        note={data ? `${data.total} total` : undefined}>
        <div className="mb-4 grid gap-3 sm:grid-cols-3">
          <div className="rounded-lg border border-risk-600/30 bg-risk-100/60 p-3">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-2">Financial exposure</p>
            <p className="text-xl font-semibold tabular-nums text-risk-600">{rupees(exposure)}</p>
          </div>
          <div className="rounded-lg border border-line bg-white p-3">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-2">Open exceptions</p>
            <p className="text-xl font-semibold tabular-nums">{filtered.length}</p>
          </div>
          <div className="rounded-lg border border-warn-600/30 bg-warn-100/60 p-3">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-2">High priority</p>
            <p className="text-xl font-semibold tabular-nums text-warn-600">{highCount}</p>
          </div>
        </div>

        <div className="mb-3 flex flex-wrap items-center gap-2 text-sm">
          <select value={status} onChange={e => setStatus(e.target.value)}
            className="rounded-lg border border-line bg-white px-2 py-1.5" aria-label="Filter by status">
            {STATUSES.map(s => <option key={s} value={s}>{s || "All statuses"}</option>)}
          </select>
          <select value={severity} onChange={e => setSeverity(e.target.value)}
            className="rounded-lg border border-line bg-white px-2 py-1.5" aria-label="Filter by severity">
            {["", "high", "medium", "low"].map(s => <option key={s} value={s}>{s || "All severities"}</option>)}
          </select>
          <label className="flex items-center gap-1.5 text-ink-2">
            <input type="checkbox" checked={onlyHigh} onChange={e => setOnlyHigh(e.target.checked)} />
            high priority only
          </label>
          <a href={`/api/v1/batches/${batchId}/export?format=csv&scope=exceptions`}
            className="ml-auto inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 font-medium hover:bg-muted">
            <Icon name="doc" className="h-3.5 w-3.5" /> Export queue
          </a>
        </div>

        {loading ? <SkeletonTable rows={6} cols={6} /> : null}
        {error ? <ErrorState error={error} retry={load} /> : null}
        {data && !loading ? (
          filtered.length === 0 ? (
            <EmptyState title="No exceptions match these filters" hint="All records reconciled, or filters too narrow." />
          ) : (
            <ul className="space-y-2.5">
              {filtered.map(r => (
                <li key={r.payment_id}
                  className={`rounded-xl border bg-white p-3.5 transition duration-150 hover:border-brand-500/50 anim-fade-up ${
                    selected?.payment_id === r.payment_id
                      ? "border-brand-600 ring-2 ring-brand-600/10"
                      : "border-line"
                  }`}>
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-sm font-semibold">{r.payment_id}</span>
                      <StatusBadge status={r.status} />
                      <SeverityBadge severity={r.severity} />
                      <ConfidenceBadge value={r.confidence} />
                    </div>
                    <div className="text-right">
                      <p className="text-lg font-semibold tabular-nums text-risk-600">
                        {rupees(Math.abs(r.variance_paise ?? r.expected_amount_paise ?? 0))}
                      </p>
                      <p className="text-[11px] text-ink-2">
                        {r.variance_paise !== null ? "variance" : "expected, unconfirmed"}
                      </p>
                    </div>
                  </div>
                  <p className="mt-2 text-sm text-ink-2">{r.reason}</p>
                  <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap gap-1">
                      {r.evidence.slice(0, 5).map(id => <EvidenceChip key={id} id={id} />)}
                      {r.evidence.length > 5 && <span className="text-[11px] text-ink-2">+{r.evidence.length - 5}</span>}
                    </div>
                    <button onClick={() => selected?.payment_id === r.payment_id ? setSelected(null) : openDetail(r)}
                      aria-expanded={selected?.payment_id === r.payment_id}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-brand-500">
                      {selected?.payment_id === r.payment_id ? "Close review" : "Review"}
                      <Icon name={selected?.payment_id === r.payment_id ? "x" : "arrowright"} className="h-3.5 w-3.5" />
                    </button>
                  </div>
                  {selected?.payment_id === r.payment_id && (
                    <div className="mt-4 border-t border-line pt-4 animate-fade-up" aria-label="Exception review details">
                      <div className="mb-3 flex items-center justify-between gap-2">
                        <div>
                          <p className="text-base font-semibold text-ink">Review details</p>
                          <p className="text-xs text-ink-2">Evidence and calculation for {r.payment_id}</p>
                        </div>
                        <span className="text-xs font-medium text-brand-600">Selected exception</span>
                      </div>
                      <div className="space-y-4">
                        <div className="rounded-lg border border-line bg-muted p-3 text-sm">
                          <p className="font-semibold text-ink">Why it was flagged</p>
                          <p className="mt-1 text-ink-2">{r.reason}</p>
                        </div>
                        <div className="rounded-lg border border-brand-500/30 bg-brand-100/50 p-3 text-sm">
                          <p className="font-semibold text-ink">Recommended action</p>
                          <p className="mt-1 text-ink-2">{r.recommended_action || "—"}</p>
                        </div>
                        {detailLoading ? <Spinner label="Loading full chain…" /> : null}
                        {detail?.decision?.expected_breakdown_paise ? (
                          <div>
                            <p className="mb-2 text-sm font-semibold">Gross-to-net calculation</p>
                            <AmountBreakdown breakdown={detail.decision.expected_breakdown_paise}
                              actualPaise={detail.decision.actual_amount_paise}
                              variancePaise={detail.decision.variance_paise} />
                          </div>
                        ) : null}
                        <div>
                          <p className="mb-2 text-sm font-semibold">Evidence records</p>
                          <div className="flex flex-wrap gap-1">
                            {r.evidence.map(id => <EvidenceChip key={id} id={id} />)}
                          </div>
                        </div>
                        <p className="text-[11px] text-ink-2">
                          Statuses are decided by the deterministic engine and cannot be changed here —
                          resolution happens in the source systems.
                        </p>
                      </div>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )
        ) : null}
      </Section>

    </>
  );
}
