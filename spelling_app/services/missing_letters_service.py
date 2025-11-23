from spelling_app.repository.missing_letters_repo import fetch_missing_letter_words


def get_missing_letter_words():
    """
    Wrapper for UI consumption.
    """
    return fetch_missing_letter_words()
