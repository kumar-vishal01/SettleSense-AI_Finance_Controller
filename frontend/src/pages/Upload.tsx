import { useEffect, useRef, useState, type DragEvent } from "react";
import { api, ApiError } from "../api";
import type { BatchCreate } from "../types";
import { ProgressStepper, Section, ValidationList } from "../components/ui";
import { Icon } from "../components/icons";

const STEPS = ["Select files", "Validate", "Create batch", "Ready"];
const PIPELINE = ["Reading sources", "Validating records", "Normalizing fields", "Creating reconciliation batch", "Ready"];

export default function Upload({ onBatch }: { onBatch: (id: string) => void }) {
  const [files, setFiles] = useState<{ ledger: File | null; settlements: File | null; bank: File | null }>({
    ledger: null, settlements: null, bank: null });
  const [busy, setBusy] = useState<"files" | "fixture" | null>(null);
  const [pipelineStep, setPipelineStep] = useState(0);
  const [error, setError] = useState<unknown>(null);
  const [created, setCreated] = useState<BatchCreate | null>(null);
  const [dragOver, setDragOver] = useState<string | null>(null);
  const inputs = useRef<Record<string, HTMLInputElement | null>>({});

  const allSelected = !!(files.ledger && files.settlements && files.bank);
  const step = created ? 3 : busy ? 2 : allSelected ? 1 : 0;

  useEffect(() => {
    if (!busy) { setPipelineStep(0); return; }
    const timer = window.setInterval(() => setPipelineStep(current => Math.min(current + 1, PIPELINE.length - 1)), 260);
    return () => window.clearInterval(timer);
  }, [busy]);

  async function submit() {
    if (!allSelected) return;
    setBusy("files"); setError(null); setCreated(null);
    try {
      const batch = await api.createBatch({
        ledger: files.ledger!, settlements: files.settlements!, bank: files.bank! });
      setCreated(batch); onBatch(batch.batch_id);
    } catch (e) { setError(e); }
    finally { setBusy(null); }
  }

  async function useFixture() {
    setBusy("fixture"); setError(null); setCreated(null);
    try {
      const batch = await api.createFixtureBatch();
      setCreated(batch); onBatch(batch.batch_id);
    } catch (e) { setError(e); }
    finally { setBusy(null); }
  }

  function drop(kind: keyof typeof files, e: DragEvent<HTMLDivElement>) {
    e.preventDefault(); setDragOver(null);
    const file = e.dataTransfer.files?.[0];
    if (file) setFiles(f => ({ ...f, [kind]: file }));
  }

  const sourceCopy: Record<keyof typeof files, { number: string; description: string }> = {
    ledger: { number: "01", description: "Your company's source-of-truth transaction records." },
    settlements: { number: "02", description: "Processor or payment-provider settlement records." },
    bank: { number: "03", description: "Actual bank-side transaction movement." },
  };

  const slot = (kind: keyof typeof files, label: string) => (
    <div key={kind}
      onDragOver={e => { e.preventDefault(); setDragOver(kind); }}
      onDragLeave={() => setDragOver(null)}
      onDrop={e => drop(kind, e)}
      className={`group rounded-xl border p-5 text-left transition-all duration-200
        ${dragOver === kind ? "border-primary bg-primary/8"
          : files[kind] ? "border-fin-600/35 bg-fin-100/40" : "border-border-hairline bg-surface hover:border-primary/50"}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="font-mono text-xs font-semibold text-primary">{sourceCopy[kind].number}</span>
          <span className={`flex h-10 w-10 items-center justify-center rounded-lg ${files[kind] ? "bg-fin-100 text-fin-600" : "bg-muted text-ink-muted group-hover:bg-brand-100 group-hover:text-brand-600"}`}>
          <Icon name={files[kind] ? "check" : "upload"} className="h-5 w-5" />
          </span>
        </div>
        {files[kind] && <span className="flex items-center gap-1 text-xs font-semibold text-fin-600"><span className="h-1.5 w-1.5 rounded-full bg-fin-600" /> Ready</span>}
      </div>
      <p className="mt-4 text-base font-semibold text-ink">{label}</p>
      <p className="mt-1 min-h-10 text-sm leading-5 text-ink-2">{sourceCopy[kind].description}</p>
      <div className="mt-4 flex items-center justify-between text-[11px] uppercase tracking-[0.08em] text-ink-subtle"><span>Expected</span><span className="font-semibold text-ink-2">CSV</span></div>
      <div className={`mt-2 rounded-lg border border-dashed px-3 py-2.5 ${files[kind] ? "border-fin-600/25 bg-white/70" : "border-border-hairline bg-muted/40"}`}>
        <p className="truncate text-sm font-medium text-ink" title={files[kind]?.name}>{files[kind]?.name ?? "Drop file here or browse"}</p>
        <p className="mt-0.5 text-[11px] text-ink-2">{files[kind] ? `${(files[kind]!.size / 1024).toFixed(1)} KB · CSV selected` : "CSV files only"}</p>
      </div>
      <input ref={el => { inputs.current[kind] = el; }} type="file" accept=".csv" className="sr-only"
        id={`file-${kind}`} onChange={e => setFiles(f => ({ ...f, [kind]: e.target.files?.[0] ?? null }))} />
      <button onClick={() => inputs.current[kind]?.click()}
        className="mt-4 rounded-lg border border-border-hairline px-3 py-1.5 text-sm font-medium text-ink hover:border-primary hover:bg-brand-100 hover:text-brand-600 transition"
        aria-label={`Choose ${label} file`}>
        Browse
      </button>
    </div>
  );

  return (
    <div className="space-y-4">
      <Section title="Load reconciliation sources" note="Bring together your internal ledger, settlement report, and bank statement.">
        <div className="mb-4"><ProgressStepper steps={STEPS} current={step} /></div>
        <div className="grid gap-3 md:grid-cols-3">
          {slot("ledger", "Internal ledger")}
          {slot("settlements", "Settlement report")}
          {slot("bank", "Bank statement")}
        </div>
        {allSelected && !created && <div className="mb-4 rounded-lg border border-fin-600/25 bg-fin-100/50 px-3.5 py-3 text-sm text-ink"><p className="font-semibold text-fin-600">3 sources ready</p><p className="mt-1 text-xs text-ink-2">✓ Internal ledger · selected &nbsp; ✓ Settlement report · selected &nbsp; ✓ Bank statement · selected</p></div>}
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button onClick={submit} disabled={!allSelected || busy !== null}
            className="btn btn-primary">
            <Icon name="check" className="h-4 w-4" />
            Validate & create batch
          </button>
          <span className="text-caption text-ink-muted">or use</span>
          <button onClick={useFixture} disabled={busy !== null}
            className="rounded-lg border border-border-hairline bg-surface-alt px-3 py-2 text-left transition hover:border-primary/40 hover:bg-brand-100">
            <Icon name="layers" className="h-4 w-4" />
            <span className="ml-1 inline-flex flex-col align-middle"><span className="text-sm font-semibold text-ink">Demo dataset</span><span className="text-[11px] text-ink-2">100 records · seeded anomalies</span></span>
          </button>
          {busy && <div className="basis-full rounded-lg border border-primary/15 bg-primary/5 px-3 py-2.5" role="status" aria-live="polite">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
              {PIPELINE.map((label, index) => <span key={label} className={`flex items-center gap-1.5 ${index <= pipelineStep ? "font-semibold text-primary" : "text-ink-subtle"}`}><span className={`h-1.5 w-1.5 rounded-full ${index === pipelineStep ? "animate-pulse bg-primary" : index < pipelineStep ? "bg-fin-600" : "bg-border-hairline"}`} />{label}{index < PIPELINE.length - 1 && <span className="ml-1 text-ink-subtle">→</span>}</span>)}
            </div>
          </div>}
        </div>
      </Section>

      {error ? (
        <div className="card border-2 border-primary/20 bg-primary/5 p-4 text-body text-primary animate-fade-up"
          role="alert">
          <p className="font-semibold">Upload failed</p>
          <p className="mt-1">
            {error instanceof ApiError ? `[${error.code}] ${error.message}` : String(error)}
          </p>
        </div>
      ) : null}

      {created ? (
        <Section title="Batch ready"
          note={`${created.record_count} records · 3 sources · ready for reconciliation`}
          actions={
            <a href={`/api/v1/batches/${created.batch_id}/export?format=csv`}
              className="inline-flex items-center gap-1.5 rounded-sm border border-border-hairline px-3 py-1.5 text-caption font-medium hover:bg-surface-alt transition">
              <Icon name="doc" className="h-3.5 w-3.5" /> Export
            </a>
          }>
          <dl className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
            <div><dt className="text-caption text-ink-muted">Batch ID</dt>
              <dd className="font-mono text-body text-ink">{created.batch_id}</dd></div>
            <div><dt className="text-caption text-ink-muted">Valid rows</dt>
              <dd className="tabular-nums text-body text-ink">{created.validation.valid_rows} / {created.validation.total_rows}</dd></div>
            <div><dt className="text-caption text-ink-muted">Ledger · Settlement · Bank</dt>
              <dd className="tabular-nums text-body text-ink">{created.counts.ledger_rows} · {created.counts.settlement_rows} · {created.counts.bank_rows}</dd></div>
            <div><dt className="text-caption text-ink-muted">Duplicates (kept, reported)</dt>
              <dd className="tabular-nums text-body text-ink">{created.validation.duplicate_rows}</dd></div>
          </dl>
          <div className="mt-4 flex flex-wrap items-center gap-3"><button onClick={() => onBatch(created.batch_id)} className="btn btn-primary"><Icon name="check" className="h-4 w-4" /> Run reconciliation</button><button onClick={() => onBatch(created.batch_id)} className="rounded-lg border border-line px-3 py-2 text-sm font-semibold hover:bg-muted">View batch</button></div>
          <ValidationList errors={created.validation.errors} />
          {created.validation.errors_truncated ? (
              <p className="mt-2 text-caption text-primary/75">
              Error list truncated in this response — the full list is stored with the batch.
            </p>
          ) : null}
        </Section>
      ) : null}
    </div>
  );
}
