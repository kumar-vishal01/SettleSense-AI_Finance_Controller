import { useState } from "react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Icon } from "../components/icons";

const trend = [
  { month: "Jan", cash: 42, forecast: 46 }, { month: "Feb", cash: 51, forecast: 54 },
  { month: "Mar", cash: 48, forecast: 61 }, { month: "Apr", cash: 68, forecast: 70 },
  { month: "May", cash: 76, forecast: 81 }, { month: "Jun", cash: 91, forecast: 95 },
];

const features = [
  ["pulse", "Live financial overview", "See the whole money picture, from ledger to bank credit, in one calm workspace."],
  ["layers", "Evidence-first reconciliation", "Match every payment against settlement and bank evidence with clear exceptions."],
  ["chart", "Cash-flow forecasting", "Know what is booked today and what is only expected tomorrow."],
  ["alert", "Anomaly detection", "Surface duplicates, missing credits, and mismatches before they become surprises."],
  ["doc", "Audit-ready reporting", "Export traceable results with source IDs and integer-precise money."],
  ["spark", "Grounded AI assistance", "Ask questions in plain language. The assistant explains records, never rewrites them."],
];

const faqs = [
  ["Does the AI change financial records?", "No. The deterministic reconciliation engine is the source of truth. AI can explain results and retrieve evidence only."],
  ["What data does SettleSense reconcile?", "An internal payment ledger, a settlement report, and a bank statement, joined into one auditable decision."],
  ["Can I export the results?", "Yes. Reconciled results and exceptions can be exported as CSV or JSON with evidence identifiers included."],
  ["Is forecast cash booked cash?", "No. Forecast values are clearly labelled as projections and are kept separate from confirmed bank cash."],
];

