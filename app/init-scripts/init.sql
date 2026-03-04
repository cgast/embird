-- First ensure we're connected to the right database
\c newsdb;

-- Required memory settings
ALTER SYSTEM SET work_mem = '65536kB';
ALTER SYSTEM SET maintenance_work_mem = '1048576kB';
ALTER SYSTEM SET checkpoint_timeout = '900s';
ALTER SYSTEM SET autovacuum_work_mem = '1048576kB';
ALTER SYSTEM SET autovacuum_vacuum_cost_delay = '20ms';
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

-- Create function to convert float array to vector
CREATE OR REPLACE FUNCTION array_to_vector(arr float[])
RETURNS vector
AS $$
BEGIN
    RETURN arr::vector;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================================
-- Topics table (must be created before tables that reference it)
-- ============================================================
CREATE TABLE IF NOT EXISTS topics (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Insert default topic if it doesn't exist
INSERT INTO topics (name, slug, description)
VALUES ('Default', 'default', 'Default topic')
ON CONFLICT (slug) DO NOTHING;

-- ============================================================
-- News table with vector support
-- ============================================================
CREATE TABLE IF NOT EXISTS news (
    id SERIAL PRIMARY KEY,
    topic_id INTEGER NOT NULL DEFAULT 1 REFERENCES topics(id),
    title TEXT NOT NULL,
    summary TEXT,
    url TEXT NOT NULL,
    source_url TEXT NOT NULL,
    first_seen_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_seen_at TIMESTAMP WITH TIME ZONE NOT NULL,
    hit_count INTEGER NOT NULL DEFAULT 1,
    embedding vector(1024),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Migration: add topic_id column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='news' AND column_name='topic_id'
    ) THEN
        ALTER TABLE news ADD COLUMN topic_id INTEGER NOT NULL DEFAULT 1;
        ALTER TABLE news ADD CONSTRAINT fk_news_topic FOREIGN KEY (topic_id) REFERENCES topics(id);
    END IF;
END $$;

-- Drop old unique index on url (now unique per topic)
DROP INDEX IF EXISTS news_url_idx;

-- Create unique index on (topic_id, url)
CREATE UNIQUE INDEX IF NOT EXISTS uix_news_topic_url ON news(topic_id, url);

-- Create index on topic_id
CREATE INDEX IF NOT EXISTS idx_news_topic_id ON news(topic_id);

-- Create index on source URL for quick filtering by source
CREATE INDEX IF NOT EXISTS news_source_url_idx ON news(source_url);

-- Create index on timestamps for time-based filtering
CREATE INDEX IF NOT EXISTS news_first_seen_idx ON news(first_seen_at);
CREATE INDEX IF NOT EXISTS news_last_seen_idx ON news(last_seen_at);

-- Create vector index for similarity search
CREATE INDEX IF NOT EXISTS news_embedding_idx ON news USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================
-- News clusters table
-- ============================================================
CREATE TABLE IF NOT EXISTS news_clusters (
    id SERIAL PRIMARY KEY,
    topic_id INTEGER NOT NULL DEFAULT 1 REFERENCES topics(id),
    hours INTEGER NOT NULL,
    min_similarity FLOAT NOT NULL,
    clusters JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Migration: add topic_id column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='news_clusters' AND column_name='topic_id'
    ) THEN
        ALTER TABLE news_clusters ADD COLUMN topic_id INTEGER NOT NULL DEFAULT 1;
        ALTER TABLE news_clusters ADD CONSTRAINT fk_news_clusters_topic FOREIGN KEY (topic_id) REFERENCES topics(id);
    END IF;
END $$;

-- Drop old constraints/indexes that don't include topic_id
DROP INDEX IF EXISTS news_clusters_lookup_idx;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'news_clusters_hours_min_similarity_key') THEN
        ALTER TABLE news_clusters DROP CONSTRAINT news_clusters_hours_min_similarity_key;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uix_hours_similarity') THEN
        ALTER TABLE news_clusters DROP CONSTRAINT uix_hours_similarity;
    END IF;
END $$;

-- Create new composite index and unique constraint with topic_id
CREATE INDEX IF NOT EXISTS idx_clusters_topic_hours_similarity ON news_clusters(topic_id, hours, min_similarity);
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uix_topic_hours_similarity') THEN
        ALTER TABLE news_clusters ADD CONSTRAINT uix_topic_hours_similarity UNIQUE (topic_id, hours, min_similarity);
    END IF;
END $$;

-- ============================================================
-- News UMAP table
-- ============================================================
CREATE TABLE IF NOT EXISTS news_umap (
    id SERIAL PRIMARY KEY,
    topic_id INTEGER NOT NULL DEFAULT 1 REFERENCES topics(id),
    hours INTEGER NOT NULL,
    visualization JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Migration: add topic_id column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='news_umap' AND column_name='topic_id'
    ) THEN
        ALTER TABLE news_umap ADD COLUMN topic_id INTEGER NOT NULL DEFAULT 1;
        ALTER TABLE news_umap ADD CONSTRAINT fk_news_umap_topic FOREIGN KEY (topic_id) REFERENCES topics(id);
    END IF;
END $$;

-- Add min_similarity column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name='news_umap' AND column_name='min_similarity'
    ) THEN
        ALTER TABLE news_umap ADD COLUMN min_similarity FLOAT NOT NULL DEFAULT 0.6;
    END IF;
END $$;

-- Drop old constraints/indexes that don't include topic_id
DROP INDEX IF EXISTS news_umap_hours_idx;
DROP INDEX IF EXISTS idx_umap_hours_similarity;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uix_umap_hours_similarity') THEN
        ALTER TABLE news_umap DROP CONSTRAINT uix_umap_hours_similarity;
    END IF;
END $$;

-- Create new composite index and unique constraint with topic_id
CREATE INDEX IF NOT EXISTS idx_umap_topic_hours_similarity ON news_umap(topic_id, hours, min_similarity);
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uix_umap_topic_hours_similarity') THEN
        ALTER TABLE news_umap ADD CONSTRAINT uix_umap_topic_hours_similarity UNIQUE (topic_id, hours, min_similarity);
    END IF;
END $$;

-- ============================================================
-- Preference vectors table
-- ============================================================
CREATE TABLE IF NOT EXISTS preference_vectors (
    id SERIAL PRIMARY KEY,
    topic_id INTEGER NOT NULL DEFAULT 1 REFERENCES topics(id),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    embedding vector(1024),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Migration: add topic_id column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='preference_vectors' AND column_name='topic_id'
    ) THEN
        ALTER TABLE preference_vectors ADD COLUMN topic_id INTEGER NOT NULL DEFAULT 1;
        ALTER TABLE preference_vectors ADD CONSTRAINT fk_preference_vectors_topic FOREIGN KEY (topic_id) REFERENCES topics(id);
    END IF;
END $$;

-- Drop old unique index on title (now unique per topic)
DROP INDEX IF EXISTS preference_vectors_title_idx;

-- Create unique index on (topic_id, title)
CREATE UNIQUE INDEX IF NOT EXISTS uix_preference_vectors_topic_title ON preference_vectors(topic_id, title);

-- Create index on topic_id
CREATE INDEX IF NOT EXISTS idx_preference_vectors_topic_id ON preference_vectors(topic_id);

-- Create vector index for similarity search
CREATE INDEX IF NOT EXISTS preference_vectors_embedding_idx ON preference_vectors USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
