-- Verify weak word tracking with latest mistakes first.
SELECT
    ww.user_id,
    u.name,
    w.word,
    ww.wrong_count,
    ww.last_wrong_at
FROM weak_words ww
JOIN spelling_words w ON w.word_id = ww.word_id
JOIN users u ON u.user_id = ww.user_id
ORDER BY ww.last_wrong_at DESC;
