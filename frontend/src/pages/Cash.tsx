import { useEffect, useState } from "react";
import { Area, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import type { CashPosition } from "../types";
import { ErrorState, MetricCard, Section, Skeleton } from "../components/ui";
import { rupees, rupeesInputToPaise } from "../format";

export default function Cash({ batchId }: { batchId: string }) {
  const [cash, setCash] = useState<CashPosition | null>(null);
  const [opening, setOpening] = useState("1000000");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  function load() {
    setLoading(true); setError(null);
    api.cash(batchId, rupeesInputToPaise(opening), 7)
      .then(setCash).catch(e => setError(e)).finally(() => setLoading(false));
  }
  useEffect(load, [batchId]); // eslint-disable-line react-hooks/exhaustive-deps

  const series = cash
        ? [{ date: "Today", confirmed: cash.actual_cash_paise, projected: null as number | null },
       ...cash.forecast.map(f => ({
          date: `T+${f.day}`, confirmed: null as number | null, projected: f.projected_cash_paise,
       }))]
    : [];

  return (
    <div className="space-y-4">
      <Section title="Cash position"
        note={cash ? `as of ${cash.as_of.replace("T", " ").slice(0, 19)} UTC · confidence ${cash.confidence}` : undefined}
        actions={
          <div className="flex items-center gap-2 text-sm">
            <label htmlFor="opening" className="text-ink-2">Opening ₹</label>
            <input id="opening" value={opening} onChange={e => setOpening(e.target.value)}
              className="w-36 rounded-lg border border-line px-2 py-1.5 tabular-nums" />
            <button onClick={load}
              className="rounded-lg border border-line px-3 py-1.5 font-medium hover:bg-muted">
              Recalculate
            </button>
          </div>
        }>
        {loading && !cash ? <div className="grid gap-3 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
        </div> : null}
        {error ? <ErrorState error={error} retry={load} /> : null}
        {cash && !loading ? (
          <>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <MetricCard label="Confirmed cash" value={rupees(cash.actual_cash_paise)} tone="brand"
                icon="bank" countUp
                sub={`credits ${rupees(cash.confirmed_credits_paise)} − debits ${rupees(cash.confirmed_debits_paise)}`}
                tip="Opening + evidence-linked bank credits − confirmed debits" />
              <MetricCard label="Pending settlements" value={rupees(cash.pending_settlements_paise)}
                tone="warn" icon="clock" countUp sub="timing-delayed only"
                tip="Settlements young enough to plausibly still be in transit" />
              <MetricCard label="Expected cash" value={rupees(cash.expected_cash_paise)}
                icon="chart" countUp sub="confirmed + pending (projection)"
                tip="What cash should become if pending settlements land" />
              <MetricCard label="Unexplained variance" value={rupees(cash.variance_paise)}
                tone={cash.variance_paise < 0 ? "bad" : "neutral"} icon="diff"
                sub={`incl. ${rupees(cash.bank_charges_paise)} bank charges`}
                tip="Confirmed cash vs what should have landed — itemized below" />
            </div>

            <div className="mt-4 h-72" role="img"
              aria-label={`Confirmed cash ${rupees(cash.actual_cash_paise)}; seven-day forecast rising to ${rupees(cash.forecast[cash.forecast.length - 1]?.projected_cash_paise ?? 0)}. Forecast is not booked cash.`}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={series} margin={{ top: 12, right: 10, left: 8, bottom: 8 }}>
                  <defs>
                    <linearGradient id="confirmedCashFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#16a36a" stopOpacity={0.18} />
                      <stop offset="100%" stopColor="#16a36a" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="#e5eaf2" />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#63708a" }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "#63708a" }} tickFormatter={(v: number) => `${(v / 1e7).toFixed(1)}Cr`} width={48} axisLine={false} tickLine={false} />
                  <Tooltip formatter={(v: number) => rupees(v)} />
                  <Legend verticalAlign="top" align="right" height={28} wrapperStyle={{ fontSize: 11, textTransform: "uppercase" }} />
                  <Area type="monotone" dataKey="confirmed" name="Confirmed" stroke="none"
                    fill="url(#confirmedCashFill)" connectNulls animationDuration={900} />
                  <Line type="monotone" dataKey="confirmed" name="Confirmed" stroke="#16a36a"
                    strokeWidth={2.5} dot={false} connectNulls animationDuration={900} />
                  <Line type="monotone" dataKey="projected" name="Forecast — NOT booked cash"
                    stroke="#305eff" strokeWidth={2} strokeDasharray="4 4" dot={false} connectNulls
                    animationDuration={900} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            <div className="mt-4 grid gap-4 lg:grid-cols-2">
              <div className="rounded-xl border border-line p-3.5">
                <p className="text-sm font-semibold">Variance explanation</p>
                <ul className="mt-2 space-y-1.5 text-sm text-ink-2">
                  <li className="flex justify-between"><span>Known bank charges</span>
                    <span className="tabular-nums text-ink">{rupees(cash.bank_charges_paise)}</span></li>
                  <li className="flex justify-between"><span>Excluded as ambiguous / duplicated</span>
                    <span className="tabular-nums text-ink">{rupees(cash.unattributed_or_excluded_paise)}</span></li>
                  <li className="flex justify-between border-t border-line pt-1.5 font-semibold">
                    <span className="text-ink">Total unexplained variance</span>
                    <span className={`tabular-nums ${cash.variance_paise < 0 ? "text-risk-600" : "text-ink"}`}>
                      {rupees(cash.variance_paise)}</span></li>
                </ul>
              </div>
              <div className="rounded-xl border border-line p-3.5">
                <p className="text-sm font-semibold">Forecast assumptions ({cash.forecast_horizon_days}-day horizon)</p>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-ink-2">
                  {cash.assumptions.map((a, i) => <li key={i}>{a}</li>)}
                </ul>
              </div>
            </div>
          </>
        ) : null}
      </Section>
    </div>
  );
}
