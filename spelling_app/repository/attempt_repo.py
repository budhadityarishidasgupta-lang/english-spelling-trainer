from shared.db import fetch_all, execute


def log_attempt(user_id, course_id, lesson_id, item_id, typed_answer, is_correct, response_ms):
    return execute(
        """
        INSERT INTO attempts
        (user_id, sp_course_id, sp_lesson_id, sp_item_id, typed_answer, is_correct, response_ms)
        VALUES
        (:uid, :cid, :lid, :iid, :ta, :correct, :ms)
        """,
        {
            "uid": user_id,
            "cid": course_id,
            "lid": lesson_id,
            "iid": item_id,
            "ta": typed_answer,
            "correct": is_correct,
            "ms": response_ms,
        }
    )
