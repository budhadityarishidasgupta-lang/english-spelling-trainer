from __future__ import annotations

import json
from typing import BinaryIO, Dict, List

import pandas as pd

from math_app.db import get_db_connection

REQUIRED_COLUMNS = [
    "question_code",
    "question_text",
    "option_a",
    "option_b",
    "option_c",
    "option_d",
    "correct_option",
    "topic",
    "difficulty",
    "is_active",
]

VALID_CORRECT = {"option_a", "option_b", "option_c", "option_d"}


def _read_csv(file_obj: BinaryIO) -> pd.DataFrame:
    file_obj.seek(0)
    try:
        df = pd.read_csv(file_obj, dtype=str).fillna("")
    except UnicodeDecodeError:
        file_obj.seek(0)
        df = pd.read_csv(file_obj, dtype=str, encoding="latin-1").fillna("")
    df.columns = [c.strip() for c in df.columns]
    return df


def _validate(df: pd.DataFrame) -> List[str]:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    return missing


def ingest_question_bank_csv(file_obj: BinaryIO) -> Dict[str, int]:
    """
    Append-only ingestion into math_question_bank.
    - New question_code => version 1
    - Existing question_code => version max+1 (new row)
    - Never updates/deletes existing rows
    """
    df = _read_csv(file_obj)
    missing = _validate(df)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    # Normalize
    df["question_code"] = df["question_code"].astype(str).str.strip()
    df["question_text"] = df["question_text"].astype(str).str.strip()

    for c in ["option_a", "option_b", "option_c", "option_d"]:
        df[c] = df[c].astype(str).str.strip()

    df["correct_option"] = df["correct_option"].astype(str).str.strip().str.lower()
    df["topic"] = df["topic"].astype(str).str.strip()
    df["difficulty"] = df["difficulty"].astype(str).str.strip()
    df["is_active"] = df["is_active"].astype(str).str.strip().str.lower()

    # Validate row-level
    bad_rows: List[str] = []
    for i, row in df.iterrows():
        rc = row["question_code"]
        if not rc:
            bad_rows.append(f"Row {i+2}: question_code is empty")
            continue
        if row["correct_option"] not in VALID_CORRECT:
            bad_rows.append(
                f"Row {i+2} ({rc}): correct_option must be one of {sorted(VALID_CORRECT)}"
            )
        if row["is_active"] not in {"true", "false"}:
            bad_rows.append(f"Row {i+2} ({rc}): is_active must be true/false")

        # Required text checks (keep minimal)
        if not row["question_text"]:
            bad_rows.append(f"Row {i+2} ({rc}): question_text is empty")
        for opt in ["option_a", "option_b", "option_c", "option_d"]:
            if not row[opt]:
                bad_rows.append(f"Row {i+2} ({rc}): {opt} is empty")

    if bad_rows:
        raise ValueError("CSV validation failed:\n" + "\n".join(bad_rows[:50]))

    inserted = 0
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for _, row in df.iterrows():
                question_code = row["question_code"]

                # Compute next version (append-only)
                cur.execute(
                    "SELECT COALESCE(MAX(version), 0) + 1 FROM math_question_bank WHERE question_code = %s;",
                    (question_code,),
                )
                next_version = int(cur.fetchone()[0])

                options_json = {
                    "a": row["option_a"],
                    "b": row["option_b"],
                    "c": row["option_c"],
                    "d": row["option_d"],
                }

                correct_map = {
                    "option_a": "A",
                    "option_b": "B",
                    "option_c": "C",
                    "option_d": "D",
                }
                correct_letter = correct_map[row["correct_option"]]

                is_active = row["is_active"] == "true"

                cur.execute(
                    """
                    INSERT INTO math_question_bank (
                        question_code,
                        question_text,
                        options_json,
                        correct_option,
                        topic,
                        difficulty,
                        is_active,
                        version
                    )
                    VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s, %s);
                    """,
                    (
                        question_code,
                        row["question_text"],
                        json.dumps(options_json),
                        correct_letter,
                        row["topic"] or None,
                        row["difficulty"] or None,
                        is_active,
                        next_version,
                    ),
                )
                inserted += 1

    return {"rows_inserted": inserted}


def export_latest_question_bank_df() -> pd.DataFrame:
    """
    Returns latest version per question_code as a DataFrame suitable for CSV download.
    """
    sql = """
    SELECT DISTINCT ON (question_code)
        question_code,
        question_text,
        options_json,
        correct_option,
        topic,
        difficulty,
        is_active
    FROM math_question_bank
    ORDER BY question_code, version DESC;
    """
    with get_db_connection() as conn:
        df = pd.read_sql(sql, conn)

    # Expand JSON options
    def _opt(dfrow, k):
        try:
            return (dfrow.get("options_json") or {}).get(k, "")
        except Exception:
            return ""

    df["option_a"] = df.apply(lambda r: _opt(r, "a"), axis=1)
    df["option_b"] = df.apply(lambda r: _opt(r, "b"), axis=1)
    df["option_c"] = df.apply(lambda r: _opt(r, "c"), axis=1)
    df["option_d"] = df.apply(lambda r: _opt(r, "d"), axis=1)

    # Map correct letter back to option_* label
    inv = {"A": "option_a", "B": "option_b", "C": "option_c", "D": "option_d"}
    df["correct_option"] = df["correct_option"].map(inv).fillna("")

    # Final column order
    out = df[
        [
            "question_code",
            "question_text",
            "option_a",
            "option_b",
            "option_c",
            "option_d",
            "correct_option",
            "topic",
            "difficulty",
            "is_active",
        ]
    ].copy()

    # Ensure boolean-style strings
    out["is_active"] = out["is_active"].apply(lambda x: "true" if bool(x) else "false")
    return out
