#!/usr/bin/env python3
# -------------------------------------------------
# Spelling Admin App (FINAL, CLEAN)
# -------------------------------------------------

import sys
import os
import streamlit as st

# ---- Force project root for Render ----
PROJECT_ROOT = "/opt/render/project/src"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from shared.db import fetch_all
from spellings_admin_clean.upload_manager_clean import process_spelling_csv


# -------------------------------------------------
# Helpers
# -------------------------------------------------

def rows_to_dicts(rows):
    if not rows:
        return []
    out = []
    for r in rows:
        if hasattr(r, "_mapping"):
            out.append(dict(r._mapping))
        elif isinstance(r, dict):
            out.append(r)
    return out


def get_all_courses():
    rows = fetch_all(
        "SELECT course_id, course_name FROM spelling_courses ORDER BY course_id"
    )
    return rows_to_dicts(rows)


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
    rows = rows_to_dicts(rows)
    return rows[0]["course_id"] if rows else None


# -------------------------------------------------
# Main UI
# -------------------------------------------------

def render_csv_upload():
    st.header("Spelling Admin – CSV Upload")

    st.subheader("1️⃣ Select or Create Course")

    courses = get_all_courses()
    course_map = {c["course_name"]: c["course_id"] for c in courses}

    col1, col2 = st.columns([2, 1])

    with col1:
        if course_map:
            course_name = st.selectbox(
                "Existing Courses",
                list(course_map.keys()),
            )
            course_id = course_map[course_name]
        else:
            st.info("No courses yet.")
            course_id = None

    with col2:
        with st.form("create_course", clear_on_submit=True):
            new_course = st.text_input("New Course Name")
            submitted = st.form_submit_button("Create")
            if submitted and new_course.strip():
                cid = create_course(new_course)
                if cid:
                    st.success(f"Course '{new_course}' created.")
                else:
                    st.error("Failed to create course.")

    st.divider()
    st.subheader("2️⃣ Upload Spelling CSV")

    uploaded_file = st.file_uploader(
        "Upload CSV (word, pattern, pattern_code, level, lesson_name, example_sentence)",
        type=["csv"],
    )

    if uploaded_file and not course_id:
        st.warning("Please select or create a course first.")
        return

    if uploaded_file and course_id:
        if st.button("Process CSV"):
            result = process_spelling_csv(uploaded_file, course_id)

            if result.get("status") == "error":
                st.error(result.get("error"))
                return

            st.success("CSV processed successfully!")

            st.markdown("### Upload Summary")
            st.write("Words Added:", result["words_added"])
            st.write("Lessons Created:", result["lessons_created"])

            if result["patterns"]:
                st.write("Patterns:", ", ".join(result["patterns"]))

    # -------------------------------------------------
    # Debug panel (IMPORTANT)
    # -------------------------------------------------
    with st.expander("Debug DB Status"):
        words = fetch_all("SELECT COUNT(*) AS c FROM spelling_words")
        lessons = fetch_all("SELECT COUNT(*) AS c FROM spelling_lessons")
        mappings = fetch_all("SELECT COUNT(*) AS c FROM spelling_lesson_items")

        words = rows_to_dicts(words)
        lessons = rows_to_dicts(lessons)
        mappings = rows_to_dicts(mappings)

        st.write("Words:", words[0]["c"] if words else 0)
        st.write("Lessons:", lessons[0]["c"] if lessons else 0)
        st.write("Lesson–Word Mappings:", mappings[0]["c"] if mappings else 0)

        sample = fetch_all(
            """
            SELECT sl.lesson_name, sw.word
            FROM spelling_lesson_items sli
            JOIN spelling_lessons sl ON sl.lesson_id = sli.lesson_id
            JOIN spelling_words sw ON sw.word_id = sli.word_id
            ORDER BY sl.lesson_id, sli.sort_order
            LIMIT 20;
            """
        )
        st.write("Sample mappings:")
        st.write(rows_to_dicts(sample))


def main():
    st.set_page_config(
        page_title="WordSprint – Spelling Admin",
        layout="wide",
    )

    st.sidebar.title("Admin")
    section = st.sidebar.radio("Section", ["CSV Upload"])

    if section == "CSV Upload":
        render_csv_upload()


if __name__ == "__main__":
    main()
