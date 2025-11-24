from spelling_app.repository.course_repo import *
from spelling_app.repository.lesson_repo import *
from spelling_app.repository.item_repo import *
from spelling_app.repository.attempt_repo import *
from shared.db import fetch_all


def load_course_data():
    result = get_all_spelling_courses()
    if isinstance(result, dict):
        return result
    return [dict(r._mapping) for r in result] if result else []


def load_lessons(course_id):
    return get_lessons(course_id)


def load_items(lesson_id):
    return get_items_for_lesson(lesson_id)


def record_attempt(user_id, course_id, lesson_id, item_id, typed_answer, correct, response_ms=0):
    return log_attempt(user_id, course_id, lesson_id, item_id, typed_answer, correct, response_ms)

import pandas as pd
from spelling_app.repository.words_repo import (
    get_word_by_text,
    insert_word,
    update_word,
    delete_word,
    ensure_lesson_exists,
    map_word_to_lesson,
)


def process_csv_upload(df: pd.DataFrame, update_mode: str, preview_only: bool):
    """
    Enhanced CSV processing with:
      - column validation
      - duplicate detection
      - invalid lesson_id reporting
      - dry-run change summary
    """
    required_cols = {"word", "lesson_id"}
    if not required_cols.issubset(df.columns):
        return {"error": f"CSV must contain columns: {required_cols}"}

    # Clean up dataframe
    df = df.copy()
    df["word"] = df["word"].astype(str).str.strip()
    df = df[df["word"] != ""]
    df = df.dropna(subset=["word"])

    # Validate lesson_id column
    invalid_lesson_rows = df[~df["lesson_id"].astype(str).str.isnumeric()]
    if len(invalid_lesson_rows) > 0:
        return {
            "error": "Some rows contain invalid lesson_id values.",
            "rows": invalid_lesson_rows.to_dict(orient="records")
        }

    df["lesson_id"] = df["lesson_id"].astype(int)
    if any(df["lesson_id"] <= 0):
        return {
            "error": "lesson_id must be positive integers.",
            "rows": df[df["lesson_id"] <= 0].to_dict(orient="records")
        }

    # Detect duplicates inside CSV
    duplicate_words = df["word"].duplicated(keep=False)
    if duplicate_words.any():
        dups = df[duplicate_words]
        return {
            "error": "Duplicate words found inside CSV.",
            "duplicates": dups.to_dict(orient="records")
        }

    # Dry-run result list
    summary = []

    # Main loop
    for _, row in df.iterrows():
        word = row["word"]
        lesson_id = row["lesson_id"]

        # Ensure lesson exists (only if not preview)
        if not preview_only:
            ensure_lesson_exists(lesson_id)

        # Check if word exists in DB
        existing = get_word_by_text(word)
        exists = isinstance(existing, list) and len(existing) > 0

        action = None
        word_id = None

        if exists:
            word_id = existing[0]["word_id"]

            if update_mode == "Overwrite existing words":
                action = f"OVERWRITE: {word}"
                if not preview_only:
                    delete_word(word_id)
                    word_id = insert_word(word)

            elif update_mode == "Update existing words":
                action = f"UPDATE: {word}"
                if not preview_only:
                    update_word(word_id, word)

            elif update_mode == "Add new words only":
                action = f"SKIP (exists): {word}"

        else:
            # Word does not exist → always insert
            action = f"INSERT: {word}"
            if not preview_only:
                word_id = insert_word(word)

        # Map to lesson (if applicable)
        if action.startswith("INSERT") or action.startswith("OVERWRITE") or action.startswith("UPDATE"):
            if not preview_only:
                map_word_to_lesson(word_id, lesson_id)

        summary.append(action)

    return {
        "message": "CSV processed successfully (dry-run)" if preview_only else "CSV updated successfully",
        "preview_only": preview_only,
        "details": summary
    }


def load_lessons_for_course(course_id: int):
    """
    Returns all lessons belonging to a given spelling course.
    """
    sql = """
        SELECT lesson_id, title, instructions
        FROM lessons
        WHERE course_id = :course_id
        ORDER BY lesson_id ASC;
    """
    result = fetch_all(sql, {"course_id": course_id})
    if isinstance(result, dict):
        return result
    return [dict(r._mapping) for r in result]


def get_lesson_progress(student_id: int, lesson_id: int):
    """
    Calculates percentage progress for a given student and lesson.
    Future logic: count attempts vs total words.
    Current logic: always return 0.
    Patch B3 will populate.
    """
    return 0
