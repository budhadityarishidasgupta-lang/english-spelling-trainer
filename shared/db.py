import os
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

    # Already a dict
    if isinstance(row, dict):
        return row

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


ensure_spelling_help_texts_table(engine)


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


ensure_spelling_content_blocks_table(engine)


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


ensure_spelling_payments_table(engine)




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
    try:
        with engine.begin() as conn:
            result = conn.execute(text(query), params or {})

            # SELECT → always rows
            if query.strip().upper().startswith("SELECT"):
                return result.fetchall()

            # INSERT/UPDATE/DELETE with RETURNING
            if "RETURNING" in query.upper():
                try:
                    return result.fetchall()
                except Exception:
                    return []

            # Non-returning write → simple dict
            return {"rows_affected": result.rowcount}

    except SQLAlchemyError as e:
        return {"error": str(e)}
