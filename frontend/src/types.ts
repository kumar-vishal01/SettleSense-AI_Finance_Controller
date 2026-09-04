// API contracts (mirror backend/schemas.py). Money is integer paise; rupees
// exist only at the display layer.
export type ValidationItem = {
  file: string; row_number: number; field: string; message: string; code: string;
};
export type BatchCreate = {
  batch_id: string; source_hash: string; status: string; idempotent: boolean;
  record_count: number;
  counts: { ledger_rows: number; settlement_rows: number; bank_rows: number };
  validation: {
    valid: boolean; total_rows: number; valid_rows: number; skipped_rows: number;
    duplicate_rows: number; conflicting_rows: number; errors: ValidationItem[];
    errors_truncated: boolean;
  };
  started_at: string;
};
export type ResultItem = {
  payment_id: string; order_id: string | null; settlement_id: string | null;
  bank_txn_id: string | null; status: string; confidence: number;
  match_method: string; expected_amount_paise: number | null;
  actual_amount_paise: number | null; variance_paise: number | null;
  expected_breakdown_paise: Record<string, number> | null;
  severity: string; reason: string; evidence: string[]; requires_review: boolean;
  recommended_action?: string;
};
export type Paginated<T> = {
  items: T[]; page: number; page_size: number; total: number; total_pages: number;
  batch_status: string; note: string | null;
};
export type ReconcileResponse = {
  batch_id: string; status: string; idempotent: boolean; result_count: number;
  summary: { status_counts: Record<string, number>; fully_reconciled: number;
    exceptions: number; match_rate: number; total_variance_paise: number };
  processing_time_ms: number;
};
export type Metrics = {
  available: boolean; note: string | null; total_records: number;
  records_processed: number; fully_reconciled: number; exceptions: number;
  match_rate: number; status_counts: Record<string, number>;
  total_variance_paise: number; max_abs_variance_paise: number;
  processing_time_ms: number; records_per_second: number;
};
export type CashPosition = {
  opening_balance_paise: number; confirmed_credits_paise: number;
  confirmed_debits_paise: number; actual_cash_paise: number;
  pending_settlements_paise: number; expected_cash_paise: number;
  expected_confirmed_cash_paise: number; variance_paise: number;
  unattributed_or_excluded_paise: number; bank_charges_paise: number;
  forecast_horizon_days: number;
  forecast: { day: number; date: string; projected_cash_paise: number; note: string }[];
  assumptions: string[]; confidence: string;
  batch_id: string; batch_status: string; as_of: string;
};
export type AiAnswer = {
  answer: string; record_ids: string[]; tools_used: string[];
  requires_review: boolean; fallback: boolean; provider: string;
};
export type TraceShape = {
  ok: boolean; payment_id?: string;
  ledger?: Record<string, unknown>;
  settlements?: Record<string, unknown>[];
  bank?: Record<string, unknown> | null;
  decision?: Record<string, unknown> | null;
  error?: { code: string; message: string };
};

export type TraceRow = {
  source_row_id?: string; internal_id?: string; settlement_id?: string | null;
  settlement_utr?: string | null; gross_amount_paise?: number; fee_paise?: number;
  tax_paise?: number; debit_paise?: number; credit_paise?: number;
  net_contribution_paise?: number; transaction_at?: string;
  transaction_type?: string;
};
export type TraceData = {
  ok: boolean; payment_id: string;
  ledger?: TraceRow;
  settlements?: TraceRow[];
  bank?: { bank_txn_id: string; utr: string | null; credit_paise: number;
           debit_paise: number; value_date: string; description_excerpt: string } | null;
  decision?: {
    status: string; confidence: number; match_method: string;
    expected_amount_paise: number | null; actual_amount_paise: number | null;
    variance_paise: number | null;
    expected_breakdown_paise: Record<string, number> | null;
    reason: string; evidence: string[]; requires_review: boolean;
    recommended_action?: string;
  } | null;
  error?: { code: string; message: string };
};
