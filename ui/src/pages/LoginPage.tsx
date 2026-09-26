/**
 * Sign-in and sign-up (reference: nexa_sign_in). Email-first: we try the
 * domain's SAML SSO, then fall back to password or a magic link. Google and
 * Microsoft are enabled only when the Supabase project has them switched on.
 */
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { useAuth } from "@/auth/AuthProvider";
import { Icon, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { authConfigured } from "@/lib/config";
import { fetchAuthProviders } from "@/lib/supabase";
import { Aurora } from "./landing/effects";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function GoogleLogo() {
  return (
    <svg aria-hidden="true" className="h-4 w-4 flex-shrink-0" viewBox="0 0 24 24">
      <path d="M12 5c1.6 0 3 .6 4.1 1.6l3.1-3.1C17.3 1.7 14.8 1 12 1 7.5 1 3.7 3.6 1.9 7.3l3.7 2.9C6.5 7.4 9 5 12 5z" fill="#EA4335" />
      <path d="M23.5 12.3c0-.8-.1-1.7-.2-2.3H12v4.5h6.5c-.3 1.5-1.1 2.8-2.4 3.7l3.7 2.9c2.2-2 3.7-5 3.7-8.8z" fill="#4285F4" />
      <path d="M5.6 14.8c-.2-.7-.4-1.5-.4-2.8s.2-2.1.4-2.8L1.9 6.3C.7 8.7 0 10.3 0 12s.7 3.3 1.9 5.7l3.7-2.9z" fill="#FBBC05" />
      <path d="M12 23c3.2 0 6-1.1 8-3l-3.7-2.9c-1.1.7-2.5 1.2-4.3 1.2-3 0-5.5-2.4-6.4-5.2L1.9 16C3.7 19.7 7.5 23 12 23z" fill="#34A853" />
    </svg>
  );
}

function MicrosoftLogo() {
  return (
    <svg aria-hidden="true" className="h-4 w-4 flex-shrink-0" viewBox="0 0 23 23">
      <path d="M1 1h10v10H1z" fill="#f35325" />
      <path d="M12 1h10v10H12z" fill="#81bc06" />
      <path d="M1 12h10v10H1z" fill="#05a6f0" />
      <path d="M12 12h10v10H12z" fill="#ffba08" />
    </svg>
  );
}

function ApiStatus() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    retry: false,
    // Poll every 2s while the API is asleep/unreachable (Render free tier), then every minute.
    refetchInterval: (query) => (query.state.status === "error" || query.state.data?.status !== "ok" ? 2000 : 60_000),
  });
  const ok = health.data?.status === "ok";
  return (
    <div className="mt-space-md flex items-center gap-2">
      <span className={clsx("inline-block h-1.5 w-1.5 rounded-full", health.isLoading ? "bg-outline-variant" : ok ? "animate-pulse bg-on-tertiary-container" : "bg-[#D97706]")} />
      <span className="font-label-code text-[11px] text-label-code text-outline">
        {health.isLoading ? "Checking Nexa API…" : ok ? "Nexa API: operational" : "Nexa API: waking up…"}
      </span>
    </div>
  );
}

