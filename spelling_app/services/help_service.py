"""
DB-backed help content for Spelling UI.
Falls back to DEFAULT_SECTIONS when DB has no entry for a key.
"""

from shared.db import fetch_all, execute
from textwrap import dedent


DEFAULT_SECTIONS = {
    "spelling_intro": dedent("""
        Turn 11+ preparation into an engaging learning journey!
        Our Spelling Trainer helps learners practise tricky words,
        build confidence, and track progress over time.
    """).strip(),

    "spelling_instructions": dedent("""
        **How to start:**
        1. Sign in using your registered email/password.
        2. Access your assigned spelling courses.
        3. Practise daily for 10 minutes.
        4. Review mistakes and try again.
    """).strip(),

    "spelling_registration": dedent("""
        **New students:**
        - Complete the PayPal payment.
        - Submit the registration form.
        - You will receive your login credentials via email.
    """).strip(),

    "spelling_paypal": dedent("""
        **Payment:**
        - Fee: £14.99 (one-time access)
        - PayPal: barktuitions@gmail.com
        - Add your child's name in the payment note.
    """).strip(),
}


def get_help_text(section_key: str) -> str:
    """
    Fetch help text from DB; fallback to defaults.
    """
    result = fetch_all(
        """
        SELECT content FROM spelling_help_content
        WHERE section_key = :k
        """,
        {"k": section_key},
    )

    if isinstance(result, dict):
        # DB error, return static default
        return DEFAULT_SECTIONS.get(section_key, "")

    if result and hasattr(result[0], "_mapping"):
        return result[0]._mapping["content"]

    # No result found, return static default
    return DEFAULT_SECTIONS.get(section_key, "")


def save_help_text(section_key: str, content: str):
    """
    Upsert help text into DB.
    """
    return execute(
        """
        INSERT INTO spelling_help_content (section_key, content)
        VALUES (:k, :c)
        ON CONFLICT (section_key)
        DO UPDATE SET content = EXCLUDED.content, updated_at = NOW()
        """,
        {"k": section_key, "c": content},
    )
