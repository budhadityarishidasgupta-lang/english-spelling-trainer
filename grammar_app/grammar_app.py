from __future__ import annotations

import streamlit as st

from grammar_app.admin_ui import render_grammar_admin
from grammar_app.student_ui import GRAMMAR_PAGE_KEY, render_grammar_lesson_list, render_grammar_practice


def render_grammar_student() -> None:
    page = st.session_state.get(GRAMMAR_PAGE_KEY, "lesson_list")
    if page == "practice":
        render_grammar_practice()
        return
    render_grammar_lesson_list()


__all__ = ["render_grammar_admin", "render_grammar_student"]
