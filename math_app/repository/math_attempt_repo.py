"""
Math Attempt Repository

All database writes for maths attempts live here.
Attempts are append-only.
"""

from shared.db import get_connection


def record_attempt(
    session_id: int,
    question_id: int,
    selected_option: str,
    is_correct: bool
):
    """
    Record a single maths question attempt.
    """

    conn = get_connection()
    cursor = conn.cursor()

    query = """
        INSERT INTO math_attempts (
            session_id,
            question_id,
            selected_option,
            is_correct
        )
        VALUES (%s, %s, %s, %s)
    """

    cursor.execute(
        query,
        (session_id, question_id, selected_option, is_correct)
    )

    conn.commit()
    cursor.close()
    conn.close()

    
    conn = get_connection()
    cursor = conn.cursor()

    # SQL will be added once math_attempts table exists
    raise NotImplementedError(
        "math_attempts table not created yet – repository wired but inactive"
    )
