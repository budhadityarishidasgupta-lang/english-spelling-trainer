from __future__ import annotations

import pandas as pd
import streamlit as st

from grammar_app.services.access_service import has_grammar_access
from grammar_app.services.grammar_service import DEFAULT_COURSE_NAME, process_grammar_csv_upload, get_student_grammar_overview
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
        st.caption("GrammarSprint access is controlled by GSM or app_code=grammar.")
        return

    st.title("GrammarSprint Admin")
    st.caption("Default course: GrammarSprint v1")
    st.info("CSV uploads are idempotent. Re-uploading the same file will not duplicate lessons, questions, or mappings.")

    overview = get_student_grammar_overview(user_email)
    lessons = overview.get("lessons", [])
    st.subheader("Current lesson map")
    if lessons:
        lesson_rows = []
        for lesson in lessons:
            lesson_rows.append(
                {
                    "lesson_id": lesson.get("lesson_id"),
                    "lesson_code": lesson.get("lesson_code"),
                    "lesson_name": lesson.get("lesson_name") or lesson.get("title"),
                    "sort_order": lesson.get("sort_order"),
                    "progress_pct": lesson.get("progress_pct"),
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
        df = pd.read_csv(uploaded)
    except Exception as exc:
        st.error(f"Could not read CSV: {exc}")
        return

    st.write("Preview")
    st.dataframe(df.head(50), use_container_width=True, hide_index=True)

    if st.button("Import CSV", type="primary"):
        result = process_grammar_csv_upload(df, default_course_name=DEFAULT_COURSE_NAME)
        if "error" in result:
            st.error(result["error"])
            return

        st.success(result["message"])
        summary = result.get("summary", {})
        metric_cols = st.columns(4)
        metric_cols[0].metric("Rows imported", summary.get("rows_imported", 0))
        metric_cols[1].metric("Rows skipped", summary.get("rows_skipped", 0))
        metric_cols[2].metric("New lessons", summary.get("lessons_created", 0))
        metric_cols[3].metric("New questions", summary.get("questions_created", 0))

        details = result.get("details", [])
        if details:
            st.dataframe(pd.DataFrame(details), use_container_width=True, hide_index=True)
