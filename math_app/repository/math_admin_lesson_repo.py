"""
MathSprint Admin — Lesson Management Repository
Read-only queries + safe display_name rename + CSV export.
No destructive operations. No schema changes.
"""
import io
import re
from typing import Dict, List, Optional

import pandas as pd

from math_app.db import get_db_connection

# ---------------------------------------------------------------------------
# LESSON QUERIES
# ---------------------------------------------------------------------------

def get_math_lessons_by_difficulty(difficulty: Optional[str]) -> List[Dict]:
    """
    Returns lessons filtered by difficulty column.
    difficulty='basic'  -> Maths Basic tab
    difficulty='advanced' -> Maths Advanced tab
    difficulty=None -> all lessons (fallback)
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if difficulty is None:
                cur.execute(
                    """
                    SELECT
                        l.id,
                        l.lesson_code,
                        l.lesson_name,
                        l.display_name,
                        l.difficulty,
                        l.is_active,
                        COUNT(mlq.question_id) AS question_count,
                        l.course_id
                    FROM math_lessons l
                    LEFT JOIN math_lesson_questions mlq ON mlq.lesson_id = l.id
                    GROUP BY l.id, l.lesson_code, l.lesson_name, l.display_name, l.difficulty, l.is_active, l.course_id
                    ORDER BY l.lesson_name
                    """
                )
            else:
                cur.execute(
                    """
                    SELECT
                        l.id,
                        l.lesson_code,
                        l.lesson_name,
                        l.display_name,
                        l.difficulty,
                        l.is_active,
                        COUNT(mlq.question_id) AS question_count,
                        l.course_id
                    FROM math_lessons l
                    LEFT JOIN math_lesson_questions mlq ON mlq.lesson_id = l.id
                    WHERE LOWER(COALESCE(l.difficulty, 'basic')) = LOWER(%s)
                    GROUP BY l.id, l.lesson_code, l.lesson_name, l.display_name, l.difficulty, l.is_active, l.course_id
                    ORDER BY l.lesson_name
                    """,
                    (difficulty,),
                )
            rows = cur.fetchall()
    finally:
        conn.close()

    return [
        {
            "lesson_id": r[0],
            "lesson_code": r[1],
            "lesson_name": r[2],
            "display_name": r[3] or r[2],
            "difficulty": r[4] or "basic",
            "is_active": r[5],
            "question_count": r[6],
            "course_id": r[7],
        }
        for r in rows
    ]


def get_lesson_questions_df(lesson_id: int) -> pd.DataFrame:
    """
    Returns all questions for a lesson as a DataFrame (for CSV export).
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    q.question_id,
                    q.topic,
                    q.difficulty,
                    q.stem,
                    q.option_a,
                    q.option_b,
                    q.option_c,
                    q.option_d,
                    q.option_e,
                    q.correct_option,
                    q.explanation,
                    q.hint
                FROM math_questions q
                JOIN math_lesson_questions mlq ON mlq.question_id = q.id
                WHERE mlq.lesson_id = %s
                ORDER BY mlq.position, q.id
                """,
                (lesson_id,),
            )
            rows = cur.fetchall()
            cols = [
                "question_id", "topic", "difficulty", "stem",
                "option_a", "option_b", "option_c", "option_d", "option_e",
                "correct_option", "explanation", "hint",
            ]
    finally:
        conn.close()

    return pd.DataFrame(rows, columns=cols)


def rename_lesson_display_name(lesson_id: int, new_display_name: str) -> None:
    """
    Updates display_name only. Never changes lesson_name or lesson_code.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE math_lessons SET display_name = %s WHERE id = %s",
                (new_display_name.strip(), lesson_id),
            )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CSV TEMPLATE
# ---------------------------------------------------------------------------

TEMPLATE_COLUMNS = [
    "question_id", "topic", "difficulty", "stem",
    "option_a", "option_b", "option_c", "option_d",
    "correct_option", "option_e", "explanation", "hint",
]

TEMPLATE_EXAMPLE = {
    "basic": {
        "question_id": "MB-FRAC-001",
        "topic": "Fractions",
        "difficulty": "Core",
        "stem": "What is 1/2 + 1/4?",
        "option_a": "1/4",
        "option_b": "3/4",
        "option_c": "1",
        "option_d": "2/4",
        "correct_option": "B",
        "option_e": "",
        "explanation": "1/2 = 2/4, so 2/4 + 1/4 = 3/4.",
        "hint": "Convert to same denominator first.",
    },
    "advanced": {
        "question_id": "MA-PCT-001",
        "topic": "Percentages",
        "difficulty": "Core",
        "stem": "What is 25% of 80?",
        "option_a": "10",
        "option_b": "20",
        "option_c": "25",
        "option_d": "40",
        "correct_option": "B",
        "option_e": "",
        "explanation": "25% means one quarter. One quarter of 80 is 20.",
        "hint": "25% = 1/4.",
    },
}


def build_blank_template_csv(difficulty: str = "basic") -> bytes:
    example = TEMPLATE_EXAMPLE.get(difficulty.lower(), TEMPLATE_EXAMPLE["basic"])
    df = pd.DataFrame([example], columns=TEMPLATE_COLUMNS)
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


def build_lesson_csv(lesson_id: int) -> bytes:
    df = get_lesson_questions_df(lesson_id)
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()
