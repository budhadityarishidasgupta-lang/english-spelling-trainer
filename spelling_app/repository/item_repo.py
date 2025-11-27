from shared.db import fetch_all, execute


def get_items_for_lesson(lesson_id):

    return fetch_all(
        """
        SELECT si.item_id, si.word
        FROM spelling_items si
        JOIN spelling_lesson_items sli ON sli.item_id = si.item_id
        WHERE sli.lesson_id = :lid
        ORDER BY si.item_id
        """,
        {"lid": lesson_id}
    )


def create_item(word: str):
    result = fetch_all(
        """
        INSERT INTO spelling_items (word, created_at)
        VALUES (:word, NOW())
        ON CONFLICT (word) DO NOTHING
        RETURNING item_id;
        """,
        {"word": word},
    )

    if isinstance(result, dict):
        return result

    # If the word already exists, ON CONFLICT DO NOTHING prevents insertion,
    # and RETURNING item_id returns an empty list. We must manually look up the ID.
    if not result:
        existing = get_item_by_word(word)
        if existing:
            return existing["item_id"]
        else:
            # Should only happen on a true DB error
            return None

    return result[0]._mapping["item_id"] if result else None


def map_item_to_lesson(lesson_id, item_id, sort_order=None):
    return fetch_all(
        """
        INSERT INTO spelling_lesson_items (lesson_id, item_id)
        VALUES (:lesson_id, :item_id)
        ON CONFLICT DO NOTHING;
        """,
        {"lesson_id": lesson_id, "item_id": item_id},
    )


def get_item_by_word(word: str):
    """
    Returns an item dict if a word already exists in spelling_items.
    Otherwise returns None.
    """
    sql = """
        SELECT item_id, word
        FROM spelling_items
        WHERE word = :word
        LIMIT 1;
    """
    result = fetch_all(sql, {"word": word})

    if isinstance(result, dict):
        return None

    if result and len(result) > 0:
        row = result[0]
        return dict(getattr(row, "_mapping", row))

    return None
