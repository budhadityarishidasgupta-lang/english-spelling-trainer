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
def list_courses(engine, include_archived: bool = True) -> pd.DataFrame:
    sql = """
        SELECT
            course_id,
            course_name,
            is_active,
            created_at
        FROM spelling_courses
        ORDER BY created_at DESC
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
            sort_order,
            is_active
        FROM spelling_lessons
        WHERE course_id = :course_id
        ORDER BY sort_order, lesson_id
    """
    return pd.read_sql(text(sql), engine, params={"course_id": course_id})


# -----------------------------
# Students
# -----------------------------
def list_students(engine) -> pd.DataFrame:
    sql = """
        SELECT
            user_id,
            name,
            email,
            is_active,
            class_name,
            created_at
        FROM spelling_users
        WHERE role = 'student'
        ORDER BY created_at DESC
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
        FROM spelling_users u
        LEFT JOIN spelling_attempts a ON a.user_id = u.user_id
        WHERE u.role = 'student'
        GROUP BY u.user_id, u.name, u.email
        ORDER BY attempts DESC
    """
    return pd.read_sql(text(sql), engine)
