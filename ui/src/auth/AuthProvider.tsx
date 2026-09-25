/**
 * Authentication state: the Supabase session plus the server-side profile
 * (`GET /api/me`). The role used for routing comes from the API — the browser
 * never decides who is an engineer or admin; the backend enforces it anyway.
 */
import type { Session } from "@supabase/supabase-js";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, ApiError } from "@/lib/api";
import { authConfigured } from "@/lib/config";
import { supabase } from "@/lib/supabase";
import type { Me } from "@/lib/types";

type Status = "loading" | "signed_out" | "signed_in" | "unconfigured";

interface AuthContextValue {
  status: Status;
  session: Session | null;
  me: Me | null;
  meLoading: boolean;
  meError: ApiError | null;
  signInWithPassword: (email: string, password: string) => Promise<void>;
  sendMagicLink: (email: string) => Promise<void>;
  signInWithProvider: (provider: "google" | "azure") => Promise<void>;
  trySso: (email: string) => Promise<boolean>;
  signUp: (name: string, email: string, password: string) => Promise<{ needsConfirmation: boolean }>;
  signOut: () => Promise<void>;
  refreshMe: () => Promise<unknown>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function redirectUrl(): string {
  return `${window.location.origin}/auth/callback`;
}

function requireClient() {
  if (!supabase) throw new Error("Sign-in isn't configured yet. Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY.");
  return supabase;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [session, setSession] = useState<Session | null>(null);
  const [status, setStatus] = useState<Status>(authConfigured ? "loading" : "unconfigured");

  useEffect(() => {
    if (!supabase) return;
    let active = true;
    supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      setSession(data.session);
      setStatus(data.session ? "signed_in" : "signed_out");
    });
    const { data } = supabase.auth.onAuthStateChange((_event, next) => {
      setSession(next);
      setStatus(next ? "signed_in" : "signed_out");
      if (!next) queryClient.clear();
    });
    return () => {
      active = false;
      data.subscription.unsubscribe();
    };
  }, [queryClient]);

  const userId = session?.user.id ?? null;
  const meQuery = useQuery({
    queryKey: ["me", userId],
    queryFn: api.me.get,
    enabled: status === "signed_in" && Boolean(userId),
    staleTime: 60_000,
    retry: (count, error) => !(error instanceof ApiError && [401, 403].includes(error.status)) && count < 2,
  });

  const signInWithPassword = useCallback(async (email: string, password: string) => {
    const { error } = await requireClient().auth.signInWithPassword({ email, password });
    if (error) throw new Error(error.message === "Invalid login credentials" ? "That email and password don't match." : error.message);
  }, []);

  const sendMagicLink = useCallback(async (email: string) => {
    const { error } = await requireClient().auth.signInWithOtp({ email, options: { emailRedirectTo: redirectUrl(), shouldCreateUser: false } });
    if (error) throw new Error(error.message);
  }, []);

  const signInWithProvider = useCallback(async (provider: "google" | "azure") => {
    const { error } = await requireClient().auth.signInWithOAuth({
      provider,
      options: { redirectTo: redirectUrl(), scopes: provider === "azure" ? "email" : undefined },
    });
    if (error) throw new Error(error.message);
  }, []);

  const trySso = useCallback(async (email: string) => {
    const domain = email.split("@")[1];
    if (!domain || !supabase) return false;
    const { data, error } = await supabase.auth.signInWithSSO({ domain, options: { redirectTo: redirectUrl() } });
    if (error || !data?.url) return false;
    window.location.assign(data.url);
    return true;
  }, []);

  const signUp = useCallback(async (name: string, email: string, password: string) => {
    const { data, error } = await requireClient().auth.signUp({ email, password, options: { data: { full_name: name }, emailRedirectTo: redirectUrl() } });
    if (error) throw new Error(error.message);
    return { needsConfirmation: !data.session };
  }, []);

  const signOut = useCallback(async () => {
    await supabase?.auth.signOut();
    queryClient.clear();
  }, [queryClient]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      session,
      me: meQuery.data ?? null,
      meLoading: meQuery.isLoading,
      meError: meQuery.error instanceof ApiError ? meQuery.error : meQuery.error ? new ApiError(0, "unknown", String(meQuery.error)) : null,
      signInWithPassword,
      sendMagicLink,
      signInWithProvider,
      trySso,
      signUp,
      signOut,
      refreshMe: meQuery.refetch,
    }),
    [status, session, meQuery.data, meQuery.isLoading, meQuery.error, meQuery.refetch, signInWithPassword, sendMagicLink, signInWithProvider, trySso, signUp, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
