from spelling_app.repository.course_repo import *
from spelling_app.repository.lesson_repo import *
from spelling_app.repository.item_repo import *
from spelling_app.repository.attempt_repo import *


def load_course_data():
    return get_all_courses()


def load_lessons(course_id):
    return get_lessons(course_id)


def load_items(lesson_id):
    return get_items_for_lesson(lesson_id)


def record_attempt(user_id, course_id, lesson_id, item_id, typed_answer, correct, response_ms=0):
    return log_attempt(user_id, course_id, lesson_id, item_id, typed_answer, correct, response_ms)
