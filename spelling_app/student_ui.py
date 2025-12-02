import os
import streamlit as st
import pandas as pd
from spelling_app.services.help_service import get_help_text
from spelling_app.repository.registration_repo import create_pending_registration
from spelling_app.services.student_service import (
    initialize_session_state,
    check_login,
    logout,
    get_available_courses,
    get_dashboard_data,
)
from shared.db import fetch_all
from spelling_app.services.enrollment_service import get_courses_for_student
from spelling_app.repository.student_repo import get_course_progress_detailed
from spelling_app.utils.ui_components import render_badge, render_stat_card, render_streak_bar

# --- Load Student CSS safely ---
css_path = os.path.join("spelling_app", "styles", "student.css")

if os.path.exists(css_path):
    with open(css_path, "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
else:
    st.error("Could not find student.css. UI will be unstyled.")

# --- Main Application Flow ---

def render_spelling_student_page():
    """
    Main entry point for the student application.
    Handles CSS injection, session state, and routing between login and main app.
    """
    initialize_session_state(st)

    if not st.session_state.is_logged_in:
        render_login_page()
    else:
        if "page" not in st.session_state:
            st.session_state.page = "Course Selection"

        page = st.session_state.page

        ##############################################
        # COURSE SELECTION PAGE
        ##############################################
        if page == "Course Selection":

            st.title("Course Selection")

            courses = get_courses_for_student(st.session_state.user_id)

            if not courses:
                st.warning("You are not enrolled in any courses.")
                return

            course_map = {c["title"]: c["course_id"] for c in courses}

            selected_course_title = st.selectbox(
                "Select a course to practice:",
                list(course_map.keys())
            )

            # When user clicks Start Practice
            if st.button("Start Practice"):
                st.session_state.selected_course_id = course_map[selected_course_title]
                st.session_state.page = "Spelling Practice"
                st.experimental_rerun()

        else:
            render_main_student_app()

# --- Login/Registration Page (Patch 3E) ---

def render_login_page():
    st.title("Welcome to WordSprint!")
    st.markdown("---")

    col_left, col_right = st.columns([1, 2])

    # LEFT: Login Card
    with col_left:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        st.subheader("Student Login")
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Login")

            if submitted:
                if check_login(st, email, password):
                    st.success("Login successful! Redirecting...")
                    st.experimental_rerun()
                else:
                    st.error("Invalid email or password.")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("---")
        st.subheader("New Student Registration")
        with st.form("registration_form"):
            st.markdown(get_help_text("spelling_registration"))
            student_name = st.text_input("Student Name", key="reg_name")
            parent_email = st.text_input("Parent Email", key="reg_email")
            submitted = st.form_submit_button("Submit Registration")

            if submitted and student_name and parent_email:
                create_pending_registration(student_name, parent_email)
                st.success("Thank you! Your registration details have been recorded. The teacher will contact you after verifying the payment.")
            elif submitted:
                st.error("Please fill in all fields.")

    # RIGHT: Intro and Instructions
    with col_right:
        st.markdown(get_help_text("spelling_intro"))
        st.markdown("---")
        st.markdown("### Instructions")
        st.markdown(get_help_text("spelling_instructions"))
        st.markdown("---")
        st.markdown("### Payment Details")
        st.markdown(get_help_text("spelling_paypal"))

# --- Main App (Dashboard and Practice) ---

def render_main_student_app():
    # Sidebar for navigation (Patch 3F - Collapsible Sidebar)
    st.sidebar.title(f"Welcome, {st.session_state.user_name}!")
    
    if st.sidebar.button("Logout"):
        logout(st)
        st.experimental_rerun()

    page = st.sidebar.radio("Navigation", ["Dashboard", "Spelling Practice"], key="page")

    ##############################################
    # STUDENT DASHBOARD (Simplified)
    ##############################################
    if page == "Dashboard":
        st.title("Dashboard")

        user_id = st.session_state.get("user_id")

        # --- Count assigned courses ---
        course_rows = fetch_all(
            """
            SELECT c.course_id, c.title
            FROM enrollments e
            JOIN courses c ON c.course_id = e.course_id
            WHERE e.user_id = :uid
            """,
            {"uid": user_id}
        )

        if hasattr(course_rows, "all"):
            course_rows = [dict(r._mapping) for r in course_rows.all()]
        else:
            course_rows = [dict(r._mapping) for r in course_rows]

        # --- Count total words across assigned courses ---
        word_rows = fetch_all(
            """
            SELECT COUNT(*) 
            FROM spelling_words
            WHERE course_id IN (
                SELECT course_id FROM enrollments WHERE user_id = :uid
            )
            """,
            {"uid": user_id}
        )

        if hasattr(word_rows, "all"):
            total_words = word_rows.all()[0][0]
        else:
            total_words = word_rows[0][0]

        # --- Count attempts made by user ---
        attempt_rows = fetch_all(
            """
            SELECT COUNT(*) 
            FROM attempts
            WHERE user_id = :uid
            """,
            {"uid": user_id}
        )

        if hasattr(attempt_rows, "all"):
            total_attempts = attempt_rows.all()[0][0]
        else:
            total_attempts = attempt_rows[0][0]

        # --- UI ---
        st.subheader("Your Learning Summary")

        st.metric("Assigned Courses", len(course_rows))
        st.metric("Total Words Available", total_words)
        st.metric("Words Practiced (attempts)", total_attempts)

        if course_rows:
            st.write("### Your Courses:")
            st.write(pd.DataFrame(course_rows))
        else:
            st.warning("You are not assigned to any courses yet.")

    ##############################################
    # SPELLING PRACTICE PAGE
    ##############################################
    elif page == "Spelling Practice":

        st.title("Spelling Practice")

        # Ensure course is selected
        course_id = st.session_state.get("selected_course_id")
        if not course_id:
            st.error("Please select a course first.")
            return

        # Load all words for this course
        words = fetch_all(
            """
            SELECT word, pattern, pattern_code
            FROM spelling_words
            WHERE course_id = :cid
            ORDER BY word_id ASC
            """,
            {"cid": course_id}
        )

        # Normalize DB rows
        if hasattr(words, "all"):
            words = [dict(r._mapping) for r in words.all()]
        else:
            words = [dict(r._mapping) for r in words]

        if not words:
            st.warning("No words found for this course.")
            return

        # Initialize session state
        if "practice_index" not in st.session_state:
            st.session_state.practice_index = 0

        index = st.session_state.practice_index

        # If finished
        if index >= len(words):
            st.success("🎉 You have completed all words in this course!")
            if st.button("Restart Course"):
                st.session_state.practice_index = 0
                st.experimental_rerun()
            return

        # Get current word
        current = words[index]
        pattern = current["pattern"]
        correct_word = current["word"]

        # Display pattern
        st.subheader(f"Pattern: {pattern}")

        st.write("Type the correct spelling for this word pattern:")

        # User input
        user_input = st.text_input("Your spelling:", key=f"spell_{index}")

        if st.button("Submit Answer"):
            if user_input.strip().lower() == correct_word.lower():
                st.success("Correct! 🎉")
                st.session_state.practice_index += 1
                st.experimental_rerun()
            else:
                st.error("Incorrect. Try again!")

# --- Dashboard (Patch 3G, 3H) ---

def render_dashboard():
    st.title("Student Dashboard")
    st.markdown("---")

    user_id = st.session_state.user_id
    dashboard_data = get_dashboard_data(user_id)

    # 1. Streak Bar
    render_streak_bar(dashboard_data.get("current_streak", 0))

    # 2. Stats Row
    col1, col2, col3 = st.columns(3)
    with col1:
        render_stat_card("Total Attempts", dashboard_data.get("total_attempts", 0), help_text="Total number of words you have attempted.")
    with col2:
        render_stat_card("Accuracy", f"{dashboard_data.get('accuracy', 0):.2f}%", help_text="Percentage of correct attempts.")
    with col3:
        render_stat_card("Mastered Words", dashboard_data.get("mastered_words", 0), help_text="Words spelled correctly 3 times in a row.")

    st.markdown("---")
    st.subheader("Your Badges")
    
    # 3. Badges
    if dashboard_data.get("badges"):
        cols = st.columns(len(dashboard_data["badges"]))
        for i, badge in enumerate(dashboard_data["badges"]):
            with cols[i]:
                render_badge(badge["emoji"], badge["text"])
    else:
        st.info("Keep practicing to earn your first badge!")

    st.markdown("---")
    st.subheader("Your Courses & Progress")

    courses = get_available_courses(user_id)
    if not courses:
        st.warning("You are not enrolled in any spelling courses.")
        return

    for course in courses:
        course_progress_data = get_course_progress_detailed(user_id, course["course_id"])
        progress = course_progress_data.get("progress", 0)
        st.metric(f"{course['title']} Progress", f"{progress:.2f}%")
