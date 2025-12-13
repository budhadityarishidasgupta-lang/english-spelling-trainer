#!/usr/bin/env python3
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

import time
import random
import streamlit as st
from datetime import datetime, date, timedelta
from sqlalchemy import text

from dotenv import load_dotenv
load_dotenv()

# ---- CORRECT IMPORTS (FINAL) ----
from shared.db import engine, execute, fetch_all, safe_rows
from spelling_app.repository.student_pending_repo import create_pending_registration
from spelling_app.repository.attempt_repo import record_attempt
from spelling_app.repository.attempt_repo import get_lesson_mastery   # <-- REQUIRED FIX
from spelling_app.repository.attempt_repo import get_word_difficulty_signals





def render_masked_word_input(masked_word, correct_word, key_prefix, blank_indices):
    chars = list(masked_word)
    input_state_key = f"{key_prefix}_letters"
    active_index_key = f"{key_prefix}_active_index"

    if input_state_key not in st.session_state:
        initial_letters = []
        for idx, ch in enumerate(chars):
            if ch == "_":
                initial_letters.append("")
            else:
                initial_letters.append(ch)
        st.session_state[input_state_key] = initial_letters

    if active_index_key not in st.session_state:
        st.session_state[active_index_key] = min(blank_indices) if blank_indices else 0

    def set_active_index(new_index: int):
        st.session_state[active_index_key] = new_index

    def update_ready_flag(letters_snapshot):
        if all((letters_snapshot[i] or "") for i in blank_indices):
            st.session_state[f"{key_prefix}_ready_to_submit"] = True

    def on_letter_change(idx: int):
        field_key = f"{key_prefix}_{idx}"
        letters = list(st.session_state.get(input_state_key, []))
        prev_val = letters[idx]
        new_val = (st.session_state.get(field_key) or "").strip()[:1]
        letters[idx] = new_val
        st.session_state[input_state_key] = letters

        if prev_val and not new_val:
            previous_blanks = [b for b in blank_indices if b < idx]
            if previous_blanks:
                set_active_index(max(previous_blanks))
        elif new_val:
            next_blanks = [b for b in blank_indices if b > idx]
            if next_blanks:
                set_active_index(min(next_blanks))
        update_ready_flag(letters)

    letters = st.session_state.get(input_state_key, list(chars))
    cols = st.columns(len(chars))

    for i, ch in enumerate(chars):
        with cols[i]:
            if ch == "_":
                field_key = f"{key_prefix}_{i}"
                if field_key not in st.session_state:
                    st.session_state[field_key] = letters[i]
                val = st.text_input(
                    "",
                    max_chars=1,
                    key=field_key,
                    label_visibility="collapsed",
                    on_change=on_letter_change,
                    args=(i,),
                )
                letters[i] = val.lower() if val else ""
            else:
                st.markdown(
                    f"<div style='padding-top:6px;font-size:20px;font-weight:600'>{ch}</div>",
                    unsafe_allow_html=True,
                )
                letters[i] = ch

    st.session_state[input_state_key] = letters
    user_answer = "".join(letters)
    update_ready_flag(letters)

    all_filled = all((letters[i] or "") for i in blank_indices)
    return user_answer, all_filled

def compute_badge(xp_total: int, mastery: float):
    """Decide a badge based on XP and mastery."""
    if xp_total >= 2000 and mastery == 100:
        return "👑 Master"
    if xp_total >= 1000 or mastery >= 90:
        return "🥇 Gold"
    if xp_total >= 500 or mastery >= 70:
        return "🥈 Silver"
    if xp_total >= 200 or mastery >= 40:
        return "🥉 Bronze"
    return "🔰 Beginner"




###########################################################
#  SESSION INIT
###########################################################

PRACTICE_MODES = [
    "Practice",   # current missing-letter mode
    "Review",     # weak words (to be implemented)
    "Daily 5",    # daily set (to be implemented)
    "Test",       # timed quiz (to be implemented)
]

SESSION_KEYS = [
    "is_logged_in",
    "user_id",
    "user_name",
    "page",
    "selected_course_id",
    "practice_index",
]

SESSION_KEYS.extend([
    "practice_mode",
    "selected_level",
    "selected_lesson",
    "selected_lesson_pattern_code",
])


def row_to_dict(row):
    """Convert SQLAlchemy Row / Tuple / Dict → Dict safely."""
    if hasattr(row, "_mapping"):
        return dict(row._mapping)
    if isinstance(row, dict):
        return row
    if isinstance(row, tuple):
        # Generic fallback: treat as positional; caller must know order
        try:
            return dict(row)
        except Exception:
            return {}
    return {}


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
#  MODE SELECTOR (Practice / Review / Daily 5 / Test)
###########################################################

