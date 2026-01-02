"""
Math Question Repository
"""

from math_app.db import get_db_connection


def insert_question(
    question_id: str,
    stem: str,
    option_a: str,
    option_b: str,
    option_c: str,
    option_d: str,
    option_e: str,
    correct_option: str,
    topic: str,
    difficulty: str,
    asset_type: str,
    asset_ref: str | None,
    solution: str,
):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO math_questions (
            question_id,
            stem,
            option_a,
            option_b,
            option_c,
            option_d,
            option_e,
            correct_option,
            topic,
            difficulty,
            asset_type,
            asset_ref,
            solution
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (question_id) DO NOTHING
        """,
        (
            question_id,
            stem,
            option_a,
            option_b,
            option_c,
            option_d,
            option_e,
            correct_option,
            topic,
            difficulty,
            asset_type,
            asset_ref,
            solution,
        ),
    )

    conn.commit()
    cursor.close()
    conn.close()


def get_all_questions():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            question_id,
            stem,
            option_a,
            option_b,
            option_c,
            option_d,
            option_e,
            correct_option,
            topic,
            difficulty,
            asset_type,
            asset_ref,
            solution
        FROM math_questions
        ORDER BY id
        """
    )

    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows
