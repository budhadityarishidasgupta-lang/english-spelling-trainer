from shared.db import fetch_all, execute
from typing import List, Dict, Any
from datetime import datetime, timedelta

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

def get_lessons_for_course(course_id: int, user_id: int) -> List[Dict[str, Any]]:
    """
    Retrieves all lessons assigned to a student for a specific course.
    """
    sql = """
    SELECT
        l.lesson_id,
        l.lesson_name,
        l.sort_order
    FROM spelling_lessons l
    JOIN lesson_assignments la ON l.lesson_id = la.lesson_id
    WHERE l.course_id = :course_id AND la.user_id = :user_id
    ORDER BY l.sort_order;
    """
    rows = fetch_all(sql, {"course_id": course_id, "user_id": user_id})
    return _to_list(rows)

def get_words_for_lesson(lesson_id: int) -> List[Dict[str, Any]]:
    """
    Retrieves all words (items) for a given lesson.
    """
    sql = """
    SELECT
        i.item_id,
        i.word
    FROM items i
    JOIN item_lesson_map ilm ON i.item_id = ilm.item_id
    WHERE ilm.lesson_id = :lesson_id
    ORDER BY i.word;
    """
    rows = fetch_all(sql, {"lesson_id": lesson_id})
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

# --- Progress and Stats Functions (New for Redesign) ---

def get_user_stats_detailed(user_id: int) -> Dict[str, Any]:
    """
    Retrieves detailed statistics for the dashboard.
    """
    # 1. Total Attempts, Correct Attempts, Accuracy
    stats_sql = """
    SELECT
        COUNT(attempt_id) AS total_attempts,
        SUM(CASE WHEN is_correct = TRUE THEN 1 ELSE 0 END) AS correct_attempts,
        CAST(SUM(CASE WHEN is_correct = TRUE THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(attempt_id) AS accuracy
    FROM attempts
    WHERE user_id = :user_id;
    """
    stats = _to_dict(fetch_all(stats_sql, {"user_id": user_id})[0])
    
    # 2. Mastered Words (words correctly spelled 3 times in a row)
    mastery_sql = """
    SELECT COUNT(DISTINCT item_id) AS mastered_words
    FROM (
        SELECT
            item_id,
            is_correct,
            LAG(is_correct, 1, FALSE) OVER (PARTITION BY user_id, item_id ORDER BY created_at) AS prev_correct_1,
            LAG(is_correct, 2, FALSE) OVER (PARTITION BY user_id, item_id ORDER BY created_at) AS prev_correct_2
        FROM attempts
        WHERE user_id = :user_id
    ) AS t
    WHERE is_correct = TRUE AND prev_correct_1 = TRUE AND prev_correct_2 = TRUE;
    """
    mastery = _to_dict(fetch_all(mastery_sql, {"user_id": user_id})[0])
    
    # 3. Lessons Completed (placeholder for now, based on mastery of all words in lesson)
    lessons_completed_sql = """
    SELECT COUNT(DISTINCT l.lesson_id) AS lessons_completed
    FROM spelling_lessons l
    WHERE NOT EXISTS (
        SELECT ilm.item_id
        FROM item_lesson_map ilm
        WHERE ilm.lesson_id = l.lesson_id
        EXCEPT
        SELECT t.item_id
        FROM (
            SELECT
                item_id,
                is_correct,
                LAG(is_correct, 1, FALSE) OVER (PARTITION BY user_id, item_id ORDER BY created_at) AS prev_correct_1,
                LAG(is_correct, 2, FALSE) OVER (PARTITION BY user_id, item_id ORDER BY created_at) AS prev_correct_2
            FROM attempts
            WHERE user_id = :user_id
        ) AS t
        WHERE t.is_correct = TRUE AND t.prev_correct_1 = TRUE AND t.prev_correct_2 = TRUE
    );
    """
    lessons_completed = _to_dict(fetch_all(lessons_completed_sql, {"user_id": user_id})[0])
    
    # 4. Attempts by Day (for streak calculation)
    attempts_by_day_sql = """
    SELECT
        strftime('%Y-%m-%d', created_at) AS attempt_date,
        COUNT(attempt_id) AS count
    FROM attempts
    WHERE user_id = :user_id
    GROUP BY 1
    ORDER BY 1 DESC
    LIMIT 7;
    """
    attempts_by_day_rows = _to_list(fetch_all(attempts_by_day_sql, {"user_id": user_id}))
    attempts_by_day = {row["attempt_date"]: row["count"] for row in attempts_by_day_rows}
    
    # Combine results
    result = {
        **stats,
        **mastery,
        **lessons_completed,
        "attempts_by_day": attempts_by_day,
    }
    
    # Clean up None values
    for key, value in result.items():
        if value is None:
            result[key] = 0
            
    return result

