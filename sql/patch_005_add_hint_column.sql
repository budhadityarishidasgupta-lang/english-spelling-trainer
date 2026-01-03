-- Add optional hint column for spelling words
ALTER TABLE spelling_words
ADD COLUMN IF NOT EXISTS hint TEXT;
