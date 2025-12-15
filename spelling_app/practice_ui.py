import time
import random
import streamlit as st

from shared.auth import get_logged_in_user
from spelling_app.services.spelling_service import (
    load_items,
    record_attempt,
)


def _mask_word(base_word: str) -> str:
    """
    Mask inner letters of the word for missing-letter gameplay.
    Keeps first and last letter visible, hides 1–3 inner letters
    depending on length.
    """
    word = base_word.strip()
    if len(word) <= 3:
        # For very short words, hide the middle letter (if exists)
        if len(word) == 3:
            return word[0] + "_" + word[2]
        elif len(word) == 2:
            return word[0] + "_"
        else:
            return "_"

    letters = list(word)
    inner_indices = list(range(1, len(letters) - 1))

    # Number of blanks scales with length, min 1, max 3
    blanks = min(3, max(1, len(inner_indices) // 3))

    rnd = random.Random(hash(word))  # deterministic per word for session
    for idx in rnd.sample(inner_indices, blanks):
        letters[idx] = "_"

    return "".join(letters)


def _init_practice_state(lesson_id: int, course_id: int, lesson_title: str):
    if "practice_state" not in st.session_state:
        st.session_state["practice_state"] = {}

    state = st.session_state["practice_state"]
    if state.get("lesson_id") != lesson_id:
        # Fresh state for a new lesson
        items_result = load_items(lesson_id)

        # Expect load_items to return a list of dict-like rows
        if isinstance(items_result, dict) and "error" in items_result:
            st.error("Error loading words for this lesson: " + str(items_result))
            return None

        # Normalize to plain dicts
        items: list[dict] = []
        for row in items_result:
            mapping = getattr(row, "_mapping", row)
            items.append(dict(mapping))

        if not items:
            st.info("No items found for this lesson yet.")
            return None

        state["lesson_id"] = lesson_id
        state["course_id"] = course_id
        state["lesson_title"] = lesson_title
        state["items"] = items
        state["index"] = 0
        state["correct_count"] = 0
        state["attempts"] = []
        state["start_ts"] = time.time()
        state["finished"] = False

    return st.session_state["practice_state"]


def _render_summary(state):
    total = len(state["items"])
    correct = state["correct_count"]
    incorrect = total - correct
    score_pct = round((correct / total) * 100) if total > 0 else 0

    st.success(f"Lesson complete! Score: {correct}/{total} ({score_pct}%)")

    if incorrect > 0:
        st.subheader("Words to Review")
        weak_rows = [a for a in state["attempts"] if not a["is_correct"]]
        for a in weak_rows:
            st.markdown(
                f"- **{a['base_word']}** — you typed: `{a['typed']}`"
            )

    if st.button("Restart Lesson"):
        # Reset for same lesson
        lesson_id = state["lesson_id"]
        course_id = state["course_id"]
        lesson_title = state["lesson_title"]
        # Clear and re-init
        del st.session_state["practice_state"]
        _init_practice_state(lesson_id, course_id, lesson_title)


def render_practice_screen(lesson_id: int, course_id: int, lesson_title: str):
    """
    Main entry for masked spelling practice.
    Called from app.py when session_state['page'] == 'practice'.
    """
    if "answered" not in st.session_state:
        st.session_state.answered = False

    if "is_correct" not in st.session_state:
        st.session_state.is_correct = None

    if "selected_answer" not in st.session_state:
        st.session_state.selected_answer = None

    st.markdown(
        """
        <style>
        .feedback-card {
            padding: 1.2rem;
            border-radius: 14px;
            margin-top: 1rem;
            font-size: 1.05rem;
            font-weight: 600;
            animation-duration: 0.6s;
            animation-fill-mode: both;
        }

        .correct-card {
            background: linear-gradient(135deg, #d4f8e8, #b2f2d6);
            border: 2px solid #2ecc71;
            color: #145a32;
            animation-name: fadeSlideUp;
        }

        .wrong-card {
            background: linear-gradient(135deg, #fde2e2, #f8caca);
            border: 2px solid #e74c3c;
            color: #7b241c;
            animation-name: fadeShake;
        }

        @keyframes fadeSlideUp {
            from {
                opacity: 0;
                transform: translateY(12px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes fadeShake {
            0% { opacity: 0; transform: translateX(0); }
            30% { transform: translateX(-6px); }
            60% { transform: translateX(6px); }
            100% { opacity: 1; transform: translateX(0); }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    user = get_logged_in_user()
    if not user:
        st.error("You must be logged in to practice this lesson.")
        return

    student_id = user["id"]

    state = _init_practice_state(lesson_id, course_id, lesson_title)
    if state is None:
        return

    if state.get("index") == 0 and not state.get("attempts"):
        st.session_state.answered = False
        st.session_state.is_correct = None
        st.session_state.selected_answer = None

    st.title(f"✏️ Spelling Practice — {lesson_title}")

    if state.get("finished"):
        _render_summary(state)
        return

    items = state["items"]
    idx = state["index"]

    if idx >= len(items):
        state["finished"] = True
        _render_summary(state)
        return

    current = items[idx]
    # Try to pick the word field: base_word preferred, fallback to display_form
    base_word = (
        current.get("base_word")
        or current.get("display_form")
        or current.get("word")
        or ""
    )

    masked = _mask_word(base_word)

    st.subheader(f"Word {idx + 1} of {len(items)}")
    st.markdown(f"**Complete the word:** `{masked}`")

    answer_key = f"practice_answer_{lesson_id}_{idx}"
    typed = st.text_input(
        "Type the full, correct spelling:",
        key=answer_key,
        disabled=st.session_state.answered,
    )

    if st.button("Submit", disabled=st.session_state.answered, type="primary"):
        typed_clean = (st.session_state.get(answer_key) or "").strip()
        is_correct = typed_clean.lower() == base_word.lower()
        st.session_state.selected_answer = typed_clean
        st.session_state.is_correct = is_correct
        st.session_state.answered = True

        response_ms = int((time.time() - state.get("start_ts", time.time())) * 1000)

        # Save attempt to DB
        item_id = current.get("sp_item_id") or current.get("item_id") or current.get("id")
        record_attempt(
            user_id=student_id,
            course_id=course_id,
            lesson_id=lesson_id,
            item_id=item_id,
            typed_answer=typed_clean,
            correct=is_correct,
            response_ms=response_ms,
        )

        if is_correct:
            state["correct_count"] += 1

        state["attempts"].append(
            {
                "base_word": base_word,
                "typed": typed_clean,
                "is_correct": is_correct,
            }
        )

    if st.session_state.answered and st.session_state.is_correct:
        st.markdown(
            """
            <div class="feedback-card correct-card">
                🎉 Correct! Excellent work — keep going!
            </div>
            """,
            unsafe_allow_html=True,
        )

    if st.session_state.answered and st.session_state.is_correct is False:
        st.markdown(
            f"""
            <div class="feedback-card wrong-card">
                😅 Not quite right — the correct answer is <strong>{base_word}</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if st.session_state.answered:
        if st.button("Next ➡️"):
            state["index"] += 1
            state["start_ts"] = time.time()

            st.session_state.answered = False
            st.session_state.is_correct = None
            st.session_state.selected_answer = None
            st.session_state.pop(answer_key, None)

            if state["index"] >= len(items):
                state["finished"] = True
            st.rerun()
