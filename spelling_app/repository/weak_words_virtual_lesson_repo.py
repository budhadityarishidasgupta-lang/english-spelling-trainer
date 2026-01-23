from spelling_app.repository.weak_words_repo import (
    get_global_weak_word_ids,
    load_weak_words_by_ids,
)


def prepare_system_weak_words_lesson_for_user(user_id: int, limit: int = 50):
    """
    Virtual lesson builder for Weak Words.
    """
    word_ids = get_global_weak_word_ids(user_id, limit)

    if not word_ids:
        return None

    words = load_weak_words_by_ids(word_ids)

    if not words:
        return None

    return {
        "word_ids": [w["word_id"] for w in words],
        "words": words,
        "word_count": len(words),
    }
