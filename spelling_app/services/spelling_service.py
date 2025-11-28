# -----------------------------
# CLEAN, WORKING IMPORT BLOCK
# -----------------------------

import pandas as pd
import streamlit as st
import random
import math
import re

from shared.db import fetch_all

# Spelling-specific repos
from spelling_app.repository.course_repo import (
    get_all_spelling_courses,
    get_spelling_course_by_id,
)

from spelling_app.repository.item_repo import (
    create_item,
    get_item_by_word,
    map_item_to_lesson,
)

from spelling_app.repository.spelling_lesson_repo import (
    get_lesson_by_name,
    create_spelling_lesson,
    update_spelling_lesson_sort_order,
)

from spelling_app.repository.attempt_repo import *
from spelling_app.utils.text_normalization import normalize_word


def load_course_data():
    result = get_all_spelling_courses()

    # If DB returned an error dict, bubble it up
    if isinstance(result, dict):
        return result

    # If empty, return empty list
    if not result:
        return []

    processed = []
    for row in result:

        # SQLAlchemy Row → dict
        if hasattr(row, "_mapping"):
            processed.append(dict(row._mapping))
            continue

        # If already dict
        if isinstance(row, dict):
            processed.append(row)
            continue

        # If tuple-like, convert using keys from cursor
        try:
            processed.append(dict(row))
            continue
        except Exception:
            # Final fallback: convert everything to string dict
            processed.append({"value": str(row)})

    return processed


def get_course_by_id(course_id: int):
    return get_spelling_course_by_id(course_id)


def load_lessons(course_id):
    return get_lessons(course_id)


def load_items(lesson_id):
    return get_items_for_lesson(lesson_id)


def record_attempt(user_id, course_id, lesson_id, item_id, typed_answer, correct, response_ms=0):
    return log_attempt(user_id, course_id, lesson_id, item_id, typed_answer, correct, response_ms)


