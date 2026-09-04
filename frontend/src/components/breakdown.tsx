import { formatPaise } from "../format";

/** Gross-to-net calculation with exact values from the API payload. */
export function AmountBreakdown({ breakdown, actualPaise, variancePaise }: {
  breakdown: Record<string, number> | null;
  actualPaise: number | null;
  variancePaise: number | null;
}) {
  if (!breakdown) return null;
  const rows: { label: string; value: number; tone: "pos" | "neg" }[] = [
    { label: "Gross payment", value: breakdown.gross_amount_paise ?? 0, tone: "pos" },
    { label: "Fee", value: -(breakdown.fee_paise ?? 0), tone: "neg" },
    { label: "Tax on fee", value: -(breakdown.tax_paise ?? 0), tone: "neg" },
    { label: "Refund / debit", value: -(breakdown.debit_paise ?? 0), tone: "neg" },
    { label: "Adjustment credit", value: breakdown.credit_paise ?? 0, tone: "pos" },
  ];
  const expected = rows.reduce((sum, r) => sum + r.value, 0);
  return (
    <div className="space-y-1" aria-label="Gross to net calculation">
      {rows.map(r => (
        <div key={r.label} className="flex items-center justify-between gap-4 rounded-md px-2 py-2 text-sm hover:bg-muted/60">
          <span className="text-ink-2">{r.label}</span>
          <span className={`shrink-0 font-medium tabular-nums ${r.tone === "neg" ? "text-risk-600" : "text-ink"}`}>
            {formatPaise(r.value)}
          </span>
        </div>
      ))}
      <div className="mt-2 flex items-center justify-between gap-4 border-t border-line px-2 pt-3 text-sm font-semibold">
        <span>Expected net</span>
        <span className="tabular-nums text-brand-600">{formatPaise(expected)}</span>
      </div>
      {actualPaise !== null && (
        <div className="flex items-center justify-between gap-4 px-2 py-2 text-sm">
          <span className="text-ink-2">Bank credit (actual)</span>
          <span className="tabular-nums text-ink">{formatPaise(actualPaise)}</span>
        </div>
      )}
      {variancePaise !== null && variancePaise !== 0 && (
        <div className={`flex items-center justify-between gap-4 rounded-md border px-3 py-2 text-sm font-semibold
          ${variancePaise < 0 ? "border-risk-600/40 bg-risk-100 text-risk-600"
            : "border-warn-600/40 bg-warn-100 text-warn-600"}`}>
          <span>Variance</span>
          <span className="tabular-nums">{formatPaise(variancePaise)}</span>
        </div>
      )}
    </div>
  );
}
