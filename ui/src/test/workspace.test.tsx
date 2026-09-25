import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TicketWorkspacePage } from "@/pages/workspace/TicketWorkspacePage";
import { engineerMe, ticketDetail } from "./fixtures";
import { renderAt } from "./utils";

const api = vi.hoisted(() => ({
  tickets: {
    get: vi.fn(), escalate: vi.fn(), resolve: vi.fn(), resolutionDraft: vi.fn(), activity: vi.fn(), related: vi.fn(),
    comments: { list: vi.fn(), add: vi.fn() },
    steps: { update: vi.fn(), add: vi.fn(), remove: vi.fn(), reorder: vi.fn(), restore: vi.fn(), list: vi.fn() },
    copilot: { history: vi.fn(), ask: vi.fn() },
    progress: vi.fn(), investigate: vi.fn(), assignToMe: vi.fn(), reopen: vi.fn(),
  },
  admin: { teams: vi.fn() },
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, api: { ...actual.api, tickets: api.tickets, admin: { ...actual.api.admin, ...api.admin } } };
});
vi.mock("@/auth/AuthProvider", () => ({ useAuth: () => ({ me: engineerMe }) }));

function renderWorkspace() {
  return renderAt(<TicketWorkspacePage />, { route: "/tickets/tk-1", path: "/tickets/:ticketId" });
}

describe("engineer ticket workspace", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.tickets.get.mockResolvedValue(ticketDetail());
    api.tickets.activity.mockResolvedValue([
      { id: "a1", at: new Date().toISOString(), actor_type: "ai", actor_label: "Nexa Copilot", action: "ai.plan_generated", summary: "Generated 3-step resolution plan", detail: null },
      { id: "a2", at: new Date().toISOString(), actor_type: "system", actor_label: "System", action: "ticket.created", summary: "Ticket created from the AI assistant", detail: null },
    ]);
    api.tickets.comments.list.mockResolvedValue([]);
    api.tickets.related.mockResolvedValue({ similar_incidents: [], knowledge: [] });
    api.admin.teams.mockResolvedValue([{ id: "t-net", name: "Network", description: null, is_service_desk: false, member_count: 3, l1_count: 2, l2_count: 1 }]);
  });

  it("shows the user problem, AI diagnosis with evidence, and the plan", async () => {
    const user = userEvent.setup();
    renderWorkspace();
    expect(await screen.findByRole("heading", { name: "VPN Connection Failure" })).toBeInTheDocument();
    expect(screen.getByText(/stopped working this morning/)).toBeInTheDocument();
    expect(screen.getByText("Err: CERT_AUTHORITY_INVALID")).toBeInTheDocument();
    expect(screen.getByText("VPN authentication certificate may have expired.")).toBeInTheDocument();
    expect(screen.getByText("high confidence")).toBeInTheDocument();
    expect(screen.getByText("AI suggested — engineer executes")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /why this was suggested/i }));
    expect(screen.getByText("KB-102")).toBeInTheDocument();
    expect(screen.getByText(/Describes CERT_AUTHORITY_INVALID/)).toBeInTheDocument();

    // Commands stay behind a disclosure.
    expect(screen.queryByText(/security find-certificate/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /view technical details/i }));
    expect(screen.getByText(/security find-certificate/)).toBeInTheDocument();
    expect(screen.getByText("Nexa Copilot")).toBeInTheDocument();
  });

  it("marks the current step complete", async () => {
    const user = userEvent.setup();
    const updated = ticketDetail().steps.map((s) => (s.id === "st-2" ? { ...s, status: "completed" as const, is_current: false } : s));
    api.tickets.steps.update.mockResolvedValue(updated);
    renderWorkspace();
    await user.click(await screen.findByRole("button", { name: "Mark complete" }));
    expect(api.tickets.steps.update).toHaveBeenCalledWith("tk-1", "st-2", { status: "completed" });
  });

  it("edits a step", async () => {
    const user = userEvent.setup();
    api.tickets.steps.update.mockResolvedValue(ticketDetail().steps);
    renderWorkspace();
    const current = await screen.findByTestId("step-st-2");
    await user.click(within(current).getByRole("button", { name: "Edit" }));
    const input = screen.getByRole("textbox", { name: "Step description" });
    await user.clear(input);
    await user.type(input, "Re-push certificate profile via MDM");
    await user.click(screen.getByRole("button", { name: "Save step" }));
    await waitFor(() =>
      expect(api.tickets.steps.update).toHaveBeenCalledWith("tk-1", "st-2", expect.objectContaining({ description: "Re-push certificate profile via MDM" })),
    );
  });

  it("escalates to L2 with a reason and note", async () => {
    const user = userEvent.setup();
    api.tickets.escalate.mockResolvedValue(ticketDetail({ status: "escalated", status_label: "Escalated", support_level: "L2" }));
    renderWorkspace();
    await user.click(await screen.findByRole("button", { name: /escalate/i }));
    const dialog = await screen.findByRole("dialog", { name: "Escalate incident" });
    await user.selectOptions(within(dialog).getByLabelText("Reason for escalation"), "requires_elevated_access");
    await user.type(within(dialog).getByLabelText(/note for l2/i), "Needs gateway access");
    expect(within(dialog).getByText(/Moves with the ticket/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Confirm escalation" }));
    expect(api.tickets.escalate).toHaveBeenCalledWith("tk-1", { reason: "requires_elevated_access", note: "Needs gateway access", target_team_id: "t-net" });
  });

  it("resolves with the editable AI draft", async () => {
    const user = userEvent.setup();
    api.tickets.resolutionDraft.mockResolvedValue({ resolution_summary: "Client certificate expired; renewed via MDM and verified.", employee_summary: "Your certificate was renewed.", generated: true });
    api.tickets.resolve.mockResolvedValue(ticketDetail({ status: "resolved", status_label: "Resolved" }));
    renderWorkspace();
    await user.click(await screen.findByRole("button", { name: /resolve incident/i }));
    const dialog = await screen.findByRole("dialog", { name: /resolve incident INC-10234/i });
    const textarea = within(dialog).getByRole("textbox");
    await waitFor(() => expect(textarea).toHaveValue("Client certificate expired; renewed via MDM and verified."));
    await user.type(textarea, " Tested with the user.");
    await user.click(within(dialog).getByRole("button", { name: "Resolve incident" }));
    expect(api.tickets.resolve).toHaveBeenCalledWith("tk-1", {
      resolution_summary: "Client certificate expired; renewed via MDM and verified. Tested with the user.",
      resolution_code: "fixed",
    });
  });

  it("hides work controls when the engineer can only view", async () => {
    api.tickets.get.mockResolvedValue(ticketDetail({ permissions: { ...ticketDetail().permissions, can_work: false, can_escalate: false, can_resolve: false, can_self_assign: true } }));
    renderWorkspace();
    expect(await screen.findByRole("button", { name: /assign to me/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /resolve incident/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Mark complete" })).not.toBeInTheDocument();
  });
});
