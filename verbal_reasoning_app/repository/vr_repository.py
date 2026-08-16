import os
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor


LEVELS = ("BASIC", "INTERMEDIATE", "MASTERY")


@contextmanager
def _connection():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL not set")
    conn = psycopg2.connect(database_url)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_vr_tables() -> None:
    """Create only Verbal Reasoning domain tables, idempotently."""
    ddl = """
    CREATE TABLE IF NOT EXISTS vr_papers (
        id BIGSERIAL PRIMARY KEY,
        level TEXT NOT NULL CHECK (level IN ('BASIC', 'INTERMEDIATE', 'MASTERY')),
        paper_number INT NOT NULL CHECK (paper_number BETWEEN 1 AND 15),
        title TEXT NOT NULL,
        duration_minutes INT NOT NULL DEFAULT 30 CHECK (duration_minutes > 0),
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (level, paper_number)
    );

    CREATE TABLE IF NOT EXISTS vr_questions (
        id BIGSERIAL PRIMARY KEY,
        question_code TEXT NOT NULL UNIQUE,
        question_type TEXT NOT NULL,
        question_text TEXT NOT NULL,
        option_a TEXT NOT NULL,
        option_b TEXT NOT NULL,
        option_c TEXT NOT NULL,
        option_d TEXT NOT NULL,
        correct_option TEXT NOT NULL CHECK (correct_option IN ('A', 'B', 'C', 'D')),
        explanation TEXT NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS vr_paper_questions (
        paper_id BIGINT NOT NULL REFERENCES vr_papers(id),
        question_id BIGINT NOT NULL REFERENCES vr_questions(id),
        question_number INT NOT NULL CHECK (question_number BETWEEN 1 AND 35),
        PRIMARY KEY (paper_id, question_number),
        UNIQUE (paper_id, question_id)
    );

    CREATE TABLE IF NOT EXISTS vr_sessions (
        id BIGSERIAL PRIMARY KEY,
        student_id BIGINT NOT NULL,
        paper_id BIGINT NOT NULL REFERENCES vr_papers(id),
        started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        submitted_at TIMESTAMPTZ NULL,
        status TEXT NOT NULL DEFAULT 'IN_PROGRESS'
            CHECK (status IN ('IN_PROGRESS', 'SUBMITTED', 'TIMED_OUT')),
        correct_count INT NULL,
        total_questions INT NOT NULL DEFAULT 35
    );

    CREATE TABLE IF NOT EXISTS vr_session_answers (
        session_id BIGINT NOT NULL REFERENCES vr_sessions(id),
        question_id BIGINT NOT NULL REFERENCES vr_questions(id),
        question_number INT NOT NULL CHECK (question_number BETWEEN 1 AND 35),
        selected_option TEXT NOT NULL CHECK (selected_option IN ('A', 'B', 'C', 'D')),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (session_id, question_id)
    );

    CREATE TABLE IF NOT EXISTS vr_attempts (
        id BIGSERIAL PRIMARY KEY,
        session_id BIGINT NOT NULL REFERENCES vr_sessions(id),
        student_id BIGINT NOT NULL,
        paper_id BIGINT NOT NULL REFERENCES vr_papers(id),
        question_id BIGINT NOT NULL REFERENCES vr_questions(id),
        question_number INT NOT NULL,
        selected_option TEXT NULL CHECK (selected_option IS NULL OR selected_option IN ('A', 'B', 'C', 'D')),
        correct_option TEXT NOT NULL CHECK (correct_option IN ('A', 'B', 'C', 'D')),
        is_correct BOOLEAN NOT NULL,
        response_ms INT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (session_id, question_id)
    );

    CREATE INDEX IF NOT EXISTS idx_vr_papers_level
        ON vr_papers (level, paper_number);
    CREATE INDEX IF NOT EXISTS idx_vr_sessions_student
        ON vr_sessions (student_id, started_at DESC);
    CREATE INDEX IF NOT EXISTS idx_vr_session_answers_session
        ON vr_session_answers (session_id, question_number);
    CREATE INDEX IF NOT EXISTS idx_vr_attempts_student
        ON vr_attempts (student_id, created_at DESC);
    """
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)


def ensure_paper_catalog() -> None:
    """Idempotently create the 45 fixed paper shells; never deletes content."""
    sql = """
    INSERT INTO vr_papers (level, paper_number, title, duration_minutes)
    VALUES (%s, %s, %s, 30)
    ON CONFLICT (level, paper_number) DO NOTHING;
    """
    with _connection() as conn:
        with conn.cursor() as cur:
            for level in LEVELS:
                for paper_number in range(1, 16):
                    title = f"{level.title()} Paper {paper_number}"
                    cur.execute(sql, (level, paper_number, title))


def list_active_papers(level: str):
    normalized = level.upper()
    if normalized not in LEVELS:
        raise ValueError("Invalid Verbal Reasoning level")
    sql = """
    SELECT p.id, p.level, p.paper_number, p.title, p.duration_minutes,
           COUNT(pq.question_id)::INT AS question_count
    FROM vr_papers p
    LEFT JOIN vr_paper_questions pq ON pq.paper_id = p.id
    WHERE p.level = %s AND p.is_active = TRUE
    GROUP BY p.id
    ORDER BY p.paper_number;
    """
    with _connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (normalized,))
            return list(cur.fetchall())


def get_paper(paper_id: int):
    sql = """
    SELECT id, level, paper_number, title, duration_minutes
    FROM vr_papers
    WHERE id = %s AND is_active = TRUE;
    """
    with _connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (paper_id,))
            return cur.fetchone()
