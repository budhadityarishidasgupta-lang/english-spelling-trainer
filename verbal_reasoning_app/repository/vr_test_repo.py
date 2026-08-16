from psycopg2.extras import RealDictCursor

from verbal_reasoning_app.repository.vr_repository import _connection


def get_paper_questions(paper_id: int):
    sql = """
    SELECT pq.question_number,
           q.id AS question_id,
           q.question_type,
           q.question_text,
           q.option_a, q.option_b, q.option_c, q.option_d,
           q.correct_option,
           q.explanation
    FROM vr_paper_questions pq
    JOIN vr_questions q ON q.id = pq.question_id
    WHERE pq.paper_id = %s AND q.is_active = TRUE
    ORDER BY pq.question_number;
    """
    with _connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (paper_id,))
            return list(cur.fetchall())


def create_session(student_id: int, paper_id: int) -> int:
    sql = """
    INSERT INTO vr_sessions (student_id, paper_id, total_questions)
    VALUES (%s, %s, 35)
    RETURNING id;
    """
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (student_id, paper_id))
            return int(cur.fetchone()[0])


def get_session(session_id: int):
    sql = """
    SELECT s.id, s.student_id, s.paper_id, s.started_at, s.submitted_at,
           s.status, s.correct_count, s.total_questions,
           p.title, p.level, p.paper_number, p.duration_minutes
    FROM vr_sessions s
    JOIN vr_papers p ON p.id = s.paper_id
    WHERE s.id = %s;
    """
    with _connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (session_id,))
            return cur.fetchone()


def save_draft_answer(session_id: int, question_id: int, question_number: int, selected_option: str):
    sql = """
    INSERT INTO vr_session_answers (session_id, question_id, question_number, selected_option, updated_at)
    VALUES (%s, %s, %s, %s, NOW())
    ON CONFLICT (session_id, question_id)
    DO UPDATE SET selected_option = EXCLUDED.selected_option,
                  question_number = EXCLUDED.question_number,
                  updated_at = NOW();
    """
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (session_id, question_id, question_number, selected_option))


def get_draft_answers(session_id: int):
    sql = """
    SELECT question_id, question_number, selected_option
    FROM vr_session_answers
    WHERE session_id = %s
    ORDER BY question_number;
    """
    with _connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (session_id,))
            return list(cur.fetchall())


def finalize_session(session_id: int, timed_out: bool = False):
    session = get_session(session_id)
    if not session:
        raise ValueError("VR session not found")
    if session["status"] != "IN_PROGRESS":
        return

    sql_attempts = """
    INSERT INTO vr_attempts (
        session_id, student_id, paper_id, question_id, question_number,
        selected_option, correct_option, is_correct
    )
    SELECT s.id, s.student_id, s.paper_id, q.id, pq.question_number,
           a.selected_option, q.correct_option,
           COALESCE(a.selected_option = q.correct_option, FALSE)
    FROM vr_sessions s
    JOIN vr_paper_questions pq ON pq.paper_id = s.paper_id
    JOIN vr_questions q ON q.id = pq.question_id
    LEFT JOIN vr_session_answers a
      ON a.session_id = s.id AND a.question_id = q.id
    WHERE s.id = %s
    ORDER BY pq.question_number
    ON CONFLICT (session_id, question_id) DO NOTHING;
    """
    sql_finish = """
    UPDATE vr_sessions
       SET submitted_at = NOW(),
           status = %s,
           correct_count = (
               SELECT COUNT(*)::INT FROM vr_attempts
               WHERE session_id = %s AND is_correct = TRUE
           )
     WHERE id = %s AND status = 'IN_PROGRESS';
    """
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql_attempts, (session_id,))
            cur.execute(sql_finish, ("TIMED_OUT" if timed_out else "SUBMITTED", session_id, session_id))


def get_result(session_id: int):
    sql = """
    SELECT s.id AS session_id, s.started_at, s.submitted_at, s.status,
           s.correct_count, s.total_questions,
           p.title, p.level, p.paper_number,
           COUNT(a.id)::INT AS answered_rows,
           COUNT(a.id) FILTER (WHERE a.selected_option IS NOT NULL)::INT AS answered_count,
           COUNT(a.id) FILTER (WHERE a.selected_option IS NULL)::INT AS unanswered_count
    FROM vr_sessions s
    JOIN vr_papers p ON p.id = s.paper_id
    LEFT JOIN vr_attempts a ON a.session_id = s.id
    WHERE s.id = %s
    GROUP BY s.id, p.id;
    """
    with _connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (session_id,))
            return cur.fetchone()


def get_review(session_id: int):
    sql = """
    SELECT a.question_number, q.question_text,
           q.option_a, q.option_b, q.option_c, q.option_d,
           a.selected_option, a.correct_option, a.is_correct, q.explanation
    FROM vr_attempts a
    JOIN vr_questions q ON q.id = a.question_id
    WHERE a.session_id = %s
    ORDER BY a.question_number;
    """
    with _connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (session_id,))
            return list(cur.fetchall())
