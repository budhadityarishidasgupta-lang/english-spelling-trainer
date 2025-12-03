import os
import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import date

from shared.db import engine, fetch_all, execute


###########################################################
#  SESSION INIT
###########################################################

SESSION_KEYS = [
    "is_logged_in",
    "user_id",
    "user_name",
    "page",
    "selected_course_id",
    "practice_index",
]


def inject_student_css():
    st.markdown(
        """
        <style>
        body { background-color: #0e1117; }
        .login-card { padding: 20px; background: #111; border-radius: 8px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def initialize_session_state(st):
    for key in SESSION_KEYS:
        if key not in st.session_state:
            if key == "is_logged_in":
                st.session_state[key] = False
            elif key == "user_id":
                st.session_state[key] = 0
            elif key == "user_name":
                st.session_state[key] = "Guest"
            else:
                st.session_state[key] = None


###########################################################
#  AUTHENTICATION
###########################################################

import bcrypt


def check_login(st, email: str, password: str) -> bool:
    sql = text(
        """
        SELECT user_id, name, email, password_hash, is_active
        FROM users
        WHERE email = :e
        """
    )

    with engine.connect() as conn:
        row = conn.execute(sql, {"e": email}).mappings().first()

    if not row:
        return False
    if not row["is_active"]:
        return False

    stored_hash = row["password_hash"]
    if isinstance(stored_hash, str):
        stored_hash = stored_hash.encode()

    if bcrypt.checkpw(password.encode(), stored_hash):
        st.session_state.is_logged_in = True
        st.session_state.user_id = row["user_id"]
        st.session_state.user_name = row["name"]
        st.session_state.page = "dashboard"
        return True

    return False


def logout(st):
    for key in SESSION_KEYS:
        if key in st.session_state:
            del st.session_state[key]
    initialize_session_state(st)


###########################################################
#  STUDENT PORTAL FUNCTIONS
###########################################################

def get_student_courses(user_id: int):
    rows = fetch_all(
        """
        SELECT c.course_id, c.course_name
        FROM spelling_courses c
        JOIN spelling_enrollments e ON e.course_id = c.course_id
        WHERE e.user_id = :uid
        ORDER BY c.course_name
        """,
        {"uid": user_id},
    )

    courses = []
    for r in rows:
        m = getattr(r, "_mapping", r)
        courses.append({
            "course_id": m["course_id"],
            "course_name": m["course_name"]
        })
    return courses


###########################################################
#  WORDS FOR PRACTICE
###########################################################

def get_words_for_course(course_id: int):
    rows = fetch_all(
        """
        SELECT word_id, word
        FROM spelling_words
        WHERE course_id = :cid
        ORDER BY word_id
        """,
        {"cid": course_id},
    )
    words = []
    for r in rows:
        m = getattr(r, "_mapping", r)
        words.append({"word_id": m["word_id"], "word": m["word"]})
    return words


###########################################################
#  LOGIN PAGE
###########################################################

def render_login_page():
    st.title("Welcome to WordSprint!")
    st.markdown("---")

    col_left, _ = st.columns([1, 1])

    with col_left:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        st.subheader("Student Login")

        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Login")

            if submitted:
                if check_login(st, email, password):
                    st.success("Login successful!")
                    st.experimental_rerun()
                else:
                    st.error("Invalid email or password.")

        st.markdown("</div>", unsafe_allow_html=True)


###########################################################
#  DASHBOARD: CHOOSE COURSE
###########################################################

def render_student_dashboard():
    st.title("📘 Select a Course")

    user_id = st.session_state.get("user_id")
    courses = get_student_courses(user_id)

    st.write("DEBUG COURSES:", courses)  # TEMP DEBUG

    if not courses:
        st.warning("No courses assigned to your account yet.")
        return

    course_names = [c["course_name"] for c in courses]

    selected_course_name = st.selectbox("Choose a course:", course_names)

    selected_course = next(c for c in courses if c["course_name"] == selected_course_name)
    st.session_state.selected_course_id = selected_course["course_id"]

    if st.button("Start Practice"):
        st.session_state.page = "practice"
        st.experimental_rerun()


###########################################################
#  PRACTICE PAGE
###########################################################

def render_practice_page():
    st.title("✏️ Practice")

    course_id = st.session_state.get("selected_course_id")

    if not course_id:
        st.error("No course selected.")
        st.session_state.page = "dashboard"
        st.experimental_rerun()

    words = get_words_for_course(course_id)

    if not words:
        st.warning("No words found for this course.")
        if st.button("Back to Courses"):
            st.session_state.page = "dashboard"
            st.experimental_rerun()
        return

# Ensure practice index always exists and is integer
    if "practice_index" not in st.session_state or st.session_state.practice_index is None:
        st.session_state.practice_index = 0

    index = int(st.session_state.practice_index)

    if index >= len(words):
        st.success("🎉 You finished all words!")
        if st.button("Back to Courses"):
            st.session_state.practice_index = 0
            st.session_state.page = "dashboard"
            st.experimental_rerun()
        return

    current_word = words[index]["word"]

    st.subheader(f"Word {index + 1} of {len(words)}")

    with st.form("practice_form"):
        answer = st.text_input("Type the word:")
        submitted = st.form_submit_button("Submit")

    if submitted:
        if answer.strip().lower() == current_word.lower():
            st.success("Correct! 🎉")
        else:
            st.error(f"Incorrect ❌ — Correct word: **{current_word}**")

        if st.button("Next"):
            st.session_state.practice_index += 1
            st.experimental_rerun()

    if st.sidebar.button("Back to Courses"):
        st.session_state.practice_index = 0
        st.session_state.page = "dashboard"
        st.experimental_rerun()


###########################################################
#  MAIN APP CONTROLLER
###########################################################

def main():
    inject_student_css()
    initialize_session_state(st)

    if not st.session_state.is_logged_in:
        render_login_page()
        return

    st.sidebar.write(f"Logged in as: {st.session_state.user_name}")
    if st.sidebar.button("Logout"):
        logout(st)
        st.experimental_rerun()

    page = st.session_state.get("page", "dashboard")

    if page == "dashboard":
        render_student_dashboard()
    elif page == "practice":
        render_practice_page()


if __name__ == "__main__":
    main()
