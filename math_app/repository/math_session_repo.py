"""
Math Session Repository
"""

from math_app.db import get_db_connection


def create_session(total_questions: int) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO math_sessions (total_questions)
        VALUES (%s)
        RETURNING id
        """,
        (total_questions,),
    )

    session_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    conn.close()

    return session_id


def end_session(session_id: int, correct_count: int):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE math_sessions
        SET ended_at = CURRENT_TIMESTAMP,
            correct_count = %s
        WHERE id = %s
        """,
        (correct_count, session_id),
    )

    conn.commit()
    cursor.close()
    conn.close()
