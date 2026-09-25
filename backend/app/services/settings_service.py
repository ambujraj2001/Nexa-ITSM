"""AI & automation settings, SLA policies, assignment rules, knowledge sources, integrations."""

from __future__ import annotations

import os
import uuid

from sqlalchemy import func, select

from app.container import Container
from app.core.errors import NotFound, PolicyViolation, ValidationFailed
from app.core.redaction import is_sensitive_key
from app.domain import policies
from app.domain.policies import Principal
from app.domain.taxonomy import normalize_category
from app.integrations import provider_for
from app.models import AssignmentRule, IncidentEmbedding, Integration, KnowledgeArticle, KnowledgeSource, SlaPolicy, Ticket
from app.schemas.misc import (
    AiPolicyView,
    AiSettingsUpdate,
    AiSettingsView,
    AssignmentRuleView,
    AssignmentRuleWrite,
    IntegrationUpdate,
    IntegrationView,
    KnowledgeSourceView,
    ModelRouteView,
    RoutingPreview,
    RoutingPreviewRequest,
    SlaPolicyUpdate,
    SlaPolicyView,
)
from app.services.assignment_service import AssignmentService
from app.services.audit_service import AuditService
from app.services.base import Repos, Service
from app.services.presenters import person_ref, service_ref, team_ref

V1_AUTOMATION_MESSAGE = "Automatic infrastructure actions are not available in V1. Engineers execute all remediation."
V1_APPROVAL_MESSAGE = "Human approval is required in V1 and can't be turned off."


