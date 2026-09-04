// Same-origin client. No keys, no hosts — the browser never holds secrets.
export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number) {
    super(message);
  }
}

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let code = "http_error";
    let message = `request failed (${response.status})`;
    try {
      const body = await response.json();
      if (body?.error) { code = body.error.code ?? code; message = body.error.message ?? message; }
    } catch { /* non-JSON error body */ }
    throw new ApiError(code, message, response.status);
  }
  return response.json() as Promise<T>;
}

export const api = {
  createBatch: (files: { ledger: File; settlements: File; bank: File }) => {
    const form = new FormData();
    form.append("internal_ledger", files.ledger);
    form.append("settlements", files.settlements);
    form.append("bank_statement", files.bank);
    return fetch("/api/v1/batches", { method: "POST", body: form })
      .then(r => parse<import("./types").BatchCreate>(r));
  },
  createFixtureBatch: () =>
    fetch("/api/v1/batches?fixture=synthetic-v2", { method: "POST" })
      .then(r => parse<import("./types").BatchCreate>(r)),
  reconcile: (batchId: string) =>
    fetch(`/api/v1/batches/${batchId}/reconcile`, { method: "POST" })
      .then(r => parse<import("./types").ReconcileResponse>(r)),
  metrics: (batchId: string) =>
    fetch(`/api/v1/batches/${batchId}/metrics`).then(r => parse<import("./types").Metrics>(r)),
  results: (batchId: string, page: number, status?: string) =>
    fetch(`/api/v1/batches/${batchId}/results?page=${page}&page_size=20${status ? `&status=${status}` : ""}`)
      .then(r => parse<import("./types").Paginated<import("./types").ResultItem>>(r)),
  exceptions: (batchId: string, page: number, status?: string) =>
    fetch(`/api/v1/batches/${batchId}/exceptions?page=${page}&page_size=100${status ? `&status=${status}` : ""}`)
      .then(r => parse<import("./types").Paginated<import("./types").ResultItem>>(r)),
  cash: (batchId: string, openingPaise: number, horizon: number) =>
    fetch(`/api/v1/batches/${batchId}/cash-position?opening_balance_paise=${openingPaise}&horizon=${horizon}`)
      .then(r => parse<import("./types").CashPosition>(r)),
  trace: (paymentId: string, batchId: string) =>
    fetch(`/api/v1/transactions/${paymentId}/trace?batch_id=${batchId}`)
      .then(r => parse<import("./types").TraceData>(r)),
  ask: (batchId: string, question: string) =>
    fetch("/api/v1/ai/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ batch_id: batchId, question }),
    }).then(r => parse<import("./types").AiAnswer>(r)),
};
