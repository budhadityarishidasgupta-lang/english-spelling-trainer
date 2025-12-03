import streamlit as st
import bcrypt
from sqlalchemy import text
from shared.db import fetch_all, execute


st.set_page_config(
    page_title="WordSprint Spelling (Clean)",
    layout="wide",
)

# -------- Session helpers --------
def init_session():
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "user_name" not in st.session_state:
        st.session_state.user_name = None
    if "role" not in st.session_state:
        st.session_state.role = "student"
    if "is_logged_in" not in st.session_state:
        st.session_state.is_logged_in = False


# -------- DB / auth helpers --------
def get_user_by_email(email: str):
    rows = fetch_all(
        """
        SELECT user_id, name, email, password_hash, is_active
        FROM users
        WHERE email = :e
        """,
        {"e": email},
    )
    if not rows:
        return None

    row = rows[0]
    mapping = getattr(row, "_mapping", row)
    return mapping


def login(email: str, password: str) -> bool:
    user = get_user_by_email(email)
    if not user:
        return False
    if not user["is_active"]:
        return False

    stored_hash = user["password_hash"]
    if isinstance(stored_hash, str):
        stored_hash = stored_hash.encode()

    if bcrypt.checkpw(password.encode(), stored_hash):
        st.session_state.user_id = user["user_id"]
        st.session_state.user_name = user["name"]
        st.session_state.is_logged_in = True
        return True
    return False


def logout():
    st.session_state.user_id = None
    st.session_state.user_name = None
    st.session_state.is_logged_in = False


# -------- UI: login + simple dashboard --------
def render_login_page():
    st.title("Student Login (Clean)")
    with st.form("login_form_clean"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            email = email.strip()
            if login(email, password):
                st.success("Login successful!")
                st.experimental_rerun()
            else:
                st.error("Invalid email or password.")


def get_student_courses(user_id: int):
    rows = fetch_all(
        """
        SELECT c.course_id, c.course_name
        FROM spelling_courses c
        JOIN spelling_enrollments e ON c.course_id = e.course_id
        WHERE e.user_id = :uid
        ORDER BY c.course_name
        """,
        {"uid": user_id},
    )
    if not rows:
        return []

    courses = []
    for r in rows:
        m = getattr(r, "_mapping", r)
        courses.append({"course_id": m["course_id"], "course_name": m["course_name"]})
    return courses

def get_lessons_for_course(course_id: int):
    rows = fetch_all(
        """
        SELECT lesson_id, lesson_name, sort_order
        FROM spelling_lessons
        WHERE course_id = :cid
        ORDER BY sort_order, lesson_name
        """,
        {"cid": course_id},
    )

    lessons = []
    for r in rows:
        m = getattr(r, "_mapping", r)
        lessons.append({
            "lesson_id": m["lesson_id"],
            "lesson_name": m["lesson_name"]
        })
    return lessons

def render_lessons_page():
    st.title("📘 Select a Lesson")

    course_id = st.session_state.get("selected_course_id")
    if not course_id:
        st.error("No course selected.")
        st.session_state.page = "dashboard"
        st.experimental_rerun()

    lessons = get_lessons_for_course(course_id)

    if not lessons:
        st.warning("No lessons found for this course yet.")
        return

    lesson_names = [l["lesson_name"] for l in lessons]
    selected_lesson_name = st.selectbox("Choose your lesson:", lesson_names)

    selected_lesson = next(l for l in lessons if l["lesson_name"] == selected_lesson_name)
    st.session_state.selected_lesson_id = selected_lesson["lesson_id"]

    st.success(f"Selected: {selected_lesson_name}")

    if st.button("Start Practice"):
        st.session_state.page = "practice"
        st.experimental_rerun()

    if st.sidebar.button("Back to Courses"):
        st.session_state.page = "dashboard"
        st.experimental_rerun()

def get_words_for_lesson(lesson_id: int):
    rows = fetch_all(
        """
        SELECT word_id, word
        FROM spelling_words
        WHERE lesson_id = :lid
        ORDER BY word_id
        """,
        {"lid": lesson_id},
    )

    words = []
    for r in rows:
        m = getattr(r, "_mapping", r)
        words.append({
            "word_id": m["word_id"],
            "word": m["word"]
        })
    return words


def render_practice_page():
    st.title("✏️ Practice")

    lesson_id = st.session_state.get("selected_lesson_id")
    if not lesson_id:
        st.error("No lesson selected.")
        st.session_state.page = "lessons"
        st.experimental_rerun()

    # Load words
    words = get_words_for_lesson(lesson_id)

    if not words:
        st.warning("No words found for this lesson.")
        return

    # Initialize a pointer to which word you are on
    if "practice_index" not in st.session_state:
        st.session_state.practice_index = 0

    index = st.session_state.practice_index
    if index >= len(words):
        st.success("🎉 You finished all words in this lesson!")
        if st.button("Back to lessons"):
            st.session_state.page = "lessons"
            st.session_state.practice_index = 0
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
        st.error(f"Incorrect ❌ — The correct word is: **{current_word}**")

    if st.button("Next"):
        st.session_state.practice_index += 1
        st.experimental_rerun()


    # Back button
    if st.sidebar.button("Back to Lessons"):
        st.session_state.page = "lessons"
        st.session_state.practice_index = 0
        st.experimental_rerun()


def render_student_dashboard():
    st.title("📘 Spelling Student Dashboard")
    st.write(f"Logged in as **{st.session_state.user_name}**")

    # ---------- GET COURSES ----------
    user_id = st.session_state.user_id
    courses = get_student_courses(user_id)

    if not courses:
        st.warning("No courses assigned to your account yet. Please contact your teacher.")
        return

    # ---------- SELECT COURSE ----------
    course_names = [c["course_name"] for c in courses]
    selected_name = st.selectbox("Select your course:", course_names)

    # store selected course
    selected_course = next(c for c in courses if c["course_name"] == selected_name)
    st.session_state.selected_course_id = selected_course["course_id"]

    st.success(f"Selected course: {selected_name}")

    if st.button("Go to Lessons"):
        st.session_state.page = "lessons"
        st.experimental_rerun()

    # Logout button
    if st.sidebar.button("Logout"):
        logout()
        st.experimental_rerun()


def admin_reset_password_panel():
    st.sidebar.markdown("### 🔧 Admin: Reset Password (temporary)")
    email = st.sidebar.text_input("Student email for reset", key="reset_email")
    new_pw = st.sidebar.text_input("New password", type="password", key="reset_pw")
    if st.sidebar.button("Reset password now"):
        if not email or not new_pw:
            st.sidebar.error("Please enter both email and new password.")
            return
        pw_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
        execute(
            "UPDATE users SET password_hash = :ph WHERE email = :e",
            {"ph": pw_hash, "e": email},
        )
        st.sidebar.success(f"Password reset for {email}")

def main():
    init_session()

    admin_reset_password_panel()

    if not st.session_state.is_logged_in:
        render_login_page()
        return

    # PAGE ROUTING
    if "page" not in st.session_state:
        st.session_state.page = "dashboard"

    if st.session_state.page == "dashboard":
        render_student_dashboard()
    elif st.session_state.page == "lessons":
        render_lessons_page()
    elif st.session_state.page == "practice":
        render_practice_page()


if __name__ == "__main__":
    main()
