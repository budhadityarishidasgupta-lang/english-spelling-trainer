import streamlit as st
from spelling_app.services.help_service import get_help_text
from spelling_app.repository.registration_repo import create_pending_registration
from spelling_app.services.student_service import (
    initialize_session_state,
    check_login,
    logout,
    get_available_courses,
    get_available_lessons,
    start_lesson,
    get_current_word,
    submit_spelling_attempt,
    get_dashboard_data,
)
from spelling_app.repository.student_repo import get_lesson_progress_detailed, get_course_progress_detailed
from spelling_app.utils.ui_components import (
    inject_css,
    render_badge,
    render_stat_card,
    render_streak_bar,
    render_course_card,
    render_lesson_card_html,
    render_lesson_card_button,
)

# --- Main Application Flow ---

def render_spelling_student_page():
    """
    Main entry point for the student application.
    Handles CSS injection, session state, and routing between login and main app.
    """
    inject_css()
    initialize_session_state(st)

    if not st.session_state.is_logged_in:
        render_login_page()
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

    page = st.sidebar.radio("Navigation", ["Dashboard", "Spelling Practice"], key="main_nav")

    if page == "Dashboard":
        render_dashboard()
    elif page == "Spelling Practice":
        render_spelling_practice()

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
    
    # 4. Course Cards
    courses = get_available_courses(user_id)
    if not courses:
        st.warning("You are not enrolled in any spelling courses.")
        return

    for course in courses:
        course_progress_data = get_course_progress_detailed(user_id, course["course_id"])
        course_progress = course_progress_data.get("progress", 0)
        
        lessons = get_available_lessons(course["course_id"], user_id)
        
        lessons_html = ""
        for lesson in lessons:
            lesson_progress_data = get_lesson_progress_detailed(user_id, lesson["lesson_id"])
            mastered = lesson_progress_data.get("mastered_words", 0)
            total = lesson_progress_data.get("total_words", 0)
            
            # Generate HTML for the lesson card
            lessons_html += render_lesson_card_html(lesson, mastered, total, f"course_{course['course_id']}")
            
            # Render the hidden Streamlit button for the lesson card
            render_lesson_card_button(
                lesson, 
                f"course_{course['course_id']}", 
                lambda lesson_id: start_lesson(st, lesson_id)
            )

        render_course_card(course, course_progress, lessons_html)

# --- Spelling Practice Engine ---

def render_spelling_practice():
    st.title("Spelling Practice")
    st.markdown("---")

    if st.session_state.current_lesson is None:
        render_lesson_selection()
    else:
        render_active_practice()

def render_lesson_selection():
    st.subheader("Select a Lesson to Begin")
    
    user_id = st.session_state.user_id
    courses = get_available_courses(user_id)
    if not courses:
        st.warning("You are not enrolled in any spelling courses.")
        return

    course_titles = [c["title"] for c in courses]
    selected_course_title = st.selectbox("Choose Course", course_titles, key="lesson_select_course")
    
    selected_course = next(c for c in courses if c["title"] == selected_course_title)
    
    lessons = get_available_lessons(selected_course["course_id"], user_id)
    if not lessons:
        st.info("No lessons available for this course.")
        return

    lesson_names = [l["lesson_name"] for l in lessons]
    selected_lesson_name = st.selectbox("Choose Lesson", lesson_names, key="lesson_select_lesson")
    
    selected_lesson = next(l for l in lessons if l["lesson_name"] == selected_lesson_name)

    if st.button("Start Practice"):
        if start_lesson(st, selected_lesson["lesson_id"]):
            st.experimental_rerun()
        else:
            st.error("This lesson has no words. Please choose another.")

def render_active_practice():
    word_data = get_current_word(st)
    
    if word_data is None:
        st.success("Congratulations! You have completed all words in this lesson.")
        if st.button("Choose Another Lesson"):
            st.session_state.current_lesson = None
            st.session_state.word_list = None
            st.session_state.current_word_index = 0
            st.experimental_rerun()
        return

    # Progress bar based on word index
    st.progress(
        st.session_state.current_word_index / len(st.session_state.word_list), 
        text=f"Word {st.session_state.current_word_index + 1} of {len(st.session_state.word_list)}"
    )

    st.markdown(f'<div class="word-prompt">{word_data["word"]}</div>', unsafe_allow_html=True)
    st.markdown("---")

    with st.form("spelling_attempt_form"):
        attempt = st.text_input("Type the word here", key="attempt_input")
        submitted = st.form_submit_button("Check Spelling")

        if submitted:
            if submit_spelling_attempt(st, attempt):
                st.markdown('<div class="feedback-correct">Correct! Moving to the next word.</div>', unsafe_allow_html=True)
                st.experimental_rerun()
            else:
                st.markdown(f'<div class="feedback-incorrect">Incorrect. The correct spelling is: **{word_data["word"]}**</div>', unsafe_allow_html=True)
                st.warning("Try again!")
