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
def fetch_all(query, params=None):
    try:
        with engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            return [dict(row) for row in result]
    except SQLAlchemyError as e:
        return {"error": str(e)}

# Helper: run INSERT/UPDATE/DELETE
def execute(query, params=None):
    try:
        with engine.begin() as conn:
            conn.execute(text(query), params or {})
        return {"status": "success"}
    except SQLAlchemyError as e:
        return {"error": str(e)}
