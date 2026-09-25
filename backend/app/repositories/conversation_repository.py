from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Attachment, Conversation, ConversationMessage


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, conversation_id: uuid.UUID) -> Conversation | None:
        return await self.session.get(Conversation, conversation_id)

    async def latest_active(self, user_id: uuid.UUID) -> Conversation | None:
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id, Conversation.status == "active")
            .order_by(Conversation.updated_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID, limit: int = 20) -> Sequence[Conversation]:
        stmt = select(Conversation).where(Conversation.user_id == user_id).order_by(Conversation.updated_at.desc()).limit(limit)
        return (await self.session.execute(stmt)).scalars().all()

    async def add(self, conversation: Conversation) -> Conversation:
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def messages(self, conversation_id: uuid.UUID, *, limit: int = 200) -> Sequence[ConversationMessage]:
        stmt = (
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.created_at, ConversationMessage.id)
            .limit(limit)
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def recent_messages(self, conversation_id: uuid.UUID, *, limit: int = 12) -> list[ConversationMessage]:
        stmt = (
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.created_at.desc(), ConversationMessage.id.desc())
            .limit(limit)
        )
        return list(reversed((await self.session.execute(stmt)).scalars().all()))

    async def get_message(self, message_id: uuid.UUID) -> ConversationMessage | None:
        return await self.session.get(ConversationMessage, message_id)

    async def add_message(self, message: ConversationMessage) -> ConversationMessage:
        self.session.add(message)
        await self.session.flush()
        return message

    async def pending_attachments(self, conversation_id: uuid.UUID) -> Sequence[Attachment]:
        stmt = select(Attachment).where(Attachment.conversation_id == conversation_id, Attachment.ticket_id.is_(None))
        return (await self.session.execute(stmt)).scalars().all()
