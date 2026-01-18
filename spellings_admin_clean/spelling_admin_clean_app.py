#!/usr/bin/env python3
# -------------------------------------------------
# Spelling Admin App (FINAL, CLEAN)
# -------------------------------------------------

import sys
import base64
import io
import os
import pandas as pd
import streamlit as st

# other imports…

st.set_page_config(
    page_title="WordSprint – Spelling Admin",
    layout="wide",
)

# ---- Force project root for Render ----
PROJECT_ROOT = "/opt/render/project/src"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from shared.db import engine as shared_engine, fetch_all

SPELLING_ADMIN_VNEXT = os.getenv("SPELLING_ADMIN_VNEXT", "0") == "1"

# =========================================================
# Admin Console vNext (READ-ONLY, FLAGGED)
# =========================================================

def render_admin_console_vnext(engine):
    """
    Admin Console vNext
    OVERVIEW ONLY.
    All mutations remain in legacy sidebar.
    """

    from spelling_app.repository.admin_console_vnext_repo import (
        list_courses,
        list_lessons,
        list_student_progress,
    )

    from spelling_app.repository.student_repo import (
        list_registered_spelling_students,
    )

    st.divider()
    st.subheader("🧪 Admin Console vNext")
    st.caption("Overview & monitoring only. Use sidebar for management actions.")

    tab_courses, tab_lessons, tab_students, tab_progress = st.tabs(
        ["Courses", "Lessons", "Students", "Progress"]
    )

    # -----------------------------
    # Courses (Overview)
    # -----------------------------
    with tab_courses:
        st.subheader("Courses")

        df_courses = list_courses(engine)
        if df_courses.empty:
            st.info("No courses found.")
        else:
            st.dataframe(df_courses, use_container_width=True)

        st.info("Create, upload, rename, archive → Course Management (sidebar)")

    # -----------------------------
    # Lessons (Overview)
    # -----------------------------
    with tab_lessons:
        st.subheader("Lessons")

        df_courses = list_courses(engine)
        if df_courses.empty:
            st.info("No courses available.")
        else:
            course_id = st.selectbox(
                "Select course",
                df_courses["course_id"].tolist(),
                format_func=lambda x: df_courses.loc[
                    df_courses["course_id"] == x, "course_name"
                ].values[0],
            )

            df_lessons = list_lessons(engine, course_id)
            if df_lessons.empty:
                st.info("No lessons for this course.")
            else:
                st.dataframe(df_lessons, use_container_width=True)

        st.info("Lesson edits & CSV uploads → Course Management (sidebar)")

    # -----------------------------
    # Students
    # -----------------------------
    with tab_students:
        st.subheader("Students")

        students = list_registered_spelling_students()
        if not students:
            st.info("No spelling students found.")
        else:
            st.dataframe(students, use_container_width=True)

        st.caption("Class & assignment features coming in Patch 3")

    # -----------------------------
    # Progress (Preview)
    # -----------------------------
    with tab_progress:
        st.subheader("Progress (Preview)")

        st.warning(
            "Progress is currently aggregated. "
            "Spelling-only filtering will be applied next."
        )

        df_progress = list_student_progress(engine)
        st.dataframe(df_progress, use_container_width=True)


engine = shared_engine
if SPELLING_ADMIN_VNEXT:
    render_admin_console_vnext(engine)

from spellings_admin_clean.spelling_help_text_repo import (
    get_help_text,
    upsert_help_text,
)
from spellings_admin_clean.upload_manager_clean import process_spelling_csv
from spellings_admin_clean.lesson_manager_clean import (
    get_matching_words,
    rebuild_lesson_mappings,
    upsert_lesson,
    update_lesson_display_name,
)
from spelling_app.repository.spelling_course_repo import archive_course
from spelling_app.repository.spelling_lesson_repo import (
    archive_lesson,
    get_lessons_for_course,
)
from spelling_app.repository.spelling_content_repo import (
    get_content_block,
    upsert_content_block,
    delete_content_block,
)
from spellings_admin_clean.spelling_pending_registration_repo import (
    ensure_pending_registration_payment_status_column,
    ensure_pending_registration_token_column,
    list_spelling_pending_registrations,
    mark_registration_approved,
)
from spelling_app.repository.lesson_maintenance_repo import (
    consolidate_legacy_lessons_into_patterns,
)
from spelling_app.repository.student_repo import list_registered_spelling_students
from spelling_app.repository.hint_repo import (
    upsert_ai_hint_drafts,
    approve_drafts_to_overrides,
)


