from shared.db import fetch_all, execute


def get_items_for_lesson(lesson_id):
    return fetch_all(
        """
        SELECT i.*
        FROM items i
        JOIN lesson_items li ON i.sp_item_id = li.sp_item_id
        WHERE li.sp_lesson_id = :lid
        ORDER BY li.sort_order NULLS LAST, i.sp_item_id
        """,
        {"lid": lesson_id}
    )


def create_item(base_word, display_form, pattern_type, options, difficulty, hint):
    return execute(
        """
        INSERT INTO items (base_word, display_form, pattern_type, options, difficulty, hint)
        VALUES (:bw, :df, :pt, :opt, :diff, :ht)
        """,
        {
            "bw": base_word,
            "df": display_form,
            "pt": pattern_type,
            "opt": options,
            "diff": difficulty,
            "ht": hint,
        }
    )


def map_item_to_lesson(lesson_id, item_id, sort_order=None):
    return execute(
        """
        INSERT INTO lesson_items (sp_lesson_id, sp_item_id, sort_order)
        VALUES (:lid, :iid, :sort)
        """,
        {"lid": lesson_id, "iid": item_id, "sort": sort_order}
    )
