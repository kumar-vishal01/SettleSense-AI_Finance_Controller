import { useRef, useState } from "react";
import { api } from "../api";
import type { AiAnswer } from "../types";
import { ErrorState, Section, Spinner } from "../components/ui";
import { Icon } from "../components/icons";

const SUGGESTIONS = [
  "Which unresolved exception has the highest monetary impact?",
  "Summarize the reconciliation results",
  "Why is actual cash lower than expected?",
  "Show missing bank credits",
  "Trace payment pay_069",
];

type Turn = { question: string; answer: AiAnswer };

const TOOL_STEPS = [
  "Inspecting reconciliation records…",
  "Checking exception exposure…",
  "Preparing evidence-backed answer…",
];

export default function Ai({ batchId, onOpenTrace }: {
  batchId: string; onOpenTrace: (paymentId: string) => void;
}) {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<Turn[]>([]);
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(0);
  const [error, setError] = useState<unknown>(null);
  const [copied, setCopied] = useState<number | null>(null);
  const timers = useRef<number[]>([]);

  function ask(q: string) {
    const text = q.trim();
    if (!text) return;
    setQuestion(text); setLoading(true); setError(null); setStep(0);
    timers.current.forEach(clearInterval); timers.current = [];
    const iv = window.setInterval(() => setStep(s => Math.min(s + 1, TOOL_STEPS.length - 1)), 350);
    timers.current.push(iv);
    api.ask(batchId, text)
      .then(answer => setHistory(h => [...h, { question: text, answer }]))
      .catch(e => setError(e))
      .finally(() => { clearInterval(iv); setLoading(false); });
  }

  function copy(text: string, idx: number) {
    navigator.clipboard?.writeText(text).then(() => {
      setCopied(idx);
      setTimeout(() => setCopied(null), 1600);
    }).catch(() => {});
  }

  return (
    <Section title="AI finance assistant"
      note="answers grounded in reconciliation records via read-only tools">
      <div className="flex flex-wrap gap-2">
        {SUGGESTIONS.map(s => (
          <button key={s} onClick={() => ask(s)}
            className="rounded-full border border-line bg-white px-3 py-1.5 text-xs font-medium text-ink-2
              transition hover:border-ai-500/40 hover:text-ink">
            {s}
          </button>
        ))}
      </div>

      <div className="mt-4 space-y-4" aria-live="polite">
        {history.map((turn, i) => (
          <div key={i} className="space-y-2 anim-fade-up">
            <div className="flex justify-end">
              <p className="max-w-lg rounded-xl rounded-br-sm bg-brand-600 px-3.5 py-2 text-sm text-white">
                {turn.question}
              </p>
            </div>
            <div className="rounded-xl border border-line bg-white p-3.5">
              <div className="flex flex-wrap items-center gap-2 text-[11px]">
                <span className="inline-flex items-center gap-1 rounded-full border border-ai-500/30 bg-white px-2 py-0.5 font-semibold text-ai-500">
                  <Icon name="spark" className="h-3 w-3" /> {turn.answer.provider === "none"
                    ? "deterministic engine" : turn.answer.provider}
                </span>
                {turn.answer.tools_used.map(t => (
                  <span key={t} className="rounded-full bg-muted px-2 py-0.5 text-ink-2">tool: {t}</span>
                ))}
                {turn.answer.fallback && (
                  <span className="rounded-full border border-warn-600/30 bg-warn-100 px-2 py-0.5 text-warn-600">
                    fallback served
                  </span>
                )}
                {turn.answer.requires_review && (
                  <span className="rounded-full border border-warn-600/30 bg-warn-100 px-2 py-0.5 font-semibold text-warn-600">
                    needs human review
                  </span>
                )}
                <button onClick={() => copy(turn.answer.answer, i)}
                  className="ml-auto inline-flex items-center gap-1 rounded border border-line px-2 py-0.5 text-ink-2 hover:bg-muted"
                  aria-label="Copy answer">
                  <Icon name="copy" className="h-3 w-3" />
                  {copied === i ? "Copied" : "Copy"}
                </button>
              </div>
              <p className="mt-2.5 whitespace-pre-wrap text-sm leading-relaxed">{turn.answer.answer}</p>
              {turn.answer.record_ids.length > 0 && (
                <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                  <span className="text-[11px] text-ink-2">Evidence:</span>
                  {turn.answer.record_ids.map(id => (
                    <button key={id} onClick={() => onOpenTrace(id)}
                      className="rounded border border-brand-500/30 bg-brand-100 px-2 py-0.5 font-mono text-[11px] text-brand-600 hover:bg-brand-100/70"
                      title="Open in trace">
                      {id}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-2 text-sm text-ink-2" role="status">
            <span className="h-2 w-2 animate-pulse rounded-full bg-ai-500" aria-hidden="true" />
            {TOOL_STEPS[step]}
          </div>
        )}
        {error ? <ErrorState error={error} /> : null}
        {!loading && history.length === 0 && !error && (
          <p className="text-sm text-ink-2">
            Ask a finance question — every answer cites record evidence from this batch.
          </p>
        )}
      </div>

      <form onSubmit={e => { e.preventDefault(); ask(question); }} className="mt-4 flex gap-2">
        <input value={question} onChange={e => setQuestion(e.target.value)}
          placeholder="Ask about this batch — amounts, exceptions, cash…"
          className="flex-1 rounded-lg border border-line px-3.5 py-2.5 text-sm"
          aria-label="Question for the finance assistant" />
        <button type="submit" disabled={loading || !question.trim()}
          className="btn btn-primary disabled:opacity-40">
          Ask
        </button>
      </form>
      {loading && <div className="mt-2"><Spinner /></div>}
    </Section>
  );
}