# -------------------------------------------------
# Helpers
# -------------------------------------------------

def rows_to_dicts(rows):
    if not rows:
        return []
    out = []
    for r in rows:
        if hasattr(r, "_mapping"):
            out.append(dict(r._mapping))
        elif isinstance(r, dict):
            out.append(r)
    return out


def get_all_courses():
    rows = fetch_all(
        "SELECT course_id, course_name FROM spelling_courses ORDER BY course_name"
    )
    return rows_to_dicts(rows)


def create_course(course_name: str):
    if not course_name.strip():
        return None

    rows = fetch_all(
        """
        INSERT INTO spelling_courses (course_name)
        VALUES (:name)
        RETURNING course_id;
        """,
        {"name": course_name.strip()},
    )
    rows = rows_to_dicts(rows)
    return rows[0]["course_id"] if rows else None


def rename_course(course_id: int, new_name: str):
    if not course_id or not new_name.strip():
        return False

    rows = fetch_all(
        """
        UPDATE spelling_courses
        SET course_name = :name
        WHERE course_id = :cid
        RETURNING course_id;
        """,
        {"name": new_name.strip(), "cid": course_id},
    )
    rows = rows_to_dicts(rows)
    return bool(rows)


def _normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace("\ufeff", "", regex=False)
    )
    return df


def _safe_int(value):
    try:
        if value is None:
            return None
        s = str(value).strip()
        if s.lower() in ("", "nan", "none"):
            return None
        return int(s)
    except (TypeError, ValueError):
        return None


def _read_lesson_csv_with_encoding_fallback(uploaded_file) -> pd.DataFrame:
    raw_bytes = (
        uploaded_file.getvalue()
        if hasattr(uploaded_file, "getvalue")
        else uploaded_file.read()
    )
    buffer = io.BytesIO(raw_bytes)
    try:
        df = pd.read_csv(buffer, encoding="utf-8")
    except UnicodeDecodeError:
        buffer.seek(0)
        df = pd.read_csv(buffer, encoding="latin-1")

    return _normalize_headers(df)


def assign_course_to_student(user_id: int, course_id: int):
    if not user_id or not course_id:
        return False

    fetch_all(
        """
        INSERT INTO spelling_enrollments (user_id, course_id)
        VALUES (:uid, :cid)
        ON CONFLICT DO NOTHING;
        """,
        {"uid": user_id, "cid": course_id},
    )
    return True


def list_classes():
    rows = fetch_all(
        """
        SELECT class_name
        FROM spelling_classes
        WHERE is_active = TRUE
        ORDER BY class_name;
        """
    )
    return [r[0] for r in rows]


def create_class(class_name: str):
    fetch_all(
        """
        INSERT INTO spelling_classes (class_name)
        VALUES (:name)
        ON CONFLICT DO NOTHING;
        """,
        {"name": class_name.strip()},
    )


# -------------------------------------------------
# Main UI
# -------------------------------------------------

