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

from spellings_admin_clean.word_manager_clean import process_uploaded_csv


REQUIRED_COLUMNS = [
    "word",
    "pattern",
    "pattern_code",
    "level",
    "lesson_name",
    "example_sentence",
]


def _normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [
        str(c).strip().replace("\ufeff", "").lower()
        for c in df.columns
    ]
    return df


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

    # 2. Delegate to the real importer
    result = process_uploaded_csv(
        io.BytesIO(raw_bytes),
        course_id
    )

    if not isinstance(result, dict):
        return {
            "status": "error",
            "error": "CSV processor returned invalid result",
        }

    result.setdefault("status", "success")
    result.setdefault("words_added", 0)
    result.setdefault("lessons_created", 0)
    result.setdefault("patterns", [])

    return result
