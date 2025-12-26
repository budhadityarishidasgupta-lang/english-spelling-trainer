#!/usr/bin/env python3
import os
from dotenv import load_dotenv

# Load env ONLY if present (local dev); do NOT override runtime env
load_dotenv()

# --- Fix PYTHONPATH so "shared" and "spelling_app" can be imported ---
import sys
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
# ---------------------------------------------------------------------

import time
import random
import pandas as pd
import streamlit as st
from datetime import datetime, date, timedelta
from sqlalchemy import text

from dotenv import load_dotenv
from html import escape
load_dotenv()

# ---- CORRECT IMPORTS (FINAL) ----
from shared.db import engine, execute, fetch_all, safe_rows
from spelling_app.repository.student_pending_repo import create_pending_registration
from spelling_app.repository.attempt_repo import record_attempt
from spelling_app.repository.attempt_repo import get_lesson_mastery   # <-- REQUIRED FIX
from spelling_app.repository.attempt_repo import get_word_difficulty_signals
from spelling_app.repository.student_repo import (
    get_resume_index_for_lesson,
    get_words_by_ids,
)
from spelling_app.services.spelling_service import get_daily_five_words, get_weak_words
from spelling_app.repository.student_repo import (
    get_lessons_for_course as repo_get_lessons_for_course,
    get_student_courses as repo_get_student_courses,
)

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


SUCCESS_MESSAGES = [
    "🎉 Fantastic! You got it right!",
    "🌟 Brilliant spelling! Keep going!",
    "👏 Nailed it! Your accuracy is improving!",
    "🚀 Great job! Another word mastered!",
    "🏆 Excellent! You’re on a roll!",
]

ENCOURAGEMENT_MESSAGES = [
    "💪 Almost there! Don’t worry, you’re learning.",
    "🌱 Good try! This word will get easier with practice.",
    "😊 Keep going! Mistakes help your brain grow.",
    "🧠 Nice attempt! You’ll get this one soon.",
]

CELEBRATION_MESSAGES = [
    "🎉 Brilliant! You nailed it!",
    "⭐ Awesome spelling!",
    "🔥 You're on fire!",
    "👏 Great job — keep going!",
    "🏆 Fantastic work!",
]

POINTS_PER_CORRECT = 10


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
    "prev_lesson_id",
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


def reset_practice_state():
    """Centralised reset for all practice state fields."""
    st.session_state.practice_index = 0
    st.session_state.current_word = None
    st.session_state.current_wid = None
    st.session_state.current_word_pick = None
    st.session_state.masked_word = None
    st.session_state.submitted = False
    st.session_state.checked = False
    st.session_state.feedback = None
    st.session_state.streak = 0
    st.session_state.word_state = "editing"
    st.session_state.correct = False
    st.session_state.hint_level = 0
    st.session_state.result_processed = False
    st.session_state.start_time = time.time()


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
    return repo_get_student_courses(user_id)


def get_lessons_for_course(course_id, user_id=None):
    lessons = repo_get_lessons_for_course(course_id) or []
    lessons = [dict(l) for l in lessons]

    for lesson_data in lessons:
        if user_id is not None:
            mastery = get_lesson_mastery(
                user_id=user_id,
                course_id=course_id,
                lesson_id=lesson_data.get("lesson_id"),
            )
            lesson_data["progress_pct"] = mastery

    return lessons


def get_words_for_lesson(lesson_id: int):
    """
    Return dict-like rows for UI: current["word_id"], current["word"], etc.
    Primary: spelling_lesson_items (Word Mastery)
    Fallback: spelling_lesson_words (Word Pattern)
    """
    with engine.connect() as conn:
        primary_sql = text(
            """
            SELECT
                w.word_id,
                w.word,
                w.pattern,
                w.pattern_code,
                w.level,
                w.example_sentence
            FROM spelling_lesson_items sli
            JOIN spelling_words w ON w.word_id = sli.word_id
            WHERE sli.lesson_id = :lesson_id
            ORDER BY w.word
        """
        )
        rows = conn.execute(primary_sql, {"lesson_id": lesson_id}).mappings().all()
        if rows:
            return rows

        fallback_sql = text(
            """
            SELECT
                w.word_id,
                w.word,
                w.pattern,
                w.pattern_code,
                w.level,
                w.example_sentence
            FROM spelling_lesson_words slw
            JOIN spelling_words w ON w.word_id = slw.word_id
            WHERE slw.lesson_id = :lesson_id
            ORDER BY w.word
        """
        )
        return conn.execute(fallback_sql, {"lesson_id": lesson_id}).mappings().all()



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
    return generate_missing_letter_question(word)


import random


