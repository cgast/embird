-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

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
    embedding vector(1536), -- Using 1536 dimensions for Cohere embeddings
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