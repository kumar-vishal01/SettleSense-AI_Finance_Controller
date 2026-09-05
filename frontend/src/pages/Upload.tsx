import {
  useEffect,
  useMemo,
  useState,
} from "react";

import { api, ApiError } from "../api";
import type { BatchCreate } from "../types";

import {
  ProgressStepper,
  Section,
  ValidationList,
} from "../components/ui";

import { Icon } from "../components/icons";
import { FileUpload } from "../components/ui/file-upload-2";

const STEPS = [
  "Select files",
  "Validate",
  "Create batch",
  "Ready",
];

const PIPELINE = [
  "Reading sources",
  "Validating records",
  "Normalizing fields",
  "Creating reconciliation batch",
  "Ready",
];

type SourceFiles = {
  ledger: File | null;
  settlements: File | null;
  bank: File | null;
};

type FileRole = keyof SourceFiles;

/* -------------------------------------------------------------------------- */
/* FILE ROLE DETECTION                                                        */
/* -------------------------------------------------------------------------- */

function detectFileRole(file: File): FileRole | null {
  const name = file.name.toLowerCase().trim();

  /*
   * Bank statement
   *
   * Examples:
   * bank_statement_1000.csv
   * bank_statement.csv
   * bank.csv
   * statement_bank.csv
   */
  if (
    name.includes("bank_statement") ||
    name.includes("bank-statement") ||
    name.includes("bankstatement") ||
    name.includes("bank_statement") ||
    name.includes("bank")
  ) {
    return "bank";
  }

  /*
   * Settlement
   *
   * Examples:
   * settlement_1000.csv
   * settlement.csv
   * settlements.csv
   * payment_settlement.csv
   */
  if (
    name.includes("settlement") ||
    name.includes("settlements") ||
    name.includes("processor") ||
    name.includes("payout")
  ) {
    return "settlements";
  }

  /*
   * Ledger
   *
   * Examples:
   * ledger_1000.csv
   * ledger.csv
   * internal_ledger.csv
   * transaction_ledger.csv
   */
  if (
    name.includes("ledger") ||
    name.includes("internal_ledger") ||
    name.includes("internal-ledger") ||
    name.includes("transaction_ledger") ||
    name.includes("transaction-ledger")
  ) {
    return "ledger";
  }

  return null;
}

/* -------------------------------------------------------------------------- */
/* FORMAT FILE SIZE                                                           */
/* -------------------------------------------------------------------------- */

function formatBytes(bytes: number) {
  if (bytes === 0) return "0 B";

  const units = ["B", "KB", "MB", "GB"];

  const index = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1,
  );

  return `${(bytes / 1024 ** index).toFixed(
    index === 0 ? 0 : 1,
  )} ${units[index]}`;
}

/* -------------------------------------------------------------------------- */
/* UPLOAD PAGE                                                                */
/* -------------------------------------------------------------------------- */