def get_lesson_progress_detailed(user_id: int, lesson_id: int) -> Dict[str, Any]:
    """
    Retrieves detailed progress for a single lesson.
    """
    sql = """
    WITH LessonWords AS (
        SELECT item_id FROM item_lesson_map WHERE lesson_id = :lesson_id
    ),
    MasteredWords AS (
        SELECT COUNT(DISTINCT t.item_id) AS mastered_words
        FROM (
            SELECT
                item_id,
                is_correct,
                LAG(is_correct, 1, FALSE) OVER (PARTITION BY user_id, item_id ORDER BY created_at) AS prev_correct_1,
                LAG(is_correct, 2, FALSE) OVER (PARTITION BY user_id, item_id ORDER BY created_at) AS prev_correct_2
            FROM attempts
            WHERE user_id = :user_id AND item_id IN (SELECT item_id FROM LessonWords)
        ) AS t
        WHERE t.is_correct = TRUE AND t.prev_correct_1 = TRUE AND t.prev_correct_2 = TRUE
    )
    SELECT
        (SELECT COUNT(item_id) FROM LessonWords) AS total_words,
        (SELECT mastered_words FROM MasteredWords) AS mastered_words;
    """
    row = fetch_all(sql, {"user_id": user_id, "lesson_id": lesson_id})
    result = _to_dict(row[0]) if row else {"total_words": 0, "mastered_words": 0}
    
    total = result.get("total_words", 0)
    mastered = result.get("mastered_words", 0)
    
    result["progress"] = (mastered / total) * 100 if total > 0 else 0
    
    return result

def get_course_progress_detailed(user_id: int, course_id: int) -> Dict[str, Any]:
    """
    Retrieves detailed progress for a single course.
    """
    sql = """
    WITH CourseLessons AS (
        SELECT lesson_id FROM spelling_lessons WHERE course_id = :course_id
    ),
    CourseWords AS (
        SELECT ilm.item_id
        FROM item_lesson_map ilm
        WHERE ilm.lesson_id IN (SELECT lesson_id FROM CourseLessons)
    ),
    MasteredWords AS (
        SELECT COUNT(DISTINCT t.item_id) AS mastered_words
        FROM (
            SELECT
                item_id,
                is_correct,
                LAG(is_correct, 1, FALSE) OVER (PARTITION BY user_id, item_id ORDER BY created_at) AS prev_correct_1,
                LAG(is_correct, 2, FALSE) OVER (PARTITION BY user_id, item_id ORDER BY created_at) AS prev_correct_2
            FROM attempts
            WHERE user_id = :user_id AND item_id IN (SELECT item_id FROM CourseWords)
        ) AS t
        WHERE t.is_correct = TRUE AND t.prev_correct_1 = TRUE AND t.prev_correct_2 = TRUE
    )
    SELECT
        (SELECT COUNT(item_id) FROM CourseWords) AS total_words,
        (SELECT mastered_words FROM MasteredWords) AS mastered_words;
    """
    row = fetch_all(sql, {"user_id": user_id, "course_id": course_id})
    result = _to_dict(row[0]) if row else {"total_words": 0, "mastered_words": 0}
    
    total = result.get("total_words", 0)
    mastered = result.get("mastered_words", 0)
    
    result["progress"] = (mastered / total) * 100 if total > 0 else 0
    
    return result
