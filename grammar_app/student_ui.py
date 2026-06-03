from __future__ import annotations

from typing import Any, Dict, Optional

import streamlit as st

from grammar_app.practice_ui import render_grammar_practice
from grammar_app.services.access_service import has_grammar_access
from grammar_app.services.grammar_service import (
    DEFAULT_COURSE_NAME,
    get_student_grammar_overview,
)
from shared.auth import get_logged_in_user

GRAMMAR_PAGE_KEY = "grammar_page"
GRAMMAR_LESSON_ID_KEY = "grammar_selected_lesson_id"
GRAMMAR_LESSON_TITLE_KEY = "grammar_selected_lesson_title"
GRAMMAR_LESSON_CODE_KEY = "grammar_selected_lesson_code"


def _user_email(user: Any) -> str:
    if isinstance(user, dict):
        return str(user.get("email") or user.get("user_email") or "").strip().lower()
    if hasattr(user, "get"):
        try:
            return str(user.get("email") or user.get("user_email") or "").strip().lower()
        except Exception:
            return ""
    return str(getattr(user, "email", "") or "").strip().lower()


def _lesson_title(lesson: Dict[str, Any]) -> str:
    return str(lesson.get("lesson_name") or lesson.get("title") or lesson.get("lesson_code") or "Lesson")


def _lesson_code(lesson: Dict[str, Any]) -> str:
    return str(lesson.get("lesson_code") or lesson.get("code") or "")


def _course_title(course: Dict[str, Any]) -> str:
    return str(course.get("course_name") or course.get("title") or DEFAULT_COURSE_NAME)


def _open_lesson(lesson: Dict[str, Any]) -> None:
    st.session_state[GRAMMAR_PAGE_KEY] = "practice"
    st.session_state[GRAMMAR_LESSON_ID_KEY] = lesson.get("lesson_id")
    st.session_state[GRAMMAR_LESSON_TITLE_KEY] = _lesson_title(lesson)
    st.session_state[GRAMMAR_LESSON_CODE_KEY] = _lesson_code(lesson)
    st.rerun()


def render_grammar_lesson_list() -> None:
    user = get_logged_in_user()
    if not user:
        st.error("You must be logged in to access GrammarSprint.")
        return

    user_email = _user_email(user)
    if not has_grammar_access(user_email):
        st.warning("Your account does not currently have GrammarSprint access.")
        st.caption("GrammarSprint access is controlled by GSM or app_code=grammar.")
        return

    overview = get_student_grammar_overview(user_email)
    course = overview.get("course", {})
    lessons = overview.get("lessons", [])
    next_lesson = overview.get("next_lesson")

    course_name = _course_title(course)
    st.title(course_name)
    st.caption("GrammarSprint v1")

    if next_lesson:
        st.info(
            f"Next incomplete lesson: {_lesson_title(next_lesson)}"
            + (f" ({_lesson_code(next_lesson)})" if _lesson_code(next_lesson) else "")
        )

    if not lessons:
        st.info("No GrammarSprint lessons are available yet.")
        return

    st.write("All lessons are visible. Open any lesson to start practice.")

    for lesson in lessons:
        progress_pct = float(lesson.get("progress_pct") or 0)
        completed = int(lesson.get("completed_questions") or 0)
        total = int(lesson.get("total_questions") or 0)
        lesson_title = _lesson_title(lesson)
        lesson_code = _lesson_code(lesson)
        is_next = bool(next_lesson and next_lesson.get("lesson_id") == lesson.get("lesson_id"))
        is_complete = bool(lesson.get("is_complete"))

        with st.container():
            col_left, col_right = st.columns([4, 1])
            with col_left:
                st.markdown(f"### {lesson_title}")
                if lesson_code:
                    st.caption(lesson_code)
                st.progress(min(max(progress_pct / 100.0, 0.0), 1.0))
                st.caption(f"Progress: {completed}/{total} questions completed")
                if is_complete:
                    st.success("Completed")
                elif is_next:
                    st.warning("Next to complete")
                elif progress_pct > 0:
                    st.info("In progress")
                else:
                    st.caption("Not started")
            with col_right:
                if st.button("Open lesson", key=f"grammar_open_{lesson.get('lesson_id')}"):
                    _open_lesson(lesson)

            st.divider()


def render_grammar_student() -> None:
    if st.session_state.get(GRAMMAR_PAGE_KEY) == "practice":
        render_grammar_practice()
        return
    render_grammar_lesson_list()
