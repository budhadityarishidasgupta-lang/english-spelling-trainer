from spelling_app.repository.daily5_repo import fetch_daily5_words


def get_daily5_words():
    """
    Wrapper for UI consumption.
    """
    return fetch_daily5_words()
