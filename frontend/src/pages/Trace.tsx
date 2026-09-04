import { useEffect, useState } from "react";
import { api } from "../api";
import type { TraceData } from "../types";
import { ErrorState, Section, Skeleton, StatusBadge, EvidenceChip } from "../components/ui";
import { Icon } from "../components/icons";
import { AmountBreakdown } from "../components/breakdown";
import { rupees } from "../format";

type Step = {
  title: string; state: "done" | "missing" | "flag";
  timestamp?: string; source?: string; id?: string; amount?: string; note?: string;
};

function buildSteps(t: TraceData): Step[] {
  const s: Step[] = [];
  s.push({
    title: "Payment created (ledger)", state: "done",
    timestamp: t.ledger?.transaction_at, source: "Internal ledger",
    id: t.ledger?.internal_id,
    amount: rupees(t.ledger?.gross_amount_paise ?? null),
  });
  if (t.settlements?.length) {
    const withUtr = t.settlements.find(x => x.settlement_utr);
    s.push({
      title: "Settlement processed", state: "done",
      timestamp: t.settlements[0].transaction_at, source: "Settlement report",
      id: t.settlements.map(x => x.source_row_id).join(", "),
      amount: rupees(t.settlements.reduce((a, x) => a + (x.net_contribution_paise ?? 0), 0)),
      note: withUtr ? `UTR ${withUtr.settlement_utr}` : "no UTR on settlement rows",
    });
  } else {
    s.push({ title: "Settlement processed", state: "missing",
      note: "No settlement row matched this payment" });
  }
  if (t.bank) {
    s.push({
      title: "Bank credit found", state: "done",
      timestamp: t.bank.value_date, source: "Bank statement",
      id: t.bank.bank_txn_id, amount: rupees(t.bank.credit_paise || t.bank.debit_paise),
      note: t.bank.utr ? `UTR ${t.bank.utr}` : `desc: ${t.bank.description_excerpt}`.slice(0, 60),
    });
  } else {
    s.push({ title: "Bank credit found", state: "missing",
      note: "No bank entry linked — the money is not confirmed in the bank statement" });
  }
  if (t.decision) {
    s.push({
      title: "Reconciliation decision", state: t.decision.requires_review ? "flag" : "done",
      note: `${t.decision.status} via ${t.decision.match_method} (confidence ${t.decision.confidence})`,
    });
  }
  return s;
}

export default function Trace({ batchId, initialPaymentId = "pay_010" }: { batchId: string; initialPaymentId?: string }) {
  const [paymentId, setPaymentId] = useState(initialPaymentId);
  const [trace, setTrace] = useState<TraceData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  function run(pid = paymentId) {
    const target = pid.trim();
    if (!target) return;
    setPaymentId(target);
    setLoading(true); setError(null); setTrace(null);
    api.trace(target, batchId)
      .then(setTrace).catch(e => setError(e)).finally(() => setLoading(false));
  }

  useEffect(() => { run(initialPaymentId); }, [batchId, initialPaymentId]);

  const steps = trace ? buildSteps(trace) : [];

  return (
    <Section title="Transaction trace"
      note="payment → settlement → bank credit → decision → evidence">
      <form onSubmit={e => { e.preventDefault(); run(); }} className="flex items-center gap-2">
        <label className="sr-only" htmlFor="trace-input">Payment ID</label>
        <input id="trace-input" value={paymentId} onChange={e => setPaymentId(e.target.value)}
          placeholder="pay_001"
          className="w-44 rounded-lg border border-line px-2.5 py-1.5 font-mono text-sm" />
        <button type="submit" disabled={loading}
          className="rounded-lg bg-brand-600 px-3.5 py-2 text-sm font-semibold text-white hover:bg-brand-500 disabled:opacity-40">
          Trace
        </button>
        {loading && <Skeleton className="h-8 w-40" />}
      </form>

      {error ? <div className="mt-3"><ErrorState error={error} /></div> : null}

      {trace && !loading ? (
        <div className="mt-5 grid gap-5 lg:grid-cols-5">
          <ol className="relative space-y-5 border-l-2 border-line pl-5 lg:col-span-3"
              aria-label="Reconciliation chain">
            {steps.map((step, i) => (
              <li key={i} className="relative anim-fade-up" style={{ animationDelay: `${i * 60}ms` }}>
                <span
                  className={`absolute -left-[27px] flex h-5 w-5 items-center justify-center rounded-full border-2 bg-white
                    ${step.state === "done" ? "border-fin-600 text-fin-600"
                      : step.state === "missing" ? "border-risk-600 text-risk-600"
                      : "border-warn-600 text-warn-600"}`}
                  aria-hidden="true">
                  <Icon name={step.state === "done" ? "check" : step.state === "missing" ? "x" : "eye"}
                    className="h-2.5 w-2.5" />
                </span>
                <p className="text-sm font-semibold">{step.title}
                  <span className="ml-2 align-middle">
                    {step.state === "missing"
                      ? <span className="rounded bg-risk-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-risk-600">missing</span>
                      : step.state === "flag"
                        ? <span className="rounded bg-warn-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-warn-600">needs review</span>
                        : null}
                  </span>
                </p>
                <p className="text-xs text-ink-2">
                  {[step.timestamp?.replace("T", " ").slice(0, 19), step.source,
                    step.id && `#${step.id}`, step.amount && step.amount,
                    step.note].filter(Boolean).join(" · ")}
                </p>
              </li>
            ))}
          </ol>

          <div className="space-y-4 lg:col-span-2">
            {trace.decision && (
              <div className="rounded-xl border border-line p-3.5">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold">Decision</p>
                  <StatusBadge status={trace.decision.status} />
                </div>
                <p className="mt-2 text-xs text-ink-2">{trace.decision.reason}</p>
                <div className="mt-3">
                  <AmountBreakdown breakdown={trace.decision.expected_breakdown_paise}
                    actualPaise={trace.decision.actual_amount_paise}
                    variancePaise={trace.decision.variance_paise} />
                </div>
              </div>
            )}
            <div className="rounded-xl border border-line p-3.5">
              <p className="text-sm font-semibold">Evidence</p>
              <div className="mt-2 flex flex-wrap gap-1">
                {(trace.decision?.evidence ?? []).map(id => <EvidenceChip key={id} id={id} />)}
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {!trace && !loading && !error ? (
        <p className="mt-3 text-sm text-ink-2">
          Enter a payment ID (e.g. <code className="font-mono">pay_069</code>) to see its full chain.
        </p>
      ) : null}
    </Section>
  );
}
