import sys, os
import streamlit as st

block_path = os.path.join(os.getcwd(), "synonym_legacy")
if block_path in sys.path:
    sys.path.remove(block_path)

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
