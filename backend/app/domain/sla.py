"""SLA arithmetic (calendar time, 24×7). Pure functions; the service layer supplies policies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum


class SlaState(StrEnum):
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    DUE_SOON = "due_soon"
    BREACHED = "breached"
    MET = "met"
    MISSED = "missed"
    NONE = "none"


@dataclass(frozen=True)
class SlaTargets:
    response_due_at: datetime
    resolution_due_at: datetime


@dataclass(frozen=True)
class SlaSnapshot:
    state: SlaState
    due_at: datetime | None
    remaining_seconds: int | None
    label: str


AT_RISK_FRACTION = 0.25


def compute_targets(start: datetime, *, response_minutes: int, resolution_minutes: int) -> SlaTargets:
    return SlaTargets(
        response_due_at=start + timedelta(minutes=response_minutes),
        resolution_due_at=start + timedelta(minutes=resolution_minutes),
    )


def format_duration(seconds: float) -> str:
    """Compact human duration: 38m, 2h 15m, 5h, 1d, 2d 4h."""
    seconds = max(0, int(seconds))
    minutes = seconds // 60
    if minutes < 1:
        return "<1m"
    if minutes < 60:
        return f"{minutes}m"
    hours, mins = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}h {mins}m" if mins else f"{hours}h"
    days, hrs = divmod(hours, 24)
    return f"{days}d {hrs}h" if hrs and days < 3 else f"{days}d"


def snapshot(
    *,
    due_at: datetime | None,
    window_start: datetime | None,
    now: datetime,
    resolved_at: datetime | None = None,
    due_soon_minutes: int = 60,
) -> SlaSnapshot:
    if due_at is None:
        return SlaSnapshot(SlaState.NONE, None, None, "No SLA")

    if resolved_at is not None:
        if resolved_at <= due_at:
            return SlaSnapshot(SlaState.MET, due_at, None, "SLA met")
        return SlaSnapshot(SlaState.MISSED, due_at, None, f"Missed by {format_duration((resolved_at - due_at).total_seconds())}")

    remaining = (due_at - now).total_seconds()
    if remaining < 0:
        return SlaSnapshot(SlaState.BREACHED, due_at, int(remaining), f"Breached {format_duration(-remaining)} ago")

    label = f"{format_duration(remaining)} left"
    if remaining <= due_soon_minutes * 60:
        return SlaSnapshot(SlaState.DUE_SOON, due_at, int(remaining), label)
    if window_start is not None:
        window = (due_at - window_start).total_seconds()
        if window > 0 and remaining <= window * AT_RISK_FRACTION:
            return SlaSnapshot(SlaState.AT_RISK, due_at, int(remaining), label)
    return SlaSnapshot(SlaState.ON_TRACK, due_at, int(remaining), label)
