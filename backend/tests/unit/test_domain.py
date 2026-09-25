"""Pure business rules: priority, SLA, lifecycle, routing, taxonomy."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.core.errors import Conflict
from app.domain.enums import Priority, TicketStatus
from app.domain.priority import determine_priority
from app.domain.sla import SlaState, compute_targets, format_duration, snapshot
from app.domain.state_machine import can_transition, ensure_transition
from app.domain.taxonomy import normalize_category
from app.services.assignment_service import match_rule


class TestPriority:
    def test_individual_blocked_user_is_p2(self) -> None:
        # "My VPN stopped working and I can't work" → individual × critical
        assert determine_priority(impact="individual", urgency="critical").priority == Priority.P2

    def test_org_wide_outage_is_p1(self) -> None:
        assert determine_priority(impact="organization", urgency="high").priority == Priority.P1

    def test_minor_individual_issue_is_p4(self) -> None:
        assert determine_priority(impact="individual", urgency="low").priority == Priority.P4

    def test_falls_back_to_ai_suggestion_then_default(self) -> None:
        assert determine_priority(impact=None, urgency=None, ai_suggestion="P2").priority == Priority.P2
        assert determine_priority(impact=None, urgency=None).priority == Priority.P3

    def test_security_incidents_are_at_least_p2(self) -> None:
        decision = determine_priority(impact="individual", urgency="low", category="Security")
        assert decision.priority == Priority.P2
        assert "security" in decision.reason

    def test_critical_service_raises_wide_impact_to_p1(self) -> None:
        assert determine_priority(impact="department", urgency="medium", service_criticality="critical").priority == Priority.P1

    def test_service_requests_are_capped(self) -> None:
        assert determine_priority(impact="organization", urgency="high", ticket_type="service_request").priority == Priority.P3
        assert determine_priority(impact="organization", urgency="critical", ticket_type="service_request").priority == Priority.P2


class TestSla:
    start = datetime(2026, 9, 25, 9, 0, tzinfo=UTC)

    def test_targets_from_policy(self) -> None:
        targets = compute_targets(self.start, response_minutes=60, resolution_minutes=480)
        assert targets.response_due_at == self.start + timedelta(hours=1)
        assert targets.resolution_due_at == self.start + timedelta(hours=8)

    def test_states(self) -> None:
        due = self.start + timedelta(hours=8)
        assert snapshot(due_at=due, window_start=self.start, now=self.start + timedelta(hours=1)).state == SlaState.ON_TRACK
        assert snapshot(due_at=due, window_start=self.start, now=self.start + timedelta(hours=6, minutes=30)).state == SlaState.AT_RISK
        assert snapshot(due_at=due, window_start=self.start, now=due - timedelta(minutes=30)).state == SlaState.DUE_SOON
        breached = snapshot(due_at=due, window_start=self.start, now=due + timedelta(minutes=12))
        assert breached.state == SlaState.BREACHED and breached.label == "Breached 12m ago"
        assert snapshot(due_at=due, window_start=self.start, now=due, resolved_at=due - timedelta(hours=1)).state == SlaState.MET
        assert snapshot(due_at=None, window_start=None, now=self.start).state == SlaState.NONE

    @pytest.mark.parametrize(
        ("seconds", "label"),
        [(30, "<1m"), (38 * 60, "38m"), (2 * 3600 + 15 * 60, "2h 15m"), (5 * 3600, "5h"), (26 * 3600, "1d 2h"), (3 * 86400, "3d")],
    )
    def test_duration_labels(self, seconds: int, label: str) -> None:
        assert format_duration(seconds) == label


class TestLifecycle:
    def test_happy_path(self) -> None:
        for a, b in [("new", "triaging"), ("triaging", "assigned"), ("assigned", "in_progress"), ("in_progress", "pending_user"),
                     ("pending_user", "pending_engineer"), ("pending_engineer", "escalated"), ("escalated", "resolved"),
                     ("resolved", "closed"), ("closed", "reopened"), ("reopened", "in_progress")]:
            assert can_transition(a, b), f"{a} → {b}"

    def test_resolved_ticket_cannot_jump_back_to_work(self) -> None:
        with pytest.raises(Conflict):
            ensure_transition(TicketStatus.RESOLVED, TicketStatus.IN_PROGRESS)

    def test_cannot_resolve_before_triage(self) -> None:
        assert not can_transition("new", "resolved")


class TestTaxonomy:
    def test_normalises_case_and_unknowns(self) -> None:
        assert normalize_category("network", "vpn") == ("Network", "VPN")
        assert normalize_category("Quantum", "stuff") == ("Other", "stuff")
        assert normalize_category("Access", None) == ("Access", None)


def rule(name: str, team: uuid.UUID, order: int = 100, enabled: bool = True, **conditions: object) -> SimpleNamespace:
    base = {"category": None, "subcategory": None, "priority": None, "ticket_type": None, "service_id": None}
    return SimpleNamespace(name=name, team_id=team, sort_order=order, enabled=enabled, support_level="L1", **{**base, **conditions})


class TestAssignmentRules:
    network, desk, security = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    def test_most_specific_rule_wins(self) -> None:
        rules = [rule("network", self.network, category="Network"), rule("vpn", self.desk, category="Network", subcategory="VPN")]
        picked = match_rule(rules, category="Network", subcategory="VPN", priority="P2", ticket_type="incident", service_id=None)
        assert picked.name == "vpn"

    def test_sort_order_breaks_ties_and_disabled_rules_are_ignored(self) -> None:
        rules = [
            rule("b", self.desk, order=20, category="Network"),
            rule("a", self.network, order=10, category="Network"),
            rule("off", self.security, order=1, category="Network", enabled=False),
        ]
        assert match_rule(rules, category="network", subcategory=None, priority=None, ticket_type=None, service_id=None).name == "a"

    def test_no_match_and_unconditional_rules(self) -> None:
        rules = [rule("catch-all", self.desk), rule("sec", self.security, category="Security")]
        assert match_rule(rules, category="Hardware", subcategory=None, priority=None, ticket_type=None, service_id=None) is None
