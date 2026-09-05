import { useState } from "react";
import {
  ArrowRight,
  Eye,
  EyeOff,
  KeyRound,
  Loader2,
  LogIn,
  Mail,
  ShieldCheck,
  UserRound,
} from "lucide-react";

import { useAuth } from "../context/AuthContext";

type AuthProps = {
  mode: "login" | "signup";
  onBack: () => void;
  onContinue: () => void;
};

export default function Auth({
  mode,
  onBack,
  onContinue,
}: AuthProps) {
  const { signIn, signUp } = useAuth();

  const [authMode, setAuthMode] = useState<"login" | "signup">(mode);

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const signup = authMode === "signup";

  const validateEmail = (value: string) => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
  };

  const switchMode = (
    nextMode: "login" | "signup",
  ) => {
    setAuthMode(nextMode);
    setError("");
    setSuccess("");
    setPassword("");
  };

  const handleSubmit = async (
    event: React.FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault();

    setError("");
    setSuccess("");

    const normalizedEmail = email.trim().toLowerCase();

    if (!normalizedEmail || !password) {
      setError(
        "Please enter both email and password.",
      );
      return;
    }

    if (!validateEmail(normalizedEmail)) {
      setError(
        "Please enter a valid email address.",
      );
      return;
    }

    if (password.length < 8) {
      setError(
        "Password must contain at least 8 characters.",
      );
      return;
    }

    if (signup && !fullName.trim()) {
      setError("Please enter your full name.");
      return;
    }

    setLoading(true);

    try {
      if (signup) {
        await signUp(
          normalizedEmail,
          password,
          fullName.trim(),
        );

        /*
         * Account creation succeeds first.
         * User is then moved to the login state.
         */
        setEmail(normalizedEmail);
        setPassword("");

        setSuccess(
          "Account created successfully. Please sign in to continue.",
        );

        setAuthMode("login");
      } else {
        /*
         * REAL SUPABASE LOGIN
         */
        await signIn(
          normalizedEmail,
          password,
        );

        /*
         * IMPORTANT:
         *
         * onContinue is controlled by App.tsx.
         * App.tsx MUST point this callback to:
         *
         * /workspace/overview
         *
         * It must NOT point to /workspace/upload.
         */
        onContinue();
      }
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : "Authentication failed. Please try again.";

      const normalizedMessage =
        message.toLowerCase();

      if (
        normalizedMessage.includes(
          "invalid login credentials",
        )
      ) {
        setError(
          "Incorrect email or password. Please check your credentials and try again.",
        );
      } else if (
        normalizedMessage.includes(
          "email not confirmed",
        )
      ) {
        setError(
          "Please confirm your email address before signing in.",
        );
      } else if (
        normalizedMessage.includes(
          "user already registered",
        )
      ) {
        setError(
          "An account with this email already exists. Please sign in instead.",
        );
      } else {
        setError(message);
      }
    } finally {
      setLoading(false);
    }
  };

  /*
   * Demo account
   */
  const handleDemoSignIn = async () => {
    setError("");
    setSuccess("");

    const demoEmail =
      import.meta.env.VITE_DEMO_EMAIL;

    const demoPassword =
      import.meta.env.VITE_DEMO_PASSWORD;

    if (!demoEmail || !demoPassword) {
      setError(
        "Demo account is not configured.",
      );
      return;
    }

    setLoading(true);

    try {
      await signIn(
        demoEmail,
        demoPassword,
      );

      /*
       * Demo login uses exactly the same
       * successful-login flow as normal login.
       */
      onContinue();
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : "Unable to sign in with demo account.";

      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full bg-[#f8fafc] text-[#0f172a]">
      <div className="flex min-h-screen items-center justify-center px-4 py-8 sm:px-6 lg:px-8">
        <div className="grid w-full max-w-[1080px] overflow-hidden rounded-[28px] border border-blue-100 bg-white shadow-[0_25px_80px_rgba(15,23,42,0.10)] lg:grid-cols-[0.9fr_1.1fr]">

          {/* LEFT PANEL */}
          <section className="relative hidden overflow-hidden bg-gradient-to-br from-[#eff6ff] via-white to-[#f8fbff] p-10 lg:flex lg:flex-col">
            <div className="absolute -right-24 -top-24 h-64 w-64 rounded-full bg-blue-100/60 blur-3xl" />

            <div className="absolute -bottom-24 -left-20 h-64 w-64 rounded-full bg-sky-100/60 blur-3xl" />

            <div className="relative z-10">
              <button
                type="button"
                onClick={onBack}
                className="flex items-center gap-3 text-left"
              >
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[#0042e2] text-white shadow-[0_6px_18px_rgba(0,66,226,0.22)]">
                  <ShieldCheck className="h-5 w-5" />
                </span>

                <span>
                  <span className="block text-[17px] font-bold tracking-tight text-slate-900">
                    SettleSense
                  </span>

                  <span className="mt-0.5 block text-[10px] font-medium uppercase tracking-[0.12em] text-slate-400">
                    AI Finance Controller
                  </span>
                </span>
              </button>

              <div className="mt-28">
                <div className="mb-5 flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-blue-100 bg-white text-[#0042e2] shadow-sm">
                  <LogIn className="h-5 w-5" />
                </div>

                <h2 className="max-w-sm text-[31px] font-bold leading-[1.16] tracking-tight text-slate-900">
                  A clearer close starts with trusted evidence.
                </h2>

                <p className="mt-5 max-w-sm text-sm leading-6 text-slate-500">
                  Reconcile payment records, settlements
                  and bank movements from one finance
                  control room.
                </p>
              </div>

              <div className="mt-10 space-y-4">
                <div className="flex items-center gap-3">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-[#0042e2]">
                    <ShieldCheck className="h-4 w-4" />
                  </span>

                  <span className="text-sm text-slate-600">
                    Evidence-backed reconciliation
                  </span>
                </div>

                <div className="flex items-center gap-3">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-[#0042e2]">
                    <KeyRound className="h-4 w-4" />
                  </span>

                  <span className="text-sm text-slate-600">
                    Secure account authentication
                  </span>
                </div>
              </div>
            </div>

            <div className="relative z-10 mt-auto pt-12 text-xs text-slate-400">
              AI explains. The deterministic engine decides.
            </div>
          </section>

          {/* RIGHT PANEL */}
          <section className="flex min-h-[680px] flex-col justify-center px-6 py-8 sm:px-10 lg:px-14">

            {/* MOBILE BRAND */}
            <div className="mb-8 flex items-center lg:hidden">
              <button
                type="button"
                onClick={onBack}
                className="flex items-center gap-3"
              >
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#0042e2] text-white">
                  <ShieldCheck className="h-5 w-5" />
                </span>

                <span className="text-lg font-bold text-slate-900">
                  SettleSense
                </span>
              </button>
            </div>

            {/* BACK */}
            <button
              type="button"
              onClick={onBack}
              className="mb-8 flex w-fit items-center gap-2 text-sm font-medium text-slate-500 transition hover:text-slate-900"
            >
              <ArrowRight className="h-4 w-4 rotate-180" />
              Back to home
            </button>

            {/* HEADER */}
            <div>
              <div className="mb-4 flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-blue-50 text-[#0042e2]">
                {signup ? (
                  <UserRound className="h-5 w-5" />
                ) : (
                  <LogIn className="h-5 w-5" />
                )}
              </div>

              <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#0042e2]">
                {signup
                  ? "Create your workspace"
                  : "Welcome back"}
              </p>

              <h1 className="mt-3 text-[30px] font-bold leading-tight tracking-tight text-slate-900">
                {signup
                  ? "Create your account"
                  : "Sign in with email"}
              </h1>

              <p className="mt-2 max-w-md text-sm leading-6 text-slate-500">
                {signup
                  ? "Create your SettleSense account and start managing your finance control room."
                  : "Sign in to continue to your SettleSense finance control room."}
              </p>
            </div>

            {/* ERROR */}
            {error && (
              <div
                role="alert"
                className="mt-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm leading-5 text-red-700"
              >
                {error}
              </div>
            )}

            {/* SUCCESS */}
            {success && (
              <div
                role="status"
                className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm leading-5 text-emerald-700"
              >
                {success}
              </div>
            )}

            {/* FORM */}
            <form
              onSubmit={handleSubmit}
              className="mt-8 space-y-5"
            >
              {/* NAME */}
              {signup && (
                <div>
                  <label
                    htmlFor="full-name"
                    className="mb-2 block text-sm font-semibold text-slate-700"
                  >
                    Full name
                  </label>

                  <div className="relative">
                    <UserRound className="pointer-events-none absolute left-3.5 top-1/2 z-10 h-[17px] w-[17px] -translate-y-1/2 text-slate-400" />

                    <input
                      id="full-name"
                      type="text"
                      value={fullName}
                      onChange={(event) =>
                        setFullName(event.target.value)
                      }
                      placeholder="Ava Morgan"
                      autoComplete="name"
                      disabled={loading}
                      required
                      style={{
                        paddingLeft: "44px",
                        paddingRight: "14px",
                      }}
                      className="box-border h-12 w-full rounded-xl border border-slate-200 bg-slate-50 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 hover:border-slate-300 focus:border-[#0042e2] focus:bg-white focus:ring-4 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
                    />
                  </div>
                </div>
              )}

              {/* EMAIL */}
              <div>
                <label
                  htmlFor="auth-email"
                  className="mb-2 block text-sm font-semibold text-slate-700"
                >
                  Email address
                </label>

                <div className="relative">
                  <Mail className="pointer-events-none absolute left-3.5 top-1/2 z-10 h-[17px] w-[17px] -translate-y-1/2 text-slate-400" />

                  <input
                    id="auth-email"
                    type="email"
                    value={email}
                    onChange={(event) =>
                      setEmail(event.target.value)
                    }
                    placeholder="you@company.com"
                    autoComplete="email"
                    disabled={loading}
                    required
                    style={{
                      paddingLeft: "44px",
                      paddingRight: "14px",
                    }}
                    className="box-border h-12 w-full rounded-xl border border-slate-200 bg-slate-50 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 hover:border-slate-300 focus:border-[#0042e2] focus:bg-white focus:ring-4 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
                  />
                </div>
              </div>

              {/* PASSWORD */}
              <div>
                <div className="mb-2 flex items-center justify-between gap-4">
                  <label
                    htmlFor="auth-password"
                    className="text-sm font-semibold text-slate-700"
                  >
                    Password
                  </label>

                  {!signup && (
                    <button
                      type="button"
                      disabled={loading}
                      onClick={() =>
                        setError(
                          "Password reset is not configured yet.",
                        )
                      }
                      className="shrink-0 text-xs font-semibold text-[#0042e2] hover:underline disabled:opacity-50"
                    >
                      Forgot password?
                    </button>
                  )}
                </div>

                <div className="relative">
                  <KeyRound className="pointer-events-none absolute left-3.5 top-1/2 z-10 h-[17px] w-[17px] -translate-y-1/2 text-slate-400" />

                  <input
                    id="auth-password"
                    type={
                      showPassword
                        ? "text"
                        : "password"
                    }
                    value={password}
                    onChange={(event) =>
                      setPassword(event.target.value)
                    }
                    placeholder="8+ characters"
                    autoComplete={
                      signup
                        ? "new-password"
                        : "current-password"
                    }
                    minLength={8}
                    disabled={loading}
                    required
                    style={{
                      paddingLeft: "44px",
                      paddingRight: "48px",
                    }}
                    className="box-border h-12 w-full rounded-xl border border-slate-200 bg-slate-50 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 hover:border-slate-300 focus:border-[#0042e2] focus:bg-white focus:ring-4 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
                  />

                  <button
                    type="button"
                    disabled={loading}
                    onClick={() =>
                      setShowPassword(
                        (visible) => !visible,
                      )
                    }
                    className="absolute right-3.5 top-1/2 z-10 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 disabled:opacity-50"
                    aria-label={
                      showPassword
                        ? "Hide password"
                        : "Show password"
                    }
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </div>

              {/* TERMS */}
              {signup && (
                <label className="flex cursor-pointer items-start gap-2.5 text-xs leading-5 text-slate-500">
                  <input
                    required
                    type="checkbox"
                    disabled={loading}
                    className="mt-[3px] h-4 w-4 shrink-0 rounded border-slate-300 accent-[#0042e2]"
                  />

                  <span>
                    I agree to the SettleSense terms and
                    privacy policy.
                  </span>
                </label>
              )}

              {/* SUBMIT */}
              <button
                type="submit"
                disabled={loading}
                className="mt-1 flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-b from-slate-700 to-slate-950 text-sm font-semibold text-white shadow-[0_8px_20px_rgba(15,23,42,0.16)] transition hover:brightness-110 active:scale-[0.995] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    {signup
                      ? "Creating account..."
                      : "Signing in..."}
                  </>
                ) : (
                  <>
                    {signup
                      ? "Create account"
                      : "Sign in"}
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </button>

              {/* DEMO LOGIN */}
              {!signup && (
                <>
                  <div className="flex items-center gap-3 py-1">
                    <div className="h-px flex-1 bg-slate-200" />

                    <span className="shrink-0 text-[11px] font-medium uppercase tracking-[0.08em] text-slate-400">
                      or
                    </span>

                    <div className="h-px flex-1 bg-slate-200" />
                  </div>

                  <button
                    type="button"
                    disabled={loading}
                    onClick={handleDemoSignIn}
                    className="flex h-11 w-full items-center justify-center gap-2 rounded-xl border border-blue-200 bg-blue-50 text-sm font-semibold text-[#0042e2] transition hover:border-blue-300 hover:bg-blue-100 active:scale-[0.995] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {loading ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Opening demo...
                      </>
                    ) : (
                      <>
                        <ShieldCheck className="h-4 w-4" />
                        Continue with Demo Account
                      </>
                    )}
                  </button>

                  <p className="text-center text-[11px] leading-5 text-slate-400">
                    Explore SettleSense with a
                    preconfigured demo account.
                  </p>
                </>
              )}
            </form>

            {/* SWITCH LOGIN / SIGNUP */}
            <div className="mt-7 text-center text-sm text-slate-500">
              {signup
                ? "Already have an account?"
                : "Don't have an account?"}{" "}

              <button
                type="button"
                disabled={loading}
                onClick={() =>
                  switchMode(
                    signup
                      ? "login"
                      : "signup",
                  )
                }
                className="font-semibold text-[#0042e2] hover:underline disabled:opacity-50"
              >
                {signup
                  ? "Sign in"
                  : "Create one"}
              </button>
            </div>

            {/* SECURITY */}
            <div className="mt-8 flex items-center justify-center gap-2 text-[11px] text-slate-400">
              <ShieldCheck className="h-3.5 w-3.5 shrink-0" />

              <span>
                Secure authentication powered by Supabase
              </span>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}