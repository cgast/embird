# EmBird API Documentation

## Overview

EmBird provides a comprehensive REST API for news aggregation, semantic search, and personalized ranking. The API is built with FastAPI and includes full OpenAPI documentation.

## API Documentation URLs

Once the application is running, you can access interactive API documentation at:

- **Swagger UI**: `http://localhost:8000/api/docs`
- **ReDoc**: `http://localhost:8000/api/redoc`
- **OpenAPI Schema**: `http://localhost:8000/api/openapi.json`

## Quick Start

### 1. Add a News Source

```bash
curl -X POST "http://localhost:8000/api/urls" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://techcrunch.com/feed/",
    "type": "rss"
  }'
```

### 2. Wait for Crawler

The crawler runs automatically every hour. You can also trigger it manually (if implemented).

### 3. Search for News

```bash
curl -X GET "http://localhost:8000/api/news/search?query=artificial%20intelligence&limit=10"
```

### 4. Get News Clusters

```bash
curl -X GET "http://localhost:8000/api/news/clusters"
```

### 5. Get UMAP Visualization

```bash
curl -X GET "http://localhost:8000/api/news/umap"
```

## API Endpoints

### Health Check

#### `GET /api/health`

Check the health status of all services.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "services": {
    "database": "healthy",
    "faiss": "healthy",
    "embedding": "healthy"
  },
  "timestamp": "2025-10-25T12:00:00Z"
}
```

---

### Sources (URL Management)

#### `GET /api/urls`

List all crawl sources.

**Response:**
```json
[
  {
    "id": 1,
    "url": "https://techcrunch.com/feed/",
    "type": "rss",
    "created_at": "2025-10-20T10:00:00Z",
    "updated_at": "2025-10-25T12:00:00Z",
    "last_crawled_at": "2025-10-25T11:30:00Z"
  }
]
```

#### `POST /api/urls`

Add a new crawl source.

**Request:**
```json
{
  "url": "https://news.ycombinator.com/rss",
  "type": "rss"
}
```

**Response:** `201 Created` with the created URL object.

#### `GET /api/urls/{url_id}`

Get a specific source by ID.

#### `DELETE /api/urls/{url_id}`

Delete a source (does not delete already crawled content).

---

### News

#### `GET /api/news`

List news items with pagination.

**Query Parameters:**
- `source_url` (optional): Filter by source URL
- `limit` (default: 100): Maximum items to return (1-1000)
- `offset` (default: 0): Number of items to skip

**Response:**
```json
[
  {
    "id": 12345,
    "title": "AI Breakthrough: New Language Model Sets Records",
    "summary": "Researchers unveil...",
    "url": "https://example.com/article",
    "source_url": "https://example.com/rss",
    "first_seen_at": "2025-10-25T08:00:00Z",
    "last_seen_at": "2025-10-25T12:00:00Z",
    "hit_count": 3,
    "created_at": "2025-10-25T08:00:00Z",
    "updated_at": "2025-10-25T12:00:00Z"
  }
]
```

#### `GET /api/news/{news_id}`

Get a specific news item by ID.

#### `GET /api/news/search`

Semantic search for news using AI embeddings.

**Query Parameters:**
- `query` (required): Search query text
- `limit` (default: 10): Maximum results (1-100)

**Response:**
```json
[
  {
    "id": 12345,
    "title": "AI Breakthrough...",
    "similarity": 0.92,
    "url": "https://example.com/article",
    ...
  }
]
```

#### `GET /api/news/trending`

Get trending news based on hit count.

**Query Parameters:**
- `limit` (default: 10): Maximum items (1-100)
- `hours` (default: 24): Time window (1-168 hours)

#### `GET /api/news/clusters`

Get automatically clustered news articles.

**Response:**
```json
{
  "0": [
    {
      "id": 1,
      "title": "Article 1",
      "similarity": 0.95,
      ...
    }
  ],
  "1": [...]
}
```

#### `GET /api/news/umap`

Get UMAP 2D visualization data.

**Response:**
```json
[
  {
    "id": 1,
    "title": "Article Title",
    "url": "https://example.com/article",
    "x": 0.23,
    "y": -0.45,
    "cluster_id": 0,
    "timestamp": "2025-10-25T12:00:00Z"
  }
]
```

---

### Preferences

#### `GET /api/preferences`

List all preference vectors (for personalized ranking).

**Response:**
```json
[
  {
    "id": 5,
    "title": "AI & Machine Learning",
    "description": "Latest developments in AI...",
    "created_at": "2025-10-20T10:00:00Z",
    "updated_at": "2025-10-25T12:00:00Z"
  }
]
```

#### `POST /api/preferences`

Create a new preference vector.

**Request:**
```json
{
  "title": "AI & Machine Learning",
  "description": "I'm interested in artificial intelligence, machine learning, and deep learning breakthroughs"
}
```

**Response:** `201 Created` with the created preference vector (including embedding).

#### `GET /api/preferences/{vector_id}`

Get a specific preference vector (includes full embedding data).

#### `PUT /api/preferences/{vector_id}`

Update a preference vector.

**Request:**
```json
{
  "title": "Updated Title",
  "description": "Updated description"
}
```

Note: Updating the description will regenerate the embedding.

#### `DELETE /api/preferences/{vector_id}`

Delete a preference vector.

---

## Error Handling

All errors follow a standard format:

```json
{
  "detail": "Human-readable error message",
  "error_code": "MACHINE_READABLE_CODE",
  "timestamp": "2025-10-25T12:00:00Z"
}
```

### Common HTTP Status Codes

- `200 OK`: Request successful
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request parameters
- `404 Not Found`: Resource not found
- `422 Unprocessable Entity`: Validation error or processing failed
- `500 Internal Server Error`: Server error

---

## Rate Limiting

Currently, EmBird does not implement rate limiting. This will be added in a future release.

---

## Authentication

Currently, EmBird does not require authentication. This is suitable for personal deployments but should be added for public-facing instances.

---

## Data Models

### NewsItem

- `id`: Unique identifier
- `title`: Article title
- `summary`: Article summary/excerpt
- `url`: Original article URL
- `source_url`: Source RSS/homepage URL
- `first_seen_at`: First discovery timestamp
- `last_seen_at`: Last seen timestamp
- `hit_count`: Number of times encountered
- `created_at`: Database creation timestamp
- `updated_at`: Database update timestamp

### NewsItemSimilarity

Extends NewsItem with:
- `similarity`: Cosine similarity score (0.0-1.0)

### URL

- `id`: Unique identifier
- `url`: Full URL
- `type`: "rss" or "homepage"
- `created_at`: Creation timestamp
- `updated_at`: Update timestamp
- `last_crawled_at`: Last crawl timestamp (nullable)

### PreferenceVector

- `id`: Unique identifier
- `title`: Short descriptive title
- `description`: Detailed interest description
- `embedding`: 1024-dimensional vector (optional in responses)
- `created_at`: Creation timestamp
- `updated_at`: Update timestamp

---

## Semantic Search

EmBird uses Cohere's `embed-english-v3.0` model to generate 1024-dimensional embeddings for:

1. **News articles** (from title + summary or title only)
2. **Search queries**
3. **Preference vectors** (from description)

### How Similarity Works

- Embeddings are compared using **cosine similarity**
- Similarity scores range from 0.0 (unrelated) to 1.0 (identical)
- Typical thresholds:
  - `> 0.9`: Very highly related
  - `0.7-0.9`: Strongly related
  - `0.5-0.7`: Moderately related
  - `< 0.5`: Weakly or unrelated

### Clustering

EmBird uses **transitive clustering**:
1. For each article, find similar articles (above threshold)
2. Expand cluster to include articles similar to any cluster member
3. Repeat until no new articles are added
4. Results in overlapping, semantically coherent clusters

### UMAP Visualization

UMAP (Uniform Manifold Approximation and Projection) reduces 1024D embeddings to 2D:
- Preserves local and global structure
- Computationally expensive (cached in database)
- Useful for exploring news landscape visually

---

## Configuration

All API behavior can be configured via environment variables:

```bash
# Cohere API
COHERE_API_KEY=your-api-key-here

