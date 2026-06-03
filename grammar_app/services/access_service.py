from __future__ import annotations


def has_grammar_access(user_email: str) -> bool:
    """
    First-build access gate for GrammarSprint.

    TODO: wire to Kiarolabs membership-service using product_code GSM / app_code grammar.
    """
    return True