def blanks_for_streak(streak: int, word_len: int) -> int:
    """Map a streak to a blanks count, clamped for very short words."""
    try:
        s = int(streak)
    except Exception:
        s = 0

    wl = max(0, int(word_len))

    if s >= 9:
        base = 5
    elif s >= 6:
        base = 4
    elif s >= 3:
        base = 3
    else:
        base = 2

    max_allowed = max(1, wl - 2)
    return max(1, min(base, max_allowed))


def generate_missing_letter_question(
    word: str, base_blanks: int = 2, max_blanks: int | None = None
):
    max_available = len(word)
    blanks = max(1, min(base_blanks, max_available))

    if max_blanks is not None:
        blanks = min(blanks, max_blanks)

    if max_available <= blanks:
        indices = list(range(max_available))
    else:
        indices = random.sample(range(max_available), blanks)

    masked = "".join("_" if i in indices else ch for i, ch in enumerate(word))
    return masked, indices



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

    st.caption("Enter your details below. An admin will approve your account shortly.")

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
    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("✏️ Practice", use_container_width=True):
            st.session_state.mode = "Practice"

    with c2:
        if st.button("🧠 Weak Words", use_container_width=True):
            st.session_state.mode = "Weak Words"

    with c3:
        if st.button("📆 Daily-5", use_container_width=True):
            st.session_state.mode = "Daily-5"


###########################################################
#  DASHBOARD: CHOOSE COURSE
###########################################################

