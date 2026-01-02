import os
import psycopg2


def get_db_connection():
    """
    Returns a new DB connection using DATABASE_URL.
    """
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    return psycopg2.connect(database_url)
