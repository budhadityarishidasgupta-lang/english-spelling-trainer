from spelling_app.repository.weak_words_repo import get_global_weak_word_ids


def prepare_system_weak_words_lesson_for_user(user_id: int, limit: int = 50):
    """
    Virtual lesson for weak words.
    No lesson table involvement.
    """
    word_ids = get_global_weak_word_ids(user_id, limit=limit)

    if not word_ids:
        return {"word_count": 0}

    return {
        "lesson_id": -1,        # virtual lesson
        "course_id": -1,
        "word_count": len(word_ids),
        "word_ids": word_ids,
    }
