"""Knowledge base and retrieval."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import ContainerDep, PrincipalDep, ReposDep, StaffDep
from app.schemas.misc import ArticleDetail, ArticlePatch, ArticleSummary, ArticleWrite, KnowledgeSearchHit, KnowledgeSearchRequest
from app.services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("", response_model=list[ArticleSummary])
async def list_articles(
    principal: PrincipalDep, repos: ReposDep, container: ContainerDep,
    q: Annotated[str | None, Query(max_length=200)] = None, category: str | None = None,
    status_filter: Annotated[str | None, Query(alias="status", pattern="^(draft|published|archived)$")] = None,
) -> list[ArticleSummary]:
    return await KnowledgeService(repos, container, principal).list_articles(query=q, category=category, status=status_filter)


@router.post("", response_model=ArticleDetail, status_code=status.HTTP_201_CREATED)
async def create_article(body: ArticleWrite, principal: StaffDep, repos: ReposDep, container: ContainerDep) -> ArticleDetail:
    return await KnowledgeService(repos, container, principal).create_article(body)


@router.post("/search", response_model=list[KnowledgeSearchHit])
async def search(body: KnowledgeSearchRequest, principal: StaffDep, repos: ReposDep, container: ContainerDep) -> list[KnowledgeSearchHit]:
    hits = await KnowledgeService(repos, container, principal).search_articles(body.query, category=body.category, limit=body.limit)
    return [
        KnowledgeSearchHit(article_id=h.article_id, article_number=h.article_number, title=h.title, category=h.category, excerpt=h.excerpt, similarity=h.similarity, matched_by=sorted(h.matched_by), updated_at=h.updated_at)
        for h in hits
    ]


@router.get("/{ref}", response_model=ArticleDetail)
async def get_article(ref: str, principal: PrincipalDep, repos: ReposDep, container: ContainerDep) -> ArticleDetail:
    return await KnowledgeService(repos, container, principal).get_article(ref)


@router.patch("/{article_id}", response_model=ArticleDetail)
async def update_article(article_id: str, body: ArticlePatch, principal: StaffDep, repos: ReposDep, container: ContainerDep) -> ArticleDetail:
    return await KnowledgeService(repos, container, principal).update_article(article_id, body)
