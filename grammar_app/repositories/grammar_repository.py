from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional

from shared.db import execute

DEFAULT_COURSE_NAME = "GrammarSprint v1"

COURSE_TABLE = "grammar_courses"
LESSON_TABLE = "grammar_lessons"
QUESTION_TABLE = "grammar_questions"
LESSON_ITEM_TABLE = "grammar_lesson_items"
ATTEMPT_TABLE = "grammar_attempts"
QUESTION_STATS_TABLE = "grammar_question_stats"
LESSON_PROGRESS_TABLE = "grammar_lesson_progress"

QUESTION_TEXT_COLUMNS = ("question_text", "text", "prompt")
QUESTION_OPTION_COLUMNS = ("option_a", "option_b", "option_c", "option_d")
QUESTION_CORRECT_COLUMNS = ("correct_option", "answer_key", "correct_answer")
QUESTION_EXPLANATION_COLUMNS = ("explanation", "rationale")
QUESTION_DIFFICULTY_COLUMNS = ("difficulty", "level")
QUESTION_SKILL_COLUMNS = ("skill_tag", "skill", "tag")
QUESTION_SOURCE_COLUMNS = ("source_ref", "source", "reference")
LESSON_CODE_COLUMNS = ("lesson_code", "code", "slug")
LESSON_NAME_COLUMNS = ("lesson_name", "title", "name")
LESSON_ORDER_COLUMNS = ("sort_order", "order_index", "display_order")
COURSE_NAME_COLUMNS = ("course_name", "title", "name")
COURSE_ACTIVE_COLUMNS = ("is_active", "active")
EMAIL_COLUMNS = ("user_email", "email")
ATTEMPT_OPTION_COLUMNS = ("selected_option", "answer", "selected_choice")
ATTEMPT_TIME_COLUMNS = ("attempted_on", "attempted_at", "created_at")
STAT_TOTAL_COLUMNS = ("total_attempts", "attempt_count", "attempts_total")
STAT_CORRECT_COLUMNS = ("correct_attempts", "correct_count", "correct_total")
STAT_ACCURACY_COLUMNS = ("accuracy_pct", "accuracy_percent", "accuracy")
STAT_TIME_COLUMNS = ("last_attempted_at", "last_attempted_on", "updated_at")
PROGRESS_TOTAL_COLUMNS = ("total_questions", "questions_total")
PROGRESS_DONE_COLUMNS = ("completed_questions", "correct_questions", "questions_completed")
PROGRESS_PCT_COLUMNS = ("progress_pct", "progress_percent", "completion_pct")
PROGRESS_STATUS_COLUMNS = ("status", "progress_status")
PROGRESS_TIME_COLUMNS = ("last_attempted_at", "last_attempted_on", "updated_at")
PROGRESS_COMPLETED_COLUMNS = ("completed_at", "completed_on")


def _safe_execute(query: str, params: Optional[Dict[str, Any]] = None):
    result = execute(query, params or {})
    if isinstance(result, dict) and result.get("error"):
        raise RuntimeError(result["error"])
    return result


def _rows_to_dicts(rows: Iterable[Any]) -> List[Dict[str, Any]]:
    dict_rows: List[Dict[str, Any]] = []
    for row in rows or []:
        if hasattr(row, "_mapping"):
            dict_rows.append(dict(row._mapping))
        elif isinstance(row, dict):
            dict_rows.append(dict(row))
        elif isinstance(row, (list, tuple)):
            dict_rows.append({"value": row[0] if row else None})
        else:
            dict_rows.append({"value": row})
    return dict_rows


def _first_dict(rows: Iterable[Any]) -> Optional[Dict[str, Any]]:
    dict_rows = _rows_to_dicts(rows)
    return dict_rows[0] if dict_rows else None


def _normalized_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _normalized_lower(value: Any) -> str:
    return _normalized_text(value).lower()


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
    for row in rows or []:
        if hasattr(row, "_mapping"):
            cols.append(str(row._mapping["column_name"]).lower())
        elif isinstance(row, dict) and "column_name" in row:
            cols.append(str(row["column_name"]).lower())
        elif isinstance(row, (list, tuple)) and row:
            cols.append(str(row[0]).lower())
    return tuple(cols)


