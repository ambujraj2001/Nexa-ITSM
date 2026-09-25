"""Configuration and catalogue data: AI config, SLA policies, assignment rules,
integrations, knowledge sources, services and assets."""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AiConfiguration,
    Asset,
    AssignmentRule,
    Integration,
    KnowledgeSource,
    Service,
    SlaPolicy,
)


class SettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── AI configuration (singleton) ─────────────────────────────────────
    async def ai_configuration(self, *, for_update: bool = False) -> AiConfiguration:
        stmt = select(AiConfiguration).where(AiConfiguration.id == 1)
        if for_update:
            stmt = stmt.with_for_update()
        config = (await self.session.execute(stmt)).scalar_one_or_none()
        if config is None:
            # Migration seeds the row; recreate V1 defaults if someone deleted it.
            config = AiConfiguration(id=1)
            self.session.add(config)
            await self.session.flush()
        return config

    # ── SLA ──────────────────────────────────────────────────────────────
    async def sla_policies(self) -> Sequence[SlaPolicy]:
        stmt = select(SlaPolicy).order_by(SlaPolicy.priority, SlaPolicy.created_at)
        return (await self.session.execute(stmt)).scalars().all()

    async def active_sla_policy(self, priority: str) -> SlaPolicy | None:
        stmt = select(SlaPolicy).where(SlaPolicy.priority == priority, SlaPolicy.enabled.is_(True))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_sla_policy(self, policy_id: uuid.UUID) -> SlaPolicy | None:
        return await self.session.get(SlaPolicy, policy_id)

    # ── assignment rules ─────────────────────────────────────────────────
    async def assignment_rules(self, *, enabled_only: bool = False) -> Sequence[AssignmentRule]:
        stmt = select(AssignmentRule).order_by(AssignmentRule.sort_order, AssignmentRule.name)
        if enabled_only:
            stmt = stmt.where(AssignmentRule.enabled.is_(True))
        return (await self.session.execute(stmt)).scalars().all()

    async def get_rule(self, rule_id: uuid.UUID) -> AssignmentRule | None:
        return await self.session.get(AssignmentRule, rule_id)

    # ── integrations / knowledge sources ─────────────────────────────────
    async def integrations(self) -> Sequence[Integration]:
        return (await self.session.execute(select(Integration).order_by(Integration.category, Integration.display_name))).scalars().all()

    async def get_integration(self, integration_id: uuid.UUID) -> Integration | None:
        return await self.session.get(Integration, integration_id)

    async def knowledge_sources(self) -> Sequence[KnowledgeSource]:
        return (await self.session.execute(select(KnowledgeSource).order_by(KnowledgeSource.name))).scalars().all()

    async def get_knowledge_source(self, source_id: uuid.UUID) -> KnowledgeSource | None:
        return await self.session.get(KnowledgeSource, source_id)

    async def knowledge_source_by_type(self, source_type: str) -> KnowledgeSource | None:
        stmt = select(KnowledgeSource).where(KnowledgeSource.source_type == source_type).order_by(KnowledgeSource.created_at).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    # ── services & assets ────────────────────────────────────────────────
    async def services(self) -> Sequence[Service]:
        return (await self.session.execute(select(Service).order_by(Service.name))).scalars().all()

    async def get_service(self, service_id: uuid.UUID) -> Service | None:
        return await self.session.get(Service, service_id)

    async def get_service_by_name(self, name: str) -> Service | None:
        stmt = select(Service).where(func.lower(Service.name) == name.strip().lower())
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def services_by_ids(self, ids: Iterable[uuid.UUID | None]) -> dict[uuid.UUID, Service]:
        wanted = {i for i in ids if i is not None}
        if not wanted:
            return {}
        rows = (await self.session.execute(select(Service).where(Service.id.in_(wanted)))).scalars().all()
        return {s.id: s for s in rows}

    async def assets_for_owner(self, owner_id: uuid.UUID) -> Sequence[Asset]:
        stmt = select(Asset).where(Asset.owner_id == owner_id).order_by(Asset.name)
        return (await self.session.execute(stmt)).scalars().all()

    async def assets(self, *, service_id: uuid.UUID | None = None, limit: int = 200) -> Sequence[Asset]:
        stmt = select(Asset).order_by(Asset.name).limit(limit)
        if service_id:
            stmt = stmt.where(Asset.service_id == service_id)
        return (await self.session.execute(stmt)).scalars().all()

    async def get_asset(self, asset_id: uuid.UUID) -> Asset | None:
        return await self.session.get(Asset, asset_id)

    async def add(self, entity: object) -> object:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def delete(self, entity: object) -> None:
        await self.session.delete(entity)
        await self.session.flush()
