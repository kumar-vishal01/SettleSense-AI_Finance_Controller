import { useCallback, useEffect, useState } from "react";
import Upload from "./pages/Upload";
import Overview from "./pages/Overview";
import Results from "./pages/Results";
import Exceptions from "./pages/Exceptions";
import Trace from "./pages/Trace";
import Cash from "./pages/Cash";
import Ai from "./pages/Ai";
import Landing from "./pages/Landing";
import Auth from "./pages/Auth";
import { api } from "./api";
import { Icon } from "./components/icons";
import { EngineStatus, Toasts, type ToastMsg } from "./components/ui";

type Page = "overview" | "upload" | "results" | "exceptions" | "trace" | "cash" | "ai";

function pageFromPath(pathname: string): Page {
  const path = pathname.replace(/\/$/, "");

  // Public / legacy aliases
  if (path === "/transactions") return "results";
  if (path === "/reports") return "cash";
  if (path === "/ai-assistant") return "ai";

  // Actual workspace routes
  if (path === "/workspace/overview") return "overview";
  if (path === "/workspace/upload") return "upload";
  if (path === "/workspace/reconciliation") return "results";
  if (path === "/workspace/exceptions") return "exceptions";
  if (path === "/workspace/trace") return "trace";
  if (path === "/workspace/cash-position") return "cash";
  if (path === "/workspace/ai-assistant") return "ai";

  // Legacy direct page names, if needed
  const page = path.split("/").pop() as Page;

  return [
    "overview",
    "upload",
    "results",
    "exceptions",
    "trace",
    "cash",
    "ai",
  ].includes(page)
    ? page
    : "overview";
}
function pathForPage(page: Page): string {
  const workspacePage: Record<Page, string> = {
    overview: "overview", upload: "upload", results: "reconciliation",
    exceptions: "exceptions", trace: "trace", cash: "cash-position", ai: "ai-assistant",
  };
  return `/workspace/${workspacePage[page]}`;
}

const NAV: { id: Page; label: string; icon: string }[] = [
  { id: "overview", label: "Overview", icon: "pulse" },
  { id: "upload", label: "Upload", icon: "upload" },
  { id: "results", label: "Reconciliation", icon: "layers" },
  { id: "exceptions", label: "Exceptions", icon: "alert" },
  { id: "cash", label: "Cash Position", icon: "bank" },
  { id: "trace", label: "Trace", icon: "search" },
  { id: "ai", label: "AI Assistant", icon: "spark" },
];

function TopNav({ page, onNavigate, health, batchId, mobile = false, onClose }: {
  page: Page;
  onNavigate: (page: Page) => void;
  health: "checking" | "up" | "down";
  batchId: string;
  mobile?: boolean;
  onClose?: () => void;
}) {
  return (
    <nav className={mobile ? "fixed inset-0 z-50 flex flex-col bg-white p-5 animate-fade-in" : "sticky top-0 z-30 border-b border-border-hairline bg-white/95 backdrop-blur-xl"} aria-label="Primary navigation">
      <div className={mobile ? "flex items-center justify-between" : "mx-auto flex min-h-[68px] max-w-[1480px] items-center gap-8 px-5 lg:px-8"}>
        <button onClick={() => onNavigate("overview")} className="flex items-center gap-2.5 text-left">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-white shadow-[0_4px_12px_rgba(0,66,226,0.2)]"><Icon name="layers" className="h-5 w-5" /></span>
          <span><span className="block text-[17px] font-bold tracking-tight text-ink">SettleSense</span><span className="hidden text-[10px] font-medium uppercase tracking-[0.12em] text-ink-muted sm:block">AI Finance Controller</span></span>
        </button>
        {!mobile && <button onClick={onClose} className="ml-auto rounded-lg border border-line p-2 text-ink-2 lg:hidden" aria-label="Open navigation"><Icon name="menu" /></button>}
        {mobile && <button onClick={onClose} className="rounded-lg border border-line p-2 text-ink-2" aria-label="Close navigation"><Icon name="x" /></button>}
        {!mobile && <div className="hidden flex-1 items-center gap-1 lg:flex">
        {NAV.map((item, idx) => {
          const active = page === item.id;
          return (
            <button
              key={item.id}
              onClick={() => {
                onNavigate(item.id);
                onClose?.();
              }}
              className={[
                "group flex items-center gap-2 border-b-2 px-3 py-2 text-[13px] font-semibold transition-all duration-200",
                active
                  ? "border-primary text-ink"
                  : "border-transparent text-ink-muted hover:border-border-hairline hover:text-ink",
              ].join(" ")}
              style={{ animationDelay: `${idx * 80}ms` }}
              aria-current={active ? "page" : undefined}
            >
              <span>{item.label}</span>
            </button>
          );
        })}
      </div>}
        {mobile && <div className="mt-8 grid gap-2">{NAV.map(item => <button key={item.id} onClick={() => { onNavigate(item.id); onClose?.(); }} className={`flex items-center gap-3 rounded-xl px-4 py-3 text-left text-base font-semibold ${page === item.id ? "bg-brand-100 text-brand-600" : "text-ink-2 hover:bg-muted"}`}><Icon name={item.icon} className="h-5 w-5" />{item.label}</button>)}</div>}
        {!mobile && page !== "overview" && <div className="ml-auto flex items-center gap-4"><EngineStatus health={health} />{batchId && <span className="hidden text-xs text-ink-2 xl:block" title={batchId}>Batch <strong className="text-ink">synthetic-v2</strong></span>}<button onClick={() => onNavigate("upload")} className="btn btn-primary whitespace-nowrap px-4 py-2 text-sm font-semibold shadow-[0_3px_10px_rgba(0,66,226,0.16)]"><span className="text-lg leading-none" aria-hidden="true">+</span> New batch</button></div>}
      </div>
      {mobile && <div className="mt-auto border-t border-line pt-5"><EngineStatus health={health} /><p className="mt-3 text-sm text-ink-2">{batchId ? "Current batch: synthetic-v2" : "No batch loaded"}</p></div>}
    </nav>
  );
}

