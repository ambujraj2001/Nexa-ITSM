import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "@/auth/AuthProvider";
import { HomeRedirect, RequireAuth, RequireRole } from "@/auth/guards";
import { adminMe, employeeMe, engineerMe } from "./fixtures";

const state = vi.hoisted(() => ({ session: null as null | { user: { id: string }; access_token: string } }));
const meGet = vi.hoisted(() => vi.fn());

vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn(async () => ({ data: { session: state.session } })),
      onAuthStateChange: vi.fn(() => ({ data: { subscription: { unsubscribe: () => undefined } } })),
      signOut: vi.fn(async () => ({})),
    },
  },
  fetchAuthProviders: vi.fn(async () => ({ google: false, azure: false, email: true, signupDisabled: false })),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, api: { ...actual.api, me: { get: meGet, update: vi.fn() } } };
});

function renderApp(route: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<div>login page</div>} />
            <Route path="/app" element={<RequireAuth><HomeRedirect /></RequireAuth>} />
            <Route path="/assistant" element={<RequireAuth><div>assistant page</div></RequireAuth>} />
            <Route path="/dispatch" element={<RequireAuth><RequireRole roles={["engineer", "admin"]}><div>dispatch page</div></RequireRole></RequireAuth>} />
            <Route path="/settings/ai" element={<RequireAuth><div>settings page</div></RequireAuth>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("login routing", () => {
  beforeEach(() => {
    state.session = null;
    meGet.mockReset();
  });

  it("sends signed-out visitors to sign in", async () => {
    renderApp("/app");
    expect(await screen.findByText("login page")).toBeInTheDocument();
  });

  it.each([
    ["employee", employeeMe, "assistant page"],
    ["engineer", engineerMe, "dispatch page"],
    ["admin", adminMe, "settings page"],
  ])("routes an %s to their home after sign-in", async (_role, me, expected) => {
    state.session = { user: { id: me.id }, access_token: "token" };
    meGet.mockResolvedValue(me);
    renderApp("/app");
    expect(await screen.findByText(expected)).toBeInTheDocument();
  });

  it("keeps employees out of engineer screens (the API enforces this too)", async () => {
    state.session = { user: { id: employeeMe.id }, access_token: "token" };
    meGet.mockResolvedValue(employeeMe);
    renderApp("/dispatch");
    expect(await screen.findByText("assistant page")).toBeInTheDocument();
    expect(screen.queryByText("dispatch page")).not.toBeInTheDocument();
  });
});
