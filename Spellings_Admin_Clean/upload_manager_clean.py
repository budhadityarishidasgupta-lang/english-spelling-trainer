from typing import Dict, List, Any, Optional

import pandas as pd

from shared.db import fetch_all
from spelling_app.repository.spelling_lesson_repo import (
    get_lesson_by_name,
    create_spelling_lesson,
)
from spelling_app.repository.words_repo import (
    insert_word,
    get_word_by_text,
)


def _get_next_sort_order(course_id: int) -> int:
    """
    Compute the next sort_order for lessons in a course.
    """
    rows = fetch_all(
        """
        SELECT COALESCE(MAX(sort_order), 0) AS max_sort
        FROM spelling_lessons
        WHERE course_id = :course_id;
        """,
        {"course_id": course_id},
    )

    if isinstance(rows, dict):
        return 1

    if not rows:
        return 1

    row = rows[0]
    max_sort = None
    if hasattr(row, "_mapping"):
        max_sort = row._mapping.get("max_sort")
    elif isinstance(row, dict):
        max_sort = row.get("max_sort")
    else:
        try:
            max_sort = row[0]
        except Exception:
            max_sort = 0

    return int(max_sort or 0) + 1


def _get_or_create_lesson(course_id: int, lesson_name: str):
    """
    Return lesson dict (existing or newly created).
    """
    lesson = get_lesson_by_name(course_id, lesson_name)
    if isinstance(lesson, dict) and lesson.get("error"):
        # error response from repo
        return lesson

    if lesson:
        return lesson

    # create new lesson with next sort order
    sort_order = _get_next_sort_order(course_id)
    return create_spelling_lesson(
        course_id=course_id,
        lesson_name=lesson_name,
        sort_order=sort_order,
    )


def _map_word_to_lesson(lesson_id: int, word_id: int, pattern_code: Optional[str]):
    """
    Insert mapping into spelling_lesson_words.
    ON CONFLICT update pattern_code.
    """
    sql = """
        INSERT INTO spelling_lesson_words (lesson_id, word_id, pattern_code)
        VALUES (:lesson_id, :word_id, :pattern_code)
        ON CONFLICT (lesson_id, word_id)
        DO UPDATE SET pattern_code = EXCLUDED.pattern_code;
    """
    return fetch_all(
        sql,
        {
            "lesson_id": lesson_id,
            "word_id": word_id,
            "pattern_code": pattern_code,
        },
    )


def process_spelling_csv(
    df: pd.DataFrame,
    course_id: int,
) -> Dict[str, Any]:
    """
    Core CSV ingestion logic for spelling admin.

    Expected columns:
        - word
        - pattern_code
        - lesson_name

    Workflow per row:
        1. Normalize + validate fields
        2. Get or create lesson
        3. Get or create word in spelling_words (with course_id)
        4. Map word to lesson in spelling_lesson_words
    """
    required_cols = {"word", "pattern_code", "lesson_name"}
    missing = required_cols - set(c.lower() for c in df.columns)
    if missing:
        return {
            "error": f"Missing required columns: {', '.join(sorted(missing))}",
            "processed": 0,
            "created_words": 0,
            "reused_words": 0,
            "created_lessons": 0,
            "rows_with_error": [],
        }

    # Normalize column names to lowercase
    df = df.rename(columns={c: c.lower() for c in df.columns})

    total_rows = 0
    created_words = 0
    reused_words = 0
    created_lessons = 0
    rows_with_error: List[Dict[str, Any]] = []

    lesson_cache: Dict[str, Dict] = {}

    for idx, row in df.iterrows():
        total_rows += 1

        raw_word = str(row.get("word", "")).strip()
        pattern_code = str(row.get("pattern_code", "")).strip() or None
        lesson_name = str(row.get("lesson_name", "")).strip() or "Lesson 1"

        if not raw_word:
            rows_with_error.append(
                {"row_index": int(idx), "reason": "Empty word"}
            )
            continue

        # 1. Get or create lesson
        if lesson_name in lesson_cache:
            lesson = lesson_cache[lesson_name]
        else:
            lesson = _get_or_create_lesson(course_id, lesson_name)
            if isinstance(lesson, dict) and lesson.get("error"):
                rows_with_error.append(
                    {"row_index": int(idx), "reason": f"Lesson error: {lesson.get('error')}"}
                )
                continue
            lesson_cache[lesson_name] = lesson
            created_lessons += 1

        lesson_id = lesson.get("lesson_id")

        # 2. Get or create word
        existing = get_word_by_text(raw_word)
        if isinstance(existing, dict) and existing.get("error"):
            rows_with_error.append(
                {"row_index": int(idx), "reason": "DB error fetching word"}
            )
            continue

        word_id = None
        if existing:
            # Reuse first matching word
            item = existing[0]
            if hasattr(item, "_mapping"):
                word_id = item._mapping.get("word_id")
            elif isinstance(item, dict):
                word_id = item.get("word_id")
            else:
                try:
                    word_id = item[0]
                except Exception:
                    word_id = None
            reused_words += 1
        else:
            # Create new word
            new_id = insert_word(
                word=raw_word,
                difficulty=None,
                pattern_code=pattern_code,
                course_id=course_id,
            )
            if isinstance(new_id, dict) and new_id.get("error"):
                rows_with_error.append(
                    {
                        "row_index": int(idx),
                        "reason": f"Error creating word: {new_id.get('error')}",
                    }
                )
                continue
            word_id = new_id
            created_words += 1

        if not word_id or not lesson_id:
            rows_with_error.append(
                {
                    "row_index": int(idx),
                    "reason": "Missing word_id or lesson_id after creation",
                }
            )
            continue

        # 3. Map word to lesson
        map_result = _map_word_to_lesson(
            lesson_id=lesson_id,
            word_id=word_id,
            pattern_code=pattern_code,
        )
        if isinstance(map_result, dict) and map_result.get("error"):
            rows_with_error.append(
                {
                    "row_index": int(idx),
                    "reason": f"Error mapping word to lesson: {map_result.get('error')}",
                }
            )
            continue

    return {
        "processed": total_rows,
        "created_words": created_words,
        "reused_words": reused_words,
        "created_lessons": created_lessons,
        "rows_with_error": rows_with_error,
    }
