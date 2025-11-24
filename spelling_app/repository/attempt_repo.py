from shared.db import fetch_all, execute


def log_attempt(user_id, course_id, lesson_id, item_id, typed_answer, is_correct, response_ms):
    return execute(
        """
        INSERT INTO spelling_attempts (student_id, item_id, is_correct, attempted_at)
        VALUES (:student_id, :item_id, :is_correct, NOW());
        """,
        {"student_id": user_id, "item_id": item_id, "is_correct": is_correct},
    )
