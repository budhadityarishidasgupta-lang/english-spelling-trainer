import os
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Load database URL from environment variable (Render or local)
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable not set.")

# Create SQLAlchemy engine with correct schema search_path
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

# Helper: run SELECT and return rows
def fetch_all(sql, params=None):
    """
    Run a SELECT (or any query expected to return rows) and
    always return a concrete list of row objects.

    This keeps behaviour consistent with execute() for RETURNING
    queries and avoids Result/iterator surprises.
    """
    with engine.connect() as connection:
        try:
            result = connection.execute(text(sql), params or {})
            try:
                rows = result.fetchall()
            except Exception:
                try:
                    rows = result.all()
                except Exception:
                    rows = []
            return rows
        except Exception as e:
            print("SQL ERROR in fetch_all():", e)
            print("Failed SQL:", sql)
            return []

# Helper: run INSERT/UPDATE/DELETE
def execute(query, params=None):
    """Execute a write query.

    Behaviour:
    - For plain INSERT/UPDATE/DELETE (no RETURNING): returns {"status": "success"} or {"error": ...}
    - For INSERT ... RETURNING / UPDATE ... RETURNING: returns a list of rows,
      so writers that expect rows continue to work.
    """
    try:
        with engine.begin() as conn:
            result = conn.execute(text(query), params or {})

            if "RETURNING" in query.upper():
                try:
                    rows = result.fetchall()
                except Exception:
                    # Some drivers expose .all() instead of .fetchall()
                    try:
                        rows = result.all()
                    except Exception:
                        rows = []
                return rows

        # Non-RETURNING write: simple status dict
        return {"status": "success"}
    except SQLAlchemyError as e:
        return {"error": str(e)}
