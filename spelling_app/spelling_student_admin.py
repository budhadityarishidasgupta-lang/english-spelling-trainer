import streamlit as st
from spelling_app.services.spelling_student_service import (
    get_spelling_student_summary,
)


def render_spelling_student_admin():
    st.title("📘 Spelling Student Admin")
    st.markdown("Review spelling performance across students.")

    data = get_spelling_student_summary()

    if isinstance(data, dict) and "error" in data:
        st.error(str(data))
        return

    if not data:
        st.info("No spelling activity yet.")
        return

    st.dataframe(data)
