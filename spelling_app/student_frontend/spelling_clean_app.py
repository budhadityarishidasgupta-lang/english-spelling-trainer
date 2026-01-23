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
from sqlalchemy.exc import OperationalError
from collections.abc import Mapping

from html import escape
import html

# ---- CORRECT IMPORTS (FINAL) ----
from shared.db import engine, execute, fetch_all, safe_rows
from spelling_app.repository.attempt_repo import record_attempt
from spelling_app.repository.attempt_repo import get_lesson_mastery   # <-- REQUIRED FIX
from spelling_app.repository.attempt_repo import get_word_difficulty_signals
from spelling_app.repository.spelling_lesson_repo import (
    get_weak_words_for_lesson,
)
from spelling_app.repository.weak_words_virtual_lesson_repo import (
    prepare_system_weak_words_lesson_for_user,
)
from spelling_app.repository.student_repo import (
    get_lessons_for_course,
    get_resume_index_for_lesson,
    get_student_courses,
    get_words_by_ids,
    get_words_for_lesson,
)
from spelling_app.services.spelling_service import get_daily_five_words, get_weak_words
from spelling_app.repository.spelling_content_repo import get_content_block
from spelling_app.repository.registration_repo import (
    create_pending_registration,
    generate_registration_token,
)

# Student app must not initialize DB tables.

def get_engine_safe():
    try:
        with engine.connect():
            return engine
    except OperationalError:
        st.error(
            "⚠️ Database temporarily unavailable. Please refresh in a few seconds."
        )
        st.stop()


def user_has_any_mistakes(user_id: int) -> bool:
    with get_engine_safe().connect() as db:
        row = db.execute(
            text(
                """
                SELECT 1
                FROM spelling_attempts
                WHERE user_id = :uid
                  AND correct = FALSE
                LIMIT 1
                """
            ),
            {"uid": user_id},
        ).fetchone()
        return row is not None


def get_global_weak_word_ids(user_id: int, limit: int = 50) -> list[int]:
    """
    Returns word_ids where the student has made mistakes.
    This is GLOBAL (across lessons & courses) by design.
    """
    with get_engine_safe().connect() as db:
        rows = db.execute(
            text(
                """
                SELECT
                    word_id
                FROM spelling_attempts
                WHERE user_id = :uid
                  AND correct IS DISTINCT FROM TRUE
                GROUP BY word_id
                ORDER BY COUNT(*) DESC
                LIMIT :limit
                """
            ),
            {"uid": user_id, "limit": limit},
        ).fetchall()

    return [r._mapping["word_id"] for r in rows]


def _load_weak_word_pool(user_id: int) -> list[dict]:
    word_ids = get_global_weak_word_ids(user_id)
    if not word_ids:
        return []

    words = get_words_by_ids(word_ids)
    by_id = {w["word_id"]: w for w in words}

    pool = []
    for wid in word_ids:
        w = by_id.get(wid)
        if not w:
            continue
        pool.append(
            {
                "word_id": wid,
                "word": w.get("word"),
                "hint": w.get("hint"),
                "example_sentence": w.get("example_sentence"),
            }
        )

    return pool


