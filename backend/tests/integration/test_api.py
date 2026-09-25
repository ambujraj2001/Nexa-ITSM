"""HTTP-level flow through the FastAPI app (auth via dependency override)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_principal, get_session
from app.container import Container
from app.domain.policies import Principal
from app.main import create_app
from tests.integration.conftest import World

pytestmark = pytest.mark.integration


@pytest.fixture
async def client(container: Container, session: AsyncSession, world: World) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(container.settings, container=container)
    people: dict[str, Principal] = {
        "employee": world.employee, "other": world.other_employee, "l1": world.l1, "l2": world.l2, "admin": world.admin,
    }

    async def principal_override(request: Request) -> Principal:
        from app.core.errors import NotAuthenticated

        who = request.headers.get("x-test-user")
        if who not in people:
            raise NotAuthenticated("Sign in to continue.")
        return people[who]

    async def session_override() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_principal] = principal_override
    app.dependency_overrides[get_session] = session_override
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://api.test") as c:
        yield c


def as_(who: str) -> dict[str, str]:
    return {"x-test-user": who}


async def test_health_is_public_and_leaks_no_secrets(client: httpx.AsyncClient) -> None:
    body = (await client.get("/health")).json()
    assert body["status"] == "ok"
    assert "key" not in str(body).lower() and "token" not in str(body).lower()


async def test_protected_endpoints_require_auth_and_use_error_envelope(client: httpx.AsyncClient) -> None:
    res = await client.get("/api/tickets")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "not_authenticated"
    assert res.headers.get("x-request-id")


async def test_roles_are_enforced_server_side(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/dashboard/engineer", headers=as_("employee"))).status_code == 403
    assert (await client.patch("/api/settings/ai", json={"ai_triage_enabled": False}, headers=as_("l1"))).status_code == 403
    res = await client.patch("/api/settings/ai", json={"automatic_actions_enabled": True}, headers=as_("admin"))
    assert res.status_code == 422 and res.json()["error"]["code"] == "automatic_actions_locked"


async def test_employee_to_resolution_over_http(client: httpx.AsyncClient, world: World) -> None:
    conversation = (await client.get("/api/conversations/current", headers=as_("employee"))).json()
    sent = (await client.post(f"/api/conversations/{conversation['id']}/messages", json={"content": "My VPN isn't working"}, headers=as_("employee"))).json()
    proposal = sent["messages"][-1]
    assert proposal["message_type"] == "triage_proposal"
    confirmed = await client.post(f"/api/conversations/{conversation['id']}/proposals/{proposal['id']}/confirm", headers=as_("employee"))
    assert confirmed.status_code == 200
    ticket = confirmed.json()["ticket"]

    # Another employee can't see it (404, not 403).
    assert (await client.get(f"/api/tickets/{ticket['id']}", headers=as_("other"))).status_code == 404

    dashboard = (await client.get("/api/dashboard/engineer", headers=as_("l1"))).json()
    assert ticket["id"] in [t["id"] for t in dashboard["my_tickets"]]

    detail = (await client.get(f"/api/tickets/{ticket['ticket_number']}", headers=as_("l1"))).json()
    assert detail["view"] == "engineer" and detail["analysis"]["diagnosis"]
    step_id = detail["steps"][0]["id"]
    steps = (await client.patch(f"/api/tickets/{ticket['id']}/steps/{step_id}", json={"status": "completed"}, headers=as_("l1"))).json()
    assert steps[0]["status"] == "completed"

    draft = (await client.post(f"/api/tickets/{ticket['id']}/resolution-draft", headers=as_("l1"))).json()
    assert draft["resolution_summary"]
    resolved = await client.post(f"/api/tickets/{ticket['id']}/resolve", json={"resolution_summary": draft["resolution_summary"]}, headers=as_("l1"))
    assert resolved.status_code == 200 and resolved.json()["status"] == "resolved"

    employee_view = (await client.get(f"/api/tickets/{ticket['id']}", headers=as_("employee"))).json()
    assert employee_view["view"] == "employee" and employee_view["resolution"]["summary"]
    assert "analysis" not in employee_view and "steps" in employee_view
    assert all("technical_details" not in s for s in employee_view["steps"])

    activity = (await client.get(f"/api/tickets/{ticket['id']}/activity", headers=as_("employee"))).json()
    assert any(a["summary"] == "Resolved" for a in activity)
    assert not any("diagnosis" in a["summary"].lower() for a in activity)  # internal AI events hidden from employees
