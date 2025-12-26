from typing import Any, Dict, List, Optional

from sqlalchemy import text

from shared.db import engine, execute, fetch_all


def _rows_to_dicts(rows: Any) -> List[Dict[str, Any]]:
    """
    Helper to normalise DB rows into plain dicts.
    Returns [] if rows is None or a dict (error payload).
    """
    if not rows or isinstance(rows, dict):
        return []

    dict_rows: List[Dict[str, Any]] = []
    for row in rows:
        if hasattr(row, "_mapping"):
            dict_rows.append(dict(row._mapping))
        elif isinstance(row, dict):
            dict_rows.append(row)
    return dict_rows


def record_wrong_attempt(user_id: int, word_id: int) -> None:
    """Insert or update a weak word for the user after an incorrect attempt."""
    sql = text(
        """
        INSERT INTO weak_words (user_id, word_id, incorrect_count, last_seen_at, is_resolved, created_at)
        VALUES (:user_id, :word_id, 1, NOW(), FALSE, NOW())
        ON CONFLICT (user_id, word_id)
        DO UPDATE SET
            incorrect_count = weak_words.incorrect_count + 1,
            last_seen_at = NOW(),
            is_resolved = FALSE
        """
    )
    execute(sql, {"user_id": user_id, "word_id": word_id})


def record_correct_attempt(user_id: int, word_id: int) -> None:
    """Placeholder: correct attempts do not immediately resolve weak words."""
    return None


def record_attempt(user_id: int, word_id: int, correct: bool, time_taken: int) -> None:
    """Insert a spelling attempt for the student."""
    execute(
        text(
            """
            INSERT INTO spelling_attempts
                (user_id, word_id, correct, time_taken, created_at)
            VALUES
                (:user_id, :word_id, :correct, :time_taken, NOW())
            """
        ),
        {
            "user_id": user_id,
            "word_id": word_id,
            "correct": correct,
            "time_taken": time_taken,
        },
    )

    if not correct:
        record_wrong_attempt(user_id, word_id)
    else:
        record_correct_attempt(user_id, word_id)


def get_weak_words(user_id: int) -> List[Dict[str, Any]]:
    """Return the user's weak words ordered by recency and mistake count."""
    rows = fetch_all(
        text(
            """
            SELECT
                ww.word_id,
                w.word,
                MIN(li.lesson_id) AS lesson_id,
                ww.incorrect_count,
                ww.last_seen_at
            FROM weak_words ww
            JOIN spelling_words w ON w.word_id = ww.word_id
            LEFT JOIN spelling_lesson_items li ON li.word_id = ww.word_id
            WHERE ww.user_id = :uid
              AND ww.is_resolved = FALSE
            GROUP BY ww.word_id, w.word, ww.incorrect_count, ww.last_seen_at
            ORDER BY ww.last_seen_at DESC, ww.incorrect_count DESC
            """
        ),
        {"uid": user_id},
    )

    return _rows_to_dicts(rows)


def upsert_weak_word(user_id: int, word_id: int, lesson_id: int | None = None) -> None:
    """Compat wrapper to preserve old imports; forwards to record_wrong_attempt."""
    record_wrong_attempt(user_id, word_id)


