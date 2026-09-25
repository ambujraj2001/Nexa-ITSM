"""Controlled category vocabulary shared by triage, assignment rules and knowledge.

The triage model must pick from this list; anything else is normalised to
"Other" so routing rules stay deterministic.
"""

from __future__ import annotations

CATEGORIES: dict[str, tuple[str, ...]] = {
    "Network": ("VPN", "Wi-Fi", "Connectivity", "DNS", "Firewall"),
    "Access": ("Password Reset", "MFA", "Account Lockout", "Permissions", "SSO", "Production Access"),
    "Email & Collaboration": ("Email", "Calendar", "Chat", "Video Conferencing", "File Sharing"),
    "Hardware": ("Laptop", "Desktop", "Peripherals", "Mobile Device", "Printer"),
    "Software": ("Installation", "Licensing", "Application Error", "Performance", "Updates"),
    "Security": ("Phishing", "Malware", "Suspicious Activity", "Data Exposure", "Certificates"),
    "Infrastructure": ("Server", "Cloud", "Deployment", "Database", "Storage", "Monitoring"),
    "Other": ("General",),
}

_CATEGORY_LOOKUP = {c.lower(): c for c in CATEGORIES}
_SUBCATEGORY_LOOKUP = {
    (c.lower(), s.lower()): s for c, subs in CATEGORIES.items() for s in subs
}


def normalize_category(category: str | None, subcategory: str | None) -> tuple[str, str | None]:
    """Map free-form model output onto the vocabulary (case-insensitive)."""
    cat = _CATEGORY_LOOKUP.get((category or "").strip().lower(), "Other")
    sub_raw = (subcategory or "").strip()
    if not sub_raw:
        return cat, None
    sub = _SUBCATEGORY_LOOKUP.get((cat.lower(), sub_raw.lower()))
    if sub is None:
        # Keep a sensible free-text subcategory, but bounded.
        sub = sub_raw[:60]
    return cat, sub


def taxonomy_for_prompt() -> str:
    return "\n".join(f"- {c}: {', '.join(subs)}" for c, subs in CATEGORIES.items())
