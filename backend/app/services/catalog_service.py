"""Service catalogue and asset register."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.container import Container
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.domain import policies
from app.domain.enums import OPEN_STATUSES
from app.domain.policies import Principal
from app.models import Asset, Service as ServiceModel, Ticket
from app.schemas.misc import AssetView, AssetWrite, ServiceView, ServiceWrite
from app.services.audit_service import AuditService
from app.services.base import Repos, Service
from app.services.presenters import person_ref, service_ref, team_ref


class CatalogService(Service):
    def __init__(self, repos: Repos, container: Container, principal: Principal) -> None:
        super().__init__(repos, container)
        self.principal = principal
        self.audit = AuditService(repos.audit)

    async def services(self) -> list[ServiceView]:
        policies.ensure_staff(self.principal)
        rows = await self.repos.settings.services()
        teams = await self.repos.users.teams_by_ids([s.owner_team_id for s in rows])
        open_counts = dict(
            (await self.session.execute(
                select(Ticket.service_id, func.count()).where(Ticket.service_id.is_not(None), Ticket.status.in_([s.value for s in OPEN_STATUSES])).group_by(Ticket.service_id)
            )).all()
        )
        asset_counts = dict((await self.session.execute(select(Asset.service_id, func.count()).where(Asset.service_id.is_not(None)).group_by(Asset.service_id))).all())
        return [
            ServiceView(
                id=s.id, name=s.name, description=s.description, category=s.category, criticality=s.criticality,
                owner_team=team_ref(teams.get(s.owner_team_id)) if s.owner_team_id else None,
                open_tickets=int(open_counts.get(s.id, 0)), asset_count=int(asset_counts.get(s.id, 0)), updated_at=s.updated_at,
            )
            for s in rows
        ]

    async def _validate_service(self, data: ServiceWrite, existing: ServiceModel | None) -> None:
        clash = await self.repos.settings.get_service_by_name(data.name)
        if clash is not None and (existing is None or clash.id != existing.id):
            raise Conflict("A service with that name exists.", code="service_exists")
        if data.owner_team_id and await self.repos.users.get_team(data.owner_team_id) is None:
            raise ValidationFailed("Unknown team.")

    async def create_service(self, data: ServiceWrite) -> ServiceView:
        policies.ensure_admin(self.principal)
        await self._validate_service(data, None)
        service = ServiceModel(**data.model_dump())
        await self.repos.settings.add(service)
        await self.audit.record("catalog.service_created", actor=self.principal, entity_type="service", entity_id=service.id, new_value={"name": service.name})
        await self.commit()
        return next(v for v in await self.services() if v.id == service.id)

    async def update_service(self, service_id: uuid.UUID, data: ServiceWrite) -> ServiceView:
        policies.ensure_admin(self.principal)
        service = await self.repos.settings.get_service(service_id)
        if service is None:
            raise NotFound("Service not found.")
        await self._validate_service(data, service)
        old = {k: str(getattr(service, k)) if getattr(service, k) is not None else None for k in data.model_dump()}
        for k, v in data.model_dump().items():
            setattr(service, k, v)
        await self.audit.record("catalog.service_updated", actor=self.principal, entity_type="service", entity_id=service.id, old_value=old, new_value=data.model_dump(mode="json"))
        await self.commit()
        return next(v for v in await self.services() if v.id == service.id)

    async def assets(self, *, service_id: uuid.UUID | None, mine: bool) -> list[AssetView]:
        if mine or not self.principal.is_staff:
            rows = await self.repos.settings.assets_for_owner(self.principal.profile_id)
        else:
            rows = await self.repos.settings.assets(service_id=service_id)
        people = await self.repos.users.get_many([a.owner_id for a in rows])
        services = await self.repos.settings.services_by_ids([a.service_id for a in rows])
        return [
            AssetView(
                id=a.id, name=a.name, asset_type=a.asset_type, owner=person_ref(people.get(a.owner_id), include_email=False) if a.owner_id else None,
                service=service_ref(services.get(a.service_id)) if a.service_id else None, metadata=a.metadata_ or {}, updated_at=a.updated_at,
            )
            for a in rows
        ]

    async def create_asset(self, data: AssetWrite) -> AssetView:
        policies.ensure_admin(self.principal)
        if data.owner_id and await self.repos.users.get(data.owner_id) is None:
            raise ValidationFailed("Unknown owner.")
        if data.service_id and await self.repos.settings.get_service(data.service_id) is None:
            raise ValidationFailed("Unknown service.")
        asset = Asset(name=data.name, asset_type=data.asset_type, owner_id=data.owner_id, service_id=data.service_id, metadata_=data.metadata)
        await self.repos.settings.add(asset)
        await self.audit.record("catalog.asset_created", actor=self.principal, entity_type="asset", entity_id=asset.id, new_value={"name": asset.name})
        await self.commit()
        return next(v for v in await self.assets(service_id=None, mine=False) if v.id == asset.id)
