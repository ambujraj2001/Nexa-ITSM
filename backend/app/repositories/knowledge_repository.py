"""Knowledge articles, chunk embeddings and resolved-incident retrieval.

Retrieval is hybrid: pgvector cosine similarity (when an embedding model is
configured) fused with Postgres full-text ranking using Reciprocal Rank Fusion.
Full-text alone still works when no embedding model is available.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeArticle

_RRF_K = 60
_TOKEN = re.compile(r"[a-z0-9]{2,40}")


def or_tsquery(query: str, *, max_terms: int = 24) -> str:
    """Build an OR tsquery from free text ('my vpn fails' → 'my | vpn | fails').

    Natural-language problem descriptions rarely contain *every* term of a
    relevant article, so AND semantics (plainto/websearch) under-match.
    Postgres drops English stop words during to_tsquery normalisation.
    """
    seen: list[str] = []
    for token in _TOKEN.findall(query.lower()):
        if token not in seen:
            seen.append(token)
    return " | ".join(seen[:max_terms])


def vector_literal(vector: Sequence[float]) -> str:
    return "[" + ",".join(f"{v:.7g}" for v in vector) + "]"


@dataclass
class KnowledgeHit:
    article_id: uuid.UUID
    article_number: str
    title: str
    category: str | None
    excerpt: str
    updated_at: datetime
    score: float
    similarity: float | None = None
    matched_by: set[str] = field(default_factory=set)


@dataclass
class IncidentHit:
    ticket_id: uuid.UUID
    ticket_number: str
    title: str
    excerpt: str
    resolution_summary: str | None
    category: str | None
    subcategory: str | None
    created_at: datetime
    resolved_at: datetime | None
    score: float
    similarity: float | None = None
    matched_by: set[str] = field(default_factory=set)


def _fuse(ranked_lists: dict[str, list[tuple[str, dict]]]) -> list[tuple[str, float, dict, set[str]]]:
    scores: dict[str, float] = {}
    payloads: dict[str, dict] = {}
    sources: dict[str, set[str]] = {}
    for source, items in ranked_lists.items():
        for rank, (key, payload) in enumerate(items):
            scores[key] = scores.get(key, 0.0) + 1.0 / (_RRF_K + rank + 1)
            merged = payloads.setdefault(key, {})
            for k, v in payload.items():
                if v is not None and merged.get(k) is None:
                    merged[k] = v
            sources.setdefault(key, set()).add(source)
    return sorted(((k, s, payloads[k], sources[k]) for k, s in scores.items()), key=lambda x: x[1], reverse=True)


class KnowledgeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── articles ─────────────────────────────────────────────────────────
    async def get(self, article_id: uuid.UUID) -> KnowledgeArticle | None:
        return await self.session.get(KnowledgeArticle, article_id)

    async def get_by_number(self, number: str) -> KnowledgeArticle | None:
        stmt = select(KnowledgeArticle).where(func.upper(KnowledgeArticle.article_number) == number.strip().upper())
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_many_by_number(self, numbers: Sequence[str]) -> dict[str, KnowledgeArticle]:
        wanted = [n.strip().upper() for n in numbers if n]
        if not wanted:
            return {}
        stmt = select(KnowledgeArticle).where(func.upper(KnowledgeArticle.article_number).in_(wanted))
        return {a.article_number.upper(): a for a in (await self.session.execute(stmt)).scalars().all()}

    async def list(
        self, *, published_only: bool, query: str | None = None, category: str | None = None, status: str | None = None, limit: int = 100
    ) -> Sequence[KnowledgeArticle]:
        stmt = select(KnowledgeArticle)
        if published_only:
            stmt = stmt.where(KnowledgeArticle.status == "published")
        elif status:
            stmt = stmt.where(KnowledgeArticle.status == status)
        if category:
            stmt = stmt.where(KnowledgeArticle.category == category)
        if query:
            q = query.strip()
            tsv = text("knowledge_articles.search_vector @@ websearch_to_tsquery('english', :kq)").bindparams(kq=q)
            stmt = stmt.where(or_(KnowledgeArticle.title.ilike(f"%{q}%"), KnowledgeArticle.article_number.ilike(f"%{q}%"), tsv))
        stmt = stmt.order_by(KnowledgeArticle.updated_at.desc()).limit(limit)
        return (await self.session.execute(stmt)).scalars().all()

    async def add(self, article: KnowledgeArticle) -> KnowledgeArticle:
        self.session.add(article)
        await self.session.flush()
        return article

    # ── chunk index ──────────────────────────────────────────────────────
    async def replace_chunks(
        self,
        article_id: uuid.UUID,
        chunks: Sequence[str],
        embeddings: Sequence[Sequence[float]] | None,
        model: str | None,
        metadata: dict,
    ) -> None:
        await self.session.execute(text("delete from public.knowledge_embeddings where knowledge_article_id = :aid"), {"aid": article_id})
        for index, chunk in enumerate(chunks):
            vector = vector_literal(embeddings[index]) if embeddings else None
            await self.session.execute(
                text(
                    "insert into public.knowledge_embeddings (knowledge_article_id, chunk_index, chunk_text, embedding, embedding_model, metadata) "
                    "values (:aid, :idx, :chunk, cast(cast(:emb as text) as extensions.vector), :model, cast(:meta as jsonb))"
                ),
                {"aid": article_id, "idx": index, "chunk": chunk, "emb": vector, "model": model, "meta": _json(metadata)},
            )

    async def upsert_incident(
        self, ticket_id: uuid.UUID, content: str, embedding: Sequence[float] | None, model: str | None, metadata: dict
    ) -> None:
        await self.session.execute(
            text(
                "insert into public.incident_embeddings (ticket_id, content, embedding, embedding_model, metadata) "
                "values (:tid, :content, cast(cast(:emb as text) as extensions.vector), :model, cast(:meta as jsonb)) "
                "on conflict (ticket_id) do update set content = excluded.content, embedding = excluded.embedding, "
                "embedding_model = excluded.embedding_model, metadata = excluded.metadata, updated_at = now()"
            ),
            {"tid": ticket_id, "content": content, "emb": vector_literal(embedding) if embedding else None, "model": model, "meta": _json(metadata)},
        )

    async def remove_incident(self, ticket_id: uuid.UUID) -> None:
        await self.session.execute(text("delete from public.incident_embeddings where ticket_id = :tid"), {"tid": ticket_id})

    async def articles_missing_embeddings(self) -> Sequence[uuid.UUID]:
        rows = await self.session.execute(
            text(
                "select ka.id from public.knowledge_articles ka where ka.status = 'published' and ("
                " ka.embedding_status <> 'indexed' or not exists (select 1 from public.knowledge_embeddings ke where ke.knowledge_article_id = ka.id))"
            )
        )
        return [r[0] for r in rows.all()]

    async def delete_article_chunks(self, article_id: uuid.UUID) -> None:
        from app.models import KnowledgeEmbedding

        await self.session.execute(delete(KnowledgeEmbedding).where(KnowledgeEmbedding.knowledge_article_id == article_id))

    # ── retrieval ────────────────────────────────────────────────────────
    async def search_knowledge(
        self,
        query: str,
        *,
        query_embedding: Sequence[float] | None,
        category: str | None = None,
        limit: int = 5,
        candidates: int = 20,
    ) -> list[KnowledgeHit]:
        ranked: dict[str, list[tuple[str, dict]]] = {}
        category_filter = "and (cast(:cat as text) is null or ka.category = cast(:cat as text))"
        if query_embedding is not None:
            rows = await self.session.execute(
                text(
                    "select ke.knowledge_article_id as aid, ke.chunk_text, "
                    " 1 - (ke.embedding operator(extensions.<=>) cast(cast(:qv as text) as extensions.vector)) as similarity "
                    "from public.knowledge_embeddings ke join public.knowledge_articles ka on ka.id = ke.knowledge_article_id "
                    f"where ka.status = 'published' and ke.embedding is not null {category_filter} "
                    "order by ke.embedding operator(extensions.<=>) cast(cast(:qv as text) as extensions.vector) limit :k"
                ),
                {"qv": vector_literal(query_embedding), "k": candidates, "cat": category},
            )
            ranked["semantic"] = [(str(r.aid), {"excerpt": r.chunk_text, "similarity": float(r.similarity)}) for r in rows.all()]
        tsq = or_tsquery(query)
        if tsq:
            rows = await self.session.execute(
                text(
                    "select ke.knowledge_article_id as aid, ke.chunk_text, "
                    " ts_rank_cd(ke.search_vector, to_tsquery('english', :tsq)) + "
                    " ts_rank_cd(ka.search_vector, to_tsquery('english', :tsq)) as rank "
                    "from public.knowledge_embeddings ke join public.knowledge_articles ka on ka.id = ke.knowledge_article_id "
                    f"where ka.status = 'published' and (ke.search_vector @@ to_tsquery('english', :tsq) or ka.search_vector @@ to_tsquery('english', :tsq)) {category_filter} "
                    "order by rank desc limit :k"
                ),
                {"tsq": tsq, "k": candidates, "cat": category},
            )
            ranked["lexical"] = [(str(r.aid), {"excerpt": r.chunk_text}) for r in rows.all()]
            # Articles never chunked (e.g. indexing pending) still match on the article itself.
            rows = await self.session.execute(
                text(
                    "select ka.id as aid, left(ka.content, 600) as excerpt, ts_rank_cd(ka.search_vector, to_tsquery('english', :tsq)) as rank "
                    "from public.knowledge_articles ka where ka.status = 'published' and ka.search_vector @@ to_tsquery('english', :tsq) "
                    f"{category_filter} order by rank desc limit :k"
                ),
                {"tsq": tsq, "k": candidates, "cat": category},
            )
            ranked["article"] = [(str(r.aid), {"excerpt": r.excerpt}) for r in rows.all()]

        fused = _fuse({k: _dedupe(v) for k, v in ranked.items() if v})[:limit]
        if not fused:
            return []
        articles = {
            str(a.id): a
            for a in (await self.session.execute(select(KnowledgeArticle).where(KnowledgeArticle.id.in_([uuid.UUID(k) for k, *_ in fused])))).scalars().all()
        }
        hits: list[KnowledgeHit] = []
        for key, score, payload, sources in fused:
            article = articles.get(key)
            if article is None:
                continue
            hits.append(
                KnowledgeHit(
                    article_id=article.id,
                    article_number=article.article_number,
                    title=article.title,
                    category=article.category,
                    excerpt=(payload.get("excerpt") or article.summary or article.content)[:700],
                    updated_at=article.updated_at,
                    score=score,
                    similarity=payload.get("similarity"),
                    matched_by=sources,
                )
            )
        return hits

    async def search_incidents(
        self,
        query: str,
        *,
        query_embedding: Sequence[float] | None,
        exclude_ticket_id: uuid.UUID | None = None,
        limit: int = 5,
        candidates: int = 20,
    ) -> list[IncidentHit]:
        ranked: dict[str, list[tuple[str, dict]]] = {}
        base_where = "t.status in ('resolved', 'closed') and (cast(:exclude as uuid) is null or t.id <> cast(:exclude as uuid))"
        if query_embedding is not None:
            rows = await self.session.execute(
                text(
                    "select ie.ticket_id as tid, 1 - (ie.embedding operator(extensions.<=>) cast(cast(:qv as text) as extensions.vector)) as similarity "
                    "from public.incident_embeddings ie join public.tickets t on t.id = ie.ticket_id "
                    f"where ie.embedding is not null and {base_where} "
                    "order by ie.embedding operator(extensions.<=>) cast(cast(:qv as text) as extensions.vector) limit :k"
                ),
                {"qv": vector_literal(query_embedding), "k": candidates, "exclude": exclude_ticket_id},
            )
            ranked["semantic"] = [(str(r.tid), {"similarity": float(r.similarity)}) for r in rows.all()]
        tsq = or_tsquery(query)
        if tsq:
            rows = await self.session.execute(
                text(
                    "select t.id as tid, ts_rank_cd(coalesce(ie.search_vector, t.search_vector), to_tsquery('english', :tsq)) as rank "
                    "from public.tickets t left join public.incident_embeddings ie on ie.ticket_id = t.id "
                    f"where {base_where} and (t.search_vector @@ to_tsquery('english', :tsq) or ie.search_vector @@ to_tsquery('english', :tsq)) "
                    "order by rank desc limit :k"
                ),
                {"tsq": tsq, "k": candidates, "exclude": exclude_ticket_id},
            )
            ranked["lexical"] = [(str(r.tid), {}) for r in rows.all()]

        fused = _fuse({k: v for k, v in ranked.items() if v})[:limit]
        if not fused:
            return []
        rows = await self.session.execute(
            text(
                "select t.id, t.ticket_number, t.title, t.description, t.resolution_summary, t.category, t.subcategory, "
                " t.created_at, t.resolved_at, ie.content from public.tickets t "
                "left join public.incident_embeddings ie on ie.ticket_id = t.id where t.id = any(cast(:ids as uuid[]))"
            ),
            {"ids": [k for k, *_ in fused]},
        )
        by_id = {str(r.id): r for r in rows.all()}
        hits: list[IncidentHit] = []
        for key, score, payload, sources in fused:
            r = by_id.get(key)
            if r is None:
                continue
            hits.append(
                IncidentHit(
                    ticket_id=r.id,
                    ticket_number=r.ticket_number,
                    title=r.title,
                    excerpt=(r.description or "")[:400],
                    resolution_summary=r.resolution_summary,
                    category=r.category,
                    subcategory=r.subcategory,
                    created_at=r.created_at,
                    resolved_at=r.resolved_at,
                    score=score,
                    similarity=payload.get("similarity"),
                    matched_by=sources,
                )
            )
        return hits


def _dedupe(items: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
    """Keep the best-ranked chunk per article."""
    seen: set[str] = set()
    out: list[tuple[str, dict]] = []
    for key, payload in items:
        if key not in seen:
            seen.add(key)
            out.append((key, payload))
    return out


def _json(value: dict) -> str:
    import json

    return json.dumps(value, default=str)
