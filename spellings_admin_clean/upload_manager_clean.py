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
    _get_next_sort_order,
    create_spelling_lesson,
    get_lesson_by_code,
    get_lesson_by_name,
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
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace("\ufeff", "", regex=False)
    )
    return df


def _safe_int(value):
    try:
        if value is None:
            return None
        s = str(value).strip()
        if s.lower() in ("", "nan", "none"):
            return None
        # Handle "L1", "L2" style values
        if len(s) > 1 and s[0].lower() == "l" and s[1:].isdigit():
            return int(s[1:])
        return int(s)
    except (TypeError, ValueError):
        return None


def _get_or_create_lesson(course_id: int, lesson_name: str, lesson_code: str | None = None):
    assert course_id is not None, "course_id is required for lesson lookup"
    lesson_key = lesson_name
    row = {"lesson_code": lesson_code}

    lesson_code_raw = row.get("lesson_code")
    lesson_code = str(lesson_code_raw).strip() if lesson_code_raw else None

    if lesson_code:
        lesson = get_lesson_by_code(course_id=course_id, lesson_code=lesson_code)
    else:
        lesson = get_lesson_by_name(course_id=course_id, lesson_name=lesson_key)

    if lesson:
        return lesson, False

    sort_order = _get_next_sort_order(course_id)
    created_lesson = create_spelling_lesson(
        course_id=course_id,
        lesson_name=lesson_key,
        lesson_code=lesson_code,
        sort_order=sort_order,
    )

    if created_lesson:
        return created_lesson, True

    return {"lesson_id": None, "course_id": course_id, "lesson_name": lesson_key}, True


def _read_csv_with_encoding_fallback(uploaded_file, **read_kwargs) -> pd.DataFrame:
    try:
        df = pd.read_csv(uploaded_file, encoding="utf-8", **read_kwargs)
    except UnicodeDecodeError:
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file, encoding="latin-1", **read_kwargs)

    return _normalize_headers(df)


def validate_csv_columns(uploaded_file) -> tuple[bool, str | None]:
    try:
        df_head = _read_csv_with_encoding_fallback(uploaded_file, nrows=0)
    except Exception as exc:
        return False, f"Could not read CSV: {exc}"

    cols = list(df_head.columns)

    missing = [c for c in REQUIRED_COLUMNS if c not in cols]
    if missing:
        return False, f"CSV missing required columns: {', '.join(missing)}"

    return True, None


def process_spelling_csv(uploaded_file, course_id: int) -> dict:
    from spellings_admin_clean.word_manager_clean import process_uploaded_csv

    assert course_id is not None, "course_id must be provided by Admin UI"
    print(f"[INGESTION] Using course_id={course_id}")

    # Always work from a fresh in-memory buffer to avoid EOF / stream reuse bugs
    raw_bytes = uploaded_file.getvalue() if hasattr(uploaded_file, "getvalue") else uploaded_file.read()

    # Validate using fresh buffer
    ok, err = validate_csv_columns(io.BytesIO(raw_bytes))
    if not ok:
        return {"status": "error", "error": err, "words_added": 0, "lessons_created": 0, "patterns": []}

    # Process using fresh buffer (critical fix)
    result = process_uploaded_csv(io.BytesIO(raw_bytes), course_id)

    # If underlying returned an error, propagate it (don't mask as success)
    if isinstance(result, dict) and result.get("error"):
        return {"status": "error", "error": result["error"], "words_added": 0, "lessons_created": 0, "patterns": []}

    # Enforce UI return contract
    return {
        "status": result.get("status", "success"),
        "words_added": result.get("words_added", 0),
        "lessons_created": result.get("lessons_created", 0),
        "patterns": result.get("patterns", []),
    }
