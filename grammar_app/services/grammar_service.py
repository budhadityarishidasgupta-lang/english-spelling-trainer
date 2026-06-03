from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from grammar_app.repositories.grammar_repository import (
    DEFAULT_COURSE_NAME,
    ensure_course,
    ensure_lesson,
    ensure_lesson_item,
    ensure_question,
    get_course_by_name,
    get_course_lessons_with_progress,
    get_lesson_by_code,
    get_lesson_item,
    get_lesson_progress,
    get_lesson_by_code,
    get_next_incomplete_lesson,
    get_question_by_id,
    get_question_by_signature,
    get_questions_for_lesson,
    record_attempt,
    refresh_lesson_progress,
    refresh_question_stats,
)

REQUIRED_CSV_COLUMNS = {
    "course_name",
    "lesson_code",
    "lesson_name",
    "sort_order",
    "question_type",
    "question_text",
    "option_a",
    "option_b",
    "option_c",
    "option_d",
    "correct_option",
    "explanation",
    "difficulty",
    "skill_tag",
    "source_ref",
}

OPTION_LABELS = ("A", "B", "C", "D")
OPTION_KEYS = ("option_a", "option_b", "option_c", "option_d")


def _normalized_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _normalized_lower(value: Any) -> str:
    return _normalized_text(value).lower()


def _sort_order(value: Any) -> int:
    try:
        if pd.isna(value):
            return 0
    except Exception:
        pass
    try:
        return int(float(value))
    except Exception:
        return 0


