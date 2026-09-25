import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AssistantPage } from "@/pages/AssistantPage";
import { completedProgress, employeeMe, message, proposalMessage } from "./fixtures";
import { renderAt } from "./utils";

const api = vi.hoisted(() => ({
  conversations: { current: vi.fn(), send: vi.fn(), confirm: vi.fn(), dismiss: vi.fn(), create: vi.fn(), upload: vi.fn() },
  dashboard: { employee: vi.fn() },
  tickets: { progress: vi.fn() },
  health: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, api: { ...actual.api, ...api, tickets: { ...actual.api.tickets, ...api.tickets } } };
});
vi.mock("@/auth/AuthProvider", () => ({ useAuth: () => ({ me: employeeMe }) }));

const conversation = { id: "c1", title: null, status: "active", created_at: new Date().toISOString(), updated_at: new Date().toISOString(), messages: [] };

describe("employee assistant", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.conversations.current.mockResolvedValue(conversation);
    api.dashboard.employee.mockResolvedValue({ active: [], recent: [], waiting_on_you: 0, open_count: 0 });
    api.health.mockResolvedValue({ status: "ok", version: "0.1.0", environment: "test", configured: { ai: true } });
  });

  it("turns a problem description into an incident with live routing", async () => {
    const user = userEvent.setup();
    const userMessage = message({ id: "m-user", role: "user", content: "My VPN isn't working since this morning." });
    api.conversations.send.mockResolvedValue({ conversation_id: "c1", messages: [userMessage, proposalMessage] });
    const created = message({
      id: "m-created", content: "Incident INC-10234 has been created. I'm investigating it now and will route it to the right team.",
      message_type: "ticket_created", ticket_id: "tk-1", payload: { ticket_id: "tk-1", ticket_number: "INC-10234", type_label: "Incident", suggestions: ["Who is handling it?"] },
    });
    api.conversations.confirm.mockResolvedValue({ ticket: {}, messages: [{ ...proposalMessage, payload: { ...proposalMessage.payload, status: "created" } }, created] });
    api.tickets.progress.mockResolvedValue(completedProgress);

    renderAt(<AssistantPage />);
    expect(await screen.findByRole("heading", { name: "How can we help you today?" })).toBeInTheDocument();

    await user.type(screen.getByRole("textbox", { name: /describe an it issue/i }), "My VPN isn't working since this morning.");
    await user.click(screen.getByRole("button", { name: /send/i }));

    expect(api.conversations.send).toHaveBeenCalledWith("c1", "My VPN isn't working since this morning.");
    expect(await screen.findByText("AI Analysis")).toBeInTheDocument();
    expect(screen.getByText("Network / VPN")).toBeInTheDocument();
    expect(screen.getByText(/certificate may have expired/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /create incident/i }));
    expect(api.conversations.confirm).toHaveBeenCalledWith("c1", "m-proposal");
    const routed = await screen.findByText(/has been assigned to/i);
    expect(routed).toHaveTextContent("Network · Rahul Sharma is handling it");
    expect(within(routed.closest("div")!).getByText("INC-10234")).toBeInTheDocument();
    await waitFor(() => expect(api.tickets.progress).toHaveBeenCalledWith("tk-1"));
  });

  it("shows an error instead of a blank screen when the assistant can't load", async () => {
    const { ApiError } = await import("@/lib/api");
    api.conversations.current.mockRejectedValue(new ApiError(503, "service_unavailable", "The database is not configured."));
    renderAt(<AssistantPage />);
    expect(await screen.findByText("Unable to load the assistant.")).toBeInTheDocument();
    expect(screen.getByText("The database is not configured.")).toBeInTheDocument();
  });
});
