"""Dashboards: engineer Operations Dispatch and the employee home."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.api.deps import ContainerDep, PrincipalDep, ReposDep, StaffDep
from app.schemas.misc import EmployeeDashboard, EngineerDashboard, UserView
from app.services.admin_service import AdminService
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/api", tags=["dashboards"])


@router.get("/dashboard/engineer", response_model=EngineerDashboard)
async def engineer_dashboard(principal: StaffDep, repos: ReposDep, container: ContainerDep) -> EngineerDashboard:
    return await DashboardService(repos, container, principal).engineer()


@router.get("/dashboard/employee", response_model=EmployeeDashboard)
async def employee_dashboard(principal: PrincipalDep, repos: ReposDep, container: ContainerDep) -> EmployeeDashboard:
    return await DashboardService(repos, container, principal).employee()


@router.get("/engineers", response_model=list[UserView])
async def assignable_engineers(principal: StaffDep, repos: ReposDep, container: ContainerDep, team_id: uuid.UUID | None = None) -> list[UserView]:
    return await AdminService(repos, container, principal).assignable(team_id)
