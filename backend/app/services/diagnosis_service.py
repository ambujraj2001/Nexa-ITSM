"""Diagnosis: the strong-model investigation Deep Agent, plus evidence checks."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.agents import prompts
from app.agents.guardrails import clean_list, neutralise_execution_claims
from app.agents.runner import build_agent, run_agent
from app.agents.schemas import DiagnosisReport, EvidenceItem
from app.agents.tools import ToolContext, investigation_tools
from app.models import Ticket, TicketAiAnalysis
from app.repositories.knowledge_repository import IncidentHit, KnowledgeHit
from app.services.base import Service
from app.utils.text import truncate

# If the model cites evidence its tools never returned, we drop it and cap confidence.
UNVERIFIED_EVIDENCE_CONFIDENCE_CAP = 0.6


@dataclass
class DiagnosisOutcome:
    report: DiagnosisReport
    evidence: list[dict]
    recommended_team_id: object | None
    model: str | None
    dropped_references: list[str]


async def investigation_brief(
    service: Service,
    ticket: Ticket,
    analysis: TicketAiAnalysis | None,
    knowledge: Sequence[KnowledgeHit],
    incidents: Sequence[IncidentHit],
) -> str:
    repos = service.repos
    requester = await repos.users.get(ticket.requester_id)
    assets = await repos.settings.assets_for_owner(ticket.requester_id)
    svc = await repos.settings.get_service(ticket.service_id) if ticket.service_id else None
    teams = await repos.users.list_teams()
    lines = [
        f"Ticket {ticket.ticket_number} ({ticket.ticket_type}, {ticket.priority})",
        f"Title: {ticket.title}",
        "Reported by: "
        + ", ".join(filter(None, [requester.name if requester else "unknown", requester.job_title if requester else None, requester.department if requester else None, requester.location if requester else None])),
        f"Reported at: {ticket.created_at.isoformat()}",
        f'Requester\'s words: """{truncate(ticket.description, 3000)}"""',
    ]
    if analysis and analysis.signals:
        lines.append("Facts the requester stated: " + "; ".join(f"{s.get('label')}: {s.get('value')}" for s in analysis.signals if isinstance(s, dict)))
    if ticket.category:
        lines.append(f"Triage: {ticket.category}" + (f" / {ticket.subcategory}" if ticket.subcategory else ""))
    if analysis and analysis.diagnosis:
        lines.append(f"Preliminary cause from triage (unverified): {analysis.diagnosis}")
    if svc:
        lines.append(f"Service: {svc.name} (criticality {svc.criticality})")
    if assets:
        lines.append("Requester assets: " + "; ".join(f"{a.name} ({a.asset_type}) {a.metadata_}" for a in assets[:5]))
    lines.append("")
    lines.append("Knowledge already retrieved (search_knowledge):")
    lines += [f"- {h.article_number} “{h.title}”: {truncate(h.excerpt, 500)}" for h in knowledge] or ["- none"]
    lines.append("Similar resolved incidents already retrieved (search_historical_incidents):")
    lines += [f"- {h.ticket_number} “{h.title}” → resolution: {truncate(h.resolution_summary, 300)}" for h in incidents] or ["- none"]
    lines.append("")
    lines.append("Teams you may recommend: " + ", ".join(t.name for t in teams))
    return "\n".join(lines)


class DiagnosisService(Service):
    async def diagnose(
        self,
        ticket: Ticket,
        *,
        analysis: TicketAiAnalysis | None,
        knowledge: Sequence[KnowledgeHit],
        incidents: Sequence[IncidentHit],
    ) -> DiagnosisOutcome:
        ctx = ToolContext(repos=self.repos, container=self.container, ticket_id=ticket.id, requester_id=ticket.requester_id)
        ctx.remember(*(h.article_number for h in knowledge), *(h.ticket_number for h in incidents))
        brief = await investigation_brief(self, ticket, analysis, knowledge, incidents)
        model_alias = self.settings.model_for_task("diagnosis") or None
        agent = build_agent(
            model=self.container.chat_model("diagnosis", ticket_id=str(ticket.id)),
            tools=investigation_tools(ctx),
            system_prompt=prompts.DIAGNOSIS,
            response_format=DiagnosisReport,
            name="nexa-diagnosis",
        )
        result = await run_agent(
            agent,
            messages=[{"role": "user", "content": brief + "\n\nInvestigate and return the DiagnosisReport."}],
            schema=DiagnosisReport,
            audit=self.repos.audit,
            agent_name="nexa-diagnosis",
            operation="diagnosis",
            model_label=model_alias,
            ticket_id=ticket.id,
            tool_calls_counter=ctx,
            timeout_seconds=min(300.0, float(self.settings.investigation_timeout_seconds)),
        )
        report: DiagnosisReport = result.output
        evidence, dropped = await self._verify_evidence(report.evidence, ctx, knowledge, incidents)
        confidence = report.confidence
        if dropped:
            confidence = min(confidence, UNVERIFIED_EVIDENCE_CONFIDENCE_CAP)
        team = await self.repos.users.get_team_by_name(report.recommended_team) if report.recommended_team else None
        cleaned = report.model_copy(
            update={
                "diagnosis": neutralise_execution_claims(report.diagnosis) or report.diagnosis,
                "summary": neutralise_execution_claims(report.summary) or report.summary,
                "rationale": neutralise_execution_claims(report.rationale) or report.rationale,
                "confidence": round(confidence, 3),
                "missing_information": clean_list(report.missing_information, limit=4),
                "hypotheses": report.hypotheses[:3],
            }
        )
        return DiagnosisOutcome(report=cleaned, evidence=evidence, recommended_team_id=team.id if team else None, model=model_alias, dropped_references=dropped)

    async def _verify_evidence(
        self, items: Sequence[EvidenceItem], ctx: ToolContext, knowledge: Sequence[KnowledgeHit], incidents: Sequence[IncidentHit]
    ) -> tuple[list[dict], list[str]]:
        kb_titles = {h.article_number.upper(): (h.title, h.article_id) for h in knowledge}
        inc_titles = {h.ticket_number.upper(): (h.title, h.ticket_id) for h in incidents}
        kept: list[dict] = []
        dropped: list[str] = []
        for item in items[:6]:
            ref = (item.reference or "").strip().upper() or None
            if item.source_type in ("knowledge_article", "historical_incident"):
                if not ref or ref not in ctx.seen_references:
                    dropped.append(ref or "(missing reference)")
                    continue
            title, ref_id = None, None
            if item.source_type == "knowledge_article" and ref:
                title, ref_id = kb_titles.get(ref, (None, None))
                if title is None:
                    article = await self.repos.knowledge.get_by_number(ref)
                    title, ref_id = (article.title, article.id) if article else (None, None)
            elif item.source_type == "historical_incident" and ref:
                title, ref_id = inc_titles.get(ref, (None, None))
                if title is None:
                    other = await self.repos.tickets.get_by_number(ref)
                    title, ref_id = (other.title, other.id) if other else (None, None)
            kept.append(
                {
                    "source_type": item.source_type,
                    "reference": ref,
                    "title": title,
                    "summary": neutralise_execution_claims(item.summary) or item.summary,
                    "ref_id": str(ref_id) if ref_id else None,
                }
            )
        return kept, dropped
