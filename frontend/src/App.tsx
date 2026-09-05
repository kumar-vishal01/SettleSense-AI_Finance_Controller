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
import { Toasts, type ToastMsg } from "./components/ui";

type Page =
  | "overview"
  | "upload"
  | "results"
  | "exceptions"
  | "trace"
  | "cash"
  | "ai";

/* -------------------------------------------------------------------------- */
/* ROUTING                                                                    */
/* -------------------------------------------------------------------------- */

function pageFromPath(pathname: string): Page {
  const path = pathname.replace(/\/$/, "");

  // Public / legacy aliases
  if (path === "/transactions") return "results";
  if (path === "/reports") return "cash";
  if (path === "/ai-assistant") return "ai";

  // Workspace routes
  if (path === "/workspace/overview") return "overview";
  if (path === "/workspace/upload") return "upload";
  if (path === "/workspace/reconciliation") return "results";
  if (path === "/workspace/exceptions") return "exceptions";
  if (path === "/workspace/trace") return "trace";
  if (path === "/workspace/cash-position") return "cash";
  if (path === "/workspace/ai-assistant") return "ai";

  // Legacy direct page names
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
    overview: "overview",
    upload: "upload",
    results: "reconciliation",
    exceptions: "exceptions",
    trace: "trace",
    cash: "cash-position",
    ai: "ai-assistant",
  };

  return `/workspace/${workspacePage[page]}`;
}

/* -------------------------------------------------------------------------- */
/* NAVIGATION                                                                  */
/* -------------------------------------------------------------------------- */

const NAV: {
  id: Page;
  label: string;
  icon: string;
}[] = [
  {
    id: "overview",
    label: "Overview",
    icon: "pulse",
  },
  {
    id: "upload",
    label: "Upload",
    icon: "upload",
  },
  {
    id: "results",
    label: "Reconciliation",
    icon: "layers",
  },
  {
    id: "exceptions",
    label: "Exceptions",
    icon: "alert",
  },
  {
    id: "cash",
    label: "Cash Position",
    icon: "bank",
  },
  {
    id: "trace",
    label: "Trace",
    icon: "search",
  },
  {
    id: "ai",
    label: "AI Assistant",
    icon: "spark",
  },
];

/* -------------------------------------------------------------------------- */
/* TOP NAVIGATION                                                              */
/* -------------------------------------------------------------------------- */

