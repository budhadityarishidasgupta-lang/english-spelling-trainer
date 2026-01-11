import random
import datetime
import streamlit as st

USE_OVERRIDE_HINTS = True

from shared.db import execute, fetch_all


def _fetch_spelling_lessons():
    """
    Fetch spelling lessons.

    The underlying table uses lesson_id as the primary key,
    but the rest of the code expects the key to be 'id',
    so we alias lesson_id AS id.
    """
    return fetch_all(
        """
        SELECT
            lesson_id AS id,
            title,
            instructions
        FROM lessons
        WHERE lesson_type = 'spelling'
        ORDER BY sort_order NULLS LAST, lesson_id
        """,
    )


def _fetch_spelling_words(lesson_id: int, course_id: int | None = None):
    if USE_OVERRIDE_HINTS:
        return fetch_all(
            """
            SELECT
                w.word_id AS id,
                w.word,
                w.level AS difficulty,
                w.pattern AS pattern_hint,
                COALESCE(o.hint_text, w.hint) AS definition,
                w.example_sentence AS sample_sentence,
                NULL AS missing_letter_mask
            FROM spelling_lesson_items li
            JOIN spelling_words w
              ON w.word_id = li.word_id
            LEFT JOIN LATERAL (
                SELECT hint_text
                FROM spelling_hint_overrides o
                WHERE o.word_id = w.word_id
                  AND o.course_id = :course_id
                ORDER BY o.updated_at DESC
                LIMIT 1
            ) o ON TRUE
            WHERE li.lesson_id = :lid
            ORDER BY w.word_id
            """,
            {"lid": lesson_id, "course_id": course_id},
        )
    return fetch_all(
        """
        SELECT
            w.word_id AS id,
            w.word,
            w.level AS difficulty,
            w.pattern AS pattern_hint,
            COALESCE(o.hint_text, w.hint) AS definition,
            w.example_sentence AS sample_sentence,
            NULL AS missing_letter_mask
        FROM spelling_lesson_items li
        JOIN spelling_words w
            ON w.word_id = li.word_id
        LEFT JOIN LATERAL (
            SELECT hint_text
            FROM spelling_hint_overrides o
            WHERE o.word_id = w.word_id
              AND o.course_id = :course_id
            ORDER BY o.updated_at DESC
            LIMIT 1
        ) o ON TRUE
        WHERE li.lesson_id = :lid
        ORDER BY w.word_id
        """,
        {
            "lid": lesson_id,
            "course_id": course_id,
        },
    )

def _record_attempt(
    user_id: int,
    lesson_id: int,
    word_id: int,
    typed_answer: str,
    is_correct: bool,
    mode: str,
    scope: str = "lesson",
):
    if scope == "daily":
        attempt_type = "spelling_daily"
    elif mode == "missing":
        attempt_type = "spelling_missing"
    else:
        attempt_type = "spelling"

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
            "atype": attempt_type,
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


def get_spelling_hint(word: str):
    if "ie" in word:
        return "💡 Remember: 'i before e except after c'."
    if word.endswith("ly"):
        return "💡 Words ending in '-ly' often come from adjectives."
    if "ough" in word:
        return "💡 'ough' can sound different in different words."
    return "💡 Say the word slowly and listen to each sound."


def _ensure_hint_state():
    if "hint_used" not in st.session_state:
        st.session_state["hint_used"] = False
    if "wrong_attempts" not in st.session_state:
        st.session_state["wrong_attempts"] = 0
    if "base_xp" not in st.session_state:
        st.session_state["base_xp"] = 10
    if "spelling_feedback" not in st.session_state:
        st.session_state["spelling_feedback"] = None
    if "spelling_last_correct" not in st.session_state:
        st.session_state["spelling_last_correct"] = False


def _weak_words_for_user(user_id: int, lesson_id: int):
    return fetch_all(
        """
        WITH incorrect_words AS (
            SELECT DISTINCT word_id
            FROM attempts
            WHERE user_id = :uid
              AND lesson_id = :lid
              AND NOT is_correct
              AND attempt_type IN ('spelling', 'spelling_missing', 'spelling_daily')
        )
        SELECT w.id, w.word, w.difficulty, w.pattern_hint, w.definition, w.sample_sentence, w.missing_letter_mask
        FROM spelling_words w
        JOIN incorrect_words iw ON iw.word_id = w.id
        WHERE w.lesson_id = :lid
        ORDER BY w.id
        """,
        {"uid": user_id, "lid": lesson_id},
    )


