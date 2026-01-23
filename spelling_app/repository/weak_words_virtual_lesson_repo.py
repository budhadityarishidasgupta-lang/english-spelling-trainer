from spelling_app.repository.weak_words_repo import get_global_weak_words
from spelling_app.repository.student_repo import get_words_by_texts


def prepare_system_weak_words_lesson_for_user(user_id: int, limit: int = 50):
    """
    Build a virtual lesson using CURRENT word_ids
    resolved from weak word TEXT.
    """

    weak_word_texts = get_global_weak_words(user_id, limit)

    if not weak_word_texts:
        return None

    # 🔑 Resolve to CURRENT spelling_words rows
    words = get_words_by_texts(weak_word_texts)

    if not words:
        return None

    return {
        "lesson_name": "Weak Words",
        "word_count": len(words),
        "words": words,
    }