def render_course_management():
    st.header("Course Management")

    courses = get_all_courses()
    course_options = {
        f"{c['course_id']} — {c['course_name']}": c["course_id"] for c in courses
    }

    selected_course_label = None
    selected_course_id = None
    if course_options:
        selected_course_label = st.selectbox(
            "Existing Courses",
            list(course_options.keys()),
        )
        selected_course_id = course_options.get(selected_course_label)
    else:
        st.info("No courses yet.")

    new_course_name = st.text_input("New Course Name")

    action_cols = st.columns(3)
    with action_cols[0]:
        if st.button("Create"):
            if not new_course_name.strip():
                st.error("Please enter a course name to create.")
            else:
                cid = create_course(new_course_name)
                if cid:
                    st.success(f"Course '{new_course_name}' created.")
                    st.experimental_rerun()
                else:
                    st.error("Failed to create course.")

    with action_cols[1]:
        if st.button("Rename"):
            if not selected_course_id:
                st.error("Select a course to rename.")
            elif not new_course_name.strip():
                st.error("Enter a new course name.")
            else:
                if rename_course(selected_course_id, new_course_name):
                    st.success(f"Course renamed to '{new_course_name}'.")
                    st.experimental_rerun()
                else:
                    st.error("Course rename failed.")

    with action_cols[2]:
        if st.checkbox("Confirm archive"):
            if st.button("Archive Course"):
                if not selected_course_id:
                    st.error("Select a course to archive.")
                else:
                    archive_course(selected_course_id)
                    st.success("Course archived successfully.")
                    st.experimental_rerun()

    st.subheader("Lessons")

    if not selected_course_id:
        st.info("Select a course to view its lessons.")
    else:
        show_archived = st.checkbox("Show archived", value=False)
        lessons = get_lessons_for_course(
            selected_course_id,
            include_archived=show_archived,
        )

        # Guard: selected lesson must belong to this course
        if st.session_state.get("selected_lesson_id"):
            valid_lesson_ids = {l["lesson_id"] for l in lessons}
            if st.session_state.selected_lesson_id not in valid_lesson_ids:
                st.session_state.selected_lesson_id = None

        if not lessons:
            st.info("No lessons for this course yet.")
        else:
            for lesson in lessons:
                if not lesson.get("is_active") and not show_archived:
                    continue

                lesson_id = lesson["lesson_id"]
                current_name = (
                    lesson.get("display_name")
                    or lesson.get("lesson_name")
                    or ""
                )
                col1, col2 = st.columns([5, 1])
                with col1:
                    new_name = st.text_input(
                        label="Lesson name",
                        value=current_name,
                        key=f"lesson_name_{lesson_id}",
                        label_visibility="collapsed",
                    )

                with col2:
                    if st.button("💾", key=f"save_lesson_{lesson_id}"):
                        update_lesson_display_name(lesson_id, new_name)
                        st.success("Lesson name updated")
                        st.experimental_rerun()

                    if lesson.get("is_active"):
                        if st.button("Archive", key=f"archive_{lesson['lesson_id']}"):
                            archive_lesson(lesson["lesson_id"])
                            archived_name = lesson.get("display_name") or lesson.get("lesson_name")
                            st.success(f"Lesson '{archived_name}' archived.")
                            st.experimental_rerun()
                    else:
                        st.caption("Archived")

    words_tab, lessons_tab, hint_ops_tab = st.tabs(["Words", "Lessons", "Hint Ops"])

    with words_tab:
        st.markdown("## Upload Spelling CSV")

        uploaded_file = st.file_uploader(
            "Upload CSV (word, pattern_code, example, difficulty)",
            type=["csv"],
            key="word_csv",
        )

        if uploaded_file and not selected_course_id:
            st.warning("Please select or create a course first.")
            return

        if uploaded_file and selected_course_id:
            if st.button("Process CSV", key="process_words_csv"):
                st.info(f"Uploading into course_id={selected_course_id}")
                result = process_spelling_csv(
                    uploaded_file,
                    course_id=selected_course_id,
                )

                if result.get("status") == "error":
                    st.error(result.get("error"))
                    return

                st.success("CSV processed successfully!")

                st.markdown("### Upload Summary")
                st.write("Words Added:", result["words_added"])
                st.write("Lessons Created:", result["lessons_created"])

                if result["patterns"]:
                    st.write("Patterns:", ", ".join(result["patterns"]))

    with lessons_tab:
        st.markdown("## Upload Lesson CSV")
        st.caption("Expected file: spelling_lessons.csv")

        lessons_file = st.file_uploader(
            "Upload CSV (lesson_code, lesson_name, course_id, description, difficulty, word_selector)",
            type=["csv"],
            key="lesson_csv",
        )

        if lessons_file is not None and st.button("Process Lessons CSV", key="process_lessons_csv"):
            df = _read_lesson_csv_with_encoding_fallback(lessons_file)
            required_columns = [
                "lesson_name",
                "course_id",
                "description",
                "difficulty",
                "word_selector",
            ]
            missing = [c for c in required_columns if c not in df.columns]
            if missing:
                st.error(f"CSV missing required columns: {', '.join(missing)}")
                st.stop()

            lessons_processed = 0
            total_mappings = 0

            for idx, row in df.iterrows():
                row_num = idx + 1
                course_id = _safe_int(row.get("course_id"))
                if course_id is None:
                    st.error(f"Row {row_num}: course_id is required.")
                    st.stop()

                lesson_name = str(row.get("lesson_name") or "").strip()
                description = row.get("description")
                description = str(description).strip() if description is not None else None
                difficulty = _safe_int(row.get("difficulty"))
                word_selector = str(row.get("word_selector") or "").strip()
                if not word_selector:
                    st.error(f"Row {row_num}: word_selector is required.")
                    st.stop()

                lesson_id = upsert_lesson(
                    course_id=course_id,
                    lesson_name=lesson_name,
                    description=description,
                    difficulty=difficulty,
                )
                word_ids = get_matching_words(course_id, word_selector)
                rebuild_lesson_mappings(lesson_id, word_ids)

                lessons_processed += 1
                total_mappings += len(word_ids)

            st.success("Lessons processed successfully!")
            st.markdown("### Lesson Upload Summary")
            st.write("Lessons processed:", lessons_processed)
            st.write("Total mappings created:", total_mappings)

    with hint_ops_tab:
        st.markdown("## 🧠 Hint Ops — AI Draft → Approve")
        st.caption("Safe workflow: upload drafts, review later, then approve to overrides.")

        course_id = st.number_input(
            "Course ID (optional for course-specific drafts)",
            min_value=0,
            value=0,
            step=1,
        )
        course_id_val = None if course_id == 0 else int(course_id)

        st.markdown("### 1) Upload AI hint drafts (CSV)")
        st.caption("CSV columns required: word OR word_id, hint_text (or hint). Optional: course_id")
        up = st.file_uploader("Upload CSV", type=["csv"], key="hint_ops_upload")

        if up is not None:
            df = pd.read_csv(up)
            df = _normalize_headers(df)

            has_word_id = "word_id" in df.columns
            has_word = "word" in df.columns

            if not (has_word_id or has_word):
                st.error("CSV must contain either 'word_id' or 'word' column.")
                st.stop()

            hint_col = "hint_text" if "hint_text" in df.columns else "hint" if "hint" in df.columns else None
            if not hint_col:
                st.error("CSV must contain hint_text (or hint) column.")
                st.stop()

            course_col = "course_id" if "course_id" in df.columns else None
            skipped = 0

            rows = []
            for _, r in df.iterrows():
                course_val = course_id_val
                if course_col:
                    course_raw = str(r.get(course_col)).strip()
                    if course_raw and course_raw.lower() not in ("nan", "none"):
                        course_val = int(course_raw)
                hint_val = str(r.get(hint_col) or "").strip()
                if hint_val.lower() in ("nan", "none"):
                    hint_val = ""
                # Resolve word_id
                if has_word_id and pd.notna(r.get("word_id")):
                    try:
                        word_id = int(r.get("word_id"))
                    except Exception:
                        skipped += 1
                        continue
                else:
                    word_raw = str(r.get("word", "")).strip()
                    if not word_raw:
                        skipped += 1
                        continue

                    rows_found = fetch_all(
                        """
                        SELECT word_id
                        FROM spelling_words
                        WHERE word = :word
                          AND (:course_id IS NULL OR course_id = :course_id)
                        """,
                        {"word": word_raw, "course_id": course_val},
                    )

                    if not rows_found:
                        skipped += 1
                        continue

                    word_id = rows_found[0][0]

                rows.append({
                    "word_id": word_id,
                    "course_id": course_val,
                    "hint_text": hint_val,
                })

            if st.button("📥 Load drafts", use_container_width=True):
                                         
                n = upsert_ai_hint_drafts(rows)
                st.success(f"Loaded {n} hint drafts into spelling_hint_ai_draft.")
                if skipped:
                    st.warning(f"Skipped {skipped} rows (word not found or invalid).")

        st.markdown("### 2) Approve drafts → Overrides (go live later)")
        st.caption("This writes only to spelling_hint_overrides. Student app is NOT changed yet.")
        if st.button("✅ Approve all drafts (this course / global)", use_container_width=True):
            approved = approve_drafts_to_overrides(course_id_val)
            st.success(f"Approved {approved} drafts to overrides.")

    with st.expander("Debug DB Status"):
        words = fetch_all("SELECT COUNT(*) AS c FROM spelling_words")
        lessons = fetch_all("SELECT COUNT(*) AS c FROM spelling_lessons")
        mappings = fetch_all("SELECT COUNT(*) AS c FROM spelling_lesson_items")

        words = rows_to_dicts(words)
        lessons = rows_to_dicts(lessons)
        mappings = rows_to_dicts(mappings)

        st.write("Words:", words[0]["c"] if words else 0)
        st.write("Lessons:", lessons[0]["c"] if lessons else 0)
        st.write("Lesson–Word Mappings:", mappings[0]["c"] if mappings else 0)

        sample = fetch_all(
            """
            SELECT sl.lesson_name, sw.word
            FROM spelling_lesson_items sli
            JOIN spelling_lessons sl ON sl.lesson_id = sli.lesson_id
            JOIN spelling_words sw ON sw.word_id = sli.word_id
            ORDER BY sl.lesson_id, sli.sort_order
            LIMIT 20;
            """
        )
        st.write("Sample mappings:")
        st.write(rows_to_dicts(sample))