class SettingsService(Service):
    def __init__(self, repos: Repos, container: Container, principal: Principal) -> None:
        super().__init__(repos, container)
        self.principal = principal
        self.audit = AuditService(repos.audit)

    # ── AI & automation ──────────────────────────────────────────────────
    async def _knowledge_sources(self) -> list[KnowledgeSourceView]:
        sources = await self.repos.settings.knowledge_sources()
        articles = int((await self.session.execute(select(func.count()).select_from(KnowledgeArticle).where(KnowledgeArticle.status == "published"))).scalar() or 0)
        indexed = int((await self.session.execute(select(func.count()).select_from(KnowledgeArticle).where(KnowledgeArticle.status == "published", KnowledgeArticle.embedding_status == "indexed"))).scalar() or 0)
        incidents = int((await self.session.execute(select(func.count()).select_from(Ticket).where(Ticket.status.in_(["resolved", "closed"])))).scalar() or 0)
        incidents_indexed = int((await self.session.execute(select(func.count()).select_from(IncidentEmbedding))).scalar() or 0)
        out = []
        for s in sources:
            count, done = (articles, indexed) if s.source_type == "internal_articles" else ((incidents, incidents_indexed) if s.source_type == "incident_history" else (0, 0))
            out.append(KnowledgeSourceView(id=s.id, name=s.name, source_type=s.source_type, description=s.description, enabled=s.enabled, item_count=count, indexed_count=done, last_indexed_at=s.last_indexed_at))
        return out

    async def _integration_view(self, integration: Integration) -> IntegrationView:
        status = await provider_for(integration.provider).check(enabled=integration.enabled, settings=self.settings, secret_ref=integration.secret_ref)
        return IntegrationView(
            id=integration.id, provider=integration.provider, display_name=integration.display_name, category=integration.category,
            description=integration.description, enabled=integration.enabled, status=status.status, config=integration.config or {},
            secret_ref=integration.secret_ref, secret_present=bool(integration.secret_ref and os.environ.get(integration.secret_ref)),
            available=status.available, status_detail=status.detail, last_checked_at=integration.last_checked_at, last_error=integration.last_error,
        )

    async def ai_settings(self) -> AiSettingsView:
        policies.ensure_staff(self.principal)
        config = await self.repos.settings.ai_configuration()
        updated_by = await self.repos.users.get(config.updated_by) if config.updated_by else None
        return AiSettingsView(
            ai_triage_enabled=config.ai_triage_enabled,
            ai_diagnosis_enabled=config.ai_diagnosis_enabled,
            resolution_plans_enabled=config.resolution_plans_enabled,
            automatic_actions_enabled=config.automatic_actions_enabled,
            human_approval_required=config.human_approval_required,
            confidence_threshold=float(config.confidence_threshold),
            policy=AiPolicyView(),
            models=ModelRouteView.model_validate(self.container.models.describe()),
            knowledge_sources=await self._knowledge_sources(),
            integrations=[await self._integration_view(i) for i in await self.repos.settings.integrations()],
            updated_at=config.updated_at,
            updated_by=person_ref(updated_by, include_email=False),
            can_edit=self.principal.is_admin,
        )

    async def update_ai(self, patch: AiSettingsUpdate) -> AiSettingsView:
        policies.ensure_admin(self.principal)
        changes = patch.model_dump(exclude_unset=True, exclude_none=True)
        # V1 human-in-the-loop boundary (also enforced by a DB CHECK constraint).
        if changes.get("automatic_actions_enabled") is True:
            raise PolicyViolation(V1_AUTOMATION_MESSAGE, code="automatic_actions_locked")
        if changes.get("human_approval_required") is False:
            raise PolicyViolation(V1_APPROVAL_MESSAGE, code="human_approval_locked")
        config = await self.repos.settings.ai_configuration(for_update=True)
        old = {k: float(getattr(config, k)) if k == "confidence_threshold" else getattr(config, k) for k in changes}
        effective = {k: v for k, v in changes.items() if old.get(k) != v}
        for field, value in effective.items():
            setattr(config, field, round(value, 2) if field == "confidence_threshold" else value)
        if effective:
            config.updated_by = self.principal.profile_id
            await self.audit.record("settings.ai_updated", actor=self.principal, entity_type="ai_configuration", entity_id=None, old_value={k: old[k] for k in effective}, new_value=effective)
            await self.commit()
        return await self.ai_settings()

    # ── SLA policies ─────────────────────────────────────────────────────
    @staticmethod
    def _sla_view(p: SlaPolicy) -> SlaPolicyView:
        return SlaPolicyView(id=p.id, name=p.name, priority=p.priority, response_time_minutes=p.response_time_minutes, resolution_time_minutes=p.resolution_time_minutes, enabled=p.enabled, updated_at=p.updated_at)

    async def sla_policies(self) -> list[SlaPolicyView]:
        policies.ensure_staff(self.principal)
        return [self._sla_view(p) for p in await self.repos.settings.sla_policies()]

    async def update_sla(self, policy_id: uuid.UUID, patch: SlaPolicyUpdate) -> SlaPolicyView:
        policies.ensure_admin(self.principal)
        policy = await self.repos.settings.get_sla_policy(policy_id)
        if policy is None:
            raise NotFound("SLA policy not found.")
        changes = patch.model_dump(exclude_unset=True, exclude_none=True)
        response = changes.get("response_time_minutes", policy.response_time_minutes)
        resolution = changes.get("resolution_time_minutes", policy.resolution_time_minutes)
        if response > resolution:
            raise ValidationFailed("The response target must not be longer than the resolution target.")
        old = {k: getattr(policy, k) for k in changes}
        for k, v in changes.items():
            setattr(policy, k, v)
        await self.audit.record("settings.sla_updated", actor=self.principal, entity_type="sla_policy", entity_id=policy.id, old_value=old, new_value=changes)
        await self.commit()
        return self._sla_view(policy)

    # ── assignment rules ─────────────────────────────────────────────────
    async def _rule_view(self, rule: AssignmentRule) -> AssignmentRuleView:
        team = await self.repos.users.get_team(rule.team_id)
        service = await self.repos.settings.get_service(rule.service_id) if rule.service_id else None
        return AssignmentRuleView(
            id=rule.id, name=rule.name, category=rule.category, subcategory=rule.subcategory, priority=rule.priority,
            ticket_type=rule.ticket_type, service=service_ref(service), team=team_ref(team), support_level=rule.support_level,  # type: ignore[arg-type]
            sort_order=rule.sort_order, enabled=rule.enabled, updated_at=rule.updated_at,
        )

    async def rules(self) -> list[AssignmentRuleView]:
        policies.ensure_staff(self.principal)
        return [await self._rule_view(r) for r in await self.repos.settings.assignment_rules()]

    async def _validate_rule(self, data: AssignmentRuleWrite) -> dict:
        if await self.repos.users.get_team(data.team_id) is None:
            raise ValidationFailed("Unknown team.")
        if data.service_id and await self.repos.settings.get_service(data.service_id) is None:
            raise ValidationFailed("Unknown service.")
        values = data.model_dump()
        if data.category:
            values["category"], values["subcategory"] = normalize_category(data.category, data.subcategory)
        if not any(values.get(k) for k in ("category", "subcategory", "priority", "ticket_type", "service_id")):
            raise ValidationFailed("A rule needs at least one condition (category, subcategory, priority, type or service).")
        for k in ("priority", "ticket_type", "support_level"):
            if values.get(k) is not None:
                values[k] = str(getattr(values[k], "value", values[k]))
        return values

    async def create_rule(self, data: AssignmentRuleWrite) -> AssignmentRuleView:
        policies.ensure_admin(self.principal)
        rule = AssignmentRule(**await self._validate_rule(data))
        await self.repos.settings.add(rule)
        await self.audit.record("settings.rule_created", actor=self.principal, entity_type="assignment_rule", entity_id=rule.id, new_value={"name": rule.name})
        await self.commit()
        return await self._rule_view(rule)

    async def update_rule(self, rule_id: uuid.UUID, data: AssignmentRuleWrite) -> AssignmentRuleView:
        policies.ensure_admin(self.principal)
        rule = await self.repos.settings.get_rule(rule_id)
        if rule is None:
            raise NotFound("Rule not found.")
        values = await self._validate_rule(data)
        old = {k: str(getattr(rule, k)) if getattr(rule, k) is not None else None for k in values}
        for k, v in values.items():
            setattr(rule, k, v)
        await self.audit.record("settings.rule_updated", actor=self.principal, entity_type="assignment_rule", entity_id=rule.id, old_value=old, new_value={k: str(v) if v is not None else None for k, v in values.items()})
        await self.commit()
        return await self._rule_view(rule)

    async def delete_rule(self, rule_id: uuid.UUID) -> None:
        policies.ensure_admin(self.principal)
        rule = await self.repos.settings.get_rule(rule_id)
        if rule is None:
            raise NotFound("Rule not found.")
        await self.audit.record("settings.rule_deleted", actor=self.principal, entity_type="assignment_rule", entity_id=rule.id, old_value={"name": rule.name})
        await self.repos.settings.delete(rule)
        await self.commit()

    async def preview_routing(self, request: RoutingPreviewRequest) -> RoutingPreview:
        policies.ensure_staff(self.principal)
        category, subcategory = normalize_category(request.category, request.subcategory) if request.category else (None, request.subcategory)
        service = AssignmentService(self.repos, self.audit)
        decision = await service.route(
            category=category, subcategory=subcategory, priority=request.priority.value if request.priority else None,
            ticket_type=request.ticket_type.value, service_id=request.service_id,
        )
        team = await self.repos.users.get_team(decision.team_id) if decision.team_id else None
        engineer = await service.pick_engineer(decision.team_id, decision.support_level) if decision.team_id else None
        return RoutingPreview(team=team_ref(team), support_level=decision.support_level, reason=decision.reason, rule_name=decision.rule_name, engineer=person_ref(engineer, include_email=False))

    # ── knowledge sources ────────────────────────────────────────────────
    async def update_knowledge_source(self, source_id: uuid.UUID, enabled: bool) -> list[KnowledgeSourceView]:
        policies.ensure_admin(self.principal)
        source: KnowledgeSource | None = await self.repos.settings.get_knowledge_source(source_id)
        if source is None:
            raise NotFound("Knowledge source not found.")
        if source.enabled != enabled:
            await self.audit.record("settings.knowledge_source_updated", actor=self.principal, entity_type="knowledge_source", entity_id=source.id, old_value={"enabled": source.enabled}, new_value={"enabled": enabled})
            source.enabled = enabled
            await self.commit()
        return await self._knowledge_sources()

    async def reindex(self) -> dict[str, int]:
        policies.ensure_admin(self.principal)
        from app.services.knowledge_service import schedule_article_index, schedule_incident_index

        article_ids = await self.repos.knowledge.articles_missing_embeddings()
        resolved = (await self.session.execute(select(Ticket.id).where(Ticket.status.in_(["resolved", "closed"]), Ticket.resolved_at.is_not(None)))).scalars().all()
        for article_id in article_ids:
            await schedule_article_index(self.container, article_id)
        for ticket_id in resolved:
            await schedule_incident_index(self.container, ticket_id)
        await self.audit.record("knowledge.reindex_requested", actor=self.principal, entity_type="knowledge", metadata={"articles": len(article_ids), "incidents": len(resolved)})
        await self.commit()
        return {"articles": len(article_ids), "incidents": len(resolved)}

    # ── integrations ─────────────────────────────────────────────────────
    async def update_integration(self, integration_id: uuid.UUID, patch: IntegrationUpdate) -> IntegrationView:
        policies.ensure_admin(self.principal)
        integration = await self.repos.settings.get_integration(integration_id)
        if integration is None:
            raise NotFound("Integration not found.")
        status = await provider_for(integration.provider).check(enabled=integration.enabled, settings=self.settings, secret_ref=integration.secret_ref)
        if patch.enabled is True and not status.available:
            raise ValidationFailed(f"The {integration.display_name} connector isn't available in this release.")
        if patch.config is not None:
            for key_name, value in patch.config.items():
                if is_sensitive_key(key_name) or (isinstance(value, str) and len(value) > 500):
                    raise ValidationFailed("Store credentials in the environment and reference them by name; integration settings hold non-secret values only.")
        old = {"enabled": integration.enabled, "config": integration.config}
        if patch.enabled is not None:
            integration.enabled = patch.enabled
        if patch.config is not None:
            integration.config = patch.config
        await self.audit.record("settings.integration_updated", actor=self.principal, entity_type="integration", entity_id=integration.id, old_value=old, new_value=patch.model_dump(exclude_unset=True))
        await self.commit()
        return await self._integration_view(integration)

