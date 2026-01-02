"""
Math Session Repository

Handles creation and completion of maths practice sessions.
"""

from shared.db import get_connection


def create_session(total_questions: int) -> int:
    """
    Create a new maths session and return its ID.
    """
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        INSERT INTO math_sessions (total_questions)
        VALUES (%s)
        RETURNING id
    """

    cursor.execute(query, (total_questions,))
    session_id = cursor.fetchone()[0]

    conn.commit()
    cursor.close()
    conn.close()

    return session_id


def end_session(session_id: int, correct_count: int):
    """
    Mark a maths session as completed.
    """
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        UPDATE math_sessions
        SET ended_at = CURRENT_TIMESTAMP,
            correct_count = %s
        WHERE id = %s
    """

    cursor.execute(query, (correct_count, session_id))

    conn.commit()
    cursor.close()
    conn.close()
