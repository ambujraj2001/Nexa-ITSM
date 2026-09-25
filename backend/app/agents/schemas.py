"""Typed outputs for every AI operation.

Models must return these shapes; anything that fails validation is repaired
once and otherwise rejected. They carry concise, user/engineer-safe
explanations only — there is deliberately no field for reasoning traces.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Intent = Literal[
    "report_issue",
    "service_request",
    "ticket_status",
    "provide_information",
    "knowledge_question",
    "greeting",
    "other",
]


class _Out(BaseModel):
    model_config = ConfigDict(extra="ignore")


def _trim(value: object, limit: int) -> object:
    if isinstance(value, str):
        return value.strip()[:limit]
    return value


class ExtractedSignal(_Out):
    label: str = Field(description="Short label, e.g. 'OS', 'VPN client', 'Error'.")
    value: str = Field(description="The fact exactly as the user stated it.")
    kind: Literal["device", "application", "error", "location", "timing", "other"] = "other"

    @field_validator("label", "value", mode="before")
    @classmethod
    def _limit(cls, v: object) -> object:
        return _trim(v, 120)


class TriageResult(_Out):
    """Fast-model classification of an employee message."""

    intent: Intent
    reply: str = Field(
        description="One or two warm, plain-language sentences acknowledging the user. Never state ticket facts."
    )
    ticket_type: Literal["incident", "service_request", "problem", "change"] | None = None
    title: str | None = Field(default=None, description="Neutral ticket title, max 80 chars.")
    summary: str | None = Field(default=None, description="One-sentence restatement of the problem or request.")
    category: str | None = None
    subcategory: str | None = None
    impact: Literal["individual", "team", "department", "organization"] | None = None
    urgency: Literal["low", "medium", "high", "critical"] | None = None
    suggested_priority: Literal["P1", "P2", "P3", "P4"] | None = None
    service_hint: str | None = Field(default=None, description="Best matching service name from the catalogue, if any.")
    likely_cause: str | None = Field(default=None, description="Hedged preliminary cause, or null if unclear.")
    confidence: float = Field(default=0.5, ge=0, le=1)
    signals: list[ExtractedSignal] = Field(default_factory=list)
    needs_clarification: bool = False
    clarifying_question: str | None = None
    referenced_ticket_number: str | None = None
    knowledge_query: str | None = None

    @field_validator("title", mode="before")
    @classmethod
    def _title(cls, v: object) -> object:
        return _trim(v, 80)

    @field_validator("reply", "summary", "likely_cause", "clarifying_question", mode="before")
    @classmethod
    def _text(cls, v: object) -> object:
        return _trim(v, 600)


class EvidenceItem(_Out):
    source_type: Literal["knowledge_article", "historical_incident", "user_report", "asset", "service"]
    reference: str | None = Field(
        default=None, description="KB or ticket number exactly as returned by a tool (e.g. KB-102, INC-10231). Null for user_report."
    )
    summary: str = Field(description="How this supports the diagnosis, max 200 chars.")

    @field_validator("summary", mode="before")
    @classmethod
    def _limit(cls, v: object) -> object:
        return _trim(v, 240)


class Hypothesis(_Out):
    cause: str
    likelihood: Literal["high", "medium", "low"]
    how_to_verify: str | None = None

    @field_validator("cause", "how_to_verify", mode="before")
    @classmethod
    def _limit(cls, v: object) -> object:
        return _trim(v, 240)


class DiagnosisReport(_Out):
    """Strong-model investigation result for one ticket."""

    summary: str = Field(description="Neutral one-sentence problem summary.")
    diagnosis: str = Field(description="Most likely cause in one hedged sentence ('… may have expired').")
    confidence: float = Field(ge=0, le=1, description="Calibrated probability that the diagnosis is correct.")
    evidence: list[EvidenceItem] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    rationale: str = Field(description="'Why this was suggested' in 1–3 sentences. A conclusion, not a thought process.")
    missing_information: list[str] = Field(default_factory=list, description="Questions to ask the requester.")
    recommended_team: str | None = Field(default=None, description="Team name from the provided list.")

    @field_validator("summary", "diagnosis", mode="before")
    @classmethod
    def _limit(cls, v: object) -> object:
        return _trim(v, 400)

    @field_validator("rationale", mode="before")
    @classmethod
    def _limit_rationale(cls, v: object) -> object:
        return _trim(v, 600)


class PlanStep(_Out):
    description: str = Field(description="Imperative action for the engineer, max 80 chars ('Verify certificate validity').")
    details: str | None = Field(default=None, description="One sentence: what to check or look for.")
    technical_details: str | None = Field(
        default=None, description="Optional commands/paths the ENGINEER may run by hand. Never executed by Nexa."
    )

    @field_validator("description", mode="before")
    @classmethod
    def _desc(cls, v: object) -> object:
        return _trim(v, 120)

    @field_validator("details", mode="before")
    @classmethod
    def _details(cls, v: object) -> object:
        return _trim(v, 400)

    @field_validator("technical_details", mode="before")
    @classmethod
    def _tech(cls, v: object) -> object:
        return _trim(v, 1200)


class ResolutionPlan(_Out):
    steps: list[PlanStep] = Field(min_length=1)


class KnowledgeAnswer(_Out):
    answer: str = Field(description="Plain-language answer grounded only in the retrieved articles.")
    sources: list[str] = Field(default_factory=list, description="Article numbers actually used, e.g. ['KB-103'].")
    grounded: bool = Field(description="True only if the answer is supported by a retrieved article.")
    suggest_ticket: bool = Field(default=False, description="True if the user likely needs IT to act.")

    @field_validator("answer", mode="before")
    @classmethod
    def _limit(cls, v: object) -> object:
        return _trim(v, 1500)


class CopilotAnswer(_Out):
    answer: str
    references: list[str] = Field(default_factory=list)
    draft_message: str | None = Field(default=None, description="Only when asked to draft a message to the requester.")

    @field_validator("answer", mode="before")
    @classmethod
    def _limit(cls, v: object) -> object:
        return _trim(v, 2500)


class ResolutionDraft(_Out):
    resolution_summary: str = Field(description="Precise record of cause and fix for engineers, 1–3 sentences.")
    employee_summary: str = Field(description="Friendly plain-language explanation for the employee, 1–2 sentences.")

    @field_validator("resolution_summary", "employee_summary", mode="before")
    @classmethod
    def _limit(cls, v: object) -> object:
        return _trim(v, 1200)


class EmployeeResolutionSummary(_Out):
    employee_summary: str

    @field_validator("employee_summary", mode="before")
    @classmethod
    def _limit(cls, v: object) -> object:
        return _trim(v, 800)


class HandoffBrief(_Out):
    summary: str
    completed_checks: list[str] = Field(default_factory=list)
    ruled_out: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    suggested_next: list[str] = Field(default_factory=list)

    @field_validator("summary", mode="before")
    @classmethod
    def _limit(cls, v: object) -> object:
        return _trim(v, 800)


class AssistantDecision(BaseModel):
    """What the employee assistant agent decided to do with the latest message.

    The agent chooses the action; Nexa renders ticket facts from the database and
    builds ticket proposals deterministically, so `reply` is only conversational text.
    """

    action: Literal["status", "propose_ticket", "clarify", "add_information", "knowledge", "reply"]
    reply: str = ""
    ticket_numbers: list[str] = Field(default_factory=list, description="Employee's own tickets (verified with get_my_ticket/list_my_tickets) this is about.")
    requested_refs: list[str] = Field(default_factory=list, description="Ticket numbers the employee mentioned, as written, even if not found.")
    target_ticket_number: str | None = None
    clarifying_question: str | None = None
    knowledge_sources: list[str] = Field(default_factory=list, description="KB references actually used for a knowledge answer.")
    skills_used: list[str] = Field(default_factory=list)


class FollowUps(BaseModel):
    suggestions: list[str] = Field(default_factory=list, description="Up to 3 short follow-up messages the employee might send next.")
