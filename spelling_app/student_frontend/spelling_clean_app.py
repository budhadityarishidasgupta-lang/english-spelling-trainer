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


def render_masked_word_inline(masked_word: str, key_prefix: str):
    cols = st.columns(len(masked_word))
    user_chars = []

    for i, ch in enumerate(masked_word):
        with cols[i]:
            if ch == "_":
                val = st.text_input(
                    "",
                    max_chars=1,
                    key=f"{key_prefix}_char_{i}",
                    label_visibility="collapsed",
                )
                user_chars.append(val or "")
            else:
                st.markdown(
                    f"<div style='font-size:22px;font-weight:700;text-align:center;'>{ch}</div>",
                    unsafe_allow_html=True,
                )
                user_chars.append(ch)

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

    ctx = f"{mode}_{selected_course_id}_{selected_lesson_id}"
    current_word_key = f"{ctx}_current_word_id"
    last_word_key = f"{ctx}_last_word_id"

    if current_word_key not in st.session_state:
        st.session_state[current_word_key] = None

    if st.session_state[current_word_key] is None:
        word_pick = choose_next_word(
            words=words,
            difficulty_map=difficulty_map,
            current_level="MEDIUM",
            weak_word_ids=weak_word_ids,
            last_word_id=st.session_state.get(last_word_key),
        )
        if not word_pick:
            st.warning("No words available.")
            return

        mapping = getattr(word_pick, "_mapping", word_pick)
        st.session_state[current_word_key] = mapping["word_id"]

    wid = st.session_state[current_word_key]
    word_row = next(w for w in words if _word_id(w) == wid)
    target_word = getattr(word_row, "_mapping", word_row)["word"]

    submitted_key = f"{wid}_submitted"
    checked_key = f"{wid}_checked"
    correct_key = f"{wid}_correct"

    for key in [submitted_key, checked_key, correct_key]:
        if key not in st.session_state:
            st.session_state[key] = False

    masked = mask_word(target_word)
    user_answer = render_masked_word_inline(masked, key_prefix=f"practice_{wid}")

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
            st.session_state[last_word_key] = wid
            st.session_state[current_word_key] = None
            st.session_state.start_time = time.time()

            for key in list(st.session_state.keys()):
                if str(key).startswith("practice_") or str(key).startswith(str(wid)):
                    del st.session_state[key]

            st.experimental_rerun()
