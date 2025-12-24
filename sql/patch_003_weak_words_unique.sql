-- Ensure each user has a single weak word entry per word.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        WHERE t.relname = 'weak_words'
          AND c.conname = 'weak_words_user_word_unique'
    ) THEN
        ALTER TABLE weak_words
        ADD CONSTRAINT weak_words_user_word_unique
        UNIQUE (user_id, word_id);
    END IF;
END
$$;
