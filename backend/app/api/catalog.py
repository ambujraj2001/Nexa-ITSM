"""Services and assets."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.api.deps import AdminDep, ContainerDep, PrincipalDep, ReposDep, StaffDep
from app.schemas.misc import AssetView, AssetWrite, ServiceView, ServiceWrite
from app.services.catalog_service import CatalogService

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get("/services", response_model=list[ServiceView])
async def list_services(principal: StaffDep, repos: ReposDep, container: ContainerDep) -> list[ServiceView]:
    return await CatalogService(repos, container, principal).services()


@router.post("/services", response_model=ServiceView, status_code=status.HTTP_201_CREATED)
async def create_service(body: ServiceWrite, principal: AdminDep, repos: ReposDep, container: ContainerDep) -> ServiceView:
    return await CatalogService(repos, container, principal).create_service(body)


@router.put("/services/{service_id}", response_model=ServiceView)
async def update_service(service_id: uuid.UUID, body: ServiceWrite, principal: AdminDep, repos: ReposDep, container: ContainerDep) -> ServiceView:
    return await CatalogService(repos, container, principal).update_service(service_id, body)


@router.get("/assets", response_model=list[AssetView])
async def list_assets(principal: PrincipalDep, repos: ReposDep, container: ContainerDep, service_id: uuid.UUID | None = None, mine: bool = False) -> list[AssetView]:
    return await CatalogService(repos, container, principal).assets(service_id=service_id, mine=mine)


@router.post("/assets", response_model=AssetView, status_code=status.HTTP_201_CREATED)
async def create_asset(body: AssetWrite, principal: AdminDep, repos: ReposDep, container: ContainerDep) -> AssetView:
    return await CatalogService(repos, container, principal).create_asset(body)