def process_csv_upload(
    df: pd.DataFrame,
    update_mode: str,
    preview_only: bool,
    course_id: int,
):
    """
    Process a CSV of spelling words and lesson names for a given spelling course.

    Expected CSV columns:
      - word          (required)
      - lesson_name   (required)
      - sort_order    (optional, integer; default 0)

    Behaviour:
      - For each (course_id, lesson_name), ensures a spelling lesson exists
        in spelling_lessons (create if missing, update sort_order if changed).
      - Ensures each word exists in spelling_items (create if missing).
      - Maps (lesson_id, item_id) into spelling_lesson_items (ON CONFLICT DO NOTHING).
      - If preview_only is True, does NOT write to DB, only returns a summary.
    """
    if df is None:
        return {"error": "No CSV file uploaded."}

    # Ensure required columns
    required_cols = {"word", "lesson_name"}
    if not required_cols.issubset(df.columns):
        return {
            "error": f"CSV must contain columns: {', '.join(sorted(required_cols))}"
        }

    # Work on a copy
    df = df.copy()

    # Normalise sort_order column
    if "sort_order" not in df.columns:
        df["sort_order"] = 0

    # Clean obvious junk in sort_order
    def _safe_int(x):
        try:
            return int(x)
        except Exception:
            return 0

    df["sort_order"] = df["sort_order"].apply(_safe_int)

    # Drop rows with completely empty word
    df["word"] = df["word"].astype(str)
    df = df[df["word"].str.strip() != ""]
    if df.empty:
        return {"error": "CSV has no valid non-empty words."}

    # Remove exact duplicate rows (same word + lesson_name + sort_order)
    before = len(df)
    df = df.drop_duplicates(subset=["word", "lesson_name", "sort_order"])
    removed = before - len(df)

    summary = []
    if removed > 0:
        summary.append({
            "word": "",
            "lesson_name": "",
            "sort_order": "",
            "action": f"Removed {removed} duplicate row(s) inside the CSV."
        })

    # Main loop
    for _, row in df.iterrows():
        raw_word = row.get("word", "")
        raw_lesson_name = str(row.get("lesson_name") or "").strip()
        sort_order = _safe_int(row.get("sort_order", 0))

        # Normalise the word consistently (quotes, spaces, unicode)
        word = normalize_word(raw_word)

        # --- Word-level validation (NON-FATAL) ---
        if not word:
            summary.append({
                "word": raw_word,
                "lesson_name": raw_lesson_name,
                "sort_order": sort_order,
                "action": "SKIP: Word empty after normalization",
            })
            continue

        if len(word) < 2 or len(word) > 40:
            summary.append({
                "word": raw_word,
                "lesson_name": raw_lesson_name,
                "sort_order": sort_order,
                "action": f"SKIP: Invalid length ({len(word)} chars)",
            })
            continue

        # Only letters and hyphen are allowed
        if not re.match(r"^[A-Za-z-]+$", word):
            summary.append({
                "word": raw_word,
                "lesson_name": raw_lesson_name,
                "sort_order": sort_order,
                "action": "SKIP: Contains disallowed characters",
            })
            continue

        blacklist = {"na", "n/a", "---", "???", "###"}
        if word.lower() in blacklist:
            summary.append({
                "word": raw_word,
                "lesson_name": raw_lesson_name,
                "sort_order": sort_order,
                "action": "SKIP: Blacklisted token",
            })
            continue

        # --- Lesson handling (Option A: spelling_lessons) ---
        if not raw_lesson_name:
            raw_lesson_name = "Lesson 1"

        lesson_action = ""

        # Find by (course_id, lesson_name)
        lesson = get_lesson_by_name(course_id, raw_lesson_name)

        if isinstance(lesson, dict) and lesson.get("error"):
            # DB error from repo
            return lesson

        if lesson is None:
            # Create spelling lesson
            lesson = create_spelling_lesson(course_id, raw_lesson_name, sort_order)
            if lesson is None:
                return {
                    "error": f"Database error: Failed to create or retrieve lesson '{raw_lesson_name}'."
                }
            if isinstance(lesson, dict) and lesson.get("error"):
                return lesson
            lesson_action = f"CREATE LESSON: {raw_lesson_name}"
        else:
            # Existing lesson: update sort_order if changed
            if "sort_order" in lesson and lesson["sort_order"] != sort_order:
                update_result = update_spelling_lesson_sort_order(
                    lesson["lesson_id"], sort_order
                )
                if isinstance(update_result, dict) and update_result.get("error"):
                    return update_result
                lesson_action = f"UPDATE SORT ORDER: {sort_order}"

        lesson_id = lesson["lesson_id"]

        if lesson_action:
            summary.append({
                "word": word,
                "lesson_name": raw_lesson_name,
                "sort_order": sort_order,
                "action": lesson_action,
            })

        # --- Item creation / mapping ---
        if not preview_only:
            item_id = create_item(word)

            if isinstance(item_id, dict):
                # Repo-level DB error
                return item_id

            if item_id is None:
                return {
                    "error": f"Database error inserting word '{word}'"
                }

            map_result = map_item_to_lesson(lesson_id, item_id)
            if isinstance(map_result, dict):
                return map_result

        summary.append({
            "word": word,
            "lesson_name": raw_lesson_name,
            "sort_order": sort_order,
            "action": f"INSERT ITEM: {word} → {raw_lesson_name}",
        })

    return {
        "message": "CSV preview generated" if preview_only else "CSV updated successfully",
        "preview_only": preview_only,
        "details": summary,
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


def update_course_details(course_id, title=None, description=None, difficulty=None, course_type=None):
    return update_spelling_course(course_id, title, description, difficulty, course_type)


def update_lesson_details(lesson_id, title=None, description=None, is_active=None):
    return update_spelling_lesson(lesson_id, title, description, is_active).astype(str).str.strip()
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

    # NOTE: The lesson rebalancing logic (Patch A3) is removed as it relies on lesson_id
    # and is incompatible with the new lesson_name/sort_order logic.
    
    # Dry-run result list
    summary = []

    # Main loop
    for _, row in df.iterrows():
        raw_word = row.get("word", "")
        raw_lesson_name = str(row.get("lesson_name") or "").strip() # Fix Minor 3: Handle NaN
        sort_order = int(row.get("sort_order", 0))
        word = normalize_word(raw_word)

        # ---------------------------
        # B4: Word Validation Patch
        # ---------------------------
        # 1. Check empty or whitespace
        if not word or word.strip() == "":
            summary.append({
                "word": raw_word,
                "lesson_name": raw_lesson_name,
                "sort_order": sort_order,
                "action": "SKIP: Word is empty after normalization",
            })
            continue

        # 2. Length sanity check
        if len(word) < 2 or len(word) > 40:
            return {"error": f"Invalid word '{word}' — must be 2 to 40 characters long."}

        # 3. Allowed characters: letters + hyphen
        import re
        if not re.match(r"^[A-Za-z-]+$", word):
            return {"error": f"Invalid word '{word}' — contains disallowed characters."}

        # 4. Blacklist common OCR or junk tokens
        blacklist = {"na", "n/a", "---", "???", "###"}
        if word.lower() in blacklist:
            return {"error": f"Invalid word '{word}' — blacklisted token."}

        # ---------------------------
        # B5: Lesson Creation/Update Logic
        # ---------------------------
        lesson_action = ""
        
        lesson = get_lesson_by_name(course_id, raw_lesson_name)
        
        if isinstance(lesson, dict) and lesson.get("error"): # Fix Minor 1: Improved error check
            return lesson # DB error
        
        if lesson is None:
            # Case A: Lesson does NOT exist -> Create it
            lesson = create_spelling_lesson(course_id, raw_lesson_name, sort_order)
            if lesson is None:
                return {"error": f"Database error: Failed to create or retrieve lesson '{raw_lesson_name}'."}
            if isinstance(lesson, dict) and lesson.get("error"):
                return lesson # DB error
            lesson_action = f"CREATE LESSON: {raw_lesson_name}"
            
        elif lesson["sort_order"] != sort_order:
            # Case B: Lesson exists and sort_order differs -> Update sort_order
            update_result = update_spelling_lesson_sort_order(lesson["lesson_id"], sort_order)
            if isinstance(update_result, dict) and update_result.get("error"):
                return update_result # DB error
            lesson_action = f"UPDATE SORT ORDER: {sort_order}"
            
        else:
            # Case C: Lesson exists and no update needed -> Do nothing
            pass

        lesson_id = lesson["lesson_id"]
        
        if lesson_action:
            summary.append({"word": word, "lesson_id": lesson_id, "lesson_name": raw_lesson_name, "sort_order": sort_order, "action": lesson_action})

        # ---------------------------
        # B6: Item Creation/Mapping Logic
        # ---------------------------
        action = f"INSERT ITEM: {word} → lesson {lesson_id} ({raw_lesson_name})"
        
        if not preview_only:
            # Try to create the item first
            item_id = create_item(word)

            # Case 1: Repo returned an error dict
            if isinstance(item_id, dict):
                return item_id

            # Case 2: create_item/get_item_by_word failed unexpectedly
            if item_id is None:
                return {"error": f"Database error inserting word '{word}'"}

            # Now map the item to the lesson
            map_result = map_item_to_lesson(lesson_id, item_id)
            if isinstance(map_result, dict):
                return map_result


        summary_row = {
            "word": word,
            "lesson_id": lesson_id, # For debugging/tracking
            "lesson_name": raw_lesson_name,
            "sort_order": sort_order,
            "action": action,
        }

        summary.append(summary_row)

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


def update_course_details(course_id, title=None, description=None, difficulty=None, course_type=None):
    return update_spelling_course(course_id, title, description, difficulty, course_type)


def update_lesson_details(lesson_id, title=None, description=None, is_active=None):
    return update_spelling_lesson(lesson_id, title, description, is_active)
