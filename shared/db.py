import os
from collections.abc import Mapping
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from dotenv import load_dotenv
import pathlib

##################################################################
# SAFE ROW NORMALIZATION LAYER — fixes tuple/Row/dict inconsistencies
##################################################################

def safe_row(row):
    """
    Normalize any row returned by SQLAlchemy/psycopg2:
    - Row → dict(row._mapping)
    - dict → dict
    - tuple → positional → dict with numeric keys
    """
    # SQLAlchemy row
    if hasattr(row, "_mapping"):
        return dict(row._mapping)

    # Already a mapping
    if isinstance(row, Mapping):
        return dict(row)

    # Tuple fallback → map to numeric field names until caller renames keys
    if isinstance(row, tuple):
        return {f"col_{i}": row[i] for i in range(len(row))}

    return {}


def safe_rows(rows):
    """Convert list of rows to list of dict rows safely."""
    if not rows:
        return []
    if isinstance(rows, dict):
        return []
    return [safe_row(r) for r in rows]

# Force-load the .env from repo root
ENV_PATH = pathlib.Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_PATH)
print("Loaded .env from:", ENV_PATH)



# Load database URL from environment variable
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable not set.")

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    isolation_level="AUTOCOMMIT",
)


# --------------------------------------------------------------------
# Ensure required spelling tables exist
# --------------------------------------------------------------------
def ensure_spelling_help_texts_table(engine):
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS spelling_help_texts (
                    id SERIAL PRIMARY KEY,
                    help_key TEXT UNIQUE NOT NULL,
                    title TEXT,
                    body TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
        )


def ensure_spelling_content_blocks_table(engine):
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS spelling_content_blocks (
                    id SERIAL PRIMARY KEY,
                    block_key TEXT UNIQUE NOT NULL,
                    title TEXT,
                    body TEXT,
                    media_data TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
        )


def ensure_spelling_payments_table(engine):
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS spelling_payments (
                    id SERIAL PRIMARY KEY,
                    user_email TEXT NOT NULL,
                    paypal_payment_id TEXT UNIQUE NOT NULL,
                    paypal_button_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    paid_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
        )


def init_spelling_tables():
    ensure_spelling_help_texts_table(engine)
    ensure_spelling_content_blocks_table(engine)
    ensure_spelling_payments_table(engine)

    # ------------------------------------------------------------
    # HINTS: Safe content ops layer (does NOT affect student app)
    # ------------------------------------------------------------
    with engine.begin() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS spelling_hint_ai_draft (
            draft_id     SERIAL PRIMARY KEY,
            word_id      INT NOT NULL,
            course_id    INT NULL,
            hint_text    TEXT NOT NULL,
            hint_style   TEXT NOT NULL DEFAULT 'meaning_plus_spelling',
            model        TEXT NULL,
            created_by   TEXT NOT NULL DEFAULT 'csv',
            status       TEXT NOT NULL DEFAULT 'draft',  -- draft | approved | rejected
            created_at   TIMESTAMP NOT NULL DEFAULT now(),
            UNIQUE (word_id, course_id, hint_style)
        );
        """))

    with engine.begin() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS spelling_hint_overrides (
            word_id     INT NOT NULL,
            course_id   INT NULL,
            hint_text   TEXT NOT NULL,
            source      TEXT NOT NULL DEFAULT 'manual',
            updated_at  TIMESTAMP NOT NULL DEFAULT now(),
            PRIMARY KEY (word_id, course_id)
        );
        """))

    with engine.begin() as conn:
        conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_hint_ai_draft_status
          ON spelling_hint_ai_draft(status);
        """))

    with engine.begin() as conn:
        conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_hint_ai_draft_word_course
          ON spelling_hint_ai_draft(word_id, course_id);
        """))


def init_math_tables():
    """
    Initialise Maths app tables.
    Additive only. Safe for repeated runs.
    """
    with engine.begin() as conn:

        # --------------------------------------------
        # Maths Courses
        # --------------------------------------------
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS math_courses (
                course_id SERIAL PRIMARY KEY,
                course_name TEXT NOT NULL,
                is_active BOOLEAN DEFAULT TRUE
            );
        """))

        # --------------------------------------------
        # Maths Lessons (Practice sets)
        # --------------------------------------------
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS math_lessons (
                lesson_id SERIAL PRIMARY KEY,
                course_id INT NOT NULL,
                lesson_name TEXT NOT NULL,      -- canonical, DO NOT EDIT
                display_name TEXT NOT NULL,     -- UI-safe label
                difficulty INT,
                is_active BOOLEAN DEFAULT TRUE
            );
        """))

        # --------------------------------------------
        # Maths Questions (Practice only)
        # --------------------------------------------
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS math_questions (
                question_id SERIAL PRIMARY KEY,
                external_question_code TEXT UNIQUE NOT NULL,
                course_id INT NOT NULL,
                lesson_id INT NOT NULL,
                topic TEXT,
                difficulty TEXT,
                question_type TEXT DEFAULT 'mcq',
                question_text TEXT NOT NULL,
                options JSONB NOT NULL,
                correct_option TEXT NOT NULL,   -- A / B / C / D
                explanation TEXT
            );
        """))

        # --------------------------------------------
        # Maths Attempts (Append-only)
        # --------------------------------------------
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS math_attempts (
                attempt_id SERIAL PRIMARY KEY,
                user_id INT NOT NULL,
                lesson_id INT NOT NULL,
                question_id INT NOT NULL,
                is_correct BOOLEAN NOT NULL,
                answer TEXT NOT NULL,
                time_taken INT,
                attempted_on TIMESTAMP DEFAULT now()
            );
        """))


# Call from your global init hook if present
# init_math_tables()



# --------------------------------------------------------------------
# fetch_all() — Always return list of rows (for SELECT queries)
# --------------------------------------------------------------------
def fetch_all(sql, params=None):
    with engine.connect() as connection:
        try:
            result = connection.execute(text(sql), params or {})
            try:
                return result.fetchall()
            except Exception:
                try:
                    return result.all()
                except Exception:
                    return []
        except Exception as e:
            print("SQL ERROR in fetch_all():", e)
            print("FAILED SQL:", sql)
            return []

# --------------------------------------------------------------------
# fetch_one() — Return a single row (or None)
# --------------------------------------------------------------------
def fetch_one(sql, params=None):
    with engine.connect() as connection:
        try:
            result = connection.execute(text(sql), params or {})
            try:
                row = result.fetchone()
            except Exception:
                try:
                    row = result.first()
                except Exception:
                    row = None
            return row
        except Exception as e:
            print("SQL ERROR in fetch_one():", e)
            print("FAILED SQL:", sql)
            return None

# --------------------------------------------------------------------
# execute() — Unified write/return behaviour
# --------------------------------------------------------------------
def execute(query: str, params=None):
    """
    Unified DB executor:

    SELECT → returns list of rows  
    INSERT/UPDATE/DELETE with RETURNING → returns list of rows  
    Non-returning INSERT/UPDATE/DELETE → returns dict {"rows_affected": n}

    Guaranteed to NEVER return a Result object.
    """
    params = params or {}

    try:
        with engine.begin() as conn:
            result = conn.execute(text(query), params)

            sql_upper = query.strip().upper()

            # SELECT queries → return rows
            if sql_upper.startswith("SELECT"):
                return result.mappings().all()

            # INSERT ... RETURNING → return rows
            if "RETURNING" in sql_upper:
                return result.mappings().all()

            # UPDATE / DELETE → return affected row count
            return result.rowcount

    except SQLAlchemyError as e:
        return {"error": str(e)}