def _has_column(table_name: str, column_name: str) -> bool:
    return column_name.lower() in _table_columns(table_name)


def _preferred_column(table_name: str, candidates: Iterable[str]) -> Optional[str]:
    columns = set(_table_columns(table_name))
    for candidate in candidates:
        if candidate.lower() in columns:
            return candidate.lower()
    return None


def _filter_payload(table_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    columns = set(_table_columns(table_name))
    return {key: value for key, value in payload.items() if key.lower() in columns and value is not None}


def _lookup_row(table_name: str, filters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not filters:
        return None
    where_clause = " AND ".join(f"{key} = :{key}" for key in filters)
    rows = _safe_execute(
        f"SELECT * FROM {table_name} WHERE {where_clause} LIMIT 1",
        filters,
    )
    return _first_dict(rows)


def _update_row(table_name: str, key_filters: Dict[str, Any], payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    filtered = _filter_payload(table_name, payload)
    updates = {key: value for key, value in filtered.items() if key not in key_filters}
    if not updates:
        return _lookup_row(table_name, key_filters)

    set_clause = ", ".join(f"{key} = :{key}" for key in updates)
    params = {**updates, **key_filters}
    _safe_execute(
        f"UPDATE {table_name} SET {set_clause} WHERE "
        + " AND ".join(f"{key} = :{key}" for key in key_filters),
        params,
    )
    return _lookup_row(table_name, key_filters)


def _insert_row(table_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    filtered = _filter_payload(table_name, payload)
    if not filtered:
        raise RuntimeError(f"No insertable columns found for {table_name}")

    columns = list(filtered.keys())
    placeholders = ", ".join(f":{column}" for column in columns)
    column_list = ", ".join(columns)
    rows = _safe_execute(
        f"INSERT INTO {table_name} ({column_list}) VALUES ({placeholders}) RETURNING *",
        filtered,
    )
    inserted = _first_dict(rows)
    if inserted is not None:
        return inserted
    return filtered


def _upsert_row(table_name: str, key_filters: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    existing = _lookup_row(table_name, key_filters)
    if existing:
        updated = _update_row(table_name, key_filters, payload)
        return updated or existing

    full_payload = {**key_filters, **payload}
    return _insert_row(table_name, full_payload)


def get_course_by_name(course_name: str = DEFAULT_COURSE_NAME) -> Optional[Dict[str, Any]]:
    name_col = _preferred_column(COURSE_TABLE, COURSE_NAME_COLUMNS)
    if not name_col:
        return None
    rows = _safe_execute(
        f"SELECT * FROM {COURSE_TABLE} WHERE LOWER(TRIM({name_col})) = LOWER(TRIM(:course_name)) LIMIT 1",
        {"course_name": course_name},
    )
    return _first_dict(rows)


def ensure_course(course_name: str = DEFAULT_COURSE_NAME) -> Dict[str, Any]:
    existing = get_course_by_name(course_name)
    if existing:
        return existing

    name_col = _preferred_column(COURSE_TABLE, COURSE_NAME_COLUMNS)
    if not name_col:
        raise RuntimeError(f"{COURSE_TABLE} is missing a course name column")

    payload: Dict[str, Any] = {name_col: course_name}
    active_col = _preferred_column(COURSE_TABLE, COURSE_ACTIVE_COLUMNS)
    if active_col:
        payload[active_col] = True
    return _insert_row(COURSE_TABLE, payload)


def list_courses() -> List[Dict[str, Any]]:
    rows = _safe_execute(f"SELECT * FROM {COURSE_TABLE} ORDER BY 1")
    return _rows_to_dicts(rows)


def get_lessons_for_course(course_id: int) -> List[Dict[str, Any]]:
    order_col = _preferred_column(LESSON_TABLE, LESSON_ORDER_COLUMNS)
    code_col = _preferred_column(LESSON_TABLE, LESSON_CODE_COLUMNS)
    name_col = _preferred_column(LESSON_TABLE, LESSON_NAME_COLUMNS)

    order_sql = []
    if order_col:
        order_sql.append(order_col)
    if code_col and code_col not in order_sql:
        order_sql.append(code_col)
    if name_col and name_col not in order_sql:
        order_sql.append(name_col)
    if not order_sql:
        order_sql.append("1")

    rows = _safe_execute(
        f"SELECT * FROM {LESSON_TABLE} WHERE course_id = :course_id ORDER BY {', '.join(order_sql)}",
        {"course_id": int(course_id)},
    )
    return _rows_to_dicts(rows)


def get_lesson_by_code(course_id: int, lesson_code: str) -> Optional[Dict[str, Any]]:
    code_col = _preferred_column(LESSON_TABLE, LESSON_CODE_COLUMNS)
    if not code_col:
        return None
    rows = _safe_execute(
        f"SELECT * FROM {LESSON_TABLE} WHERE course_id = :course_id AND LOWER(TRIM({code_col})) = LOWER(TRIM(:lesson_code)) LIMIT 1",
        {"course_id": int(course_id), "lesson_code": lesson_code},
    )
    return _first_dict(rows)


def ensure_lesson(course_id: int, lesson_code: str, lesson_name: str, sort_order: int) -> Dict[str, Any]:
    existing = get_lesson_by_code(course_id, lesson_code)
    code_col = _preferred_column(LESSON_TABLE, LESSON_CODE_COLUMNS)
    name_col = _preferred_column(LESSON_TABLE, LESSON_NAME_COLUMNS)
    order_col = _preferred_column(LESSON_TABLE, LESSON_ORDER_COLUMNS)
    active_col = _preferred_column(LESSON_TABLE, COURSE_ACTIVE_COLUMNS)

    if not code_col or not name_col:
        raise RuntimeError(f"{LESSON_TABLE} is missing a lesson code or lesson name column")

    payload: Dict[str, Any] = {
        code_col: lesson_code,
        name_col: lesson_name,
    }
    if order_col:
        payload[order_col] = int(sort_order)
    if active_col:
        payload[active_col] = True

    if existing:
        key_filters = {"lesson_id": existing["lesson_id"]} if "lesson_id" in existing else {"course_id": course_id, code_col: lesson_code}
        updated = _update_row(LESSON_TABLE, key_filters, payload)
        return updated or existing

    payload["course_id"] = int(course_id)
    return _insert_row(LESSON_TABLE, payload)


def get_questions_for_lesson(lesson_id: int) -> List[Dict[str, Any]]:
    lesson_item_order_col = _preferred_column(LESSON_ITEM_TABLE, LESSON_ORDER_COLUMNS)
    lesson_item_id_col = _preferred_column(LESSON_ITEM_TABLE, ("lesson_item_id", "id"))
    question_order_col = _preferred_column(QUESTION_TABLE, LESSON_ORDER_COLUMNS)

    order_parts: List[str] = []
    if lesson_item_order_col:
        order_parts.append(f"li.{lesson_item_order_col}")
    if lesson_item_id_col:
        order_parts.append(f"li.{lesson_item_id_col}")
    if question_order_col:
        order_parts.append(f"q.{question_order_col}")
    if not order_parts:
        order_parts.append("q.question_id")

    rows = _safe_execute(
        f"""
        SELECT q.*
        FROM {LESSON_ITEM_TABLE} li
        JOIN {QUESTION_TABLE} q ON q.question_id = li.question_id
        WHERE li.lesson_id = :lesson_id
        ORDER BY {', '.join(order_parts)}
        """,
        {"lesson_id": int(lesson_id)},
    )
    return _rows_to_dicts(rows)


def get_lesson_item(lesson_id: int, question_id: int) -> Optional[Dict[str, Any]]:
    rows = _safe_execute(
        f"SELECT * FROM {LESSON_ITEM_TABLE} WHERE lesson_id = :lesson_id AND question_id = :question_id LIMIT 1",
        {"lesson_id": int(lesson_id), "question_id": int(question_id)},
    )
    return _first_dict(rows)


def ensure_lesson_item(lesson_id: int, question_id: int, sort_order: int) -> Dict[str, Any]:
    existing = get_lesson_item(lesson_id, question_id)
    payload: Dict[str, Any] = {"lesson_id": int(lesson_id), "question_id": int(question_id)}
    sort_col = _preferred_column(LESSON_ITEM_TABLE, LESSON_ORDER_COLUMNS)
    if sort_col:
        payload[sort_col] = int(sort_order)
    if existing:
        key_filters = {"lesson_id": int(lesson_id), "question_id": int(question_id)}
        updated = _update_row(LESSON_ITEM_TABLE, key_filters, payload)
        return updated or existing
    return _insert_row(LESSON_ITEM_TABLE, payload)


def _question_lookup_filters(question_data: Dict[str, Any]) -> Dict[str, Any]:
    filters: Dict[str, Any] = {}
    source_col = _preferred_column(QUESTION_TABLE, QUESTION_SOURCE_COLUMNS)
    if source_col and _normalized_text(question_data.get(source_col)):
        filters[source_col] = _normalized_text(question_data.get(source_col))
        return filters

    text_col = _preferred_column(QUESTION_TABLE, QUESTION_TEXT_COLUMNS)
    correct_col = _preferred_column(QUESTION_TABLE, QUESTION_CORRECT_COLUMNS)
    if text_col:
        filters[text_col] = _normalized_text(question_data.get(text_col))
    if correct_col:
        filters[correct_col] = _normalized_text(question_data.get(correct_col))
    for option_col in QUESTION_OPTION_COLUMNS:
        if _has_column(QUESTION_TABLE, option_col) and _normalized_text(question_data.get(option_col)):
            filters[option_col] = _normalized_text(question_data.get(option_col))
    return filters


def get_question_by_signature(question_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    filters = _question_lookup_filters(question_data)
    if not filters:
        return None

    where_parts = []
    params: Dict[str, Any] = {}
    for column, value in filters.items():
        if column in QUESTION_SOURCE_COLUMNS or column in QUESTION_OPTION_COLUMNS or column in QUESTION_TEXT_COLUMNS or column in QUESTION_EXPLANATION_COLUMNS or column in QUESTION_DIFFICULTY_COLUMNS or column in QUESTION_SKILL_COLUMNS:
            where_parts.append(f"LOWER(TRIM(COALESCE({column}, ''))) = LOWER(TRIM(:{column}))")
        else:
            where_parts.append(f"{column} = :{column}")
        params[column] = value

    rows = _safe_execute(
        f"SELECT * FROM {QUESTION_TABLE} WHERE {' AND '.join(where_parts)} LIMIT 1",
        params,
    )
    return _first_dict(rows)


def get_question_by_id(question_id: int) -> Optional[Dict[str, Any]]:
    rows = _safe_execute(
        f"SELECT * FROM {QUESTION_TABLE} WHERE question_id = :question_id LIMIT 1",
        {"question_id": int(question_id)},
    )
    return _first_dict(rows)


def ensure_question(question_data: Dict[str, Any]) -> Dict[str, Any]:
    existing = get_question_by_signature(question_data)
    text_col = _preferred_column(QUESTION_TABLE, QUESTION_TEXT_COLUMNS)
    correct_col = _preferred_column(QUESTION_TABLE, QUESTION_CORRECT_COLUMNS)
    if not text_col or not correct_col:
        raise RuntimeError(f"{QUESTION_TABLE} is missing question text or correct answer columns")

    payload: Dict[str, Any] = {text_col: question_data.get(text_col, question_data.get("question_text", "")), correct_col: question_data.get(correct_col, question_data.get("correct_option", ""))}
    for column in QUESTION_OPTION_COLUMNS:
        if _has_column(QUESTION_TABLE, column):
            payload[column] = question_data.get(column)
    for column in QUESTION_EXPLANATION_COLUMNS:
        if _has_column(QUESTION_TABLE, column):
            payload[column] = question_data.get(column)
    for column in QUESTION_DIFFICULTY_COLUMNS:
        if _has_column(QUESTION_TABLE, column):
            payload[column] = question_data.get(column)
    for column in QUESTION_SKILL_COLUMNS:
        if _has_column(QUESTION_TABLE, column):
            payload[column] = question_data.get(column)
    for column in QUESTION_SOURCE_COLUMNS:
        if _has_column(QUESTION_TABLE, column):
            payload[column] = question_data.get(column)

    if existing:
        key_filters = {"question_id": existing["question_id"]} if "question_id" in existing else _question_lookup_filters(question_data)
        updated = _update_row(QUESTION_TABLE, key_filters, payload)
        return updated or existing

    return _insert_row(QUESTION_TABLE, payload)


def record_attempt(
    user_email: str,
    lesson_id: int,
    question_id: int,
    selected_option: str,
    selected_text: Optional[str],
    is_correct: bool,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "user_email": user_email,
        "email": user_email,
        "lesson_id": int(lesson_id),
        "question_id": int(question_id),
        "selected_option": selected_option,
        "answer": selected_option,
        "selected_choice": selected_option,
        "selected_text": selected_text,
        "is_correct": bool(is_correct),
        "attempted_on": None,
        "attempted_at": None,
        "created_at": None,
    }
    time_col = _preferred_column(ATTEMPT_TABLE, ATTEMPT_TIME_COLUMNS)
    if time_col:
        payload[time_col] = None
    return _insert_row(ATTEMPT_TABLE, payload)


def get_question_stats(question_id: int) -> Optional[Dict[str, Any]]:
    rows = _safe_execute(
        f"SELECT * FROM {QUESTION_STATS_TABLE} WHERE question_id = :question_id LIMIT 1",
        {"question_id": int(question_id)},
    )
    return _first_dict(rows)


def refresh_question_stats(question_id: int) -> Dict[str, Any]:
    attempt_time_col = _preferred_column(ATTEMPT_TABLE, ATTEMPT_TIME_COLUMNS)
    select_parts = [
        "COUNT(*) AS total_attempts",
        "COALESCE(SUM(CASE WHEN is_correct THEN 1 ELSE 0 END), 0) AS correct_attempts",
    ]
    if attempt_time_col:
        select_parts.append(f"MAX({attempt_time_col}) AS last_attempted_at")
    rows = _safe_execute(
        f"SELECT {', '.join(select_parts)} FROM {ATTEMPT_TABLE} WHERE question_id = :question_id",
        {"question_id": int(question_id)},
    )
    stats = _first_dict(rows) or {"total_attempts": 0, "correct_attempts": 0}
    total_attempts = int(stats.get("total_attempts") or 0)
    correct_attempts = int(stats.get("correct_attempts") or 0)
    accuracy = round((correct_attempts / total_attempts) * 100, 2) if total_attempts else 0.0

    payload: Dict[str, Any] = {
        "question_id": int(question_id),
        "total_attempts": total_attempts,
        "attempt_count": total_attempts,
        "attempts_total": total_attempts,
        "correct_attempts": correct_attempts,
        "correct_count": correct_attempts,
        "correct_total": correct_attempts,
        "accuracy_pct": accuracy,
        "accuracy_percent": accuracy,
        "accuracy": accuracy,
        "last_attempted_at": stats.get("last_attempted_at"),
        "last_attempted_on": stats.get("last_attempted_at"),
        "updated_at": stats.get("last_attempted_at"),
    }
    existing = get_question_stats(question_id)
    if existing:
        updated = _update_row(QUESTION_STATS_TABLE, {"question_id": int(question_id)}, payload)
        return updated or existing
    return _insert_row(QUESTION_STATS_TABLE, payload)


def get_lesson_progress(user_email: str, lesson_id: int) -> Optional[Dict[str, Any]]:
    email_col = _preferred_column(LESSON_PROGRESS_TABLE, EMAIL_COLUMNS)
    if not email_col:
        return None
    rows = _safe_execute(
        f"SELECT * FROM {LESSON_PROGRESS_TABLE} WHERE LOWER(TRIM({email_col})) = LOWER(TRIM(:user_email)) AND lesson_id = :lesson_id LIMIT 1",
        {"user_email": user_email, "lesson_id": int(lesson_id)},
    )
    return _first_dict(rows)


def refresh_lesson_progress(user_email: str, lesson_id: int) -> Dict[str, Any]:
    progress_email_col = _preferred_column(LESSON_PROGRESS_TABLE, EMAIL_COLUMNS)
    if not progress_email_col:
        raise RuntimeError(f"{LESSON_PROGRESS_TABLE} is missing a user email column")

    time_col = _preferred_column(ATTEMPT_TABLE, ATTEMPT_TIME_COLUMNS)
    attempts_where = ["lesson_id = :lesson_id"]
    params: Dict[str, Any] = {"lesson_id": int(lesson_id), "user_email": user_email}
    email_attempt_col = _preferred_column(ATTEMPT_TABLE, EMAIL_COLUMNS)
    if email_attempt_col:
        attempts_where.append(f"LOWER(TRIM({email_attempt_col})) = LOWER(TRIM(:user_email))")
    completed_time_sql = f"MAX({time_col}) AS last_attempted_at" if time_col else "NULL AS last_attempted_at"

    total_questions_rows = _safe_execute(
        f"SELECT COUNT(*) AS total_questions FROM {LESSON_ITEM_TABLE} WHERE lesson_id = :lesson_id",
        {"lesson_id": int(lesson_id)},
    )
    total_questions = int((_first_dict(total_questions_rows) or {}).get("total_questions") or 0)

    completed_rows = _safe_execute(
        f"""
        SELECT
            COUNT(DISTINCT question_id) AS completed_questions,
            {completed_time_sql}
        FROM {ATTEMPT_TABLE}
        WHERE {' AND '.join(attempts_where)} AND is_correct = TRUE
        """,
        params,
    )
    completed_data = _first_dict(completed_rows) or {}
    completed_questions = int(completed_data.get("completed_questions") or 0)
    progress_pct = round((completed_questions / total_questions) * 100, 2) if total_questions else 0.0
    is_complete = total_questions > 0 and completed_questions >= total_questions

    existing = get_lesson_progress(user_email, lesson_id)
    completed_at = existing.get("completed_at") if existing else None
    if is_complete and not completed_at:
        completed_at = completed_data.get("last_attempted_at")

    payload: Dict[str, Any] = {
        progress_email_col: user_email,
        "email": user_email,
        "lesson_id": int(lesson_id),
        "total_questions": total_questions,
        "questions_total": total_questions,
        "completed_questions": completed_questions,
        "correct_questions": completed_questions,
        "questions_completed": completed_questions,
        "progress_pct": progress_pct,
        "progress_percent": progress_pct,
        "completion_pct": progress_pct,
        "status": "completed" if is_complete else "in_progress",
        "progress_status": "completed" if is_complete else "in_progress",
        "last_attempted_at": completed_data.get("last_attempted_at"),
        "last_attempted_on": completed_data.get("last_attempted_at"),
        "updated_at": completed_data.get("last_attempted_at"),
        "completed_at": completed_at,
        "completed_on": completed_at,
    }
    if existing:
        updated = _update_row(LESSON_PROGRESS_TABLE, {progress_email_col: user_email, "lesson_id": int(lesson_id)}, payload)
        return updated or existing
    return _insert_row(LESSON_PROGRESS_TABLE, payload)


def get_course_lessons_with_progress(user_email: str, course_id: int) -> List[Dict[str, Any]]:
    lessons = get_lessons_for_course(course_id)
    results: List[Dict[str, Any]] = []
    for lesson in lessons:
        lesson_id = int(lesson.get("lesson_id"))
        progress = get_lesson_progress(user_email, lesson_id) or {}
        total_questions = int(progress.get("total_questions") or 0)
        completed_questions = int(progress.get("completed_questions") or 0)
        if not total_questions:
            total_questions = len(get_questions_for_lesson(lesson_id))
        progress_pct = progress.get("progress_pct")
        if progress_pct is None:
            progress_pct = round((completed_questions / total_questions) * 100, 2) if total_questions else 0.0
        results.append(
            {
                **lesson,
                "total_questions": total_questions,
                "completed_questions": completed_questions,
                "progress_pct": progress_pct,
                "is_complete": bool(progress.get("status") == "completed" or progress.get("progress_status") == "completed"),
                "progress_row": progress,
            }
        )
    return results


def get_next_incomplete_lesson(user_email: str, course_id: int) -> Optional[Dict[str, Any]]:
    lessons = get_course_lessons_with_progress(user_email, course_id)
    for lesson in lessons:
        if not lesson.get("is_complete"):
            return lesson
    return None
