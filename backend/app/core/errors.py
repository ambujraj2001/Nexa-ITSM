"""Application error types and their safe HTTP representations.

Handlers never leak internals: unexpected exceptions become a generic 500 with
the request id, while the full detail goes to logs/traces only.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    status_code: int = 400
    code: str = "bad_request"

    def __init__(self, message: str, *, code: str | None = None, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.details = details or {}


class NotAuthenticated(AppError):
    status_code = 401
    code = "not_authenticated"


class PermissionDenied(AppError):
    status_code = 403
    code = "forbidden"


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class Conflict(AppError):
    status_code = 409
    code = "conflict"


class ValidationFailed(AppError):
    status_code = 422
    code = "validation_failed"


class PolicyViolation(AppError):
    """A request that V1's human-in-the-loop policy forbids (e.g. enabling automation)."""

    status_code = 422
    code = "policy_violation"


class RateLimited(AppError):
    status_code = 429
    code = "rate_limited"

    def __init__(self, message: str = "Too many requests. Please slow down.", *, retry_after: int = 60) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class ServiceUnavailable(AppError):
    status_code = 503
    code = "service_unavailable"


class AIUnavailable(AppError):
    """The AI layer could not produce a result. Callers degrade to manual flows."""

    status_code = 503
    code = "ai_unavailable"
