"""Deterministic assignment rules and routing preview."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.api.deps import AdminDep, ContainerDep, ReposDep, StaffDep
from app.schemas.common import OkResponse
from app.schemas.misc import AssignmentRuleView, AssignmentRuleWrite, RoutingPreview, RoutingPreviewRequest
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/api/assignment-rules", tags=["assignment"])


@router.get("", response_model=list[AssignmentRuleView])
async def list_rules(principal: StaffDep, repos: ReposDep, container: ContainerDep) -> list[AssignmentRuleView]:
    return await SettingsService(repos, container, principal).rules()


@router.post("", response_model=AssignmentRuleView, status_code=status.HTTP_201_CREATED)
async def create_rule(body: AssignmentRuleWrite, principal: AdminDep, repos: ReposDep, container: ContainerDep) -> AssignmentRuleView:
    return await SettingsService(repos, container, principal).create_rule(body)


@router.put("/{rule_id}", response_model=AssignmentRuleView)
async def update_rule(rule_id: uuid.UUID, body: AssignmentRuleWrite, principal: AdminDep, repos: ReposDep, container: ContainerDep) -> AssignmentRuleView:
    return await SettingsService(repos, container, principal).update_rule(rule_id, body)


@router.delete("/{rule_id}", response_model=OkResponse)
async def delete_rule(rule_id: uuid.UUID, principal: AdminDep, repos: ReposDep, container: ContainerDep) -> OkResponse:
    await SettingsService(repos, container, principal).delete_rule(rule_id)
    return OkResponse()


@router.post("/preview", response_model=RoutingPreview)
async def preview(body: RoutingPreviewRequest, principal: StaffDep, repos: ReposDep, container: ContainerDep) -> RoutingPreview:
    return await SettingsService(repos, container, principal).preview_routing(body)
