import io
import pandas as pd

from spellings_admin_clean.word_manager_clean import process_uploaded_csv


REQUIRED_COLUMNS = ["word", "pattern", "pattern_code", "level", "lesson_name"]


def _normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Trim whitespace/BOM and lowercase column headers.
    """
    df.columns = [str(c).strip().replace("\ufeff", "").lower() for c in df.columns]
    return df


def validate_csv_columns(uploaded_file) -> tuple[bool, str | None]:
    """
    Lightweight header validation for the spelling CSV.

    Returns (is_valid, error_message).
    """
    try:
        # Read only the header row for speed
        df_head = pd.read_csv(uploaded_file, nrows=0)
    except Exception as exc:
        return False, f"Could not read CSV header: {exc}"

    df_head = _normalize_headers(df_head)
    cols = list(df_head.columns)

    missing = [col for col in REQUIRED_COLUMNS if col not in cols]
    if missing:
        return False, f"CSV is missing required columns: {', '.join(missing)}"

    return True, None


def process_spelling_csv(uploaded_file, course_id: int) -> dict:
    """
    Validate headers then delegate to word_manager_clean.process_uploaded_csv.

    This is the single entrypoint used by the admin UI.
    Returns a result dict with at least:
      - words_added (int)
      - lessons_created (int)
      - patterns (list[str])
      - status (str)
      - error (optional str)
    """
    # We must be able to read the file twice (once for header, once for processing),
    # so grab the raw bytes and construct two independent buffers.
    raw_bytes = uploaded_file.getvalue()

    # 1) Header validation
    is_valid, err = validate_csv_columns(io.BytesIO(raw_bytes))
    if not is_valid:
        return {"status": "error", "error": err}

    # 2) Delegate to the main CSV processor
    result = process_uploaded_csv(io.BytesIO(raw_bytes), course_id)

    # Normalise result structure
    if not isinstance(result, dict):
        return {
            "status": "error",
            "error": "Unexpected CSV processor return type.",
        }

    result.setdefault("status", "success")
    result.setdefault("words_added", result.get("words_added", 0))
    result.setdefault("lessons_created", result.get("lessons_created", 0))
    result.setdefault("patterns", result.get("patterns", []))

    return result
