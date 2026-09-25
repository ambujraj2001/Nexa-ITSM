import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { authConfigured, config } from "./config";

/**
 * Supabase is used in the browser for authentication only (anon key, PKCE flow,
 * persisted session). All application data goes through the Nexa API.
 */
export const supabase: SupabaseClient | null = authConfigured
  ? createClient(config.supabaseUrl, config.supabaseAnonKey, {
      auth: { flowType: "pkce", persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
    })
  : null;

export interface AuthProviders {
  google: boolean;
  azure: boolean;
  email: boolean;
  signupDisabled: boolean;
}

/** Which sign-in methods the Supabase project has enabled (public endpoint). */
export async function fetchAuthProviders(): Promise<AuthProviders> {
  const fallback = { google: false, azure: false, email: true, signupDisabled: false };
  if (!authConfigured) return fallback;
  try {
    const res = await fetch(`${config.supabaseUrl}/auth/v1/settings`, { headers: { apikey: config.supabaseAnonKey } });
    if (!res.ok) return fallback;
    const body = (await res.json()) as { external?: Record<string, boolean>; disable_signup?: boolean };
    return {
      google: Boolean(body.external?.google),
      azure: Boolean(body.external?.azure),
      email: body.external?.email !== false,
      signupDisabled: Boolean(body.disable_signup),
    };
  } catch {
    return fallback;
  }
}
