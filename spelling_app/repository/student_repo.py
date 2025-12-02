from shared.db import fetch_all, execute
from typing import List, Dict, Any

# --- Helper Functions ---

def _to_dict(row):
    """Convert SQLAlchemy row or mapping to dict safely."""
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    if hasattr(row, "_mapping"):
        return dict(row._mapping)
    try:
        return dict(row)
    except Exception:
        return None

def _to_list(rows):
    """Normalize fetch_all results into a list of dicts."""
    if rows is None:
        return []
    if isinstance(rows, list):
        return [_to_dict(r) for r in rows if _to_dict(r) is not None]
    if hasattr(rows, "all"):  # CursorResult
        try:
            return [_to_dict(r) for r in rows.all() if _to_dict(r) is not None]
        except Exception:
            return []
    return []

def get_user_stats_detailed(user_id: int):
    """
    Returns aggregated statistics for a student, used in the dashboard:
      - total_attempts
      - correct_attempts
      - accuracy (0–100)
      - mastered_words (correct 3 times)
    """

    # Total attempts
    total_rows = fetch_all(
        "SELECT COUNT(*) AS total_attempts FROM attempts WHERE user_id = :uid",
        {"uid": user_id},
    )
    total_attempts = 0
    if total_rows:
        row = total_rows[0]
        if hasattr(row, "_mapping"):
            total_attempts = row._mapping.get("total_attempts", 0)
        elif isinstance(row, (list, tuple)):
            total_attempts = row[0]
        elif isinstance(row, dict):
            total_attempts = row.get("total_attempts", 0)

    # Correct attempts
    correct_rows = fetch_all(
        "SELECT COUNT(*) AS correct_attempts FROM attempts WHERE user_id = :uid AND is_correct = TRUE",
        {"uid": user_id},
    )
    correct_attempts = 0
    if correct_rows:
        row = correct_rows[0]
        if hasattr(row, "_mapping"):
            correct_attempts = row._mapping.get("correct_attempts", 0)
        elif isinstance(row, (list, tuple)):
            correct_attempts = row[0]
        elif isinstance(row, dict):
            correct_attempts = row.get("correct_attempts", 0)

    # Accuracy (avoid divide-by-zero)
    accuracy = 0.0
    if total_attempts > 0:
        accuracy = (correct_attempts / total_attempts) * 100.0

    # Mastered words = correct 3+ times
    mastered_rows = fetch_all(
        """
        SELECT item_id
        FROM attempts
        WHERE user_id = :uid AND is_correct = TRUE
        GROUP BY item_id
        HAVING COUNT(*) >= 3
        """,
        {"uid": user_id},
    )
    mastered_words = len(mastered_rows) if isinstance(mastered_rows, list) else 0

    return {
        "total_attempts": total_attempts,
        "correct_attempts": correct_attempts,
        "accuracy": accuracy,
        "mastered_words": mastered_words,
    }

def get_lessons_for_course(course_id: int):
    """
    Returns distinct lessons (pattern groups) for a spelling course:
      lesson_id    = pattern_code
      lesson_name  = pattern
    """
    sql = """
    SELECT DISTINCT
        pattern_code AS lesson_id,
        pattern      AS lesson_name
    FROM spelling_words
    WHERE course_id = :cid
    ORDER BY pattern_code;
    """
    rows = fetch_all(sql, {"cid": course_id})
    return _to_list(rows)

def get_words_for_lesson(course_id: int, pattern_code: int):
    """
    Returns all words belonging to a specific lesson (pattern_code)
    inside the given course.
    """
    sql = """
    SELECT
        word_id,
        word,
        pattern_code,
        pattern
    FROM spelling_words
    WHERE course_id = :cid
      AND pattern_code = :pcode
    ORDER BY word_id;
    """
    rows = fetch_all(sql, {"cid": course_id, "pcode": pattern_code})
    return _to_list(rows)

# --- Student-Facing Repository Functions ---

def get_student_courses(user_id: int) -> List[Dict[str, Any]]:
    """
    Retrieves all courses a student is enrolled in.
    """
    sql = """
    SELECT
        c.course_id,
        c.title,
        c.description
    FROM courses c
    JOIN enrollments e ON c.course_id = e.course_id
    WHERE e.user_id = :user_id AND c.course_type = 'spelling'
    ORDER BY c.title;
    """
    rows = fetch_all(sql, {"user_id": user_id})
    return _to_list(rows)

def record_attempt(user_id: int, item_id: int, is_correct: bool, attempt_text: str) -> None:
    """
    Records a spelling attempt.
    """
    sql = """
    INSERT INTO attempts (user_id, item_id, is_correct, attempt_text)
    VALUES (:user_id, :item_id, :is_correct, :attempt_text);
    """
    execute(sql, {
        "user_id": user_id,
        "item_id": item_id,
        "is_correct": is_correct,
        "attempt_text": attempt_text
    })

def get_user_info(user_id: int) -> Dict[str, Any]:
    """
    Retrieves basic user information.
    """
    sql = "SELECT user_id, name, email FROM users WHERE user_id = :user_id;"
    row = fetch_all(sql, {"user_id": user_id})
    return _to_dict(row[0]) if row else {}