function TopNav({
  page,
  onNavigate,
  mobile = false,
  onMenuOpen,
  onClose,
}: {
  page: Page;
  onNavigate: (page: Page) => void;
  mobile?: boolean;
  onMenuOpen?: () => void;
  onClose?: () => void;
}) {
  return (
    <nav
      className={
        mobile
          ? "fixed inset-0 z-50 flex flex-col bg-white p-5 animate-fade-in"
          : "sticky top-0 z-30 border-b border-border-hairline bg-white/95 backdrop-blur-xl"
      }
      aria-label="Primary navigation"
    >
      <div
        className={
          mobile
            ? "flex items-center justify-between"
            : "mx-auto flex min-h-[68px] max-w-[1480px] items-center gap-6 px-5 lg:px-8"
        }
      >
        {/* ---------------------------------------------------------------- */}
        {/* LOGO                                                             */}
        {/* ---------------------------------------------------------------- */}

            <button
      type="button"
      onClick={() => {
        window.history.pushState({}, "", "/");
        window.dispatchEvent(new PopStateEvent("popstate"));
      }}
      className="flex shrink-0 items-center gap-2.5 text-left"
      aria-label="Go to landing page"
    >
      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-white shadow-[0_4px_12px_rgba(0,66,226,0.2)]">
        <Icon name="layers" className="h-5 w-5" />
      </span>

      <span>
        <span className="block text-[17px] font-bold tracking-tight text-ink">
          SettleSense
        </span>

        <span className="hidden text-[10px] font-medium uppercase tracking-[0.12em] text-ink-muted sm:block">
          AI Finance Controller
        </span>
      </span>
    </button>

        {/* ---------------------------------------------------------------- */}
        {/* MOBILE MENU BUTTON                                               */}
        {/* ---------------------------------------------------------------- */}

        {!mobile && (
          <button
            type="button"
            onClick={onMenuOpen}
            className="ml-auto rounded-lg border border-line p-2 text-ink-2 lg:hidden"
            aria-label="Open navigation"
          >
            <Icon name="menu" />
          </button>
        )}

        {/* ---------------------------------------------------------------- */}
        {/* MOBILE CLOSE BUTTON                                              */}
        {/* ---------------------------------------------------------------- */}

        {mobile && (
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-line p-2 text-ink-2"
            aria-label="Close navigation"
          >
            <Icon name="x" />
          </button>
        )}

        {/* ---------------------------------------------------------------- */}
        {/* DESKTOP NAVIGATION                                               */}
        {/* ---------------------------------------------------------------- */}

        {!mobile && (
          <div className="hidden min-w-0 flex-1 items-center gap-1 lg:flex">
            {NAV.map((item) => {
              const active = page === item.id;

              return (
                <button
                  type="button"
                  key={item.id}
                  onClick={() => {
                    // Direct navigation — no intermediate menu.
                    onNavigate(item.id);
                  }}
                  className={[
                    "group flex shrink-0 items-center gap-2 border-b-2 px-3 py-2 text-[13px] font-semibold transition-all duration-200",
                    active
                      ? "border-primary text-ink"
                      : "border-transparent text-ink-muted hover:border-border-hairline hover:text-ink",
                  ].join(" ")}
                  aria-current={active ? "page" : undefined}
                >
                  <Icon
                    name={item.icon}
                    className="h-4 w-4"
                  />

                  <span>{item.label}</span>
                </button>
              );
            })}
          </div>
        )}

        {/* ---------------------------------------------------------------- */}
        {/* NEW BATCH BUTTON                                                 */}
        {/* ---------------------------------------------------------------- */}

        {!mobile && (
          <div className="ml-auto flex shrink-0 items-center">
            <button
              type="button"
              onClick={() => onNavigate("upload")}
              className="btn btn-primary whitespace-nowrap px-4 py-2 text-sm font-semibold shadow-[0_3px_10px_rgba(0,66,226,0.16)]"
            >
              <span
                className="text-lg leading-none"
                aria-hidden="true"
              >
                +
              </span>

              <span>New batch</span>
            </button>
          </div>
        )}
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* MOBILE NAVIGATION                                                  */}
      {/* ------------------------------------------------------------------ */}

      {mobile && (
        <div className="mt-8 grid gap-2">
          {NAV.map((item) => {
            const active = page === item.id;

            return (
              <button
                type="button"
                key={item.id}
                onClick={() => {
                  onNavigate(item.id);
                  onClose?.();
                }}
                className={[
                  "flex items-center gap-3 rounded-xl px-4 py-3 text-left text-base font-semibold transition-colors",
                  active
                    ? "bg-brand-100 text-brand-600"
                    : "text-ink-2 hover:bg-muted",
                ].join(" ")}
              >
                <Icon
                  name={item.icon}
                  className="h-5 w-5"
                />

                {item.label}
              </button>
            );
          })}
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* MOBILE NEW BATCH                                                   */}
      {/* ------------------------------------------------------------------ */}

      {mobile && (
        <div className="mt-auto border-t border-line pt-5">
          <button
            type="button"
            onClick={() => {
              onNavigate("upload");
              onClose?.();
            }}
            className="btn btn-primary w-full justify-center"
          >
            <span
              className="text-lg leading-none"
              aria-hidden="true"
            >
              +
            </span>

            New batch
          </button>
        </div>
      )}
    </nav>
  );
}

/* -------------------------------------------------------------------------- */
/* OVERVIEW EMPTY STATE                                                       */
/* -------------------------------------------------------------------------- */