export function LoginPage({ mode = "signin" }: { mode?: "signin" | "signup" }) {
  const { status, signInWithPassword, sendMagicLink, signInWithProvider, trySso, signUp } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = params.get("next") || "/app";
  const providers = useQuery({ queryKey: ["auth-providers"], queryFn: fetchAuthProviders, staleTime: 5 * 60_000 });

  const [step, setStep] = useState<"email" | "password" | "link_sent" | "confirm_sent">("email");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const valid = EMAIL.test(email.trim());

  useEffect(() => {
    if (status === "signed_in") navigate(next, { replace: true });
  }, [status, navigate, next]);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message || "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  const onContinue = (e: FormEvent) => {
    e.preventDefault();
    if (!valid) return setError("Enter a valid work email.");
    void run(async () => {
      const redirected = await trySso(email.trim());
      if (!redirected) setStep("password");
    });
  };

  const onPassword = (e: FormEvent) => {
    e.preventDefault();
    void run(() => signInWithPassword(email.trim(), password));
  };

  const onSignUp = (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return setError("Tell us your name.");
    if (!valid) return setError("Enter a valid work email.");
    if (password.length < 8) return setError("Use at least 8 characters for your password.");
    void run(async () => {
      const { needsConfirmation } = await signUp(name.trim(), email.trim(), password);
      if (needsConfirmation) setStep("confirm_sent");
    });
  };

  const signup = mode === "signup";
  return (
    <main className="relative isolate flex min-h-screen w-full flex-col items-center justify-center overflow-hidden bg-surface px-margin py-space-xl">
      <Aurora />
      <div className="relative flex w-full items-center justify-center overflow-hidden px-gutter py-space-xl">
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div className="h-[640px] w-[640px] -translate-y-8 rounded-full bg-surface-container-high/40 blur-[120px]" />
          <div className="absolute -top-32 right-1/4 h-80 w-80 rounded-full bg-secondary-fixed/30 blur-[90px]" />
        </div>
        <div className="relative z-10 mx-auto flex w-full max-w-[440px] flex-col items-center">
          <Link to="/" className="group mb-space-lg flex items-center gap-space-xs">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-on-surface font-display-lg text-[15px] font-semibold tracking-tighter text-surface shadow-sm">N</div>
            <div className="flex items-baseline gap-1.5 pl-1">
              <span className="font-headline-md text-headline-md font-semibold tracking-tight text-on-surface">Nexa</span>
              <span className="rounded bg-surface-container px-1.5 py-0.5 font-label-caps text-[10px] uppercase tracking-widest text-on-surface-variant">AI ITSM</span>
            </div>
          </Link>

          <div className="nx-depth nx-float-card flex w-full flex-col rounded-2xl border border-white/80 bg-white/80 p-8 backdrop-blur-xl sm:p-10">
            <div className="mb-space-lg flex flex-col space-y-1 text-left">
              <h1 className="font-display-lg text-display-lg font-semibold tracking-tight text-on-surface">{signup ? "Get started." : "Welcome back."}</h1>
              <p className="font-body-md text-body-md text-on-surface-variant">{signup ? "Create your account to reach IT through Nexa." : "Sign in to your IT workspace."}</p>
            </div>

            {!authConfigured && (
              <p role="alert" className="mb-space-md rounded-lg bg-error-container px-3 py-2 font-body-sm text-body-sm text-on-error-container">
                Sign-in isn't configured. Add VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY to the repository .env.
              </p>
            )}
            {error && (
              <p role="alert" className="mb-space-md rounded-lg bg-error-container px-3 py-2 font-body-sm text-body-sm text-on-error-container">
                {error}
              </p>
            )}

            {step === "link_sent" || step === "confirm_sent" ? (
              <div className="flex flex-col gap-space-sm rounded-lg bg-surface-container-low p-space-md">
                <div className="flex items-center gap-space-xs font-headline-sm text-headline-sm text-on-surface">
                  <Icon name="mark_email_read" className="text-[18px] text-secondary" /> Check your inbox
                </div>
                <p className="font-body-md text-body-md text-on-surface-variant">
                  {step === "link_sent" ? `We sent a sign-in link to ${email}.` : `We sent a confirmation link to ${email}. Open it to finish creating your account.`}
                </p>
                <button type="button" className="self-start font-body-sm text-body-sm font-medium text-on-surface hover:text-secondary" onClick={() => setStep("email")}>
                  Use a different email
                </button>
              </div>
            ) : signup ? (
              <form className="flex flex-col gap-space-md" onSubmit={onSignUp}>
                <div className="flex flex-col space-y-1.5 text-left">
                  <label htmlFor="full-name" className="font-label-caps text-[10px] uppercase tracking-wider text-on-surface-variant">Full name</label>
                  <input id="full-name" className="input h-10" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
                </div>
                <div className="flex flex-col space-y-1.5 text-left">
                  <label htmlFor="work-email" className="font-label-caps text-[10px] uppercase tracking-wider text-on-surface-variant">Work email</label>
                  <input id="work-email" type="email" className="input h-10" placeholder="name@company.com" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
                </div>
                <div className="flex flex-col space-y-1.5 text-left">
                  <label htmlFor="new-password" className="font-label-caps text-[10px] uppercase tracking-wider text-on-surface-variant">Password</label>
                  <input id="new-password" type="password" className="input h-10" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" minLength={8} />
                </div>
                <button type="submit" disabled={busy || !authConfigured} className="group flex h-10 w-full items-center justify-center gap-space-xs rounded-lg nx-cta bg-on-surface font-body-md text-body-md font-medium text-surface-container-lowest shadow-sm transition-all duration-150 hover:bg-inverse-surface disabled:opacity-60">
                  {busy ? <Spinner className="border-t-white" /> : <span>Create account</span>}
                </button>
              </form>
            ) : step === "email" ? (
              <form className="flex flex-col gap-space-md" onSubmit={onContinue}>
                <div className="flex flex-col space-y-1.5 text-left">
                  <div className="flex items-center justify-between">
                    <label htmlFor="work-email" className="font-label-caps text-[10px] uppercase tracking-wider text-on-surface-variant">Work email</label>
                    <span className="font-label-code text-[11px] text-label-code text-outline">SAML / OIDC</span>
                  </div>
                  <div className="relative flex items-center">
                    <input
                      id="work-email"
                      type="email"
                      required
                      autoComplete="email"
                      placeholder="name@company.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="h-10 w-full rounded-lg bg-surface-container-low px-3 font-body-md text-body-md text-on-surface transition-colors duration-150 placeholder:text-outline focus:bg-surface-container-lowest focus:outline-none"
                    />
                    <Icon name={valid ? "check_circle" : "mail"} className={clsx("pointer-events-none absolute right-3 text-[18px]", valid ? "text-on-tertiary-container" : "text-outline")} />
                  </div>
                </div>
                <button type="submit" disabled={busy || !authConfigured} className="group flex h-10 w-full items-center justify-center gap-space-xs rounded-lg nx-cta bg-on-surface font-body-md text-body-md font-medium text-surface-container-lowest shadow-sm transition-all duration-150 hover:bg-inverse-surface active:bg-primary-container disabled:opacity-60">
                  {busy ? <Spinner className="border-t-white" /> : (
                    <>
                      <span>Continue</span>
                      <Icon name="arrow_forward" className="text-[16px] transition-transform duration-150 group-hover:translate-x-0.5" />
                    </>
                  )}
                </button>
              </form>
            ) : (
              <form className="flex flex-col gap-space-md" onSubmit={onPassword}>
                <div className="flex items-center justify-between rounded-lg bg-surface-container-low px-3 py-2">
                  <span className="truncate font-body-md text-body-md text-on-surface">{email}</span>
                  <button type="button" className="font-body-sm text-body-sm text-on-surface-variant hover:text-on-surface" onClick={() => setStep("email")}>
                    Change
                  </button>
                </div>
                <div className="flex flex-col space-y-1.5 text-left">
                  <label htmlFor="password" className="font-label-caps text-[10px] uppercase tracking-wider text-on-surface-variant">Password</label>
                  <input id="password" type="password" autoFocus required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} className="input h-10" />
                </div>
                <button type="submit" disabled={busy || !password} className="flex h-10 w-full items-center justify-center gap-space-xs rounded-lg nx-cta bg-on-surface font-body-md text-body-md font-medium text-surface-container-lowest shadow-sm transition-all hover:bg-inverse-surface disabled:opacity-60">
                  {busy ? <Spinner className="border-t-white" /> : <span>Sign in</span>}
                </button>
                <button type="button" disabled={busy} className="self-center font-body-sm text-body-sm text-on-surface-variant hover:text-on-surface" onClick={() => void run(async () => { await sendMagicLink(email.trim()); setStep("link_sent"); })}>
                  Email me a sign-in link instead
                </button>
              </form>
            )}

            <div className="relative my-space-lg flex items-center justify-center">
              <div className="absolute inset-0 flex items-center">
                <div className="h-[1px] w-full bg-surface-container" />
              </div>
              <span className="relative bg-surface-container-lowest px-3 font-label-caps text-[10px] uppercase tracking-wider text-outline">or</span>
            </div>

            <div className="flex flex-col gap-2.5">
              {(["google", "azure"] as const).map((provider) => {
                const enabled = providers.data?.[provider] ?? false;
                return (
                  <button
                    key={provider}
                    type="button"
                    disabled={!enabled || busy}
                    onClick={() => void run(() => signInWithProvider(provider))}
                    className="group flex h-10 w-full items-center justify-between rounded-lg bg-surface-container-low px-4 font-body-md text-body-md text-on-surface transition-colors duration-150 hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-60"
                    title={enabled ? undefined : "Not enabled for this workspace"}
                  >
                    <div className="flex items-center gap-3">
                      {provider === "google" ? <GoogleLogo /> : <MicrosoftLogo />}
                      <span className="font-medium text-on-surface">Continue with {provider === "google" ? "Google" : "Microsoft"}</span>
                    </div>
                    <span className="font-label-code text-[11px] text-label-code text-outline opacity-0 transition-opacity group-hover:opacity-100">
                      {enabled ? (provider === "google" ? "SSO" : "Azure AD") : "Not enabled"}
                    </span>
                  </button>
                );
              })}
            </div>

            <div className="mt-space-lg pt-2 text-center">
              <p className="font-body-sm text-body-sm text-on-surface-variant">
                {signup ? "Already have an account?" : "Don't have an account?"}
                <Link className="ml-1 inline-flex items-center gap-0.5 font-medium text-on-surface transition-colors hover:text-secondary" to={signup ? "/login" : "/signup"}>
                  <span>{signup ? "Sign in" : "Get started"}</span>
                  <Icon name="north_east" className="text-[13px]" />
                </Link>
              </p>
            </div>
          </div>

          <div className="mt-space-lg flex items-center gap-space-sm rounded-full bg-surface-container-low px-3 py-1.5 text-on-surface-variant">
            <Icon name="verified_user" filled className="text-[16px] text-tertiary-container" />
            <span className="font-label-code text-[11px] text-label-code tracking-tight">Your session is verified by the server on every request</span>
          </div>
          <ApiStatus />
        </div>
      </div>
    </main>
  );
}

export function AuthCallbackPage() {
  const { status } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const error = params.get("error_description") || new URLSearchParams(window.location.hash.slice(1)).get("error_description");
  useEffect(() => {
    if (status === "signed_in") navigate("/app", { replace: true });
  }, [status, navigate]);
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-space-md bg-surface px-gutter">
      {error ? (
        <>
          <p className="font-headline-sm text-headline-sm text-on-surface">We couldn't sign you in</p>
          <p className="max-w-md text-center font-body-md text-body-md text-on-surface-variant">{error}</p>
          <Link to="/login" className="btn-primary h-9 px-4">Back to sign in</Link>
        </>
      ) : (
        <div className="flex items-center gap-space-sm font-body-md text-body-md text-on-surface-variant">
          <Spinner /> Signing you in…
        </div>
      )}
    </main>
  );
}
