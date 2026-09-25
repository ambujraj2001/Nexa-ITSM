"""Scrubbing of secrets before anything reaches logs or telemetry.

Applied to every structured log event and to span attributes we set ourselves.
Keys that look sensitive are replaced wholesale; string values are scanned for
tokens that commonly leak (JWTs, bearer tokens, API keys, DSNs with passwords).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

REDACTED = "[REDACTED]"

_SENSITIVE_KEY = re.compile(
    r"(authorization|api[_-]?key|apikey|token|secret|password|passwd|cookie|"
    r"service[_-]?role|jwt|credential|private[_-]?key|db[_-]?url|dsn)",
    re.IGNORECASE,
)

_VALUE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # JSON Web Tokens (Supabase access/refresh tokens, service-role keys).
    (re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"), "[REDACTED_JWT]"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}"), "Bearer [REDACTED]"),
    # Provider-style secret keys (sk-..., sb_secret_..., xoxb-...).
    (re.compile(r"\b(sk|sb_secret|sb_publishable|xox[abpr]|xapp)[-_][A-Za-z0-9_-]{12,}"), "[REDACTED_KEY]"),
    # Passwords inside connection strings.
    (re.compile(r"(?i)(postgres(?:ql)?(?:\+asyncpg)?://[^:/\s]+:)[^@\s]+@"), r"\1[REDACTED]@"),
)

# Keys whose values are identifiers, not secrets, despite matching the pattern.
_ALLOWED_KEYS = frozenset({"token_count", "tokens", "input_tokens", "output_tokens", "total_tokens"})


def scrub_string(value: str) -> str:
    for pattern, replacement in _VALUE_PATTERNS:
        value = pattern.sub(replacement, value)
    return value


def is_sensitive_key(key: str) -> bool:
    return key not in _ALLOWED_KEYS and bool(_SENSITIVE_KEY.search(key))


def scrub(value: Any, *, _depth: int = 0) -> Any:
    """Return a copy of `value` with secrets removed (recursively, bounded depth)."""
    if _depth > 6:
        return value
    if isinstance(value, str):
        return scrub_string(value)
    if isinstance(value, Mapping):
        return {
            k: (REDACTED if isinstance(k, str) and is_sensitive_key(k) else scrub(v, _depth=_depth + 1))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return type(value)(scrub(v, _depth=_depth + 1) for v in value)
    return value