function OverviewLanding({ onUpload, onFixture }: { onUpload: () => void; onFixture: () => void }) {
  return (
    <div className="card border-2 border-dashed border-border-hairline p-10 text-center animate-scale-in sm:p-16">
      <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-sm bg-primary/20 text-primary">
        <Icon name="layers" className="h-5 w-5" />
      </span>
      <p className="mt-4 text-title-lg font-semibold text-ink">No batch loaded</p>
      <p className="mx-auto mt-1 max-w-md text-body text-ink-muted">
        Upload three CSVs or load the synthetic fixture to begin reconciliation.
      </p>
      <div className="mt-5 flex flex-wrap justify-center gap-2"><button onClick={onUpload} className="btn btn-primary">Go to upload</button><button onClick={onFixture} className="rounded-lg border border-line bg-white px-3 py-2 text-sm font-semibold hover:bg-muted">Load synthetic fixture</button></div>
    </div>
  );
}

export default function App() {
  const [route, setRoute] = useState(() => window.location.pathname);
  const [page, setPage] = useState<Page>(() => pageFromPath(window.location.pathname));
  const [batchId, setBatchId] = useState(() => window.localStorage.getItem("settlesense.batchId") ?? "");
  const [tracePaymentId, setTracePaymentId] = useState("pay_010");
  const [health, setHealth] = useState<"checking" | "up" | "down">("checking");
  const [toasts, setToasts] = useState<ToastMsg[]>([]);
  const [navOpen, setNavOpen] = useState(false);

  const toast = useCallback((text: string, tone: ToastMsg["tone"] = "info") => {
    const id = Date.now() + Math.random();
    setToasts((ts) => [...ts, { id, text, tone }]);
    setTimeout(() => setToasts((ts) => ts.filter((t) => t.id !== id)), 4200);
  }, []);

  useEffect(() => {
    const onPopState = () => {
      setRoute(window.location.pathname);
      setPage(pageFromPath(window.location.pathname));
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    fetch("/health")
      .then((r) => {
        if (!r.ok) throw new Error(String(r.status));
        return r.json();
      })
      .then(() => setHealth("up"))
      .catch(() => setHealth("down"));
  }, []);

  async function selectBatchFromFixture() {
    try {
      const batch = await api.createFixtureBatch();
      await selectBatch(batch.batch_id);
    } catch (err) {
      toast(err instanceof Error ? `Fixture load failed: ${err.message}` : "Fixture load failed", "bad");
    }
  }

  async function selectBatch(id: string) {
    setBatchId(id);
    window.localStorage.setItem("settlesense.batchId", id);
    try {
      const result = await api.reconcile(id);
      window.localStorage.setItem("settlesense.batchRecords", String(result.result_count));
      window.localStorage.setItem("settlesense.lastReconciled", "Just now");
      toast("Reconciliation complete — results ready", "good");
    } catch (err) {
      toast(
        err instanceof Error ? `Reconciliation failed: ${err.message}` : "Reconciliation failed",
        "bad",
      );
    }
    const nextPath = pathForPage("overview");
    window.history.pushState({}, "", nextPath);
    setRoute(nextPath);
    setPage("overview");
  }

  const go = (nextPage: Page) => {
  const nextPath = pathForPage(nextPage);

  window.history.pushState({}, "", nextPath);

  setRoute(nextPath);
  setPage(nextPage);
  setNavOpen(false);
};

  const openRoute = (path: string) => {
    window.history.pushState({}, "", path);
    setRoute(path);
    setPage(pageFromPath(path));
  };

  const openTrace = (paymentId: string) => {
    setTracePaymentId(paymentId);
    go("trace");
  };

  if (route === "/") return <Landing onEnter={openRoute} />;
  if (route === "/login" || route === "/signup") {
    return <Auth mode={route === "/signup" ? "signup" : "login"}
      onBack={() => openRoute("/")} onContinue={() => openRoute("/workspace/upload")} />;
  }

  return (
    <div className="min-h-screen bg-surface text-ink">
      <TopNav page={page} onNavigate={go} health={health} batchId={batchId} onClose={() => setNavOpen(true)} />
      {navOpen && <TopNav page={page} onNavigate={go} health={health} batchId={batchId} mobile onClose={() => setNavOpen(false)} />}
      <div className="flex min-h-[calc(100vh-68px)] min-w-0 flex-col">
          <header className="border-b border-border-hairline bg-surface">
            <div className="mx-auto flex w-full max-w-[1480px] flex-wrap items-center gap-x-7 gap-y-3 px-4 py-4 sm:px-6 lg:px-8">
              <div className="min-w-[220px] flex-1">
                <h1 className={`truncate font-bold leading-tight tracking-[-0.02em] text-ink ${page === "overview" ? "text-[40px]" : "text-title-lg"}`}>{NAV.find((n) => n.id === page)?.label ?? "SettleSense"}</h1>
              </div>
              <button onClick={() => go("upload")} className="btn btn-primary ml-auto whitespace-nowrap px-4 py-2 text-sm font-semibold shadow-[0_3px_10px_rgba(0,66,226,0.16)]"><span className="text-lg leading-none" aria-hidden="true">+</span>New batch</button>
            </div>
          </header>

          <main
            className="mx-auto w-full max-w-[1480px] flex-1 px-4 py-5 sm:px-6 sm:py-6 lg:px-8 animate-fade-up"
            key={page}
          >
            {!batchId && page === "overview" ? (
              <OverviewLanding onUpload={() => go("upload")} onFixture={() => { void selectBatchFromFixture(); }} />
            ) : !batchId && page !== "upload" ? (
              <div className="card border-2 border-dashed border-border-hairline text-center p-10 sm:p-16 animate-scale-in">
                <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-sm bg-primary/20 text-primary">
                  <Icon name="layers" className="h-5 w-5" />
                </span>
                <p className="mt-4 text-title-lg font-semibold text-ink">No batch loaded</p>
                <p className="mx-auto mt-1 max-w-md text-body text-ink-muted">
                  Upload three CSVs or load the synthetic fixture to begin reconciliation.
                </p>
                <button onClick={() => go("upload")} className="btn btn-primary mt-5">
                  Go to upload
                </button>
              </div>
            ) : (
              <>
                {page === "upload" && <Upload onBatch={selectBatch} />}
                {page === "overview" && batchId && (
                  <Overview batchId={batchId} onRerun={() => selectBatch(batchId)} onOpenTrace={openTrace} onOpenExceptions={() => go("exceptions")} />
                )}
                {page === "results" && batchId && (
                  <Results batchId={batchId} onOpenTrace={openTrace} />
                )}
                {page === "exceptions" && batchId && <Exceptions batchId={batchId} />}
                {page === "trace" && batchId && (
                  <Trace batchId={batchId} initialPaymentId={tracePaymentId} />
                )}
                {page === "cash" && batchId && <Cash batchId={batchId} />}
                {page === "ai" && batchId && <Ai batchId={batchId} onOpenTrace={openTrace} />}
              </>
            )}
          </main>

          <footer className="footer">
            <div className="mx-auto max-w-[1480px] px-4 py-3 sm:px-6 lg:px-8">
              <p className="text-caption text-ink-muted">
                Deterministic engine · AI explains, never decides · Paise-integer money · Every exception visible with evidence.
              </p>
            </div>
          </footer>
      </div>

      <Toasts items={toasts} onDismiss={(id) => setToasts((ts) => ts.filter((t) => t.id !== id))} />
    </div>
  );
}
