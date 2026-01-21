#!/usr/bin/env python3
# -------------------------------------------------
# Upload Manager (FINAL, CLEAN)
# Enhanced ingestion: Word Pool + Lesson Metadata (incremental, safe)
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
from spelling_app.repository.hint_repo import upsert_manual_hint_overrides_concat


REQUIRED_COLUMNS = [
    "word",
    "pattern_code",
    "example",
    "difficulty",
]

WORD_POOL_REQUIRED = ["word", "lesson_code", "lesson_name"]
LESSON_META_REQUIRED = ["lesson_code"]


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


def _clean_str(v) -> str:
    s = "" if v is None else str(v)
    s = s.strip()
    return "" if s.lower() in ("nan", "none", "null") else s


def _read_csv_with_encoding_fallback(uploaded_file, **read_kwargs) -> pd.DataFrame:
    try:
        df = pd.read_csv(uploaded_file, encoding="utf-8", **read_kwargs)
    except UnicodeDecodeError:
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file, encoding="latin-1", **read_kwargs)

    return _normalize_headers(df)


def _require_columns(df: pd.DataFrame, required: list[str]) -> tuple[bool, str | None]:
    missing = [c for c in required if c not in df.columns]
    if missing:
        return False, f"CSV missing required columns: {', '.join(missing)}"
    return True, None


def _extract_lesson_id(lesson_row) -> int | None:
    """
    Be defensive: repo functions may return dict-like row, SQLAlchemy Row, or tuple.
    We only need lesson_id.
    """
    if lesson_row is None:
        return None

    # dict-like (most likely in this repo)
    try:
        if isinstance(lesson_row, dict) and "lesson_id" in lesson_row:
            return int(lesson_row["lesson_id"])
    except Exception:
        pass

    # SQLAlchemy Row supports mapping access
    try:
        return int(lesson_row["lesson_id"])
    except Exception:
        pass

    # tuple/list fallback: assume lesson_id is first column
    try:
        if isinstance(lesson_row, (tuple, list)) and len(lesson_row) > 0:
            return int(lesson_row[0])
    except Exception:
        pass

    return None


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


# ============================================================
# NEW: WORD POOL UPLOAD (auto lessons via lesson_code + lesson_name)
# ============================================================

def process_word_pool_csv(uploaded_file, course_id: int, dry_run: bool = True) -> dict:
    """
    Single CSV ingestion:
    - required: word, lesson_code, lesson_name
    - optional: example, example_sentence, hint, pattern, pattern_code, level/difficulty
    Behaviour:
    - Lesson identity: (course_id + lesson_name)
    - lesson_code is required metadata for creation (schema), but NOT identity
    - create word if missing
    - map word to lesson (idempotent)
    - if hint present: append/concat into overrides
    """
    assert course_id is not None, "course_id must be provided by Admin UI"

    raw_bytes = uploaded_file.getvalue() if hasattr(uploaded_file, "getvalue") else uploaded_file.read()
    df = _read_csv_with_encoding_fallback(io.BytesIO(raw_bytes))

    ok, err = _require_columns(df, WORD_POOL_REQUIRED)
    if not ok:
        return {"status": "error", "error": err}

    lessons_created = 0
    words_created = 0
    mappings_added = 0
    hints_appended = 0
    lessons_detected: set[str] = set()

    for _, row in df.iterrows():
        word = _clean_str(row.get("word"))
        lesson_code = _clean_str(row.get("lesson_code"))
        lesson_name = _clean_str(row.get("lesson_name"))

        if not word or not lesson_code or not lesson_name:
            continue

        lessons_detected.add(lesson_name)

        # 1) Resolve lesson_id via lesson_name (stable identity)
        lesson_row = get_lesson_by_name(course_id=course_id, lesson_name=lesson_name)
        lesson_id = _extract_lesson_id(lesson_row)

        # 2) Create lesson if missing (requires lesson_code), then re-fetch
        if not lesson_id and not dry_run:
            create_spelling_lesson(
                course_id=course_id,
                lesson_name=lesson_name,
                lesson_code=lesson_code,  # required by schema
                sort_order=_get_next_sort_order(course_id),
            )
            lessons_created += 1
            lesson_row = get_lesson_by_name(course_id=course_id, lesson_name=lesson_name)
            lesson_id = _extract_lesson_id(lesson_row)

        # If still no lesson_id (dry run or failure), skip mapping/hints safely
        if not lesson_id:
            continue

        # Word payload
        pattern = _clean_str(row.get("pattern")) or None
        pattern_code = _safe_int(row.get("pattern_code"))
        level = _safe_int(row.get("level")) or _safe_int(row.get("difficulty"))
        example_sentence = _clean_str(row.get("example_sentence")) or _clean_str(row.get("example")) or None
        hint = _clean_str(row.get("hint")) or None

        # 3) Ensure word exists
        word_id, created = get_or_create_word(
            word=word,
            pattern=pattern,
            pattern_code=pattern_code,
            level=level,
            lesson_name=lesson_name,
            course_id=course_id,
            example_sentence=example_sentence,
            hint=None,  # never overwrite legacy hint field here
            return_created=True,
        )
        if not word_id:
            continue
        if created:
            words_created += 1

        # 4) Map word -> lesson
        if not dry_run:
            link_word_to_lesson(word_id=word_id, lesson_id=lesson_id)
            mappings_added += 1

        # 5) Append/concat hint into overrides
        if hint:
            if not dry_run:
                hints_appended += upsert_manual_hint_overrides_concat(
                    rows=[{"word_id": int(word_id), "course_id": int(course_id), "hint_text": hint}]
                )

    return {
        "status": "success",
        "lessons_created": lessons_created if not dry_run else 0,
        "words_created": words_created if not dry_run else 0,
        "mappings_added": mappings_added if not dry_run else 0,
        "hints_appended": hints_appended if not dry_run else 0,
        "lessons_detected": sorted(lessons_detected),
    }


