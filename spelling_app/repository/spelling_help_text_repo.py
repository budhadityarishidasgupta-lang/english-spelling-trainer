from sqlalchemy import text

from shared.db import fetch_all


def _to_dict(row):
    if row is None:
        return {}
    if isinstance(row, dict):
        return row
    if hasattr(row, "_mapping"):
        return dict(row._mapping)
    try:
        return dict(row)
    except Exception:
        return {}


def get_help_text(db, help_key):
    query = """
        SELECT help_key, title, body
        FROM spelling_help_texts
        WHERE help_key = :help_key
    """
    result = db.execute(text(query), {"help_key": help_key})
    return result.fetchone()


def upsert_help_text(help_key: str, title: str, body: str):
    rows = fetch_all(
        """
        INSERT INTO spelling_help_texts (help_key, title, body, updated_at)
        VALUES (:help_key, :title, :body, NOW())
        ON CONFLICT (help_key) DO UPDATE
        SET title = EXCLUDED.title,
            body = EXCLUDED.body,
            updated_at = NOW()
        RETURNING id, help_key, title, body, updated_at;
        """,
        {"help_key": help_key, "title": title, "body": body},
    )

    if isinstance(rows, dict):
        return rows

    if not rows:
        return {}

    return _to_dict(rows[0])
