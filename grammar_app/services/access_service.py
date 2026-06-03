from __future__ import annotations

import os


def _env_flag_true(name: str, default: str = "false") -> bool:
    value = os.getenv(name, default).strip().lower()
    return value == "true"


def _uat_emails() -> set[str]:
    raw_value = os.getenv("GRAMMARSPRINT_UAT_EMAILS", "")
    return {
        email.strip().lower()
        for email in raw_value.split(",")
        if email.strip()
    }


def has_grammar_access(user_email: str) -> bool:
    """
    Safe production UAT gate for GrammarSprint.

    TODO: replace this with Kiarolabs membership-service entitlement checks using product_code GSM / app_code grammar.
    """
    if not user_email:
        return False
    if not _env_flag_true("ENABLE_GRAMMARSPRINT", default="false"):
        return False
    return user_email.strip().lower() in _uat_emails()
