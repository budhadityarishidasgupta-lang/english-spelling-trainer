import csv
from io import StringIO

from math_app.db import get_db_connection


EXPORT_COLUMNS = [
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
    "hint",
]


def export_lesson_to_csv(lesson_id: int) -> str:
    """
    Export all questions for a lesson into a CSV string.
    Format matches ingestion contract exactly.
    """

    sql = """
    SELECT
        q.question_id,
        q.topic,
        q.difficulty,
        q.stem,
        q.option_a,
        q.option_b,
        q.option_c,
        q.option_d,
        q.correct_option,
        q.explanation,
        q.hint
    FROM math_lesson_questions lq
    JOIN math_questions q
      ON q.id = lq.question_id
    WHERE lq.lesson_id = %s
    ORDER BY lq.position ASC;
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (lesson_id,))
            rows = cur.fetchall()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(EXPORT_COLUMNS)

    for row in rows:
        writer.writerow(row)

    return output.getvalue()
