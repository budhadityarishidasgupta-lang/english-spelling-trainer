import random
import streamlit as st

from shared.db import execute, fetch_all


def _fetch_spelling_lessons():
    return fetch_all(
        """
        SELECT id, title, instructions
        FROM lessons
        WHERE lesson_type = 'spelling'
        ORDER BY sort_order NULLS LAST, id
        """,
    )


def _fetch_spelling_words(lesson_id: int):
    return fetch_all(
        """
        SELECT id, word, difficulty, pattern_hint, definition, sample_sentence, missing_letter_mask
        FROM spelling_words
        WHERE lesson_id = :lid
        ORDER BY id
        """,
        {"lid": lesson_id},
    )


def _record_attempt(
    user_id: int,
    lesson_id: int,
    word_id: int,
    typed_answer: str,
    is_correct: bool,
    mode: str,
):
    return execute(
        """
        INSERT INTO attempts (user_id, lesson_id, word_id, attempt_type, typed_answer, is_correct)
        VALUES (:uid, :lid, :wid, :atype, :ans, :correct)
        """,
        {
            "uid": user_id,
            "lid": lesson_id,
            "wid": word_id,
            "ans": typed_answer,
            "atype": "spelling_missing" if mode == "missing" else "spelling",
            "correct": is_correct,
        },
    )