def assign_student_to_class(user_id: int, class_name: str):
    fetch_all(
        """
        UPDATE spelling_users
        SET class_name = :class_name
        WHERE user_id = :user_id;
        """,
        {"user_id": user_id, "class_name": class_name},
    )


def render_student_management():
    st.markdown("## 👩‍🎓 Students (Spelling App)")
    st.subheader("🏫 Class Management")

    existing_classes = list_classes()

    new_class_name = st.text_input(
        "Create new class",
        placeholder="e.g. Year 5 – Group A",
    )

    if st.button("Create Class"):
        if not new_class_name.strip():
            st.error("Class name cannot be empty.")
        elif new_class_name in existing_classes:
            st.warning("Class already exists.")
        else:
            create_class(new_class_name)
            st.success(f"Class '{new_class_name}' created.")
            st.experimental_rerun()

    selected_class = st.selectbox(
        "Select class",
        options=existing_classes,
    )

    # ------------------------------------
    # Class roster preview (read-only)
    # ------------------------------------
    st.markdown("#### Students in selected class")

    students = list_registered_spelling_students()

    class_students = [
        s for s in students if s.get("class_name") == selected_class
    ]

    if not class_students:
        st.info(f"No students currently assigned to '{selected_class}'.")
    else:
        h1, h2 = st.columns([3, 5])
        h1.markdown("**Name**")
        h2.markdown("**Email**")

        for s in class_students:
            c1, c2 = st.columns([3, 5])
            c1.write(s["name"])
            c2.write(s["email"])

    search_term = st.text_input(
        "Search students (name or email)",
        placeholder="Type to search…",
    )

    filtered_students = []
    for s in students:
        if search_term:
            q = search_term.lower()
            if q not in s["name"].lower() and q not in s["email"].lower():
                continue
        filtered_students.append(s)

    st.markdown("### Assign students to selected class")

    if not filtered_students:
        st.info("No students match the search.")
        return

    h1, h2, h3, h4 = st.columns([1, 3, 4, 3])
    h1.markdown("**Select**")
    h2.markdown("**Name**")
    h3.markdown("**Email**")
    h4.markdown("**Current Class**")

    selected_user_ids = []

    for s in filtered_students:
        c1, c2, c3, c4 = st.columns([1, 3, 4, 3])

        with c1:
            checked = st.checkbox(
                "",
                key=f"select_student_{s['user_id']}",
            )
            if checked:
                selected_user_ids.append(s["user_id"])

        with c2:
            st.write(s["name"])

        with c3:
            st.write(s["email"])

        with c4:
            st.write(s["class_name"] or "—")

    st.divider()

    if st.button("Assign selected students to class"):
        if not selected_user_ids:
            st.warning("Please select at least one student.")
        else:
            for uid in selected_user_ids:
                assign_student_to_class(
                    user_id=uid,
                    class_name=selected_class,
                )
            st.success(
                f"{len(selected_user_ids)} student(s) assigned to class '{selected_class}'."
            )
            st.experimental_rerun()

    st.subheader("Pending Registrations")

    with engine.connect() as db:
        ensure_pending_registration_payment_status_column(db)
        ensure_pending_registration_token_column(db)

        verified_only = st.toggle("Show only payment-verified", value=False)

        rows = list_spelling_pending_registrations(db, verified_only=verified_only)

        if not rows:
            st.info("No pending registrations found.")
            return

        for r in rows:
            payment_status = (r.get("payment_status") or "unverified").lower()
            is_verified = payment_status == "verified"

            left, mid, right = st.columns([5, 2, 2])

            with left:
                st.markdown(f"**{r['student_name']}**  \n{r['email']}")
                st.caption(f"Requested: {r['requested_at']}")
                token_suffix = r.get("token_suffix")
                if token_suffix:
                    st.caption(f"Token …{token_suffix}")

            with mid:
                if is_verified:
                    st.success("✅ Verified")
                else:
                    st.warning("⏳ Unverified")

            with right:
                approve_disabled = not is_verified
                if st.button(
                    "Approve",
                    key=f"approve_{r['id']}",
                    disabled=approve_disabled,
                    help="Payment must be verified before approval." if approve_disabled else None,
                ):
                    mark_registration_approved(db, r["id"])
                    st.success("Approved. You can now assign courses / enable access.")
                    st.rerun()


