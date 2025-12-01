import pandas as pd
from spelling_app.repository.course_repo import get_all_spelling_courses
from shared.db import execute

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


# ------------------------------------------------------------
# CSV UPLOAD FOR SPELLINGS
# ------------------------------------------------------------

def process_csv_upload(df: pd.DataFrame, update_mode: str, preview_only: bool, course_id: int):

    required_cols = {"word", "pattern", "pattern_code"}
    if not required_cols.issubset(df.columns):
        return {"error": f"CSV must contain columns: {', '.join(sorted(required_cols))}"}

    df = df.copy()
    df["word"] = df["word"].astype(str).str.strip()
    df = df[df["word"] != ""]
    df = df.dropna(subset=["word"])

    summary = []

    for _, row in df.iterrows():
        word = str(row["word"]).strip()
        pattern = str(row["pattern"]).strip()
        pattern_code = int(row["pattern_code"])

        if preview_only:
            summary.append({"word": word, "pattern": pattern, "pattern_code": pattern_code})
            continue

        execute(
            """
            INSERT INTO spelling_words (course_id, word, pattern, pattern_code)
            VALUES (:cid, :w, :p, :pc)
            ON CONFLICT DO NOTHING;
            """,
            {"cid": course_id, "w": word, "p": pattern, "pc": pattern_code},
        )

        summary.append({"word": word, "pattern": pattern, "pattern_code": pattern_code})

    return {"message": "CSV uploaded", "details": summary}
