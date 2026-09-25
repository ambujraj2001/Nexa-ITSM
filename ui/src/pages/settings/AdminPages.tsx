/** Settings: teams & users, assignment rules, SLA, knowledge sources, integrations, security, audit, profile. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router";
import { useAuth } from "@/auth/AuthProvider";
import { useToast } from "@/components/Toast";
import { EmptyState, ErrorState, FieldLabel, Icon, LoadingState, Modal, Spinner, Toggle } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { relative, shortDate } from "@/lib/format";
import type { AssignmentRule, AssignmentRuleWrite, Priority, Role, RoutingPreview, SlaPolicy, TicketType } from "@/lib/types";
import { SettingsHeader } from "./SettingsLayout";

const CATEGORIES = ["Network", "Access", "Email & Collaboration", "Hardware", "Software", "Security", "Infrastructure", "Other"];

function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={clsx("overflow-hidden rounded-xl bg-surface-container-lowest shadow-sm", className)}>{children}</div>;
}

// ── Teams & Users ──────────────────────────────────────────────────────────

function InviteModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const teams = useQuery({ queryKey: ["teams"], queryFn: api.admin.teams, enabled: open });
  const [form, setForm] = useState({ email: "", name: "", role: "employee" as Role, engineer_level: "L1", team_id: "" });
  const invite = useMutation({
    mutationFn: () => api.admin.invite({ email: form.email.trim(), name: form.name.trim(), role: form.role, engineer_level: form.role === "employee" ? null : form.engineer_level, team_id: form.team_id || null }),
    onSuccess: (u) => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
      toast(`Invitation sent to ${u.email}`);
      onClose();
    },
    onError: (e) => toast(errorMessage(e), "error"),
  });
  return (
    <Modal open={open} onClose={onClose} title="Invite a user" footer={<><button type="button" className="btn-ghost h-8 px-3" onClick={onClose}>Cancel</button><button type="button" className="btn-primary h-8 px-4" disabled={invite.isPending || !form.email || !form.name} onClick={() => invite.mutate()}>{invite.isPending ? <Spinner className="border-t-white" /> : "Send invite"}</button></>}>
      <div className="flex flex-col gap-space-xs"><FieldLabel htmlFor="inv-name">Name</FieldLabel><input id="inv-name" className="input h-9" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
      <div className="flex flex-col gap-space-xs"><FieldLabel htmlFor="inv-email">Work email</FieldLabel><input id="inv-email" type="email" className="input h-9" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
      <div className="grid grid-cols-3 gap-space-sm">
        <div className="flex flex-col gap-space-xs"><FieldLabel htmlFor="inv-role">Role</FieldLabel><select id="inv-role" className="input h-9" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })}><option value="employee">Employee</option><option value="engineer">Engineer</option><option value="admin">Admin</option></select></div>
        <div className="flex flex-col gap-space-xs"><FieldLabel htmlFor="inv-level">Level</FieldLabel><select id="inv-level" className="input h-9" disabled={form.role === "employee"} value={form.engineer_level} onChange={(e) => setForm({ ...form, engineer_level: e.target.value })}><option>L1</option><option>L2</option></select></div>
        <div className="flex flex-col gap-space-xs"><FieldLabel htmlFor="inv-team">Team</FieldLabel><select id="inv-team" className="input h-9" value={form.team_id} onChange={(e) => setForm({ ...form, team_id: e.target.value })}><option value="">—</option>{teams.data?.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></div>
      </div>
    </Modal>
  );
}

export function TeamsUsersPage() {
  const { me } = useAuth();
  const admin = me?.role === "admin";
  const toast = useToast();
  const queryClient = useQueryClient();
  const [q, setQ] = useState("");
  const [inviting, setInviting] = useState(false);
  const [teamForm, setTeamForm] = useState<{ id?: string; name: string; description: string; is_service_desk: boolean } | null>(null);
  const teams = useQuery({ queryKey: ["teams"], queryFn: api.admin.teams });
  const users = useQuery({ queryKey: ["admin", "users", q], queryFn: () => api.admin.users({ q: q || undefined }), enabled: admin });
  const update = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) => api.admin.updateUser(id, body),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ["admin", "users"] }); void queryClient.invalidateQueries({ queryKey: ["teams"] }); toast("User updated"); },
    onError: (e) => toast(errorMessage(e), "error"),
  });
  const saveTeam = useMutation({
    mutationFn: () => (teamForm?.id ? api.admin.updateTeam(teamForm.id, teamForm) : api.admin.createTeam(teamForm!)),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ["teams"] }); setTeamForm(null); toast("Team saved"); },
    onError: (e) => toast(errorMessage(e), "error"),
  });
  return (
    <main className="flex flex-col gap-space-xl">
      <SettingsHeader title="Teams & Users" description="Who can resolve tickets, which team they belong to, and who handles escalations (L2)." />
      <section className="flex flex-col gap-space-md">
        <div className="flex items-center justify-between">
          <h3 className="font-headline-md text-headline-md font-semibold text-on-surface">Teams</h3>
          {admin && <button type="button" className="btn-ghost h-8 px-3" onClick={() => setTeamForm({ name: "", description: "", is_service_desk: false })}><Icon name="add" className="text-[16px]" /> New team</button>}
        </div>
        {teams.isLoading && <LoadingState />}
        {teams.isError && <ErrorState title="Unable to load teams." onRetry={() => void teams.refetch()} />}
        <Card>
          {teams.data?.map((t) => (
            <div key={t.id} className="flex items-center justify-between gap-space-md border-b border-surface-container-low px-space-lg py-space-md last:border-b-0">
              <div className="flex flex-col">
                <span className="flex items-center gap-space-xs font-body-md text-body-md font-medium text-on-surface">{t.name}{t.is_service_desk && <span className="chip bg-secondary-fixed text-on-secondary-fixed-variant">Service desk</span>}</span>
                <span className="font-body-sm text-body-sm text-on-surface-variant">{t.description ?? "—"}</span>
              </div>
              <div className="flex items-center gap-space-md font-label-code text-label-code text-on-surface-variant">
                <span>{t.member_count} people</span><span>L1 {t.l1_count}</span><span>L2 {t.l2_count}</span>
                {admin && <button type="button" className="btn-ghost h-7 px-2" onClick={() => setTeamForm({ id: t.id, name: t.name, description: t.description ?? "", is_service_desk: t.is_service_desk })}>Edit</button>}
              </div>
            </div>
          ))}
        </Card>
      </section>
      {admin && (
        <section className="flex flex-col gap-space-md">
          <div className="flex flex-wrap items-center justify-between gap-space-sm">
            <h3 className="font-headline-md text-headline-md font-semibold text-on-surface">Users</h3>
            <div className="flex items-center gap-space-sm">
              <input className="input h-8 w-56" placeholder="Search people" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search people" />
              <button type="button" className="btn-primary h-8 px-3" onClick={() => setInviting(true)}><Icon name="person_add" className="text-[16px]" /> Invite</button>
            </div>
          </div>
          {users.isLoading && <LoadingState />}
          {users.isError && <ErrorState title="Unable to load users." message={errorMessage(users.error)} />}
          <Card>
            <div className="w-full overflow-x-auto">
              <table className="w-full border-collapse text-left">
                <thead><tr className="bg-surface-container-low/60 font-label-caps text-label-caps uppercase tracking-wider text-on-surface-variant"><th className="px-space-lg py-space-md">Person</th><th className="px-space-md py-space-md">Role</th><th className="px-space-md py-space-md">Level</th><th className="px-space-md py-space-md">Team</th><th className="px-space-lg py-space-md text-right">Active</th></tr></thead>
                <tbody className="font-body-md text-body-md">
                  {users.data?.map((u) => (
                    <tr key={u.id} className="border-t border-surface-container-low">
                      <td className="px-space-lg py-space-sm"><div className="flex flex-col"><span className="font-medium text-on-surface">{u.name}</span><span className="font-body-sm text-body-sm text-on-surface-variant">{u.email}{!u.has_login && " · invited"}</span></div></td>
                      <td className="px-space-md py-space-sm"><select aria-label={`Role for ${u.name}`} className="input h-8 w-32" value={u.role} disabled={u.id === me?.id} onChange={(e) => update.mutate({ id: u.id, body: { role: e.target.value, ...(e.target.value === "employee" ? { clear_engineer_level: true } : u.engineer_level ? {} : { engineer_level: "L1" }) } })}><option value="employee">Employee</option><option value="engineer">Engineer</option><option value="admin">Admin</option></select></td>
                      <td className="px-space-md py-space-sm"><select aria-label={`Level for ${u.name}`} className="input h-8 w-24" value={u.engineer_level ?? ""} disabled={u.role === "employee"} onChange={(e) => update.mutate({ id: u.id, body: e.target.value ? { engineer_level: e.target.value } : { clear_engineer_level: true } })}><option value="">—</option><option>L1</option><option>L2</option></select></td>
                      <td className="px-space-md py-space-sm"><select aria-label={`Team for ${u.name}`} className="input h-8 w-40" value={u.team?.id ?? ""} onChange={(e) => update.mutate({ id: u.id, body: e.target.value ? { team_id: e.target.value } : { clear_team: true } })}><option value="">—</option>{teams.data?.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></td>
                      <td className="px-space-lg py-space-sm text-right"><Toggle checked={u.is_active} disabled={u.id === me?.id} onChange={(v) => update.mutate({ id: u.id, body: { is_active: v } })} label={`${u.name} active`} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </section>
      )}
      <InviteModal open={inviting} onClose={() => setInviting(false)} />
      <Modal open={Boolean(teamForm)} onClose={() => setTeamForm(null)} title={teamForm?.id ? "Edit team" : "New team"} footer={<><button type="button" className="btn-ghost h-8 px-3" onClick={() => setTeamForm(null)}>Cancel</button><button type="button" className="btn-primary h-8 px-4" disabled={!teamForm?.name.trim() || saveTeam.isPending} onClick={() => saveTeam.mutate()}>Save</button></>}>
        {teamForm && (
          <>
            <div className="flex flex-col gap-space-xs"><FieldLabel htmlFor="team-name">Name</FieldLabel><input id="team-name" className="input h-9" value={teamForm.name} onChange={(e) => setTeamForm({ ...teamForm, name: e.target.value })} /></div>
            <div className="flex flex-col gap-space-xs"><FieldLabel htmlFor="team-desc">Description</FieldLabel><input id="team-desc" className="input h-9" value={teamForm.description} onChange={(e) => setTeamForm({ ...teamForm, description: e.target.value })} /></div>
            <label className="flex items-center gap-space-sm font-body-md text-body-md text-on-surface"><input type="checkbox" className="accent-primary" checked={teamForm.is_service_desk} onChange={(e) => setTeamForm({ ...teamForm, is_service_desk: e.target.checked })} /> Service desk (default intake queue)</label>
          </>
        )}
      </Modal>
    </main>
  );
}

// ── Assignment rules ───────────────────────────────────────────────────────

const EMPTY_RULE: AssignmentRuleWrite = { name: "", category: "", subcategory: "", priority: null, ticket_type: null, service_id: null, team_id: "", support_level: "L1", sort_order: 100, enabled: true };

export function AssignmentRulesPage() {
  const { me } = useAuth();
  const admin = me?.role === "admin";
  const toast = useToast();
  const queryClient = useQueryClient();
  const rules = useQuery({ queryKey: ["rules"], queryFn: api.rules.list });
  const teams = useQuery({ queryKey: ["teams"], queryFn: api.admin.teams });
  const [editing, setEditing] = useState<{ id?: string; body: AssignmentRuleWrite } | null>(null);
  const [preview, setPreview] = useState<{ category: string; subcategory: string; priority: Priority | "" }>({ category: "Network", subcategory: "VPN", priority: "" });
  const [result, setResult] = useState<RoutingPreview | null>(null);
  const invalidate = () => void queryClient.invalidateQueries({ queryKey: ["rules"] });
  const save = useMutation({
    mutationFn: () => {
      const body = { ...editing!.body, category: editing!.body.category || null, subcategory: editing!.body.subcategory || null };
      return editing!.id ? api.rules.update(editing!.id, body) : api.rules.create(body);
    },
    onSuccess: () => { invalidate(); setEditing(null); toast("Rule saved"); },
    onError: (e) => toast(errorMessage(e), "error"),
  });
  const remove = useMutation({ mutationFn: (id: string) => api.rules.remove(id), onSuccess: () => { invalidate(); toast("Rule deleted"); }, onError: (e) => toast(errorMessage(e), "error") });
  const toggle = useMutation({
    mutationFn: (r: AssignmentRule) => api.rules.update(r.id, { name: r.name, category: r.category, subcategory: r.subcategory, priority: r.priority, ticket_type: r.ticket_type, service_id: r.service?.id ?? null, team_id: r.team.id, support_level: r.support_level, sort_order: r.sort_order, enabled: !r.enabled }),
    onSuccess: invalidate,
    onError: (e) => toast(errorMessage(e), "error"),
  });
  const run = useMutation({ mutationFn: () => api.rules.preview({ category: preview.category || undefined, subcategory: preview.subcategory || undefined, priority: preview.priority || undefined }), onSuccess: setResult, onError: (e) => toast(errorMessage(e), "error") });
  const edit = (r?: AssignmentRule) =>
    setEditing(r ? { id: r.id, body: { name: r.name, category: r.category ?? "", subcategory: r.subcategory ?? "", priority: r.priority, ticket_type: r.ticket_type, service_id: r.service?.id ?? null, team_id: r.team.id, support_level: r.support_level, sort_order: r.sort_order, enabled: r.enabled } } : { body: { ...EMPTY_RULE, team_id: teams.data?.[0]?.id ?? "" } });

  return (
    <main className="flex flex-col gap-space-xl">
      <SettingsHeader title="Assignment Rules" description="Deterministic routing. Rules always win over AI recommendations; unmatched tickets go to the service owner, then the AI-recommended team, then the service desk." />
      <section className="flex flex-col gap-space-md">
        <div className="flex items-center justify-between">
          <h3 className="font-headline-md text-headline-md font-semibold text-on-surface">Rules</h3>
          {admin && <button type="button" className="btn-ghost h-8 px-3" onClick={() => edit()}><Icon name="add" className="text-[16px]" /> New rule</button>}
        </div>
        {rules.isLoading && <LoadingState />}
        {rules.isError && <ErrorState title="Unable to load rules." onRetry={() => void rules.refetch()} />}
        {rules.data?.length === 0 && <EmptyState icon="rule_folder" title="No rules yet" message="Without rules, tickets route to service owners and the service desk." />}
        {rules.data && rules.data.length > 0 && (
          <Card>
            {rules.data.map((r) => (
              <div key={r.id} className={clsx("flex items-center justify-between gap-space-md border-b border-surface-container-low px-space-lg py-space-md last:border-b-0", !r.enabled && "opacity-60")}>
                <div className="flex min-w-0 flex-col">
                  <span className="font-body-md text-body-md font-medium text-on-surface">{r.name}</span>
                  <span className="font-body-sm text-body-sm text-on-surface-variant">
                    {[r.category, r.subcategory, r.priority, r.ticket_type?.replace("_", " "), r.service?.name].filter(Boolean).join(" · ") || "Any"} → <span className="font-medium text-on-surface">{r.team.name}</span> ({r.support_level})
                  </span>
                </div>
                <div className="flex shrink-0 items-center gap-space-sm">
                  <span className="font-label-code text-[11px] text-outline">order {r.sort_order}</span>
                  {admin && (
                    <>
                      <Toggle checked={r.enabled} onChange={() => toggle.mutate(r)} label={`${r.name} enabled`} />
                      <button type="button" className="btn-ghost h-7 px-2" onClick={() => edit(r)}>Edit</button>
                      <button type="button" className="btn-ghost h-7 px-2 text-error" onClick={() => remove.mutate(r.id)} aria-label={`Delete ${r.name}`}><Icon name="delete" className="text-[16px]" /></button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </Card>
        )}
      </section>
      <section className="flex flex-col gap-space-md">
        <h3 className="font-headline-md text-headline-md font-semibold text-on-surface">Test routing</h3>
        <Card className="flex flex-col gap-space-md p-space-lg">
          <div className="grid grid-cols-1 gap-space-sm sm:grid-cols-4">
            <select aria-label="Category" className="input h-9" value={preview.category} onChange={(e) => setPreview({ ...preview, category: e.target.value })}>{CATEGORIES.map((c) => <option key={c}>{c}</option>)}</select>
            <input aria-label="Subcategory" className="input h-9" placeholder="Subcategory" value={preview.subcategory} onChange={(e) => setPreview({ ...preview, subcategory: e.target.value })} />
            <select aria-label="Priority" className="input h-9" value={preview.priority} onChange={(e) => setPreview({ ...preview, priority: e.target.value as Priority | "" })}><option value="">Any priority</option>{["P1", "P2", "P3", "P4"].map((p) => <option key={p}>{p}</option>)}</select>
            <button type="button" className="btn-primary h-9" onClick={() => run.mutate()} disabled={run.isPending}>{run.isPending ? <Spinner className="border-t-white" /> : "Preview"}</button>
          </div>
          {result && (
            <p className="rounded-lg bg-surface-container-low px-space-md py-space-sm font-body-md text-body-md text-on-surface">
              → <span className="font-medium">{result.team?.name ?? "No team"}</span> ({result.support_level}){result.engineer ? ` · next engineer: ${result.engineer.name}` : " · team queue"}
              <span className="block font-body-sm text-body-sm text-on-surface-variant">Basis: {result.rule_name ? `rule “${result.rule_name}”` : result.reason.replace(/_/g, " ")}</span>
            </p>
          )}
        </Card>
      </section>
      <Modal open={Boolean(editing)} onClose={() => setEditing(null)} title={editing?.id ? "Edit rule" : "New rule"} width="max-w-lg" footer={<><button type="button" className="btn-ghost h-8 px-3" onClick={() => setEditing(null)}>Cancel</button><button type="button" className="btn-primary h-8 px-4" disabled={save.isPending || !editing?.body.name || !editing?.body.team_id} onClick={() => save.mutate()}>Save rule</button></>}>
        {editing && (
          <div className="grid grid-cols-2 gap-space-sm">
            <div className="col-span-2 flex flex-col gap-space-xs"><FieldLabel htmlFor="rule-name">Name</FieldLabel><input id="rule-name" className="input h-9" value={editing.body.name} onChange={(e) => setEditing({ ...editing, body: { ...editing.body, name: e.target.value } })} /></div>
            <div className="flex flex-col gap-space-xs"><FieldLabel htmlFor="rule-cat">Category</FieldLabel><select id="rule-cat" className="input h-9" value={editing.body.category ?? ""} onChange={(e) => setEditing({ ...editing, body: { ...editing.body, category: e.target.value } })}><option value="">Any</option>{CATEGORIES.map((c) => <option key={c}>{c}</option>)}</select></div>
            <div className="flex flex-col gap-space-xs"><FieldLabel htmlFor="rule-sub">Subcategory</FieldLabel><input id="rule-sub" className="input h-9" value={editing.body.subcategory ?? ""} onChange={(e) => setEditing({ ...editing, body: { ...editing.body, subcategory: e.target.value } })} placeholder="Any" /></div>
            <div className="flex flex-col gap-space-xs"><FieldLabel htmlFor="rule-pri">Priority</FieldLabel><select id="rule-pri" className="input h-9" value={editing.body.priority ?? ""} onChange={(e) => setEditing({ ...editing, body: { ...editing.body, priority: (e.target.value || null) as Priority | null } })}><option value="">Any</option>{["P1", "P2", "P3", "P4"].map((p) => <option key={p}>{p}</option>)}</select></div>
            <div className="flex flex-col gap-space-xs"><FieldLabel htmlFor="rule-type">Type</FieldLabel><select id="rule-type" className="input h-9" value={editing.body.ticket_type ?? ""} onChange={(e) => setEditing({ ...editing, body: { ...editing.body, ticket_type: (e.target.value || null) as TicketType | null } })}><option value="">Any</option><option value="incident">Incident</option><option value="service_request">Request</option><option value="change">Change</option><option value="problem">Problem</option></select></div>
            <div className="flex flex-col gap-space-xs"><FieldLabel htmlFor="rule-team">Team</FieldLabel><select id="rule-team" className="input h-9" value={editing.body.team_id} onChange={(e) => setEditing({ ...editing, body: { ...editing.body, team_id: e.target.value } })}>{teams.data?.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></div>
            <div className="flex flex-col gap-space-xs"><FieldLabel htmlFor="rule-level">Level</FieldLabel><select id="rule-level" className="input h-9" value={editing.body.support_level} onChange={(e) => setEditing({ ...editing, body: { ...editing.body, support_level: e.target.value as "L1" | "L2" } })}><option>L1</option><option>L2</option></select></div>
            <div className="flex flex-col gap-space-xs"><FieldLabel htmlFor="rule-order">Order</FieldLabel><input id="rule-order" type="number" className="input h-9" value={editing.body.sort_order} onChange={(e) => setEditing({ ...editing, body: { ...editing.body, sort_order: Number(e.target.value) } })} /></div>
          </div>
        )}
      </Modal>
    </main>
  );
}

// ── SLA policies ───────────────────────────────────────────────────────────

function SlaRow({ policy, editable }: { policy: SlaPolicy; editable: boolean }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [response, setResponse] = useState(policy.response_time_minutes);
  const [resolution, setResolution] = useState(policy.resolution_time_minutes);
  useEffect(() => { setResponse(policy.response_time_minutes); setResolution(policy.resolution_time_minutes); }, [policy]);
  const save = useMutation({
    mutationFn: () => api.settings.updateSla(policy.id, { response_time_minutes: response, resolution_time_minutes: resolution }),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ["sla"] }); toast(`${policy.priority} SLA saved — applies to new and re-prioritised tickets`); },
    onError: (e) => toast(errorMessage(e), "error"),
  });
  const dirty = response !== policy.response_time_minutes || resolution !== policy.resolution_time_minutes;
  return (
    <div className="flex flex-wrap items-center justify-between gap-space-md border-b border-surface-container-low px-space-lg py-space-md last:border-b-0">
      <div className="flex flex-col"><span className="font-body-md text-body-md font-medium text-on-surface">{policy.name}</span><span className="font-body-sm text-body-sm text-on-surface-variant">Updated {relative(policy.updated_at)}</span></div>
      <div className="flex items-center gap-space-md font-body-sm text-body-sm text-on-surface-variant">
        <label className="flex items-center gap-1">Response<input type="number" min={1} disabled={!editable} className="input h-8 w-20" value={response} onChange={(e) => setResponse(Number(e.target.value))} />min</label>
        <label className="flex items-center gap-1">Resolution<input type="number" min={1} disabled={!editable} className="input h-8 w-24" value={resolution} onChange={(e) => setResolution(Number(e.target.value))} />min</label>
        {editable && <button type="button" className="btn-primary h-8 px-3" disabled={!dirty || save.isPending} onClick={() => save.mutate()}>Save</button>}
      </div>
    </div>
  );
}

export function SlaPoliciesPage() {
  const { me } = useAuth();
  const query = useQuery({ queryKey: ["sla"], queryFn: api.settings.slaPolicies });
  return (
    <main className="flex flex-col gap-space-xl">
      <SettingsHeader title="SLA Policies" description="Response and resolution targets by priority, in calendar minutes (24×7). Due dates are calculated when a ticket is created or re-prioritised." />
      {query.isLoading && <LoadingState />}
      {query.isError && <ErrorState title="Unable to load SLA policies." onRetry={() => void query.refetch()} />}
      <Card>{query.data?.map((p) => <SlaRow key={p.id} policy={p} editable={me?.role === "admin"} />)}</Card>
    </main>
  );
}

// ── Knowledge sources & integrations ──────────────────────────────────────

export function KnowledgeSourcesPage() {
  const { me } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["settings", "ai"], queryFn: api.settings.ai });
  const toggle = useMutation({ mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => api.settings.updateKnowledgeSource(id, enabled), onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["settings", "ai"] }), onError: (e) => toast(errorMessage(e), "error") });
  const reindex = useMutation({ mutationFn: api.settings.reindex, onSuccess: (r) => toast(`Re-indexing ${r.articles} articles and ${r.incidents} incidents`), onError: (e) => toast(errorMessage(e), "error") });
  const admin = me?.role === "admin";
  return (
    <main className="flex flex-col gap-space-xl">
      <SettingsHeader title="Knowledge Sources" description="What the AI may search as evidence. Disabling a source removes it from investigations immediately." />
      {query.isLoading && <LoadingState />}
      {query.data && (
        <Card>
          {query.data.knowledge_sources.map((k) => (
            <div key={k.id} className="flex items-center justify-between gap-space-md border-b border-surface-container-low px-space-lg py-space-md last:border-b-0">
              <div className="flex flex-col"><span className="font-body-md text-body-md font-medium text-on-surface">{k.name}</span><span className="font-body-sm text-body-sm text-on-surface-variant">{k.description} · {k.item_count} items · {k.indexed_count} indexed</span></div>
              <Toggle checked={k.enabled} disabled={!admin} onChange={(v) => toggle.mutate({ id: k.id, enabled: v })} label={`${k.name} enabled`} />
            </div>
          ))}
        </Card>
      )}
      {admin && <button type="button" className="btn-ghost h-8 self-start px-3" onClick={() => reindex.mutate()} disabled={reindex.isPending}><Icon name="sync" className="text-[16px]" /> Re-index missing items</button>}
      <p className="font-body-sm text-body-sm text-on-surface-variant">Semantic search uses {query.data?.models.embedding_model ?? "no embedding model (full-text only)"}. Manage articles in <Link to="/knowledge" className="font-medium text-on-surface underline">Knowledge</Link>.</p>
    </main>
  );
}

export function IntegrationsPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["settings", "ai"], queryFn: api.settings.ai });
  const update = useMutation({ mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => api.settings.updateIntegration(id, { enabled }), onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["settings", "ai"] }), onError: (e) => toast(errorMessage(e), "error") });
  return (
    <main className="flex flex-col gap-space-xl">
      <SettingsHeader title="Integrations" description="Connectors are configured with non-secret settings here; credentials stay in the server environment and are referenced by name." />
      {query.isLoading && <LoadingState />}
      {query.data && (
        <Card>
          {query.data.integrations.map((i) => (
            <div key={i.id} className="flex items-center justify-between gap-space-md border-b border-surface-container-low px-space-lg py-space-md last:border-b-0">
              <div className="flex min-w-0 flex-col">
                <span className="flex items-center gap-space-xs font-body-md text-body-md font-medium text-on-surface">{i.display_name}
                  <span className={clsx("chip", i.status === "connected" ? "bg-tertiary-fixed/40 text-on-tertiary-fixed-variant" : "bg-surface-container-high text-on-surface-variant")}>{i.status === "connected" ? "Connected" : i.available ? "Not configured" : "Later release"}</span>
                </span>
                <span className="font-body-sm text-body-sm text-on-surface-variant">{i.description}</span>
                {i.status_detail && <span className="font-label-code text-[11px] text-outline">{i.status_detail}</span>}
              </div>
              <Toggle checked={i.enabled} disabled={!i.available || update.isPending || i.provider === "supabase_auth"} onChange={(v) => update.mutate({ id: i.id, enabled: v })} label={`${i.display_name} enabled`} />
            </div>
          ))}
        </Card>
      )}
    </main>
  );
}

// ── Security & compliance ─────────────────────────────────────────────────

export function SecurityPage() {
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, retry: false });
  const c = health.data?.configured;
  const rows: [string, string, boolean | undefined][] = [
    ["Authentication", "Supabase Auth sessions; every API request's token is verified server-side (JWKS or project secret).", c?.auth],
    ["Authorization", "Role and ticket access are decided by the API from the database — never from the browser. Row Level Security mirrors the rules for direct database access.", true],
    ["Human-in-the-loop", "Automatic infrastructure actions are disabled and human approval is required; both are enforced by the API and a database constraint.", true],
    ["Audit trail", "Every state change is recorded append-only with actor (person, AI or system), old and new values.", true],
    ["Secrets", "Service-role, LiteLLM, Upstash and Axiom credentials live only on the server; the UI build rejects secret-looking public variables.", true],
    ["Telemetry", "OpenTelemetry traces and logs export to Axiom without prompts, message bodies or credentials.", c?.telemetry],
  ];
  return (
    <main className="flex flex-col gap-space-xl">
      <SettingsHeader title="Security & Compliance" description="The controls this workspace enforces today." />
      <Card>
        {rows.map(([title, detail, ok]) => (
          <div key={title} className="flex items-start justify-between gap-space-md border-b border-surface-container-low px-space-lg py-space-md last:border-b-0">
            <div className="flex flex-col"><span className="font-body-md text-body-md font-medium text-on-surface">{title}</span><span className="font-body-sm text-body-sm text-on-surface-variant">{detail}</span></div>
            <span className={clsx("chip shrink-0", ok ? "bg-tertiary-fixed/40 text-on-tertiary-fixed-variant" : "bg-surface-container-high text-on-surface-variant")}>{ok === undefined ? "…" : ok ? "Active" : "Not configured"}</span>
          </div>
        ))}
      </Card>
      {health.data && <p className="font-label-code text-[11px] text-outline">Transient state store: {health.data.configured.redis === "upstash" ? "Upstash Redis" : "in-process (development)"}</p>}
    </main>
  );
}

// ── Audit log ──────────────────────────────────────────────────────────────

export function AuditLogPage() {
  const [actor, setActor] = useState("");
  const [action, setAction] = useState("");
  const [before, setBefore] = useState<string | undefined>();
  const query = useQuery({ queryKey: ["audit", actor, action, before], queryFn: () => api.admin.audit({ actor_type: actor || undefined, action: action || undefined, before, limit: 50 }) });
  const actorTone = { user: "text-on-surface", ai: "text-secondary", system: "text-on-surface-variant" } as const;
  return (
    <main className="flex flex-col gap-space-xl">
      <SettingsHeader title="Audit Log" description="Append-only history of every meaningful change across the workspace." />
      <div className="flex flex-wrap items-center gap-space-sm">
        <select aria-label="Actor" className="input h-8 w-40" value={actor} onChange={(e) => { setActor(e.target.value); setBefore(undefined); }}><option value="">All actors</option><option value="user">People</option><option value="ai">AI</option><option value="system">System</option></select>
        <select aria-label="Action" className="input h-8 w-48" value={action} onChange={(e) => { setAction(e.target.value); setBefore(undefined); }}><option value="">All actions</option><option value="ticket.">Tickets</option><option value="step.">Resolution steps</option><option value="ai.">AI</option><option value="settings.">Settings</option><option value="admin.">Administration</option><option value="knowledge.">Knowledge</option></select>
        {before && <button type="button" className="btn-ghost h-8 px-3" onClick={() => setBefore(undefined)}>Back to latest</button>}
      </div>
      {query.isLoading && <LoadingState />}
      {query.isError && <ErrorState title="Unable to load the audit log." message={errorMessage(query.error)} />}
      {query.data?.length === 0 && <EmptyState icon="receipt_long" title="No events" />}
      {query.data && query.data.length > 0 && (
        <Card>
          {query.data.map((e) => (
            <div key={e.id} className="flex items-baseline gap-space-md border-b border-surface-container-low px-space-lg py-2 font-body-sm text-body-sm last:border-b-0">
              <span className="w-32 shrink-0 font-label-code text-[11px] text-outline">{shortDate(e.created_at)}</span>
              <span className={clsx("w-36 shrink-0 truncate font-medium", actorTone[e.actor_type])}>{e.actor_type === "ai" && <Icon name="auto_awesome" className="mr-0.5 align-[-2px] text-[13px]" />}{e.actor_label}</span>
              <span className="flex-1 text-on-surface-variant">{e.summary}{e.ticket_number && <Link to={`/tickets/${e.ticket_id}`} className="ml-1 font-label-code text-label-code text-on-surface hover:underline">{e.ticket_number}</Link>}</span>
              <span className="hidden font-label-code text-[10px] text-outline md:inline">{e.action}</span>
            </div>
          ))}
        </Card>
      )}
      {query.data && query.data.length === 50 && <button type="button" className="btn-ghost h-8 self-start px-3" onClick={() => setBefore(query.data![query.data!.length - 1].created_at)}>Older events</button>}
    </main>
  );
}

// ── Profile ────────────────────────────────────────────────────────────────

export function ProfilePage() {
  const { me, signOut, refreshMe } = useAuth();
  const toast = useToast();
  const [form, setForm] = useState({ name: me?.name ?? "", job_title: me?.job_title ?? "", department: me?.department ?? "", location: me?.location ?? "" });
  const save = useMutation({ mutationFn: () => api.me.update(form), onSuccess: () => { void refreshMe(); toast("Profile saved"); }, onError: (e) => toast(errorMessage(e), "error") });
  if (!me) return null;
  const submit = (e: FormEvent) => { e.preventDefault(); save.mutate(); };
  return (
    <main className="flex flex-col gap-space-xl">
      <SettingsHeader title="Profile" description="How you appear to IT staff and colleagues." />
      <form onSubmit={submit} className="flex flex-col gap-space-md rounded-xl bg-surface-container-lowest p-space-lg shadow-sm">
        <div className="grid grid-cols-1 gap-space-md sm:grid-cols-2">
          {(["name", "job_title", "department", "location"] as const).map((k) => (
            <div key={k} className="flex flex-col gap-space-xs"><FieldLabel htmlFor={`p-${k}`}>{k.replace("_", " ").replace(/^./, (c) => c.toUpperCase())}</FieldLabel><input id={`p-${k}`} className="input h-9" value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} /></div>
          ))}
        </div>
        <div className="flex flex-wrap items-center justify-between gap-space-sm border-t border-surface-container-low pt-space-md font-body-sm text-body-sm text-on-surface-variant">
          <span>{me.email} · {me.role}{me.engineer_level ? ` · ${me.engineer_level}` : ""}{me.team ? ` · ${me.team.name}` : ""}</span>
          <div className="flex items-center gap-space-sm">
            <button type="button" className="btn-ghost h-8 px-3" onClick={() => void signOut()}>Sign out</button>
            <button type="submit" className="btn-primary h-8 px-4" disabled={save.isPending}>{save.isPending ? <Spinner className="border-t-white" /> : "Save"}</button>
          </div>
        </div>
      </form>
    </main>
  );
}
