"""
Read-only repository for Admin Console vNext.
Patch 1: SELECT-only functions.
NO side effects.
"""

import pandas as pd
from sqlalchemy import text


# -----------------------------
# Courses
# -----------------------------
def list_courses(engine) -> pd.DataFrame:
    sql = """
        SELECT
            course_id,
            course_name
        FROM spelling_courses
        ORDER BY course_id DESC
    """
    return pd.read_sql(text(sql), engine)


# -----------------------------
# Lessons
# -----------------------------
def list_lessons(engine, course_id: int) -> pd.DataFrame:
    sql = """
        SELECT
            lesson_id,
            lesson_name,
            display_name,
            sort_order
        FROM spelling_lessons
        WHERE course_id = :course_id
          AND lesson_name NOT ILIKE '__SYSTEM%'
        ORDER BY sort_order, lesson_id
    """
    return pd.read_sql(text(sql), engine, params={"course_id": course_id})


# -----------------------------
# Students
# -----------------------------
def list_students(engine) -> pd.DataFrame:
    sql = """
        SELECT
            u.user_id,
            u.name,
            u.email,
            u.class_name
        FROM users u
        WHERE u.role = 'student'
        ORDER BY u.user_id DESC
    """
    return pd.read_sql(text(sql), engine)


# -----------------------------
# Progress (read-only snapshot)
# -----------------------------
def list_student_progress(engine) -> pd.DataFrame:
    sql = """
        SELECT
            u.user_id,
            u.name,
            u.email,
            COUNT(a.attempt_id) AS attempts
        FROM users u
        LEFT JOIN spelling_attempts a
            ON a.user_id = u.user_id
        WHERE u.role = 'student'
        GROUP BY u.user_id, u.name, u.email
        ORDER BY attempts DESC
    """
    return pd.read_sql(text(sql), engine)