# Crawler
CRAWLER_INTERVAL=3600  # seconds
NEWS_RETENTION_DAYS=30
NEWS_MAX_ITEMS=10000
EMBED_TITLE_ONLY=True

# Visualization
VISUALIZATION_TIME_RANGE=48  # hours
VISUALIZATION_SIMILARITY=0.55  # threshold

# FAISS
FAISS_UPDATE_INTERVAL=3600  # seconds
FAISS_MAX_VECTORS=10000
```

See `app/config.py` for all available settings.

---

## Future API Endpoints (Planned)

### News Normalization Service

EmBird is being extended with a **news normalization** service that will:

1. **Remove bias and clickbait** from article titles
2. **Extract structured facts** from articles
3. **Generate normalized "frontmatter"** with:
   - Subject entities
   - Object entities
   - Actions
   - Effects
   - Timestamps

This will enable:
- **Bias-free news consumption**
- **Fact-based comparisons** across sources
- **Structured querying** (e.g., "Show me all news about [Entity X] doing [Action Y]")

### Planned Endpoints

```
POST /api/news/{news_id}/normalize
  - Normalize a single article
  - Returns structured frontmatter

GET /api/news/{news_id}/normalized
  - Get normalized version if available

GET /api/news/normalized
  - List all normalized news
  - Filter by entities, actions, etc.

POST /api/news/compare
  - Compare multiple articles about same event
  - Identify consensus facts vs. differences
```

---

## Development

### Running Tests

```bash
# Install dependencies
pip install -r requirements.txt

# Run API validation
python validate_api.py
```

### Generating OpenAPI Schema

The OpenAPI schema is automatically generated and available at:
- `/api/openapi.json`

To save it to a file:

```bash
curl http://localhost:8000/api/openapi.json > openapi.json
```

---

## Support

For issues, feature requests, or contributions:
- GitHub: https://github.com/cgast/embird
- Issues: https://github.com/cgast/embird/issues

---

## License

MIT License - See LICENSE file for details
