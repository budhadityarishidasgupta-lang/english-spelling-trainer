import streamlit as st

from spelling_app.student_ui import render_spelling_student_page


def main():
    # Keep layout consistent with the main app
    st.set_page_config(
        page_title="WordSprint – Spelling Student",
        layout="wide",
    )
    render_spelling_student_page()


if __name__ == "__main__":
    main()
