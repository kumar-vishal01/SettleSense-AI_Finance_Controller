import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Paginated, ResultItem } from "../types";
import {
  ConfidenceBadge, EmptyState, ErrorState, Pager, Section, SkeletonTable, StatusBadge,
} from "../components/ui";
import { Icon } from "../components/icons";
import { rupees } from "../format";

const STATUSES = ["", "FULLY_RECONCILED", "MISSING_IN_SETTLEMENT", "MISSING_BANK_CREDIT",
  "AMOUNT_MISMATCH", "DUPLICATE", "TIMING_DELAY", "NEEDS_HUMAN_REVIEW"];
type SortKey = "variance" | "expected" | "confidence";

export default function Results({ batchId, onOpenTrace }: { batchId: string; onOpenTrace: (paymentId: string) => void }) {
  const [data, setData] = useState<Paginated<ResultItem> | null>(null);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortKey>("variance");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  function load() {
    setLoading(true); setError(null);
    api.results(batchId, page, status || undefined)
      .then(setData).catch(e => setError(e)).finally(() => setLoading(false));
  }
  useEffect(load, [batchId, page, status]);

  const items = useMemo(() => {
    const q = search.trim().toLowerCase();
    const filtered = (data?.items ?? []).filter(r =>
      !q || [r.payment_id, r.order_id, r.settlement_id, r.bank_txn_id]
        .some(f => (f ?? "").toLowerCase().includes(q)));
    return [...filtered].sort((a, b) => {
      if (sort === "confidence") return b.confidence - a.confidence;
      if (sort === "expected") return (b.expected_amount_paise ?? 0) - (a.expected_amount_paise ?? 0);
      return Math.abs(b.variance_paise ?? 0) - Math.abs(a.variance_paise ?? 0);
    });
  }, [data, search, sort]);

  const pageExceptions = items.filter(r => r.status !== "FULLY_RECONCILED").length;
  const pageReconciled = items.filter(r => r.status === "FULLY_RECONCILED").length;
  const firstRecord = data ? (data.page - 1) * data.page_size + 1 : 0;
  const lastRecord = data ? Math.min(data.page * data.page_size, data.total) : 0;
  const cell = "px-3 py-3 text-[13px] tabular-nums";
  return (
    <Section title="Reconciliation results"
      note={data ? `${data.total} records · batch ${data.batch_status}` : undefined}
      actions={
        <a href={`/api/v1/batches/${batchId}/export?format=csv`}
          className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-sm font-medium text-ink hover:bg-muted">
          <Icon name="doc" className="h-3.5 w-3.5" /> Export CSV
        </a>
      }>
      <div className="mb-3 flex flex-wrap items-center gap-2 text-sm">
        <label className="relative">
          <span className="sr-only">Search records</span>
          <Icon name="search" className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-ink-2" />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search payment / order / settlement / UTR…"
            className="w-72 rounded-lg border border-line py-2 pl-8 pr-3 text-sm" />
        </label>
        <select value={status} onChange={e => { setPage(1); setStatus(e.target.value); }}
          className="rounded-lg border border-line bg-white px-2 py-2" aria-label="Filter by status">
          {STATUSES.map(s => <option key={s} value={s}>{s || "All statuses"}</option>)}
        </select>
        <select value={sort} onChange={e => setSort(e.target.value as SortKey)}
          className="rounded-lg border border-line bg-white px-2 py-2" aria-label="Sort records">
          <option value="variance">Sort: variance</option>
          <option value="expected">Sort: expected net</option>
          <option value="confidence">Sort: confidence</option>
        </select>
      </div>

      {data && !loading && (
        <div className="mb-4 grid gap-2 sm:grid-cols-3">
          <div className="rounded-lg border border-line bg-muted/50 px-3 py-2.5">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-2">Showing</p>
            <p className="mt-0.5 font-semibold tabular-nums text-ink">{firstRecord}–{lastRecord} <span className="font-normal text-ink-2">of {data.total}</span></p>
          </div>
          <div className="rounded-lg border border-fin-600/25 bg-fin-100/50 px-3 py-2.5">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-2">Reconciled on page</p>
            <p className="mt-0.5 font-semibold tabular-nums text-fin-600">{pageReconciled}</p>
          </div>
          <div className="rounded-lg border border-risk-600/25 bg-risk-100/50 px-3 py-2.5">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-2">Needs attention</p>
            <p className="mt-0.5 font-semibold tabular-nums text-risk-600">{pageExceptions}</p>
          </div>
        </div>
      )}

      {loading ? <SkeletonTable rows={8} cols={7} /> : null}
      {error ? <ErrorState error={error} retry={load} /> : null}

      {data && !loading ? (
        items.length === 0 ? (
          <EmptyState title="No records match"
            hint={data.note ?? "Adjust the search or filters."} />
        ) : (
          <>
            <div className="max-w-full overflow-x-auto rounded-lg border border-line">
              <table className="min-w-[1320px] divide-y divide-line text-left">
                <colgroup>
                  <col className="w-[140px]" />
                  <col className="w-[150px]" />
                  <col className="w-[170px]" />
                  <col className="w-[150px]" />
                  <col className="w-[130px]" />
                  <col className="w-[130px]" />
                  <col className="w-[120px]" />
                  <col className="w-[170px]" />
                  <col className="w-[110px]" />
                  <col className="w-[150px]" />
                  <col className="w-[90px]" />
                </colgroup>
                <thead className="bg-muted text-[11px] uppercase tracking-wide text-ink-2">
                  <tr>
                    {["Payment", "Order", "Settlement", "Bank txn", "Expected net", "Actual credit",
                      "Variance", "Status", "Confidence", "Match method", "Trace"].map(h => (
                      <th key={h} className="whitespace-nowrap px-3 py-2 font-semibold">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-line bg-white">
                  {items.map(r => (
                    <tr key={r.payment_id}
                      className={`cursor-pointer border-l-2 transition-colors duration-150 hover:bg-brand-100/40 ${
                        r.variance_paise && r.variance_paise < 0 ? "border-l-risk-600/60" : "border-l-transparent"
                      }`}
                      onClick={() => onOpenTrace(r.payment_id)}
                      title="Open transaction trace">
                      <td className={`${cell} whitespace-nowrap font-mono font-medium`}>
                        {r.payment_id}
                      </td>
                      <td className={`${cell} whitespace-nowrap font-mono text-ink-2`}>
                        {r.order_id ?? "—"}
                      </td>
                      <td className={`${cell} whitespace-nowrap font-mono text-ink-2`}>
                        {r.settlement_id ?? "—"}
                      </td>
                      <td className={`${cell} whitespace-nowrap font-mono text-ink-2`}>
                        {r.bank_txn_id ?? "—"}
                      </td>
                      <td className={cell}>{rupees(r.expected_amount_paise)}</td>
                      <td className={cell}>{rupees(r.actual_amount_paise)}</td>
                      <td className={`${cell} font-semibold ${r.variance_paise && r.variance_paise < 0 ? "text-risk-600" : r.variance_paise && r.variance_paise > 0 ? "text-fin-600" : "text-ink-2"}`}>
                        {r.variance_paise === null ? "—" : rupees(r.variance_paise)}
                      </td>
                      <td className="px-3 py-2"><StatusBadge status={r.status} /></td>
                      <td className="px-3 py-2"><ConfidenceBadge value={r.confidence} /></td>
                      <td className={`${cell} max-w-48 truncate text-ink-2`} title={r.match_method}>
                        {r.match_method}
                      </td>
                      <td className="px-3 py-3">
                        <button
                          onClick={e => { e.stopPropagation(); onOpenTrace(r.payment_id); }}
                          className="inline-flex items-center gap-1 rounded-md border border-line px-2 py-1 text-xs font-semibold text-brand-600 hover:border-brand-500 hover:bg-brand-100"
                          aria-label={`Open trace for ${r.payment_id}`}>
                          <Icon name="search" className="h-3.5 w-3.5" /> Trace
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager page={data.page} totalPages={data.total_pages} onPage={setPage} />
          </>
        )
      ) : null}
    </Section>
  );
}
