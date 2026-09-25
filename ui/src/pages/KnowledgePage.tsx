/** Knowledge base: list/search, article view and editor (staff). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useAuth } from "@/auth/AuthProvider";
import { Markdown } from "@/components/Markdown";
import { useToast } from "@/components/Toast";
import { EmptyState, ErrorState, FieldLabel, Icon, LoadingState, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { relative } from "@/lib/format";
import type { ArticleDetail, ArticleWrite } from "@/lib/types";

const CATEGORIES = ["Network", "Access", "Email & Collaboration", "Hardware", "Software", "Security", "Infrastructure", "Other"];

const INDEX_LABEL: Record<string, string> = { indexed: "Indexed", pending: "Indexing…", failed: "Index failed", skipped: "Not indexed" };

export function KnowledgeListPage() {
  const { me } = useAuth();
  const staff = me?.role !== "employee";
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  useEffect(() => {
    const id = window.setTimeout(() => setSearch(q.trim()), 250);
    return () => window.clearTimeout(id);
  }, [q]);
  const query = useQuery({ queryKey: ["knowledge", search, category, status], queryFn: () => api.knowledge.list({ q: search || undefined, category: category || undefined, status: status || undefined }) });
  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-space-lg px-gutter py-space-xl">
      <div className="flex flex-col justify-between gap-space-md sm:flex-row sm:items-end">
        <div>
          <h1 className="font-headline-lg text-headline-lg font-semibold tracking-tight text-on-surface">Knowledge</h1>
          <p className="font-body-md text-body-md text-on-surface-variant">{staff ? "Articles and runbooks the AI uses as evidence." : "Guides for common IT questions."}</p>
        </div>
        {staff && (
          <Link to="/knowledge/new" className="btn-primary h-9 px-4">
            <Icon name="add" className="text-[16px]" /> New article
          </Link>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-space-sm">
        <div className="relative w-full sm:w-80">
          <Icon name="search" className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[16px] text-on-surface-variant" />
          <input className="input h-9 pl-8" placeholder="Search articles" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search articles" />
        </div>
        <select aria-label="Category" className="input h-9 w-48" value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">All categories</option>
          {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
        </select>
        {staff && (
          <select aria-label="Status" className="input h-9 w-40" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Any status</option>
            <option value="published">Published</option>
            <option value="draft">Draft</option>
            <option value="archived">Archived</option>
          </select>
        )}
      </div>
      {query.isLoading && <LoadingState label="Loading articles…" />}
      {query.isError && <ErrorState title="Unable to load articles." message={errorMessage(query.error)} onRetry={() => void query.refetch()} />}
      {query.data?.length === 0 && <EmptyState icon="library_books" title="No articles found" message={search ? "Try different words." : staff ? "Write the first runbook for your team." : "Ask the assistant instead — it can route your question to IT."} />}
      <div className="flex flex-col divide-y divide-surface-container-low overflow-hidden rounded-xl bg-surface-container-lowest shadow-sm">
        {query.data?.map((a) => (
          <Link key={a.id} to={`/knowledge/${a.id}`} className="flex items-start justify-between gap-space-md px-space-lg py-space-md transition-colors hover:bg-surface-container-low">
            <div className="flex min-w-0 flex-col gap-0.5">
              <div className="flex flex-wrap items-center gap-space-sm">
                <span className="font-label-code text-label-code text-on-surface-variant">{a.article_number}</span>
                <span className="font-body-md text-body-md font-medium text-on-surface">{a.title}</span>
                {a.status !== "published" && <span className="chip bg-surface-container-high text-on-surface-variant">{a.status}</span>}
              </div>
              {a.summary && <p className="truncate font-body-sm text-body-sm text-on-surface-variant">{a.summary}</p>}
            </div>
            <div className="flex shrink-0 flex-col items-end gap-0.5">
              <span className="font-label-code text-[11px] text-outline">Updated {relative(a.updated_at)}</span>
              {staff && <span className={clsx("font-label-code text-[10px]", a.embedding_status === "indexed" ? "text-on-tertiary-container" : "text-outline")}>{INDEX_LABEL[a.embedding_status]}</span>}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

export function ArticlePage() {
  const { articleId = "" } = useParams();
  const { me } = useAuth();
  const query = useQuery({ queryKey: ["article", articleId], queryFn: () => api.knowledge.get(articleId) });
  if (query.isLoading) return <LoadingState label="Loading article…" className="py-24" />;
  if (query.isError || !query.data) return <div className="mx-auto max-w-xl px-gutter py-space-xl"><ErrorState title="Unable to load this article." message={errorMessage(query.error)} /></div>;
  const a = query.data;
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-space-lg px-gutter py-space-xl">
      <div className="flex items-center justify-between">
        <Link to="/knowledge" className="inline-flex items-center gap-1 font-body-sm text-body-sm text-on-surface-variant hover:text-on-surface">
          <Icon name="arrow_back" className="text-[16px]" /> Knowledge
        </Link>
        {me?.role !== "employee" && (
          <Link to={`/knowledge/${a.id}/edit`} className="btn-ghost h-8 px-3"><Icon name="edit" className="text-[16px]" /> Edit</Link>
        )}
      </div>
      <div className="flex flex-col gap-space-xs">
        <div className="flex flex-wrap items-center gap-space-sm font-label-code text-label-code text-on-surface-variant">
          <span>{a.article_number}</span>
          {a.category && <span>· {[a.category, a.subcategory].filter(Boolean).join(" / ")}</span>}
          {a.service && <span>· {a.service.name}</span>}
          <span>· Updated {relative(a.updated_at)}{a.updated_by ? ` by ${a.updated_by.name}` : ""}</span>
        </div>
        <h1 className="font-headline-lg text-headline-lg font-semibold tracking-tight text-on-surface">{a.title}</h1>
        {a.summary && <p className="font-body-lg text-body-lg text-on-surface-variant">{a.summary}</p>}
      </div>
      <article className="rounded-xl bg-surface-container-lowest p-space-lg shadow-sm">
        <Markdown source={a.content} />
      </article>
    </div>
  );
}

export function ArticleEditorPage() {
  const { articleId } = useParams();
  const isNew = !articleId;
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();
  const existing = useQuery({ queryKey: ["article", articleId], queryFn: () => api.knowledge.get(articleId as string), enabled: !isNew });
  const services = useQuery({ queryKey: ["services"], queryFn: api.catalog.services });
  const [form, setForm] = useState<ArticleWrite>({ title: "", summary: "", content: "", category: "", subcategory: "", service_id: null, status: "draft" });
  const [preview, setPreview] = useState(false);
  useEffect(() => {
    const a: ArticleDetail | undefined = existing.data;
    if (a) setForm({ title: a.title, summary: a.summary ?? "", content: a.content, category: a.category ?? "", subcategory: a.subcategory ?? "", service_id: a.service?.id ?? null, status: a.status });
  }, [existing.data]);
  const save = useMutation({
    mutationFn: () => {
      const body = { ...form, category: form.category || null, subcategory: form.subcategory || null, summary: form.summary || null };
      return isNew ? api.knowledge.create(body) : api.knowledge.update(articleId as string, body);
    },
    onSuccess: (a) => {
      void queryClient.invalidateQueries({ queryKey: ["knowledge"] });
      queryClient.setQueryData(["article", a.id], a);
      toast(a.status === "published" ? "Published — indexing for AI retrieval" : "Saved");
      navigate(`/knowledge/${a.id}`);
    },
    onError: (e) => toast(errorMessage(e), "error"),
  });
  const set = <K extends keyof ArticleWrite>(k: K, v: ArticleWrite[K]) => setForm((f) => ({ ...f, [k]: v }));
  const submit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate();
  };
  if (!isNew && existing.isLoading) return <LoadingState label="Loading article…" className="py-24" />;
  return (
    <form onSubmit={submit} className="mx-auto flex w-full max-w-3xl flex-col gap-space-lg px-gutter py-space-xl">
      <div className="flex items-center justify-between">
        <h1 className="font-headline-lg text-headline-lg font-semibold tracking-tight text-on-surface">{isNew ? "New article" : "Edit article"}</h1>
        <div className="flex items-center gap-space-sm">
          <button type="button" className="btn-ghost h-8 px-3" onClick={() => navigate(-1)}>Cancel</button>
          <button type="submit" className="btn-primary h-8 px-4" disabled={save.isPending || form.title.trim().length < 3 || form.content.trim().length < 10}>
            {save.isPending ? <Spinner className="border-t-white" /> : "Save"}
          </button>
        </div>
      </div>
      <div className="flex flex-col gap-space-xs">
        <FieldLabel htmlFor="kb-title">Title</FieldLabel>
        <input id="kb-title" className="input h-9" value={form.title} onChange={(e) => set("title", e.target.value)} maxLength={200} />
      </div>
      <div className="flex flex-col gap-space-xs">
        <FieldLabel htmlFor="kb-summary">Summary</FieldLabel>
        <input id="kb-summary" className="input h-9" value={form.summary ?? ""} onChange={(e) => set("summary", e.target.value)} maxLength={600} />
      </div>
      <div className="grid grid-cols-1 gap-space-md sm:grid-cols-4">
        <div className="flex flex-col gap-space-xs">
          <FieldLabel htmlFor="kb-cat">Category</FieldLabel>
          <select id="kb-cat" className="input h-9" value={form.category ?? ""} onChange={(e) => set("category", e.target.value)}>
            <option value="">—</option>
            {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-space-xs">
          <FieldLabel htmlFor="kb-sub">Subcategory</FieldLabel>
          <input id="kb-sub" className="input h-9" value={form.subcategory ?? ""} onChange={(e) => set("subcategory", e.target.value)} />
        </div>
        <div className="flex flex-col gap-space-xs">
          <FieldLabel htmlFor="kb-svc">Service</FieldLabel>
          <select id="kb-svc" className="input h-9" value={form.service_id ?? ""} onChange={(e) => set("service_id", e.target.value || null)}>
            <option value="">—</option>
            {services.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-space-xs">
          <FieldLabel htmlFor="kb-status">Status</FieldLabel>
          <select id="kb-status" className="input h-9" value={form.status} onChange={(e) => set("status", e.target.value as ArticleWrite["status"])}>
            <option value="draft">Draft</option>
            <option value="published">Published</option>
            <option value="archived">Archived</option>
          </select>
        </div>
      </div>
      <div className="flex flex-col gap-space-xs">
        <div className="flex items-center justify-between">
          <FieldLabel htmlFor="kb-content">Content (Markdown)</FieldLabel>
          <button type="button" className="font-body-sm text-body-sm text-on-surface-variant hover:text-on-surface" onClick={() => setPreview((v) => !v)}>{preview ? "Edit" : "Preview"}</button>
        </div>
        {preview ? (
          <div className="min-h-[320px] rounded-xl bg-surface-container-lowest p-space-lg shadow-sm"><Markdown source={form.content} /></div>
        ) : (
          <textarea id="kb-content" className="input min-h-[320px] resize-y py-2 font-label-code text-[13px]" value={form.content} onChange={(e) => set("content", e.target.value)} />
        )}
        <p className="font-body-sm text-body-sm text-outline">Published articles are chunked and indexed so the AI can cite them as evidence.</p>
      </div>
    </form>
  );
}
