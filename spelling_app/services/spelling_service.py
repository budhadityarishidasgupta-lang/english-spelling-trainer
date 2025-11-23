from spelling_app.repository.course_repo import *
from spelling_app.repository.lesson_repo import *
from spelling_app.repository.item_repo import *
from spelling_app.repository.attempt_repo import *


def load_course_data():
    return get_all_courses()


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
    Process uploaded CSV for spelling words.
    Supports:
        - Overwrite existing words
        - Update existing words
        - Add new words only
        - Preview-only mode
    Automatically creates lessons based on lesson_id.
    """
    if not {"word", "lesson_id"}.issubset(df.columns):
        return {"error": "CSV must contain 'word' and 'lesson_id' columns."}

    results = []
    for _, row in df.iterrows():
        word = str(row["word"]).strip()
        lesson_id = int(row["lesson_id"])

        # Ensure lesson exists
        if not preview_only:
            ensure_lesson_exists(lesson_id)

        # Check if word already exists
        existing = get_word_by_text(word)
        exists = isinstance(existing, list) and len(existing) > 0

        if exists:
            word_id = existing[0]["word_id"]

            if update_mode == "Overwrite existing words":
                if not preview_only:
                    delete_word(word_id)
                    word_id = insert_word(word)
                action = f"Overwrote: {word}"

            elif update_mode == "Update existing words":
                if not preview_only:
                    update_word(word_id, word)
                action = f"Updated: {word}"

            elif update_mode == "Add new words only":
                action = f"Skipped (exists): {word}"

        else:
            # Word does not exist, always insert
            if not preview_only:
                word_id = insert_word(word)
            action = f"Inserted: {word}"

        # Map to lesson
        if not preview_only:
            map_word_to_lesson(word_id, lesson_id)

        results.append(action)

    return "\n".join(results)
