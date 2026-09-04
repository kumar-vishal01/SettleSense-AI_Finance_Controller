// Paise -> rupees ONLY here (display layer). Never send rupees back.
export function rupees(paise: number | null | undefined): string {
  if (paise === null || paise === undefined) return "—";
  const sign = paise < 0 ? "-" : "";
  const abs = Math.abs(paise);
  const whole = Math.floor(abs / 100).toLocaleString("en-IN");
  const frac = String(abs % 100).padStart(2, "0");
  return `${sign}₹${whole}.${frac}`;
}

export function paiseLabel(paise: number | null | undefined): string {
  if (paise === null || paise === undefined) return "—";
  return `${paise.toLocaleString("en-IN")} paise`;
}

export const STATUS_STYLES: Record<string, string> = {
  FULLY_RECONCILED: "bg-emerald-100 text-emerald-900 border-emerald-300",
  MISSING_IN_SETTLEMENT: "bg-red-100 text-red-900 border-red-300",
  MISSING_BANK_CREDIT: "bg-red-100 text-red-900 border-red-300",
  AMOUNT_MISMATCH: "bg-orange-100 text-orange-900 border-orange-300",
  DUPLICATE: "bg-purple-100 text-purple-900 border-purple-300",
  TIMING_DELAY: "bg-sky-100 text-sky-900 border-sky-300",
  NEEDS_HUMAN_REVIEW: "bg-amber-100 text-amber-900 border-amber-300",
};

export function statusStyle(status: string): string {
  return STATUS_STYLES[status] ?? "bg-slate-100 text-slate-900 border-slate-300";
}

export function friendlyStatus(status: string): string {
  return status.replaceAll("_", " ").toLowerCase();
}

export const SEVERITY_STYLES: Record<string, string> = {
  high: "bg-red-50 text-red-800 border-red-200",
  medium: "bg-amber-50 text-amber-800 border-amber-200",
  low: "bg-slate-50 text-slate-700 border-slate-200",
  none: "bg-slate-50 text-slate-500 border-slate-200",
};

/** Parse a user-typed rupee amount into integer paise using string math
 * only — the frontend twin of the backend's Decimal discipline. Accepts
 * "123", "123.4", "123.45"; rejects negatives/garbage by returning 0. */
export function rupeesInputToPaise(text: string): number {
  const trimmed = text.trim();
  if (!/^\d+(\.\d{1,2})?$/.test(trimmed)) return 0;
  const [whole, frac = ""] = trimmed.split(".");
  const fracPadded = (frac + "00").slice(0, 2);
  return Number(whole) * 100 + Number(fracPadded);
}

/** Signed paise -> "₹1,234.56" with sign, Indian grouping (display only). */
export function formatPaise(paise: number): string {
  return rupees(paise);
}