def _lesson_accuracy(user_id: int, lesson_id: int):
    stats = fetch_all(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) AS correct,
            SUM(CASE WHEN NOT is_correct THEN 1 ELSE 0 END) AS wrong,
            SUM(CASE WHEN is_correct THEN 1 ELSE 0 END)::decimal / NULLIF(COUNT(*), 0) AS accuracy
        FROM attempts
        WHERE user_id = :uid
          AND lesson_id = :lid
          AND attempt_type IN ('spelling', 'spelling_missing', 'spelling_daily')
        """,
        {"uid": user_id, "lid": lesson_id},
    )

    if isinstance(stats, dict):
        return {"total": 0, "correct": 0, "wrong": 0, "accuracy": None, "error": stats.get("error")}

    if not stats:
        return {"total": 0, "correct": 0, "wrong": 0, "accuracy": None}

    return stats[0]


def _load_word_stats(user_id: int, lesson_id: int):
    rows = fetch_all(
        """
        SELECT w.id AS word_id,
               COUNT(a.*) AS total_attempts,
               COALESCE(SUM(CASE WHEN a.is_correct THEN 1 ELSE 0 END), 0) AS correct_attempts
        FROM spelling_words w
        LEFT JOIN attempts a ON a.word_id = w.id
                           AND a.user_id = :uid
                           AND a.lesson_id = :lid
                           AND a.attempt_type IN ('spelling', 'spelling_missing', 'spelling_daily')
        WHERE w.lesson_id = :lid
        GROUP BY w.id
        """,
        {"uid": user_id, "lid": lesson_id},
    )

    if isinstance(rows, dict):
        return []

    stats = {}
    for r in rows:
        total = r.get("total_attempts", 0)
        correct = r.get("correct_attempts", 0)
        accuracy = float(correct) / float(total) if total else 0.0
        stats[int(r["word_id"])] = {"total": total, "correct": correct, "accuracy": accuracy}
    return stats


def _compute_daily_words(user_id: int, lesson_id: int):
    today = datetime.date.today()
    cached_date = st.session_state.get("daily_date")
    cached_words = st.session_state.get("daily_words") or []
    cached_lesson = st.session_state.get("daily_lesson_id")

    if cached_date == today and cached_words and cached_lesson == lesson_id:
        return cached_words

    all_words = _fetch_spelling_words(int(lesson_id)) or []
    stats = _load_word_stats(user_id, lesson_id)
    if isinstance(all_words, dict) or isinstance(stats, dict):
        return []

    weak_candidates = []
    other_candidates = []

    for word in all_words:
        word_id = int(word["id"])
        info = stats.get(word_id, {"total": 0, "correct": 0, "accuracy": 0.0})
        total = info.get("total", 0)
        accuracy = info.get("accuracy", 0.0)
        is_weak = total >= 2 and accuracy < 0.8

        if is_weak:
            weak_candidates.append((accuracy, word))
        else:
            other_candidates.append((total, accuracy, word))

    weak_candidates = sorted(weak_candidates, key=lambda w: w[0])
    selected = [w for _, w in weak_candidates[:3]]

    other_candidates = sorted(other_candidates, key=lambda t: (t[0], t[1]))
    for _, _, word in other_candidates:
        if len(selected) >= 5:
            break
        selected.append(word)

    if len(selected) < 5 and len(all_words) >= len(selected):
        remaining = [w for w in all_words if w not in selected]
        random.shuffle(remaining)
        selected.extend(remaining[: 5 - len(selected)])

    selected = selected[:5]

    st.session_state["daily_words"] = selected
    st.session_state["daily_date"] = today
    st.session_state["daily_lesson_id"] = lesson_id
    st.session_state["daily_index"] = 0
    st.session_state["daily_results"] = []
    st.session_state["daily_correct"] = 0
    st.session_state["daily_wrong"] = 0

    return selected


def _reset_session(
    words,
    lesson_id: int,
    lesson_title: str,
    mode: str,
    scope: str = "lesson",
    mode_label: str | None = None,
):
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
    st.session_state["spelling_scope"] = scope
    st.session_state["weak_mode"] = scope == "weak"
    st.session_state["practice_mode"] = mode_label or mode
    # Mirrors for explicit progress keys requested by the spec
    st.session_state["current_index"] = 0
    st.session_state["current_streak"] = 0
    st.session_state["correct_count"] = 0
    st.session_state["wrong_count"] = 0
    st.session_state["hint_used"] = False
    st.session_state["wrong_attempts"] = 0
    st.session_state["base_xp"] = 10
    st.session_state["spelling_feedback"] = None
    st.session_state["spelling_last_correct"] = False
    st.session_state["current_display_mask"] = None
    st.session_state["active_word_id"] = None


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
    raw_mode = st.session_state.get("practice_mode", "Normal Mode")
    mode_label = "Missing-Letter" if raw_mode in ("missing", "Missing-Letter Mode") else "Normal"
    scope = st.session_state.get("spelling_scope", "lesson")
    scope_text = "Daily 5 Words" if scope == "daily" else (
        "Practising weak words only" if scope == "weak" else "Full lesson"
    )

    st.markdown(
        f"""
        <div class="quiz-surface">
          <div class="quiz-heading">
              <div>
              <p class="quiz-instructions">{lesson_title} — {scope_text}</p>
              <h3 style="margin: 0;">Spell this word ({mode_label} mode)</h3>
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

        col1, col2, col3 = st.columns([3, 1, 1], gap="small")
        with col1:
            selected_title = st.selectbox(
                "Select Spelling Lesson",
                list(lesson_titles.keys()),
                index=list(lesson_titles.keys()).index(default_lesson) if default_lesson in lesson_titles else 0,
                key="spelling_lesson",
            )

        selected_lesson = lesson_titles[selected_title]

        with col2:
            practice_mode = st.radio(
                "Practice Mode",
                ["Normal Mode", "Missing-Letter Mode"],
                horizontal=False,
                key="practice_mode",
            )

        with col3:
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            weak_mode = st.button("Practice Weak Words", use_container_width=True)

        start_practice = st.button("Start Lesson", type="primary")

        st.markdown(
            """
            <div class="quiz-surface" style="margin-top:12px;">
              <div class="lesson-header">
                <h3>Daily 5 Words Challenge</h3>
                <p class="lesson-instruction">Blend weak words and new practice into a quick daily sprint.</p>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        daily_button = st.button("Start Today's 5 Words", use_container_width=True)

        if start_practice:
            st.session_state["practice_mode"] = practice_mode
            words = _fetch_spelling_words(int(selected_lesson["id"]))
            if isinstance(words, dict) and words.get("error"):
                st.error(f"Could not load words: {words['error']}")
            elif not words:
                st.warning("This lesson has no words yet.")
            else:
                _reset_session(
                    words,
                    int(selected_lesson["id"]),
                    selected_title,
                    "missing" if practice_mode == "Missing-Letter Mode" else "normal",
                    mode_label=practice_mode,
                )

        if weak_mode:
            weak_words = _weak_words_for_user(int(user_id), int(selected_lesson["id"]))
            if isinstance(weak_words, dict) and weak_words.get("error"):
                st.error(f"Could not load weak words: {weak_words['error']}")
            elif not weak_words:
                st.info("You currently have no weak words in this lesson.")
            else:
                st.session_state["practice_mode"] = practice_mode
                _reset_session(
                    weak_words,
                    int(selected_lesson["id"]),
                    selected_title,
                    "missing" if practice_mode == "Missing-Letter Mode" else "normal",
                    scope="weak",
                    mode_label=practice_mode,
                )

        if 'daily_button' in locals() and daily_button:
            st.session_state["practice_mode"] = practice_mode
            daily_words = _compute_daily_words(int(user_id), int(selected_lesson["id"]))
            if not daily_words:
                st.error("Could not load today's words right now. Please try again.")
            else:
                _reset_session(
                    daily_words,
                    int(selected_lesson["id"]),
                    f"{selected_title} — Daily 5 Words",
                    "missing" if practice_mode == "Missing-Letter Mode" else "normal",
                    scope="daily",
                    mode_label="Daily 5 Words",
                )

        if st.session_state.get("spelling_words"):
            active_lesson_id = int(st.session_state.get("spelling_lesson_id") or selected_lesson["id"])
            if st.session_state.get("spelling_done"):
                _render_summary(int(user_id), active_lesson_id)
            else:
                _render_active_session(active_lesson_id, int(user_id))


def _render_active_session(lesson_id: int, user_id: int):
    words = st.session_state.get("spelling_words") or []
    idx = st.session_state.get("spelling_index", 0)
    total = len(words)
    word = _current_word()
    mode = st.session_state.get("spelling_mode", "normal")
    scope = st.session_state.get("spelling_scope", "lesson")

    _ensure_hint_state()

    if not word:
        st.info("No words to practice right now.")
        return

    if st.session_state.get("active_word_id") != word.get("id"):
        st.session_state["active_word_id"] = word.get("id")
        st.session_state["hint_used"] = False
        st.session_state["wrong_attempts"] = 0
        st.session_state["base_xp"] = 10
        st.session_state["spelling_feedback"] = None
        st.session_state["spelling_last_submitted"] = False
        st.session_state["spelling_last_correct"] = False
        st.session_state["current_display_mask"] = None

    _session_hud(total)

    st.caption(f"Word {idx + 1} of {total}")

    display_mask = word.get("missing_letter_mask") or _generate_mask(str(word.get("word", "")))
    if st.session_state.get("current_display_mask") is None:
        st.session_state["current_display_mask"] = display_mask

    current_mask = st.session_state.get("current_display_mask") or display_mask
    masked_word = current_mask if mode == "missing" else str(word.get("word", ""))
    if mode == "missing":
        st.markdown(
            f"<div class='masked-word' style='font-size:28px;font-weight:700;'>{masked_word}</div>",
            unsafe_allow_html=True,
        )
        st.caption("Fill in the missing letters to spell the full word.")
    elif word.get("pattern_hint"):
        st.caption(f"Hint: {word.get('pattern_hint')}")

    st.text_input(
        "Your answer",
        key="spelling_input",
        placeholder="Type the spelling here...",
    )

    show_hint_button = (
        st.session_state.get("spelling_last_submitted")
        and not st.session_state.get("spelling_last_correct")
        and not st.session_state.get("hint_used")
    )

    if show_hint_button:
        if st.button("💡 Hint", help="Reveal the first missing letter"):
            blank_indices = [i for i, ch in enumerate(masked_word) if ch == "_"]
            reveal_index = blank_indices[0] if blank_indices else None
            if reveal_index is not None:
                word_text = str(word.get("word", ""))
                hint_word = list(masked_word)
                if reveal_index < len(word_text):
                    hint_word[reveal_index] = word_text[reveal_index]
                    st.session_state["current_display_mask"] = "".join(hint_word)
            st.session_state["hint_used"] = True
            st.session_state["spelling_last_submitted"] = False

    submitted = False
    if not st.session_state.get("spelling_last_submitted"):
        submitted = st.button("Submit", type="primary")
    if submitted:
        typed = (st.session_state.get("spelling_input") or "").strip()
        is_correct = typed.lower() == str(word.get("word", "")).strip().lower()

        _record_attempt(user_id, lesson_id, int(word["id"]), typed, is_correct, mode, scope)

        st.session_state["spelling_results"].append(
            {
                "word": word.get("word"),
                "correct": is_correct,
                "typed": typed,
            }
        )

        if is_correct:
            st.session_state["spelling_streak"] = st.session_state.get("spelling_streak", 0) + 1
            st.session_state["current_streak"] = st.session_state.get("current_streak", 0) + 1
            st.session_state["spelling_correct"] = st.session_state.get("spelling_correct", 0) + 1
            st.session_state["correct_count"] = st.session_state.get("correct_count", 0) + 1
        else:
            st.session_state["spelling_streak"] = 0
            st.session_state["current_streak"] = 0
            st.session_state["spelling_wrong"] = st.session_state.get("spelling_wrong", 0) + 1
            st.session_state["wrong_count"] = st.session_state.get("wrong_count", 0) + 1
            st.session_state["wrong_attempts"] = st.session_state.get("wrong_attempts", 0) + 1

        xp_awarded = 0
        feedback_lines = []
        if is_correct:
            st.session_state["spelling_last_correct"] = True
            base_xp = st.session_state.get("base_xp", 10)
            xp_awarded = base_xp if not st.session_state.get("hint_used") else max(base_xp - 2, 0)
            primary = (
                "🏆 Fantastic work! ⭐ You earned 10 XP"
                if not st.session_state.get("hint_used")
                else "⭐ Well done! You earned 8 XP"
            )
            secondary = (
                "🎯 No hints used — excellent spelling!"
                if not st.session_state.get("hint_used")
                else "💡 Hint used: first letter revealed"
            )
            feedback_lines = [primary, secondary]
        else:
            st.session_state["spelling_last_correct"] = False
            feedback_lines = [
                "😅 Not quite right — keep trying!",
                "💡 Need help? Use a hint to reveal the first letter.",
            ]

        example_sentence = word.get("sample_sentence") or ""
        feedback_lines.append(f'📘 Example sentence: "{example_sentence}"')

        st.session_state["spelling_feedback"] = {
            "correct": is_correct,
            "xp": xp_awarded,
            "lines": feedback_lines,
        }

        st.session_state["spelling_last_submitted"] = True

    feedback = st.session_state.get("spelling_feedback")
    if feedback:
        feedback_block = ["<div class=\"quiz-surface\" style=\"margin-top:12px;\">"]
        for line in feedback.get("lines", []):
            feedback_block.append(f"<p class='quiz-instructions' style='margin:4px 0;'>{line}</p>")
        feedback_block.append("</div>")
        st.markdown("\n".join(feedback_block), unsafe_allow_html=True)

    if st.session_state.get("spelling_last_submitted") and st.session_state.get("spelling_last_correct"):
        if idx + 1 < total:
            if st.button("Next word →"):
                st.session_state["spelling_index"] += 1
                st.session_state["current_index"] = st.session_state.get("current_index", 0) + 1
                st.session_state["spelling_input"] = ""
                st.session_state["spelling_last_submitted"] = False
                st.session_state["spelling_last_correct"] = False
                st.session_state["spelling_feedback"] = None
                st.session_state["hint_used"] = False
                st.session_state["wrong_attempts"] = 0
                st.session_state["base_xp"] = 10
                st.session_state["current_display_mask"] = None
                st.session_state["active_word_id"] = None
                st.rerun()
        else:
            st.session_state["spelling_done"] = True
            st.session_state["spelling_last_submitted"] = False
            st.session_state["spelling_last_correct"] = False
            st.session_state["spelling_feedback"] = None
            st.session_state["spelling_input"] = ""
            _render_summary(user_id, lesson_id)


def _render_summary(user_id: int, lesson_id: int):
    results = st.session_state.get("spelling_results", [])
    total = len(results)
    correct = st.session_state.get("spelling_correct", 0)
    wrong = st.session_state.get("spelling_wrong", 0)
    accuracy = round((correct / total) * 100, 1) if total else 0.0
    weak_again = [r.get("word") for r in results if not r.get("correct")]
    lesson_stats = _lesson_accuracy(user_id, lesson_id)
    weak_words = _weak_words_for_user(user_id, lesson_id)
    weak_count = 0 if isinstance(weak_words, dict) else len(weak_words)
    scope = st.session_state.get("spelling_scope", "lesson")
    is_weak_session = st.session_state.get("weak_mode", False) or scope == "weak"
    daily_message = "Great job! You've completed today's 5 words." if scope == "daily" else "Here's how you did in this round."
    heading = "Weak-Word Summary" if is_weak_session else "Session summary"

    if isinstance(lesson_stats, dict) and lesson_stats.get("accuracy") is not None:
        lesson_accuracy = round(float(lesson_stats.get("accuracy", 0) * 100), 1)
    else:
        lesson_accuracy = 0.0

    st.markdown(
        f"""
        <div class="quiz-surface">
          <div class="lesson-header">
            <h2>{heading}</h2>
            <p class="lesson-instruction">{daily_message}</p>
          </div>
          <p><strong>Total correct:</strong> {correct}</p>
          <p><strong>Total wrong:</strong> {wrong}</p>
          <p><strong>Accuracy:</strong> {accuracy}%</p>
          <p><strong>Words to revise again:</strong> {', '.join(weak_again) if weak_again else 'None — excellent work!'}</p>
          <p><strong>Lesson accuracy so far:</strong> {lesson_accuracy}%</p>
          <p><strong>Weak words remaining:</strong> {weak_count}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Practice Weak Words Now"):
            weak_words = _weak_words_for_user(int(user_id), int(lesson_id)) if lesson_id else []
            if isinstance(weak_words, dict) and weak_words.get("error"):
                st.error(f"Could not load weak words: {weak_words['error']}")
            elif weak_words:
                current_mode = st.session_state.get("practice_mode", "Normal Mode")
                _reset_session(
                    weak_words,
                    int(lesson_id),
                    st.session_state.get("spelling_lesson_title", ""),
                    "missing" if current_mode in ("missing", "Missing-Letter Mode") else "normal",
                    scope="weak",
                    mode_label=current_mode,
                )
                st.rerun()
            else:
                st.info("Great! You have no weak words right now in this lesson.")

    with col2:
        if st.button("Restart Lesson"):
            lesson_title = st.session_state.get("spelling_lesson_title", "")
            if lesson_id:
                words = _fetch_spelling_words(int(lesson_id))
                if not isinstance(words, dict) and words:
                    current_mode = st.session_state.get("practice_mode", "Normal Mode")
                    _reset_session(
                        words,
                        int(lesson_id),
                        lesson_title,
                        "missing" if current_mode in ("missing", "Missing-Letter Mode") else "normal",
                        mode_label=current_mode,
                    )
                    st.rerun()
