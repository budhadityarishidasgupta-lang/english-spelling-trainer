import random
from typing import Any, Iterable, Mapping, Optional

import streamlit as st

from shared.db import execute


def _word_id(word_row: Any) -> Optional[int]:
    mapping: Any = getattr(word_row, "_mapping", word_row)

    if isinstance(mapping, Mapping):
        return mapping.get("word_id") or mapping.get("id")

    return getattr(word_row, "word_id", None) or getattr(word_row, "id", None)


def mask_word(word: str) -> str:
    clean = word.strip()
    if len(clean) <= 3:
        if len(clean) == 3:
            return clean[0] + "_" + clean[2]
        if len(clean) == 2:
            return clean[0] + "_"
        return "_"

    letters = list(clean)
    inner_indices = list(range(1, len(letters) - 1))
    blanks = min(3, max(1, len(inner_indices) // 3))

    rnd = random.Random(hash(clean))
    for idx in rnd.sample(inner_indices, blanks):
        letters[idx] = "_"

    return "".join(letters)


def choose_next_word(
    words: Iterable[Any],
    difficulty_map: Mapping[int, str],
    current_level: str,
    weak_word_ids: Iterable[int],
    last_word_id: Optional[int],
) -> Optional[Any]:
    weak_set = set(weak_word_ids or [])
    available = []

    for word_row in words:
        wid = _word_id(word_row)
        if wid is None or wid == last_word_id:
            continue

        difficulty = difficulty_map.get(wid)
        is_current_level = difficulty == current_level if difficulty is not None else True
        available.append((wid in weak_set, is_current_level, word_row))

    for is_weak, _, word_row in available:
        if is_weak:
            return word_row

    for _, matches_level, word_row in available:
        if matches_level:
            return word_row

    return available[0][2] if available else None


def record_attempt(
    user_id: int,
    word_id: int,
    correct: bool,
    time_taken: int,
    blanks_count: int,
    wrong_letters_count: int,
) -> None:
    try:
        execute(
            """
            INSERT INTO spelling_attempts (
                user_id,
                word_id,
                correct,
                time_taken,
                blanks_count,
                wrong_letters_count
            )
            VALUES (
                :user_id,
                :word_id,
                :correct,
                :time_taken,
                :blanks_count,
                :wrong_letters_count
            )
            """,
            {
                "user_id": user_id,
                "word_id": word_id,
                "correct": correct,
                "time_taken": time_taken,
                "blanks_count": blanks_count,
                "wrong_letters_count": wrong_letters_count,
            },
        )
    except Exception:
        attempts = st.session_state.setdefault("practice_attempt_log", [])
        attempts.append(
            {
                "user_id": user_id,
                "word_id": word_id,
                "correct": correct,
                "time_taken": time_taken,
                "blanks_count": blanks_count,
                "wrong_letters_count": wrong_letters_count,
            }
        )


def render_practice_mode(
    *,
    mode: str,
    words: Iterable[Any],
    difficulty_map: Mapping[int, str],
    weak_word_ids: Iterable[int],
    selected_course_id: int,
    selected_lesson_id: int,
):
    import time

    if "submitted" not in st.session_state:
        st.session_state.submitted = False

    if "checked" not in st.session_state:
        st.session_state.checked = False

    if "correct" not in st.session_state:
        st.session_state.correct = False

    if "start_time" not in st.session_state:
        st.session_state.start_time = time.time()

    # ---------------------------------------------------------
    # LOCK CURRENT WORD PER (mode, course, lesson)
    # Streamlit reruns on every keystroke, so we must NOT re-pick.
    # ---------------------------------------------------------
    ctx = f"{mode}_{selected_course_id}_{selected_lesson_id}"
    current_wid_key = f"{ctx}_current_wid"
    last_wid_key = f"{ctx}_last_wid"

    if current_wid_key not in st.session_state:
        st.session_state[current_wid_key] = None

    # Pick a word ONCE when there is no locked word
    if st.session_state[current_wid_key] is None:
        last_word_id = st.session_state.get(last_wid_key)
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
        st.session_state[current_wid_key] = wid

    # Resolve locked word from list
    wid = st.session_state[current_wid_key]
    row = next((w for w in words if _word_id(w) == wid), None)
    if not row:
        # If the list changed, unlock and try again
        st.session_state[current_wid_key] = None
        return

    m_word = getattr(row, "_mapping", row)
    target_word = m_word["word"]

    if st.session_state.get("active_word_id") != wid:
        st.session_state["active_word_id"] = wid

    masked_word = mask_word(target_word)

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
        ">
            {masked_word}
        </div>
        """,
        unsafe_allow_html=True,
    )

    user_answer = st.text_input(
        "Type the complete word",
        key=f"answer_{wid}",
        disabled=st.session_state.checked,
    )

    if not st.session_state.submitted:
        if st.button("✅ Submit"):
            time_taken = int(time.time() - st.session_state.start_time)

            is_correct = user_answer.strip().lower() == target_word.lower()

            record_attempt(
                user_id=st.session_state.user_id,
                word_id=wid,
                correct=is_correct,
                time_taken=time_taken,
                blanks_count=masked_word.count("_"),
                wrong_letters_count=0 if is_correct else 1,
            )

            st.session_state.submitted = True
            st.session_state.checked = True
            st.session_state.correct = is_correct

    if st.session_state.checked:
        if st.session_state.correct:
            st.success("🎉 Correct! Great job!")
            st.info("⭐ You earned 10 XP")
        else:
            st.error("😅 Not quite right — keep going!")

    if st.session_state.checked:
        if st.button("➡️ Next"):
            # mark last word ONLY when user chooses to advance
            st.session_state[last_wid_key] = wid

            # unlock next word so a new pick happens
            st.session_state[current_wid_key] = None

            # reset state
            st.session_state.submitted = False
            st.session_state.checked = False
            st.session_state.correct = False
            st.session_state.start_time = time.time()

            # clear input
            del st.session_state[f"answer_{wid}"]

            st.experimental_rerun()