export default function Landing({ onEnter }: { onEnter: (path: string) => void }) {
  const [openFaq, setOpenFaq] = useState<number | null>(null);
  return (
    <div className="min-h-screen overflow-hidden bg-[#f8fafc] text-ink">
      <header className="sticky top-0 z-30 border-b border-[#dce4ef] bg-[#f8fafc]/90 backdrop-blur-xl">
        <div className="mx-auto flex h-[72px] max-w-7xl items-center justify-between px-5 lg:px-8">
          <button onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })} className="flex items-center gap-2.5" aria-label="SettleSense home">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#0042e2] text-white shadow-[0_8px_18px_rgba(0,66,226,.2)]"><Icon name="layers" className="h-5 w-5" /></span>
            <span className="text-lg font-bold tracking-tight">SettleSense</span>
          </button>
          <nav className="hidden items-center gap-7 text-sm font-medium text-ink-2 md:flex">
            <a href="#features" className="hover:text-ink">Features</a><a href="#how" className="hover:text-ink">How it works</a><a href="#proof" className="hover:text-ink">Why SettleSense</a><a href="#faq" className="hover:text-ink">FAQ</a>
          </nav>
          <div className="flex items-center gap-2"><button onClick={() => onEnter("/login")} className="hidden rounded-lg px-3 py-2 text-sm font-semibold text-ink-2 hover:bg-white sm:block">Sign in</button><button onClick={() => onEnter("/signup")} className="btn btn-primary px-4 py-2 text-sm">Get started <Icon name="arrowright" className="h-4 w-4" /></button></div>
        </div>
      </header>

      <main>
        <section className="relative mx-auto grid max-w-7xl items-center gap-12 px-5 pb-20 pt-20 lg:grid-cols-[.9fr_1.1fr] lg:px-8 lg:pb-28 lg:pt-28">
          <div className="relative z-10 animate-fade-up">
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-[#b9d5c8] bg-[#eef9f3] px-3 py-1.5 text-xs font-bold uppercase tracking-[.12em] text-[#168a5a]"><span className="h-2 w-2 rounded-full bg-[#168a5a]" /> Finance operations, made legible</div>
            <h1 className="max-w-2xl text-5xl font-bold leading-[1.02] tracking-[-0.04em] text-[#07152f] sm:text-7xl">Close the books with <span className="text-[#0042e2]">evidence.</span></h1>
            <p className="mt-6 max-w-xl text-lg leading-8 text-ink-2">SettleSense turns payments, settlements, and bank credits into one reliable control loop, so your team knows what happened and what needs attention.</p>
            <div className="mt-8 flex flex-wrap items-center gap-3"><button onClick={() => onEnter("/signup")} className="btn btn-primary px-5 py-3">Start with a demo batch <Icon name="arrowright" className="h-4 w-4" /></button><a href="#how" className="inline-flex items-center gap-2 px-3 py-3 text-sm font-semibold text-ink-2 hover:text-ink">See how it works <Icon name="chevron" className="h-4 w-4" /></a></div>
            <div className="mt-10 flex flex-wrap gap-x-7 gap-y-2 text-xs font-medium text-ink-2"><span className="flex items-center gap-1.5"><Icon name="check" className="h-4 w-4 text-[#168a5a]" /> No spreadsheet glue</span><span className="flex items-center gap-1.5"><Icon name="check" className="h-4 w-4 text-[#168a5a]" /> Every exception visible</span></div>
          </div>
          <div className="relative animate-scale-in lg:pl-8">
            <div className="absolute -inset-8 bg-[radial-gradient(circle_at_center,rgba(0,66,226,.12),transparent_62%)]" aria-hidden="true" />
            <div className="relative rounded-2xl border border-[#d7e0ed] bg-white p-4 shadow-[0_24px_70px_rgba(16,33,63,.12)] sm:p-6">
              <div className="flex items-center justify-between border-b border-[#edf1f6] pb-4"><div><p className="text-xs font-bold uppercase tracking-[.12em] text-ink-2">Control room</p><p className="mt-1 text-lg font-bold">Cash position</p></div><span className="rounded-full bg-[#eef9f3] px-2.5 py-1 text-[11px] font-bold text-[#168a5a]">Engine healthy</span></div>
              <div className="mt-4 grid grid-cols-3 gap-2"><div className="rounded-xl bg-[#f5f8fc] p-3"><p className="text-[10px] uppercase text-ink-2">Confirmed</p><p className="mt-1 text-xl font-bold">₹1.68Cr</p></div><div className="rounded-xl bg-[#f5f8fc] p-3"><p className="text-[10px] uppercase text-ink-2">Pending</p><p className="mt-1 text-xl font-bold">₹8.4L</p></div><div className="rounded-xl bg-[#fff7e8] p-3"><p className="text-[10px] uppercase text-ink-2">Review</p><p className="mt-1 text-xl font-bold text-[#c77700]">13</p></div></div>
              <div className="mt-5 h-48"><ResponsiveContainer width="100%" height="100%"><AreaChart data={trend} margin={{ top: 8, right: 4, left: -25, bottom: 0 }}><defs><linearGradient id="landingCash" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#0042e2" stopOpacity=".2" /><stop offset="1" stopColor="#0042e2" stopOpacity="0" /></linearGradient></defs><XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: "#63708a" }} /><YAxis hide /><Tooltip /><Area type="monotone" dataKey="cash" stroke="#0042e2" strokeWidth={2.5} fill="url(#landingCash)" animationDuration={1000} /><Area type="monotone" dataKey="forecast" stroke="#168a5a" strokeWidth={2} strokeDasharray="5 4" fill="none" animationDuration={1200} /></AreaChart></ResponsiveContainer></div>
              <div className="flex items-center gap-4 border-t border-[#edf1f6] pt-3 text-[11px] text-ink-2"><span className="flex items-center gap-1.5"><i className="h-2 w-2 rounded-full bg-[#0042e2]" /> Confirmed cash</span><span className="flex items-center gap-1.5"><i className="h-2 w-2 rounded-full bg-[#168a5a]" /> Forecast</span></div>
            </div>
          </div>
        </section>

        <section id="features" className="border-y border-[#e1e7f0] bg-white px-5 py-20 lg:px-8"><div className="mx-auto max-w-7xl"><div className="max-w-xl"><p className="text-xs font-bold uppercase tracking-[.15em] text-[#0042e2]">One source of truth</p><h2 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">Finance control that holds up under questions.</h2></div><div className="mt-10 grid gap-px overflow-hidden rounded-2xl border border-[#dce4ef] bg-[#dce4ef] sm:grid-cols-2 lg:grid-cols-3">{features.map(([icon, title, text]) => <article key={title} className="bg-white p-7 transition hover:bg-[#f8fbff]"><span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#edf2ff] text-[#0042e2]"><Icon name={icon} className="h-5 w-5" /></span><h3 className="mt-5 font-bold">{title}</h3><p className="mt-2 text-sm leading-6 text-ink-2">{text}</p></article>)}</div></div></section>

        <section id="how" className="mx-auto max-w-7xl px-5 py-20 lg:px-8"><div className="grid gap-12 lg:grid-cols-[.7fr_1.3fr]"><div><p className="text-xs font-bold uppercase tracking-[.15em] text-[#168a5a]">How it works</p><h2 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">From raw files to a clear decision.</h2></div><div className="grid gap-8 sm:grid-cols-3">{[["01", "Connect", "Bring your ledger, settlement report, and bank statement."], ["02", "Reconcile", "The deterministic engine matches records and preserves evidence."], ["03", "Act", "Resolve exceptions, forecast cash, and export the audit trail."]].map(([n, t, d]) => <div key={n} className="border-t-2 border-[#0042e2] pt-4"><span className="font-mono text-sm text-[#0042e2]">{n}</span><h3 className="mt-8 font-bold">{t}</h3><p className="mt-2 text-sm leading-6 text-ink-2">{d}</p></div>)}</div></div></section>

        <section id="proof" className="bg-[#07152f] px-5 py-20 text-white lg:px-8"><div className="mx-auto grid max-w-7xl gap-10 sm:grid-cols-3"><div><p className="text-4xl font-bold">100%</p><p className="mt-2 text-sm text-white/60">of decisions tied to evidence</p></div><div><p className="text-4xl font-bold">13</p><p className="mt-2 text-sm text-white/60">anomaly scenarios tested in demo data</p></div><div><p className="text-4xl font-bold">0</p><p className="mt-2 text-sm text-white/60">financial records changed by AI</p></div></div></section>

        <section id="faq" className="mx-auto max-w-3xl px-5 py-20 lg:px-8"><p className="text-center text-xs font-bold uppercase tracking-[.15em] text-[#0042e2]">Questions, answered</p><h2 className="mt-3 text-center text-3xl font-bold tracking-tight">Built for scrutiny.</h2><div className="mt-10 divide-y divide-[#dce4ef] border-y border-[#dce4ef]">{faqs.map(([q, a], i) => <div key={q}><button onClick={() => setOpenFaq(openFaq === i ? null : i)} className="flex w-full items-center justify-between gap-4 py-5 text-left font-semibold"><span>{q}</span><Icon name="chevron" className={`h-4 w-4 transition-transform ${openFaq === i ? "rotate-90" : ""}`} /></button>{openFaq === i && <p className="pb-5 pr-8 text-sm leading-6 text-ink-2 animate-fade-up">{a}</p>}</div>)}</div></section>
        <section className="bg-[#eaf0ff] px-5 py-16 text-center"><h2 className="text-3xl font-bold tracking-tight">Make your next close less mysterious.</h2><p className="mx-auto mt-3 max-w-lg text-ink-2">Load the seeded demo batch and see the full control loop in under a minute.</p><button onClick={() => onEnter("/signup")} className="btn btn-primary mt-7 px-5 py-3">Open the control room <Icon name="arrowright" className="h-4 w-4" /></button></section>
      </main>
      <footer className="border-t border-[#dce4ef] bg-white px-5 py-8 lg:px-8"><div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 text-sm text-ink-2"><span className="font-bold text-ink">SettleSense</span><span>Deterministic engine · grounded AI · auditable cash</span><span>© 2026 SettleSense</span></div></footer>
    </div>
  );
}