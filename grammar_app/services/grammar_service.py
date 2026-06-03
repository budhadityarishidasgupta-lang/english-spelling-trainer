from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

from shared.db import execute

DEFAULT_COURSE_NAME = "GrammarSprint v1"
DEFAULT_DIFFICULTY = 1
DEFAULT_SOURCE_REF = "csv_upload"

COURSE_TABLE = "grammar_courses"
LESSON_TABLE = "grammar_lessons"
QUESTION_TABLE = "grammar_questions"
LESSON_ITEM_TABLE = "grammar_lesson_items"
ATTEMPT_TABLE = "grammar_attempts"
QUESTION_STATS_TABLE = "grammar_question_stats"
LESSON_PROGRESS_TABLE = "grammar_lesson_progress"

REQUIRED_UPLOAD_COLUMNS = {
    "lesson_code",
    "question_type",
    "question_text",
    "option_a",
    "option_b",
    "option_c",
    "option_d",
    "correct_option",
}

OPTION_COLUMNS = ("option_a", "option_b", "option_c", "option_d")


def _safe_execute(query: str, params: Optional[Dict[str, Any]] = None):
    result = execute(query, params or {})
    if isinstance(result, dict) and result.get("error"):
        raise RuntimeError(result["error"])
    return result


def _rows_to_dicts(rows: Any) -> List[Dict[str, Any]]:
    if not rows:
        return []
    if isinstance(rows, dict):
        return [dict(rows)]

    dict_rows: List[Dict[str, Any]] = []
    for row in rows:
        if hasattr(row, "_mapping"):
            dict_rows.append(dict(row._mapping))
        elif isinstance(row, dict):
            dict_rows.append(dict(row))
        elif isinstance(row, (list, tuple)):
            dict_rows.append({"value": row[0] if row else None})
        else:
            dict_rows.append({"value": row})
    return dict_rows


def _first_row(rows: Any) -> Optional[Dict[str, Any]]:
    dict_rows = _rows_to_dicts(rows)
    return dict_rows[0] if dict_rows else None


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _normalize_lower(value: Any) -> str:
    return _clean_text(value).lower()


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    try:
        return int(float(value))
    except Exception:
        return default


