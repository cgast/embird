-- First ensure we're connected to the right database
\c newsdb;

-- Required memory settings
-- Increase work memory for operations (from current 4MB to 64MB)
ALTER SYSTEM SET work_mem = '65536kB';

-- Increase maintenance work memory (from current 512MB to 1GB)
ALTER SYSTEM SET maintenance_work_mem = '1048576kB';

-- Add statement timeout if needed (currently unlimited)
-- Only set this if you want to prevent indefinitely long queries
-- ALTER SYSTEM SET statement_timeout = '3600000ms';  -- 1 hour

-- Increase checkpoint timeout (from current 5 min to 15 min)
ALTER SYSTEM SET checkpoint_timeout = '900s';

-- For autovacuum, since it's causing issues:
ALTER SYSTEM SET autovacuum_work_mem = '1048576kB';  -- Currently -1 (uses maintenance_work_mem)
ALTER SYSTEM SET autovacuum_vacuum_cost_delay = '20ms';  -- Make it less aggressive
SELECT pg_reload_conf();


-- Create the vector extension if it doesn't exist
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify the extension was created
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM pg_extension 
        WHERE extname = 'vector'
    ) THEN
        RAISE EXCEPTION 'Vector extension not installed properly';
    END IF;
END
$$;


-- Create news table with vector support
CREATE TABLE IF NOT EXISTS news (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT,
    url TEXT NOT NULL,
    source_url TEXT NOT NULL,
    first_seen_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_seen_at TIMESTAMP WITH TIME ZONE NOT NULL,
    hit_count INTEGER NOT NULL DEFAULT 1,
    embedding vector(1024), -- Updated to 1024 dimensions for Cohere embed-english-v3.0 model
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create unique index on URL to ensure we don't duplicate entries
CREATE UNIQUE INDEX IF NOT EXISTS news_url_idx ON news(url);

-- Create index on source URL for quick filtering by source
CREATE INDEX IF NOT EXISTS news_source_url_idx ON news(source_url);

-- Create index on timestamps for time-based filtering
CREATE INDEX IF NOT EXISTS news_first_seen_idx ON news(first_seen_at);
CREATE INDEX IF NOT EXISTS news_last_seen_idx ON news(last_seen_at);

-- Create vector index for similarity search
CREATE INDEX IF NOT EXISTS news_embedding_idx ON news USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
