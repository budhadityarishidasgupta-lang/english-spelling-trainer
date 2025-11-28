import pandas as pd
from spelling_app.repository.course_repo import (
    get_all_spelling_courses,
    get_spelling_course_by_id,
)
from spelling_app.repository.item_repo import (
    create_item,
    map_item_to_lesson,
)
from shared.db import fetch_all, execute
from spelling_app.utils.text_normalization import normalize_word

# ------------------------------------------------------------
# LOAD SPELLING COURSES
# ------------------------------------------------------------

def load_course_data():
    """
    Load all spelling courses and normalize DB rows → list[dict].
    """
    result = get_all_spelling_courses()

    # Bubble up DB error dicts
    if isinstance(result, dict):
        return result

    if not result:
        return []

    normalized = []
    for row in result:
        # Already a dict
        if isinstance(row, dict):
            normalized.append(row)
            continue

        # SQLAlchemy Row / RowMapping
        if hasattr(row, "_mapping"):
            normalized.append(dict(row._mapping))
            continue

        # Fallback: try generic dict(row)
        try:
            normalized.append(dict(row))
        except Exception:
            normalized.append({"value": str(row)})

    return normalized


def load_lessons_for_course(course_id: int):
    """
    Loads lessons from global 'lessons' table for a given course.
    """
    rows = fetch_all(
        """
        SELECT lesson_id, course_id, lesson_name
        FROM lessons
        WHERE course_id=:course_id
        ORDER BY lesson_id ASC;
        """,
        {"course_id": course_id},
    )

    if isinstance(rows, dict):
        return rows

    return [dict(r._mapping) for r in rows] if rows else []


def ensure_lesson_exists(lesson_id: int, course_id: int, lesson_name: str):
    """
    Ensures a lesson record exists in the global 'lessons' table.
    """
    return execute(
        """
        INSERT INTO lessons (lesson_id, course_id, lesson_name)
        VALUES (:lesson_id, :course_id, :lesson_name)
        ON CONFLICT (lesson_id) DO UPDATE SET lesson_name=excluded.lesson_name;
        """,
        {"lesson_id": lesson_id, "course_id": course_id, "lesson_name": lesson_name},
    )

# ------------------------------------------------------------
# CSV UPLOAD FOR SPELLINGS
# ------------------------------------------------------------

def process_csv_upload(df: pd.DataFrame, update_mode: str, preview_only: bool, course_id: int):

    # Validate course exists
    course = get_spelling_course_by_id(course_id)
    if course is None or (isinstance(course, dict) and "error" in course):
        return {"error": f"Invalid course id {course_id}"}

    required_cols = {"word", "lesson_id", "lesson_name"}
    if not required_cols.issubset(df.columns):
        # FIX: proper f-string with single quotes around join separator
        return {
            "error": f"CSV must contain columns: {', '.join(sorted(required_cols))}"
        }

    df = df.copy()
    df["word"] = df["word"].astype(str).str.strip()
    df = df[df["word"] != ""]
    df = df.dropna(subset=["word"])

    summary = []

    for _, row in df.iterrows():
        raw_word = row.get("word", "")
        lesson_name = str(row.get("lesson_name", "")).strip()
        lesson_id = int(row["lesson_id"])
        word = normalize_word(raw_word)

        # -------------------------
        # Create/update lesson (global table)
        # -------------------------
        ensure_lesson_exists(lesson_id, course_id, lesson_name)
        summary.append({"word": word, "lesson_id": lesson_id, "lesson_name": lesson_name, "action": f"Ensure lesson {lesson_name}"})

        # -------------------------
        # Create item + map to lesson_words
        # -------------------------
        if not preview_only:
            item_id = create_item(word)

            if isinstance(item_id, dict):
                return item_id
            if item_id is None:
                return {"error": f"Database error inserting '{word}'"}

            link = map_item_to_lesson(lesson_id, item_id)
            if isinstance(link, dict):
                return link

        summary.append({"word": word, "lesson_id": lesson_id, "lesson_name": lesson_name, "action": f"INSERT {word}"})

    return {"message": "CSV updated successfully", "details": summary}
