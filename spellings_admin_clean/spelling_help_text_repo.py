from sqlalchemy import text


def get_help_text(db, help_key):
    query = """
        SELECT help_key, title, body
        FROM spelling_help_texts
        WHERE help_key = :help_key
    """
    result = db.execute(text(query), {"help_key": help_key})
    return result.fetchone()


def upsert_help_text(db, help_key, title, body):
    query = """
        INSERT INTO spelling_help_texts (help_key, title, body, updated_at)
        VALUES (:help_key, :title, :body, CURRENT_TIMESTAMP)
        ON CONFLICT (help_key)
        DO UPDATE SET
            title = EXCLUDED.title,
            body = EXCLUDED.body,
            updated_at = CURRENT_TIMESTAMP
    """
    db.execute(
        text(query),
        {
            "help_key": help_key,
            "title": title,
            "body": body,
        },
    )
    db.commit()
