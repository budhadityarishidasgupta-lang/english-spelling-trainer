from spelling_app.repository.weak_words_repo import fetch_user_weak_words


def get_virtual_weak_words_for_user(conn, user_id: int):
    return fetch_user_weak_words(conn, user_id)
