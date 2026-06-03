from __future__ import annotations

import pandas as pd
import streamlit as st

from grammar_app.services.access_service import has_grammar_access
from grammar_app.services.grammar_service import (
    DEFAULT_COURSE_NAME,
    get_grammar_course_by_name,
    get_lesson_questions,
    ingest_grammar_csv,
    list_grammar_lessons,
)
from shared.auth import get_logged_in_user


def _user_email(user) -> str:
    if isinstance(user, dict):
        return str(user.get("email") or user.get("user_email") or "").strip().lower()
    if hasattr(user, "get"):
        try:
            return str(user.get("email") or user.get("user_email") or "").strip().lower()
        except Exception:
            return ""
    return str(getattr(user, "email", "") or "").strip().lower()


def render_grammar_admin() -> None:
    user = get_logged_in_user()
    if not user:
        st.error("You must be logged in to access GrammarSprint admin tools.")
        return

    user_email = _user_email(user)
    if not has_grammar_access(user_email):
        st.warning("Your account does not currently have GrammarSprint admin access.")
        return

    course = get_grammar_course_by_name(DEFAULT_COURSE_NAME)
    if not course:
        st.warning("GrammarSprint v1 is not available yet.")
        return

    st.title("GrammarSprint Admin")
    st.caption("Default course: GrammarSprint v1")

    st.subheader("Current lesson map")
    lessons = list_grammar_lessons(int(course["course_id"]))
    if lessons:
        lesson_rows = []
        for lesson in lessons:
            lesson_questions = get_lesson_questions(int(lesson["lesson_id"]))
            lesson_rows.append(
                {
                    "lesson_id": lesson.get("lesson_id"),
                    "lesson_code": lesson.get("lesson_code"),
                    "lesson_name": lesson.get("lesson_name"),
                    "sort_order": lesson.get("sort_order"),
                    "question_count": len(lesson_questions),
                }
            )
        st.dataframe(pd.DataFrame(lesson_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No lessons found yet for GrammarSprint v1.")

    st.subheader("Upload Grammar CSV")
    uploaded = st.file_uploader("Choose a CSV file", type=["csv"])
    if uploaded is None:
        return

    try:
        preview_df = pd.read_csv(uploaded)
    except Exception as exc:
        st.error(f"Could not read CSV: {exc}")
        return

    st.write("Preview")
    st.dataframe(preview_df.head(50), use_container_width=True, hide_index=True)

    if st.button("Import CSV", type="primary"):
        uploaded.seek(0)
        result = ingest_grammar_csv(uploaded)
        if "error" in result:
            st.error(result["error"])
            return

        summary = result.get("summary", {})
        st.success("CSV import completed.")

        metric_cols = st.columns(5)
        metric_cols[0].metric("Rows seen", summary.get("rows_seen", 0))
        metric_cols[1].metric("Inserted", summary.get("rows_inserted", 0))
        metric_cols[2].metric("Updated", summary.get("rows_updated", 0))
        metric_cols[3].metric("Mappings created", summary.get("mappings_created", 0))
        metric_cols[4].metric("Mappings existing", summary.get("mappings_existing", 0))

        if result.get("errors"):
            st.subheader("Row-level errors")
            st.dataframe(pd.DataFrame(result["errors"]), use_container_width=True, hide_index=True)

        if result.get("details"):
            st.subheader("Import details")
            st.dataframe(pd.DataFrame(result["details"]), use_container_width=True, hide_index=True)
