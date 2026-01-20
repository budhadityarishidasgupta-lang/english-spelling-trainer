"""spelling_app/repository/weak_words_virtual_lesson_repo.py

Virtual-lesson implementation for **global Weak Words**.

Why this exists
--------------
The student practice engine is lesson-based (lesson -> spelling_lesson_items -> spelling_words).
Global weak-words practice must therefore be represented as a lesson to avoid risky refactors.

Safety
------
- No schema changes.
- Uses existing tables: spelling_lessons, spelling_lesson_items, spelling_attempts.
- Hidden from admin/student lesson lists via lesson_code prefix "__SYSTEM" (filtered elsewhere).
"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import text

from shared.db import execute, fetch_all

from spelling_app.repository.spelling_lesson_repo import (
    create_spelling_lesson,
    get_lesson_by_code,
)

SYSTEM_LESSON_CODE = "__SYSTEM_WEAK_WORDS__"
SYSTEM_LESSON_NAME = "Weak Words"


def _rows_to_word_ids(rows) -> List[int]:
    if not rows:
        return []
    out: List[int] = []
    for r in rows:
        m = getattr(r, "_mapping", r)
        if hasattr(m, "get"):
            wid = m.get("word_id")
        else:
            wid = None
        if wid is None:
            try:
                wid = r[0]
            except Exception:
                wid = None
        if isinstance(wid, int):
            out.append(wid)
    return out


def pick_course_for_system_lesson(user_id: int) -> Optional[int]:
    """
    Attach the system lesson to a course.
    Prefer the user's enrolled course; fallback to any spelling course (safety).
    """
    rows = fetch_all(
        text(
            """
            SELECT e.course_id
            FROM spelling_enrollments e
            WHERE e.user_id = :uid
            ORDER BY e.course_id
            LIMIT 1
            """
        ),
        {"uid": user_id},
    )
    if rows:
        m = getattr(rows[0], "_mapping", rows[0])
        return m.get("course_id")

    rows2 = fetch_all(
        text(
            """
            SELECT course_id
            FROM spelling_courses
            ORDER BY course_id
            LIMIT 1
            """
        ),
        {},
    )
    if not rows2:
        return None
    m2 = getattr(rows2[0], "_mapping", rows2[0])
    return m2.get("course_id")


def ensure_system_weak_words_lesson(course_id: int) -> Optional[int]:
    """Return the system weak-words lesson_id, creating it if needed."""
    existing = get_lesson_by_code(course_id=course_id, lesson_code=SYSTEM_LESSON_CODE)
    if existing and existing.get("lesson_id"):
        return int(existing["lesson_id"])

    created = create_spelling_lesson(
        course_id=course_id,
        lesson_name=SYSTEM_LESSON_NAME,
        lesson_code=SYSTEM_LESSON_CODE,
        sort_order=9999,
    )
    if not created or not created.get("lesson_id"):
        return None
    return int(created["lesson_id"])


def get_recent_wrong_word_ids(user_id: int, limit: int = 50) -> List[int]:
    """Distinct word_ids the user recently got wrong (global, across lessons)."""
    rows = fetch_all(
        text(
            """
            SELECT a.word_id
            FROM spelling_attempts a
            WHERE a.user_id = :uid
              AND a.correct = FALSE
            GROUP BY a.word_id
            ORDER BY MAX(a.attempt_id) DESC
            LIMIT :limit
            """
        ),
        {"uid": user_id, "limit": limit},
    )
    return _rows_to_word_ids(rows)


def sync_system_weak_words_lesson_items(lesson_id: int, word_ids: List[int]) -> None:
    """Replace lesson items for the system weak-words lesson with the given word_ids."""
    execute(
        text(
            """
            DELETE FROM spelling_lesson_items
            WHERE lesson_id = :lesson_id
            """
        ),
        {"lesson_id": lesson_id},
    )

    if not word_ids:
        return

    for wid in word_ids:
        execute(
            text(
                """
                INSERT INTO spelling_lesson_items (lesson_id, word_id)
                VALUES (:lesson_id, :word_id)
                ON CONFLICT DO NOTHING
                """
            ),
            {"lesson_id": lesson_id, "word_id": int(wid)},
        )


def prepare_system_weak_words_lesson_for_user(user_id: int, limit: int = 50) -> Optional[dict]:
    """
    Ensure + sync the system weak-words lesson for the user.

    Returns:
        {"course_id": int, "lesson_id": int, "word_count": int}
    """
    course_id = pick_course_for_system_lesson(user_id)
    if course_id is None:
        return None

    lesson_id = ensure_system_weak_words_lesson(course_id)
    if lesson_id is None:
        return None

    word_ids = get_recent_wrong_word_ids(user_id=user_id, limit=limit)
    sync_system_weak_words_lesson_items(lesson_id=lesson_id, word_ids=word_ids)

    return {"course_id": int(course_id), "lesson_id": int(lesson_id), "word_count": len(word_ids)}