def ensure_default_mode():
    """
    Ensure we always have a valid practice_mode in session.
    """
    if "practice_mode" not in st.session_state or st.session_state.practice_mode not in PRACTICE_MODES:
        st.session_state.practice_mode = "Practice"


def render_mode_selector_sidebar():
    """
    Renders a simple mode selector in the sidebar.
    For now, only 'Practice' is fully implemented; the others show placeholders.
    """
    ensure_default_mode()

    st.sidebar.markdown("### 🎯 Mode")
    current_mode = st.sidebar.radio(
        "Choose how you want to work today:",
        PRACTICE_MODES,
        index=PRACTICE_MODES.index(st.session_state.practice_mode),
    )
    if current_mode != st.session_state.practice_mode:
        st.session_state.practice_mode = current_mode
        # When changing mode, send user back to dashboard for a clean flow.
        st.session_state.page = "dashboard"
        st.experimental_rerun()


def render_mode_cards():
    st.markdown("### 🎯 What would you like to do today?")
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        if st.button("✏️ Practice", use_container_width=True):
            st.session_state.mode = "Practice"

    with c2:
        if st.button("🧠 Weak Words", use_container_width=True):
            st.session_state.mode = "Weak Words"

    with c3:
        if st.button("📆 Daily-5", use_container_width=True):
            st.session_state.mode = "Daily-5"

    with c4:
        if st.button("📊 Dashboard", use_container_width=True):
            st.session_state.mode = "Dashboard"


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

    # Show current mode to the student
    ensure_default_mode()
    mode_label = st.session_state.practice_mode

    st.success(f"Mode: **{mode_label}**")

    if mode_label == "Practice":
        st.info("Select a lesson from the left sidebar to begin practising.")
    else:
        st.info("Select a lesson from the left sidebar. This mode is in early build – behaviour may be limited.")


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
    ensure_default_mode()
    mode = st.session_state.practice_mode

    # Top title reflects current mode
    if mode == "Practice":
        st.title("✏️ Practice")
    elif mode == "Review":
        st.title("🔁 Review (Weak Words)")
    elif mode == "Daily 5":
        st.title("📆 Daily 5")
    elif mode == "Test":
        st.title("⏱️ Test Mode")
    else:
        st.title("✏️ Practice")

    # For Step A we only implement the Practice mode.
    # Other modes show a placeholder and return early.
    if mode != "Practice":
        st.info(
            "This mode is not fully implemented yet. "
            "For now, please use **Practice** mode."
        )
        return

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

    key_prefix = f"word_{word_id}"

    # reset per-word state when switching to a new word
    if st.session_state.get("active_word_id") != word_id:
        previous_word_id = st.session_state.get("active_word_id")
        if previous_word_id is not None:
            prev_prefix = f"word_{previous_word_id}"
            for state_key in list(st.session_state.keys()):
                if isinstance(state_key, str) and state_key.startswith(f"{prev_prefix}_"):
                    st.session_state.pop(state_key, None)

        for state_key in list(st.session_state.keys()):
            if isinstance(state_key, str) and state_key.startswith(f"{key_prefix}_"):
                st.session_state.pop(state_key, None)
        st.session_state["active_word_id"] = word_id

    user_answer, is_complete = render_masked_word_input(
        masked_word=masked,
        correct_word=current_word,
        key_prefix=key_prefix,
        blank_indices=blank_indices,
    )

    submitted_key = f"{key_prefix}_submitted"
    checked_key = f"{key_prefix}_checked"
    correct_key = f"{key_prefix}_correct"

    ready_to_submit = st.session_state.pop(f"{key_prefix}_ready_to_submit", False)

    # auto-submit once all blanks are filled
    if ready_to_submit and not st.session_state.get(submitted_key):
        wrong_letters = 0
        for pos in blank_indices:
            typed_letter = (user_answer[pos: pos + 1] or "").lower()
            correct_letter = (current_word[pos: pos + 1] or "").lower()
            if typed_letter != correct_letter:
                wrong_letters += 1

        all_correct = wrong_letters == 0

        st.session_state[submitted_key] = True
        st.session_state[checked_key] = True
        st.session_state[correct_key] = all_correct

        time_taken = int(time.time() - st.session_state.start_time)
        record_attempt(
            user_id=st.session_state.user_id,
            word_id=word_id,
            correct=all_correct,
            time_taken=time_taken,
            blanks_count=len(blank_indices),
            wrong_letters_count=wrong_letters,
        )

        if not all_correct:
            execute(
                """
                INSERT INTO spelling_weak_words(user_id, course_id, lesson_id, word_id, added_on)
                VALUES(:uid, :cid, :lid, :wid, now())
                ON CONFLICT DO NOTHING;
                """,
                {
                    "uid": st.session_state["user_id"],
                    "cid": cid,
                    "lid": st.session_state.get("selected_lesson_id", 0) or 0,
                    "wid": word_id,
                },
            )

        # rerun to immediately show highlighting feedback
        st.experimental_rerun()

    # ---------------- FEEDBACK + NEXT ----------------
    if st.session_state.get(checked_key, False):

        new_mastery = get_lesson_mastery(
            st.session_state["user_id"],
            cid,
            st.session_state.get("selected_lesson_id", 0) or 0,
        )

        encouragements = [
            "🎉 Amazing work! You spelled it correctly!<br>Keep the streak going 💪🔥",
            "🌟 Stellar! Every letter was perfect!<br>You’re on fire 🔥",
            "👏 Nailed it! That spelling was spot on!<br>Keep climbing 🚀",
        ]

        if st.session_state.get(correct_key, False):
            success_message = random.choice(encouragements)
            st.markdown(
                f"""
                <div style='
                    background-color: #28a745;
                    color: white;
                    font-size: 18px;
                    font-weight: 700;
                    padding: 14px 12px;
                    border-radius: 10px;
                    text-align: center;
                '>
                    {success_message}
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.caption(f"Mastery now at {new_mastery}%")
        else:
            st.markdown(
                f"""
                <div style='
                    background-color: #dc3545;
                    color: white;
                    font-size: 18px;
                    font-weight: 700;
                    padding: 14px 12px;
                    border-radius: 10px;
                    text-align: center;
                '>
                    ❌ Not quite right<br>
                    The correct spelling is <strong>{current_word}</strong><br>
                    This word has been added to your Weak Words list for practice 🧠
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.caption(f"Mastery now at {new_mastery}%")

        feedback_letters = []
        for idx, ch in enumerate(current_word):
            typed = user_answer[idx:idx+1]
            is_blank = idx in blank_indices
            if is_blank and typed:
                if typed.lower() == (ch or "").lower():
                    feedback_letters.append(
                        f"<span style='background:#28a745;color:white;padding:6px 8px;border-radius:6px;font-weight:700'>{typed}</span>"
                    )
                else:
                    feedback_letters.append(
                        f"<span style='background:#dc3545;color:white;padding:6px 8px;border-radius:6px;font-weight:700'>{typed}</span>"
                    )
            elif is_blank:
                feedback_letters.append(
                    f"<span style='padding:6px 8px;border-radius:6px;border:1px solid #ccc;font-weight:700'>{ch}</span>"
                )
            else:
                feedback_letters.append(
                    f"<span style='padding:6px 8px;border-radius:6px;font-weight:700'>{ch}</span>"
                )

        st.markdown(
            f"<div style='margin:12px 0;text-align:center;display:flex;gap:8px;justify-content:center;flex-wrap:wrap'>{''.join(feedback_letters)}</div>",
            unsafe_allow_html=True,
        )

        if st.button("Next →"):
            # Move to next word
            st.session_state.practice_index += 1

            # Reset timer
            st.session_state.start_time = time.time()

            # Clean inputs + per-word flags
            for state_key in list(st.session_state.keys()):
                if isinstance(state_key, str) and state_key.startswith(f"{key_prefix}_"):
                    st.session_state.pop(state_key, None)

            st.session_state[checked_key] = False
            st.session_state[correct_key] = False
            st.session_state[submitted_key] = False
            st.session_state["active_word_id"] = None

            st.experimental_rerun()

    # Sidebar navigation
    if st.sidebar.button("Back to Courses"):
        st.session_state.practice_index = 0
        st.session_state.page = "dashboard"
        st.experimental_rerun()




def compute_word_difficulty(word: str, level: int | None) -> int:
    """
    Compute a difficulty score (1–5) for a word.
    Uses length + level (if provided).
    """
    word = word or ""
    length = len(word)

    # base from length
    if length <= 4:
        base = 1
    elif length <= 7:
        base = 2
    elif length <= 10:
        base = 3
    elif length <= 13:
        base = 4
    else:
        base = 5

    # adjust with level (if we have it)
    try:
        lvl = int(level) if level is not None else None
    except Exception:
        lvl = None

    if lvl is not None:
        if lvl >= 6:
            base = min(5, base + 1)
        elif lvl <= 3:
            base = max(1, base - 1)

    return max(1, min(5, base))


def get_xp_and_streak(user_id: int):
    """
    Compute total XP and current streak (days in a row with at least 1 correct attempt)
    based on spelling_attempts joined to spelling_words.
    """
    rows = fetch_all(
        """
        SELECT a.correct,
               a.attempted_on,
               w.word,
               w.level
        FROM spelling_attempts a
        JOIN spelling_words w ON w.word_id = a.word_id
        WHERE a.user_id = :uid
        ORDER BY a.attempted_on ASC
        """,
        {"uid": user_id},
    )

    if not rows or isinstance(rows, dict):
        return 0, 0

    # XP calculation
    xp_total = 0
    per_day_correct = {}  # date -> had_correct_bool

    for r in rows:
        m = getattr(r, "_mapping", r)
        correct = bool(m["correct"])
        attempted_on = m["attempted_on"]
        word = m.get("word") or ""
        level = m.get("level")

        # Normalise date
        if isinstance(attempted_on, datetime):
            d = attempted_on.date()
        else:
            # assume date or string
            try:
                d = attempted_on.date()
            except Exception:
                try:
                    d = datetime.fromisoformat(str(attempted_on)).date()
                except Exception:
                    continue

        if correct:
            # base XP + difficulty bonus
            diff = compute_word_difficulty(word, level)
            xp_total += 10 + (diff * 2)
            per_day_correct[d] = True

    # Streak calculation: count consecutive days up to today with at least 1 correct
    if not per_day_correct:
        return xp_total, 0

    today = date.today()
    streak = 0
    d = today

    # walk backwards while days have correct attempts
    while d in per_day_correct:
        streak += 1
        d = d - timedelta(days=1)

    return xp_total, streak


@st.cache_data(ttl=60)
def get_cached_word_signals(user_id: int, course_id: int, lesson_id: int):
    rows = safe_rows(get_word_difficulty_signals(user_id, course_id, lesson_id))
    out = {}
    for r in rows:
        m = getattr(r, "_mapping", r)
        out[m["word_id"]] = {
            "accuracy": float(m.get("accuracy") or 0),
            "avg_time": float(m.get("avg_time") or 0),
            "avg_wrong_letters": float(m.get("avg_wrong_letters") or 0),
            "recent_failures": int(m.get("recent_failures") or 0),
            "total_attempts": int(m.get("total_attempts") or 0),
        }
    return out


def classify_word_difficulty(signals: dict, avg_time_threshold: float = 8.0):
    accuracy = signals.get("accuracy", 0)
    avg_time = signals.get("avg_time", 0) or 0
    avg_wrong = signals.get("avg_wrong_letters", 0) or 0
    recent_failures = signals.get("recent_failures", 0) or 0
    total_attempts = signals.get("total_attempts", 0) or 0

    if total_attempts == 0:
        return "MEDIUM"

    if accuracy >= 0.85 and avg_time < avg_time_threshold and recent_failures == 0 and avg_wrong < 1.5:
        return "EASY"

    if accuracy < 0.6 or recent_failures > 0 or avg_wrong >= 2:
        return "HARD"

    return "MEDIUM"


def build_difficulty_map(words, signals_map):
    difficulty_map = {}
    for w in words:
        m = getattr(w, "_mapping", w)
        wid = m.get("word_id") or m.get("col_0")
        signals = signals_map.get(wid, {})
        difficulty_map[wid] = classify_word_difficulty(signals)
    return difficulty_map


def get_weak_word_ids(difficulty_map, signals_map):
    weak_ids = set()
    for wid, level in difficulty_map.items():
        signals = signals_map.get(wid, {})
        accuracy = signals.get("accuracy", 1)
        recent_failures = signals.get("recent_failures", 0)
        if level == "HARD" or accuracy < 0.6 or recent_failures >= 2:
            weak_ids.add(wid)
    return weak_ids


def difficulty_breakdown(difficulty_map):
    counts = {"EASY": 0, "MEDIUM": 0, "HARD": 0}
    for level in difficulty_map.values():
        if level in counts:
            counts[level] += 1
    total = sum(counts.values()) or 1
    return {k: round((v / total) * 100, 1) for k, v in counts.items()}


def _word_id(word_row):
    m = getattr(word_row, "_mapping", word_row)
    return m.get("word_id") or m.get("col_0")


def choose_next_word(words, difficulty_map, current_level: str, weak_word_ids=None, last_word_id=None):
    """
    Adaptive selector using difficulty buckets:
      - 60% from current level
      - 20% from one level easier
      - 20% from one level harder
    Weak words are prioritised inside each bucket and immediate repeats are avoided.
    """
    import random

    if not words:
        return None

    weak_word_ids = weak_word_ids or set()
    levels = ["EASY", "MEDIUM", "HARD"]
    current_level = current_level if current_level in levels else "MEDIUM"
    idx = levels.index(current_level)
    easier = levels[max(0, idx - 1)]
    harder = levels[min(len(levels) - 1, idx + 1)]

    roll = random.random()
    if roll < 0.6:
        target_levels = [current_level]
    elif roll < 0.8:
        target_levels = [easier]
    else:
        target_levels = [harder]

    def bucket(levels_to_use):
        return [
            w for w in words
            if difficulty_map.get(_word_id(w), "MEDIUM") in levels_to_use
            and _word_id(w) != last_word_id
        ]

    candidates = bucket(target_levels)
    if not candidates:
        candidates = bucket(levels)  # full fallback

    if not candidates:
        return None

    weak_candidates = [w for w in candidates if _word_id(w) in weak_word_ids]
    if weak_candidates and random.random() < 0.6:
        candidates = weak_candidates

    return random.choice(candidates)


def select_daily_five(words, difficulty_map, signals_map, weak_word_ids):
    import random

    selected = []
    seen = set()

    def take_from(pool, count):
        picks = []
        filtered = [w for w in pool if _word_id(w) not in seen]
        if filtered:
            picks = random.sample(filtered, min(count, len(filtered)))
        for p in picks:
            wid = _word_id(p)
            seen.add(wid)
        return picks

    weak_pool = [w for w in words if _word_id(w) in weak_word_ids]
    medium_pool = [w for w in words if difficulty_map.get(_word_id(w), "MEDIUM") == "MEDIUM"]
    new_pool = [w for w in words if signals_map.get(_word_id(w), {}).get("total_attempts", 0) == 0]

    selected.extend(take_from(weak_pool, 2))
    selected.extend(take_from(medium_pool, 2))
    selected.extend(take_from(new_pool, 1))

    if len(selected) < 5:
        remaining = [w for w in words if _word_id(w) not in seen]
        selected.extend(take_from(remaining, 5 - len(selected)))

    return selected[:5]


def get_lesson_attempt_stats(user_id: int, course_id: int, lesson_id: int):
    """
    Return dict[word_id] -> (correct_count, total_count) for a given lesson.
    """
    rows = fetch_all(
        """
        SELECT word_id,
               SUM(CASE WHEN correct THEN 1 ELSE 0 END) AS correct_count,
               COUNT(*) AS total_count
        FROM spelling_attempts
        WHERE user_id = :uid
          AND course_id = :cid
          AND lesson_id = :lid
        GROUP BY word_id
        """,
        {"uid": user_id, "cid": course_id, "lid": lesson_id},
    )

    out = {}
    if not rows or isinstance(rows, dict):
        return out

    for r in rows:
        m = getattr(r, "_mapping", r)
        out[m["word_id"]] = (m["correct_count"], m["total_count"])

    return out


@st.cache_data(ttl=60)
def get_course_accuracy_stats(user_id: int, course_id: int):
    rows = fetch_all(
        """
        SELECT COUNT(*) AS total_attempts,
               SUM(CASE WHEN correct THEN 1 ELSE 0 END) AS correct_attempts,
               COUNT(DISTINCT word_id) AS words_attempted
        FROM spelling_attempts
        WHERE user_id = :uid
          AND course_id = :cid
        """,
        {"uid": user_id, "cid": course_id},
    )

    if not rows or isinstance(rows, dict):
        return {"total_attempts": 0, "correct_attempts": 0, "words_attempted": 0}

    m = getattr(rows[0], "_mapping", rows[0])
    return {
        "total_attempts": m.get("total_attempts") or 0,
        "correct_attempts": m.get("correct_attempts") or 0,
        "words_attempted": m.get("words_attempted") or 0,
    }


def render_learning_dashboard(user_id: int, course_id: int, xp_total: int, streak: int,
                              mastery_map: dict, difficulty_map: dict, weak_word_ids: set):
    stats = get_course_accuracy_stats(user_id, course_id)
    total_attempts = stats.get("total_attempts", 0)
    correct_attempts = stats.get("correct_attempts", 0)
    words_attempted = stats.get("words_attempted", 0)
    overall_accuracy = round((correct_attempts / total_attempts) * 100, 1) if total_attempts else 0
    breakdown = difficulty_breakdown(difficulty_map)

    st.markdown(
        """
        <style>
        .learning-card {
            background: linear-gradient(135deg, #0b1224, #0f172a);
            padding: 18px;
            border-radius: 14px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.35);
            border: 1px solid rgba(255,255,255,0.05);
        }
        .learning-card h3 { margin-top: 0; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    card = st.container()
    with card:
        st.markdown("<div class='learning-card'>", unsafe_allow_html=True)
        st.markdown("### 📊 Your Learning Dashboard")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Words Attempted", int(words_attempted))
        col2.metric("Overall Accuracy", f"{overall_accuracy}%")
        col3.metric("Total XP", int(xp_total))
        col4.metric("Current Streak 🔥", f"{streak} days")

        st.markdown("---")

        col_left, col_right = st.columns([2, 1])

        with col_left:
            st.markdown("#### 🧩 Pattern-wise Mastery")
            mastery_rows = []
            for pattern, mastery in mastery_map.items():
                status = "🟢 Strong" if mastery >= 85 else "🟡 Improving" if mastery >= 60 else "🔴 Needs Work"
                mastery_rows.append({"Pattern": pattern, "Mastery %": mastery, "Status": status})
            if mastery_rows:
                st.table(mastery_rows)
            else:
                st.caption("No mastery data yet.")

        with col_right:
            st.markdown("#### 🪨 Weak Words Summary")
            st.metric("Weak Words", len(weak_word_ids))
            if st.button("Practice Weak Words"):
                st.session_state.mode = "Weak Words"
                st.session_state.practice_mode = "Weak Words"
                st.session_state.page = "dashboard"
                st.experimental_rerun()
            st.caption("Weak words are those below 60% accuracy or missed twice recently.")

            st.markdown("#### 🎚️ Difficulty Breakdown")
            d_cols = st.columns(3)
            d_cols[0].progress(min(1.0, breakdown.get("EASY", 0) / 100))
            d_cols[0].caption(f"Easy {breakdown.get('EASY', 0)}%")
            d_cols[1].progress(min(1.0, breakdown.get("MEDIUM", 0) / 100))
            d_cols[1].caption(f"Medium {breakdown.get('MEDIUM', 0)}%")
            d_cols[2].progress(min(1.0, breakdown.get("HARD", 0) / 100))
            d_cols[2].caption(f"Hard {breakdown.get('HARD', 0)}%")

        st.markdown("</div>", unsafe_allow_html=True)


def render_practice_mode(mode: str, words: list, difficulty_map: dict, signals_map: dict,
                         weak_word_ids: set, selected_course_id: int, selected_lesson_id: int,
                         selected_lesson_name: str):
    if mode == "Weak Words":
        filtered = [w for w in words if _word_id(w) in weak_word_ids]
        words = filtered
        if not filtered:
            st.info("You have no weak words yet!")

    if mode == "Daily-5":
        words = select_daily_five(words, difficulty_map, signals_map, weak_word_ids)

    if not words:
        st.warning("No words available to practice.")
        return

    last_word_id = st.session_state.get("last_word_id")
    current_level = difficulty_map.get(last_word_id, "MEDIUM") if last_word_id else "MEDIUM"
    word_pick = choose_next_word(
        words,
        difficulty_map,
        current_level=current_level,
        weak_word_ids=weak_word_ids,
        last_word_id=last_word_id,
    )
    if not word_pick:
        st.warning("No words available to practise.")
        return

    m_word = getattr(word_pick, "_mapping", word_pick)
    wid = m_word.get("word_id") or m_word.get("col_0")
    target_word = m_word["word"]
    st.session_state["last_word_id"] = wid

    st.subheader("Spell the word:")

    masked_word, blank_indices = generate_question(
        target_word,
        selected_lesson_name
    )
    st.code(masked_word, language="text")

    key_prefix = f"practice_{selected_course_id}_{selected_lesson_id}_{wid}"

    # Reset state when word changes
    if st.session_state.get("active_word_id") != wid:
        for k in list(st.session_state.keys()):
            if isinstance(k, str) and k.startswith("practice_"):
                st.session_state.pop(k, None)
        st.session_state["active_word_id"] = wid

    user_answer, is_complete = render_masked_word_input(
        masked_word,
        target_word,
        key_prefix,
        blank_indices,
    )

    ready = st.session_state.pop(f"{key_prefix}_ready_to_submit", False)
    submitted_key = f"{key_prefix}_submitted"
    checked_key = f"{key_prefix}_checked"
    correct_key = f"{key_prefix}_correct"

    if ready and not st.session_state.get(submitted_key, False):

        wrong_letters = sum(
            1 for i in blank_indices
            if user_answer[i:i+1] != target_word[i:i+1]
        )
        is_correct = (wrong_letters == 0)

        execute(
            """
            INSERT INTO spelling_attempts(user_id, course_id, lesson_id, word_id, correct, attempted_on)
            VALUES (:uid, :cid, :lid, :wid, :correct, NOW());
            """,
            {
                "uid": st.session_state["user_id"],
                "cid": selected_course_id,
                "lid": selected_lesson_id,
                "wid": wid,
                "correct": is_correct,
            },
        )

        st.session_state[submitted_key] = True
        st.session_state[checked_key] = True
        st.session_state[correct_key] = is_correct

        st.experimental_rerun()

    if st.session_state.get(checked_key, False):

        new_mastery = get_lesson_mastery(
            st.session_state["user_id"],
            selected_course_id,
            selected_lesson_id,
        )

        # CORRECT ANSWER
        if st.session_state.get(correct_key, False):
            encouragements = [
                "🎉 Amazing work! You spelled it correctly!<br>Keep the streak going 💪🔥",
                "🌟 Stellar! Every letter was perfect!<br>You’re on fire 🔥",
                "👏 Nailed it! That spelling was spot on!<br>Keep climbing 🚀",
            ]
            st.markdown(
                f"""
                <div style='
                    background-color: #28a745;
                    color: white;
                    font-size: 18px;
                    font-weight: 700;
                    padding: 14px 12px;
                    border-radius: 10px;
                    text-align: center;
                '>
                    {random.choice(encouragements)}
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.caption(f"Mastery now at {new_mastery}%")

        # INCORRECT ANSWER
        else:
            # add to weak words table
            execute(
                """
                INSERT INTO spelling_weak_words(user_id, course_id, lesson_id, word_id, added_on)
                VALUES(:uid, :cid, :lid, :wid, now())
                ON CONFLICT DO NOTHING;
                """,
                {
                    "uid": st.session_state["user_id"],
                    "cid": selected_course_id,
                    "lid": selected_lesson_id,
                    "wid": wid,
                },
            )

            st.markdown(
                f"""
                <div style='
                    background-color: #dc3545;
                    color: white;
                    font-size: 18px;
                    font-weight: 700;
                    padding: 14px 12px;
                    border-radius: 10px;
                    text-align: center;
                '>
                    ❌ Not quite right<br>
                    The correct spelling is <strong>{target_word}</strong><br>
                    This word has been added to your Weak Words list for practice 🧠
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.caption(f"Mastery now at {new_mastery}%")

        feedback_letters = []
        for idx, ch in enumerate(target_word):
            typed = user_answer[idx:idx+1]
            display = typed or ch
            if idx in blank_indices and typed:
                if (typed or "").lower() == (ch or "").lower():
                    feedback_letters.append(
                        f"<span style='background:#28a745;color:white;padding:6px 8px;border-radius:6px;font-weight:700'>{display}</span>"
                    )
                else:
                    feedback_letters.append(
                        f"<span style='background:#dc3545;color:white;padding:6px 8px;border-radius:6px;font-weight:700'>{display}</span>"
                    )
            elif idx in blank_indices:
                feedback_letters.append(
                    f"<span style='padding:6px 8px;border-radius:6px;border:1px solid #ccc;font-weight:700'>{display}</span>"
                )
            else:
                feedback_letters.append(
                    f"<span style='padding:6px 8px;border-radius:6px;font-weight:700'>{display}</span>"
                )
        st.markdown(
            f"<div style='margin:12px 0;text-align:center;display:flex;gap:8px;justify-content:center;flex-wrap:wrap'>{''.join(feedback_letters)}</div>",
            unsafe_allow_html=True,
        )

        if st.button("Next Word →", key=f"{key_prefix}_next"):
            for k in list(st.session_state.keys()):
                if isinstance(k, str) and k.startswith(key_prefix):
                    st.session_state.pop(k, None)
            st.session_state["active_word_id"] = None
            st.experimental_rerun()


###########################################################
#  MAIN APP CONTROLLER
###########################################################

def main():
    inject_student_css()
    initialize_session_state(st)

    if "mode" not in st.session_state:
        st.session_state.mode = "Practice"

    # NOT LOGGED IN → show Login + Registration tabs
    if not st.session_state.is_logged_in:
        tab_login, tab_register = st.tabs(["Login", "New Registration"])

        with tab_login:
            render_login_page()

        with tab_register:
            render_registration_page()

        return  # stop here when logged out

    # LOGGED IN
    # Sidebar content: user and logout
    st.sidebar.write(f"Logged in as: {st.session_state.user_name}")
    if st.sidebar.button("Logout"):
        logout(st)
        st.experimental_rerun()

    st.sidebar.title("📚 My Spelling Courses")

    # XP & streak header (computed from attempts)
    user_id = st.session_state.get("user_id")
    if user_id:
        xp_total, streak = get_xp_and_streak(user_id)
        st.sidebar.metric("⭐ XP", xp_total)
        st.sidebar.metric("🔥 Streak (days)", streak)

    # 1) Load student courses
    courses = safe_rows(
        fetch_all(
            """
            SELECT c.course_id, c.course_name
            FROM spelling_courses c
            JOIN spelling_enrollments e ON e.course_id = c.course_id
            WHERE e.user_id = :uid
            ORDER BY c.course_name
            """,
            {"uid": st.session_state["user_id"]},
        )
    )

    if not courses:
        st.sidebar.warning("No courses assigned.")
        return

    course_map = {
        c.get("course_name") or c.get("col_1"): c.get("course_id") or c.get("col_0")
        for c in courses
    }
    selected_course_name = st.sidebar.selectbox("Select Course", list(course_map.keys()))
    selected_course_id = course_map[selected_course_name]

    # 2) Load lessons (patterns)
    lessons = safe_rows(fetch_all("""
        SELECT lesson_id, lesson_name
        FROM spelling_lessons
        WHERE course_id = :cid
        ORDER BY lesson_name
    """, {"cid": selected_course_id}))

    if not lessons:
        st.sidebar.info("No lessons found.")
        return

    lesson_map = {}
    mastery_map = {}
    for l in lessons:
        lname = l.get("lesson_name") or l.get("col_1")
        lid = l.get("lesson_id") or l.get("col_0")
        mastery = get_lesson_mastery(
            user_id=st.session_state["user_id"],
            course_id=selected_course_id,
            lesson_id=lid
        )
        lesson_map[lname] = lid
        mastery_map[lname] = mastery

    # sidebar with mastery
    st.sidebar.markdown("### 📘 Lessons (Patterns)")
    for lname in lesson_map.keys():
        st.sidebar.write(f"**{lname}** — {mastery_map[lname]}%")
    selected_lesson_name = st.sidebar.radio("Select Pattern", list(lesson_map.keys()))
    selected_lesson_id = lesson_map[selected_lesson_name]

    # ---------------------------------------------
    # FETCH WORDS FOR THIS LESSON
    # ---------------------------------------------
    words = safe_rows(
        fetch_all(
            """
            SELECT w.word_id, w.word, w.example_sentence, w.level
            FROM spelling_words w
            JOIN spelling_lesson_items li ON li.word_id = w.word_id
            WHERE li.lesson_id = :lid
            ORDER BY w.word
            """,
            {"lid": selected_lesson_id},
        )
    )

    signals_map = get_cached_word_signals(
        user_id=st.session_state["user_id"],
        course_id=selected_course_id,
        lesson_id=selected_lesson_id,
    )
    difficulty_map = build_difficulty_map(words, signals_map)
    weak_word_ids = get_weak_word_ids(difficulty_map, signals_map)

    mastery = mastery_map[selected_lesson_name]
    xp_total, streak = get_xp_and_streak(st.session_state["user_id"])
    badge = compute_badge(xp_total, mastery)

    st.header(f"{selected_lesson_name}  {badge}")
    st.progress(mastery / 100)
    st.caption(f"Mastery: {mastery}% | XP: {xp_total} | Streak: {streak} days")

    render_mode_cards()

    if st.session_state.mode == "Dashboard":
        render_learning_dashboard(
            user_id=st.session_state["user_id"],
            course_id=selected_course_id,
            xp_total=xp_total,
            streak=streak,
            mastery_map=mastery_map,
            difficulty_map=difficulty_map,
            weak_word_ids=weak_word_ids,
        )
        return

    elif st.session_state.mode == "Practice":
        st.session_state.practice_mode = "Practice"
        render_practice_mode(
            mode="Practice",
            words=words,
            difficulty_map=difficulty_map,
            signals_map=signals_map,
            weak_word_ids=weak_word_ids,
            selected_course_id=selected_course_id,
            selected_lesson_id=selected_lesson_id,
            selected_lesson_name=selected_lesson_name,
        )
        return

    elif st.session_state.mode == "Weak Words":
        st.session_state.practice_mode = "Weak Words"
        render_practice_mode(
            mode="Weak Words",
            words=words,
            difficulty_map=difficulty_map,
            signals_map=signals_map,
            weak_word_ids=weak_word_ids,
            selected_course_id=selected_course_id,
            selected_lesson_id=selected_lesson_id,
            selected_lesson_name=selected_lesson_name,
        )
        return

    elif st.session_state.mode == "Daily-5":
        st.session_state.practice_mode = "Daily-5"
        render_practice_mode(
            mode="Daily-5",
            words=words,
            difficulty_map=difficulty_map,
            signals_map=signals_map,
            weak_word_ids=weak_word_ids,
            selected_course_id=selected_course_id,
            selected_lesson_id=selected_lesson_id,
            selected_lesson_name=selected_lesson_name,
        )
        return


if __name__ == "__main__":
    main()
