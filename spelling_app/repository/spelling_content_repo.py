from sqlalchemy import text


def get_content_block(db, block_key):
    """
    Returns a row with: block_key, title, body, media_data
    or None if missing.
    """
    query = """
        SELECT block_key, title, body, media_data
        FROM spelling_content_blocks
        WHERE block_key = :block_key
    """
    result = db.execute(text(query), {"block_key": block_key})
    return result.fetchone()


def upsert_content_block(db, block_key, title=None, body=None, media_data=None):
    """
    Admin-authored content: upsert is allowed.
    """
    query = """
        INSERT INTO spelling_content_blocks (block_key, title, body, media_data, updated_at)
        VALUES (:block_key, :title, :body, :media_data, CURRENT_TIMESTAMP)
        ON CONFLICT (block_key)
        DO UPDATE SET
            title = EXCLUDED.title,
            body = EXCLUDED.body,
            media_data = EXCLUDED.media_data,
            updated_at = CURRENT_TIMESTAMP
    """
    db.execute(
        text(query),
        {
            "block_key": block_key,
            "title": title,
            "body": body,
            "media_data": media_data,
        },
    )
    db.commit()


def delete_content_block(db, block_key):
    """
    Explicit admin delete (not silent).
    Removes the row for this block_key.
    """
    query = "DELETE FROM spelling_content_blocks WHERE block_key = :block_key"
    db.execute(text(query), {"block_key": block_key})
    db.commit()