export default function Upload({
  onBatch,
}: {
  onBatch: (id: string) => void;
}) {
  const [files, setFiles] = useState<SourceFiles>({
    ledger: null,
    settlements: null,
    bank: null,
  });

  const [busy, setBusy] = useState<
    "files" | "fixture" | null
  >(null);

  const [pipelineStep, setPipelineStep] = useState(0);

  const [error, setError] = useState<unknown>(null);

  const [created, setCreated] =
    useState<BatchCreate | null>(null);

  /* ------------------------------------------------------------------------ */
  /* FILE STATE                                                               */
  /* ------------------------------------------------------------------------ */

  const selectedFiles = useMemo(
    () =>
      [
        files.ledger,
        files.settlements,
        files.bank,
      ].filter(Boolean) as File[],
    [files],
  );

  const allSelected =
    !!files.ledger &&
    !!files.settlements &&
    !!files.bank;

  const selectedCount = selectedFiles.length;

  const step = created
    ? 3
    : busy
      ? 2
      : allSelected
        ? 1
        : 0;

  /* ------------------------------------------------------------------------ */
  /* PIPELINE ANIMATION                                                       */
  /* ------------------------------------------------------------------------ */

  useEffect(() => {
    if (!busy) {
      setPipelineStep(0);
      return;
    }

    const timer = window.setInterval(() => {
      setPipelineStep((current) =>
        Math.min(
          current + 1,
          PIPELINE.length - 1,
        ),
      );
    }, 500);

    return () =>
      window.clearInterval(timer);
  }, [busy]);

  /* ------------------------------------------------------------------------ */
  /* HANDLE FILE SELECTION                                                    */
  /* ------------------------------------------------------------------------ */

  function handleFilesAccepted(
    incomingFiles: File[],
  ) {
    setError(null);
    setCreated(null);

    /*
     * Only CSV files.
     */
    const csvFiles = incomingFiles.filter(
      (file) =>
        file.name
          .toLowerCase()
          .endsWith(".csv") ||
        file.type === "text/csv",
    );

    /*
     * Must have exactly 3 files.
     */
    if (csvFiles.length !== 3) {
      setFiles({
        ledger: null,
        settlements: null,
        bank: null,
      });

      setError(
        `Please select exactly 3 CSV files: Ledger, Settlement, and Bank. You selected ${csvFiles.length}.`,
      );

      return;
    }

    /*
     * ------------------------------------------------------------
     * IMPORTANT FIX
     * ------------------------------------------------------------
     *
     * Do NOT depend on:
     *
     * incomingFiles[0] = ledger
     * incomingFiles[1] = settlement
     * incomingFiles[2] = bank
     *
     * Instead identify the files by their names.
     */

    const detected: SourceFiles = {
      ledger: null,
      settlements: null,
      bank: null,
    };

    const unknownFiles: File[] = [];
    const duplicateRoles: FileRole[] = [];

    for (const file of csvFiles) {
      const role = detectFileRole(file);

      if (!role) {
        unknownFiles.push(file);
        continue;
      }

      if (detected[role]) {
        duplicateRoles.push(role);
        continue;
      }

      detected[role] = file;
    }

    /*
     * Unknown filename.
     */
    if (unknownFiles.length > 0) {
      const names = unknownFiles
        .map((file) => file.name)
        .join(", ");

      setFiles({
        ledger: null,
        settlements: null,
        bank: null,
      });

      setError(
        `Could not identify the source type for: ${names}. Please use filenames containing "ledger", "settlement", or "bank".`,
      );

      return;
    }

    /*
     * Duplicate source type.
     */
    if (duplicateRoles.length > 0) {
      const roleNames = duplicateRoles
        .map((role) => {
          if (role === "ledger") return "Ledger";
          if (role === "settlements")
            return "Settlement";
          return "Bank";
        })
        .join(", ");

      setFiles({
        ledger: null,
        settlements: null,
        bank: null,
      });

      setError(
        `Multiple files were detected as ${roleNames}. Please select one Ledger, one Settlement, and one Bank CSV.`,
      );

      return;
    }

    /*
     * Missing source.
     */
    const missing: string[] = [];

    if (!detected.ledger) {
      missing.push("Ledger");
    }

    if (!detected.settlements) {
      missing.push("Settlement");
    }

    if (!detected.bank) {
      missing.push("Bank");
    }

    if (missing.length > 0) {
      setFiles(detected);

      setError(
        `Missing required source: ${missing.join(
          ", ",
        )}. Please select one Ledger, one Settlement, and one Bank CSV.`,
      );

      return;
    }

    /*
     * Everything correctly identified.
     */
    setFiles(detected);
    setError(null);
  }

  /* ------------------------------------------------------------------------ */
  /* SUBMIT / CREATE BATCH                                                    */
  /* ------------------------------------------------------------------------ */

  async function submit() {
    if (
      !files.ledger ||
      !files.settlements ||
      !files.bank
    ) {
      setError(
        "All 3 required files are needed before creating a batch.",
      );

      return;
    }

    setBusy("files");
    setError(null);
    setCreated(null);

    try {
      /*
       * IMPORTANT:
       *
       * Explicitly pass the correctly identified files.
       *
       * This guarantees that bank_statement_1000.csv
       * can never accidentally become the ledger file.
       */

      const batch = await api.createBatch({
        ledger: files.ledger,
        settlements: files.settlements,
        bank: files.bank,
      });

      setCreated(batch);

      onBatch(batch.batch_id);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  }

  /* ------------------------------------------------------------------------ */
  /* DEMO DATASET                                                             */
  /* ------------------------------------------------------------------------ */

  async function useFixture() {
    setBusy("fixture");
    setError(null);
    setCreated(null);

    try {
      const batch =
        await api.createFixtureBatch();

      setCreated(batch);

      onBatch(batch.batch_id);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  }

  /* ------------------------------------------------------------------------ */
  /* SOURCE STATUS CARD                                                       */
  /* ------------------------------------------------------------------------ */

  function SourceStatus({
    number,
    title,
    description,
    file,
  }: {
    number: string;
    title: string;
    description: string;
    file: File | null;
  }) {
    return (
      <div
        className={[
          "rounded-xl border p-4 transition-all duration-300",
          file
            ? "border-fin-600/30 bg-fin-100/40"
            : "border-border-hairline bg-surface",
        ].join(" ")}
      >
        <div className="flex items-start gap-3">
          <span className="font-mono text-xs font-semibold text-primary">
            {number}
          </span>

          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-semibold text-ink">
                {title}
              </p>

              {file ? (
                <span className="flex shrink-0 items-center gap-1 text-[11px] font-semibold text-fin-600">
                  <span className="h-1.5 w-1.5 rounded-full bg-fin-600" />
                  Ready
                </span>
              ) : (
                <span className="text-[11px] font-medium text-ink-subtle">
                  Required
                </span>
              )}
            </div>

            <p className="mt-1 text-xs leading-5 text-ink-2">
              {description}
            </p>

            {file ? (
              <div className="mt-3 flex items-center gap-2 rounded-lg border border-fin-600/20 bg-white/70 px-2.5 py-2">
                <Icon
                  name="check"
                  className="h-3.5 w-3.5 shrink-0 text-fin-600"
                />

                <span
                  className="truncate text-xs font-medium text-ink"
                  title={file.name}
                >
                  {file.name}
                </span>
              </div>
            ) : (
              <div className="mt-3 rounded-lg border border-dashed border-border-hairline px-2.5 py-2 text-xs text-ink-subtle">
                Waiting for file
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  /* ------------------------------------------------------------------------ */
  /* RENDER                                                                   */
  /* ------------------------------------------------------------------------ */

  return (
    <div className="space-y-4">
      <Section
        title="Load reconciliation sources"
        note="Upload all three source files together to create a reconciliation batch."
      >
        <div className="mb-5">
          <ProgressStepper
            steps={STEPS}
            current={step}
          />
        </div>

        {/* ------------------------------------------------------------------ */}
        {/* UPLOAD                                                              */}
        {/* ------------------------------------------------------------------ */}

        <FileUpload
          accept=".csv,text/csv"
          multiple
          showBorderBeam
          showFileList={false}
          title="Upload all 3 reconciliation files"
          description="Select or drop your Ledger, Settlement, and Bank CSV files together"
          browseLabel="Browse 3 CSV files"
          draggingLabel="Drop all 3 files here"
          onFilesAccepted={
            handleFilesAccepted
          }
        />

        {/* ------------------------------------------------------------------ */}
        {/* SOURCE STATUS                                                       */}
        {/* ------------------------------------------------------------------ */}

        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <SourceStatus
            number="01"
            title="Internal ledger"
            description="Your company's source-of-truth transaction records."
            file={files.ledger}
          />

          <SourceStatus
            number="02"
            title="Settlement report"
            description="Processor or payment-provider settlement records."
            file={files.settlements}
          />

          <SourceStatus
            number="03"
            title="Bank statement"
            description="Actual bank-side transaction movement."
            file={files.bank}
          />
        </div>

        {/* ------------------------------------------------------------------ */}
        {/* FILE COUNT                                                          */}
        {/* ------------------------------------------------------------------ */}

        <div
          className={[
            "mt-4 rounded-xl border px-4 py-3 transition-all duration-300",
            allSelected
              ? "border-fin-600/25 bg-fin-100/50"
              : selectedCount > 0
                ? "border-primary/20 bg-primary/5"
                : "border-border-hairline bg-muted/30",
          ].join(" ")}
        >
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-ink">
                {allSelected
                  ? "All required sources are ready"
                  : `${selectedCount} of 3 required files selected`}
              </p>

              <p className="mt-0.5 text-xs text-ink-2">
                {allSelected
                  ? "Ledger · Settlement · Bank"
                  : "You must provide all three CSV files to continue."}
              </p>
            </div>

            <div
              className={[
                "flex h-9 min-w-9 items-center justify-center rounded-full px-3 text-xs font-bold",
                allSelected
                  ? "bg-fin-600 text-white"
                  : "bg-muted text-ink-2",
              ].join(" ")}
            >
              {selectedCount}/3
            </div>
          </div>
        </div>

        {/* ------------------------------------------------------------------ */}
        {/* ERROR                                                               */}
        {/* ------------------------------------------------------------------ */}

        {error ? (
          <div
            className="mt-4 rounded-xl border border-primary/20 bg-primary/5 px-4 py-3.5 text-sm text-primary animate-fade-up"
            role="alert"
          >
            <div className="flex items-start gap-3">
              <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10">
                <Icon
                  name="alert"
                  className="h-4 w-4"
                />
              </span>

              <div>
                <p className="font-semibold">
                  Upload incomplete
                </p>

                <p className="mt-1 text-xs leading-5 text-primary/80">
                  {error instanceof ApiError
                    ? `[${error.code}] ${error.message}`
                    : String(error)}
                </p>
              </div>
            </div>
          </div>
        ) : null}

        {/* ------------------------------------------------------------------ */}
        {/* ACTIONS                                                             */}
        {/* ------------------------------------------------------------------ */}

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={submit}
            disabled={
              !allSelected ||
              busy !== null
            }
            className="btn btn-primary disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy === "files" ? (
              <>
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                Creating batch...
              </>
            ) : (
              <>
                <Icon
                  name="check"
                  className="h-4 w-4"
                />
                Validate & create batch
              </>
            )}
          </button>

          <span className="text-caption text-ink-muted">
            or use
          </span>

          <button
            type="button"
            onClick={useFixture}
            disabled={busy !== null}
            className="rounded-lg border border-border-hairline bg-surface-alt px-3 py-2 text-left transition hover:border-primary/40 hover:bg-brand-100 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Icon
              name="layers"
              className="h-4 w-4"
            />

            <span className="ml-1 inline-flex flex-col align-middle">
              <span className="text-sm font-semibold text-ink">
                Demo dataset
              </span>

              <span className="text-[11px] text-ink-2">
                100 records · seeded anomalies
              </span>
            </span>
          </button>
        </div>

        {/* ------------------------------------------------------------------ */}
        {/* PROCESSING PIPELINE                                                 */}
        {/* ------------------------------------------------------------------ */}

        {busy && (
          <div
            className="mt-4 overflow-hidden rounded-xl border border-primary/15 bg-primary/5 px-4 py-4"
            role="status"
            aria-live="polite"
          >
            <div className="mb-3 flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10">
                <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-primary/25 border-t-primary" />
              </span>

              <div>
                <p className="text-sm font-semibold text-ink">
                  Processing reconciliation sources
                </p>

                <p className="text-xs text-ink-2">
                  Please wait while the batch is prepared.
                </p>
              </div>
            </div>

            <div className="grid gap-2 sm:grid-cols-5">
              {PIPELINE.map(
                (label, index) => {
                  const complete =
                    index < pipelineStep;

                  const active =
                    index === pipelineStep;

                  return (
                    <div
                      key={label}
                      className={[
                        "relative rounded-lg border px-2.5 py-2 text-center transition-all duration-300",
                        complete
                          ? "border-fin-600/20 bg-fin-100/50"
                          : active
                            ? "border-primary/20 bg-primary/10"
                            : "border-border-hairline bg-background",
                      ].join(" ")}
                    >
                      <div className="flex items-center justify-center gap-1.5">
                        {complete ? (
                          <Icon
                            name="check"
                            className="h-3.5 w-3.5 text-fin-600"
                          />
                        ) : active ? (
                          <span className="h-3 w-3 animate-pulse rounded-full bg-primary" />
                        ) : (
                          <span className="h-2.5 w-2.5 rounded-full bg-border-hairline" />
                        )}

                        <span
                          className={[
                            "text-[10px] font-medium leading-4",
                            complete
                              ? "text-fin-600"
                              : active
                                ? "text-primary"
                                : "text-ink-subtle",
                          ].join(" ")}
                        >
                          {label}
                        </span>
                      </div>
                    </div>
                  );
                },
              )}
            </div>
          </div>
        )}
      </Section>

      {/* -------------------------------------------------------------------- */}
      {/* CREATED BATCH                                                        */}
      {/* -------------------------------------------------------------------- */}

      {created ? (
        <Section
          title="Batch ready"
          note={`${created.record_count} records · 3 sources · ready for reconciliation`}
          actions={
            <a
              href={`/api/v1/batches/${created.batch_id}/export?format=csv`}
              className="inline-flex items-center gap-1.5 rounded-sm border border-border-hairline px-3 py-1.5 text-caption font-medium transition hover:bg-surface-alt"
            >
              <Icon
                name="doc"
                className="h-3.5 w-3.5"
              />
              Export
            </a>
          }
        >
          <dl className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
            <div>
              <dt className="text-caption text-ink-muted">
                Batch ID
              </dt>

              <dd className="font-mono text-body text-ink">
                {created.batch_id}
              </dd>
            </div>

            <div>
              <dt className="text-caption text-ink-muted">
                Valid rows
              </dt>

              <dd className="tabular-nums text-body text-ink">
                {created.validation.valid_rows} /{" "}
                {created.validation.total_rows}
              </dd>
            </div>

            <div>
              <dt className="text-caption text-ink-muted">
                Ledger · Settlement · Bank
              </dt>

              <dd className="tabular-nums text-body text-ink">
                {created.counts.ledger_rows} ·{" "}
                {created.counts.settlement_rows} ·{" "}
                {created.counts.bank_rows}
              </dd>
            </div>

            <div>
              <dt className="text-caption text-ink-muted">
                Duplicates
              </dt>

              <dd className="tabular-nums text-body text-ink">
                {created.validation.duplicate_rows}
              </dd>
            </div>
          </dl>

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() =>
                onBatch(created.batch_id)
              }
              className="btn btn-primary"
            >
              <Icon
                name="check"
                className="h-4 w-4"
              />
              Run reconciliation
            </button>

            <button
              type="button"
              onClick={() =>
                onBatch(created.batch_id)
              }
              className="rounded-lg border border-line px-3 py-2 text-sm font-semibold transition hover:bg-muted"
            >
              View batch
            </button>
          </div>

          <ValidationList
            errors={created.validation.errors}
          />

          {created.validation.errors_truncated ? (
            <p className="mt-2 text-caption text-primary/75">
              Error list truncated in this response
              — the full list is stored with the
              batch.
            </p>
          ) : null}
        </Section>
      ) : null}
    </div>
  );
}