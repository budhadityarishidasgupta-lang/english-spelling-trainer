#!/usr/bin/env python3
# -------------------------------------------------
# Upload Manager (FINAL, CLEAN)
# -------------------------------------------------

import sys
import io
import pandas as pd

# ---- Force project root for Render ----
PROJECT_ROOT = "/opt/render/project/src"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from spelling_app.repository.spelling_lesson_repo import (
    get_lesson_by_name_and_course,
    get_or_create_lesson as repo_get_or_create_lesson,
)
from spellings_admin_clean.word_manager_clean import (
    get_or_create_word,
    link_word_to_lesson,
)


REQUIRED_COLUMNS = [
    "word",
    "pattern_code",
    "example",
    "difficulty",
]


def _normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [
        str(c).strip().replace("\ufeff", "").lower()
        for c in df.columns
    ]
    return df


def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _get_or_create_lesson(course_id: int, lesson_name: str):
    existing = get_lesson_by_name_and_course(
        lesson_name=lesson_name,
        course_id=course_id,
    )

    if existing and isinstance(existing, dict):
        return (
            {
                "lesson_id": existing.get("lesson_id"),
                "course_id": existing.get("course_id"),
                "lesson_name": existing.get("lesson_name"),
            },
            False,
        )

    lesson_id = repo_get_or_create_lesson(
        course_id=course_id,
        lesson_name=lesson_name,
    )

    if lesson_id:
        return ({"lesson_id": lesson_id, "course_id": course_id, "lesson_name": lesson_name}, True)

    return ({"lesson_id": None, "course_id": course_id, "lesson_name": lesson_name}, False)


def validate_csv_columns(uploaded_file) -> tuple[bool, str | None]:
    try:
        df_head = pd.read_csv(uploaded_file, nrows=0)
    except Exception as exc:
        return False, f"Could not read CSV: {exc}"

    df_head = _normalize_headers(df_head)
    cols = list(df_head.columns)

    missing = [c for c in REQUIRED_COLUMNS if c not in cols]
    if missing:
        return False, f"CSV missing required columns: {', '.join(missing)}"

    return True, None


def process_spelling_csv(uploaded_file, course_id: int) -> dict:
    """
    SINGLE ENTRYPOINT for admin CSV uploads.
    """

    raw_bytes = uploaded_file.getvalue()

    # 1. Validate headers
    ok, err = validate_csv_columns(io.BytesIO(raw_bytes))
    if not ok:
        return {"status": "error", "error": err}

    # 2. Process CSV with pattern-based lessons
    try:
        df = pd.read_csv(io.BytesIO(raw_bytes))
    except Exception as exc:
        return {"status": "error", "error": f"Could not read CSV: {exc}"}

    df = _normalize_headers(df)

    words_added = 0
    lessons_created = 0
    patterns_set = set()
    lesson_cache: dict[str, dict] = {}

    for _, row in df.iterrows():
        word = str(row.get("word", "")).strip()
        if not word:
            continue

        pattern_raw = row.get("pattern")
        pattern = str(pattern_raw).strip() if pattern_raw is not None else None
        pattern = pattern or None

        pattern_code_raw = row.get("pattern_code", "")
        pattern_code_str = str(pattern_code_raw).strip()
        pattern_code_value = _safe_int(pattern_code_raw)

        lesson_key = pattern_code_str or "Uncategorized"

        if lesson_key in lesson_cache:
            lesson_info = lesson_cache[lesson_key]
            lesson_created = False
        else:
            lesson_info, lesson_created = _get_or_create_lesson(
                course_id=course_id,
                lesson_name=lesson_key,
            )
            lesson_cache[lesson_key] = lesson_info
        
        lesson_id = lesson_info.get("lesson_id")
        if lesson_created:
            lessons_created += 1

        if not lesson_id:
            print(f"[WARN] Lesson creation failed for '{lesson_key}'. Skipping row.")
            continue

        level = _safe_int(row.get("difficulty") or row.get("level"))

        example_sentence_raw = row.get("example") or row.get("example_sentence")
        example_sentence = str(example_sentence_raw).strip() if example_sentence_raw is not None else None

        word_id = get_or_create_word(
            word=word,
            pattern=pattern,
            pattern_code=pattern_code_value,
            level=level,
            lesson_name=lesson_key,
            example_sentence=example_sentence,
            course_id=course_id,
        )

        if not word_id:
            print(f"[WARN] Word creation failed for '{word}'.")
            continue

        link_word_to_lesson(word_id=word_id, lesson_id=lesson_id)

        if pattern:
            patterns_set.add(pattern)
        words_added += 1

    return {
        "status": "success",
        "words_added": words_added,
        "lessons_created": lessons_created,
        "patterns": sorted(patterns_set),
    }
