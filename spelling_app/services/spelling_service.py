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
import streamlit as st
from spelling_app.repository.words_repo import ensure_lesson_exists
import math
import random


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

    # Remove duplicates inside the same lesson
    before_dedup = len(df)
    df = df.drop_duplicates(subset=["word", "lesson_id"], keep="first")
    after_dedup = len(df)

    # Count how many intra-lesson duplicates were removed
    removed = before_dedup - after_dedup
    if removed > 0:
        st.info(
            f"Auto-removed {removed} duplicate entries inside identical lessons. "
            "Cross-lesson duplicates were kept."
        )

    # -----------------------------
    # A3: Balanced Lesson Distribution
    # -----------------------------
    MAX_ITEMS_PER_LESSON = 20
    MIN_ITEMS_PER_LESSON = 10

    # Group items by lesson
    lesson_groups = (
        df.groupby("lesson_id")["word"]
          .apply(list)
          .to_dict()
    )

    # Collect all words & lessons for redistribution
    all_items = []
    for lesson_id, words in lesson_groups.items():
        for w in words:
            all_items.append((w, lesson_id))

    # Order lessons numerically
    sorted_lessons = sorted(lesson_groups.keys())

    # Pass 1: Rebalance overloaded lessons
    for lesson_id in sorted_lessons:
        words = lesson_groups[lesson_id]
        if len(words) > MAX_ITEMS_PER_LESSON:
            overflow = len(words) - MAX_ITEMS_PER_LESSON
            extra_words = words[MAX_ITEMS_PER_LESSON:]
            lesson_groups[lesson_id] = words[:MAX_ITEMS_PER_LESSON]

            # Distribute overflow to NEIGHBORING lessons
            for w in extra_words:
                # Try next+1 lesson
                for neighbor in [lesson_id + 1, lesson_id - 1]:
                    if neighbor in lesson_groups and len(lesson_groups[neighbor]) < MAX_ITEMS_PER_LESSON:
                        lesson_groups[neighbor].append(w)
                        break

    # Pass 2: Ensure each lesson has MIN_ITEMS, pull from neighbors
    for lesson_id in sorted_lessons:
        while len(lesson_groups[lesson_id]) < MIN_ITEMS_PER_LESSON:
            # Try to borrow from a neighboring overloaded lesson
            for neighbor in [lesson_id - 1, lesson_id + 1]:
                if neighbor in lesson_groups and len(lesson_groups[neighbor]) > MIN_ITEMS_PER_LESSON:
                    w = lesson_groups[neighbor].pop()
                    lesson_groups[lesson_id].append(w)
                    break
            else:
                break

    # Final: flatten back to df
    balanced_rows = []
    for lesson_id, words in lesson_groups.items():
        for w in words:
            balanced_rows.append({"word": w, "lesson_id": lesson_id})

    df = pd.DataFrame(balanced_rows)

    # Shuffle final distribution for natural randomness
    df = df.sample(frac=1).reset_index(drop=True)

    # -----------------------------
    # END of Patch A3
    # -----------------------------

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

    # Skip duplicate checks across lessons; only intra-lesson duplicates are removed above.

    # Dry-run result list
    summary = []

    # Main loop
    for _, row in df.iterrows():
        word = row["word"]
        lesson_id = row["lesson_id"]

        action = f"INSERT ITEM: {word} (lesson {lesson_id})"

        if not preview_only:
            ensure_lesson_exists(lesson_id)

            item_id = create_item(word)
            if isinstance(item_id, dict):
                return item_id
            if item_id is None:
                return {"error": f"Failed to insert item for word '{word}'"}

            map_result = map_item_to_lesson(lesson_id, item_id)
            if isinstance(map_result, dict):
                return map_result

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