# ---------------------------------------------------------
# PENDING REGISTRATIONS
# ---------------------------------------------------------
def get_pending_spelling_students() -> List[Dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT pending_id, student_name, email, created_at
        FROM pending_spelling_registrations
        ORDER BY created_at DESC
        """
    )
    return _rows_to_dicts(rows)


def approve_spelling_student(pending_id: int, default_password_hash: str) -> bool:
    """
    Approve a pending spelling student:
    - read from pending_spelling_registrations
    - insert into users with app_source='spelling'
    - delete from pending table
    """
    pending_rows = fetch_all(
        """
        SELECT pending_id, student_name, email
        FROM pending_spelling_registrations
        WHERE pending_id = :pid
        """,
        {"pid": pending_id},
    )

    pending_list = _rows_to_dicts(pending_rows)
    if not pending_list:
        return False

    pending = pending_list[0]

    execute(
        """
        INSERT INTO users (name, email, password_hash, role, status, class_name, app_source)
        VALUES (:name, :email, :phash, 'student', 'ACTIVE', NULL, 'spelling')
        """,
        {
            "name": pending.get("student_name"),
            "email": pending.get("email"),
            "phash": default_password_hash,
        },
    )

    execute(
        """
        DELETE FROM pending_spelling_registrations
        WHERE pending_id = :pid
        """,
        {"pid": pending_id},
    )

    return True


# ---------------------------------------------------------
# REGISTERED SPELLING STUDENTS
# ---------------------------------------------------------
def list_registered_spelling_students() -> List[Dict[str, Any]]:
    """
    Return ONLY spelling students (role=student AND app_source='spelling'),
    with a comma-separated list of registered courses.
    """
    rows = fetch_all(
        """
        SELECT
            u.user_id,
            u.name,
            u.email,
            u.class_name,
            u.status,
            COALESCE(string_agg(c.course_name, ', ' ORDER BY c.course_name), '') AS registered_courses
        FROM users u
        LEFT JOIN spelling_enrollments e ON e.user_id = u.user_id
        LEFT JOIN spelling_courses c ON c.course_id = e.course_id
        WHERE u.role = 'student' AND u.app_source = 'spelling'
        GROUP BY u.user_id, u.name, u.email, u.class_name, u.status
        ORDER BY u.name
        """
    )

    return _rows_to_dicts(rows)


def update_student_profile(
    user_id: int, class_name: Optional[str], status: str
) -> None:
    """
    Update class_name + status for a spelling student.
    """
    execute(
        """
        UPDATE users
        SET class_name = :cname, status = :status
        WHERE user_id = :uid AND role = 'student' AND app_source = 'spelling'
        """,
        {"cname": class_name, "status": status, "uid": user_id},
    )


# ---------------------------------------------------------
# COURSE ENROLMENTS
# ---------------------------------------------------------
def get_student_courses(user_id: int) -> List[Dict[str, Any]]:
    """
    AUTHORITATIVE student course visibility.
    Enrollment row existence = visibility.
    """

    sql = text(
        """
        SELECT
            c.course_id,
            c.course_name,
            c.description
        FROM spelling_enrollments e
        JOIN spelling_courses c
          ON c.course_id = e.course_id
        WHERE e.user_id = :user_id
        ORDER BY c.course_name
    """
    )

    with engine.connect() as conn:
        return conn.execute(sql, {"user_id": user_id}).mappings().all()


def assign_courses_to_student(user_id: int, course_ids: List[int]) -> None:
    """
    Assign multiple courses to a student (idempotent).
    """
    if not course_ids:
        return

    for course_id in course_ids:
        execute(
            """
            INSERT INTO spelling_enrollments (user_id, course_id)
            VALUES (:uid, :cid)
            ON CONFLICT DO NOTHING
            """,
            {"uid": user_id, "cid": course_id},
        )


def remove_courses_from_student(user_id: int, course_ids: List[int]) -> None:
    """
    Remove multiple courses from a student.
    """
    if not course_ids:
        return

    for course_id in course_ids:
        execute(
            """
            DELETE FROM spelling_enrollments
            WHERE user_id = :uid AND course_id = :cid
            """,
            {"uid": user_id, "cid": course_id},
        )


# ---------------------------------------------------------
# LESSONS
# ---------------------------------------------------------
def get_lessons_for_course(course_id: int) -> List[Dict[str, Any]]:
    """
    AUTHORITATIVE lesson fetch.
    Lessons must ALWAYS be visible regardless of word mappings.
    """
    from sqlalchemy import text

    sql = text(
        """
        SELECT
            lesson_id,
            lesson_name,
            course_id,
            sort_order,
            is_active
        FROM spelling_lessons
        WHERE course_id = :course_id
          AND is_active = TRUE
        ORDER BY sort_order, lesson_id
    """
    )

    with engine.connect() as conn:
        return conn.execute(sql, {"course_id": course_id}).mappings().all()


def get_words_for_lesson(lesson_id: int) -> List[Dict[str, Any]]:
    with engine.connect() as conn:
        primary_sql = text(
            """
            SELECT w.word_id,
                   w.word,
                   w.pattern,
                   w.pattern_code,
                   w.level,
                   w.lesson_name,
                   w.example_sentence
            FROM spelling_words w
            JOIN spelling_lesson_items li ON li.word_id = w.word_id
            WHERE li.lesson_id = :lesson_id
            ORDER BY w.word
            """
        )
        rows = conn.execute(primary_sql, {"lesson_id": lesson_id}).mappings().all()
        if rows:
            return _rows_to_dicts(rows)

        fallback_sql = text(
            """
            SELECT w.word_id,
                   w.word,
                   w.pattern,
                   w.pattern_code,
                   w.level,
                   w.lesson_name,
                   w.example_sentence
            FROM spelling_words w
            JOIN spelling_lesson_words lw ON lw.word_id = w.word_id
            WHERE lw.lesson_id = :lesson_id
            ORDER BY w.word
            """
        )
        return _rows_to_dicts(
            conn.execute(fallback_sql, {"lesson_id": lesson_id}).mappings().all()
        )


def get_resume_index_for_lesson(student_id, lesson_id):
    """
    Resume Word Mastery progress safely.
    Derives lesson membership via lesson→word mappings.
    Schema-agnostic and non-breaking.
    """

    with engine.connect() as conn:

        # --- 1) Ordered lesson words (Word Mastery only) ---
        lesson_words_sql = text(
            """
            SELECT w.word_id
            FROM spelling_lesson_items sli
            JOIN spelling_words w ON w.word_id = sli.word_id
            WHERE sli.lesson_id = :lesson_id
            ORDER BY w.word
        """
        )

        lesson_word_ids = [
            row.word_id
            for row in conn.execute(lesson_words_sql, {"lesson_id": lesson_id}).fetchall()
        ]

        if not lesson_word_ids:
            return 0

        # --- 2) Detect user column in spelling_attempts ---
        cols_sql = text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'spelling_attempts'
        """
        )

        columns = {r.column_name for r in conn.execute(cols_sql).fetchall()}

        if "user_id" in columns:
            user_col = "user_id"
        elif "student_id" in columns:
            user_col = "student_id"
        elif "student_user_id" in columns:
            user_col = "student_user_id"
        else:
            return 0  # fail safe

        # --- 3) Last correct attempt FOR THIS LESSON (via JOIN) ---
        last_correct_sql = text(
            f"""
            SELECT sa.word_id
            FROM spelling_attempts sa
            JOIN spelling_lesson_items sli
              ON sli.word_id = sa.word_id
            WHERE sa.{user_col} = :student_id
              AND sli.lesson_id = :lesson_id
              AND sa.correct = TRUE
            ORDER BY sa.created_at DESC
            LIMIT 1
        """
        )

        row = conn.execute(
            last_correct_sql,
            {"student_id": student_id, "lesson_id": lesson_id},
        ).fetchone()

        if not row:
            return 0

        # --- 4) Resume from next word ---
        try:
            last_index = lesson_word_ids.index(row.word_id)
            return min(last_index + 1, len(lesson_word_ids))
        except ValueError:
            return 0


