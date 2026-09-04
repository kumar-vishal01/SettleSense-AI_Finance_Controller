import { useEffect, useState } from "react";
import { Area, AreaChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import type { CashPosition, Metrics, ResultItem } from "../types";
import { ErrorState, MetricCard, Section, Skeleton, StatusBadge } from "../components/ui";
import { rupees } from "../format";
import { Icon } from "../components/icons";

const STATUS_LABELS: Record<string, string> = {
  FULLY_RECONCILED: "Fully reconciled",
  MISSING_IN_SETTLEMENT: "Settlement missing",
  MISSING_BANK_CREDIT: "Bank credit missing",
  AMOUNT_MISMATCH: "Amount mismatch",
  DUPLICATE: "Duplicate",
  TIMING_DELAY: "Timing delay",
  NEEDS_HUMAN_REVIEW: "Needs human review",
};

export default function Overview({ batchId, onRerun, onOpenTrace, onOpenExceptions }: {
  batchId: string; onRerun: () => void; onOpenTrace?: (paymentId: string) => void;
  onOpenExceptions?: () => void;
}) {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [cash, setCash] = useState<CashPosition | null>(null);
  const [top, setTop] = useState<ResultItem[]>([]);
  const [recent, setRecent] = useState<ResultItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  function load() {
    setLoading(true); setError(null);
    Promise.all([
      api.metrics(batchId), api.cash(batchId, 1_000_000, 7),
      api.exceptions(batchId, 1), api.results(batchId, 1),
    ]).then(([m, c, e, r]) => {
      setMetrics(m); setCash(c);
      setTop([...(e.items ?? [])]
        .sort((a, b) => Math.abs(b.variance_paise ?? b.expected_amount_paise ?? 0)
                        - Math.abs(a.variance_paise ?? a.expected_amount_paise ?? 0))
        .slice(0, 3));
      setRecent(r.items.slice(0, 5));
    }).catch(e => setError(e)).finally(() => setLoading(false));
  }
  useEffect(load, [batchId]);

  if (loading && !metrics) return <div className="space-y-4">
    <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-6">
      {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
    </div>
    <Skeleton className="h-64 rounded-xl" />
  </div>;
  if (error) return <ErrorState error={error} retry={load} />;
  if (!metrics?.available) return (
    <Section title="Finance control center" note={metrics?.note ?? undefined}>
      <p className="text-sm text-ink-2">This batch is validated but not reconciled yet.</p>
      <button onClick={onRerun}
        className="mt-3 rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-500">
        Run reconciliation
      </button>
          </Section>
  );

  const partialCount = (metrics.status_counts.TIMING_DELAY ?? 0) + (metrics.status_counts.NEEDS_HUMAN_REVIEW ?? 0);
  const duplicateCount = metrics.status_counts.DUPLICATE ?? 0;
  const unmatchedCount = Math.max(0, metrics.exceptions - partialCount - duplicateCount);
  const healthData = [
    { name: "Matched", value: metrics.fully_reconciled, color: "#168A5A" },
    { name: "Partial matches", value: partialCount, color: "#C77700" },
    { name: "Unmatched", value: unmatchedCount, color: "#D64545" },
    { name: "Duplicate / ambiguous", value: duplicateCount, color: "#7E22CE" },
  ].filter(item => item.value > 0);
  const forecastSeries = cash ? [{ date: "Today", confirmed: cash.actual_cash_paise, projected: null as number | null },
    ...cash.forecast.map(f => ({ date: `T+${f.day}`, confirmed: null as number | null, projected: f.projected_cash_paise }))] : [];

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <MetricCard label="Records" value={String(metrics.total_records)} sub="processed" icon="layers" countUp />
        <MetricCard label="Matched" value={String(metrics.fully_reconciled)} sub={`${metrics.exceptions} need review`} tone="good" icon="check" countUp />
        <div className="card border border-brand-500/30 bg-brand-100/60 p-4 shadow-[0_4px_16px_rgba(0,66,226,.1)] animate-fade-up">
          <div className="flex items-center justify-between"><p className="text-label-caps text-brand-600">Match rate</p><span className="rounded-sm bg-brand-600 p-1.5 text-white"><Icon name="pulse" className="h-3.5 w-3.5" /></span></div>
          <p className="mt-1.5 text-title-xl font-bold tabular-nums text-brand-600">{(metrics.match_rate * 100).toFixed(1)}%</p>
          <p className="mt-1 text-caption text-ink-muted">primary control metric</p>
        </div>
        <MetricCard label="Exceptions" value={String(metrics.exceptions)} sub="visible with evidence" tone="warn" icon="alert" countUp />
        <MetricCard label="Net cash position" value={rupees(cash?.actual_cash_paise ?? null)} sub={`expected ${rupees(cash?.expected_cash_paise ?? null)}`} tone="brand" icon="bank" />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.2fr_.8fr]">
        <Section title="Reconciliation health" note="deterministic engine outcome">
          <div className="grid items-center gap-4 sm:grid-cols-[minmax(180px,240px)_1fr]">
            <div className="h-52" role="img" aria-label={`${metrics.fully_reconciled} matched and ${metrics.exceptions} exceptions out of ${metrics.total_records} records`}>
              <ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={healthData} dataKey="value" innerRadius="62%" outerRadius="86%" paddingAngle={3} stroke="#fff" strokeWidth={3} isAnimationActive animationDuration={850}>{healthData.map(item => <Cell key={item.name} fill={item.color} />)}</Pie><Tooltip formatter={(v: number) => [`${v} records`, "Result"]} /></PieChart></ResponsiveContainer>
            </div>
            <div className="space-y-2.5 text-sm">{healthData.map(item => <div key={item.name} className="flex items-center justify-between gap-3"><span className="flex items-center gap-2 text-ink-2"><span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.color }} />{item.name}</span><strong className="tabular-nums">{item.value}</strong></div>)}<p className="border-t border-line pt-3 text-xs leading-5 text-ink-2">{metrics.fully_reconciled} of {metrics.total_records} records were reconciled automatically. {metrics.exceptions} records require review.</p></div>
          </div>
        </Section>
        <Section title="Controller insight" note="evidence-backed summary">
          <div className="rounded-lg border border-warn-600/25 bg-warn-100/50 p-3.5"><div className="flex items-center gap-2 text-sm font-semibold"><Icon name="spark" className="h-4 w-4 text-warn-600" /> Review queue</div><p className="mt-3 text-sm leading-6 text-ink-2">{metrics.exceptions} records could not be resolved automatically. The largest unresolved amount is {top[0] ? rupees(Math.abs(top[0].variance_paise ?? top[0].expected_amount_paise ?? 0)) : "—"}{top[0] ? ` due to ${STATUS_LABELS[top[0].status]?.toLowerCase() ?? top[0].status.toLowerCase().replaceAll("_", " ")}.` : "."}</p><button onClick={onOpenExceptions} disabled={!onOpenExceptions} className="mt-4 inline-flex items-center gap-1.5 text-sm font-semibold text-brand-600 disabled:opacity-50">Open exceptions <Icon name="arrowright" className="h-3.5 w-3.5" /></button></div>
          <dl className="mt-4 space-y-2 text-xs"><div className="flex justify-between"><dt className="text-ink-2">Engine</dt><dd className="font-semibold">Deterministic</dd></div><div className="flex justify-between"><dt className="text-ink-2">Data scope</dt><dd className="font-semibold">Synthetic demo data</dd></div></dl>
        </Section>
      </div>

      <Section title="Cash position" note="confirmed versus projected · synthetic demo data">
        <div className="grid gap-4 lg:grid-cols-[.7fr_1.3fr]"><dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4 lg:grid-cols-2"><div><dt className="text-xs text-ink-2">Opening balance</dt><dd className="mt-1 font-semibold tabular-nums">{rupees(cash?.opening_balance_paise)}</dd></div><div><dt className="text-xs text-ink-2">Inflows</dt><dd className="mt-1 font-semibold tabular-nums text-fin-600">{rupees(cash?.confirmed_credits_paise)}</dd></div><div><dt className="text-xs text-ink-2">Outflows</dt><dd className="mt-1 font-semibold tabular-nums text-risk-600">-{rupees(cash?.confirmed_debits_paise)}</dd></div><div><dt className="text-xs text-ink-2">Forecast balance</dt><dd className="mt-1 font-semibold tabular-nums text-brand-600">{rupees(cash?.expected_cash_paise)}</dd></div></dl><div className="h-48" role="img" aria-label="Current and projected cash trajectory"><ResponsiveContainer width="100%" height="100%"><AreaChart data={forecastSeries} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}><defs><linearGradient id="overviewCash" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#168a5a" stopOpacity=".18" /><stop offset="1" stopColor="#168a5a" stopOpacity="0" /></linearGradient></defs><CartesianGrid vertical={false} strokeDasharray="3 3" stroke="#e5eaf2" /><XAxis dataKey="date" tick={{ fontSize: 10, fill: "#63708a" }} axisLine={false} tickLine={false} /><YAxis hide /><Tooltip formatter={(v: number) => rupees(v)} /><Area type="monotone" dataKey="confirmed" name="Current" stroke="#168a5a" fill="url(#overviewCash)" strokeWidth={2.5} dot={false} animationDuration={800} /><Area type="monotone" dataKey="projected" name="Forecast" stroke="#0042e2" fill="none" strokeWidth={2} strokeDasharray="5 4" dot={false} animationDuration={950} /></AreaChart></ResponsiveContainer></div></div>
        {cash && cash.expected_cash_paise < cash.actual_cash_paise && <p className="mt-3 flex items-center gap-2 text-xs font-medium text-warn-600"><Icon name="alert" className="h-3.5 w-3.5" /> Forecast is below current confirmed cash; review pending and excluded amounts.</p>}
      </Section>

      <div className="grid gap-4 lg:grid-cols-[1.1fr_.9fr]">
        <Section title="Exceptions requiring attention" note="highest monetary impact">
          <div className="overflow-x-auto"><table className="w-full min-w-[600px] text-left text-xs"><thead className="border-b border-line text-[10px] uppercase tracking-wide text-ink-2"><tr><th className="pb-2">Exception</th><th className="pb-2">Type</th><th className="pb-2">Amount</th><th className="pb-2">Severity</th><th className="pb-2">Status</th><th /></tr></thead><tbody className="divide-y divide-line">{top.map(r => <tr key={r.payment_id} className="transition hover:bg-muted/50"><td className="py-2.5 font-mono font-semibold">{r.payment_id}</td><td className="py-2.5 text-ink-2">{STATUS_LABELS[r.status] ?? r.status}</td><td className="py-2.5 font-semibold tabular-nums text-risk-600">{rupees(Math.abs(r.variance_paise ?? r.expected_amount_paise ?? 0))}</td><td className="py-2.5"><span className="font-semibold uppercase text-warn-600">{r.severity}</span></td><td className="py-2.5"><StatusBadge status={r.status} /></td><td className="py-2.5 text-right"><button onClick={() => onOpenTrace?.(r.payment_id)} className="font-semibold text-brand-600 hover:underline">View</button></td></tr>)}</tbody></table></div><button onClick={onOpenExceptions} className="mt-3 text-xs font-semibold text-brand-600 hover:underline">View all exceptions →</button>
        </Section>
        <Section title="Recent reconciliations" note={`${recent.length} latest records`}>
          <div className="overflow-x-auto"><table className="w-full min-w-[480px] text-left text-xs"><thead className="border-b border-line text-[10px] uppercase tracking-wide text-ink-2"><tr><th className="pb-2">Record</th><th className="pb-2">Amount</th><th className="pb-2">Result</th><th className="pb-2">Confidence</th></tr></thead><tbody className="divide-y divide-line">{recent.map(r => <tr key={r.payment_id} className="transition hover:bg-muted/50"><td className="py-2.5 font-mono font-semibold">{r.payment_id}</td><td className="py-2.5 tabular-nums">{rupees(r.expected_amount_paise)}</td><td className="py-2.5"><StatusBadge status={r.status} /></td><td className="py-2.5 tabular-nums text-ink-2">{(r.confidence * 100).toFixed(0)}%</td></tr>)}</tbody></table></div>
        </Section>
      </div>

      <Section title="Recent activity" note="current batch workflow">
        <ol className="grid gap-3 sm:grid-cols-5" aria-label="Recent reconciliation activity">
          {[
            ["Batch loaded", "3 sources validated", "check"],
            ["Records processed", `${metrics.records_processed} records`, "layers"],
            ["Records matched", `${metrics.fully_reconciled} records`, "check"],
            ["Exceptions identified", `${metrics.exceptions} records`, "alert"],
            ["Cash position", cash?.confidence ?? "confidence pending", "bank"],
          ].map(([title, detail, icon], index) => <li key={title} className="relative border-l-2 border-line pl-3 sm:border-l-0 sm:border-t-2 sm:pl-0 sm:pt-3">
            <span className={`absolute -left-[7px] top-1 h-3 w-3 rounded-full border-2 border-white ${index === 3 ? "bg-warn-600" : "bg-fin-600"} sm:-top-[7px] sm:left-0`} aria-hidden="true" />
            <div className="flex items-center gap-1.5 text-xs font-semibold text-ink"><Icon name={icon} className="h-3.5 w-3.5 text-ink-muted" />{title}</div>
            <p className="mt-1 text-[11px] text-ink-2">{detail}</p>
          </li>)}
        </ol>
      </Section>
    </div>
  );
}
