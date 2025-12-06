import os
import random
import time
import streamlit as st
from sqlalchemy import text

from shared.db import engine, fetch_all
from spelling_app.repository.student_pending_repo import create_pending_registration
from spelling_app.repository.attempt_repo import get_last_attempts, record_attempt




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


###########################################################
#  WORDS FOR PRACTICE
###########################################################

def get_words_for_course(course_id: int, user_id: int | None = None):
    """
    If user_id is None → simple list (no stats, legacy mode).
    If user_id is provided → includes pattern, level, and basic accuracy stats.
    """
    if user_id is None:
        rows = fetch_all(
            """
            SELECT word_id, word, pattern, level
            FROM spelling_words
            WHERE course_id = :cid
            ORDER BY word_id
            """,
            {"cid": course_id},
        )
    else:
        rows = fetch_all(
            """
            SELECT
                w.word_id,
                w.word,
                w.pattern,
                w.level,
                AVG(CASE WHEN a.correct THEN 1.0 ELSE 0.0 END) AS accuracy,
                COUNT(a.attempt_id) AS attempts
            FROM spelling_words w
            LEFT JOIN spelling_attempts a
              ON a.word_id = w.word_id
             AND a.user_id = :uid
            WHERE w.course_id = :cid
            GROUP BY w.word_id, w.word, w.pattern, w.level
            ORDER BY w.word_id
            """,
            {"cid": course_id, "uid": user_id},
        )

    if not rows or isinstance(rows, dict):
        return []

    words = []
    for r in rows:
        m = getattr(r, "_mapping", r)
        words.append(
            {
                "word_id": m.get("word_id"),
                "word": m.get("word"),
                "pattern": m.get("pattern"),
                "level": m.get("level"),
                # These may be None when user_id is None:
                "accuracy": m.get("accuracy"),
                "attempts": m.get("attempts"),
            }
        )
    return words



###########################################################
#  MISSING-LETTER QUESTION LOGIC
###########################################################
def generate_missing_letter_question(word: str, base_blanks: int = 2):
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
    blanks = max(1, min(blanks, 3))  # clamp 1–3

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
    st.title("📘 Select a Course")

    user_id = st.session_state.get("user_id")
    courses = get_student_courses(user_id)

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
#  PRACTICE PAGE — MISSING LETTER MODE (FIXED)
###########################################################
def render_practice_page():
    st.title("✏️ Practice")

    # track time per attempt
    if "start_time" not in st.session_state:
        st.session_state.start_time = time.time()

    course_id = st.session_state.get("selected_course_id")

    if not course_id:
        st.error("No course selected.")
        st.session_state.page = "dashboard"
        st.experimental_rerun()

    # Load words for the selected course
        user_id = st.session_state.get("user_id")
        words = build_session_word_list(user_id, course_id)

        if not words:
            st.warning("No words found for this course.")
            if st.button("Back to Courses"):
                st.session_state.page = "dashboard"
                st.experimental_rerun()
            return

def build_session_word_list(user_id: int, course_id: int):
    """
    Option 3 lite:
      - Uses pattern + accuracy to prioritise words
      - Approximates 70% focus pattern, 20% weak, 10% mastered via scoring
    """
    words = get_words_for_course(course_id, user_id=user_id)
    if not words:
        return []

    # Determine focus pattern = pattern with lowest accuracy (among attempted)
    pattern_stats = {}
    for w in words:
        pattern = w.get("pattern") or "other"
        acc = w.get("accuracy")
        attempts = w.get("attempts") or 0

        if attempts == 0 or acc is None:
            # no data yet → treat as neutral for now
            continue

        if pattern not in pattern_stats:
            pattern_stats[pattern] = {"total_acc": 0.0, "count": 0}

        pattern_stats[pattern]["total_acc"] += float(acc)
        pattern_stats[pattern]["count"] += 1

    if pattern_stats:
        # compute average accuracy per pattern
        avg_acc = {
            p: v["total_acc"] / v["count"] for p, v in pattern_stats.items()
        }
        # focus = lowest accuracy pattern
        focus_pattern = min(avg_acc, key=avg_acc.get)
    else:
        # no stats yet → pick first non-null pattern or default
        focus_pattern = None
        for w in words:
            if w.get("pattern"):
                focus_pattern = w["pattern"]
                break

    # Score words
    scored = []
    for w in words:
        pattern = w.get("pattern") or "other"
        acc = w.get("accuracy")
        attempts = w.get("attempts") or 0

        is_focus = (focus_pattern is not None and pattern == focus_pattern)
        is_weak = (attempts > 0 and acc is not None and float(acc) < 0.7)
        is_mastered = (attempts >= 3 and acc is not None and float(acc) >= 0.9)

        score = 0
        if is_focus:
            score += 3    # push focus pattern near top
        if is_weak:
            score += 2    # weak words get high priority too
        if is_mastered:
            score -= 1    # mastered words drift later

        scored.append((score, w))

    # Sort by score DESC, then word_id ASC
    scored.sort(key=lambda x: (-x[0], x[1]["word_id"] or 0))

    # Return just the word dicts in this new order
    return [w for _, w in scored]


    # Ensure practice_index exists
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

    # Current word
        pattern = current.get("pattern")
    level = current.get("level")

    info_bits = []
    if level is not None:
        info_bits.append(f"Level {level}")
    if pattern:
        info_bits.append(f"Pattern: {pattern}")

    if info_bits:
        st.caption(" • ".join(info_bits))


    # ---- ADAPTIVE DIFFICULTY RULE (Model 2) ----
    last_three = get_last_attempts(st.session_state.user_id, word_id, limit=3)

    base_blanks = 2  # default
    if len(last_three) == 3:
        if all(last_three):
            base_blanks = 3   # increase difficulty
        elif not any(last_three):
            base_blanks = 1   # decrease difficulty
        else:
            base_blanks = 2   # keep normal

    # Generate masked word
    masked, blank_indices = generate_missing_letter_question(current_word, base_blanks)

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