def render_help_texts_page(db):
    st.header("🛠️ Help Texts")
    st.caption("Manage instructional messages shown to students")

    st.subheader("Daily 5 Help Text")

    existing = get_help_text(db, "daily5_intro")

    title = st.text_input(
        "Title (optional)",
        value=existing.title if existing else "Daily 5 — Why it matters",
    )

    body = st.text_area(
        "Help text (Markdown supported)",
        height=220,
        value=existing.body if existing else "",
    )

    if st.button("💾 Save"):
        upsert_help_text(
            db=db,
            help_key="daily5_intro",
            title=title,
            body=body,
        )
        st.success("Daily 5 help text saved successfully.")


def render_text_block_editor(db, block_key, label, placeholder=""):
    existing = get_content_block(db, block_key)

    body = st.text_area(
        label,
        value=existing.body if existing else "",
        height=160,
        placeholder=placeholder,
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button(f"💾 Save {label}", key=f"save_{block_key}"):
            upsert_content_block(
                db,
                block_key=block_key,
                body=body,
            )
            st.success(f"{label} saved.")

    with col2:
        if existing and st.button(f"🗑️ Delete {label}", key=f"delete_{block_key}"):
            delete_content_block(db, block_key)
            st.success(f"{label} deleted.")

    if body:
        st.markdown("**Preview:**")
        st.markdown(body)


def render_branding_landing_page(db):
    st.header("🎨 Branding & Landing Page")
    st.caption("Edit content shown on the Spelling app front page.")

    st.divider()

    # ---------------------------
    # Banner Image (Data URI)
    # ---------------------------
    st.subheader("Landing Banner")

    existing_banner = get_content_block(db, "landing_banner")

    if existing_banner and existing_banner.media_data:
        st.image(existing_banner.media_data, use_column_width=True)

    uploaded = st.file_uploader(
        "Upload banner image (PNG/JPG)",
        type=["png", "jpg", "jpeg"],
    )

    if uploaded:
        encoded = base64.b64encode(uploaded.read()).decode("utf-8")
        data_uri = f"data:{uploaded.type};base64,{encoded}"

        if st.button("💾 Save Banner"):
            upsert_content_block(
                db,
                block_key="landing_banner",
                media_data=data_uri,
            )
            st.success("Banner updated.")
            st.experimental_rerun()

    if existing_banner and st.button("🗑️ Delete Banner"):
        delete_content_block(db, "landing_banner")
        st.success("Banner removed.")
        st.experimental_rerun()

    st.divider()

    st.subheader("Landing Page Text")

    render_text_block_editor(
        db,
        block_key="landing_tagline",
        label="Tagline",
        placeholder="Elevate your vocabulary",
    )

    render_text_block_editor(
        db,
        block_key="landing_value",
        label="Value Proposition",
        placeholder="• Daily practice that adapts\n• Fix weak areas automatically\n• Clear progress for parents",
    )

    render_text_block_editor(
        db,
        block_key="landing_register",
        label="Registration Section",
        placeholder="One-time access: £14.99\nSecure checkout via PayPal",
    )

    render_text_block_editor(
        db,
        block_key="landing_support",
        label="Help & Support",
        placeholder="Contact us at support@wordsprint.app",
    )


def render_maintenance():
    st.divider()
    st.header("🛠 Maintenance")

    courses = get_all_courses()

    if courses:
        course_id = st.selectbox(
            "Select course for consolidation",
            options=[c["course_id"] for c in courses],
            format_func=lambda cid: next(
                c["course_name"] for c in courses if c["course_id"] == cid
            ),
        )

        if st.button("Consolidate legacy lessons into patterns"):
            with st.spinner("Running consolidation..."):
                stats = consolidate_legacy_lessons_into_patterns(course_id)

            st.success("Consolidation completed")
            st.json(stats)
    else:
        st.info("No courses available for maintenance.")


def main():
    # -------------------------------------------------
    # vNext Admin Console (Preview)
    # -------------------------------------------------
    if "admin_page" not in st.session_state:
        st.session_state.admin_page = "course_management"

    admin_options = ["Course Management", "Students", "Help Texts", "Maintenance"]
    default_index = 0

    if st.session_state.admin_page == "students":
        default_index = admin_options.index("Students")
    elif st.session_state.admin_page == "help_texts":
        default_index = admin_options.index("Help Texts")
    elif st.session_state.admin_page == "maintenance":
        default_index = admin_options.index("Maintenance")

    admin_section = st.sidebar.radio(
        "Admin Sections",
        admin_options,
        index=default_index,
    )

    if admin_section == "Course Management":
        st.session_state.admin_page = "course_management"
    elif admin_section == "Students":
        st.session_state.admin_page = "students"
    elif admin_section == "Help Texts":
        st.session_state.admin_page = "help_texts"
    elif admin_section == "Maintenance":
        st.session_state.admin_page = "maintenance"

    st.sidebar.markdown("### 🧩 Content")
    if st.sidebar.button("Help Texts"):
        st.session_state.admin_page = "help_texts"

    if st.sidebar.button("Branding & Landing"):
        st.session_state.admin_page = "branding_landing"

    if st.session_state.admin_page == "course_management":
        render_course_management()
    elif st.session_state.admin_page == "students":
        render_student_management()
    elif st.session_state.admin_page == "help_texts":
        with engine.connect() as db:
            render_help_texts_page(db)
    elif st.session_state.admin_page == "maintenance":
        render_maintenance()
    elif st.session_state.admin_page == "branding_landing":
        with engine.connect() as db:
            render_branding_landing_page(db)


if __name__ == "__main__":
    main()
