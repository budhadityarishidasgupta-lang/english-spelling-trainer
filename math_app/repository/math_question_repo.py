"""
Math Question Repository

All database access for math_questions lives here.
UI files must NEVER contain SQL.
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
):
    """
    Insert a maths question into the database.
    Intended for admin CSV ingestion.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
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
            asset_ref
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (question_id) DO NOTHING
    """

    cursor.execute(
        query,
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
        )
    )

    conn.commit()
    cursor.close()
    conn.close()


def get_all_questions():
    """
    Fetch all maths questions.
    """
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
            asset_ref
        FROM math_questions
        ORDER BY id
        """
    )

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows
