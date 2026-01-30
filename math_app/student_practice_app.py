def render_practice_mode(show_back_button=True):
    import streamlit as st

    # --- PRACTICE STICKY GUARD ---
    st.session_state["in_practice"] = True

    from math_app.repository.math_practice_repo import (
        get_lessons_for_student,
        get_practice_progress,
        get_questions_for_lesson,
        record_practice_attempt,
        save_practice_progress,
    )

    student_id = st.session_state.get("student_id")
    lesson_id = st.session_state.get("active_lesson_id")

    st.subheader("🧠 Practice & Skill Builder")
    st.caption(
        "Lesson-based practice. One question at a time. "
        "Submit → feedback → next. Attempts are saved."
    )
    if st.button("⬅ Back to Home"):
        st.session_state.pop("in_practice", None)
        st.session_state["mode"] = "HOME"
        st.rerun()
    st.markdown("---")

    # ------------------------------------------------------------
    # TEMP STUDENT / COURSE SELECTOR
    # (Replace later with real auth from shell)
    # ------------------------------------------------------------
    student_id = st.number_input(
        "Student ID",
        min_value=1,
        value=int(st.session_state.get("student_id", 1)),
        step=1,
        key="practice_student_id_input",
    )

    course_id = st.number_input(
        "Course ID",
        min_value=1,
        value=int(st.session_state.get("course_id", 1)),
        step=1,
        key="practice_course_id_input",
    )

    # Persist for future shell integration
    st.session_state["student_id"] = int(student_id)
    st.session_state["course_id"] = int(course_id)

    # ------------------------------------------------------------
    # LESSON SELECTION
    # ------------------------------------------------------------
    lessons = get_lessons_for_student(course_id=int(course_id))

    if not lessons:
        st.info("No practice lessons found for this course.")
        if show_back_button:
            st.markdown("---")
            if st.button("⬅ Back to Home", use_container_width=True):
                st.session_state.pop("in_practice", None)
                st.session_state["mode"] = "HOME"
                st.rerun()
        return

    # Handle possible None display_name safely
    lesson_label_to_id = {
        (l.get("display_name") or f"Lesson {l['lesson_id']}"): l["lesson_id"]
        for l in lessons
    }

    lesson_label = st.selectbox(
        "Select Practice Lesson",
        options=list(lesson_label_to_id.keys()),
        key="practice_lesson_select",
    )

    lesson_id = int(lesson_label_to_id[lesson_label])
    st.session_state["active_lesson_id"] = lesson_id

    # ------------------------------------------------------------
    # LOAD QUESTIONS
    # ------------------------------------------------------------
    questions = get_questions_for_lesson(lesson_id=int(lesson_id))

    if not questions:
        st.warning("This lesson has no questions yet.")
        if show_back_button:
            st.markdown("---")
            if st.button("⬅ Back to Home", use_container_width=True):
                st.session_state.pop("in_practice", None)
                st.session_state["mode"] = "HOME"
                st.rerun()
        return

    total_questions = len(questions)

    # ------------------------------------------------------------
    # SESSION STATE (NAMESPACED)
    # ------------------------------------------------------------
    if "practice_lesson_id" not in st.session_state:
        st.session_state.practice_lesson_id = None
    if "practice_question_index" not in st.session_state:
        start_idx = get_practice_progress(int(student_id), int(lesson_id))
        st.session_state.practice_question_index = start_idx
    if "practice_submitted" not in st.session_state:
        st.session_state.practice_submitted = False
    if "practice_selected_option" not in st.session_state:
        st.session_state.practice_selected_option = None
    if "practice_feedback" not in st.session_state:
        st.session_state.practice_feedback = None

    # Reset state & apply resume when lesson changes
    if st.session_state.practice_lesson_id != lesson_id:
        st.session_state.practice_lesson_id = lesson_id
        st.session_state.practice_submitted = False
        st.session_state.practice_selected_option = None
        st.session_state.practice_feedback = None

        resume_at = get_practice_progress(
            student_id=int(student_id),
            lesson_id=int(lesson_id),
        )
        st.session_state.practice_question_index = min(
            int(resume_at),
            total_questions,
        )

    # ------------------------------------------------------------
    # RESTART PRACTICE (does NOT delete attempts)
    # ------------------------------------------------------------
    if st.button("🔄 Restart Practice", key="practice_restart"):
        st.session_state.practice_question_index = 0
        st.session_state.practice_submitted = False
        st.session_state.practice_selected_option = None
        st.session_state.practice_feedback = None
        st.rerun()

    # ------------------------------------------------------------
    # COMPLETION
    # ------------------------------------------------------------
    current_index = st.session_state.get("practice_question_index", 0)

    # --- PRACTICE COMPLETE ---
    if current_index >= total_questions:
        correct_count = st.session_state.get("practice_correct_count", 0)
        accuracy = int((correct_count / total_questions) * 100) if total_questions else 0

        st.markdown("## 🧠 Practice Complete!")
        st.markdown("🎉 **Great work!**")

        st.markdown("---")
        st.markdown("### 📊 Your Summary")
        st.write(f"Questions attempted: **{total_questions}**")
        st.write(f"Correct answers: **{correct_count}**")
        st.write(f"Accuracy: **{accuracy}%**")

        st.markdown("---")
        st.markdown("### 🔁 What would you like to do next?")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("🔄 Retry Lesson", use_container_width=True):
                st.session_state["practice_question_index"] = 0
                st.session_state["practice_correct_count"] = 0
                st.session_state.pop("in_practice", None)
                st.rerun()

        with col2:
            if st.button("⬅ Back to Home", use_container_width=True):
                st.session_state.pop("in_practice", None)
                st.session_state["mode"] = "HOME"
                st.rerun()

        return

    # ------------------------------------------------------------
    # CURRENT QUESTION
    # ------------------------------------------------------------
    q = questions[st.session_state.practice_question_index]
    current_question = {**q, "id": q.get("id", q["question_id"])}

    st.subheader(
        f"Question {st.session_state.practice_question_index + 1} of {total_questions}"
    )
    st.write(q["stem"])

    options = {
        "A": q["option_a"],
        "B": q["option_b"],
        "C": q["option_c"],
        "D": q["option_d"],
    }

    option_labels = [f"{k}) {v}" for k, v in options.items()]

    def handle_practice_submission(selected):
        selected_key = selected.split(")")[0]
        correct_key = (q["correct_option"] or "").strip().upper()
        is_correct = selected_key == correct_key

        record_practice_attempt(
            student_id=int(student_id),
            lesson_id=int(lesson_id),
            question_id=int(q["question_id"]),
            selected_option=selected_key,
            is_correct=is_correct,
        )

        if is_correct:
            st.session_state["practice_correct_count"] = (
                st.session_state.get("practice_correct_count", 0) + 1
            )

        st.session_state.practice_submitted = True
        st.session_state.practice_selected_option = selected_key
        st.session_state.practice_feedback = {
            "is_correct": is_correct,
            "correct_key": correct_key,
            "explanation": q.get("explanation"),
        }

    # --- Practice answer selection (no auto-advance) ---
    answer_key = f"practice_answer_{current_question['id']}"
    selected = st.radio(
        "Choose your answer",
        option_labels,
        key=answer_key,
    )

    # --- Submit gate ---
    if st.button("Submit Answer"):
        selected = st.session_state.get(answer_key)
        if selected is None:
            st.warning("Please select an answer.")
        else:
            # MOVE the existing evaluation / save-attempt logic here
            # (whatever currently runs when an option button is clicked)
            handle_practice_submission(selected)

            # Advance question index
            st.session_state.practice_question_index += 1

            # Persist progress
            save_practice_progress(
                int(student_id),
                int(lesson_id),
                st.session_state.practice_question_index,
            )

            st.session_state.practice_submitted = False
            st.session_state.practice_selected_option = None
            st.session_state.practice_feedback = None

            # Clear selection for next question
            st.session_state.pop(answer_key, None)
            st.rerun()

    # ------------------------------------------------------------
    # FEEDBACK
    # ------------------------------------------------------------
    if st.session_state.practice_submitted and st.session_state.practice_feedback:
        fb = st.session_state.practice_feedback

        if fb["is_correct"]:
            st.success("✅ Correct!")
        else:
            correct_text = options.get(fb["correct_key"], "")
            st.error(f"❌ Incorrect. Correct answer: {fb['correct_key']}) {correct_text}")

        if fb.get("explanation"):
            with st.expander("📘 Explanation"):
                st.write(fb["explanation"])

        if st.button("Next", key="practice_next"):
            st.session_state.practice_submitted = False
            st.session_state.practice_selected_option = None
            st.session_state.practice_feedback = None
            st.rerun()

    if show_back_button:
        st.markdown("---")
        if st.button("⬅ Back to Home", use_container_width=True):
            st.session_state.pop("in_practice", None)
            st.session_state["mode"] = "HOME"
            st.rerun()
