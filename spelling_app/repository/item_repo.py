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

    # Case 1: DB error on INSERT
    if isinstance(result, dict):
        return result

    # Case 2: Conflict occurred → no row returned → look up existing item
    if not result:
        existing = get_item_by_word(word)
        if isinstance(existing, dict):
            return existing
        if existing:
            return existing["item_id"]
        return None  # unexpected DB inconsistency

    # Case 3: Newly inserted
    return result[0]._mapping["item_id"]


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
    Fetch a single spelling item row by its word.
    Returns:
      - dict-like row mapping containing 'item_id' and 'word'
      - None if no row exists
      - dict error object if the DB returned an error
    """
    rows = fetch_all(
        """
        SELECT item_id, word
        FROM spelling_items
        WHERE LOWER(word) = LOWER(:word)
        LIMIT 1;
        """,
        {"word": word},
    )

    if isinstance(rows, dict):
        return rows  # DB error

    if not rows:
        return None  # word not found

    return rows[0]._mapping
