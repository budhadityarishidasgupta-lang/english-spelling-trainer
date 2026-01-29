import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    """
    Create and return a new DB connection using DATABASE_URL.
    """
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set")

    return psycopg2.connect(database_url)


def init_math_tables():
    """
    SAFE / ADDITIVE ONLY
    Creates maths tables used by the Streamlit apps.
    """
    ddl = [
        """
        CREATE TABLE IF NOT EXISTS math_questions (
            id SERIAL PRIMARY KEY,
            question_id VARCHAR(128) UNIQUE NOT NULL,
            stem TEXT NOT NULL,
            option_a TEXT,
            option_b TEXT,
            option_c TEXT,
            option_d TEXT,
            option_e TEXT,
            correct_option CHAR(1) NOT NULL,
            topic VARCHAR(128),
            difficulty VARCHAR(32),
            asset_type VARCHAR(64),
            asset_ref TEXT,
            hint TEXT,
            solution TEXT,
            explanation TEXT,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS math_sessions (
            id SERIAL PRIMARY KEY,
            started_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            ended_at TIMESTAMP WITHOUT TIME ZONE,
            total_questions INTEGER,
            correct_count INTEGER
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS math_attempts (
            id SERIAL PRIMARY KEY,
            session_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            selected_option CHAR(1) NOT NULL,
            is_correct BOOLEAN NOT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_math_questions_topic
            ON math_questions(topic);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_math_questions_difficulty
            ON math_questions(difficulty);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_math_attempts_session
            ON math_attempts(session_id);
        """,
    ]

    alterations = [
        "ALTER TABLE math_questions ADD COLUMN IF NOT EXISTS hint TEXT;",
        "ALTER TABLE math_questions ADD COLUMN IF NOT EXISTS solution TEXT;",
        "ALTER TABLE math_questions ADD COLUMN IF NOT EXISTS explanation TEXT;",
        "ALTER TABLE math_questions ADD COLUMN IF NOT EXISTS asset_type VARCHAR(64);",
        "ALTER TABLE math_questions ADD COLUMN IF NOT EXISTS asset_ref TEXT;",
        "ALTER TABLE math_questions ADD COLUMN IF NOT EXISTS topic VARCHAR(128);",
        "ALTER TABLE math_questions ADD COLUMN IF NOT EXISTS difficulty VARCHAR(32);",
        "ALTER TABLE math_questions ADD COLUMN IF NOT EXISTS option_e TEXT;",
    ]

    conn = None
    try:
        conn = get_db_connection()
        conn.autocommit = True
        with conn.cursor() as cur:
            for stmt in ddl:
                cur.execute(stmt)
            for stmt in alterations:
                cur.execute(stmt)
    finally:
        if conn:
            conn.close()


def init_math_practice_progress_table():
    from math_app.db import get_db_connection

    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS math_practice_progress (
                id SERIAL PRIMARY KEY,
                student_id INTEGER NOT NULL,
                lesson_id INTEGER NOT NULL,
                question_index INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.commit()

    init_math_practice_attempts_table()


def init_math_practice_attempts_table():
    from math_app.db import get_db_connection

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS math_practice_attempts (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER NOT NULL,
                    lesson_id INTEGER NOT NULL,
                    question_id INTEGER NOT NULL,
                    selected_option CHAR(1) NOT NULL,
                    is_correct BOOLEAN NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.commit()
    finally:
        if conn:
            conn.close()