def render_student_dashboard():
    st.title("📘 My Courses")

    user_id = st.session_state.get("user_id")

    courses = get_student_courses(user_id)
    st.session_state["courses"] = courses

    if not courses:
        st.info("No courses assigned yet.")
        st.caption("Your teacher will assign a course soon.")
        return

    course_names = [c["course_name"] for c in courses]
    selected_course_name = st.selectbox("Choose a course:", course_names)

    selected_course = next(
        c for c in courses if c["course_name"] == selected_course_name
    )

    previous_course_id = st.session_state.get("active_course_id")
    new_course_id = selected_course["course_id"]

    if previous_course_id != new_course_id:
        reset_practice_state()
        st.session_state.selected_lesson_id = None
        st.session_state.prev_lesson_id = None

    st.session_state.active_course_id = new_course_id
    st.session_state.selected_level = None
    st.session_state.selected_lesson = None


    # Show current mode to the student
    ensure_default_mode()
    mode_label = st.session_state.practice_mode

    st.success(f"Mode: **{mode_label}**")

    if mode_label == "Practice":
        st.info("Use the lesson catalogue to begin practising.")
    else:
        st.info("Use the lesson catalogue. This mode is in early build – behaviour may be limited.")



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

    cid = st.session_state.get("active_course_id")
    lesson_id = st.session_state.get("selected_lesson_id")
    lesson_name = st.session_state.get("selected_lesson")

    if not cid or not lesson_id:
        st.error("No lesson selected. Choose from the lesson catalogue.")
        st.session_state.page = "dashboard"
        st.experimental_rerun()
        return

    st.markdown(f"### Lesson: **{lesson_name}**")

    words = get_words_for_lesson(lesson_id)
    if not words:
        st.warning("No words found for this lesson.")
        return

    # track time per attempt
    if "start_time" not in st.session_state:
        st.session_state.start_time = time.time()

    if "practice_index" not in st.session_state or st.session_state.practice_index is None:
        st.session_state.practice_index = 0

    index = int(st.session_state.practice_index)
    total_words = len(words)
    current_index = min(index, total_words - 1)
    progress = (current_index + 1) / total_words if total_words else 0

    if progress < 0.3:
        bar_color = "#ef4444"
    elif progress < 0.7:
        bar_color = "#f59e0b"
    else:
        bar_color = "#22c55e"

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

    st.session_state.current_example_sentence = current.get("example_sentence")

    info_bits = []
    if level is not None:
        info_bits.append(f"Level {level}")
    if pattern:
        info_bits.append(f"Pattern: {pattern}")

    if info_bits:
        st.caption(" • ".join(info_bits))


    if practice_mode != "Daily-5":
        if practice_mode == "Weak Words":
            # Weak Words counter should reflect only weak words in this lesson
            lesson_id = st.session_state.get("active_lesson_id")

            weak_words_for_lesson = [
                w for w in practice_words
                if w.get("lesson_id") == lesson_id
            ]

            total_weak_words = len(weak_words_for_lesson)
            st.session_state["q_index"] = current_index

            st.caption(f"{st.session_state['q_index'] + 1} / {total_weak_words}")
        else:
            st.markdown(
                f"""
                <div style="font-size:14px; opacity:0.8; margin-bottom:6px;">
                    Q {current_index + 1} / {total_words}
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown(
        f"""
        <div style="
            width:100%;
            background:#1f2937;
            border-radius:8px;
            height:10px;
            margin-bottom:18px;
        ">
            <div style="
                width:{int(progress * 100)}%;
                background:{bar_color};
                height:10px;
                border-radius:8px;
                transition:width 0.4s ease;
            "></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.get("streak", 0) > 0:
        st.markdown(
            f"🔥 <b>{st.session_state.streak}-day streak!</b>",
            unsafe_allow_html=True,
        )

    blanks_count = blanks_for_streak(st.session_state.get("streak", 0), len(current_word))
    masked, _ = generate_missing_letter_question(
        current_word, base_blanks=blanks_count, max_blanks=blanks_count
    )

    st.markdown(
        f"""
        <div style="
            font-size:26px;
            font-weight:700;
            letter-spacing:6px;
            background:#111827;
            padding:16px 20px;
            border-radius:14px;
            margin-bottom:18px;
            text-align:center;
        ">
            {masked}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption(f"Difficulty: {blanks_count} blanks")

    if st.session_state.get("current_wid") != word_id:
        st.session_state.current_wid = word_id
        st.session_state.submitted = False
        st.session_state.checked = False
        st.session_state.correct = False
        st.session_state.pop(f"answer_{word_id}", None)

    if "submitted" not in st.session_state:
        st.session_state.submitted = False
        st.session_state.checked = False
        st.session_state.correct = False

    user_answer = st.text_input(
        "Type the complete word",
        key=f"answer_{word_id}",
        disabled=st.session_state.get("checked", False),
    )

    action_col, _ = st.columns([1, 1])
    submit_clicked = False
    next_clicked = False

    if not st.session_state.submitted:
        with action_col:
            submit_clicked = st.button("✅ Submit", use_container_width=True)

    if submit_clicked:
        start = st.session_state.get("start_time", time.time())
        time_taken = int(time.time() - start)

        is_correct = user_answer.strip().lower() == current_word.lower()

        record_attempt(
            user_id=st.session_state.user_id,
            word_id=word_id,
            correct=is_correct,
            time_taken=time_taken,
            blanks_count=masked.count("_"),
            wrong_letters_count=0 if is_correct else 1,
        )

        # IMPORTANT: evaluation only
        st.session_state.submitted = True
        st.session_state.checked = True
        st.session_state.correct = is_correct

        # ❌ DO NOT reset current_wid
        # ❌ DO NOT rerun

    # ---------------- FEEDBACK + NEXT ----------------
    if st.session_state.checked:
        example_sentence = st.session_state.get("current_example_sentence")
        example_html = ""
        if example_sentence:
            example_html = f"""
                <div style=\"font-size:13px; opacity:0.9;\">
                    📘 Example sentence: \"{escape(example_sentence)}\"
                </div>
            """

        if st.session_state.correct:
            xp_earned = 10
            st.markdown(
                f"""
                <div style=\"
                    background:#064e3b;
                    color:#d1fae5;
                    padding:12px 16px;
                    border-radius:10px;
                    font-weight:600;
                    margin-top:8px;
                \">
                    <div style=\"display:flex; flex-direction:column; gap:4px;\">
                        <div>🏆 Fantastic work! ⭐ You earned {xp_earned} XP</div>
                        {example_html}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
                <div style=\"
                    background:#1f2937;
                    color:#e5e7eb;
                    padding:12px 16px;
                    border-radius:10px;
                    font-weight:600;
                    margin-top:8px;
                \">
                    <div style=\"display:flex; flex-direction:column; gap:4px;\">
                        <div>😅 Not quite right — keep trying!</div>
                        {example_html}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if st.session_state.submitted:
        with action_col:
            next_clicked = st.button("➡️ Next", use_container_width=True)

    if next_clicked:
        # advance progress
        st.session_state.question_number += 1

        if is_weak_mode:
            if st.session_state[index_key] < total_words - 1:
                st.session_state[index_key] += 1
            else:
                st.success("🎉 You’ve practiced all weak words for this lesson!")
                return
        else:
            st.session_state.practice_index += 1

        # reset per-word state
        st.session_state.submitted = False
        st.session_state.checked = False
        st.session_state.correct = False
        st.session_state.hint_level = 0
        st.session_state.start_time = time.time()
        st.session_state.current_example_sentence = None
        st.session_state.hint_used = False
        st.session_state.wrong_attempts = 0
        st.session_state.user_input = ""

        # clear input
        st.session_state[f"answer_{word_id}"] = ""
        del st.session_state[f"answer_{word_id}"]

        # THIS is the only place we move on
        st.session_state.current_wid = None

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
            "recent_correct": float(m.get("recent_correct") or 0),
            "recent_wrong_last3": int(m.get("recent_wrong_last3") or 0),
            "total_attempts": int(m.get("total_attempts") or 0),
        }
    return out


def compute_word_score(stats):
    """
    Compute an adaptive score (0-1) using accuracy, recent performance, and speed.
    Lower scores imply the word is harder for the student.
    """
    if stats["attempts"] == 0:
        return 0.5  # unseen words are medium priority

    accuracy = stats["correct"] / stats["attempts"]

    score = (
        0.6 * accuracy +
        0.2 * stats.get("recent_correct", accuracy) +
        0.2 * max(0, 1 - (stats.get("avg_time", 5) / 6))
    )

    return round(score, 2)


def classify_word_difficulty(stats: dict):
    score = compute_word_score(stats)

    if score < 0.4:
        return "HARD"
    if score > 0.75:
        return "EASY"
    return "MEDIUM"


def build_stats_map(signals_map: dict):
    stats_map = {}
    for wid, signals in signals_map.items():
        attempts = int(signals.get("total_attempts", 0) or 0)
        accuracy = float(signals.get("accuracy", 0) or 0)
        correct = int(round(accuracy * attempts)) if attempts else 0
        stats_map[wid] = {
            "attempts": attempts,
            "correct": correct,
            "avg_time": float(signals.get("avg_time", 5) or 5),
            "recent_correct": float(
                signals.get("recent_correct", accuracy if attempts else 0.5)
            ),
            "recent_wrong_last3": int(signals.get("recent_wrong_last3", 0) or 0),
            "accuracy": accuracy,
        }
    return stats_map


def build_difficulty_map(words, stats_map):
    difficulty_map = {}
    for w in words:
        m = getattr(w, "_mapping", w)
        wid = m.get("word_id") or m.get("col_0")
        stats = stats_map.get(wid, {"attempts": 0, "correct": 0, "avg_time": 5, "recent_correct": 0.5})
        difficulty_map[wid] = classify_word_difficulty(stats)
    return difficulty_map


def get_weak_word_ids(stats_map):
    weak_ids = set()
    for wid, stats in stats_map.items():
        accuracy = stats.get("accuracy", 1)
        recent_wrong = stats.get("recent_wrong_last3", 0)
        if accuracy < 0.6 or recent_wrong >= 2:
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


def select_next_word(words, stats_map, force_easy_word: bool = False, last_word_id=None):
    """
    Score all available words, weight towards weaker items, and optionally bias
    towards easy words when the student is struggling.
    """
    import random

    if not words:
        return None

    scored = []
    for w in words:
        wid = _word_id(w)
        stats = stats_map.get(wid, {
            "attempts": 0,
            "correct": 0,
            "avg_time": 5,
            "recent_correct": 0.5,
        })
        score = compute_word_score(stats)
        scored.append((w, wid, score))

    # Sort weakest first
    scored.sort(key=lambda x: x[2])

    if force_easy_word:
        easy_bucket = [item for item in scored if item[2] > 0.75 and item[1] != last_word_id]
        if easy_bucket:
            return random.choice(easy_bucket)[0]

    bucket = (
        scored[:5] * 3 +      # weakest words appear more often
        scored[5:10] * 2 +    # medium words
        scored[10:20]         # easy words
    )

    bucket = [item for item in bucket if item[1] != last_word_id] or [item for item in scored if item[1] != last_word_id]
    if not bucket:
        bucket = scored

    return random.choice(bucket)[0]


def select_daily_five(words, stats_map):
    import random

    scored = []
    for w in words:
        wid = _word_id(w)
        stats = stats_map.get(wid, {"attempts": 0, "correct": 0, "avg_time": 5, "recent_correct": 0.5})
        score = compute_word_score(stats)
        scored.append((w, wid, score))

    scored.sort(key=lambda x: x[2])

    hard_words = [item for item in scored if item[2] < 0.4]
    medium_words = [item for item in scored if 0.4 <= item[2] <= 0.75]
    easy_words = [item for item in scored if item[2] > 0.75]

    daily_words = (
        [w for w, _, _ in hard_words[:3]] +
        [w for w, _, _ in medium_words[:1]] +
        [w for w, _, _ in easy_words[:1]]
    )

    if len(daily_words) < 5:
        remaining = [w for w, _, _ in scored if w not in daily_words]
        daily_words.extend(remaining[: max(0, 5 - len(daily_words))])

    return daily_words[:5] if daily_words else [w for w, _, _ in scored[:5]]


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


def render_practice_mode(lesson_id: int, course_id: int):
    import time

    ensure_default_mode()
    practice_mode = st.session_state.get("practice_mode", "Practice") or "Practice"
    st.session_state.practice_mode = practice_mode

    # --- SAFETY INITIALISATION ---
    st.session_state.setdefault("correct_streak", 0)
    st.session_state.setdefault("recent_results", [])
    st.session_state.setdefault("difficulty_level", 2)
    st.session_state.setdefault("earned_badges", set())
    st.session_state.setdefault("attempts_total", 0)
    st.session_state.setdefault("correct_total", 0)
    st.session_state.setdefault("result_processed", False)

    if "word_state" not in st.session_state:
        st.session_state.word_state = "editing"

    if "practice_index" not in st.session_state:
        st.session_state.practice_index = 0

    if "start_time" not in st.session_state:
        st.session_state.start_time = time.time()

    if "practice_index" not in st.session_state or st.session_state.practice_index is None:
        st.session_state.practice_index = 0

    if "current_wid" not in st.session_state:
        st.session_state.current_wid = None

    if "submitted" not in st.session_state:
        st.session_state.submitted = False

    if "checked" not in st.session_state:
        st.session_state.checked = False
    # --- GUARANTEED session state initialization ---
    if "start_time" not in st.session_state:
        st.session_state.start_time = time.time()

    if "correct" not in st.session_state:
        st.session_state.correct = False

    if "question_number" not in st.session_state:
        st.session_state.question_number = 1

    if "hint_level" not in st.session_state:
        st.session_state.hint_level = 0

    if "current_word_pick" not in st.session_state:
        st.session_state.current_word_pick = None
    # ------------------------------------------------

    if st.session_state.get("practice_lesson_id") != lesson_id:
        st.session_state.practice_index = 0
        st.session_state.current_wid = None
        st.session_state.current_word_pick = None
        st.session_state.word_state = "editing"
        st.session_state.practice_lesson_id = lesson_id

    user_id = st.session_state.get("user_id")
    lesson_name = st.session_state.get("active_lesson_name")

    lessons = get_lessons_for_course(course_id, user_id=user_id) if course_id else []
    lesson_lookup = {lesson["lesson_id"]: lesson for lesson in lessons}
    lesson = lesson_lookup.get(lesson_id, {})

    if not lesson_name:
        lesson_name = lesson.get("lesson_name")

    mastery = lesson.get("progress_pct", 0) or 0
    xp_total, streak = get_xp_and_streak(user_id)
    badge = compute_badge(xp_total, mastery)

    if lesson_name:
        st.header(f"{lesson_name}  {badge}")
        st.progress(mastery / 100)
        st.caption(f"Mastery: {mastery}% | XP: {xp_total} | Streak: {streak} days")

    render_mode_cards()

    active_lesson_id = st.session_state.get("active_lesson_id") or lesson_id

    lesson_weak_words = []
    if practice_mode == "Weak Words":
        lesson_weak_words = [
            w for w in get_weak_words(st.session_state["user_id"])
            if w.get("lesson_id") == active_lesson_id
        ]

        weak_word_ids = [w["word_id"] for w in lesson_weak_words]

        if weak_word_ids:
            lesson_word_rows = get_words_by_ids(weak_word_ids)
            lesson_word_lookup = {
                w["word_id"]: w
                for w in lesson_word_rows
            }

            ordered_weak_words = [
                lesson_word_lookup[wid]
                for wid in weak_word_ids
                if wid in lesson_word_lookup
            ]

            for word in ordered_weak_words:
                word.setdefault("lesson_id", active_lesson_id)
        else:
            ordered_weak_words = []

        if st.session_state.get("weak_words_lesson_id") != active_lesson_id:
            st.session_state.practice_index = 0
            st.session_state.current_wid = None
            st.session_state.current_word_pick = None

        st.session_state.weak_words_lesson_id = active_lesson_id
        st.session_state.practice_words = ordered_weak_words

        if st.session_state.practice_index >= len(ordered_weak_words):
            st.session_state.practice_index = 0

        words = ordered_weak_words
    else:
        words = get_words_for_lesson(lesson_id)

    if not words:
        if practice_mode == "Weak Words":
            st.info("No weak words logged for this lesson yet.")
            st.caption("Weak Words come from your incorrect attempts in this lesson.")
            return

        # Explicit debug counts (prevents silent “nothing happens”)
        with engine.connect() as conn:
            c_items = conn.execute(
                text("SELECT COUNT(*) FROM spelling_lesson_items WHERE lesson_id=:lid"),
                {"lid": lesson_id},
            ).scalar() or 0
            c_words = conn.execute(
                text("SELECT COUNT(*) FROM spelling_lesson_words WHERE lesson_id=:lid"),
                {"lid": lesson_id},
            ).scalar() or 0

        st.error("No practice words are mapped to this lesson yet.")
        st.caption(
            f"lesson_id={lesson_id} | spelling_lesson_items={int(c_items)} | spelling_lesson_words={int(c_words)}"
        )
        return

    signals_map = get_cached_word_signals(
        user_id=user_id,
        course_id=course_id,
        lesson_id=lesson_id,
    )
    stats_map = build_stats_map(signals_map)
    difficulty_map = build_difficulty_map(words, stats_map)
    weak_word_ids = (
        {w["word_id"] for w in lesson_weak_words}
        if practice_mode == "Weak Words"
        else get_weak_word_ids(stats_map)
    )

    if practice_mode == "Daily-5":
        daily_ids = get_daily_five_words(user_id)
        words = get_words_by_ids(daily_ids)
        st.session_state.practice_words = words
        st.session_state.practice_index = 0
        st.session_state.current_wid = None
        st.session_state.current_word_pick = None

        if not words:
            st.info("Your Daily-5 will appear once you start practising.")
            st.button("Start Daily-5", disabled=True)
            return

        if len(words) < 5:
            st.info("Only a few personalised words are available right now, but let's practise them!")

    if not words:
        st.info("This lesson doesn’t have words yet.")
        st.caption("Try another lesson.")
        return

    practice_words = words
    is_weak_mode = practice_mode == "Weak Words"
    index_key = "q_index" if is_weak_mode else "practice_index"

    if index_key not in st.session_state:
        st.session_state[index_key] = 0

    total_words = len(practice_words)
    practice_index = int(st.session_state[index_key])
    current_index = min(practice_index, total_words - 1) if total_words else 0
    progress = (current_index + 1) / total_words if total_words else 0

    if progress < 0.3:
        bar_color = "#ef4444"
    elif progress < 0.7:
        bar_color = "#f59e0b"
    else:
        bar_color = "#22c55e"

    if practice_index >= total_words:
        finish_message = (
            "🎉 You’ve practiced all weak words for this lesson!"
            if is_weak_mode
            else "🎉 You finished all words!"
        )
        st.success(finish_message)
        if st.button("Restart practice"):
            st.session_state[index_key] = 0
            st.session_state.current_wid = None
            st.session_state.current_word_pick = None
            st.session_state.word_state = "editing"
            st.session_state.start_time = time.time()
            st.experimental_rerun()
        return

    if st.session_state.current_wid is None:
        current = practice_words[st.session_state[index_key]]
        st.session_state.current_wid = current["word_id"]
        st.session_state.current_word_pick = current
        st.session_state.start_time = time.time()
    else:
        current = st.session_state.get("current_word_pick") or practice_words[current_index]
        st.session_state.current_word_pick = current

    st.session_state.current_example_sentence = current.get("example_sentence")

    wid = st.session_state.current_wid
    target_word = current["word"]
    st.session_state["last_word_id"] = wid

    st.subheader("Spell the word:")

    if is_weak_mode:
        # Weak Words counter should reflect only weak words in this lesson
        lesson_id = st.session_state.get("active_lesson_id")

        weak_words_for_lesson = [
            w for w in practice_words
            if w.get("lesson_id") == lesson_id
        ]

        total_weak_words = len(weak_words_for_lesson)
        st.session_state["q_index"] = current_index

        st.caption(f"{st.session_state['q_index'] + 1} / {total_weak_words}")
    else:
        st.markdown(
            f"""
            <div style="font-size:14px; opacity:0.8; margin-bottom:6px;">
                Q {current_index + 1} / {total_words}
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        f"""
        <div style="
            width:100%;
            background:#1f2937;
            border-radius:8px;
            height:10px;
            margin-bottom:18px;
        ">
            <div style="
                width:{int(progress * 100)}%;
                background:{bar_color};
                height:10px;
                border-radius:8px;
                transition:width 0.4s ease;
            "></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.get("streak", 0) > 0:
        st.markdown(
            f"🔥 <b>{st.session_state.streak}-day streak!</b>",
            unsafe_allow_html=True,
        )

    blanks_count = blanks_for_streak(
        st.session_state.get("streak", 0), len(target_word)
    )

    masked_word, _ = generate_missing_letter_question(
        target_word,
        base_blanks=blanks_count,
        max_blanks=blanks_count,
    )

    st.markdown(
        f"""
        <div style="
            font-size:26px;
            font-weight:700;
            letter-spacing:6px;
            background:#111827;
            padding:16px 20px;
            border-radius:14px;
            margin-bottom:18px;
            text-align:center;
        ">
            {masked_word}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption(f"Difficulty: {blanks_count} blanks")

    if st.session_state.get("current_wid") != wid:
        st.session_state.current_wid = wid
        st.session_state.submitted = False
        st.session_state.checked = False
        st.session_state.correct = False
        st.session_state.pop(f"answer_{wid}", None)

    if "submitted" not in st.session_state:
        st.session_state.submitted = False
        st.session_state.checked = False
        st.session_state.correct = False

    user_input = st.text_input(
        "Type the complete word",
        key=f"input_{wid}",
        disabled=(st.session_state.word_state == "submitted"),
    )

    action_col, _ = st.columns([1, 1])

    if st.session_state.word_state == "editing":
        with action_col:
            if st.button("✅ Submit", key=f"submit_{wid}"):
                is_correct = user_input.lower() == target_word.lower()

                time_taken = int(time.time() - st.session_state.start_time)
                blanks_count = masked_word.count("_")

                record_attempt(
                    user_id=st.session_state.user_id,
                    word_id=wid,
                    correct=is_correct,
                    time_taken=time_taken,
                    blanks_count=blanks_count,
                    wrong_letters_count=0 if is_correct else 1,
                )

                st.session_state.last_result_correct = is_correct
                st.session_state.word_state = "submitted"

                st.experimental_rerun()

    if (
        st.session_state.word_state == "submitted"
        and not st.session_state.get("result_processed")
    ):
        st.session_state.correct = st.session_state.get("last_result_correct", False)
        st.session_state.attempts_total = st.session_state.get("attempts_total", 0) + 1
        if st.session_state.correct:
            st.session_state.correct_total = st.session_state.get("correct_total", 0) + 1

        if st.session_state.correct:
            st.session_state.correct_streak += 1
        else:
            st.session_state.correct_streak = 0

        st.session_state.recent_results.append(st.session_state.correct)
        st.session_state.recent_results = st.session_state.recent_results[-3:]

        level = st.session_state.difficulty_level

        if st.session_state.correct_streak >= 5:
            level = min(level + 1, 5)
        elif st.session_state.correct_streak >= 3:
            level = min(level + 1, 4)
        elif st.session_state.recent_results.count(False) >= 2:
            level = max(level - 1, 1)

        st.session_state.difficulty_level = level

        def award_badge(badge_name, emoji):
            if badge_name not in st.session_state.earned_badges:
                st.session_state.earned_badges.add(badge_name)
                st.success(f"{emoji} **Badge Unlocked:** {badge_name}")

        if st.session_state.correct_streak == 3:
            award_badge("Streak Starter", "🔥")

        if st.session_state.correct_streak == 5:
            award_badge("On Fire", "🚀")

        attempts = st.session_state.get("attempts_total", 0)
        corrects = st.session_state.get("correct_total", 0)

        if attempts >= 10 and (attempts and (corrects / attempts) >= 0.9):
            award_badge("Sharp Shooter", "🎯")

        if st.session_state.correct_streak == 10:
            award_badge("Perfect Run", "🏆")

        st.session_state.result_processed = True

    if st.session_state.word_state == "submitted":
        example_sentence = st.session_state.get("current_example_sentence")

        if st.session_state.last_result_correct:
            st.success(
                "🏆 Fantastic work! ⭐ You earned 10 XP\n\n"
                f"📘 Example sentence: \"{example_sentence}\""
            )
        else:
            st.warning(
                "😅 Try again!\n\n"
                f"📘 Example sentence: \"{example_sentence}\""
            )

    if st.session_state.word_state == "submitted":
        with action_col:
            if st.button("➡️ Next", key=f"next_{wid}"):

                st.session_state.practice_index += 1
                st.session_state.word_state = "editing"
                st.session_state.start_time = time.time()

                # Clear old inputs safely
                for k in list(st.session_state.keys()):
                    if k.startswith("input_") or k.startswith("submit_"):
                        del st.session_state[k]

                # force new word selection
                st.session_state.current_wid = None
                st.session_state.current_word_pick = None
                st.session_state.result_processed = False

                st.experimental_rerun()


###########################################################
#  MAIN APP CONTROLLER
###########################################################

def main():
    # === HARD SAFETY: if a lesson is selected, ALWAYS enter practice ===
    if st.session_state.get("active_lesson_id") is not None:
        st.session_state["mode"] = "Practice"
        st.session_state["lesson_started"] = True

    inject_student_css()
    initialize_session_state(st)

    if "mode" not in st.session_state:
        st.session_state.mode = "Practice"

    st.title("WordSprint")

    # NOT LOGGED IN → show Login + Registration tabs
    if not st.session_state.is_logged_in:
        tab_login, tab_register = st.tabs(["Login", "New Registration"])

        with tab_login:
            render_login_page()

        with tab_register:
            render_registration_page()

        return  # stop here when logged out

    # LOGGED IN
    st.sidebar.markdown(f"### 👤 Hi, {st.session_state.user_name}")
    
    
    if st.sidebar.button("Logout"):
        logout(st)
        st.experimental_rerun()
        

    st.sidebar.markdown("### 📘 Course")

    courses = get_student_courses(st.session_state["user_id"])
    st.session_state["courses"] = courses

    if not courses:
        st.info("No courses assigned yet.")
        st.caption("Your teacher will assign a course soon.")
        return

    # --- Course switcher (available even during practice) ---
    if st.session_state.get("courses"):

        current_course_id = st.session_state.get("active_course_id")

        selected_course = st.sidebar.selectbox(
            "Switch course",
            options=st.session_state["courses"],
            format_func=lambda c: c["course_name"],
            index=next(
                (i for i, c in enumerate(st.session_state["courses"])
                 if c["course_id"] == current_course_id),
                0,
            ),
            key="sidebar_course_switcher",
        )

        # If user selects a different course
        if selected_course["course_id"] != current_course_id:

            # --- Reset practice state safely ---
            st.session_state["active_course_id"] = selected_course["course_id"]
            st.session_state["active_lesson_id"] = None
            st.session_state["lesson_started"] = False
            st.session_state["q_index"] = 0
            st.session_state["show_feedback"] = False
            st.session_state["current_input"] = ""

            # Optional: clear practice-specific cached data
            st.session_state.pop("practice_words", None)

            st.rerun()

    if st.session_state.get("lesson_started"):
        render_practice_mode(
            lesson_id=st.session_state["active_lesson_id"],
            course_id=st.session_state["active_course_id"],
        )
        return

    course_map = {
        c.get("course_id") or c.get("col_0"): c.get("course_name") or c.get("col_1")
        for c in courses
    }

    active_course_id = st.session_state.get("active_course_id")

    if active_course_id not in course_map:
        # default to the first available course when none is active
        active_course_id = courses[0]["course_id"]
        st.session_state["active_course_id"] = active_course_id

    st.session_state.selected_course_title = course_map[active_course_id]

    lessons = get_lessons_for_course(
        active_course_id,
        user_id=st.session_state.user_id,
    )

    # Guard: selected lesson must belong to this course
    if st.session_state.get("selected_lesson_id"):
        valid_lesson_ids = {l["lesson_id"] for l in lessons}
        if st.session_state.selected_lesson_id not in valid_lesson_ids:
            st.session_state.selected_lesson_id = None

    if not lessons:
        st.info("No lessons available in this course yet.")
        if st.button("Back to courses"):
            st.session_state.active_course_id = None
            st.experimental_rerun()
        return

    st.markdown("### Lesson catalogue")

    header_cols = st.columns([3, 1, 1, 1])
    headers = ["Lesson", "Words", "Status", "Action"]
    for col, label in zip(header_cols, headers):
        col.markdown(f"**{label}**")

    for lesson in lessons:
        progress = lesson.get("progress_pct", 0) or 0
        word_count = lesson.get("word_count", "—")

        if progress >= 90:
            status = "Mastered"
            status_color = "#16a34a"  # green
        elif progress > 0:
            status = "In progress"
            status_color = "#2563eb"  # blue
        else:
            status = "Not started"
            status_color = "#6b7280"  # grey

        row_cols = st.columns([3, 1, 1, 1])
        with row_cols[0]:
            st.markdown(f"**{lesson['lesson_name']}**")
        with row_cols[1]:
            st.markdown(str(word_count))
        with row_cols[2]:
            st.markdown(
                f"<span style='color:{status_color}'>{status}</span>",
                unsafe_allow_html=True,
            )
        with row_cols[3]:
            if st.button("Start", key=f"start_{lesson['lesson_id']}"):

                # SINGLE PRACTICE ENTRY CONTRACT (ALL COURSES)
                st.session_state["mode"] = "Practice"
                st.session_state["lesson_started"] = True
                st.session_state["active_lesson_id"] = lesson["lesson_id"]
                st.session_state["active_course_id"] = lesson["course_id"]
                st.session_state["active_lesson_name"] = lesson["lesson_name"]

                # Reset practice state
                st.session_state["q_index"] = 0
                st.session_state["current_input"] = ""
                st.session_state["show_feedback"] = False

                st.rerun()


if __name__ == "__main__":
    main()
