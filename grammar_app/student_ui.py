from __future__ import annotations

from typing import Any, Dict, Optional

import streamlit as st

from grammar_app.services.access_service import has_grammar_access
from grammar_app.services.grammar_service import (
    DEFAULT_COURSE_NAME,
    get_grammar_course_by_name,
    get_grammar_lesson_questions,
    get_lesson_progress,
    list_grammar_lessons,
    submit_grammar_answer,
)
from shared.auth import get_logged_in_user

GRAMMAR_PAGE_KEY = "grammar_page"
GRAMMAR_LESSON_ID_KEY = "grammar_selected_lesson_id"
GRAMMAR_LESSON_TITLE_KEY = "grammar_selected_lesson_title"
GRAMMAR_LESSON_CODE_KEY = "grammar_selected_lesson_code"
GRAMMAR_STATE_KEY = "grammar_practice_state"


def _user_email(user: Any) -> str:
    if isinstance(user, dict):
        return str(user.get("email") or user.get("user_email") or "").strip().lower()
    if hasattr(user, "get"):
        try:
            return str(user.get("email") or user.get("user_email") or "").strip().lower()
        except Exception:
            return ""
    return str(getattr(user, "email", "") or "").strip().lower()


def _user_id(user: Any) -> Optional[int]:
    if isinstance(user, dict):
        value = user.get("id") or user.get("user_id")
    else:
        value = getattr(user, "id", None) or getattr(user, "user_id", None)
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


def _lesson_title(lesson: Dict[str, Any]) -> str:
    return str(lesson.get("lesson_name") or lesson.get("title") or lesson.get("lesson_code") or "Lesson")


def _lesson_code(lesson: Dict[str, Any]) -> str:
    return str(lesson.get("lesson_code") or lesson.get("code") or "")


def _open_lesson(lesson: Dict[str, Any]) -> None:
    st.session_state[GRAMMAR_PAGE_KEY] = "practice"
    st.session_state[GRAMMAR_LESSON_ID_KEY] = int(lesson.get("lesson_id"))
    st.session_state[GRAMMAR_LESSON_TITLE_KEY] = _lesson_title(lesson)
    st.session_state[GRAMMAR_LESSON_CODE_KEY] = _lesson_code(lesson)
    st.session_state.pop(GRAMMAR_STATE_KEY, None)
    st.rerun()


def _reset_to_lessons() -> None:
    st.session_state[GRAMMAR_PAGE_KEY] = "lesson_list"
    st.session_state.pop(GRAMMAR_STATE_KEY, None)
    st.rerun()


def _load_practice_state(lesson_id: int) -> Optional[Dict[str, Any]]:
    state = st.session_state.get(GRAMMAR_STATE_KEY)
    if state and state.get("lesson_id") == lesson_id:
        return state

    questions = get_grammar_lesson_questions(lesson_id)
    if not questions:
        return None

    state = {
        "lesson_id": lesson_id,
        "questions": questions,
        "index": 0,
        "feedback": None,
        "submitted": False,
    }
    st.session_state[GRAMMAR_STATE_KEY] = state
    return state


def render_grammar_lesson_list() -> None:
    user = get_logged_in_user()
    if not user:
        st.error("You must be logged in to access GrammarSprint.")
        return

    user_email = _user_email(user)
    user_id = _user_id(user)
    if not has_grammar_access(user_email):
        st.warning("Your account does not currently have GrammarSprint access.")
        return

    course = get_grammar_course_by_name(DEFAULT_COURSE_NAME)
    if not course:
        st.warning("GrammarSprint v1 is not available yet.")
        return

    if user_id is None:
        st.error("Could not identify the current student.")
        return

    raw_lessons = list_grammar_lessons(int(course["course_id"]))
    lessons = []
    for lesson in raw_lessons:
        progress = get_lesson_progress(user_id, int(lesson["lesson_id"]))
        lessons.append({**lesson, **progress})

    next_lesson = next((lesson for lesson in lessons if not lesson.get("is_completed")), None)

    st.title(DEFAULT_COURSE_NAME)
    st.caption("GrammarSprint v1")

    if next_lesson:
        st.info(f"Recommended next lesson: {_lesson_title(next_lesson)}")

    if not lessons:
        st.info("No GrammarSprint lessons are available yet.")
        return

    st.write("All 10 lessons are visible. Open any lesson to start practice.")

    for lesson in lessons:
        lesson_title = _lesson_title(lesson)
        lesson_code = _lesson_code(lesson)
        attempted = int(lesson.get("attempted_questions") or 0)
        total = int(lesson.get("total_questions") or 0)
        accuracy = float(lesson.get("accuracy_pct") or 0)
        is_complete = bool(lesson.get("is_completed"))
        is_next = bool(next_lesson and next_lesson.get("lesson_id") == lesson.get("lesson_id"))

        with st.container():
            left, right = st.columns([4, 1])
            with left:
                st.markdown(f"### {lesson_title}")
                if lesson_code:
                    st.caption(lesson_code)
                st.caption(f"Attempted: {attempted}/{total} | Accuracy: {accuracy:.1f}%")
                if is_complete:
                    st.success("Completed")
                elif is_next:
                    st.warning("Recommended next")
                else:
                    st.info("Not completed")
            with right:
                if st.button("Open lesson", key=f"grammar_open_{lesson.get('lesson_id')}"):
                    _open_lesson(lesson)
            st.divider()


