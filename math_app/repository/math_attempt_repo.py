"""
Math Attempt Repository
"""

from math_app.db import get_db_connection


def record_attempt(
    session_id: int,
    question_id: int,
    selected_option: str,
    is_correct: bool,
):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO math_attempts (
            session_id,
            question_id,
            selected_option,
            is_correct
        )
        VALUES (%s, %s, %s, %s)
        """,
        (session_id, question_id, selected_option, is_correct),
    )

    conn.commit()
    cursor.close()
    conn.close()
