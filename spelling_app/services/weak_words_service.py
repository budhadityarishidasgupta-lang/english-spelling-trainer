from spelling_app.repository.weak_words_repo import get_weak_words_summary

def load_weak_words():
    """
    Wrapper for UI consumption.
    """
    return get_weak_words_summary()