def _fetch_spelling_words(lesson_id: int):
    return safe_rows(
        fetch_all(
            """
            SELECT
                w.word_id,
                w.word,
                COALESCE(
                    o_same.hint_text,
                    o_any.hint_text,
                    w.hint
                ) AS hint,
                w.example_sentence,
                w.pattern,
                w.pattern_code
            FROM spelling_lesson_items sli
            JOIN spelling_words w
                ON w.word_id = sli.word_id

            -- 1️⃣ AI override for SAME course
            LEFT JOIN spelling_hint_overrides o_same
              ON o_same.word_id = w.word_id
             AND o_same.course_id = w.course_id

            -- 2️⃣ AI override for SAME WORD TEXT (any course)
            LEFT JOIN spelling_hint_overrides o_any
              ON o_any.word_id = (
                  SELECT w2.word_id
                  FROM spelling_words w2
                  WHERE w2.word = w.word
                    AND w2.word_id <> w.word_id
                  LIMIT 1
              )

            WHERE sli.lesson_id = :lesson_id
            ORDER BY w.word_id
            """,
            {"lesson_id": lesson_id},
        )
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

PAYPAL_CHECKOUT_URL = "https://www.paypal.com/ncp/payment/QAN2QNPSJPQ88"

POINTS_PER_CORRECT = 10


###########################################################
#  SESSION INIT
###########################################################

PRACTICE_MODES = [
    "Practice",   # current missing-letter mode
    "Review",     # weak words (to be implemented)
    "Test",       # timed quiz (to be implemented)
]

VALID_PRACTICE_MODES = ["lesson", "weak_words"]

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
    """Convert SQLAlchemy Row / RowMapping / Tuple / Dict → plain dict safely."""
    if row is None:
        return {}

    # SQLAlchemy Row has _mapping
    if hasattr(row, "_mapping"):
        return dict(row._mapping)

    # SQLAlchemy RowMapping (and any mapping-like object)
    if isinstance(row, Mapping):
        return dict(row)

    # Already a dict
    if isinstance(row, dict):
        return row

    # Tuple fallback (only works if it's (k,v) pairs)
    if isinstance(row, tuple):
        try:
            return dict(row)
        except Exception:
            return {}

    return {}


def _get_block(db, key):
    row = get_content_block(db, key)
    if not row:
        return None
    # row fields: block_key, title, body, media_data
    return row


def get_landing_content(db):
    banner = _get_block(db, "landing_banner")
    tagline = _get_block(db, "landing_tagline")
    value = _get_block(db, "landing_value")
    register = _get_block(db, "landing_register")
    support = _get_block(db, "landing_support")

    # Safe fallbacks
    banner_data = banner.media_data if banner and banner.media_data else None
    tagline_text = (tagline.body if tagline and tagline.body else "Building confidence, one step at a time.")
    value_text = (value.body if value and value.body else "• Daily practice that adapts\n• Fix weak areas automatically\n• Clear progress for parents")
    register_text = (
        register.body
        if register and register.body
        else "One-time access to SpellingSprint learning apps\nSecure checkout via PayPal."
    )
    support_text = (support.body if support and support.body else "Support: support@wordsprint.app")

    return banner_data, tagline_text, value_text, register_text, support_text


def _get_student_home_text(db, key: str, fallback: str = "") -> str:
    """
    Fetch Student Home content from admin-managed content blocks.
    Handles ORM and SQLAlchemy Core row formats safely.
    """
    row = get_content_block(db, key)
    if not row:
        return fallback

    # ORM-style access
    if hasattr(row, "body") and row.body:
        return row.body

    # SQLAlchemy Core Row
    if hasattr(row, "_mapping"):
        return row._mapping.get("body", fallback)

    return fallback


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
        .practice-word, .practice-answer {
            font-size:26px;
            font-weight:700;
            letter-spacing:6px;
            background:#111827;
            padding:16px 20px;
            border-radius:14px;
            margin-bottom:18px;
            text-align:center;
        }
        .letter-span {
            display: inline-block;
            padding: 0 0.02em;
            border-radius: 6px;
        }

        .letter-ok {
            color: #7ED321;
        }

        .letter-bad {
            color: #ff5c5c;
        }

        .letter-neutral {
            color: inherit;
        }
        .example-box {
            background-color: rgba(255, 215, 0, 0.12);
            padding: 1rem;
            border-radius: 8px;
            margin-top: 1rem;
        }
        .daily5-help-box {
            background-color: rgba(126, 211, 33, 0.12);
            padding: 0.9rem 1rem;
            border-radius: 8px;
            margin: 0.8rem 0 1.2rem 0;
            font-size: 0.95rem;
        }
        .landing-card {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 14px;
            padding: 1rem;
            margin: 0.8rem 0;
        }

        .landing-muted {
            opacity: 0.85;
            font-size: 0.95rem;
        }

        .landing-cta {
            margin-top: 0.6rem;
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


def init_weak_words(db, user_id, lesson_id):
    if "weak_words" not in st.session_state:
        st.session_state.weak_words = get_weak_words_for_lesson(
            db=db,
            user_id=user_id,
            lesson_id=lesson_id,
        )
        st.session_state.weak_index = 0
        st.session_state.weak_words_lesson_id = lesson_id


def reset_practice_state():
    """Centralised reset for all practice state fields."""
    st.session_state.practice_index = 0


def render_letter_highlight_html(correct_word: str, user_answer: str) -> str:
    """UI-only: render correct_word with per-letter classes based on user_answer positional match."""
    if correct_word is None:
        correct_word = ""
    if user_answer is None:
        user_answer = ""

    cw_display = str(correct_word)
    ua_value = str(user_answer)

    cw = cw_display.lower()
    ua = ua_value.lower()

    spans = []
    for i, ch in enumerate(cw_display):
        user_ch = ua[i] if i < len(ua) else None
        cls = "letter-ok" if (user_ch is not None and user_ch == cw[i]) else "letter-bad"
        spans.append(f"<span class='letter-span {cls}'>{html.escape(ch)}</span>")

    return "".join(spans)


def render_hint_block(hint: str):
    """
    Collapsible hint shown before submission.
    Auto-hides after submit.
    Font aligned with masked word.
    """
    if not hint:
        return

    if not st.session_state.get("show_hint", True):
        return

    with st.expander("💡 Hint"):
        st.markdown(
            f"""
            <div style="
                font-size:26px;
                font-weight:600;
                letter-spacing:2px;
                background:#0f172a;
                padding:14px 18px;
                border-radius:12px;
                margin-top:8px;
                text-align:center;
                color:#9ca3af;
            ">
                {escape(str(hint))}
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_spelling_question(
    word: str,
    example_sentence: str = None,
    hint: str = None,
    word_id: int = None,
    on_next=None,
):
    if "word_state" not in st.session_state:
        st.session_state.word_state = "editing"
    if "result_processed" not in st.session_state:
        st.session_state.result_processed = False
    if "start_time" not in st.session_state:
        st.session_state.start_time = time.time()
    if "correct_streak" not in st.session_state:
        st.session_state.correct_streak = 0
    if "recent_results" not in st.session_state:
        st.session_state.recent_results = []
    if "difficulty_level" not in st.session_state:
        st.session_state.difficulty_level = 2
    if "earned_badges" not in st.session_state:
        st.session_state.earned_badges = set()
    if "attempts_total" not in st.session_state:
        st.session_state.attempts_total = 0
    if "correct_total" not in st.session_state:
        st.session_state.correct_total = 0

    wid = word_id or st.session_state.get("current_wid")
    if st.session_state.get("current_wid") != wid:
        st.session_state.current_wid = wid
        st.session_state.word_state = "editing"
        st.session_state.result_processed = False
        st.session_state.show_hint = True

    st.session_state.current_example_sentence = example_sentence
    st.session_state.current_hint = hint

    st.subheader("Spell the word:")

    if st.session_state.get("streak", 0) > 0:
        st.markdown(
            f"🔥 <b>{st.session_state.streak}-day streak!</b>",
            unsafe_allow_html=True,
        )

    blanks_count = blanks_for_streak(
        st.session_state.get("streak", 0), len(word)
    )

    masked_word, _ = generate_missing_letter_question(
        word,
        base_blanks=blanks_count,
        max_blanks=blanks_count,
    )

    answer_submitted = st.session_state.word_state == "submitted"
    st.session_state.answer_submitted = answer_submitted

    if not answer_submitted:
        st.markdown(
            f"<div class='practice-word'>{masked_word}</div>",
            unsafe_allow_html=True,
        )
    else:
        highlight_html = render_letter_highlight_html(
            word, st.session_state.get(f"input_{wid}", "")
        )
        st.markdown(
            f"<div class='practice-answer'>{highlight_html}</div>",
            unsafe_allow_html=True,
        )

    render_hint_block(st.session_state.get("current_hint"))

    st.caption(f"Difficulty: {blanks_count} blanks")

    if "submitted" not in st.session_state:
        st.session_state.submitted = False
        st.session_state.checked = False
        st.session_state.correct = False

    if not answer_submitted:
        user_input = st.text_input(
            "Type the complete word",
            key=f"input_{wid}",
        )

    if st.session_state.word_state == "editing":
        if "submit_disabled" not in st.session_state:
            st.session_state.submit_disabled = False

        submit_col, _ = st.columns([1, 1])

        with submit_col:
            if not answer_submitted:
                if st.button(
                    "✅ Submit", key=f"submit_{wid}", disabled=st.session_state.submit_disabled
                ):
                    st.session_state.submit_disabled = True
                    st.session_state.action_lock = True
                    is_correct = user_input.lower() == word.lower()

                    time_taken = int(time.time() - st.session_state.start_time)
                    blanks_count = masked_word.count("_")

                    if wid is not None:
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
                    st.session_state.show_hint = False
                    st.session_state.submit_disabled = False

                    st.experimental_rerun()

    if answer_submitted:
        is_correct = st.session_state.get("last_result_correct", False)

        if is_correct:
            st.success("✅ Correct!")
        else:
            st.error(f"❌ Not quite right — the correct answer is “{word}”")

        if example_sentence:
            safe_example = escape(str(example_sentence))
            st.markdown(
                f"""
                <div class="example-box">
                    📘 <strong>Example sentence:</strong><br>
                    {safe_example}
                </div>
                """,
                unsafe_allow_html=True,
            )

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

    if st.session_state.word_state == "submitted" and st.session_state.get("action_lock"):
        st.session_state.action_lock = False

    if "next_disabled" not in st.session_state:
        st.session_state.next_disabled = False

    if st.session_state.answer_submitted:
        next_col, _ = st.columns([1, 1])

        with next_col:
            if st.button("➡️ Next", key=f"next_{wid}", disabled=st.session_state.next_disabled):

                st.session_state.next_disabled = True

                st.session_state.action_lock = True
                if on_next is not None:
                    on_next(st.session_state.get("last_result_correct"))
                st.session_state.word_state = "editing"
                st.session_state.start_time = time.time()
                st.session_state.show_hint = True

                for k in list(st.session_state.keys()):
                    if k.startswith("input_") or k.startswith("submit_"):
                        del st.session_state[k]

                st.session_state.current_wid = None
                st.session_state.current_word_pick = None
                st.session_state.result_processed = False
                st.session_state.action_lock = False

                st.session_state.next_disabled = False

                st.experimental_rerun()


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

    with get_engine_safe().connect() as conn:
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
        st_module.session_state.page = "home"
        return True

    return False


def logout(st_module):
    cleanup_keys = SESSION_KEYS + [
        "practice_mode",
        "current_wid",
        "current_word_pick",
        "word_state",
        "result_processed",
        "hint_level",
        "hint_used",
        "current_example_sentence",
        "action_lock",
    ]

    for key in cleanup_keys:
        if key in st_module.session_state:
            del st_module.session_state[key]
    initialize_session_state(st_module)


###########################################################
#  STUDENT PORTAL FUNCTIONS
###########################################################


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
    st.title("Welcome to SpellingSprint!")
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
#  REGISTRATION SUBMIT HANDLER
###########################################################


def submit_registration():
    full_name = st.session_state.get("reg_full_name")
    email = st.session_state.get("reg_email")
    token = st.session_state.get("registration_token")

    if not full_name or not email:
        st.error("Please enter both name and email.")
        return

    if not token:
        token = generate_registration_token()
        st.session_state.registration_token = token

    try:
        create_pending_registration(
            student_name=full_name,
            email=email,
            token=token,
        )

        # Mark registration as successful
        st.session_state.registration_success = True

    except Exception as e:
        st.error("Registration failed. Please try again or contact support.")
        st.exception(e)


###########################################################
#  MODE SELECTOR (Practice / Review / Test)
###########################################################

def ensure_default_mode():
    """
    Ensure we always have a valid practice_mode in session.
    """
    if "practice_mode" not in st.session_state:
        st.session_state.practice_mode = "lesson"
    elif (
        st.session_state.practice_mode not in PRACTICE_MODES
        and st.session_state.practice_mode not in VALID_PRACTICE_MODES
    ):
        st.session_state.practice_mode = "lesson"
    elif st.session_state.practice_mode == "Daily 5":
        st.session_state.practice_mode = "lesson"


def normalized_practice_mode():
    return (st.session_state.get("practice_mode") or "practice").lower()


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
        st.session_state.page = "practice"
        st.experimental_rerun()


def render_mode_cards(db, user_id, selected_lesson_id):
    st.markdown("### 🎯 What would you like to do today?")
    c1, _ = st.columns(2)

    with c1:
        if st.button("✏️ Practice", use_container_width=True):
            st.session_state.active_mode = "practice"
            st.session_state.mode = "Practice"
            st.session_state.practice_mode = "Practice"
            st.session_state.page = "practice"
            st.experimental_rerun()


def render_student_home(db, user_id: int) -> None:
    # Fetch admin-managed content (ALWAYS)
    title = _get_student_home_text(db, "student_home_title", "Welcome")
    intro = _get_student_home_text(db, "student_home_intro", "")
    practice_txt = _get_student_home_text(db, "student_home_practice", "")
    weak_txt = _get_student_home_text(db, "student_home_weak_words", "")
    show_weak_words = user_has_any_mistakes(st.session_state.user_id)

    st.markdown(f"## {title}")
    st.markdown(intro)
    st.markdown("---")

    # Practice section (always)
    st.markdown("### ✏️ Practice")
    st.markdown(practice_txt)
    if st.button("Start Practice"):
        st.session_state.page = "practice"
        st.experimental_rerun()

    # Weak Words section (conditional)
    if show_weak_words:
        st.markdown("### 🧠 Weak Words")
        st.markdown(weak_txt)
        if st.button("Start Weak Words"):
            prepared = prepare_system_weak_words_lesson_for_user(
                user_id=user_id,
                limit=50,
            )
            # --- WEAK WORDS FIX (DO NOT TOUCH OTHER FLOWS) ---
            word_ids = prepared.get("word_ids", [])

            if not word_ids:
                st.info("No weak words yet — great job!")
                return

            # Reuse existing helper (already used elsewhere)
            words = get_words_by_ids(word_ids)

            if not words:
                st.warning("Weak words exist but could not be loaded.")
                return

            st.session_state.weak_word_pool = words
            st.session_state.weak_word_index = 0
            # ------------------------------------------------


def render_practice_question(word_ids: list[int]) -> None:
    if "practice_index" not in st.session_state or st.session_state.practice_index is None:
        st.session_state.practice_index = 0

    practice_word_ids = word_ids
    if not practice_word_ids:
        st.info("No practice words are available right now.")
        st.stop()

    practice_index = st.session_state.practice_index
    if practice_index >= len(practice_word_ids):
        return

    word_id = practice_word_ids[practice_index]

    word_rows = get_words_by_ids([word_id])
    if not word_rows:
        st.warning("No practice words are available right now.")
        return

    current = word_rows[0]

    def handle_next(_):
        st.session_state.practice_index += 1

    render_spelling_question(
        word_id=word_id,
        word=current["word"],
        example_sentence=current.get("example_sentence"),
        hint=current.get("hint"),
        on_next=handle_next,
    )


def render_weak_words_page(user_id: int) -> None:
    st.title("🧠 Weak Words")

    word_ids = st.session_state.get("weak_word_ids", [])

    if not word_ids:
        st.info("No weak words yet — great job!")
        return

    # Weak words must NOT be course-filtered
    words = get_words_by_ids(
        [int(wid) for wid in word_ids if wid is not None]
    )

    # SAFETY: RowMapping / tuple → dict
    clean_words = []
    for w in words:
        if hasattr(w, "_mapping"):
            clean_words.append(dict(w._mapping))
        elif isinstance(w, dict):
            clean_words.append(w)

    if not clean_words:
        st.warning("Weak words exist but could not be loaded.")
        return

    st.session_state.weak_word_pool = clean_words
    st.session_state.weak_word_index = 0

    idx = st.session_state.get("weak_index", 0)

    if idx >= len(words):
        st.success("🎉 You’ve completed all weak words!")
        return

    current = words[idx]

    def _next(correct: bool):
        if correct:
            st.session_state.weak_index = idx + 1

    render_spelling_question(
        word=current["word"],
        example_sentence=current.get("example_sentence"),
        hint=current.get("hint"),
        word_id=current["word_id"],
        on_next=_next,
    )


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
    lesson_name = (
        st.session_state.get("selected_lesson")
        or st.session_state.get("active_lesson_name")
    )

    if not cid or not lesson_id:
        st.error("No lesson selected. Choose from the lesson catalogue.")
        st.session_state.page = "practice"
        st.experimental_rerun()
        return

    st.markdown(f"### Lesson: **{lesson_name}**")

    words = get_words_for_lesson(lesson_id, cid)
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
            st.session_state.page = "practice"
            st.experimental_rerun()
        return

    current = words[index]
    current_word = current["word"]
    word_id = current.get("word_id")
    pattern = current.get("pattern") or ""
    level = current.get("level")

    st.session_state.current_example_sentence = current.get("example_sentence")
    st.session_state.current_hint = current.get("hint")
    # Initialise hint visibility ONLY when word changes
    if st.session_state.get("current_wid") != word_id:
        st.session_state.show_hint = True

    info_bits = []
    if level is not None:
        info_bits.append(f"Level {level}")
    if pattern:
        info_bits.append(f"Pattern: {pattern}")

    if info_bits:
        st.caption(" • ".join(info_bits))


    if normalized_practice_mode() != "daily-5":
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

    # --- HINT (collapsible, auto-hide after submit) ---
    render_hint_block(st.session_state.get("current_hint"))

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
    if st.session_state.get("submitted") and st.session_state.get("action_lock"):
        st.session_state.action_lock = False
    action_lock = st.session_state.get("action_lock", False)

    if not st.session_state.submitted:
        with action_col:
            submit_clicked = st.button(
                "✅ Submit",
                use_container_width=True,
                disabled=action_lock,
            )

    if submit_clicked and not action_lock:
        st.session_state.action_lock = True
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
        # Auto-hide hint after submission
        st.session_state.show_hint = False

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
            next_clicked = st.button(
                "➡️ Next",
                use_container_width=True,
                disabled=action_lock,
            )

    if next_clicked and not action_lock:
        st.session_state.action_lock = True
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
        # Re-enable hint for next word
        st.session_state.show_hint = True
        st.session_state.current_example_sentence = None
        st.session_state.hint_used = False
        st.session_state.wrong_attempts = 0
        st.session_state.user_input = ""

        st.session_state.action_lock = False

        # clear input
        st.session_state[f"answer_{word_id}"] = ""
        del st.session_state[f"answer_{word_id}"]

        # THIS is the only place we move on
        st.session_state.current_wid = None

        st.experimental_rerun()

    st.markdown("---")
    if st.button("🔁 Restart lesson"):
        st.session_state.practice_index = 0
        st.session_state.current_wid = None
        st.session_state.word_state = "editing"

        st.experimental_rerun()

    # Sidebar navigation
    if st.sidebar.button("Back to Courses"):
        st.session_state.practice_index = 0
        st.session_state.page = "practice"
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
            if st.button("Weak Words"):
                # Ensure system weak-words lesson is prepared
                result = prepare_system_weak_words_lesson_for_user(
                    user_id=st.session_state.user_id,
                    limit=50,
                )

                if not result or result.get("word_count", 0) == 0:
                    st.info("No weak words yet — great job!")
                    st.stop()

                # Route into normal lesson engine
                st.session_state.course_id = result["course_id"]
                st.session_state.lesson_id = result["lesson_id"]
                st.session_state.page = "practice"

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

    active_lesson_id = st.session_state.get("active_lesson_id")

    ensure_default_mode()
    practice_mode = st.session_state.get("practice_mode", "Practice") or "Practice"
    st.session_state.practice_mode = practice_mode
    user_id = st.session_state.get("user_id")

    # -----------------------------
    # Session isolation (CRITICAL)
    # -----------------------------
    if "active_mode" not in st.session_state:
        st.session_state.active_mode = "practice"  # "practice" | "weak_words"

    # Practice session state
    if "practice_words" not in st.session_state:
        st.session_state.practice_words = None
    if "practice_index" not in st.session_state:
        st.session_state.practice_index = 0

    # Weak Words session state (separate!)
    if "weak_words" not in st.session_state:
        st.session_state.weak_words = None
    if "weak_index" not in st.session_state:
        st.session_state.weak_index = 0
    if "weak_words_lesson_id" not in st.session_state:
        st.session_state.weak_words_lesson_id = None

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
        resume_index = get_resume_index_for_lesson(
            user_id=st.session_state.user_id,
            lesson_id=lesson_id,
        )
        st.session_state.practice_index = resume_index or 0
        st.session_state["q_index"] = 0
        st.session_state.current_wid = None
        st.session_state.current_word_pick = None
        st.session_state.word_state = "editing"
        st.session_state.practice_lesson_id = lesson_id

    lesson_name = st.session_state.get("active_lesson_name")

    raw_lessons = get_lessons_for_course(course_id) if course_id else []
    lessons = [row_to_dict(r) for r in raw_lessons if row_to_dict(r)]

    for lesson_data in lessons:
        lid = lesson_data.get("lesson_id")
        if not lid:
            continue
        mastery = get_lesson_mastery(
            user_id=user_id,
            course_id=course_id,
            lesson_id=lid,
        )
        lesson_data["progress_pct"] = mastery

    lesson_lookup = {l.get("lesson_id"): l for l in lessons if l.get("lesson_id")}
    lesson = lesson_lookup.get(lesson_id, {})

    if not lesson_name:
        lesson_name = lesson.get("display_name") or lesson.get("lesson_name")

    mastery = lesson.get("progress_pct", 0) or 0
    xp_total, streak = get_xp_and_streak(user_id)
    badge = compute_badge(xp_total, mastery)

    if lesson_name:
        st.header(f"{lesson_name}  {badge}")
        st.progress(mastery / 100)
        st.caption(f"Mastery: {mastery}% | XP: {xp_total} | Streak: {streak} days")

    selected_lesson_id = (
        st.session_state.get("selected_lesson_id")
        or st.session_state.get("active_lesson_id")
    )

    with get_engine_safe().connect() as db:
        render_mode_cards(
            db=db,
            user_id=user_id,
            selected_lesson_id=selected_lesson_id,
        )

    active_lesson_id = st.session_state.get("active_lesson_id") or lesson_id
    st.session_state.active_lesson_id = active_lesson_id

    if st.session_state.active_mode == "weak_words":
        # Build weak words ONCE per lesson per entry
        if st.session_state.weak_words_lesson_id != active_lesson_id:
            st.session_state.weak_words = None
            st.session_state.weak_index = 0
            st.session_state.weak_words_lesson_id = active_lesson_id
        if st.session_state.weak_words is not None and not st.session_state.weak_words:
            st.info("No weak words for this lesson yet 👍")
            if st.button("▶️ Go to Practice"):
                st.session_state.active_mode = "practice"
                st.session_state.practice_mode = "Practice"
                st.session_state.page = "practice"
                st.experimental_rerun()
            st.stop()
        if st.session_state.weak_words is None:
            if st.session_state.get("mode") == "weak_words":
                practice_word_ids = st.session_state.get("practice_word_pool", [])
            else:
                practice_word_ids = get_words_for_lesson(course_id, lesson_id)

            if not practice_word_ids:
                st.info("No practice words are available right now.")
                st.stop()

            if st.session_state.get("mode") == "weak_words":
                weak_rows = get_words_by_ids(practice_word_ids)
            else:
                weak_rows = practice_word_ids

            if not weak_rows:
                if st.session_state.get("mode") == "weak_words":
                    st.info("No practice words are available right now.")
                    st.stop()
                st.info("No weak words for this lesson yet 👍")
                if st.button("▶️ Go to Practice"):
                    st.session_state.active_mode = "practice"
                    st.session_state.practice_mode = "Practice"
                    st.session_state.page = "practice"
                    st.experimental_rerun()
                st.stop()

            weak_words = []
            for r in weak_rows:
                m = getattr(r, "_mapping", r)
                weak_words.append({
                    "word_id": m["word_id"],
                    "word": m["word"],
                    "pattern": m.get("pattern"),
                    "pattern_code": m.get("pattern_code"),
                    "example_sentence": m.get("example_sentence"),
                    "hint": m.get("hint"),
                })

            st.session_state.weak_words = weak_words
            st.session_state.weak_index = 0
            st.session_state.weak_words_lesson_id = active_lesson_id

        words = st.session_state.weak_words
        idx = st.session_state.weak_index
    else:
        if st.session_state.practice_words is None:
            words = get_words_for_lesson(lesson_id, course_id)
            practice_words = _fetch_spelling_words(lesson_id)

            if not words:
                if not practice_words:
                    st.warning("No practice words are mapped to this lesson yet.")
                    return
                words = practice_words

            st.session_state.practice_words = words
            st.session_state.practice_index = 0

        words = st.session_state.practice_words
        idx = st.session_state.practice_index

    signals_map = get_cached_word_signals(
        user_id=user_id,
        course_id=course_id,
        lesson_id=lesson_id,
    )
    stats_map = build_stats_map(signals_map)
    difficulty_map = build_difficulty_map(words, stats_map)
    weak_word_ids = get_weak_word_ids(stats_map)

    if normalized_practice_mode() == "daily-5":
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

    is_weak_mode = st.session_state.active_mode == "weak_words"
    if normalized_practice_mode() == "daily-5":
        practice_words = st.session_state.get("daily5_words", [])
        total_words = len(practice_words)
        daily5_index = st.session_state.get("daily5_index", 0)
        current_index = min(daily5_index, total_words - 1) if total_words else 0
    else:
        practice_words = words
        total_words = len(practice_words)
        current_index = min(idx, total_words - 1) if total_words else 0

    total_words = len(practice_words)
    progress = (current_index + 1) / total_words if total_words else 0

    if progress < 0.3:
        bar_color = "#ef4444"
    elif progress < 0.7:
        bar_color = "#f59e0b"
    else:
        bar_color = "#22c55e"

    if normalized_practice_mode() == "daily-5":
        daily5_words = st.session_state.get("daily5_words", [])

        if st.session_state.daily5_index >= len(daily5_words):
            st.success("🎉 Daily 5 complete!")

            # Daily 5 cleanup (hardening)
            st.session_state.pop("daily5_words", None)
            st.session_state.pop("daily5_index", None)
            st.session_state.daily5_active = False
            st.session_state.practice_mode = "lesson"

            st.experimental_rerun()
        else:
            word_row = daily5_words[
                st.session_state.daily5_index
            ]
            current = row_to_dict(word_row)
            st.session_state.current_wid = current["word_id"]
            st.session_state.current_word_pick = current
            st.session_state.start_time = time.time()
            st.session_state.action_lock = False
    else:
        if st.session_state.active_mode == "weak_words":
            if st.session_state.weak_index >= len(words):
                st.success("🎉 You’ve completed all weak words for this lesson!")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🔁 Restart weak words"):
                        st.session_state.weak_index = 0
                        st.experimental_rerun()
                with col2:
                    if st.button("▶️ Go to Practice"):
                        st.session_state.active_mode = "practice"
                        st.session_state.practice_mode = "Practice"
                        st.session_state.page = "practice"
                        st.experimental_rerun()
                st.stop()
        else:
            if st.session_state.practice_index >= len(words):
                st.success("✅ Practice completed for this lesson!")
                st.stop()

        if st.session_state.current_wid is None:
            current = practice_words[idx]
            st.session_state.current_wid = current["word_id"]
            st.session_state.current_word_pick = current
            st.session_state.start_time = time.time()
            st.session_state.action_lock = False
        else:
            current = st.session_state.get("current_word_pick") or practice_words[current_index]
            st.session_state.current_word_pick = current

    wid = st.session_state.current_wid
    mode = st.session_state.get("mode")
    if mode != "weak_words":
        lesson_word_ids = {w.get("word_id") for w in words if w.get("word_id")}
        if lesson_id and wid not in lesson_word_ids:
            st.warning("Word not mapped to this lesson. Skipping.")
            return
    st.session_state.current_example_sentence = current.get("example_sentence")
    st.session_state.current_hint = current.get("hint")
    # Initialise hint visibility ONLY when word changes
    if st.session_state.get("current_wid") != wid:
        st.session_state.show_hint = True

    target_word = current["word"]
    st.session_state["last_word_id"] = wid
    if is_weak_mode:
        total_weak_words = len(practice_words)
        st.caption(f"{idx + 1} / {total_weak_words}")
    else:
        if normalized_practice_mode() == "daily-5":
            st.caption(f"Daily 5 — {st.session_state.get('daily5_index', 0) + 1} / 5")
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

    def handle_next(_):
        if st.session_state.active_mode == "weak_words":
            st.session_state.weak_index += 1
        else:
            st.session_state.practice_index += 1
        if normalized_practice_mode() == "daily-5":
            st.session_state.daily5_index += 1

    render_spelling_question(
        word_id=wid,
        word=target_word,
        example_sentence=current.get("example_sentence"),
        hint=current.get("hint"),
        on_next=handle_next,
    )


###########################################################
#  MAIN APP CONTROLLER
###########################################################

def main():
    if "registration_success" not in st.session_state:
        st.session_state.registration_success = False

    if "registration_token" not in st.session_state:
        st.session_state.registration_token = generate_registration_token()

    inject_student_css()
    initialize_session_state(st)

    if "page" not in st.session_state or st.session_state.page is None:
        st.session_state.page = "home"
    elif st.session_state.page not in {"home", "practice", "weak_words"}:
        st.session_state.page = "home"

    if "mode" not in st.session_state:
        st.session_state.mode = None
    if "action_lock" not in st.session_state:
        st.session_state.action_lock = False

    st.title("SpellingSprint")

    # NOT LOGGED IN → show Login + Registration tabs
    if not st.session_state.is_logged_in:
        with get_engine_safe().connect() as db:
            banner_data, tagline_text, value_text, register_text, support_text = get_landing_content(db)

        # Branding
        if banner_data:
            st.image(banner_data, use_column_width=True)

        st.markdown(
            f"<div class='landing-card'><div class='landing-muted' style='text-align:center;'>{tagline_text}</div></div>",
            unsafe_allow_html=True,
        )

        # Value proposition
        st.markdown(
            f"<div class='landing-card'><strong>Why SpellingSprint?</strong><br><br>{value_text.replace(chr(10), '<br>')}</div>",
            unsafe_allow_html=True,
        )

        st.markdown("<div class='landing-card'>", unsafe_allow_html=True)
        st.subheader("Login")

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

        with st.expander("➕ New to SpellingSprint? Create an account"):
            st.markdown(
                f"<div class='landing-card'><strong>Registration</strong><br><br>{register_text.replace(chr(10), '<br>')}</div>",
                unsafe_allow_html=True,
            )

            st.markdown("<div class='landing-card'>", unsafe_allow_html=True)

            st.markdown("## Secure Checkout")

            checkout_url = f"{PAYPAL_CHECKOUT_URL}?custom_id={st.session_state.get('registration_token')}"

            st.markdown(
                f"""
                <div style="text-align:center; margin: 24px 0;">
                    <a href="{checkout_url}" target="_blank"
                       style="
                         display:inline-flex;
                         align-items:center;
                         justify-content:center;
                         gap:10px;
                         background-color:#ffc439;
                         color:#111;
                         font-weight:600;
                         padding:14px 28px;
                         border-radius:8px;
                         text-decoration:none;
                         font-size:16px;
                         box-shadow:0 4px 10px rgba(0,0,0,0.25);
                       ">
                       <img src="https://www.paypalobjects.com/webstatic/icon/pp258.png"
                            alt="PayPal"
                            style="height:22px;">
                       Buy Now with PayPal
                    </a>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown("### Submit your details")
            st.caption(
                "After payment, enter your details once to complete registration."
            )

            if st.session_state.get("registration_success"):
                st.success("✅ Registration submitted successfully!")

                st.markdown(
                    """
                    **What happens next?**
                    - We’ve received your details  
                    - Our team will verify your payment  
                    - Your account will be activated shortly  

                    You can safely close this page for now.
                    """
                )

            else:
                st.text_input("Full name", key="reg_full_name")
                st.text_input("Email address", key="reg_email")

                if st.button("Submit registration"):
                    submit_registration()
            st.markdown("</div>", unsafe_allow_html=True)

        with st.expander("Need help?"):
            st.markdown(
                f"<div class='landing-card'>{support_text.replace(chr(10), '<br>')}</div>",
                unsafe_allow_html=True,
            )

        return  # stop here when logged out

    # LOGGED IN
    st.sidebar.markdown(f"### 👤 Hi, {st.session_state.user_name}")


    if st.sidebar.button("Logout"):
        logout(st)
        # Session hard reset on logout (hardening)
        for key in [
            "practice_mode",
            "answer_submitted",
            "weak_page_pool",
            "weak_page_index",
            "weak_page_submitted",
            "weak_page_last_correct",
            "weak_page_current_word_id",
            "weak_page_user_id",
            "weak_page_start_time",
        ]:
            st.session_state.pop(key, None)
        st.experimental_rerun()

    user_id = st.session_state.get("user_id")

    # Pre-warm weak words system lesson (safe, idempotent)
    prepare_system_weak_words_lesson_for_user(
        user_id=st.session_state.user_id,
        limit=50,
    )

    if st.session_state.page == "home":
        with get_engine_safe().connect() as db:
            render_student_home(db, st.session_state.user_id)
        st.stop()

    if st.session_state.page == "weak_words":
        render_weak_words_page(user_id)
        st.stop()

    if st.session_state.page != "practice":
        st.session_state.page = "home"
        st.experimental_rerun()

    st.session_state.active_mode = "practice"

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

        course_labels = [course["course_name"] for course in st.session_state["courses"]]
        course_options = {
            course["course_name"]: course for course in st.session_state["courses"]
        }
        current_index = next(
            (
                i for i, course in enumerate(st.session_state["courses"])
                if course["course_id"] == current_course_id
            ),
            0,
        )
        selected_course_label = st.sidebar.radio(
            "Practice Mode",
            options=course_labels,
            index=current_index,
            key="sidebar_course_switcher",
        )
        selected_course = course_options[selected_course_label]

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
        raw_lessons = get_lessons_for_course(st.session_state.active_course_id)
        lessons = [row_to_dict(r) for r in raw_lessons if row_to_dict(r)]

        lesson_map = {
            l["lesson_id"]: (l.get("display_name") or l.get("lesson_name"))
            for l in lessons
            if l.get("lesson_id") is not None
        }

        selected_lesson_id = st.sidebar.selectbox(
            "Change lesson",
            options=list(lesson_map.keys()),
            format_func=lambda lid: lesson_map[lid],
            index=list(lesson_map.keys()).index(st.session_state.active_lesson_id),
        )

        if selected_lesson_id != st.session_state.active_lesson_id:
            resume_index = get_resume_index_for_lesson(
                user_id=st.session_state.user_id,
                lesson_id=selected_lesson_id,
            )

            st.session_state.active_lesson_id = selected_lesson_id
            st.session_state.practice_index = resume_index or 0
            st.session_state.current_wid = None
            st.session_state.word_state = "editing"

            st.experimental_rerun()

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

    raw_lessons = get_lessons_for_course(active_course_id)

    lessons = []
    for row in raw_lessons:
        lesson_data = row_to_dict(row)
        mastery = get_lesson_mastery(
            user_id=st.session_state.user_id,
            course_id=active_course_id,
            lesson_id=lesson_data["lesson_id"],
        )
        lesson_data["progress_pct"] = mastery
        lessons.append(lesson_data)

    if not lessons:
        st.info("No lessons available in this course yet.")
        return

    st.markdown("### Lesson catalogue")

    header_cols = st.columns([3, 1, 1, 1])
    headers = ["Lesson", "Words", "Status", "Action"]
    for col, label in zip(header_cols, headers):
        col.markdown(f"**{label}**")

    for lesson in lessons:
        progress = lesson.get("progress_pct", 0) or 0
        word_count = lesson.get("word_count", 0)

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
            lesson_label = lesson.get("display_name") or lesson.get("lesson_name")
            st.markdown(f"**{lesson_label}**")
        with row_cols[1]:
            st.markdown(str(word_count))
        with row_cols[2]:
            st.markdown(
                f"<span style='color:{status_color}'>{status}</span>",
                unsafe_allow_html=True,
            )
        with row_cols[3]:
            if st.button("Start", key=f"start_{lesson['lesson_id']}"):
                lesson_id = lesson["lesson_id"]
                user_id = st.session_state.user_id

                resume_index = get_resume_index_for_lesson(
                    user_id=user_id,
                    lesson_id=lesson_id,
                )

                # SINGLE PRACTICE ENTRY CONTRACT (ALL COURSES)
                st.session_state["mode"] = "Practice"
                st.session_state["lesson_started"] = True
                st.session_state["active_lesson_id"] = lesson_id
                st.session_state["active_course_id"] = lesson["course_id"]
                lesson_label = lesson.get("display_name") or lesson.get("lesson_name")
                st.session_state["active_lesson_name"] = lesson_label
                st.session_state["selected_lesson"] = lesson_label

                # Reset practice state
                st.session_state["practice_index"] = resume_index or 0
                st.session_state["q_index"] = 0
                st.session_state["current_input"] = ""
                st.session_state["show_feedback"] = False
                st.session_state["current_wid"] = None
                st.session_state["word_state"] = "editing"

                st.experimental_rerun()


if __name__ == "__main__":
    main()
