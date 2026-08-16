from verbal_reasoning_app.repository.vr_repository import LEVELS, _connection


def upsert_question_and_mapping(*, level, paper_number, question_number, question_code,
                                question_type, question_text, option_a, option_b,
                                option_c, option_d, correct_option, explanation):
    level = level.upper().strip()
    correct_option = correct_option.upper().strip()
    if level not in LEVELS:
        raise ValueError(f"Invalid level: {level}")
    if not 1 <= int(paper_number) <= 15:
        raise ValueError("paper_number must be 1..15")
    if not 1 <= int(question_number) <= 35:
        raise ValueError("question_number must be 1..35")
    if correct_option not in ("A", "B", "C", "D"):
        raise ValueError("correct_option must be A, B, C or D")

    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM vr_papers WHERE level=%s AND paper_number=%s",
                (level, int(paper_number)),
            )
            paper = cur.fetchone()
            if not paper:
                raise ValueError(f"Paper not found: {level} {paper_number}")
            paper_id = paper[0]

            cur.execute(
                """
                INSERT INTO vr_questions (
                    question_code, question_type, question_text,
                    option_a, option_b, option_c, option_d,
                    correct_option, explanation
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (question_code) DO UPDATE SET
                    question_type = EXCLUDED.question_type,
                    question_text = EXCLUDED.question_text,
                    option_a = EXCLUDED.option_a,
                    option_b = EXCLUDED.option_b,
                    option_c = EXCLUDED.option_c,
                    option_d = EXCLUDED.option_d,
                    correct_option = EXCLUDED.correct_option,
                    explanation = EXCLUDED.explanation,
                    is_active = TRUE
                RETURNING id;
                """,
                (question_code, question_type, question_text,
                 option_a, option_b, option_c, option_d,
                 correct_option, explanation),
            )
            question_id = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO vr_paper_questions (paper_id, question_id, question_number)
                VALUES (%s,%s,%s)
                ON CONFLICT (paper_id, question_number) DO UPDATE SET
                    question_id = EXCLUDED.question_id;
                """,
                (paper_id, question_id, int(question_number)),
            )
