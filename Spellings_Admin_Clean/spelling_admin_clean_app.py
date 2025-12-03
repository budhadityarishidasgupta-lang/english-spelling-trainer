import streamlit as st

from Spellings_Admin_Clean.course_manager_clean import (
    list_courses,
    create_course_admin,
)
from Spellings_Admin_Clean.word_manager_clean import (
    get_words_for_course,
    get_lessons_for_course,
    get_lesson_words,
)
from Spellings_Admin_Clean.upload_manager_clean import process_spelling_csv
from Spellings_Admin_Clean.utils_clean import read_csv_to_df, show_upload_summary


def render_course_section():
    st.subheader("Courses")

    courses = list_courses()
    course_options = {f"{c['course_id']}: {c['title']}": c["course_id"] for c in courses}

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
                st.success(f"Created course with ID {cid}")
                st.experimental_rerun()

    return selected_course_id


def render_upload_section(course_id: int):
    st.subheader("Upload CSV for course words & lessons")

    uploaded = st.file_uploader(
        "Upload CSV (columns: word, pattern_code, lesson_name)",
        type=["csv"],
        key="spelling_csv_uploader",
    )

    if uploaded is not None:
        df = read_csv_to_df(uploaded)
        if df.empty:
            st.warning("CSV appears to be empty or invalid.")
            return

        st.write("Preview of uploaded CSV:")
        st.dataframe(df.head())

        if st.button("Process CSV for this course"):
            summary = process_spelling_csv(df=df, course_id=course_id)
            show_upload_summary(summary)


def render_words_lessons_section(course_id: int):
    st.subheader("Words & Lessons Overview")

    lessons = get_lessons_for_course(course_id)
    if not lessons:
        st.info("No lessons found yet. Upload a CSV to create lessons and words.")
        return

    lesson_label_map = {
        f"{l['lesson_id']}: {l['lesson_name']}": l["lesson_id"] for l in lessons
    }

    selected_lesson_label = st.selectbox(
        "Select lesson",
        options=list(lesson_label_map.keys()),
    )
    lesson_id = lesson_label_map[selected_lesson_label]

    lesson_words = get_lesson_words(course_id=course_id, lesson_id=lesson_id)
    if not lesson_words:
        st.info("No words mapped to this lesson yet.")
    else:
        st.write(f"Words in lesson {selected_lesson_label}:")
        st.dataframe(lesson_words)


def main():
    st.set_page_config(
        page_title="Spelling Admin Console (Clean)",
        layout="wide",
    )

    st.title("Spelling Admin Console (Clean Build)")

    selected_course_id = render_course_section()

    if not selected_course_id:
        st.info("Create or select a course to continue.")
        return

    col1, col2 = st.columns([2, 2])

    with col1:
        render_upload_section(selected_course_id)

    with col2:
        render_words_lessons_section(selected_course_id)


if __name__ == "__main__":
    main()