def _render_feedback(state: Dict[str, Any], lesson_id: int, course_id: int, user_id: int, user_email: str) -> None:
    feedback = state.get("feedback") or {}
    if feedback.get("is_correct"):
        st.success("Correct")
    else:
        st.error("Incorrect")

    st.markdown(f"**Correct answer:** {feedback.get('correct_option') or ''}")
    if feedback.get("explanation"):
        st.info(feedback["explanation"])

    next_col, back_col = st.columns(2)
    with next_col:
        if st.button("Next Question", key=f"grammar_next_{lesson_id}_{state['index']}"):
            state["index"] += 1
            state["feedback"] = None
            state["submitted"] = False
            if state["index"] >= len(state["questions"]):
                st.session_state[GRAMMAR_PAGE_KEY] = "lesson_list"
                st.session_state.pop(GRAMMAR_STATE_KEY, None)
            st.rerun()
    with back_col:
        if st.button("Back to lessons", key=f"grammar_back_{lesson_id}_{state['index']}"):
            _reset_to_lessons()


def _render_question(state: Dict[str, Any], lesson_id: int, course_id: int, user_id: int, user_email: str) -> None:
    questions = state["questions"]
    index = int(state["index"])
    if index >= len(questions):
        st.success("Lesson complete.")
        if st.button("Back to lessons", key=f"grammar_done_back_{lesson_id}"):
            _reset_to_lessons()
        return

    current = questions[index]
    st.subheader(f"Question {index + 1} of {len(questions)}")
    st.markdown(f"### {current.get('question_text') or ''}")
    if current.get("difficulty"):
        st.caption(f"Difficulty: {current.get('difficulty')}")
    if current.get("skill_tag"):
        st.caption(f"Skill tag: {current.get('skill_tag')}")

    options = current.get("options") or {}
    with st.form(key=f"grammar_practice_{lesson_id}_{index}"):
        selected_label = st.radio(
            "Choose the best answer",
            options=list(options.keys()),
            format_func=lambda label: f"{label}. {options[label]}",
            key=f"grammar_choice_{lesson_id}_{index}",
        )
        submitted = st.form_submit_button("Submit")

    if submitted:
        result = submit_grammar_answer(
            user_id=user_id,
            course_id=course_id,
            lesson_id=lesson_id,
            question_id=int(current["question_id"]),
            selected_option=selected_label,
            user_email=user_email,
        )
        state["feedback"] = result
        state["submitted"] = True
        st.rerun()

    if st.button("Back to lessons", key=f"grammar_back_question_{lesson_id}_{index}"):
        _reset_to_lessons()


def render_grammar_practice() -> None:
    user = get_logged_in_user()
    if not user:
        st.error("You must be logged in to practice GrammarSprint.")
        return

    user_email = _user_email(user)
    user_id = _user_id(user)
    if not has_grammar_access(user_email):
        st.warning("Your account does not currently have GrammarSprint access.")
        return

    course = get_grammar_course_by_name(DEFAULT_COURSE_NAME)
    if not course:
        st.warning("GrammarSprint v1 is not available yet.")
        return

    if user_id is None:
        st.error("Could not identify the current student.")
        return

    lesson_id = st.session_state.get(GRAMMAR_LESSON_ID_KEY)
    if not lesson_id:
        _reset_to_lessons()
        return

    state = _load_practice_state(int(lesson_id))
    if state is None:
        st.info("This lesson does not have any questions yet.")
        if st.button("Back to lessons", key="grammar_back_no_questions"):
            _reset_to_lessons()
        return

    st.title(st.session_state.get(GRAMMAR_LESSON_TITLE_KEY) or DEFAULT_COURSE_NAME)
    if st.session_state.get(GRAMMAR_LESSON_CODE_KEY):
        st.caption(st.session_state[GRAMMAR_LESSON_CODE_KEY])

    progress = (state["index"] / max(len(state["questions"]), 1))
    st.progress(min(max(progress, 0.0), 1.0))

    if state.get("feedback"):
        _render_feedback(state, int(lesson_id), int(course["course_id"]), user_id, user_email)
        return

    _render_question(state, int(lesson_id), int(course["course_id"]), user_id, user_email)
