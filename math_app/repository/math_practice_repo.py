from typing import List, Dict, Optional
from math_app.db import get_db_connection


# ------------------------------------------------------------
# LESSONS (STUDENT VIEW)
# ------------------------------------------------------------

def get_lessons_for_student(course_id: int) -> List[Dict]:
    """
    Return lessons available for a course for student practice.

    Uses display_name if present, otherwise lesson_name.
    """
    sql = """
        SELECT
            id AS lesson_id,
            lesson_name,
            display_name
        FROM math_lessons
        WHERE course_id = %s
        ORDER BY lesson_name
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (course_id,))
            rows = cur.fetchall()

    return [
        {
            "lesson_id": row[0],
            "lesson_name": row[1],
            "display_name": row[2] or row[1],
        }
        for row in rows
    ]


# ------------------------------------------------------------
# QUESTIONS FOR A LESSON
# ------------------------------------------------------------

def get_questions_for_lesson(lesson_id: int) -> List[Dict]:
    """
    Returns ordered questions for a lesson.

    Order is defined by lesson_question mapping order.
    """
    sql = """
        SELECT
            q.id AS question_id,
            q.stem,
            q.option_a,
            q.option_b,
            q.option_c,
            q.option_d,
            q.correct_option,
            q.explanation
        FROM math_lesson_questions mlq
        JOIN math_questions q
            ON q.id = mlq.question_id
        WHERE mlq.lesson_id = %s
        ORDER BY mlq.position ASC
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (lesson_id,))
            rows = cur.fetchall()

    return [
        {
            "question_id": row[0],
            "stem": row[1],
            "option_a": row[2],
            "option_b": row[3],
            "option_c": row[4],
            "option_d": row[5],
            "correct_option": row[6],
            "explanation": row[7],
        }
        for row in rows
    ]


# ------------------------------------------------------------
# RESUME LOGIC
# ------------------------------------------------------------

def get_resume_index(student_id: int, lesson_id: int) -> int:
    """
    Returns the index (0-based) of the first unanswered question
    for a student in a lesson.

    If all questions have been attempted, returns total count.
    """
    sql = """
        SELECT
            COUNT(DISTINCT a.question_id)
        FROM math_attempts a
        WHERE a.student_id = %s
          AND a.lesson_id = %s
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (student_id, lesson_id))
            attempted_count = cur.fetchone()[0]

    # Resume index = number of attempted questions
    return attempted_count or 0


# ------------------------------------------------------------
# ATTEMPTS (APPEND-ONLY)
# ------------------------------------------------------------

def record_attempt(
    student_id: int,
    lesson_id: int,
    question_id: int,
    selected_option: str,
    is_correct: bool,
) -> None:
    """
    Record a student attempt.
    Append-only. Never updates or deletes history.
    """
    sql = """
        INSERT INTO math_attempts (
            student_id,
            lesson_id,
            question_id,
            selected_option,
            is_correct,
            attempted_at
        )
        VALUES (%s, %s, %s, %s, %s, NOW())
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    student_id,
                    lesson_id,
                    question_id,
                    selected_option,
                    is_correct,
                ),
            )
        conn.commit()
