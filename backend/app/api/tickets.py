"""Tickets: lifecycle, analysis, resolution steps, comments, activity, attachments, copilot."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from app.api.deps import ContainerDep, PrincipalDep, ReposDep, StaffDep
from app.core.errors import ValidationFailed
from app.domain import policies
from app.domain.enums import Priority, TicketSource, TicketStatus, TicketType
from app.schemas.tickets import (
    ActivityItem,
    AnalysisView,
    AnyTicketView,
    AttachmentView,
    CommentCreate,
    CommentView,
    CopilotReplyView,
    CopilotRequest,
    EmployeeTicketDetail,
    EscalateRequest,
    ProgressView,
    ReassignRequest,
    RelatedView,
    ReopenRequest,
    ResolutionDraftView,
    ResolveRequest,
    StepCreate,
    StepReorder,
    StepUpdate,
    StepView,
    TicketCreate,
    TicketDetail,
    TicketListParams,
    TicketListResponse,
    TicketUpdate,
)
from app.services.copilot_service import CopilotService
from app.services.investigation_service import schedule_investigation
from app.services.presenters import analysis_view
from app.services.ticket_service import NewTicket, TicketService

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


def tickets_service(principal: PrincipalDep, repos: ReposDep, container: ContainerDep) -> TicketService:
    return TicketService(repos, container, principal)


TicketsDep = Annotated[TicketService, Depends(tickets_service)]


async def _detail(service: TicketService, ref: str) -> TicketDetail | EmployeeTicketDetail:
    return await service.view(ref)


@router.get("", response_model=TicketListResponse)
async def list_tickets(
    service: TicketsDep,
    scope: Annotated[str, Query(pattern="^(visible|assigned|team|requested)$")] = "visible",
    ticket_type: TicketType | None = None,
    status_filter: Annotated[list[TicketStatus] | None, Query(alias="status")] = None,
    priority: Priority | None = None,
    open_only: bool = False,
    q: Annotated[str | None, Query(max_length=200)] = None,
    sort: Annotated[str, Query(pattern="^(updated|sla|priority|created)$")] = "updated",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TicketListResponse:
    params = TicketListParams(scope=scope, ticket_type=ticket_type, status=status_filter or [], priority=priority, open_only=open_only, q=q, sort=sort, limit=limit, offset=offset)  # type: ignore[arg-type]
    return await service.list(params)


@router.post("", response_model=AnyTicketView, status_code=status.HTTP_201_CREATED)
async def create_ticket(body: TicketCreate, service: TicketsDep) -> AnyTicketView:
    ticket = await service.create(
        NewTicket(description=body.description, title=body.title, ticket_type=body.ticket_type, priority=body.priority, service_id=body.service_id, source=TicketSource.PORTAL)
    )
    return await _detail(service, str(ticket.id))


@router.get("/{ref}", response_model=AnyTicketView)
async def get_ticket(ref: str, service: TicketsDep) -> AnyTicketView:
    return await _detail(service, ref)


@router.patch("/{ref}", response_model=AnyTicketView)
async def update_ticket(ref: str, body: TicketUpdate, service: TicketsDep) -> AnyTicketView:
    ticket = await service.update(ref, body)
    return await _detail(service, str(ticket.id))


@router.get("/{ref}/progress", response_model=ProgressView)
async def ticket_progress(ref: str, service: TicketsDep) -> ProgressView:
    return await service.progress(ref)


@router.get("/{ref}/analysis", response_model=AnalysisView | None)
async def ticket_analysis(ref: str, service: TicketsDep, repos: ReposDep) -> AnalysisView | None:
    ticket = await service.load(ref)
    policies.ensure(policies.can_view_internal(service.principal, await service.facts(ticket)), "The full AI analysis is available to IT staff.")
    analysis = await repos.tickets.get_analysis(ticket.id)
    config = await repos.settings.ai_configuration()
    teams = await repos.users.teams_by_ids([analysis.recommended_team_id] if analysis else [])
    return analysis_view(analysis, threshold=float(config.confidence_threshold), teams=teams)


@router.post("/{ref}/investigate", response_model=ProgressView)
async def retry_investigation(ref: str, service: TicketsDep, container: ContainerDep) -> ProgressView:
    ticket = await service.load(ref, for_update=True)
    policies.ensure(policies.can_work_ticket(service.principal, await service.facts(ticket)), "Only the assigned engineer can re-run the investigation.")
    if not container.ai_available:
        raise ValidationFailed("AI is not configured for this workspace.")
    if ticket.ai_status in ("pending", "running"):
        return await service.progress(ref)
    ticket.ai_status = "pending"
    ticket.ai_error = None
    await service.audit.record("ai.investigation_requested", actor=service.principal, ticket_id=ticket.id)
    await service.commit()
    await schedule_investigation(container, ticket.id)
    return await service.progress(ref)


# ── lifecycle actions ──────────────────────────────────────────────────────


@router.post("/{ref}/assign-to-me", response_model=TicketDetail)
async def assign_to_me(ref: str, _: StaffDep, service: TicketsDep) -> TicketDetail:
    ticket = await service.assign_to_me(ref)
    return await _detail(service, str(ticket.id))  # type: ignore[return-value]


@router.post("/{ref}/reassign", response_model=TicketDetail)
async def reassign(ref: str, body: ReassignRequest, _: StaffDep, service: TicketsDep) -> TicketDetail:
    ticket = await service.reassign(ref, body)
    return await _detail(service, str(ticket.id))  # type: ignore[return-value]


@router.post("/{ref}/escalate", response_model=TicketDetail)
async def escalate(ref: str, body: EscalateRequest, _: StaffDep, service: TicketsDep) -> TicketDetail:
    ticket = await service.escalate(ref, body)
    return await _detail(service, str(ticket.id))  # type: ignore[return-value]


@router.post("/{ref}/resolve", response_model=AnyTicketView)
async def resolve(ref: str, body: ResolveRequest, _: StaffDep, service: TicketsDep) -> AnyTicketView:
    ticket = await service.resolve(ref, body)
    return await _detail(service, str(ticket.id))


@router.post("/{ref}/reopen", response_model=AnyTicketView)
async def reopen(ref: str, body: ReopenRequest, service: TicketsDep) -> AnyTicketView:
    ticket = await service.reopen(ref, body)
    return await _detail(service, str(ticket.id))


@router.post("/{ref}/close", response_model=AnyTicketView)
async def close(ref: str, service: TicketsDep) -> AnyTicketView:
    ticket = await service.close(ref)
    return await _detail(service, str(ticket.id))


@router.post("/{ref}/resolution-draft", response_model=ResolutionDraftView)
async def resolution_draft(ref: str, principal: StaffDep, repos: ReposDep, container: ContainerDep) -> ResolutionDraftView:
    return await CopilotService(repos, container, principal).draft_resolution(ref)


# ── resolution steps ───────────────────────────────────────────────────────


async def _step_views(service: TicketService, ref: str) -> list[StepView]:
    detail = await service.view(ref)
    if not isinstance(detail, TicketDetail):
        raise ValidationFailed("Step details are available to IT staff.")
    return detail.steps


@router.get("/{ref}/steps", response_model=list[StepView])
async def list_steps(ref: str, _: StaffDep, service: TicketsDep) -> list[StepView]:
    return await _step_views(service, ref)


@router.post("/{ref}/steps", response_model=list[StepView], status_code=status.HTTP_201_CREATED)
async def add_step(ref: str, body: StepCreate, _: StaffDep, service: TicketsDep) -> list[StepView]:
    await service.add_step(ref, body)
    return await _step_views(service, ref)


@router.patch("/{ref}/steps/{step_id}", response_model=list[StepView])
async def update_step(ref: str, step_id: uuid.UUID, body: StepUpdate, _: StaffDep, service: TicketsDep) -> list[StepView]:
    await service.update_step(ref, step_id, body)
    return await _step_views(service, ref)


@router.delete("/{ref}/steps/{step_id}", response_model=list[StepView])
async def delete_step(ref: str, step_id: uuid.UUID, _: StaffDep, service: TicketsDep) -> list[StepView]:
    await service.delete_step(ref, step_id)
    return await _step_views(service, ref)


@router.post("/{ref}/steps/reorder", response_model=list[StepView])
async def reorder_steps(ref: str, body: StepReorder, _: StaffDep, service: TicketsDep) -> list[StepView]:
    await service.reorder_steps(ref, body)
    return await _step_views(service, ref)


@router.post("/{ref}/steps/restore", response_model=list[StepView])
async def restore_steps(ref: str, _: StaffDep, service: TicketsDep) -> list[StepView]:
    await service.restore_ai_steps(ref)
    return await _step_views(service, ref)


# ── comments, activity, related, attachments ───────────────────────────────


@router.get("/{ref}/comments", response_model=list[CommentView])
async def list_comments(ref: str, service: TicketsDep) -> list[CommentView]:
    return await service.comments(ref)


@router.post("/{ref}/comments", response_model=list[CommentView], status_code=status.HTTP_201_CREATED)
async def add_comment(ref: str, body: CommentCreate, service: TicketsDep) -> list[CommentView]:
    await service.add_comment(ref, body)
    return await service.comments(ref)


@router.get("/{ref}/activity", response_model=list[ActivityItem])
async def activity(ref: str, service: TicketsDep) -> list[ActivityItem]:
    return await service.activity(ref)


@router.get("/{ref}/related", response_model=RelatedView)
async def related(ref: str, _: StaffDep, service: TicketsDep) -> RelatedView:
    return await service.related(ref)


@router.get("/{ref}/attachments", response_model=list[AttachmentView])
async def list_attachments(ref: str, service: TicketsDep) -> list[AttachmentView]:
    return await service.attachments(ref)


@router.post("/{ref}/attachments", response_model=AttachmentView, status_code=status.HTTP_201_CREATED)
async def upload_attachment(ref: str, service: TicketsDep, container: ContainerDep, file: Annotated[UploadFile, File()]) -> AttachmentView:
    content = await file.read(container.settings.max_upload_bytes + 1)
    return await service.upload_attachment(ref, file_name=file.filename or "attachment", content=content, content_type=file.content_type)


# ── copilot ────────────────────────────────────────────────────────────────


@router.get("/{ref}/copilot", response_model=list[dict])
async def copilot_history(ref: str, principal: StaffDep, repos: ReposDep, container: ContainerDep) -> list[dict]:
    return await CopilotService(repos, container, principal).history(ref)


@router.post("/{ref}/copilot", response_model=CopilotReplyView)
async def ask_copilot(ref: str, body: CopilotRequest, principal: StaffDep, repos: ReposDep, container: ContainerDep) -> CopilotReplyView:
    return await CopilotService(repos, container, principal).ask(ref, body.message)

