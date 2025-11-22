import streamlit as st

from shared.db import execute, fetch_all


def _fetch_spelling_lessons():
    return fetch_all(
        """
        SELECT id, title, instructions
        FROM lessons
        WHERE lesson_type = 'spelling'
        ORDER BY sort_order NULLS LAST, id
        """
    )


def _fetch_spelling_words(lesson_id: int):
    return fetch_all(
        """
        SELECT id, word, difficulty, pattern_hint, definition, sample_sentence
        FROM spelling_words
        WHERE lesson_id = :lid
        ORDER BY id
        """,
        {"lid": lesson_id},
    )


def _fetch_weak_words(user_id: int, lesson_id: int):
    return fetch_all(
        """
        SELECT w.id, w.word, w.difficulty, w.pattern_hint, w.definition, w.sample_sentence
        FROM spelling_words w
        JOIN (
            SELECT word_id
            FROM attempts
            WHERE attempt_type = 'spelling' AND user_id = :uid AND lesson_id = :lid
            GROUP BY word_id
            HAVING AVG(CASE WHEN correct THEN 1 ELSE 0 END) < 0.8
        ) aw ON aw.word_id = w.id
        WHERE w.lesson_id = :lid
        ORDER BY w.id
        """,
        {"uid": user_id, "lid": lesson_id},
    )


def _record_attempt(user_id: int, lesson_id: int, word_id: int, typed_answer: str, is_correct: bool):
    return execute(
        """
        INSERT INTO attempts (user_id, lesson_id, word_id, attempt_type, typed_answer, correct)
        VALUES (:uid, :lid, :wid, 'spelling', :ans, :correct)
        """,
        {
            "uid": user_id,
            "lid": lesson_id,
            "wid": word_id,
            "ans": typed_answer,
            "correct": is_correct,
        },
    )


def _reset_session(words, mode_label: str, lesson_id: int):
    st.session_state["spelling_words"] = words
    st.session_state["spelling_index"] = 0
    st.session_state["spelling_results"] = []
    st.session_state["spelling_mode"] = mode_label
    st.session_state["spelling_streak"] = 0
    st.session_state["spelling_done"] = False
    st.session_state["spelling_input"] = ""
    st.session_state["spelling_last_submitted"] = False
    st.session_state["spelling_lesson_id"] = lesson_id


def _current_word():
    words = st.session_state.get("spelling_words") or []
    idx = st.session_state.get("spelling_index", 0)
    if 0 <= idx < len(words):
        return words[idx]
    return None


def render_spelling_student(user_id: int | None = None):
    st.title("Student Dashboard")

    tab_practice = st.tabs(["Spelling Practice"])[0]

    with tab_practice:
        st.markdown(
            """
            <div class="quiz-surface">
              <div class="lesson-header">
                <h2>Spelling Practice</h2>
                <p class="lesson-instruction">Choose a spelling lesson or focus on your weak words. Keep the streak alive!</p>
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

        col1, col2 = st.columns([3, 1], gap="small")
        lesson_titles = {l["title"]: l for l in lessons}
        default_lesson = st.session_state.get("spelling_lesson") or list(lesson_titles.keys())[0]
        with col1:
            selected_title = st.selectbox(
                "Select Spelling Lesson",
                list(lesson_titles.keys()),
                index=list(lesson_titles.keys()).index(default_lesson) if default_lesson in lesson_titles else 0,
                key="spelling_lesson",
            )

        selected_lesson = lesson_titles[selected_title]

        with col2:
            weak_mode = st.button("Practice Weak Words", use_container_width=True)

        start_practice = st.button("Start Lesson", type="primary")

        if start_practice:
            words = _fetch_spelling_words(int(selected_lesson["id"]))
            if isinstance(words, dict) and words.get("error"):
                st.error(f"Could not load words: {words['error']}")
            elif not words:
                st.warning("This lesson has no words yet.")
            else:
                _reset_session(words, "full", int(selected_lesson["id"]))

        if weak_mode:
            weak_words = _fetch_weak_words(int(user_id), int(selected_lesson["id"]))
            if isinstance(weak_words, dict) and weak_words.get("error"):
                st.error(f"Could not load weak words: {weak_words['error']}")
            elif not weak_words:
                st.info("No weak words found yet. Keep practicing!")
            else:
                _reset_session(weak_words, "weak", int(selected_lesson["id"]))

        if st.session_state.get("spelling_words"):
            if st.session_state.get("spelling_done"):
                _render_summary()
            else:
                _render_active_session(int(selected_lesson["id"]), int(user_id))


def _render_active_session(lesson_id: int, user_id: int):
    words = st.session_state.get("spelling_words") or []
    idx = st.session_state.get("spelling_index", 0)
    total = len(words)
    word = _current_word()

    if not word:
        st.info("No words to practice right now.")
        return

    st.markdown(
        f"""
        <div class="quiz-surface">
          <div class="quiz-heading">
            <div>
              <p class="quiz-instructions">Lesson progress: word {idx + 1} of {total}</p>
              <h3 style="margin: 0;">Spell the word</h3>
            </div>
            <div class="difficulty-badge">🔥 Current streak: {st.session_state.get('spelling_streak', 0)}</div>
          </div>
          <p class="quiz-instructions">Words mastered in this session: {sum(1 for r in st.session_state.get('spelling_results', []) if r.get('correct'))}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.text_input(
        "Your answer",
        key="spelling_input",
        placeholder="Type the spelling here...",
    )

    submitted = st.button("Submit", type="primary")
    if submitted:
        typed = (st.session_state.get("spelling_input") or "").strip()
        is_correct = typed.lower() == str(word.get("word", "")).strip().lower()

        _record_attempt(user_id, lesson_id, int(word["id"]), typed, is_correct)

        st.session_state["spelling_results"].append(
            {
                "word": word.get("word"),
                "correct": is_correct,
                "typed": typed,
            }
        )

        if is_correct:
            st.session_state["spelling_streak"] = st.session_state.get("spelling_streak", 0) + 1
            st.success("Great job! You spelled it correctly.")
        else:
            st.session_state["spelling_streak"] = 0
            st.error(f"Not quite. The correct spelling is: **{word.get('word')}**")

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
            _render_summary()


def _render_summary():
    results = st.session_state.get("spelling_results", [])
    total = len(results)
    correct = sum(1 for r in results if r.get("correct"))
    wrong = total - correct
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

    if st.button("Practice Weak Words Again"):
        lesson_id = st.session_state.get("spelling_lesson_id")

        if lesson_id is None:
            current_lesson = st.session_state.get("spelling_lesson")
            lessons = _fetch_spelling_lessons()
            for l in lessons:
                if l.get("title") == current_lesson:
                    lesson_id = l.get("id")
                    break

        if lesson_id:
            weak_words = _fetch_weak_words(int(st.session_state.get("user_id", 1)), int(lesson_id))
            if isinstance(weak_words, dict) and weak_words.get("error"):
                st.error(f"Could not load weak words: {weak_words['error']}")
            elif weak_words:
                _reset_session(weak_words, "weak", int(lesson_id))
                st.rerun()
            else:
                st.info("No weak words available right now.")
