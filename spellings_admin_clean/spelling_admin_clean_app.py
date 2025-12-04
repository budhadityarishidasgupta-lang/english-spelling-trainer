import sys, os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Fix Python path for Codespaces
ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(ROOT)
sys.path.insert(0, PROJECT_ROOT)

import streamlit as st

# Must be first Streamlit command
st.set_page_config(
    page_title="Spelling Admin Console (Clean Build)",
    layout="wide",
)

# Debug: DB URL
st.write("DEBUG DATABASE_URL:", os.getenv("DATABASE_URL"))

import sqlalchemy
from shared.db import engine, fetch_all

with engine.connect() as conn:
    schema_path = conn.execute(sqlalchemy.text("SHOW search_path;")).scalar()
st.write("DEBUG: Active search_path:", schema_path)

# -----------------------------
# IMPORT CLEAN MANAGERS
# -----------------------------

from spellings_admin_clean.upload_manager_clean import process_spelling_csv
from spellings_admin_clean.word_manager_clean import (
    get_or_create_word,
    get_or_create_lesson,
    link_word_to_lesson,
)
from spellings_admin_clean.course_manager_clean import (
    list_courses,
    create_course_admin,
)

# -----------------------------
# HELPER UI FUNCTIONS
# -----------------------------

def ui_get_lessons_for_course(course_id: int):
    rows = fetch_all(
        """
        SELECT lesson_id, lesson_name
        FROM spelling_lessons
        WHERE course_id = :cid
        ORDER BY lesson_id ASC;
        """,
        {"cid": course_id},
    )
    return [dict(row._mapping) for row in rows] if rows else []


def ui_get_lesson_words(lesson_id: int):
    rows = fetch_all(
        """
        SELECT w.word_id, w.word, w.pattern_code
        FROM spelling_words w
        JOIN spelling_lesson_words lw ON lw.word_id = w.word_id
        WHERE lw.lesson_id = :lid
        ORDER BY w.word_id ASC;
        """,
        {"lid": lesson_id},
    )
    return [dict(row._mapping) for row in rows] if rows else []


# -----------------------------
# COURSE SECTION
# -----------------------------

def render_course_section():
    st.subheader("Courses")

    courses = list_courses()
    course_options = {
        f"{c['course_id']}: {c['course_name']}": c["course_id"] for c in courses
    }

    selected_course_label = st.selectbox(
        "Select course",
        options=list(course_options.keys()) if course_options else ["No courses yet"],
    )

    selected_course_id = None
    if course_options:
        selected_course_id = course_options[selected_course_label]

    with st.expander("Create new course"):
        new_title = st.text_input("Course title", key="new_course_title")
        new_desc = st.text_area("Course description", key="new_course_desc")
        if st.button("Create course"):
            if not new_title.strip():
                st.error("Title is required.")
            else:
                cid = create_course_admin(new_title.strip(), new_desc.strip() or None)
                if cid:
                    st.success(f"Created course with ID {cid}")
                else:
                    st.error("Error creating course.")
                st.experimental_rerun()

    return selected_course_id


# -----------------------------
# UPLOAD SECTION
# -----------------------------

def render_upload_section(course_id: int):
    st.subheader("Upload CSV for course words & lessons")

    uploaded = st.file_uploader(
        "Upload CSV (columns: word, pattern_code, lesson_name)",
        type=["csv"],
        key="spelling_csv_uploader",
    )

    if uploaded is not None:
        import pandas as pd

        df = pd.read_csv(uploaded)
        if df.empty:
            st.warning("CSV appears empty or invalid.")
            return

        st.write("Preview:")
        st.dataframe(df.head())

        if st.button("Process CSV for this course"):
            summary = process_spelling_csv(df=df, course_id=course_id)
            st.success("Upload processed.")
            st.write(summary)
            st.experimental_rerun()


# -----------------------------
# WORD + LESSON OVERVIEW
# -----------------------------

def render_words_lessons_section(course_id: int):
    st.subheader("Words & Lessons Overview")

    lessons = ui_get_lessons_for_course(course_id)
    if not lessons:
        st.info("No lessons found yet. Upload a CSV.")
        return

    lesson_label_map = {
        f"{l['lesson_id']}: {l['lesson_name']}": l["lesson_id"] for l in lessons
    }

    selected_label = st.selectbox(
        "Select lesson",
        options=list(lesson_label_map.keys())
    )

    lesson_id = lesson_label_map[selected_label]

    words = ui_get_lesson_words(lesson_id)

    if not words:
        st.info("No words mapped to this lesson yet.")
    else:
        st.write("Words in this lesson:")
        st.dataframe(words)


# -----------------------------
# MAIN
# -----------------------------

def main():
    st.title("Spelling Admin Console (Clean Build)")

    course_id = render_course_section()

    if not course_id:
        st.info("Create or select a course to continue.")
        return

    col1, col2 = st.columns([2, 2])

    with col1:
        render_upload_section(course_id)

    with col2:
        render_words_lessons_section(course_id)


if __name__ == "__main__":
    main()