# ============================================================
# NEW: LESSON METADATA UPLOAD (append or overwrite)
# ============================================================

def process_lesson_metadata_csv(uploaded_file, course_id: int, overwrite: bool = False, dry_run: bool = True) -> dict:
    """
    Lesson metadata ingestion:
    - required: lesson_code
    - optional: lesson_name, display_name, sort_order, is_active
    Default mode (overwrite=False): create missing lessons only.
    Overwrite mode: update allowed fields on existing lessons.
    """
    assert course_id is not None, "course_id must be provided by Admin UI"

    raw_bytes = uploaded_file.getvalue() if hasattr(uploaded_file, "getvalue") else uploaded_file.read()
    df = _read_csv_with_encoding_fallback(io.BytesIO(raw_bytes))

    ok, err = _require_columns(df, LESSON_META_REQUIRED)
    if not ok:
        return {"status": "error", "error": err}

    lessons_created = 0
    lessons_updated = 0
    skipped = 0

    from shared.db import execute

    for _, row in df.iterrows():
        lesson_code = _clean_str(row.get("lesson_code"))
        if not lesson_code:
            skipped += 1
            continue

        lesson_name = _clean_str(row.get("lesson_name")) or _clean_str(row.get("display_name")) or lesson_code
        display_name = _clean_str(row.get("display_name")) or lesson_name
        sort_order = _safe_int(row.get("sort_order"))
        is_active_raw = _clean_str(row.get("is_active"))
        is_active = None
        if is_active_raw:
            is_active = is_active_raw.lower() in ("1", "true", "yes", "y")

        existing = get_lesson_by_code(course_id=course_id, lesson_code=lesson_code)
        if not existing:
            if not dry_run:
                so = sort_order if sort_order is not None else _get_next_sort_order(course_id)
                create_spelling_lesson(
                    course_id=course_id,
                    lesson_name=lesson_name,
                    lesson_code=lesson_code,
                    sort_order=so,
                )
                # display_name may exist; set if possible
                execute(
                    """
                    UPDATE spelling_lessons
                    SET display_name = :display_name
                    WHERE course_id = :course_id AND LOWER(lesson_code) = LOWER(:lesson_code)
                    """,
                    {"display_name": display_name, "course_id": course_id, "lesson_code": lesson_code},
                )
            lessons_created += 1
            continue

        if not overwrite:
            skipped += 1
            continue

        if dry_run:
            lessons_updated += 1
            continue

        execute(
            """
            UPDATE spelling_lessons
               SET display_name = COALESCE(:display_name, display_name),
                   sort_order   = COALESCE(:sort_order, sort_order),
                   is_active    = COALESCE(:is_active, is_active)
             WHERE course_id = :course_id
               AND LOWER(lesson_code) = LOWER(:lesson_code)
            """,
            {
                "display_name": display_name if display_name else None,
                "sort_order": sort_order,
                "is_active": is_active,
                "course_id": course_id,
                "lesson_code": lesson_code,
            },
        )
        lessons_updated += 1

    return {
        "status": "success",
        "lessons_created": lessons_created if not dry_run else 0,
        "lessons_updated": lessons_updated if not dry_run else 0,
        "skipped": skipped,
    }