function OverviewLanding({
  onUpload,
  onFixture,
}: {
  onUpload: () => void;
  onFixture: () => void;
}) {
  return (
    <div className="card border-2 border-dashed border-border-hairline p-10 text-center animate-scale-in sm:p-16">
      <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-sm bg-primary/20 text-primary">
        <Icon
          name="layers"
          className="h-5 w-5"
        />
      </span>

      <p className="mt-4 text-title-lg font-semibold text-ink">
        No batch loaded
      </p>

      <p className="mx-auto mt-1 max-w-md text-body text-ink-muted">
        Upload three CSVs or load the synthetic fixture
        to begin reconciliation.
      </p>

      <div className="mt-5 flex flex-wrap justify-center gap-2">
        <button
          type="button"
          onClick={onUpload}
          className="btn btn-primary"
        >
          Go to upload
        </button>

        <button
          type="button"
          onClick={onFixture}
          className="rounded-lg border border-line bg-white px-3 py-2 text-sm font-semibold hover:bg-muted"
        >
          Load synthetic fixture
        </button>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* MAIN APP                                                                    */
/* -------------------------------------------------------------------------- */

export default function App() {
  const [route, setRoute] = useState(
    () => window.location.pathname
  );

  const [page, setPage] = useState<Page>(
    () => pageFromPath(window.location.pathname)
  );

  const [batchId, setBatchId] = useState(
    () =>
      window.localStorage.getItem(
        "settlesense.batchId"
      ) ?? ""
  );

  const [tracePaymentId, setTracePaymentId] =
    useState("pay_010");

  const [toasts, setToasts] = useState<ToastMsg[]>([]);

  const [navOpen, setNavOpen] = useState(false);

  /* ------------------------------------------------------------------------ */
  /* TOAST                                                                    */
  /* ------------------------------------------------------------------------ */

  const toast = useCallback(
    (
      text: string,
      tone: ToastMsg["tone"] = "info"
    ) => {
      const id = Date.now() + Math.random();

      setToasts((ts) => [
        ...ts,
        {
          id,
          text,
          tone,
        },
      ]);

      setTimeout(() => {
        setToasts((ts) =>
          ts.filter((t) => t.id !== id)
        );
      }, 4200);
    },
    []
  );

  /* ------------------------------------------------------------------------ */
  /* BROWSER BACK / FORWARD                                                   */
  /* ------------------------------------------------------------------------ */

  useEffect(() => {
    const onPopState = () => {
      const currentPath =
        window.location.pathname;

      setRoute(currentPath);
      setPage(pageFromPath(currentPath));
      setNavOpen(false);

      window.scrollTo({
        top: 0,
        behavior: "auto",
      });
    };

    window.addEventListener(
      "popstate",
      onPopState
    );

    return () => {
      window.removeEventListener(
        "popstate",
        onPopState
      );
    };
  }, []);

  /* ------------------------------------------------------------------------ */
  /* LOAD SYNTHETIC FIXTURE                                                   */
  /* ------------------------------------------------------------------------ */

  async function selectBatchFromFixture() {
    try {
      const batch =
        await api.createFixtureBatch();

      await selectBatch(batch.batch_id);
    } catch (err) {
      toast(
        err instanceof Error
          ? `Fixture load failed: ${err.message}`
          : "Fixture load failed",
        "bad"
      );
    }
  }

  /* ------------------------------------------------------------------------ */
  /* SELECT BATCH                                                             */
  /* ------------------------------------------------------------------------ */

  async function selectBatch(id: string) {
    setBatchId(id);

    window.localStorage.setItem(
      "settlesense.batchId",
      id
    );

    try {
      const result =
        await api.reconcile(id);

      window.localStorage.setItem(
        "settlesense.batchRecords",
        String(result.result_count)
      );

      window.localStorage.setItem(
        "settlesense.lastReconciled",
        "Just now"
      );

      toast(
        "Reconciliation complete — results ready",
        "good"
      );
    } catch (err) {
      toast(
        err instanceof Error
          ? `Reconciliation failed: ${err.message}`
          : "Reconciliation failed",
        "bad"
      );
    }

    /*
     * After selecting/uploading a batch,
     * always go directly to Overview.
     */

    const nextPath = pathForPage("overview");

    window.history.pushState(
      {},
      "",
      nextPath
    );

    setRoute(nextPath);
    setPage("overview");
    setNavOpen(false);

    window.scrollTo({
      top: 0,
      behavior: "auto",
    });
  }

  /* ------------------------------------------------------------------------ */
  /* DIRECT NAVIGATION                                                        */
  /* ------------------------------------------------------------------------ */

  const go = (nextPage: Page) => {
    const nextPath = pathForPage(nextPage);

    if (window.location.pathname !== nextPath) {
      window.history.pushState(
        {},
        "",
        nextPath
      );
    }

    setRoute(nextPath);
    setPage(nextPage);

    // Always close mobile navigation after navigation.
    setNavOpen(false);

    // Start the new section from the top.
    window.scrollTo({
      top: 0,
      behavior: "auto",
    });
  };

  /* ------------------------------------------------------------------------ */
  /* OPEN PUBLIC ROUTE                                                        */
  /* ------------------------------------------------------------------------ */

  const openRoute = (path: string) => {
    if (window.location.pathname !== path) {
      window.history.pushState(
        {},
        "",
        path
      );
    }

    setRoute(path);
    setPage(pageFromPath(path));
    setNavOpen(false);

    window.scrollTo({
      top: 0,
      behavior: "auto",
    });
  };

  /* ------------------------------------------------------------------------ */
  /* TRACE                                                                    */
  /* ------------------------------------------------------------------------ */

  const openTrace = (paymentId: string) => {
    setTracePaymentId(paymentId);
    go("trace");
  };

  /* ------------------------------------------------------------------------ */
  /* LANDING PAGE                                                             */
  /* ------------------------------------------------------------------------ */

  if (route === "/") {
    return (
      <Landing
        onEnter={openRoute}
      />
    );
  }

  /* ------------------------------------------------------------------------ */
  /* AUTH                                                                     */
  /* ------------------------------------------------------------------------ */

  if (
    route === "/login" ||
    route === "/signup"
  ) {
    return (
      <Auth
        mode={
          route === "/signup"
            ? "signup"
            : "login"
        }
        onBack={() =>
          openRoute("/")
        }
        onContinue={() =>
          openRoute(
            "/workspace/overview"
          )
        }
      />
    );
  }

  /* ------------------------------------------------------------------------ */
  /* WORKSPACE                                                                */
  /* ------------------------------------------------------------------------ */

  return (
    <div className="min-h-screen bg-surface text-ink">

      {/* ================================================================== */}
      {/* SINGLE GLOBAL TOP NAVIGATION                                      */}
      {/* ================================================================== */}

      <TopNav
        page={page}
        onNavigate={go}
        onMenuOpen={() => setNavOpen(true)}
      />

      {/* ================================================================== */}
      {/* MOBILE NAVIGATION OVERLAY                                          */}
      {/* ================================================================== */}

      {navOpen && (
        <TopNav
          page={page}
          onNavigate={go}
          mobile
          onClose={() => setNavOpen(false)}
        />
      )}

      {/* ================================================================== */}
      {/* PAGE CONTENT                                                        */}
      {/* ================================================================== */}

      <div className="flex min-h-[calc(100vh-68px)] min-w-0 flex-col">

        <main
          className="mx-auto w-full max-w-[1480px] flex-1 px-4 py-5 sm:px-6 sm:py-6 lg:px-8 animate-fade-up"
          key={page}
        >

          {/* -------------------------------------------------------------- */}
          {/* NO BATCH — OVERVIEW                                           */}
          {/* -------------------------------------------------------------- */}

          {!batchId && page === "overview" ? (
            <OverviewLanding
              onUpload={() =>
                go("upload")
              }
              onFixture={() => {
                void selectBatchFromFixture();
              }}
            />

          ) : !batchId &&
            page !== "upload" ? (

            /* ------------------------------------------------------------ */
            /* NO BATCH — OTHER SECTIONS                                    */
            /* ------------------------------------------------------------ */

            <div className="card border-2 border-dashed border-border-hairline p-10 text-center animate-scale-in sm:p-16">

              <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-sm bg-primary/20 text-primary">
                <Icon
                  name="layers"
                  className="h-5 w-5"
                />
              </span>

              <p className="mt-4 text-title-lg font-semibold text-ink">
                No batch loaded
              </p>

              <p className="mx-auto mt-1 max-w-md text-body text-ink-muted">
                Upload three CSVs or load the
                synthetic fixture to begin
                reconciliation.
              </p>

              <button
                type="button"
                onClick={() =>
                  go("upload")
                }
                className="btn btn-primary mt-5"
              >
                Go to upload
              </button>
            </div>

          ) : (

            /* ------------------------------------------------------------ */
            /* ACTUAL WORKSPACE PAGES                                       */
            /* ------------------------------------------------------------ */

            <>
              {page === "upload" && (
                <Upload
                  onBatch={selectBatch}
                />
              )}

              {page === "overview" &&
                batchId && (
                  <Overview
                    batchId={batchId}
                    onRerun={() =>
                      selectBatch(batchId)
                    }
                    onOpenTrace={
                      openTrace
                    }
                    onOpenExceptions={() =>
                      go("exceptions")
                    }
                  />
                )}

              {page === "results" &&
                batchId && (
                  <Results
                    batchId={batchId}
                    onOpenTrace={
                      openTrace
                    }
                  />
                )}

              {page === "exceptions" &&
                batchId && (
                  <Exceptions
                    batchId={batchId}
                  />
                )}

              {page === "trace" &&
                batchId && (
                  <Trace
                    batchId={batchId}
                    initialPaymentId={
                      tracePaymentId
                    }
                  />
                )}

              {page === "cash" &&
                batchId && (
                  <Cash
                    batchId={batchId}
                  />
                )}

              {page === "ai" &&
                batchId && (
                  <Ai
                    batchId={batchId}
                    onOpenTrace={
                      openTrace
                    }
                  />
                )}
            </>
          )}
        </main>

        {/* ================================================================== */}
        {/* FOOTER                                                             */}
        {/* ================================================================== */}

        <footer className="footer">
          <div className="mx-auto max-w-[1480px] px-4 py-3 sm:px-6 lg:px-8">
            <p className="text-caption text-ink-muted">
              Deterministic engine · AI explains,
              never decides · Paise-integer money ·
              Every exception visible with evidence.
            </p>
          </div>
        </footer>
      </div>

      {/* ================================================================== */}
      {/* TOASTS                                                              */}
      {/* ================================================================== */}

      <Toasts
        items={toasts}
        onDismiss={(id) =>
          setToasts((ts) =>
            ts.filter(
              (t) => t.id !== id
            )
          )
        }
      />
    </div>
  );
}