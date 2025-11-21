import streamlit as st
from shared.db import engine, fetch_all, execute
from spelling_app.student_ui import render_spelling_student
from spelling_app.admin_ui import render_spelling_admin

# Load custom CSS theme
def load_css():
    try:
        with open("static/theme.css", "r") as f:
            css = f"<style>{f.read()}</style>"
            st.markdown(css, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Could not load CSS: {e}")

def main():
    load_css()
    st.sidebar.title("Spelling Trainer")

    mode = st.sidebar.radio("Select mode", ["Student", "Admin"])

    if mode == "Student":
        render_spelling_student()
    else:
        render_spelling_admin()

if __name__ == "__main__":
    main()
