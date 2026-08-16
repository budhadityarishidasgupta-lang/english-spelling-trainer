import csv
import io

from verbal_reasoning_app.repository.vr_ingest_repo import upsert_question_and_mapping


ALIASES = {
    "level": ("level", "difficulty", "stage"),
    "paper_number": ("paper_number", "paper", "test_paper", "paper_no"),
    "question_number": ("question_number", "question_no", "q_no", "number"),
    "question_code": ("question_code", "question_id", "id", "code"),
    "question_type": ("question_type", "type", "category", "question_category"),
    "question_text": ("question_text", "question", "prompt", "stem"),
    "option_a": ("option_a", "a", "answer_a"),
    "option_b": ("option_b", "b", "answer_b"),
    "option_c": ("option_c", "c", "answer_c"),
    "option_d": ("option_d", "d", "answer_d"),
    "correct_option": ("correct_option", "correct_answer", "answer", "correct"),
    "explanation": ("explanation", "reason", "solution", "answer_explanation"),
}


def _normalized_headers(fieldnames):
    return {str(name).strip().lower(): name for name in (fieldnames or [])}


def _resolve_columns(fieldnames):
    headers = _normalized_headers(fieldnames)
    resolved = {}
    missing = []
    for canonical, aliases in ALIASES.items():
        match = next((headers[a] for a in aliases if a in headers), None)
        if match is None:
            missing.append(canonical)
        else:
            resolved[canonical] = match
    if missing:
        raise ValueError("Missing required CSV fields: " + ", ".join(missing))
    return resolved


def ingest_csv_bytes(data: bytes):
    text = data.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    columns = _resolve_columns(reader.fieldnames)
    imported = 0
    errors = []

    for row_number, row in enumerate(reader, start=2):
        try:
            values = {key: (row.get(source) or "").strip() for key, source in columns.items()}
            if not values["question_code"]:
                values["question_code"] = (
                    f"VR-{values['level']}-{values['paper_number']}-{values['question_number']}"
                )
            upsert_question_and_mapping(**values)
            imported += 1
        except Exception as exc:
            errors.append(f"Row {row_number}: {exc}")

    return {"imported": imported, "errors": errors, "headers": reader.fieldnames or []}
