import re
from typing import BinaryIO, Dict, List, Optional

import pandas as pd

from math_app.db import get_db_connection

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


def _norm_topic_to_lesson_name(topic: str) -> str:
    """
    Normalize CSV topic -> lesson_name (canonical identity key).
    Example:
      "Fractions - Add Different Denominators" -> "fractions_add_different_denominators"
    """
    s = (topic or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "untitled"


def _read_csv(file_obj: BinaryIO) -> pd.DataFrame:
    # Streamlit file_uploader provides a BytesIO-like object
    file_obj.seek(0)
    df = pd.read_csv(file_obj, dtype=str).fillna("")
    # Normalize headers
    df.columns = [c.strip() for c in df.columns]
    return df


def _validate(df: pd.DataFrame) -> List[str]:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    return missing


def ingest_practice_csv(
    file_obj: BinaryIO,
    *,
    course_id: int = 1,
    created_by: str = "admin_ui",
) -> Dict[str, int]:
    """
    Idempotent ingestion for PRACTICE papers only.

    - Creates/Upserts lessons from topic -> lesson_name
    - Upserts questions by question_id
    - Maps lesson <-> questions via math_lesson_questions
    - Safe to re-upload: questions update, mapping does not duplicate
    """
    df = _read_csv(file_obj)
    missing = _validate(df)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    # Ensure optional columns exist
    for c in OPTIONAL_COLUMNS:
        if c not in df.columns:
            df[c] = ""

    # Basic row cleanup
    df["question_id"] = df["question_id"].astype(str).str.strip()
    df["topic"] = df["topic"].astype(str).str.strip()
    df["difficulty"] = df["difficulty"].astype(str).str.strip()
    df["stem"] = df["stem"].astype(str).str.strip()
    df["correct_option"] = df["correct_option"].astype(str).str.strip().str.upper()

    # Count metrics
    lessons_created = 0
    lessons_seen = set()
    questions_upserted = 0
    mappings_created = 0

    with get_db_connection() as conn:
        conn.autocommit = False

        try:
            with conn.cursor() as cur:
                # --- Helpers (SQL stays here, NOT in UI) ---
                def upsert_lesson(topic: str) -> int:
                    nonlocal lessons_created
                    lesson_name = _norm_topic_to_lesson_name(topic)
                    display_name = (topic or "").strip() or lesson_name

                    # Track per-run "created" roughly: if we didn't see it before, check existence
                    key = (course_id, lesson_name)
                    if key not in lessons_seen:
                        lessons_seen.add(key)

                    cur.execute(
                        """
                        INSERT INTO math_lessons (course_id, lesson_name, display_name, is_active)
                        VALUES (%s, %s, %s, TRUE)
                        ON CONFLICT (course_id, lesson_name)
                        DO UPDATE SET display_name = EXCLUDED.display_name
                        RETURNING id;
                        """,
                        (course_id, lesson_name, display_name),
                    )
                    row = cur.fetchone()
                    if not row:
                        raise RuntimeError("Failed to create/find lesson_id")
                    # We cannot perfectly detect "created vs updated" without extra query.
                    # Keep metric simple: count unique lessons encountered in CSV.
                    return int(row[0])

                def upsert_question(row_dict: Dict[str, str]) -> int:
                    nonlocal questions_upserted
                    qid = row_dict["question_id"].strip()
                    topic = row_dict["topic"].strip()
                    difficulty = row_dict.get("difficulty", "").strip()
                    stem = row_dict["stem"].strip()

                    # Options
                    oa = row_dict.get("option_a", "").strip()
                    ob = row_dict.get("option_b", "").strip()
                    oc = row_dict.get("option_c", "").strip()
                    od = row_dict.get("option_d", "").strip()
                    oe = row_dict.get("option_e", "").strip() if "option_e" in row_dict else ""

                    correct = (row_dict.get("correct_option") or "").strip().upper()
                    if correct not in ("A", "B", "C", "D", "E"):
                        raise ValueError(f"Invalid correct_option '{correct}' for question_id={qid}")

                    explanation = (row_dict.get("explanation") or "").strip()
                    hint = (row_dict.get("hint") or "").strip()

                    # NOTE: We store CSV 'explanation' into explanation column (and also mirror to solution if you want later)
                    cur.execute(
                        """
                        INSERT INTO math_questions (
                            question_id, stem,
                            option_a, option_b, option_c, option_d, option_e,
                            correct_option, topic, difficulty,
                            explanation, hint
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
                        (qid, stem, oa, ob, oc, od, oe, correct, topic, difficulty, explanation, hint),
                    )
                    qpk = cur.fetchone()
                    if not qpk:
                        raise RuntimeError(f"Failed to upsert question_id={qid}")
                    questions_upserted += 1
                    return int(qpk[0])

                def ensure_mapping(lesson_id: int, question_pk: int, position: Optional[int]) -> None:
                    nonlocal mappings_created
                    cur.execute(
                        """
                        INSERT INTO math_lesson_questions (lesson_id, question_pk, position)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (lesson_id, question_pk)
                        DO UPDATE SET position = COALESCE(EXCLUDED.position, math_lesson_questions.position);
                        """,
                        (lesson_id, question_pk, position),
                    )
                    mappings_created += 1

                # --- Main loop ---
                for idx, r in df.iterrows():
                    row = {c: str(r.get(c, "")) for c in df.columns}

                    if not row.get("question_id", "").strip():
                        # Skip blank rows
                        continue
                    if not row.get("topic", "").strip():
                        raise ValueError(f"Missing topic for question_id={row.get('question_id')}")
                    if not row.get("stem", "").strip():
                        raise ValueError(f"Missing stem for question_id={row.get('question_id')}")

                    lesson_id = upsert_lesson(row["topic"])
                    question_pk = upsert_question(row)
                    ensure_mapping(lesson_id, question_pk, position=int(idx) + 1)

                # Lessons metric: count unique topics encountered (safe/clear)
                lessons_created = len(lessons_seen)

            conn.commit()

            return {
                "lessons_processed": lessons_created,
                "questions_upserted": questions_upserted,
                "mappings_processed": mappings_created,
            }

        except Exception:
            conn.rollback()
            raise
