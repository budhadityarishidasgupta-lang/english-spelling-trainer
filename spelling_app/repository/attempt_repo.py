# spelling_app/repository/attempt_repo.py

from shared.db import execute


def log_attempt(
    student_id: int,
    item_id: int,
    is_correct: bool,
):
    """
    Insert a single attempt into spelling_attempts.

    Only stores:
      - student_id
      - item_id
      - is_correct
      - attempted_at (NOW)

    Additional metadata (course, lesson, timing, typed answer)
    can be added later but is intentionally excluded here.
    """

    return execute(
        """
        INSERT INTO spelling_attempts (student_id, item_id, is_correct, attempted_at)
        VALUES (:student_id, :item_id, :is_correct, NOW());
        """,
        {
            "student_id": student_id,
            "item_id": item_id,
            "is_correct": is_correct,
        },
    )
