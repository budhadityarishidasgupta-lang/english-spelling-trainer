from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st

from grammar_app.services.access_service import has_grammar_access
from grammar_app.services.grammar_service import get_grammar_lesson_questions, submit_grammar_answer
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


def _lesson_title() -> str:
    return str(st.session_state.get(GRAMMAR_LESSON_TITLE_KEY) or "GrammarSprint Practice")


def _lesson_code() -> str:
    return str(st.session_state.get(GRAMMAR_LESSON_CODE_KEY) or "")


def _reset_to_lessons() -> None:
    st.session_state[GRAMMAR_PAGE_KEY] = "lesson_list"
    st.session_state.pop(GRAMMAR_STATE_KEY, None)
    st.rerun()


def _init_state(lesson_id: int) -> Optional[Dict[str, Any]]:
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
        "attempt_results": [],
        "finished": False,
    }
    st.session_state[GRAMMAR_STATE_KEY] = state
    return state


def _render_summary(state: Dict[str, Any]) -> None:
    total = len(state.get("questions", []))
    correct = sum(1 for result in state.get("attempt_results", []) if result.get("is_correct"))
    st.success(f"Lesson complete. Score: {correct}/{total}")
    if correct == total and total > 0:
        st.balloons()

    if state.get("attempt_results"):
        st.subheader("Review")
        for result in state["attempt_results"]:
            if result.get("is_correct"):
                st.markdown(f"- ✅ {result.get('question_text', 'Question')}")
            else:
                st.markdown(
                    f"- ❌ {result.get('question_text', 'Question')} | Your answer: {result.get('selected_option') or result.get('selected_text') or 'blank'}"
                )

    col_back, col_restart = st.columns(2)
    with col_back:
        if st.button("Back to lessons", key="grammar_back_to_lessons"):
            _reset_to_lessons()
    with col_restart:
        if st.button("Restart lesson", key="grammar_restart_lesson"):
            st.session_state.pop(GRAMMAR_STATE_KEY, None)
            st.rerun()


def _render_feedback(state: Dict[str, Any]) -> None:
    feedback = state.get("feedback") or {}
    if feedback.get("is_correct"):
        st.success("Correct")
    else:
        st.error("Incorrect")

    st.markdown(f"**Correct answer:** {feedback.get('correct_label') or ''}{('. ' if feedback.get('correct_label') else '')}{feedback.get('correct_text') or ''}")
    if feedback.get("explanation"):
        st.info(feedback["explanation"])

    col_next, col_back = st.columns(2)
    with col_next:
        if st.button("Next question", key=f"grammar_next_{state['lesson_id']}_{state['index']}"):
            state["index"] += 1
            state["feedback"] = None
            state["finished"] = state["index"] >= len(state.get("questions", []))
            st.rerun()
    with col_back:
        if st.button("Back to lessons", key=f"grammar_back_{state['lesson_id']}_{state['index']}"):
            _reset_to_lessons()


def _render_question(state: Dict[str, Any], user_email: str) -> None:
    questions = state.get("questions", [])
    index = int(state.get("index") or 0)
    if index >= len(questions):
        state["finished"] = True
        return

    current = questions[index]
    options = current.get("options") or {}
    if not options:
        st.warning("This question does not have any options yet.")
        if st.button("Back to lessons", key=f"grammar_back_empty_{state['lesson_id']}_{index}"):
            _reset_to_lessons()
        return

    st.subheader(f"Question {index + 1} of {len(questions)}")
    st.markdown(f"### {current.get('question_text') or ''}")
    if current.get("difficulty"):
        st.caption(f"Difficulty: {current.get('difficulty')}")
    if current.get("skill_tag"):
        st.caption(f"Skill tag: {current.get('skill_tag')}")

    radio_options = list(options.keys())
    with st.form(key=f"grammar_practice_form_{state['lesson_id']}_{index}"):
        selected_label = st.radio(
            "Choose the best answer",
            options=radio_options,
            format_func=lambda label: f"{label}. {options[label]}",
            key=f"grammar_choice_{state['lesson_id']}_{index}",
        )
        submitted = st.form_submit_button("Submit")

    if submitted:
        result = submit_grammar_answer(
            user_email=user_email,
            lesson_id=int(state["lesson_id"]),
            question_id=int(current["question_id"]),
            selected_option=selected_label,
            selected_text=options.get(selected_label),
        )
        state["feedback"] = result
        state.setdefault("attempt_results", []).append(result)
        st.rerun()

    if st.button("Back to lessons", key=f"grammar_back_question_{state['lesson_id']}_{index}"):
        _reset_to_lessons()


def render_grammar_practice() -> None:
    user = get_logged_in_user()
    if not user:
        st.error("You must be logged in to practice GrammarSprint.")
        return

    user_email = _user_email(user)
    if not has_grammar_access(user_email):
        st.warning("Your account does not currently have GrammarSprint access.")
        return

    lesson_id = st.session_state.get(GRAMMAR_LESSON_ID_KEY)
    if not lesson_id:
        _reset_to_lessons()
        return

    state = _init_state(int(lesson_id))
    if state is None:
        st.info("This lesson does not have any questions yet.")
        if st.button("Back to lessons", key="grammar_back_no_questions"):
            _reset_to_lessons()
        return

    st.title(_lesson_title())
    if _lesson_code():
        st.caption(_lesson_code())

    progress = (state.get("index", 0) / max(len(state.get("questions", [])), 1))
    st.progress(min(max(progress, 0.0), 1.0))

    if state.get("finished"):
        _render_summary(state)
        return

    if state.get("feedback"):
        _render_feedback(state)
        return

    _render_question(state, user_email)
