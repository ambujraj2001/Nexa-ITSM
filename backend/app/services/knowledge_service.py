"""Knowledge base management and retrieval (articles + resolved incidents)."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Sequence

from app.container import Container
from app.core.errors import AIUnavailable, NotFound
from app.core.logging import get_logger
from app.domain import policies
from app.domain.enums import StepStatus
from app.domain.policies import Principal
from app.domain.taxonomy import normalize_category
from app.infrastructure.cache import key as cache_key
from app.infrastructure.telemetry import span
from app.models import KnowledgeArticle
from app.repositories.knowledge_repository import IncidentHit, KnowledgeHit
from app.schemas.misc import ArticleDetail, ArticlePatch, ArticleSummary, ArticleWrite
from app.services.audit_service import AuditService
from app.services.base import Repos, Service
from app.services.presenters import person_ref, service_ref
from app.utils.text import chunk_text, truncate

log = get_logger(__name__)
_QUERY_EMBEDDING_TTL = 3600


class KnowledgeService(Service):
    def __init__(self, repos: Repos, container: Container, principal: Principal | None = None) -> None:
        super().__init__(repos, container)
        self.principal = principal
        self.audit = AuditService(repos.audit)

    # ── retrieval ────────────────────────────────────────────────────────
    async def _source_enabled(self, source_type: str) -> bool:
        source = await self.repos.settings.knowledge_source_by_type(source_type)
        return source is None or source.enabled

    async def embed_query(self, query: str) -> list[float] | None:
        """Semantic query vector, cached in Redis. None → lexical-only search."""
        if not self.container.models.embeddings_available or not query.strip():
            return None
        model = self.settings.nexa_model_embedding
        ck = cache_key("emb", hashlib.sha256(f"{model}:{query}".encode()).hexdigest()[:40])
        cached = await self.container.store.get(ck)
        if cached:
            try:
                return json.loads(cached)
            except ValueError:
                pass
        try:
            vectors, _ = await self.container.models.embed([truncate(query, 2000)])
        except Exception as exc:  # noqa: BLE001 — degrade to full-text search
            log.warning("knowledge.query_embedding_failed", error=type(exc).__name__)
            return None
        await self.container.store.set(ck, json.dumps(vectors[0]), ttl_seconds=_QUERY_EMBEDDING_TTL)
        return vectors[0]

    async def search_articles(self, query: str, *, category: str | None = None, limit: int = 5) -> list[KnowledgeHit]:
        with span("knowledge.search", **{"nexa.search.kind": "articles"}) as current:
            if not query.strip() or not await self._source_enabled("internal_articles"):
                return []
            embedding = await self.embed_query(query)
            hits = await self.repos.knowledge.search_knowledge(query, query_embedding=embedding, category=category, limit=limit)
            current.set_attribute("nexa.search.results", len(hits))
            current.set_attribute("nexa.search.semantic", embedding is not None)
            return hits

    async def search_incidents(self, query: str, *, exclude_ticket_id: uuid.UUID | None = None, limit: int = 5) -> list[IncidentHit]:
        with span("knowledge.search", **{"nexa.search.kind": "incidents"}) as current:
            if not query.strip() or not await self._source_enabled("incident_history"):
                return []
            embedding = await self.embed_query(query)
            hits = await self.repos.knowledge.search_incidents(query, query_embedding=embedding, exclude_ticket_id=exclude_ticket_id, limit=limit)
            current.set_attribute("nexa.search.results", len(hits))
            return hits

    # ── indexing ─────────────────────────────────────────────────────────
    async def index_article(self, article_id: uuid.UUID) -> str:
        article = await self.repos.knowledge.get(article_id)
        if article is None:
            return "missing"
        if article.status != "published":
            await self.repos.knowledge.delete_article_chunks(article.id)
            article.embedding_status = "skipped"
            await self.commit()
            return "skipped"
        with span("knowledge.index_article", **{"nexa.article": article.article_number}):
            header = f"{article.title}\n{article.summary or ''}".strip()
            chunks = [f"{header}\n\n{c}" if i == 0 else f"{article.title}\n{c}" for i, c in enumerate(chunk_text(article.content))] or [header]
            vectors: list[list[float]] | None = None
            model: str | None = None
            status = "indexed"
            if self.container.models.embeddings_available:
                try:
                    vectors, model = await self.container.models.embed(chunks)
                except (AIUnavailable, Exception) as exc:  # noqa: BLE001
                    log.warning("knowledge.embedding_failed", article=article.article_number, error=type(exc).__name__)
                    vectors, status = None, "failed"
            await self.repos.knowledge.replace_chunks(
                article.id, chunks, vectors, model, {"article_number": article.article_number, "category": article.category}
            )
            article.embedding_status = status
            await self.commit()
            return status

    async def index_resolved_ticket(self, ticket_id: uuid.UUID) -> None:
        ticket = await self.repos.tickets.get(ticket_id)
        if ticket is None or ticket.resolved_at is None:
            return
        analysis = await self.repos.tickets.get_analysis(ticket.id)
        steps = await self.repos.tickets.list_steps(ticket.id)
        done = [s.description for s in steps if s.status == StepStatus.COMPLETED.value]
        content = "\n".join(
            filter(
                None,
                [
                    f"Title: {ticket.title}",
                    f"Problem: {truncate(ticket.description, 1500)}",
                    f"Category: {' / '.join(filter(None, [ticket.category, ticket.subcategory]))}" if ticket.category else None,
                    f"Diagnosis: {analysis.diagnosis}" if analysis and analysis.diagnosis else None,
                    f"Resolution: {ticket.resolution_summary}" if ticket.resolution_summary else None,
                    f"Steps completed: {'; '.join(done)}" if done else None,
                ],
            )
        )
        vector: list[float] | None = None
        model: str | None = None
        if self.container.models.embeddings_available:
            try:
                vectors, model = await self.container.models.embed([content])
                vector = vectors[0]
            except Exception as exc:  # noqa: BLE001
                log.warning("knowledge.incident_embedding_failed", error=type(exc).__name__)
        await self.repos.knowledge.upsert_incident(
            ticket.id, content, vector, model,
            {"ticket_number": ticket.ticket_number, "category": ticket.category, "subcategory": ticket.subcategory, "resolution_code": ticket.resolution_code},
        )
        await self.commit()

    # ── CRUD (API) ───────────────────────────────────────────────────────
    def _require_principal(self) -> Principal:
        if self.principal is None:
            raise RuntimeError("principal required")
        return self.principal

    async def _summaries(self, articles: Sequence[KnowledgeArticle]) -> list[ArticleSummary]:
        services = await self.repos.settings.services_by_ids([a.service_id for a in articles])
        return [
            ArticleSummary(
                id=a.id, article_number=a.article_number, title=a.title, summary=a.summary, category=a.category,
                subcategory=a.subcategory, status=a.status, embedding_status=a.embedding_status,
                service=service_ref(services.get(a.service_id)) if a.service_id else None, updated_at=a.updated_at,
            )
            for a in articles
        ]

    async def list_articles(self, *, query: str | None, category: str | None, status: str | None) -> list[ArticleSummary]:
        principal = self._require_principal()
        rows = await self.repos.knowledge.list(published_only=not principal.is_staff, query=query, category=category, status=status)
        return await self._summaries(rows)

    async def get_article(self, ref: str) -> ArticleDetail:
        principal = self._require_principal()
        try:
            article = await self.repos.knowledge.get(uuid.UUID(ref))
        except ValueError:
            article = await self.repos.knowledge.get_by_number(ref)
        if article is None or (article.status != "published" and not principal.is_staff):
            raise NotFound("Article not found.")
        [summary] = await self._summaries([article])
        people = await self.repos.users.get_many([article.created_by, article.updated_by])
        return ArticleDetail(
            **summary.model_dump(), content=article.content, created_at=article.created_at,
            created_by=person_ref(people.get(article.created_by), include_email=False) if article.created_by else None,
            updated_by=person_ref(people.get(article.updated_by), include_email=False) if article.updated_by else None,
        )

    async def create_article(self, data: ArticleWrite) -> ArticleDetail:
        principal = self._require_principal()
        policies.ensure(policies.can_manage_knowledge(principal), "Only IT staff can write knowledge articles.")
        category, subcategory = normalize_category(data.category, data.subcategory) if data.category else (None, data.subcategory)
        source = await self.repos.settings.knowledge_source_by_type("internal_articles")
        article = KnowledgeArticle(
            title=data.title.strip(), summary=(data.summary or "").strip() or None, content=data.content.strip(),
            category=category, subcategory=subcategory, service_id=data.service_id, source_id=source.id if source else None,
            status=data.status, created_by=principal.profile_id, updated_by=principal.profile_id,
        )
        await self.repos.knowledge.add(article)
        await self.audit.record("knowledge.created", actor=principal, entity_type="knowledge_article", entity_id=article.id, new_value={"title": article.title, "status": article.status})
        await self.commit()
        await schedule_article_index(self.container, article.id)
        return await self.get_article(str(article.id))

    async def update_article(self, ref: str, patch: ArticlePatch) -> ArticleDetail:
        principal = self._require_principal()
        policies.ensure(policies.can_manage_knowledge(principal), "Only IT staff can edit knowledge articles.")
        article = await self.repos.knowledge.get(uuid.UUID(ref))
        if article is None:
            raise NotFound("Article not found.")
        changes = patch.model_dump(exclude_unset=True)
        old = {k: getattr(article, k) for k in changes}
        if "category" in changes or "subcategory" in changes:
            cat, sub = normalize_category(changes.get("category", article.category), changes.get("subcategory", article.subcategory))
            changes["category"], changes["subcategory"] = cat, sub
        for key_name, value in changes.items():
            setattr(article, key_name, value.strip() if isinstance(value, str) else value)
        article.updated_by = principal.profile_id
        article.embedding_status = "pending"
        await self.audit.record("knowledge.updated", actor=principal, entity_type="knowledge_article", entity_id=article.id, old_value={k: str(v) if v is not None else None for k, v in old.items() if k != "content"}, new_value={k: v for k, v in changes.items() if k != "content"})
        await self.commit()
        await schedule_article_index(self.container, article.id)
        return await self.get_article(str(article.id))


async def schedule_article_index(container: Container, article_id: uuid.UUID) -> None:
    async def job() -> None:
        async with container.db.session() as session:
            await KnowledgeService(Repos.for_session(session), container).index_article(article_id)

    await container.jobs.spawn(f"index-article-{article_id}", job)


async def schedule_incident_index(container: Container, ticket_id: uuid.UUID) -> None:
    async def job() -> None:
        async with container.db.session() as session:
            await KnowledgeService(Repos.for_session(session), container).index_resolved_ticket(ticket_id)

    await container.jobs.spawn(f"index-incident-{ticket_id}", job)

