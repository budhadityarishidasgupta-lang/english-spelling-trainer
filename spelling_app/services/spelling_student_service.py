from spelling_app.repository.attempts_repo import (
    get_spelling_attempts_summary,
)


def get_spelling_student_summary():
    """
    Returns student spelling analytics formatted for UI.
    """
    return get_spelling_attempts_summary()
