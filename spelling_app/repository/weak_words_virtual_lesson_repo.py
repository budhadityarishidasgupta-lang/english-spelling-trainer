from spelling_app.repository.weak_words_repo import get_user_weak_words

def prepare_system_weak_words_lesson_for_user(
    user_id: int,
    course_id: int,
    limit: int = 30
):
    """
    Builds a virtual lesson object for Weak Words.
    """

    words = get_user_weak_words(user_id, course_id, limit)

    if not words:
        return None

    return {
        "lesson_id": -1,  # virtual system lesson
        "lesson_name": "Weak Words",
        "word_count": len(words),
        "words": words,
    }