def get_words_by_ids(word_ids: List[int]) -> List[Dict[str, Any]]:
    if not word_ids:
        return []

    placeholders = ", ".join([f":w{i}" for i in range(len(word_ids))])
    params = {f"w{i}": wid for i, wid in enumerate(word_ids)}

    sql = text(
        f"""
        SELECT word_id,
               word,
               pattern,
               pattern_code,
               level,
               lesson_name,
               example_sentence
        FROM spelling_words
        WHERE word_id IN ({placeholders})
        ORDER BY CASE word_id {" ".join([f'WHEN :w{i} THEN {i}' for i in range(len(word_ids))])} END
        """
    )

    rows = fetch_all(sql, params)
    return _rows_to_dicts(rows)


def get_daily_five_word_ids(user_id: int) -> List[int]:
    weak_rows = fetch_all(
        text(
            """
            SELECT word_id
            FROM weak_words
            WHERE user_id = :uid
              AND is_resolved = FALSE
            ORDER BY last_seen_at DESC, incorrect_count DESC
            LIMIT 3
            """
        ),
        {"uid": user_id},
    )

    result: List[int] = []
    seen: set[int] = set()

    for row in _rows_to_dicts(weak_rows):
        wid = row.get("word_id")
        if wid is not None and wid not in seen:
            result.append(wid)
            seen.add(wid)

    remaining_slots = 5 - len(result)

    if remaining_slots > 0:
        recent_rows = fetch_all(
            text(
                """
                SELECT DISTINCT a.word_id
                FROM spelling_attempts a
                LEFT JOIN weak_words w
                  ON w.word_id = a.word_id AND w.user_id = :uid
                WHERE a.user_id = :uid
                  AND a.correct = false
                  AND w.word_id IS NULL
                ORDER BY a.created_at DESC
                LIMIT 2
                """
            ),
            {"uid": user_id},
        )

        for row in _rows_to_dicts(recent_rows):
            wid = row.get("word_id")
            if wid is not None and wid not in seen and len(result) < 5:
                result.append(wid)
                seen.add(wid)

    remaining_slots = 5 - len(result)

    if remaining_slots > 0:
        backfill_rows = fetch_all(
            text(
                """
                SELECT DISTINCT a.word_id
                FROM spelling_attempts a
                WHERE a.user_id = :uid
                  AND a.correct = true
                ORDER BY a.created_at ASC
                LIMIT :lim
                """
            ),
            {"uid": user_id, "lim": remaining_slots},
        )

        for row in _rows_to_dicts(backfill_rows):
            wid = row.get("word_id")
            if wid is not None and wid not in seen and len(result) < 5:
                result.append(wid)
                seen.add(wid)

    return result
