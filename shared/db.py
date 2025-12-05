import os
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

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
