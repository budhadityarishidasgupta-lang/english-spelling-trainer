from typing import List
from math_app.db import get_db_connection
from datetime import datetime


def get_random_test_questions(limit: int = 50) -> List[int]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id
                FROM math_question_bank
                WHERE is_active = true
                ORDER BY RANDOM()
                LIMIT %s;
                """,
                (limit,),
            )
            rows = cur.fetchall()
    return [r[0] for r in rows]


def create_test_session(total_questions: int) -> int:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO math_sessions (started_at, total_questions, correct_count)
                VALUES (%s, %s, 0)
                RETURNING id;
                """,
                (datetime.utcnow(), total_questions),
            )
            session_id = cur.fetchone()[0]
    return session_id


def end_test_session(session_id: int, correct_count: int):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE math_sessions
                SET ended_at = %s,
                    correct_count = %s
                WHERE id = %s;
                """,
                (datetime.utcnow(), correct_count, session_id),
            )