def _clean_frame(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned.columns = [str(column).strip().lower() for column in cleaned.columns]
    for column in cleaned.columns:
        cleaned[column] = cleaned[column].astype(str).replace({"nan": ""}).str.strip()
    return cleaned


def _question_options(question: Dict[str, Any]) -> Dict[str, str]:
    options: Dict[str, str] = {}
    for key, label in zip(OPTION_KEYS, OPTION_LABELS):
        value = _normalized_text(question.get(key))
        if value:
            options[label] = value
    return options


def _resolve_correct_answer(question: Dict[str, Any]) -> Dict[str, str]:
    correct_raw = _normalized_text(question.get("correct_option"))
    options = _question_options(question)
    correct_label = ""
    correct_text = correct_raw

    if correct_raw.upper() in options:
        correct_label = correct_raw.upper()
        correct_text = options[correct_label]
    else:
        for label, text in options.items():
            if _normalized_lower(text) == _normalized_lower(correct_raw):
                correct_label = label
                correct_text = text
                break

    return {
        "label": correct_label,
        "text": correct_text,
    }


def process_grammar_csv_upload(df: pd.DataFrame, default_course_name: str = DEFAULT_COURSE_NAME) -> Dict[str, Any]:
    cleaned = _clean_frame(df)
    missing = sorted(REQUIRED_CSV_COLUMNS - set(cleaned.columns))
    if missing:
        return {"error": f"CSV must contain columns: {', '.join(missing)}"}

    summary = {
        "rows_seen": int(len(cleaned)),
        "rows_imported": 0,
        "rows_skipped": 0,
        "courses_created": 0,
        "lessons_created": 0,
        "questions_created": 0,
        "lesson_links_created": 0,
        "existing_courses": 0,
        "existing_lessons": 0,
        "existing_questions": 0,
        "existing_links": 0,
    }
    details: List[Dict[str, Any]] = []

    for _, row in cleaned.iterrows():
        course_name = _normalized_text(row.get("course_name")) or default_course_name
        lesson_code = _normalized_text(row.get("lesson_code"))
        lesson_name = _normalized_text(row.get("lesson_name"))
        question_text = _normalized_text(row.get("question_text"))
        question_type = _normalized_text(row.get("question_type")) or "mcq"
        correct_option = _normalized_text(row.get("correct_option"))

        if not lesson_code or not lesson_name or not question_text or not correct_option:
            summary["rows_skipped"] += 1
            details.append(
                {
                    "course_name": course_name,
                    "lesson_code": lesson_code,
                    "question_text": question_text,
                    "status": "skipped",
                    "reason": "Missing a required lesson or question field",
                }
            )
            continue

        course_before = get_course_by_name(course_name)
        course_row = ensure_course(course_name)
        if course_before:
            summary["existing_courses"] += 1
        else:
            summary["courses_created"] += 1

        lesson_before = get_lesson_by_code(int(course_row["course_id"]), lesson_code)
        lesson_row = ensure_lesson(
            int(course_row["course_id"]),
            lesson_code,
            lesson_name,
            _sort_order(row.get("sort_order")),
        )
        if lesson_before:
            summary["existing_lessons"] += 1
        else:
            summary["lessons_created"] += 1

        question_payload = {
            "question_type": question_type,
            "question_text": question_text,
            "option_a": _normalized_text(row.get("option_a")),
            "option_b": _normalized_text(row.get("option_b")),
            "option_c": _normalized_text(row.get("option_c")),
            "option_d": _normalized_text(row.get("option_d")),
            "correct_option": correct_option,
            "explanation": _normalized_text(row.get("explanation")),
            "difficulty": _normalized_text(row.get("difficulty")),
            "skill_tag": _normalized_text(row.get("skill_tag")),
            "source_ref": _normalized_text(row.get("source_ref")),
        }
        question_before = get_question_by_signature(question_payload)
        question_row = ensure_question(question_payload)
        if question_before:
            summary["existing_questions"] += 1
        else:
            summary["questions_created"] += 1

        link_before = get_lesson_item(int(lesson_row["lesson_id"]), int(question_row["question_id"]))
        ensure_lesson_item(int(lesson_row["lesson_id"]), int(question_row["question_id"]), _sort_order(row.get("sort_order")))
        if link_before:
            summary["existing_links"] += 1
        else:
            summary["lesson_links_created"] += 1

        summary["rows_imported"] += 1
        details.append(
            {
                "course_name": course_name,
                "lesson_code": lesson_code,
                "lesson_name": lesson_name,
                "question_text": question_text,
                "question_id": question_row.get("question_id"),
                "lesson_id": lesson_row.get("lesson_id"),
                "status": "imported",
                "lesson_status": "existing" if lesson_before else "created",
                "question_status": "existing" if question_before else "created",
                "mapping_status": "existing" if link_before else "created",
            }
        )

    message = f"Imported {summary['rows_imported']} grammar rows into {default_course_name}."
    if summary["rows_skipped"]:
        message += f" Skipped {summary['rows_skipped']} invalid row(s)."
    return {"message": message, "summary": summary, "details": details}


def get_student_grammar_overview(user_email: str, course_name: str = DEFAULT_COURSE_NAME) -> Dict[str, Any]:
    course = ensure_course(course_name)
    lessons = get_course_lessons_with_progress(user_email, int(course["course_id"]))
    next_lesson = get_next_incomplete_lesson(user_email, int(course["course_id"]))
    return {
        "course": course,
        "lessons": lessons,
        "next_lesson": next_lesson,
    }


def get_grammar_lesson_questions(lesson_id: int) -> List[Dict[str, Any]]:
    questions = get_questions_for_lesson(int(lesson_id))
    normalized: List[Dict[str, Any]] = []
    for row in questions:
        question = dict(row)
        question["options"] = _question_options(question)
        correct = _resolve_correct_answer(question)
        question["correct_label"] = correct["label"]
        question["correct_text"] = correct["text"]
        normalized.append(question)
    return normalized


def submit_grammar_answer(
    user_email: str,
    lesson_id: int,
    question_id: int,
    selected_option: str,
    selected_text: Optional[str] = None,
) -> Dict[str, Any]:
    question = get_question_by_id(int(question_id))
    if not question:
        raise RuntimeError("Question not found")

    correct = _resolve_correct_answer(question)
    selected_label = _normalized_text(selected_option).upper()
    selected_text_value = _normalized_text(selected_text)

    is_correct = False
    if correct["label"]:
        is_correct = selected_label == correct["label"].upper()
    else:
        is_correct = _normalized_lower(selected_text_value or selected_label) == _normalized_lower(correct["text"])

    attempt_row = record_attempt(
        user_email=user_email,
        lesson_id=int(lesson_id),
        question_id=int(question_id),
        selected_option=selected_label or selected_text_value,
        selected_text=selected_text_value or None,
        is_correct=is_correct,
    )
    refresh_question_stats(int(question_id))
    progress_row = refresh_lesson_progress(user_email, int(lesson_id))

    return {
        "attempt": attempt_row,
        "progress": progress_row,
        "question_id": int(question_id),
        "question_text": _normalized_text(question.get("question_text")),
        "selected_option": selected_label,
        "selected_text": selected_text_value,
        "is_correct": is_correct,
        "correct_label": correct["label"],
        "correct_text": correct["text"],
        "explanation": _normalized_text(question.get("explanation")),
    }
