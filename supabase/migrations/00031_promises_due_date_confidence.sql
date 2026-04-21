-- 00031_promises_due_date_confidence.sql
-- Civic Scout robustness:
--   1. Persist due_date + date_confidence on promises (extractor already
--      computes these; DB currently drops them).
--   2. Add append_processed_pdf_url_capped(scout_id, url, cap) helper so the
--      civic-extract-worker can mark a URL as processed only after a
--      successful extraction, replacing the previous "mark on enqueue" path
--      which silently dropped URLs when Firecrawl failed.

-- --------------------------------------------------------------------------
-- promises: due_date + date_confidence
-- --------------------------------------------------------------------------

ALTER TABLE promises
    ADD COLUMN IF NOT EXISTS due_date DATE,
    ADD COLUMN IF NOT EXISTS date_confidence TEXT
        CHECK (date_confidence IN ('high', 'medium', 'low'));

CREATE INDEX IF NOT EXISTS idx_promises_due_date
    ON promises (due_date)
    WHERE due_date IS NOT NULL;

-- --------------------------------------------------------------------------
-- scouts.processed_pdf_urls — append+cap helper
-- --------------------------------------------------------------------------
-- Append p_url to scouts.processed_pdf_urls, deduped, keeping the most
-- recent p_cap entries (FIFO eviction). No-op if the URL is already present.

CREATE OR REPLACE FUNCTION append_processed_pdf_url_capped(
    p_scout_id UUID,
    p_url TEXT,
    p_cap INT DEFAULT 100
) RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    cur_arr TEXT[];
    new_arr TEXT[];
    new_len INT;
BEGIN
    SELECT COALESCE(processed_pdf_urls, ARRAY[]::text[])
      INTO cur_arr
      FROM scouts
     WHERE id = p_scout_id
     FOR UPDATE;

    IF cur_arr IS NULL THEN
        RETURN;  -- scout not found
    END IF;

    IF p_url = ANY(cur_arr) THEN
        RETURN;
    END IF;

    new_arr := cur_arr || ARRAY[p_url];
    new_len := array_length(new_arr, 1);
    IF new_len > p_cap THEN
        new_arr := new_arr[(new_len - p_cap + 1):new_len];
    END IF;

    UPDATE scouts
       SET processed_pdf_urls = new_arr
     WHERE id = p_scout_id;
END;
$$;
