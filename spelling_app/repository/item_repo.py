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
        RETURNING item_id;
        """,
        {"word": word},
    )

    if isinstance(result, dict):
        return result

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
