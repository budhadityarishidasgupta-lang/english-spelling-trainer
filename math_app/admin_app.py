import streamlit as st

from math_app.db import init_math_tables
from math_app.repository.math_practice_ingest_repo import ingest_practice_csv
from math_app.repository.math_lessons_repo import (
    get_lessons_for_course,
    update_lesson_display_name,
)

# Ensure maths tables exist (SAFE)
init_math_tables()

st.title("📘 WordSprint Maths — Admin")

st.markdown("### 🧾 Upload Practice Paper CSV")
st.caption(
    "This uploader is for **Practice Papers only**. "
    "It will create lessons from the CSV `topic` and upsert questions by `question_id`. "
    "It is safe to re-upload the same file."
)

course_id = st.number_input("Course ID", min_value=1, value=1, step=1)

uploaded = st.file_uploader(
    "Upload a practice CSV (Fractions, etc.)",
    type=["csv"],
    accept_multiple_files=False,
)

if uploaded is not None:
    st.write("File:", uploaded.name)
    if st.button("✅ Ingest Practice CSV", use_container_width=True):
        try:
            summary = ingest_practice_csv(
                uploaded,
                course_id=int(course_id),
                created_by="admin_ui",
            )
            st.success("Practice CSV ingested successfully!")
            st.json(summary)
        except Exception as e:
            st.error("Ingestion failed. Fix the CSV and try again.")
            st.exception(e)

st.divider()
st.header("Maths Practice Lessons")

lessons = get_lessons_for_course(int(course_id))

if not lessons:
    st.info("No practice lessons found.")
else:
    for lesson in lessons:
        col1, col2, col3 = st.columns([3, 4, 1])

        with col1:
            st.text(lesson["lesson_name"])

        with col2:
            new_display_name = st.text_input(
                label="Display Name",
                value=lesson["display_name"] or "",
                key=f"display_name_{lesson['lesson_id']}",
            )

        with col3:
            if st.button("Save", key=f"save_lesson_{lesson['lesson_id']}"):
                update_lesson_display_name(
                    lesson_id=lesson["lesson_id"],
                    display_name=new_display_name.strip() or None,
                )
                st.success("Saved")
