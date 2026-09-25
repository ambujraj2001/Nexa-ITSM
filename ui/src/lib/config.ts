/**
 * Public runtime configuration. Only VITE_* values reach the browser, and the
 * build refuses any that look like secrets (see vite.config.ts). The browser
 * talks to the Nexa API for everything except sign-in, which uses Supabase Auth
 * with the public anon key.
 */

function read(name: string): string {
  const value = (import.meta.env[name] as string | undefined) ?? "";
  return value.trim().replace(/\/+$/, "");
}

export const config = {
  apiBaseUrl: read("VITE_API_BASE_URL") || "http://localhost:8000",
  supabaseUrl: read("VITE_SUPABASE_URL"),
  supabaseAnonKey: read("VITE_SUPABASE_ANON_KEY"),
} as const;

export const authConfigured = Boolean(config.supabaseUrl && config.supabaseAnonKey);
