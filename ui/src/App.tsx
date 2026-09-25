import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router";
import { useAuth } from "@/auth/AuthProvider";
import { HomeRedirect, RequireAuth, RequireRole } from "@/auth/guards";
import { AppShell } from "@/components/AppShell";
import { EmptyState, LoadingState, NexaMark } from "@/components/ui";
import { AuthCallbackPage, LoginPage } from "@/pages/LoginPage";

// Route-level code splitting: each screen loads on first visit.
const named = <K extends string>(loader: () => Promise<Record<K, React.ComponentType<never>>>, key: K) =>
  lazy(async () => ({ default: (await loader())[key] as React.ComponentType }));

const LandingPage = lazy(() => import("@/pages/LandingPage"));
const AssistantPage = named(() => import("@/pages/AssistantPage"), "AssistantPage");
const DispatchPage = named(() => import("@/pages/DispatchPage"), "DispatchPage");
const KnowledgeListPage = named(() => import("@/pages/KnowledgePage"), "KnowledgeListPage");
const ArticlePage = named(() => import("@/pages/KnowledgePage"), "ArticlePage");
const ArticleEditorPage = named(() => import("@/pages/KnowledgePage"), "ArticleEditorPage");
const MyTicketsPage = named(() => import("@/pages/MyTicketsPage"), "MyTicketsPage");
const EmployeeTicketPage = named(() => import("@/pages/MyTicketsPage"), "EmployeeTicketPage");
const ServicesPage = named(() => import("@/pages/ServicesPage"), "ServicesPage");
const TicketListPage = lazy(async () => ({ default: (await import("@/pages/TicketListPage")).TicketListPage }));
const TicketWorkspacePage = named(() => import("@/pages/workspace/TicketWorkspacePage"), "TicketWorkspacePage");
const SettingsLayout = named(() => import("@/pages/settings/SettingsLayout"), "SettingsLayout");
const AiSettingsPage = named(() => import("@/pages/settings/AiSettingsPage"), "AiSettingsPage");
const TeamsUsersPage = named(() => import("@/pages/settings/AdminPages"), "TeamsUsersPage");
const AssignmentRulesPage = named(() => import("@/pages/settings/AdminPages"), "AssignmentRulesPage");
const SlaPoliciesPage = named(() => import("@/pages/settings/AdminPages"), "SlaPoliciesPage");
const KnowledgeSourcesPage = named(() => import("@/pages/settings/AdminPages"), "KnowledgeSourcesPage");
const IntegrationsPage = named(() => import("@/pages/settings/AdminPages"), "IntegrationsPage");
const SecurityPage = named(() => import("@/pages/settings/AdminPages"), "SecurityPage");
const AuditLogPage = named(() => import("@/pages/settings/AdminPages"), "AuditLogPage");
const ProfilePage = named(() => import("@/pages/settings/AdminPages"), "ProfilePage");

const STAFF = ["engineer", "admin"] as const;

function SettingsIndex() {
  const { me } = useAuth();
  return <Navigate to={me?.role === "employee" ? "/settings/profile" : "/settings/ai"} replace />;
}

function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-space-md">
      <NexaMark size={36} />
      <EmptyState icon="explore_off" title="Page not found" message="That page doesn't exist or you don't have access to it." />
    </div>
  );
}

const staff = (el: ReactNode) => <RequireRole roles={[...STAFF]}>{el}</RequireRole>;
const admin = (el: ReactNode) => <RequireRole roles={["admin"]}>{el}</RequireRole>;

export function App() {
  return (
    <Suspense fallback={<LoadingState label="Loading…" className="min-h-[50vh]" />}>
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<LoginPage mode="signup" />} />
      <Route path="/auth/callback" element={<AuthCallbackPage />} />
      <Route path="/app" element={<RequireAuth><HomeRedirect /></RequireAuth>} />
      <Route element={<RequireAuth><AppShell /></RequireAuth>}>
        <Route path="/assistant" element={<AssistantPage />} />
        <Route path="/my-tickets" element={<MyTicketsPage />} />
        <Route path="/my-tickets/:ticketId" element={<EmployeeTicketPage />} />
        <Route path="/dispatch" element={staff(<DispatchPage />)} />
        <Route path="/tickets/mine" element={staff(<TicketListPage kind="mine" />)} />
        <Route path="/tickets/incidents" element={staff(<TicketListPage kind="incidents" />)} />
        <Route path="/tickets/requests" element={staff(<TicketListPage kind="requests" />)} />
        <Route path="/tickets/changes" element={staff(<TicketListPage kind="changes" />)} />
        <Route path="/tickets/:ticketId" element={staff(<TicketWorkspacePage />)} />
        <Route path="/knowledge" element={<KnowledgeListPage />} />
        <Route path="/knowledge/new" element={staff(<ArticleEditorPage />)} />
        <Route path="/knowledge/:articleId" element={<ArticlePage />} />
        <Route path="/knowledge/:articleId/edit" element={staff(<ArticleEditorPage />)} />
        <Route path="/services" element={staff(<ServicesPage />)} />
        <Route path="/settings" element={<SettingsLayout />}>
          <Route index element={<SettingsIndex />} />
          <Route path="ai" element={staff(<AiSettingsPage />)} />
          <Route path="teams" element={staff(<TeamsUsersPage />)} />
          <Route path="rules" element={staff(<AssignmentRulesPage />)} />
          <Route path="sla" element={staff(<SlaPoliciesPage />)} />
          <Route path="knowledge-sources" element={staff(<KnowledgeSourcesPage />)} />
          <Route path="integrations" element={admin(<IntegrationsPage />)} />
          <Route path="security" element={staff(<SecurityPage />)} />
          <Route path="audit" element={admin(<AuditLogPage />)} />
          <Route path="profile" element={<ProfilePage />} />
        </Route>
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
    </Suspense>
  );
}
