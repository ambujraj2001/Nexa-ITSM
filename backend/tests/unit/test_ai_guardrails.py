"""The V1 human-execution boundary and structured AI output handling."""

from __future__ import annotations

import pytest
from langchain_core.tools import StructuredTool

from app.agents.guardrails import UnsafeToolError, assert_read_only_tools, contains_execution_claim, neutralise_execution_claims, strip_reasoning
from app.agents.runner import build_agent
from app.agents.schemas import DiagnosisReport, PlanStep, TriageResult
from app.infrastructure.litellm import _extract_json
from app.services.resolution_service import sanitize_plan
from app.services.triage_service import TriageService
from tests.fakes import VPN_DIAGNOSIS, VPN_PLAN, VPN_TRIAGE, FakeAgentModel


def _tool(name: str) -> StructuredTool:
    async def fn(query: str = "") -> str:
        return f"{name} result for {query}"

    return StructuredTool.from_function(coroutine=fn, name=name, description=f"{name} tool")


@pytest.mark.parametrize("name", ["restart_server", "delete_resource", "modify_production_config", "run_production_command", "execute", "deploy_app", "update_dns"])
def test_action_tools_are_refused_at_build_time(name: str) -> None:
    with pytest.raises(UnsafeToolError):
        assert_read_only_tools([_tool(name)])


def test_read_only_tools_are_allowed() -> None:
    assert assert_read_only_tools([_tool("search_knowledge"), _tool("get_ticket"), _tool("recommend_assignment")]) == [
        "search_knowledge", "get_ticket", "recommend_assignment",
    ]


async def test_deep_agent_only_sees_nexa_tools_and_returns_structured_output() -> None:
    model = FakeAgentModel(canned={"DiagnosisReport": VPN_DIAGNOSIS}, first_tool={"DiagnosisReport": ("search_knowledge", {"query": "vpn cert"})})
    agent = build_agent(model=model, tools=[_tool("search_knowledge")], system_prompt="test", response_format=DiagnosisReport, name="t")
    result = await agent.ainvoke({"messages": [{"role": "user", "content": "VPN broken"}]})
    assert isinstance(result["structured_response"], DiagnosisReport)
    offered = {name for call in model.offered for name in call}
    # Deep Agents' built-in shell/filesystem/subagent tools never reach the model.
    assert offered <= {"search_knowledge", "DiagnosisReport"}, offered
    assert {"execute", "write_file", "edit_file", "task", "ls", "read_file"}.isdisjoint(offered)


async def test_hallucinated_action_tool_call_is_blocked() -> None:
    model = FakeAgentModel(
        canned={"DiagnosisReport": VPN_DIAGNOSIS},
        first_tool={"DiagnosisReport": ("execute", {"command": "systemctl restart vpn-gateway"})},
        force_first_tool=True,
    )
    agent = build_agent(model=model, tools=[_tool("search_knowledge")], system_prompt="test", response_format=DiagnosisReport, name="t")
    result = await agent.ainvoke({"messages": [{"role": "user", "content": "x"}]})
    blocked = [m for m in result["messages"] if m.type == "tool" and m.name == "execute"]
    assert blocked and "not available" in str(blocked[0].content)
    assert isinstance(result["structured_response"], DiagnosisReport)


def test_execution_claims_are_rewritten() -> None:
    assert contains_execution_claim("I have restarted the VPN gateway")
    rewritten = neutralise_execution_claims("I have restarted the VPN gateway")
    assert "restarted" in rewritten and not rewritten.lower().startswith("i have")
    assert not contains_execution_claim("Restart the VPN gateway after verifying the certificate")


def test_reasoning_traces_are_stripped() -> None:
    assert strip_reasoning("<think>secret chain of thought</think>Likely an expired certificate.") == "Likely an expired certificate."


def test_plan_sanitization() -> None:
    steps = sanitize_plan([PlanStep.model_validate(s) for s in VPN_PLAN["steps"]] + [PlanStep(description="Test user authentication")])
    descriptions = [s.description for s in steps]
    assert len(descriptions) == len(set(d.lower() for d in descriptions)), "duplicates removed"
    assert not any(contains_execution_claim(d) for d in descriptions)
    assert steps[1].technical_details and "openssl" in steps[1].technical_details


def test_triage_postprocess_normalises_taxonomy() -> None:
    result = TriageService.postprocess(TriageResult.model_validate(VPN_TRIAGE))
    assert (result.category, result.subcategory) == ("Network", "VPN")
    assert result.signals[0].value == "CERT_AUTHORITY_INVALID"


@pytest.mark.parametrize(
    "raw",
    ['{"a": 1}', '```json\n{"a": 1}\n```', 'Sure! Here you go: {"a": 1} Hope that helps.'],
)
def test_json_extraction_tolerates_wrappers(raw: str) -> None:
    assert _extract_json(raw) == {"a": 1}


def test_schemas_trim_and_bound_values() -> None:
    report = DiagnosisReport.model_validate({**VPN_DIAGNOSIS, "diagnosis": "x" * 2000})
    assert len(report.diagnosis) <= 400
    with pytest.raises(ValueError):
        DiagnosisReport.model_validate({**VPN_DIAGNOSIS, "confidence": 1.7})


def test_assistant_skills_load_and_tools_stay_read_only() -> None:
    from app.agents.guardrails import assert_read_only_tools
    from app.agents.skills import load_skills, skills_index
    from app.agents.tools import ToolContext, assistant_agent_tools

    skills = load_skills()
    assert {"ticket-status", "report-issue", "knowledge-answer", "provide-information", "service-request"} <= set(skills)
    assert all(s.description and s.body for s in skills.values())
    assert "ticket-status:" in skills_index()
    tools = assistant_agent_tools(ToolContext(repos=None, container=None))  # type: ignore[arg-type]
    assert set(assert_read_only_tools(tools)) == {"get_skill", "get_my_ticket", "list_my_tickets", "search_knowledge"}
