import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// Anything VITE_* is inlined into the browser bundle. Refuse names that look like secrets,
// and values that are Supabase secret keys (sb_secret_… or a service_role JWT).
const SECRET_LIKE = /(SERVICE_ROLE|SECRET|PASSWORD|PRIVATE|TOKEN|API_KEY|DB_URL|DSN)/i;

function isSupabaseSecret(value: string): boolean {
  if (value.startsWith("sb_secret_")) return true;
  const payload = value.split(".")[1];
  if (!payload) return false;
  try {
    return JSON.parse(Buffer.from(payload, "base64url").toString("utf8")).role === "service_role";
  } catch {
    return false;
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, import.meta.dirname, "VITE_");
  for (const [name, value] of Object.entries(env)) {
    if (SECRET_LIKE.test(name.replace(/^VITE_/, "")) || isSupabaseSecret(value)) {
      throw new Error(`Refusing to expose ${name} to the browser: VITE_* variables are public.`);
    }
  }
  return {
    plugins: [react()],
    resolve: { alias: { "@": path.resolve(import.meta.dirname, "src") } },
    server: { port: 5173, strictPort: true },
    preview: { port: 5173 },
    build: { sourcemap: mode !== "production" },
  };
});
