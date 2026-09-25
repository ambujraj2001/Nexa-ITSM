"""Employee AI assistant conversations."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status

from app.api.deps import ContainerDep, PrincipalDep, ReposDep
from app.schemas.misc import ConfirmProposalResponse, ConversationView, SendMessageRequest, SendMessageResponse
from app.services.conversation_service import ConversationService

router = APIRouter(prefix="/api/conversations", tags=["assistant"])


def conversation_service(principal: PrincipalDep, repos: ReposDep, container: ContainerDep) -> ConversationService:
    return ConversationService(repos, container, principal)


ConversationsDep = Annotated[ConversationService, Depends(conversation_service)]


@router.get("/current", response_model=ConversationView)
async def current_conversation(service: ConversationsDep) -> ConversationView:
    return await service.current()


@router.post("", response_model=ConversationView, status_code=status.HTTP_201_CREATED)
async def new_conversation(service: ConversationsDep) -> ConversationView:
    return await service.start_new()


@router.get("/{conversation_id}", response_model=ConversationView)
async def get_conversation(conversation_id: uuid.UUID, service: ConversationsDep) -> ConversationView:
    return await service.view(conversation_id)


@router.post("/{conversation_id}/messages", response_model=SendMessageResponse)
async def send_message(conversation_id: uuid.UUID, body: SendMessageRequest, service: ConversationsDep) -> SendMessageResponse:
    return await service.send(conversation_id, body.content)


@router.post("/{conversation_id}/proposals/{message_id}/confirm", response_model=ConfirmProposalResponse)
async def confirm_proposal(conversation_id: uuid.UUID, message_id: uuid.UUID, service: ConversationsDep) -> ConfirmProposalResponse:
    return await service.confirm(conversation_id, message_id)


@router.post("/{conversation_id}/proposals/{message_id}/dismiss", response_model=SendMessageResponse)
async def dismiss_proposal(conversation_id: uuid.UUID, message_id: uuid.UUID, service: ConversationsDep) -> SendMessageResponse:
    return await service.dismiss(conversation_id, message_id)


@router.post("/{conversation_id}/attachments", status_code=status.HTTP_201_CREATED)
async def upload_attachment(conversation_id: uuid.UUID, service: ConversationsDep, container: ContainerDep, file: Annotated[UploadFile, File()]) -> dict:
    content = await file.read(container.settings.max_upload_bytes + 1)
    return await service.upload(conversation_id, file_name=file.filename or "attachment", content=content, content_type=file.content_type)
