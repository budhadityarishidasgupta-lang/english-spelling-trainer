import random
import time
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


def render_masked_word_input(masked_word, correct_word, key_prefix, blank_indices):
    """
    Udemy-style: render masked word in ONE horizontal row.
    Returns the full user_answer string (fixed letters + typed blanks).
    """
    user_chars = [""] * len(masked_word)

    cols = st.columns(len(masked_word))
    for i, ch in enumerate(masked_word):
        with cols[i]:
            if ch == "_":
                val = st.text_input(
                    "",
                    max_chars=1,
                    key=f"{key_prefix}_char_{i}",
                    label_visibility="collapsed",
                )
                user_chars[i] = (val or "")
            else:
                st.markdown(
                    f"<div style='font-size:22px;font-weight:800;text-align:center;line-height:36px;'>{ch}</div>",
                    unsafe_allow_html=True,
                )
                user_chars[i] = ch

    return "".join(user_chars)


def render_practice_mode(
    *,
    mode: str,
    words: Iterable[Any],
    difficulty_map: Mapping[int, str],
    weak_word_ids: Iterable[int],
    selected_course_id: int,
    selected_lesson_id: int,
):
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
        st.experimental_rerun()

    m_word = getattr(row, "_mapping", row)
    target_word = m_word["word"]

    submitted_key = f"{wid}_submitted"
    checked_key = f"{wid}_checked"
    correct_key = f"{wid}_correct"

    if st.session_state.get("active_word_id") != wid:
        st.session_state["active_word_id"] = wid

    for key in [submitted_key, checked_key, correct_key]:
        if key not in st.session_state:
            st.session_state[key] = False

    masked = mask_word(target_word)
    key_prefix = f"practice_{wid}"
    blank_indices = [idx for idx, ch in enumerate(masked) if ch == "_"]
    user_answer = render_masked_word_input(masked, target_word, key_prefix, blank_indices)

    if not st.session_state[submitted_key]:
        if st.button("✅ Submit"):
            is_correct = user_answer.lower() == target_word.lower()

            record_attempt(
                user_id=st.session_state.user_id,
                word_id=wid,
                correct=is_correct,
                time_taken=int(time.time() - st.session_state.start_time),
                blanks_count=masked.count("_"),
                wrong_letters_count=0 if is_correct else 1,
            )

            st.session_state[submitted_key] = True
            st.session_state[checked_key] = True
            st.session_state[correct_key] = is_correct

            st.experimental_rerun()

    if st.session_state[checked_key]:
        if st.session_state[correct_key]:
            st.success("🎉 Correct! Great job!")
            st.info("⭐ You earned 10 XP")
        else:
            st.error("😅 Not quite right — keep going!")

    if st.session_state[checked_key]:
        if st.button("➡️ Next"):
            # mark last word ONLY when user chooses to advance
            st.session_state[last_wid_key] = wid

            # unlock next word so a new pick happens
            st.session_state[current_wid_key] = None

            # reset timer
            st.session_state.start_time = time.time()

            # clear ONLY the current word's input state
            for key in list(st.session_state.keys()):
                if isinstance(key, str) and key.startswith(key_prefix):
                    st.session_state.pop(key, None)

            st.experimental_rerun()
