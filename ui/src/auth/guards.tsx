import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";
import { ErrorState, LoadingState, NexaMark } from "@/components/ui";
import type { Role } from "@/lib/types";
import { useAuth } from "./AuthProvider";

function FullPage({ children }: { children: ReactNode }) {
  return <div className="flex min-h-screen flex-col items-center justify-center gap-space-lg bg-surface px-gutter">{children}</div>;
}

/** Renders children only for a signed-in user whose profile loaded from the API. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { status, me, meLoading, meError, signOut, refreshMe } = useAuth();
  const location = useLocation();

  if (status === "unconfigured") {
    return (
      <FullPage>
        <NexaMark size={40} />
        <ErrorState title="Sign-in isn't configured" message="Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in the repository .env, then restart the UI." />
      </FullPage>
    );
  }
  if (status === "loading" || (status === "signed_in" && meLoading)) {
    return (
      <FullPage>
        <LoadingState label="Opening your workspace…" />
      </FullPage>
    );
  }
  if (status === "signed_out") {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  if (meError || !me) {
    const inactive = meError?.code === "account_inactive" || meError?.code === "profile_conflict";
    return (
      <FullPage>
        <ErrorState
          title={inactive ? "Your account can't be used" : "Unable to load your workspace"}
          message={meError?.message ?? "Please try again."}
          onRetry={inactive ? undefined : () => void refreshMe()}
        />
        <button type="button" className="btn-ghost h-8 px-3" onClick={() => void signOut()}>
          Sign out
        </button>
      </FullPage>
    );
  }
  return <>{children}</>;
}

/** UI routing by role. The API independently rejects anything a role can't do. */
export function RequireRole({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { me } = useAuth();
  if (!me) return null;
  if (!roles.includes(me.role)) return <Navigate to={me.home_path} replace />;
  return <>{children}</>;
}

export function HomeRedirect() {
  const { me } = useAuth();
  return <Navigate to={me?.home_path ?? "/assistant"} replace />;
}
