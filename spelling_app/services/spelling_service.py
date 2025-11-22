from spelling_app.repository.course_repo import *
from spelling_app.repository.lesson_repo import *
from spelling_app.repository.item_repo import *
from spelling_app.repository.attempt_repo import *


def load_course_data(course_type: str = "spelling"):
    results = get_all_courses()

    if isinstance(results, dict) and results.get("error"):
        return results

    if course_type != "spelling":
        return results

    return [
        {
            "course_id": r["course_id"],
            "title": r["title"],
            "description": r.get("description"),
        }
        for r in results
    ]


def load_lessons(course_id):
    return get_lessons(course_id)


def load_items(lesson_id):
    return get_items_for_lesson(lesson_id)


def record_attempt(user_id, course_id, lesson_id, item_id, typed_answer, correct, response_ms=0):
    return log_attempt(user_id, course_id, lesson_id, item_id, typed_answer, correct, response_ms)
