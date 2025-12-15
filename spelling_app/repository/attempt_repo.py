from typing import List, Dict, Any
from shared.db import fetch_all, execute

def record_attempt(user_id: int, word_id: int, correct: bool,
                   time_taken: int, blanks_count: int, wrong_letters_count: int):
    execute("""
        INSERT INTO spelling_attempts
        (user_id, word_id, correct, time_taken, blanks_count, wrong_letters_count)
        VALUES (:uid, :wid, :c, :t, :b, :w)
    """, {
        "uid": user_id,
        "wid": word_id,
        "c": correct,
        "t": time_taken,
        "b": blanks_count,
        "w": wrong_letters_count,
    })


def get_last_attempts(user_id: int, word_id: int, limit: int = 3):
    rows = fetch_all("""
        SELECT correct
        FROM spelling_attempts
        WHERE user_id = :uid
          AND word_id = :wid
        ORDER BY created_at DESC
        LIMIT :lim
    """, {
        "uid": user_id,
        "wid": word_id,
        "lim": limit,
    })
    return [r._mapping["correct"] for r in rows] if rows else []


def get_word_difficulty_signals(user_id: int, course_id: int, lesson_id: int):
    """
    Fetch per-word difficulty signals for a user within a lesson.
    Returns rows containing:
      - word_id
      - accuracy (0-1)
      - avg_time
      - avg_wrong_letters
      - recent_failures (count in last 5 attempts)
      - recent_correct (ratio in last 3 attempts)
      - recent_wrong_last3
      - total_attempts
    """
    return fetch_all(
        """
        WITH ranked AS (
            SELECT word_id,
                   correct,
                   time_taken,
                   wrong_letters_count,
                   ROW_NUMBER() OVER(PARTITION BY word_id ORDER BY created_at DESC) AS rn
            FROM spelling_attempts
            WHERE user_id = :uid
              AND course_id = :cid
              AND lesson_id = :lid
        )
        SELECT word_id,
               AVG(CASE WHEN correct THEN 1 ELSE 0 END) AS accuracy,
               AVG(time_taken) AS avg_time,
               AVG(wrong_letters_count) AS avg_wrong_letters,
               SUM(CASE WHEN rn <= 5 AND correct = false THEN 1 ELSE 0 END) AS recent_failures,
               AVG(CASE WHEN rn <= 3 THEN CASE WHEN correct THEN 1 ELSE 0 END END) AS recent_correct,
               SUM(CASE WHEN rn <= 3 AND correct = false THEN 1 ELSE 0 END) AS recent_wrong_last3,
               COUNT(*) AS total_attempts
        FROM ranked
        GROUP BY word_id;
        """,
        {"uid": user_id, "cid": course_id, "lid": lesson_id},
    )


def get_weak_words(user_id: int, threshold: float = 0.7):
    rows = fetch_all("""
        SELECT word_id,
               AVG(CASE WHEN correct THEN 1 ELSE 0 END) AS accuracy
        FROM spelling_attempts
        WHERE user_id = :uid
        GROUP BY word_id
        HAVING AVG(CASE WHEN correct THEN 1 ELSE 0 END) < :th
    """, {
        "uid": user_id,
        "th": threshold,
    })

    return [r._mapping for r in rows] if rows else []


def get_daily5(user_id: int):
    rows = fetch_all("""
        SELECT word_id
        FROM spelling_attempts
        WHERE user_id = :uid
        ORDER BY created_at DESC
        LIMIT 5
    """, {"uid": user_id})

    return [r._mapping["word_id"] for r in rows] if rows else []


def get_attempt_stats(user_id: int, course_id: int, lesson_id: int):
    return fetch_all(
        """
        SELECT word_id,
               SUM(CASE WHEN correct=false THEN 1 ELSE 0 END) AS wrongs,
               COUNT(*) AS total
        FROM spelling_attempts
        WHERE user_id = :uid
          AND course_id = :cid
          AND lesson_id = :lid
        GROUP BY word_id;
        """,
        {"uid": user_id, "cid": course_id, "lid": lesson_id},
    )


def get_lesson_mastery(user_id: int, course_id: int, lesson_id: int):
    """
    Returns mastery % for a lesson:
      correct / total * 100
    """
    rows = fetch_all(
        """
        SELECT 
            SUM(CASE WHEN correct THEN 1 ELSE 0 END) AS correct_count,
            COUNT(*) AS total_count
        FROM spelling_attempts
        WHERE user_id = :uid AND course_id = :cid AND lesson_id = :lid
        """,
        {"uid": user_id, "cid": course_id, "lid": lesson_id},
    )

    if not rows or isinstance(rows, dict):
        return 0

    m = getattr(rows[0], "_mapping", rows[0])
    correct = m.get("correct_count") or 0
    total = m.get("total_count") or 0

    if total == 0:
        return 0

    return round((correct / total) * 100, 1)
