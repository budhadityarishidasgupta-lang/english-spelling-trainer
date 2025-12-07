# --- Force load .env from project root ---
import os
from dotenv import load_dotenv

ROOT_ENV = "/workspaces/english-spelling-trainer/.env"
load_dotenv(ROOT_ENV)
print("Loaded DB:", os.getenv("DATABASE_URL"))


# --- Fix PYTHONPATH so "shared" and "spelling_app" can be imported ---
import sys
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
# ---------------------------------------------------------------------


import os
import random
import time
import streamlit as st
from sqlalchemy import text

from dotenv import load_dotenv
load_dotenv()


from shared.db import engine, fetch_all
from spelling_app.repository.student_pending_repo import create_pending_registration
from spelling_app.repository.attempt_repo import record_attempt




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

SESSION_KEYS.extend([
    "selected_level",
    "selected_lesson",
    "selected_lesson_pattern_code",
])


def inject_student_css():
    st.markdown(
        """
        <style>
        body { background-color: #0e1117; }
        .login-card {
            padding: 20px;
            background: #111;
            border-radius: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def initialize_session_state(st_module):
    for key in SESSION_KEYS:
        if key not in st_module.session_state:
            if key == "is_logged_in":
                st_module.session_state[key] = False
            elif key == "user_id":
                st_module.session_state[key] = 0
            elif key == "user_name":
                st_module.session_state[key] = "Guest"
            else:
                st_module.session_state[key] = None


###########################################################
#  AUTHENTICATION
###########################################################

import bcrypt


def check_login(st_module, email: str, password: str) -> bool:
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
        st_module.session_state.is_logged_in = True
        st_module.session_state.user_id = row["user_id"]
        st_module.session_state.user_name = row["name"]
        st_module.session_state.page = "dashboard"
        return True

    return False


def logout(st_module):
    for key in SESSION_KEYS:
        if key in st_module.session_state:
            del st_module.session_state[key]
    initialize_session_state(st_module)


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

    if isinstance(rows, dict) or not rows:
        return []

    courses = []
    for r in rows:
        m = getattr(r, "_mapping", r)
        courses.append(
            {
                "course_id": m["course_id"],
                "course_name": m["course_name"],
            }
        )
    return courses


def get_lessons_for_course(course_id):
    """
    Returns distinct levels and lesson names for left menu.
    """
    rows = fetch_all(
        """
        SELECT DISTINCT pattern_code, pattern, level, lesson_name
        FROM spelling_words
        WHERE course_id = :cid
        ORDER BY level, pattern_code
        """,
        {"cid": course_id},
    )
    out = []
    for r in rows:
        m = getattr(r, "_mapping", r)
        out.append(
            {
                "pattern_code": m["pattern_code"],
                "pattern": m["pattern"],
                "level": m["level"],
                "lesson_name": m["lesson_name"],
            }
        )
    return out


def get_words_for_lesson(course_id, pattern_code):
    rows = fetch_all(
        """
        SELECT word_id, word, pattern, pattern_code, level, lesson_name
        FROM spelling_words
        WHERE course_id = :cid
        AND pattern_code = :pc
        ORDER BY word_id
        """,
        {"cid": course_id, "pc": pattern_code},
    )
    out = []
    for r in rows:
        m = getattr(r, "_mapping", r)
        out.append({
            "word_id": m["word_id"],
            "word": m["word"],
            "pattern": m.get("pattern"),
            "pattern_code": m.get("pattern_code"),
            "level": m.get("level"),
            "lesson_name": m.get("lesson_name"),
        })
    return out



###########################################################
#  WORDS FOR PRACTICE
###########################################################


def sort_words(words):
    # later we can plug in real stats; for now just use level + pattern_code + word
    return sorted(
        words,
        key=lambda w: (
            w.get("level") or 0,
            w.get("pattern_code") or 0,
            w["word"],
        ),
    )



###########################################################
#  MISSING-LETTER QUESTION LOGIC
###########################################################


def generate_question(word: str, pattern: str):
    # simple rule-based version
    p = (pattern or "").lower()
    if "gh" in p or "ph" in p:
        return generate_missing_letter_question(word, max_blanks=2)
    if "tion" in p or "sion" in p or "ssion" in p:
        return generate_missing_letter_question(word, max_blanks=3)
    if "dge" in p:
        return generate_missing_letter_question(word, max_blanks=1)
    # default
    return generate_missing_letter_question(word)


def generate_missing_letter_question(word: str, base_blanks: int = 2, max_blanks: int | None = None):
    """
    Returns masked_word, blank_indices.
    Example:
        word = chemist
        masked = ch_m_st
        blank_indices = [2, 4]
    """

    if not word:
        return word, []

    word = word.strip()
    length = len(word)

    # default blanks from word length
    blanks = base_blanks
    clamp_max = max_blanks if max_blanks is not None else 3
    blanks = max(1, min(blanks, clamp_max))  # clamp 1–max

    # pick stable random indices using a seed based on the word
    rng = random.Random(hash(word) % (2**32))
    indices = rng.sample(range(length), blanks)

    chars = []
    for i, ch in enumerate(word):
        if i in indices:
            chars.append("_")
        else:
            chars.append(ch)

    masked_display = "".join(chars)  # VERY IMPORTANT (no spaces)
    return masked_display, indices



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
#  NEW REGISTRATION PAGE
###########################################################

def render_registration_page():
    st.header("New Student Registration")

    st.write("Enter your details below. An admin will approve your account shortly.")

    name = st.text_input("Full name")
    email = st.text_input("Email address")

    if st.button("Submit registration"):
        if not name.strip() or not email.strip():
            st.error("Both name and email are required.")
            return

        result = create_pending_registration(name.strip(), email.strip())

        if isinstance(result, dict) and result.get("error"):
            st.error(result["error"])
        else:
            st.success(
                "Registration submitted! "
                "Once approved, you can log in using the default password: Learn123!"
            )


###########################################################
#  DASHBOARD: CHOOSE COURSE
###########################################################

def render_student_dashboard():
    st.title("📘 My Courses")

    user_id = st.session_state.get("user_id")
    courses = get_student_courses(user_id)

    if not courses:
        st.warning("No courses assigned yet.")
        return

    # Let student choose a course
    course_names = [c["course_name"] for c in courses]
    selected_course_name = st.selectbox("Choose a course:", course_names)

    selected_course = next(c for c in courses if c["course_name"] == selected_course_name)
    st.session_state.selected_course_id = selected_course["course_id"]
    st.session_state.selected_level = None
    st.session_state.selected_lesson = None
    st.session_state.selected_lesson_pattern_code = None
    st.session_state.practice_index = 0

    st.info("Select a lesson from the left sidebar to begin.")


def render_sidebar_navigation():
    st.sidebar.title("📚 Lessons")

    cid = st.session_state.get("selected_course_id")
    if not cid:
        st.sidebar.info("Select a course first.")
        return

    lessons = get_lessons_for_course(cid)
    if not lessons:
        st.sidebar.warning("No lessons found.")
        return

    levels = sorted(set(int(l["level"]) for l in lessons if l["level"] is not None))


    for lvl in levels:
        st.sidebar.markdown(f"### ⭐ Level {lvl}")

        lvl_lessons = [l for l in lessons if l["level"] == lvl]
        for lesson in lvl_lessons:
            pattern_code = lesson["pattern_code"]
            label = f"{lesson['lesson_name']} ({lesson.get('pattern','')})"


            if st.sidebar.button(label, key=f"lesson_{pattern_code}"):
                st.session_state.selected_level = lvl
                st.session_state.selected_lesson = lesson["lesson_name"]
                st.session_state.selected_lesson_pattern_code = pattern_code
                st.session_state.practice_index = 0
                st.session_state.start_time = time.time()
                st.session_state.page = "practice"
                st.experimental_rerun()


###########################################################
#  PRACTICE PAGE — MISSING LETTER MODE (FIXED)
###########################################################
def render_practice_page():
    st.title("✏️ Practice")

    cid = st.session_state.get("selected_course_id")
    pc = st.session_state.get("selected_lesson_pattern_code")
    lesson_name = st.session_state.get("selected_lesson")

    if not cid or not pc:
        st.error("No lesson selected. Choose from the left panel.")
        st.session_state.page = "dashboard"
        st.experimental_rerun()
        return

    st.markdown(f"### Lesson: **{lesson_name}**")

    words = get_words_for_lesson(cid, pc)
    if not words:
        st.warning("No words found for this lesson.")
        return

    # track time per attempt
    if "start_time" not in st.session_state:
        st.session_state.start_time = time.time()

    if "practice_index" not in st.session_state or st.session_state.practice_index is None:
        st.session_state.practice_index = 0

    index = int(st.session_state.practice_index)

    # Completed all words
    if index >= len(words):
        st.success("🎉 You finished all words!")
        if st.button("Back to Courses"):
            st.session_state.practice_index = 0
            st.session_state.page = "dashboard"
            st.experimental_rerun()
        return

    current = words[index]
    current_word = current["word"]
    word_id = current.get("word_id")
    pattern = current.get("pattern") or ""
    level = current.get("level")

    info_bits = []
    if level is not None:
        info_bits.append(f"Level {level}")
    if pattern:
        info_bits.append(f"Pattern: {pattern}")

    if info_bits:
        st.caption(" • ".join(info_bits))


    masked, blank_indices = generate_question(current_word, pattern)

    st.markdown("**Fill in the missing letters:**")
    st.markdown(f"### {masked}")

    # ---------------- FORM ----------------
    blanks_inputs = []
    with st.form("practice_form"):
        for i, pos in enumerate(blank_indices):
            correct_letter = current_word[pos]
            key = f"blank_{index}_{i}"
            user_letter = st.text_input(
                f"Letter for blank #{i + 1}",
                max_chars=1,
                key=key,
            )
            blanks_inputs.append((pos, correct_letter, user_letter))

        submitted = st.form_submit_button("Check")
    # --------------------------------------

    # ---------------- PROCESS CHECK ----------------
    if submitted:
        st.session_state["checked"] = True

        wrong_letters = 0
        all_correct = True

        for _, correct_letter, user_letter in blanks_inputs:
            user_val = (user_letter or "").strip().lower()
            correct_val = (correct_letter or "").strip().lower()

            if user_val != correct_val:
                all_correct = False
                wrong_letters += 1


        st.session_state["correct"] = all_correct

        # ---- record attempt ----
        time_taken = int(time.time() - st.session_state.start_time)
        record_attempt(
            user_id=st.session_state.user_id,
            word_id=word_id,
            correct=all_correct,
            time_taken=time_taken,
            blanks_count=len(blank_indices),
            wrong_letters_count=wrong_letters,
        )

    # ---------------- FEEDBACK + NEXT ----------------
    if st.session_state.get("checked", False):

        if st.session_state.get("correct", False):
            st.success("✅ All letters correct! 🎉")
        else:
            st.error(f"❌ Incorrect. The word is **{current_word}**")

        if st.button("Next →"):
            # Move to next word
            st.session_state.practice_index += 1

            # Reset state flags
            st.session_state["checked"] = False
            st.session_state["correct"] = False

            # Reset timer
            st.session_state.start_time = time.time()

            # Clean inputs
            for i in range(len(blank_indices)):
                st.session_state.pop(f"blank_{index}_{i}", None)

            st.experimental_rerun()

    # Sidebar navigation
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

    if st.session_state.is_logged_in:
        render_sidebar_navigation()

    # NOT LOGGED IN → show Login + Registration tabs
    if not st.session_state.is_logged_in:
        tab_login, tab_register = st.tabs(["Login", "New Registration"])

        with tab_login:
            render_login_page()

        with tab_register:
            render_registration_page()

        return  # stop here when logged out

    # LOGGED IN
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