@lru_cache(maxsize=None)
def _table_columns(table_name: str) -> tuple[str, ...]:
    rows = _safe_execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = :table_name
        ORDER BY ordinal_position
        """,
        {"table_name": table_name},
    )
    cols: List[str] = []
    for row in _rows_to_dicts(rows):
        col = row.get("column_name") or row.get("value")
        if col:
            cols.append(str(col).lower())
    return tuple(cols)


def _preferred_column(table_name: str, candidates: Iterable[str]) -> Optional[str]:
    cols = set(_table_columns(table_name))
    for candidate in candidates:
        if candidate.lower() in cols:
            return candidate.lower()
    return None


def _select_one(table_name: str, where_sql: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    rows = _safe_execute(f"SELECT * FROM {table_name} WHERE {where_sql} LIMIT 1", params)
    return _first_row(rows)


def _select_all(table_name: str, where_sql: str = "1=1", params: Optional[Dict[str, Any]] = None, order_sql: str = "") -> List[Dict[str, Any]]:
    sql = f"SELECT * FROM {table_name} WHERE {where_sql}"
    if order_sql:
        sql += f" ORDER BY {order_sql}"
    return _rows_to_dicts(_safe_execute(sql, params or {}))


def _insert_row(table_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    insertable = {k: v for k, v in payload.items() if k.lower() in _table_columns(table_name) and v is not None}
    if not insertable:
        raise RuntimeError(f"No insertable columns found for {table_name}")

    cols = list(insertable.keys())
    placeholders = ", ".join(f":{c}" for c in cols)
    column_sql = ", ".join(cols)
    rows = _safe_execute(
        f"INSERT INTO {table_name} ({column_sql}) VALUES ({placeholders}) RETURNING *",
        insertable,
    )
    return _first_row(rows) or insertable


def _update_row(table_name: str, key_filters: Dict[str, Any], payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    updates = {
        k: v
        for k, v in payload.items()
        if k.lower() in _table_columns(table_name) and v is not None and k not in key_filters
    }
    if not updates:
        return _select_one(table_name, " AND ".join(f"{k} = :{k}" for k in key_filters), key_filters)

    set_sql = ", ".join(f"{k} = :{k}" for k in updates)
    params = {**key_filters, **updates}
    where_sql = " AND ".join(f"{k} = :{k}" for k in key_filters)
    _safe_execute(f"UPDATE {table_name} SET {set_sql} WHERE {where_sql}", params)
    return _select_one(table_name, where_sql, key_filters)


def _upsert_row(table_name: str, key_filters: Dict[str, Any], payload: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    existing = _select_one(table_name, " AND ".join(f"{k} = :{k}" for k in key_filters), key_filters)
    if existing:
        updated = _update_row(table_name, key_filters, payload)
        return updated or existing, "updated"
    merged = {**key_filters, **payload}
    return _insert_row(table_name, merged), "inserted"


def _user_identity_filters(user_id: Any = None, user_email: Any = None) -> Dict[str, Any]:
    filters: Dict[str, Any] = {}
    if user_id is not None and _preferred_column(ATTEMPT_TABLE, ("user_id",)):
        filters["user_id"] = int(user_id)
    if user_email:
        email = _clean_text(user_email)
        if email and _preferred_column(ATTEMPT_TABLE, ("user_email", "email")):
            email_col = _preferred_column(ATTEMPT_TABLE, ("user_email", "email"))
            if email_col:
                filters[email_col] = email
    return filters


def has_grammar_access(user_email: str) -> bool:
    """
    First-build access gate for GrammarSprint.

    TODO: wire to Kiarolabs membership-service using product_code GSM / app_code grammar.
    """
    return True


def get_grammar_course_by_name(course_name: str = DEFAULT_COURSE_NAME) -> Optional[Dict[str, Any]]:
    course_col = _preferred_column(COURSE_TABLE, ("course_name", "title", "name"))
    if not course_col:
        return None
    return _select_one(
        COURSE_TABLE,
        f"LOWER(TRIM({course_col})) = LOWER(TRIM(:course_name))",
        {"course_name": course_name},
    )


def list_grammar_lessons(course_id: int, user_id: int | None = None, user_email: str | None = None) -> List[Dict[str, Any]]:
    sort_col = _preferred_column(LESSON_TABLE, ("sort_order", "order_index", "display_order")) or "lesson_id"
    lessons = _select_all(
        LESSON_TABLE,
        "course_id = :course_id",
        {"course_id": int(course_id)},
        order_sql=f"{sort_col}, lesson_code, lesson_name",
    )
    progress_map = get_student_grammar_progress(user_id=user_id or 0, course_id=course_id, user_email=user_email) if (user_id is not None or user_email) else []
    indexed_progress = {row["lesson_id"]: row for row in progress_map}

    combined: List[Dict[str, Any]] = []
    for lesson in lessons:
        progress = indexed_progress.get(lesson.get("lesson_id"), {})
        combined.append({**lesson, **progress})
    return combined


def get_grammar_lesson_by_code(course_id: int, lesson_code: str) -> Optional[Dict[str, Any]]:
    lesson_col = _preferred_column(LESSON_TABLE, ("lesson_code", "code", "slug"))
    if not lesson_col:
        return None
    return _select_one(
        LESSON_TABLE,
        f"course_id = :course_id AND LOWER(TRIM({lesson_col})) = LOWER(TRIM(:lesson_code))",
        {"course_id": int(course_id), "lesson_code": lesson_code},
    )


def get_grammar_lesson_by_name(course_id: int, lesson_name: str) -> Optional[Dict[str, Any]]:
    lesson_col = _preferred_column(LESSON_TABLE, ("lesson_name", "title", "name"))
    if not lesson_col:
        return None
    return _select_one(
        LESSON_TABLE,
        f"course_id = :course_id AND LOWER(TRIM({lesson_col})) = LOWER(TRIM(:lesson_name))",
        {"course_id": int(course_id), "lesson_name": lesson_name},
    )


def _question_payload_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "question_type": _clean_text(row.get("question_type")) or "mcq",
        "question_text": _clean_text(row.get("question_text")),
        "option_a": _clean_text(row.get("option_a")),
        "option_b": _clean_text(row.get("option_b")),
        "option_c": _clean_text(row.get("option_c")),
        "option_d": _clean_text(row.get("option_d")),
        "correct_option": _clean_text(row.get("correct_option")),
        "explanation": _clean_text(row.get("explanation")),
        "difficulty": _to_int(row.get("difficulty"), DEFAULT_DIFFICULTY),
        "skill_tag": _clean_text(row.get("skill_tag")),
        "source_ref": _clean_text(row.get("source_ref")) or DEFAULT_SOURCE_REF,
    }
    return payload


def get_grammar_question_by_course_and_text(course_id: int, question_text: str) -> Optional[Dict[str, Any]]:
    question_col = _preferred_column(QUESTION_TABLE, ("question_text", "text", "prompt"))
    if not question_col:
        return None
    return _select_one(
        QUESTION_TABLE,
        f"course_id = :course_id AND LOWER(TRIM({question_col})) = LOWER(TRIM(:question_text))",
        {"course_id": int(course_id), "question_text": question_text},
    )


def upsert_grammar_question(row: Dict[str, Any]) -> Dict[str, Any]:
    course_name = _clean_text(row.get("course_name")) or DEFAULT_COURSE_NAME
    course = get_grammar_course_by_name(course_name)
    if not course:
        raise RuntimeError(f"Grammar course not found: {course_name}")

    lesson = None
    lesson_code = _clean_text(row.get("lesson_code"))
    lesson_name = _clean_text(row.get("lesson_name"))
    if lesson_code:
        lesson = get_grammar_lesson_by_code(int(course["course_id"]), lesson_code)
    if not lesson and lesson_name:
        lesson = get_grammar_lesson_by_name(int(course["course_id"]), lesson_name)
    if not lesson:
        raise RuntimeError(f"Lesson not found for course {course_name}")

    payload = _question_payload_from_row(row)
    existing = get_grammar_question_by_course_and_text(int(course["course_id"]), payload["question_text"])
    key_filters = {"course_id": int(course["course_id"]), "question_text": payload["question_text"]}

    if existing:
        updated = _update_row(QUESTION_TABLE, key_filters, payload)
        question = updated or existing
        status = "updated"
    else:
        question = _insert_row(QUESTION_TABLE, {**key_filters, **payload})
        status = "inserted"

    return {"course": course, "lesson": lesson, "question": question, "status": status}


def map_question_to_lesson(lesson_id: int, question_id: int, sort_order: int | None = None) -> Dict[str, Any]:
    existing = _select_one(
        LESSON_ITEM_TABLE,
        "lesson_id = :lesson_id AND question_id = :question_id",
        {"lesson_id": int(lesson_id), "question_id": int(question_id)},
    )
    payload: Dict[str, Any] = {}
    if sort_order is not None:
        payload["sort_order"] = int(sort_order)

    if existing:
        updated = _update_row(
            LESSON_ITEM_TABLE,
            {"lesson_id": int(lesson_id), "question_id": int(question_id)},
            payload,
        )
        return {"lesson_item": updated or existing, "status": "existing"}

    lesson_item = _insert_row(LESSON_ITEM_TABLE, {"lesson_id": int(lesson_id), "question_id": int(question_id), **payload})
    return {"lesson_item": lesson_item, "status": "created"}


def ingest_grammar_csv(uploaded_file) -> Dict[str, Any]:
    try:
        df = pd.read_csv(uploaded_file)
    except Exception as exc:
        return {"error": f"Could not read CSV: {exc}"}

    cleaned = df.copy()
    cleaned.columns = [str(col).strip().lower() for col in cleaned.columns]

    missing = sorted(REQUIRED_UPLOAD_COLUMNS - set(cleaned.columns))
    if missing:
        return {"error": f"CSV must contain columns: {', '.join(missing)}"}

    summary = {
        "rows_seen": int(len(cleaned)),
        "rows_inserted": 0,
        "rows_updated": 0,
        "mappings_created": 0,
        "mappings_existing": 0,
        "errors": [],
    }
    details: List[Dict[str, Any]] = []

    for index, row in cleaned.iterrows():
        row_number = int(index) + 2
        row_data = {k: row.get(k) for k in cleaned.columns}
        course_name = _clean_text(row_data.get("course_name")) or DEFAULT_COURSE_NAME
        row_data["course_name"] = course_name
        row_data["difficulty"] = row_data.get("difficulty") if _clean_text(row_data.get("difficulty")) else DEFAULT_DIFFICULTY
        row_data["source_ref"] = row_data.get("source_ref") if _clean_text(row_data.get("source_ref")) else DEFAULT_SOURCE_REF

        required_values = {field: _clean_text(row_data.get(field)) for field in REQUIRED_UPLOAD_COLUMNS}
        invalid_fields = [field for field, value in required_values.items() if not value]
        if invalid_fields:
            summary["errors"].append({"row": row_number, "error": f"Missing required fields: {', '.join(sorted(invalid_fields))}"})
            continue

        course = get_grammar_course_by_name(course_name)
        if not course:
            summary["errors"].append({"row": row_number, "error": f"Course not found: {course_name}"})
            continue

        lesson = None
        lesson_code = _clean_text(row_data.get("lesson_code"))
        lesson_name = _clean_text(row_data.get("lesson_name"))
        if lesson_code:
            lesson = get_grammar_lesson_by_code(int(course["course_id"]), lesson_code)
        if not lesson and lesson_name:
            lesson = get_grammar_lesson_by_name(int(course["course_id"]), lesson_name)
        if not lesson:
            summary["errors"].append({"row": row_number, "error": f"Lesson not found for course {course_name}"})
            continue

        try:
            question_result = upsert_grammar_question(row_data)
        except Exception as exc:
            summary["errors"].append({"row": row_number, "error": str(exc)})
            continue

        question = question_result["question"]
        if question_result["status"] == "inserted":
            summary["rows_inserted"] += 1
        else:
            summary["rows_updated"] += 1

        mapping_result = map_question_to_lesson(
            int(lesson["lesson_id"]),
            int(question["question_id"]),
            _to_int(row_data.get("sort_order"), 0) or None,
        )
        if mapping_result["status"] == "created":
            summary["mappings_created"] += 1
        else:
            summary["mappings_existing"] += 1

        details.append(
            {
                "row": row_number,
                "course_name": course_name,
                "lesson_code": lesson_code,
                "lesson_name": lesson_name,
                "question_text": required_values["question_text"],
                "question_status": question_result["status"],
                "mapping_status": mapping_result["status"],
            }
        )

    return {
        "summary": summary,
        "details": details,
        "errors": summary["errors"],
        "rows_seen": summary["rows_seen"],
        "rows_inserted": summary["rows_inserted"],
        "rows_updated": summary["rows_updated"],
        "mappings_created": summary["mappings_created"],
        "mappings_existing": summary["mappings_existing"],
    }


def get_lesson_questions(lesson_id: int, user_id: int | None = None) -> List[Dict[str, Any]]:
    rows = _rows_to_dicts(
        _safe_execute(
            f"""
            SELECT q.*
            FROM {LESSON_ITEM_TABLE} li
            JOIN {QUESTION_TABLE} q ON q.question_id = li.question_id
            WHERE li.lesson_id = :lesson_id
            ORDER BY COALESCE(li.sort_order, q.question_id)
            """,
            {"lesson_id": int(lesson_id)},
        )
    )
    return [dict(row, options={"A": _clean_text(row.get("option_a")), "B": _clean_text(row.get("option_b")), "C": _clean_text(row.get("option_c")), "D": _clean_text(row.get("option_d"))}) for row in rows]


def get_next_question(lesson_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    questions = get_lesson_questions(lesson_id, user_id=user_id)
    if not questions:
        return None

    user_col = _preferred_column(ATTEMPT_TABLE, ("user_id", "user_email", "email"))
    if user_col != "user_id":
        return questions[0]

    attempted = _rows_to_dicts(
        _safe_execute(
            f"SELECT DISTINCT question_id FROM {ATTEMPT_TABLE} WHERE lesson_id = :lesson_id AND user_id = :user_id",
            {"lesson_id": int(lesson_id), "user_id": int(user_id)},
        )
    )
    attempted_ids = {row.get("question_id") for row in attempted}
    for question in questions:
        if question.get("question_id") not in attempted_ids:
            return question
    return None


def _attempt_stats_for_lesson(user_id: int, lesson_id: int) -> Dict[str, Any]:
    user_filter_col = _preferred_column(ATTEMPT_TABLE, ("user_id", "user_email", "email"))
    user_filter_sql = ""
    params: Dict[str, Any] = {"lesson_id": int(lesson_id)}
    if user_filter_col == "user_id":
        user_filter_sql = " AND user_id = :user_id"
        params["user_id"] = int(user_id)
    elif user_filter_col:
        return {"total_attempts": 0, "correct_attempts": 0, "attempted_questions": 0}

    rows = _rows_to_dicts(
        _safe_execute(
            f"""
            SELECT
                COUNT(*) AS total_attempts,
                COALESCE(SUM(CASE WHEN is_correct THEN 1 ELSE 0 END), 0) AS correct_attempts,
                COUNT(DISTINCT question_id) AS attempted_questions
            FROM {ATTEMPT_TABLE}
            WHERE lesson_id = :lesson_id{user_filter_sql}
            """,
            params,
        )
    )
    return rows[0] if rows else {"total_attempts": 0, "correct_attempts": 0, "attempted_questions": 0}


def get_lesson_progress(user_id: int, lesson_id: int) -> Dict[str, Any]:
    total_questions = len(get_lesson_questions(lesson_id, user_id=user_id))
    stats = _attempt_stats_for_lesson(user_id, lesson_id)
    total_attempts = int(stats.get("total_attempts") or 0)
    correct_attempts = int(stats.get("correct_attempts") or 0)
    attempted_questions = int(stats.get("attempted_questions") or 0)
    accuracy = round((correct_attempts / total_attempts) * 100, 2) if total_attempts else 0.0
    completed = total_questions > 0 and attempted_questions >= total_questions

    return {
        "lesson_id": int(lesson_id),
        "total_questions": total_questions,
        "attempted_questions": attempted_questions,
        "correct_attempts": correct_attempts,
        "total_attempts": total_attempts,
        "accuracy_pct": accuracy,
        "is_completed": completed,
    }


def update_grammar_question_stats(user_id: int, question_id: int) -> Dict[str, Any]:
    rows = _rows_to_dicts(
        _safe_execute(
            f"""
            SELECT
                COUNT(*) AS total_attempts,
                COALESCE(SUM(CASE WHEN is_correct THEN 1 ELSE 0 END), 0) AS correct_attempts,
                MAX(attempted_on) AS last_attempted_at
            FROM {ATTEMPT_TABLE}
            WHERE question_id = :question_id
            """,
            {"question_id": int(question_id)},
        )
    )
    stats = rows[0] if rows else {"total_attempts": 0, "correct_attempts": 0}
    total_attempts = int(stats.get("total_attempts") or 0)
    correct_attempts = int(stats.get("correct_attempts") or 0)
    accuracy_pct = round((correct_attempts / total_attempts) * 100, 2) if total_attempts else 0.0

    payload = {
        "question_id": int(question_id),
        "user_id": int(user_id),
        "total_attempts": total_attempts,
        "correct_attempts": correct_attempts,
        "accuracy_pct": accuracy_pct,
        "last_attempted_at": stats.get("last_attempted_at"),
    }
    existing = _select_one(QUESTION_STATS_TABLE, "question_id = :question_id", {"question_id": int(question_id)})
    if existing:
        updated = _update_row(QUESTION_STATS_TABLE, {"question_id": int(question_id)}, payload)
        return updated or existing
    return _insert_row(QUESTION_STATS_TABLE, payload)


def update_grammar_lesson_progress(user_id: int, course_id: int, lesson_id: int) -> Dict[str, Any]:
    progress = get_lesson_progress(user_id, lesson_id)
    payload = {
        "user_id": int(user_id),
        "course_id": int(course_id),
        "lesson_id": int(lesson_id),
        "total_questions": progress["total_questions"],
        "attempted_questions": progress["attempted_questions"],
        "correct_attempts": progress["correct_attempts"],
        "total_attempts": progress["total_attempts"],
        "accuracy_pct": progress["accuracy_pct"],
        "is_completed": progress["is_completed"],
        "updated_at": None,
    }
    completed_col = _preferred_column(LESSON_PROGRESS_TABLE, ("completed_at", "completed_on"))
    if progress["is_completed"] and completed_col:
        payload[completed_col] = pd.Timestamp.utcnow().to_pydatetime()

    key_filters = {"user_id": int(user_id), "lesson_id": int(lesson_id)}
    existing = _select_one(LESSON_PROGRESS_TABLE, "user_id = :user_id AND lesson_id = :lesson_id", key_filters)
    if existing:
        updated = _update_row(LESSON_PROGRESS_TABLE, key_filters, payload)
        return updated or existing
    return _insert_row(LESSON_PROGRESS_TABLE, payload)


def record_grammar_attempt(
    user_id: int,
    course_id: int,
    lesson_id: int,
    question_id: int,
    selected_option: str,
    time_taken: int | None = None,
    user_email: str | None = None,
) -> Dict[str, Any]:
    question = _select_one(QUESTION_TABLE, "question_id = :question_id", {"question_id": int(question_id)})
    if not question:
        raise RuntimeError("Question not found")

    correct_option = _clean_text(question.get("correct_option"))
    selected = _clean_text(selected_option)
    is_correct = _normalize_lower(selected) == _normalize_lower(correct_option)

    payload: Dict[str, Any] = {
        "user_id": int(user_id),
        "course_id": int(course_id),
        "lesson_id": int(lesson_id),
        "question_id": int(question_id),
        "selected_option": selected,
        "is_correct": bool(is_correct),
    }
    if time_taken is not None and _preferred_column(ATTEMPT_TABLE, ("time_taken",)):
        payload["time_taken"] = int(time_taken)
    if user_email and _preferred_column(ATTEMPT_TABLE, ("user_email", "email")):
        email_col = _preferred_column(ATTEMPT_TABLE, ("user_email", "email"))
        if email_col:
            payload[email_col] = _clean_text(user_email)

    attempt = _insert_row(ATTEMPT_TABLE, payload)
    update_grammar_question_stats(user_id, question_id)
    progress = update_grammar_lesson_progress(user_id, course_id, lesson_id)
    return {"attempt": attempt, "progress": progress, "is_correct": is_correct, "correct_option": correct_option}


def get_student_grammar_progress(user_id: int, course_id: int) -> List[Dict[str, Any]]:
    lessons = list_grammar_lessons(course_id, user_id=user_id)
    results: List[Dict[str, Any]] = []
    next_found = False
    for lesson in lessons:
        progress = get_lesson_progress(user_id, int(lesson["lesson_id"]))
        row = {**lesson, **progress}
        row["lesson_id"] = int(lesson["lesson_id"])
        row["is_next_recommended"] = False
        if not next_found and not row.get("is_completed"):
            row["is_next_recommended"] = True
            next_found = True
        results.append(row)
    return results


def _normalize_question_row(question: Dict[str, Any]) -> Dict[str, Any]:
    options = {
        "A": _clean_text(question.get("option_a")),
        "B": _clean_text(question.get("option_b")),
        "C": _clean_text(question.get("option_c")),
        "D": _clean_text(question.get("option_d")),
    }
    question = dict(question)
    question["options"] = options
    return question


def get_grammar_lesson_questions(lesson_id: int) -> List[Dict[str, Any]]:
    rows = _rows_to_dicts(
        _safe_execute(
            f"""
            SELECT q.*
            FROM {LESSON_ITEM_TABLE} li
            JOIN {QUESTION_TABLE} q ON q.question_id = li.question_id
            WHERE li.lesson_id = :lesson_id
            ORDER BY COALESCE(li.sort_order, q.question_id)
            """,
            {"lesson_id": int(lesson_id)},
        )
    )
    return [_normalize_question_row(row) for row in rows]


def submit_grammar_answer(
    user_id: int,
    course_id: int,
    lesson_id: int,
    question_id: int,
    selected_option: str,
    user_email: str | None = None,
    time_taken: int | None = None,
) -> Dict[str, Any]:
    question = _select_one(QUESTION_TABLE, "question_id = :question_id", {"question_id": int(question_id)})
    if not question:
        raise RuntimeError("Question not found")

    attempt_result = record_grammar_attempt(
        user_id=user_id,
        course_id=course_id,
        lesson_id=lesson_id,
        question_id=question_id,
        selected_option=selected_option,
        time_taken=time_taken,
        user_email=user_email,
    )
    return {
        "is_correct": attempt_result["is_correct"],
        "correct_option": attempt_result["correct_option"],
        "explanation": _clean_text(question.get("explanation")),
        "question_text": _clean_text(question.get("question_text")),
        "attempt": attempt_result["attempt"],
        "progress": attempt_result["progress"],
    }
