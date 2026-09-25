"""AI & automation settings, SLA policies, knowledge sources and integrations."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.api.deps import AdminDep, ContainerDep, ReposDep, StaffDep
from app.schemas.misc import (
    AiSettingsUpdate,
    AiSettingsView,
    IntegrationUpdate,
    IntegrationView,
    KnowledgeSourceUpdate,
    KnowledgeSourceView,
    SlaPolicyUpdate,
    SlaPolicyView,
)
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/ai", response_model=AiSettingsView)
async def get_ai_settings(principal: StaffDep, repos: ReposDep, container: ContainerDep) -> AiSettingsView:
    return await SettingsService(repos, container, principal).ai_settings()


@router.patch("/ai", response_model=AiSettingsView)
async def update_ai_settings(body: AiSettingsUpdate, principal: AdminDep, repos: ReposDep, container: ContainerDep) -> AiSettingsView:
    return await SettingsService(repos, container, principal).update_ai(body)


@router.get("/sla-policies", response_model=list[SlaPolicyView])
async def sla_policies(principal: StaffDep, repos: ReposDep, container: ContainerDep) -> list[SlaPolicyView]:
    return await SettingsService(repos, container, principal).sla_policies()


@router.patch("/sla-policies/{policy_id}", response_model=SlaPolicyView)
async def update_sla_policy(policy_id: uuid.UUID, body: SlaPolicyUpdate, principal: AdminDep, repos: ReposDep, container: ContainerDep) -> SlaPolicyView:
    return await SettingsService(repos, container, principal).update_sla(policy_id, body)


@router.patch("/knowledge-sources/{source_id}", response_model=list[KnowledgeSourceView])
async def update_knowledge_source(source_id: uuid.UUID, body: KnowledgeSourceUpdate, principal: AdminDep, repos: ReposDep, container: ContainerDep) -> list[KnowledgeSourceView]:
    return await SettingsService(repos, container, principal).update_knowledge_source(source_id, body.enabled)


@router.post("/knowledge-sources/reindex")
async def reindex_knowledge(principal: AdminDep, repos: ReposDep, container: ContainerDep) -> dict[str, int]:
    return await SettingsService(repos, container, principal).reindex()


@router.patch("/integrations/{integration_id}", response_model=IntegrationView)
async def update_integration(integration_id: uuid.UUID, body: IntegrationUpdate, principal: AdminDep, repos: ReposDep, container: ContainerDep) -> IntegrationView:
    return await SettingsService(repos, container, principal).update_integration(integration_id, body)
