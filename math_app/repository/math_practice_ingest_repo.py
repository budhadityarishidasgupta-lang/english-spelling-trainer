import re
from typing import BinaryIO, Dict, List, Optional

import pandas as pd

from math_app.db import get_db_connection

# ------------------------------------------------------------
# CSV CONTRACT
# ------------------------------------------------------------

REQUIRED_COLUMNS = [
    "question_id",
    "topic",
    "difficulty",
    "stem",
    "option_a",
    "option_b",
    "option_c",
    "option_d",
    "correct_option",
]

OPTIONAL_COLUMNS = ["explanation", "hint"]


# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------

def _norm_topic_to_lesson_name(topic: str) -> str:
    """
    Normalize CSV topic -> lesson_name (canonical identity).
    Example:
      "Fractions - Add" -> "fractions_add"
    """
    s = (topic or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "untitled"


def _read_csv(file_obj: BinaryIO) -> pd.DataFrame:
    file_obj.seek(0)
    df = pd.read_csv(file_obj, dtype=str).fillna("")
    df.columns = [c.strip() for c in df.columns]
    return df


def _validate(df: pd.DataFrame) -> List[str]:
    return [c for c in REQUIRED_COLUMNS if c not in df.columns]


# ------------------------------------------------------------
# MAIN INGESTION
# ------------------------------------------------------------

def ingest_practice_csv(
    file_obj: BinaryIO,
    *,
    course_id: int = 1,
    created_by: str = "admin_ui",
) -> Dict[str, int]:
    """
    Idempotent ingestion for Maths PRACTICE papers.

    - Creates / upserts lessons from CSV topic
    - Upserts questions by question_id
    - Maps lesson <-> questions
    """

    df = _read_csv(file_obj)
    missing = _validate(df)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    for col in OPTIONAL_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df["question_id"] = df["question_id"].str.strip()
    df["topic"] = df["topic"].str.strip()
    df["difficulty"] = df["difficulty"].str.strip()
    df["stem"] = df["stem"].str.strip()
    df["correct_option"] = df["correct_option"].str.strip().str.upper()

    lessons_seen = set()
    questions_upserted = 0
    mappings_created = 0

    with get_db_connection() as conn:
        with conn.cursor() as cur:

            # ------------------------------------------------------------
            # UPSERT LESSON (FIXED: lesson_code INCLUDED)
            # ------------------------------------------------------------
            def upsert_lesson(topic: str) -> int:
                lesson_name = _norm_topic_to_lesson_name(topic)
                lesson_code = lesson_name        # REQUIRED (NOT NULL)
                display_name = topic.strip()

                lessons_seen.add((course_id, lesson_name))

                cur.execute(
                    """
                    INSERT INTO math_lessons (
                        course_id,
                        lesson_code,
                        lesson_name,
                        display_name,
                        is_active
                    )
                    VALUES (%s, %s, %s, %s, TRUE)
                    ON CONFLICT (course_id, lesson_name)
                    DO UPDATE SET
                        display_name = EXCLUDED.display_name
                    RETURNING id;
                    """,
                    (course_id, lesson_code, lesson_name, display_name),
                )

                return cur.fetchone()[0]

            # ------------------------------------------------------------
            # UPSERT QUESTION
            # ------------------------------------------------------------
            def upsert_question(row: Dict[str, str]) -> int:
                nonlocal questions_upserted

                correct = row["correct_option"]
                if correct not in {"A", "B", "C", "D", "E"}:
                    raise ValueError(
                        f"Invalid correct_option '{correct}' for question_id={row['question_id']}"
                    )

                cur.execute(
                    """
                    INSERT INTO math_questions (
                        question_id,
                        stem,
                        option_a,
                        option_b,
                        option_c,
                        option_d,
                        option_e,
                        correct_option,
                        topic,
                        difficulty,
                        explanation,
                        hint
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (question_id)
                    DO UPDATE SET
                        stem = EXCLUDED.stem,
                        option_a = EXCLUDED.option_a,
                        option_b = EXCLUDED.option_b,
                        option_c = EXCLUDED.option_c,
                        option_d = EXCLUDED.option_d,
                        option_e = EXCLUDED.option_e,
                        correct_option = EXCLUDED.correct_option,
                        topic = EXCLUDED.topic,
                        difficulty = EXCLUDED.difficulty,
                        explanation = EXCLUDED.explanation,
                        hint = EXCLUDED.hint
                    RETURNING id;
                    """,
                    (
                        row["question_id"],
                        row["stem"],
                        row["option_a"],
                        row["option_b"],
                        row["option_c"],
                        row["option_d"],
                        row.get("option_e", ""),
                        correct,
                        row["topic"],
                        row["difficulty"],
                        row["explanation"],
                        row["hint"],
                    ),
                )

                questions_upserted += 1
                return cur.fetchone()[0]

            # ------------------------------------------------------------
            # ENSURE LESSON–QUESTION MAPPING
            # ------------------------------------------------------------
            def ensure_mapping(lesson_id: int, question_id: int, position: int) -> None:
                nonlocal mappings_created
                cur.execute(
                    """
                    INSERT INTO math_lesson_questions (lesson_id, question_id, position)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (lesson_id, question_id)
                    DO UPDATE SET position = EXCLUDED.position;
                    """,
                    (lesson_id, question_id, position),
                )
                mappings_created += 1

            # ------------------------------------------------------------
            # MAIN LOOP
            # ------------------------------------------------------------
            for idx, r in df.iterrows():
                row = {c: str(r.get(c, "")) for c in df.columns}

                if not row["question_id"]:
                    continue

                lesson_id = upsert_lesson(row["topic"])
                question_id = upsert_question(row)
                ensure_mapping(lesson_id, question_id, idx + 1)

        conn.commit()

    return {
        "lessons_processed": len(lessons_seen),
        "questions_upserted": questions_upserted,
        "mappings_processed": mappings_created,
    }
