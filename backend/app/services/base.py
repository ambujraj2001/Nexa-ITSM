from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.container import Container
from app.repositories.audit_repository import AuditRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.settings_repository import SettingsRepository
from app.repositories.ticket_repository import TicketRepository
from app.repositories.user_repository import UserRepository


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class Repos:
    session: AsyncSession
    users: UserRepository
    tickets: TicketRepository
    knowledge: KnowledgeRepository
    settings: SettingsRepository
    audit: AuditRepository
    conversations: ConversationRepository

    @classmethod
    def for_session(cls, session: AsyncSession) -> Repos:
        return cls(
            session=session,
            users=UserRepository(session),
            tickets=TicketRepository(session),
            knowledge=KnowledgeRepository(session),
            settings=SettingsRepository(session),
            audit=AuditRepository(session),
            conversations=ConversationRepository(session),
        )


class Service:
    """Base for request-scoped services: repositories + app container."""

    def __init__(self, repos: Repos, container: Container) -> None:
        self.repos = repos
        self.container = container
        self.settings = container.settings

    @property
    def session(self) -> AsyncSession:
        return self.repos.session

    async def commit(self) -> None:
        await self.repos.session.commit()
