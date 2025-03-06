-- Add min_similarity column to news_umap table if it doesn't exist
DO $BLOCK$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name='news_umap' AND column_name='min_similarity'
    ) THEN
        ALTER TABLE news_umap ADD COLUMN min_similarity FLOAT NOT NULL DEFAULT 0.6;
    END IF;
END $BLOCK$;
