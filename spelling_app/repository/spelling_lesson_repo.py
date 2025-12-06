# spelling_app/repository/spelling_lesson_repo.py

from shared.db import fetch_all


def _to_dict(row):
    """Convert SQLAlchemy row or mapping to dict safely."""
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    if hasattr(row, "_mapping"):
        return dict(row._mapping)
    try:
        return dict(row)
    except Exception:
        return None


def _to_list(rows):
    """Convert fetch_all results into a plain list."""
    if rows is None:
        return []
    if isinstance(rows, list):
        return rows
    if hasattr(rows, "all"):  # for CursorResult
        try:
            return rows.all()
        except Exception:
            return []
    return []


# ============================================================
# LESSON LOOKUP
# ============================================================

def get_lesson_by_name_and_course(lesson_name: str, course_id: int):
    """
    Returns a lesson row for the given name + course.
    """
    rows = fetch_all(
        """
        SELECT
            lesson_id,
            lesson_name,
            course_id
        FROM spelling_lessons
        WHERE LOWER(lesson_name) = LOWER(:lesson_name)
          AND course_id = :course_id
        LIMIT 1;
        """,
        {"lesson_name": lesson_name, "course_id": course_id},
    )

    if isinstance(rows, dict):  # DB error
        return None

    rows = _to_list(rows)
    if not rows:
        return None

    return _to_dict(rows[0])


# ============================================================
# CREATE LESSON
# ============================================================

def create_lesson(lesson_name: str, course_id: int):
    """
    Inserts a new spelling lesson.
    Returns lesson_id.
    """
    rows = fetch_all(
        """
        INSERT INTO spelling_lessons (lesson_name, course_id)
        VALUES (:lesson_name, :course_id)
        RETURNING lesson_id;
        """,
        {"lesson_name": lesson_name, "course_id": course_id},
    )

    if isinstance(rows, dict):
        return None

    rows = _to_list(rows)
    if not rows:
        return None

    row = rows[0]
    if hasattr(row, "_mapping"):
        return row._mapping.get("lesson_id")
    if isinstance(row, dict):
        return row.get("lesson_id")
    try:
        return row[0]
    except:
        return None


def get_or_create_lesson(course_id: int, lesson_name: str):
    """Return an existing lesson_id or create a new lesson for the course."""
    rows = fetch_all(
        """
        SELECT lesson_id
        FROM spelling_lessons
        WHERE course_id = :cid AND lesson_name = :lname
        """,
        {"cid": course_id, "lname": lesson_name},
    )

    if rows:
        m = getattr(rows[0], "_mapping", rows[0])
        return m.get("lesson_id")

    rows = fetch_all(
        """
        INSERT INTO spelling_lessons (course_id, lesson_name)
        VALUES (:cid, :lname)
        RETURNING lesson_id
        """,
        {"cid": course_id, "lname": lesson_name},
    )

    if rows:
        m = getattr(rows[0], "_mapping", rows[0])
        return m.get("lesson_id")

    return None


# ============================================================
# WORD → LESSON MAPPING
# ============================================================

def map_word_to_lesson(word_id: int, lesson_id: int):
    """
    Map a word to a lesson.
    Ignores duplicates via ON CONFLICT DO NOTHING.
    """
    return fetch_all(
        """
        INSERT INTO spelling_lesson_words (lesson_id, word_id)
        VALUES (:lesson_id, :word_id)
        ON CONFLICT DO NOTHING;
        """,
        {"lesson_id": lesson_id, "word_id": word_id},
    )

def update_lesson_name(lesson_id: int, new_name: str):
    """
    Update the lesson name.
    """
    sql = """
        UPDATE spelling_lessons
        SET lesson_name = :new_name
        WHERE lesson_id = :lesson_id;
    """
    return fetch_all(sql, {"lesson_id": lesson_id, "new_name": new_name})


def delete_lesson(lesson_id: int):
    """
    Delete a lesson. CASCADE deletes mappings in spelling_lesson_words.
    Words remain in spelling_words (safe).
    """
    sql = """
        DELETE FROM spelling_lessons
        WHERE lesson_id = :lesson_id;
    """
    return fetch_all(sql, {"lesson_id": lesson_id})

# ============================================================
# LESSON LIST FOR A COURSE
# ============================================================

def get_lessons_for_course(course_id: int):
    """
    Returns all lessons for a given course.
    Output: list of dicts with {lesson_id, lesson_name, course_id}
    """
    rows = fetch_all(
        """
        SELECT lesson_id, lesson_name, course_id
        FROM spelling_lessons
        WHERE course_id = :cid
        ORDER BY lesson_id ASC;
        """,
        {"cid": course_id},
    )

    if isinstance(rows, dict) or not rows:
        return []

    out = []
    for r in _to_list(rows):
        out.append(_to_dict(r))
    return out


# ============================================================
# WORDS IN A LESSON
# ============================================================

def get_lesson_words(course_id: int, lesson_id: int):
    """
    Returns all words mapped to a lesson.
    Output: list of dicts with {word_id, word, pattern_code, lesson_id}
    """
    rows = fetch_all(
        """
        SELECT
            w.word_id,
            w.word,
            w.pattern_code,
            lw.lesson_id
        FROM spelling_words w
        JOIN spelling_lesson_words lw ON lw.word_id = w.word_id
        WHERE lw.lesson_id = :lid
        ORDER BY w.word_id ASC;
        """,
        {"lid": lesson_id},
    )

    if isinstance(rows, dict) or not rows:
        return []

    out = []
    for r in _to_list(rows):
        out.append(_to_dict(r))
    return out