def _generate_mask(word: str) -> str:
    if len(word) <= 3:
        return word

    letters = list(word)
    inner_indices = list(range(1, len(letters) - 1))
    blanks = min(3, max(1, len(inner_indices) // 3))
    random.seed(hash(word))
    for idx in random.sample(inner_indices, blanks):
        letters[idx] = "_"
    return "".join(letters)


def _weak_words_for_user(user_id: int, lesson_id: int):
    return fetch_all(
        """
        WITH stats AS (
            SELECT word_id,
                   COUNT(*) AS total,
                   SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) AS correct
            FROM attempts
            WHERE user_id = :uid
              AND lesson_id = :lid
              AND attempt_type IN ('spelling', 'spelling_missing')
            GROUP BY word_id
            HAVING COUNT(*) >= 2 AND (SUM(CASE WHEN is_correct THEN 1 ELSE 0 END)::decimal / COUNT(*)) < 0.8
        )
        SELECT w.id, w.word, w.difficulty, w.pattern_hint, w.definition, w.sample_sentence, w.missing_letter_mask
        FROM spelling_words w
        JOIN stats s ON s.word_id = w.id
        WHERE w.lesson_id = :lid
        ORDER BY w.id
        """,
        {"uid": user_id, "lid": lesson_id},
    )


def _reset_session(words, lesson_id: int, lesson_title: str, mode: str):
    st.session_state["spelling_words"] = words
    st.session_state["spelling_index"] = 0
    st.session_state["spelling_results"] = []
    st.session_state["spelling_mode"] = mode
    st.session_state["spelling_streak"] = 0
    st.session_state["spelling_done"] = False
    st.session_state["spelling_input"] = ""
    st.session_state["spelling_last_submitted"] = False
    st.session_state["spelling_lesson_id"] = lesson_id
    st.session_state["spelling_lesson_title"] = lesson_title
    st.session_state["spelling_correct"] = 0
    st.session_state["spelling_wrong"] = 0
    st.session_state["spelling_scope"] = "weak" if mode == "weak" else "lesson"


def _current_word():
    words = st.session_state.get("spelling_words") or []
    idx = st.session_state.get("spelling_index", 0)
    if 0 <= idx < len(words):
        return words[idx]
    return None


def _session_hud(total_words: int):
    streak = st.session_state.get("spelling_streak", 0)
    correct = st.session_state.get("spelling_correct", 0)
    wrong = st.session_state.get("spelling_wrong", 0)
    lesson_title = st.session_state.get("spelling_lesson_title", "")
    mode = st.session_state.get("practice_mode", "Normal")
    scope = st.session_state.get("spelling_scope", "lesson")

    st.markdown(
        f"""
        <div class="quiz-surface">
          <div class="quiz-heading">
            <div>
              <p class="quiz-instructions">{lesson_title} — {('Practising weak words only' if scope == 'weak' else 'Full lesson')}</p>
              <h3 style="margin: 0;">Spell this word ({mode} mode)</h3>
            </div>
            <div class="difficulty-badge">🔥 Current streak: {streak}</div>
          </div>
          <div style="display:flex; gap:12px; flex-wrap:wrap;">
            <p class="quiz-instructions">Words completed: {correct + wrong} / {total_words}</p>
            <p class="quiz-instructions">✅ Correct: {correct}</p>
            <p class="quiz-instructions">❌ Wrong: {wrong}</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_spelling_student(user_id: int | None = None):
    st.title("Student Dashboard")

    tab_practice = st.tabs(["Spelling Practice"])[0]

    with tab_practice:
        st.markdown(
            """
            <div class="quiz-surface">
              <div class="lesson-header">
                <h2>Spelling Practice</h2>
                <p class="lesson-instruction">Choose a spelling lesson, pick your mode, and chase your streak.</p>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        user_id = user_id or st.session_state.get("user_id", 1)
        lessons = _fetch_spelling_lessons()

        if isinstance(lessons, dict) and lessons.get("error"):
            st.error(f"Could not load lessons: {lessons['error']}")
            return

        if not lessons:
            st.info("No spelling lessons available yet.")
            return

        lesson_titles = {l["title"]: l for l in lessons}
        default_lesson = st.session_state.get("spelling_lesson") or list(lesson_titles.keys())[0]

        col1, col2 = st.columns([3, 1], gap="small")
        with col1:
            selected_title = st.selectbox(
                "Select Spelling Lesson",
                list(lesson_titles.keys()),
                index=list(lesson_titles.keys()).index(default_lesson) if default_lesson in lesson_titles else 0,
                key="spelling_lesson",
            )

        selected_lesson = lesson_titles[selected_title]

        with col2:
            practice_mode = st.radio("Practice mode", ["Normal", "Missing letters"], horizontal=False, key="practice_mode")

        start_practice = st.button("Start Lesson", type="primary")
        weak_mode = st.button("Practice Weak Words", use_container_width=True)

        if start_practice:
            words = _fetch_spelling_words(int(selected_lesson["id"]))
            if isinstance(words, dict) and words.get("error"):
                st.error(f"Could not load words: {words['error']}")
            elif not words:
                st.warning("This lesson has no words yet.")
            else:
                _reset_session(words, int(selected_lesson["id"]), selected_title, practice_mode.lower())

        if weak_mode:
            weak_words = _weak_words_for_user(int(user_id), int(selected_lesson["id"]))
            if isinstance(weak_words, dict) and weak_words.get("error"):
                st.error(f"Could not load weak words: {weak_words['error']}")
            elif not weak_words:
                st.info("Great! You have no weak words right now in this lesson.")
            else:
                _reset_session(weak_words, int(selected_lesson["id"]), selected_title, "weak")

        if st.session_state.get("spelling_words"):
            if st.session_state.get("spelling_done"):
                _render_summary(int(user_id))
            else:
                _render_active_session(int(selected_lesson["id"]), int(user_id))


def _render_active_session(lesson_id: int, user_id: int):
    words = st.session_state.get("spelling_words") or []
    idx = st.session_state.get("spelling_index", 0)
    total = len(words)
    word = _current_word()
    mode = st.session_state.get("practice_mode", "Normal").lower()

    if not word:
        st.info("No words to practice right now.")
        return

    _session_hud(total)

    display_mask = word.get("missing_letter_mask") or _generate_mask(str(word.get("word", "")))
    if mode == "missing":
        st.markdown(f"### {display_mask}")
        st.caption("Fill in the missing letters to spell the full word.")
    elif word.get("pattern_hint"):
        st.caption(f"Hint: {word.get('pattern_hint')}")

    st.text_input(
        "Your answer",
        key="spelling_input",
        placeholder="Type the spelling here...",
    )

    submitted = st.button("Submit", type="primary")
    if submitted:
        typed = (st.session_state.get("spelling_input") or "").strip()
        is_correct = typed.lower() == str(word.get("word", "")).strip().lower()

        _record_attempt(user_id, lesson_id, int(word["id"]), typed, is_correct, mode)

        st.session_state["spelling_results"].append(
            {
                "word": word.get("word"),
                "correct": is_correct,
                "typed": typed,
            }
        )

        if is_correct:
            st.session_state["spelling_streak"] = st.session_state.get("spelling_streak", 0) + 1
            st.session_state["spelling_correct"] = st.session_state.get("spelling_correct", 0) + 1
            st.success("Correct! Keep the streak going.")
        else:
            st.session_state["spelling_streak"] = 0
            st.session_state["spelling_wrong"] = st.session_state.get("spelling_wrong", 0) + 1
            st.error(f"Incorrect. The correct spelling is: **{word.get('word')}**")

        st.session_state["spelling_last_submitted"] = True

    if st.session_state.get("spelling_last_submitted"):
        if idx + 1 < total:
            if st.button("Next word →"):
                st.session_state["spelling_index"] += 1
                st.session_state["spelling_input"] = ""
                st.session_state["spelling_last_submitted"] = False
                st.rerun()
        else:
            st.session_state["spelling_done"] = True
            st.session_state["spelling_last_submitted"] = False
            st.session_state["spelling_input"] = ""
            _render_summary(user_id)


def _render_summary(user_id: int):
    results = st.session_state.get("spelling_results", [])
    total = len(results)
    correct = st.session_state.get("spelling_correct", 0)
    wrong = st.session_state.get("spelling_wrong", 0)
    accuracy = round((correct / total) * 100, 1) if total else 0.0
    weak_again = [r.get("word") for r in results if not r.get("correct")]

    st.markdown(
        f"""
        <div class="quiz-surface">
          <div class="lesson-header">
            <h2>Session summary</h2>
            <p class="lesson-instruction">Here's how you did in this round.</p>
          </div>
          <p><strong>Total correct:</strong> {correct}</p>
          <p><strong>Total wrong:</strong> {wrong}</p>
          <p><strong>Accuracy:</strong> {accuracy}%</p>
          <p><strong>Words to revise again:</strong> {', '.join(weak_again) if weak_again else 'None — excellent work!'}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Practice Weak Words Now"):
            lesson_id = st.session_state.get("spelling_lesson_id")
            weak_words = _weak_words_for_user(int(user_id), int(lesson_id)) if lesson_id else []
            if isinstance(weak_words, dict) and weak_words.get("error"):
                st.error(f"Could not load weak words: {weak_words['error']}")
            elif weak_words:
                _reset_session(weak_words, int(lesson_id), st.session_state.get("spelling_lesson_title", ""), "weak")
                st.rerun()
            else:
                st.info("Great! You have no weak words right now in this lesson.")

    with col2:
        if st.button("Restart Lesson"):
            lesson_id = st.session_state.get("spelling_lesson_id")
            lesson_title = st.session_state.get("spelling_lesson_title", "")
            if lesson_id:
                words = _fetch_spelling_words(int(lesson_id))
                if not isinstance(words, dict) and words:
                    _reset_session(
                        words,
                        int(lesson_id),
                        lesson_title,
                        st.session_state.get("practice_mode", "Normal").lower(),
                    )
                    st.rerun()
