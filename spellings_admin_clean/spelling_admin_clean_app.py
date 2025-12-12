#!/usr/bin/env python3

# -------------------------------------------------
# FORCE PYTHONPATH (Render-safe)
# -------------------------------------------------
import os
import sys

PROJECT_ROOT = "/opt/render/project/src"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# -------------------------------------------------
# Imports AFTER path fix
# -------------------------------------------------
import streamlit as st
from shared.db import fetch_all, execute
from spellings_admin_clean.upload_manager_clean import process_spelling_csv



# -----------------------------
# Helpers for courses
# -----------------------------

def _rows_to_dicts(rows):
    if not rows:
        return []
    result = []
    for r in rows:
        if hasattr(r, "_mapping"):
            result.append(dict(r._mapping))
        elif isinstance(r, dict):
            result.append(r)
    return result


def get_all_courses():
    rows = fetch_all(
        "SELECT course_id, course_name FROM spelling_courses ORDER BY course_id"
    )
    return _rows_to_dicts(rows)


def create_course(course_name: str):
    if not course_name.strip():
        return None
    rows = fetch_all(
        """
        INSERT INTO spelling_courses (course_name)
        VALUES (:name)
        RETURNING course_id;
        """,
        {"name": course_name.strip()},
    )
    rows = _rows_to_dicts(rows)
    return rows[0]["course_id"] if rows else None


# -----------------------------
# Main page: CSV Upload + Courses
# -----------------------------

def render_spelling_csv_upload():
    st.header("Spelling Admin – Pattern Word Import")

    st.markdown(
        "Use this tool to create **courses, lessons, and words** from a structured CSV."
    )

    # --- Course section ---
    st.subheader("1. Select or Create Course")

    courses = get_all_courses()
    course_map = {c["course_name"]: c["course_id"] for c in courses} if courses else {}

    col1, col2 = st.columns([2, 1])

    with col1:
        if course_map:
            course_name = st.selectbox(
                "Existing Courses",
                options=list(course_map.keys()),
                index=0,
            )
            selected_course_id = course_map[course_name]
        else:
            st.info("No courses found yet. Please create one on the right.")
            selected_course_id = None

    with col2:
        with st.form("create_course_form", clear_on_submit=True):
            new_course_name = st.text_input("New Course Name")
            submitted = st.form_submit_button("Create Course")
            if submitted and new_course_name.strip():
                cid = create_course(new_course_name)
                if cid:
                    st.success(f"Course '{new_course_name}' created with id {cid}.")
                else:
                    st.error("Failed to create course. Check logs/DB.")

    st.markdown("---")

    # --- CSV upload section ---
    st.subheader("2. Upload Spelling CSV")

    uploaded_file = st.file_uploader(
        "Upload CSV file with columns: word, pattern, pattern_code, level, lesson_name, example_sentence",
        type=["csv"],
    )

    if uploaded_file is not None and selected_course_id is None:
        st.warning("Please select a course before uploading.")
        return

    if uploaded_file is not None and selected_course_id is not None:
        if st.button("Process CSV Upload"):
            result = process_spelling_csv(uploaded_file, selected_course_id)

            if not isinstance(result, dict):
                st.error("Unexpected result from CSV processor.")
                return

            if result.get("status") == "error":
                st.error(result.get("error", "Unknown error during CSV upload."))
                return

            st.success("Words uploaded to Pattern Words!")

            st.markdown("### Upload Summary")
            st.write(f"**Words Added:** {result.get('words_added', 0)}")
            st.write(f"**Lessons Created:** {result.get('lessons_created', 0)}")

            patterns = result.get("patterns") or []
            if patterns:
                st.write("**Patterns Detected:**")
                st.write(", ".join(patterns))

    # --- Debug DB status ---
    with st.expander("Debug DB Status"):
        words_count = fetch_all("SELECT COUNT(*) AS c FROM spelling_words")
        lessons_count = fetch_all("SELECT COUNT(*) AS c FROM spelling_lessons")
        mappings_count = fetch_all("SELECT COUNT(*) AS c FROM spelling_lesson_items")

        words_count = _rows_to_dicts(words_count)
        lessons_count = _rows_to_dicts(lessons_count)
        mappings_count = _rows_to_dicts(mappings_count)

        st.write("Words:", words_count[0]["c"] if words_count else 0)
        st.write("Lessons:", lessons_count[0]["c"] if lessons_count else 0)
        st.write("Lesson–Word Mappings:", mappings_count[0]["c"] if mappings_count else 0)

        sample_mappings = fetch_all(
            """
            SELECT sli.lesson_id, sl.lesson_name, sli.word_id, sw.word
            FROM spelling_lesson_items sli
            JOIN spelling_lessons sl ON sl.lesson_id = sli.lesson_id
            JOIN spelling_words sw ON sw.word_id = sli.word_id
            ORDER BY sli.lesson_id, sli.sort_order
            LIMIT 20;
            """
        )
        st.write("Sample mappings:")
        st.write(_rows_to_dicts(sample_mappings))


def main():
    st.set_page_config("WordSprint Spelling Admin", layout="wide")

    st.sidebar.title("Admin Navigation")
    section = st.sidebar.radio(
        "Section",
        ["Spelling CSV Upload"],
        index=0,
    )

    if section == "Spelling CSV Upload":
        render_spelling_csv_upload()


if __name__ == "__main__":
    main()
