import csv
import re

from shared.db import execute, fetch_one


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def normalize_lesson_name(topic: str) -> str:
    """
    Normalize topic into a stable lesson_name.
    Example: 'Fractions - Add' -> 'fractions_add'
    """
    if not topic:
        raise ValueError("Topic is required for lesson creation")

    name = topic.lower()
    name = re.sub(r"[^a-z0-9\s]", "", name)
    name = re.sub(r"\s+", "_", name.strip())
    return name


# ------------------------------------------------------------
# Core ingestion
# ------------------------------------------------------------

def ingest_practice_csv(
    csv_path: str,
    course_id: int,
):
    """
    Ingest a Maths practice CSV into existing maths tables.

    Rules:
    - question_id is the unique upsert key
    - topic defines lesson identity
    - lesson_name is normalized, display_name is editable
    - never deletes
    - never overwrites display_name
    """

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        required_fields = {
            "question_id",
            "topic",
            "difficulty",
            "stem",
            "option_a",
            "option_b",
            "option_c",
            "option_d",
            "correct_option",
            "explanation",
        }

        missing = required_fields - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV missing required columns: {missing}")

        for row in reader:
            topic = row["topic"].strip()
            lesson_name = normalize_lesson_name(topic)

            # ------------------------------------------------
            # Ensure lesson exists (DO NOT overwrite display)
            # ------------------------------------------------
            lesson = fetch_one(
                """
                SELECT lesson_id
                FROM math_lessons
                WHERE lesson_name = :lesson_name
                """,
                {"lesson_name": lesson_name},
            )

            if lesson:
                lesson_id = lesson["lesson_id"]
            else:
                result = execute(
                    """
                    INSERT INTO math_lessons (
                        course_id,
                        lesson_name,
                        display_name,
                        difficulty,
                        is_active
                    )
                    VALUES (
                        :course_id,
                        :lesson_name,
                        :display_name,
                        :difficulty,
                        TRUE
                    )
                    RETURNING lesson_id
                    """,
                    {
                        "course_id": course_id,
                        "lesson_name": lesson_name,
                        "display_name": topic,
                        "difficulty": row["difficulty"],
                    },
                )
                lesson_id = result[0]["lesson_id"]

            # ------------------------------------------------
            # Upsert question
            # ------------------------------------------------
            execute(
                """
                INSERT INTO math_questions (
                    question_id,
                    stem,
                    option_a,
                    option_b,
                    option_c,
                    option_d,
                    correct_option,
                    topic,
                    difficulty,
                    solution
                )
                VALUES (
                    :question_id,
                    :stem,
                    :option_a,
                    :option_b,
                    :option_c,
                    :option_d,
                    :correct_option,
                    :topic,
                    :difficulty,
                    :solution
                )
                ON CONFLICT (question_id) DO UPDATE
                SET
                    stem = EXCLUDED.stem,
                    option_a = EXCLUDED.option_a,
                    option_b = EXCLUDED.option_b,
                    option_c = EXCLUDED.option_c,
                    option_d = EXCLUDED.option_d,
                    correct_option = EXCLUDED.correct_option,
                    topic = EXCLUDED.topic,
                    difficulty = EXCLUDED.difficulty,
                    solution = EXCLUDED.solution
                """,
                {
                    "question_id": row["question_id"],
                    "stem": row["stem"],
                    "option_a": row["option_a"],
                    "option_b": row["option_b"],
                    "option_c": row["option_c"],
                    "option_d": row["option_d"],
                    "correct_option": row["correct_option"],
                    "topic": topic,
                    "difficulty": row["difficulty"],
                    "solution": row["explanation"],
                },
            )

            # ------------------------------------------------
            # Ensure lesson - question mapping
            # ------------------------------------------------
            execute(
                """
                INSERT INTO math_lesson_questions (lesson_id, question_id)
                SELECT :lesson_id, :question_id
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM math_lesson_questions
                    WHERE lesson_id = :lesson_id
                      AND question_id = :question_id
                )
                """,
                {
                    "lesson_id": lesson_id,
                    "question_id": row["question_id"],
                },
            )
