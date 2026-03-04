# Multi-Topic EmBird Implementation Plan

## Overview

Transform EmBird from a single-topic news aggregator into a multi-topic platform where each topic has its own isolated set of sources (URLs), news items, preference vectors, clusters, and UMAP visualizations. Topics are selected via URL path prefix: `yourdomain.xyz/topic_a/news`, `yourdomain.xyz/topic_b/clusters`, etc.

---

## Phase 1: Database & Models

### 1.1 New `topics` table (PostgreSQL)

Add a `topics` table:

```sql
CREATE TABLE IF NOT EXISTS topics (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,      -- URL-safe identifier (e.g. "tech-news", "politics")
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

New SQLAlchemy model in `app/models/topic.py`:
- `Topic(Base)` with fields: id, name, slug, description, created_at, updated_at
- Pydantic models: `TopicCreate`, `TopicResponse`
- Slug validation: lowercase alphanumeric + hyphens only

### 1.2 Add `topic_id` foreign key to existing PostgreSQL tables

**`news` table:**
- Add `topic_id INTEGER REFERENCES topics(id)` (NOT NULL after migration)
- Add index on `topic_id`
- Update unique constraint: `url` uniqueness should be per-topic → `UNIQUE(topic_id, url)`

**`preference_vectors` table:**
- Add `topic_id INTEGER REFERENCES topics(id)` (NOT NULL after migration)
- Update unique constraint: `title` uniqueness per-topic → `UNIQUE(topic_id, title)`

**`news_clusters` table:**
- Add `topic_id INTEGER REFERENCES topics(id)` (NOT NULL after migration)
- Update unique constraint: `UNIQUE(topic_id, hours, min_similarity)`

**`news_umap` table:**
- Add `topic_id INTEGER REFERENCES topics(id)` (NOT NULL after migration)
- Update unique constraint: `UNIQUE(topic_id, hours, min_similarity)`

### 1.3 Add `topic_id` to SQLite `urls` table

- Add `topic_id INTEGER NOT NULL DEFAULT 1` column
- Remove global uniqueness on `url`, make it `UNIQUE(topic_id, url)` (same source can be in multiple topics)

### 1.4 Update SQLAlchemy models

- `NewsItem`: add `topic_id` column + FK, update `__table_args__`
- `PreferenceVector`: add `topic_id` column + FK, update unique constraint
- `NewsClusters`: add `topic_id` column + FK, update unique constraint
- `NewsUMAP`: add `topic_id` column + FK, update unique constraint
- `URLDatabase`: add `topic_id` parameter to all methods

### 1.5 Migration for existing data

- Create a "default" topic with slug `"default"` and name `"Default"`
- Set `topic_id = 1` (the default topic) on all existing rows in `news`, `preference_vectors`, `news_clusters`, `news_umap`, and SQLite `urls`
- Then add NOT NULL constraints

**Files changed:** `app/models/topic.py` (new), `app/models/news.py`, `app/models/preference_vector.py`, `app/models/url.py`, `app/init-scripts/init.sql`

---

## Phase 2: Topic CRUD & URL Database Updates

### 2.1 Topic management API

New endpoints in `app/routes/api.py`:
- `GET /api/topics` — list all topics
- `POST /api/topics` — create topic (name, slug, description)
- `GET /api/topics/{slug}` — get topic by slug
- `PUT /api/topics/{slug}` — update topic
- `DELETE /api/topics/{slug}` — delete topic (and all associated data)

### 2.2 Update `URLDatabase` class

Update all methods in `app/models/url.py` to be topic-aware:
- `add_url(url_data, topic_id)` — associate URL with topic
- `get_all_urls(topic_id=None)` — filter by topic, or return all
- `get_urls_to_crawl(topic_id=None)` — filter by topic
- `delete_url(url_id)` — unchanged (URL has its own ID)
- Add `get_topic_id_for_url(url_id)` helper

### 2.3 Update `app/services/db.py`

- Import `Topic` model
- Add `get_or_create_default_topic()` helper for bootstrapping

**Files changed:** `app/routes/api.py`, `app/models/url.py`, `app/services/db.py`

---

## Phase 3: Topic-Scoped Routing

### 3.1 Web routes (`app/routes/web.py`)

Restructure all web routes with a `/{topic_slug}` prefix. A topic dependency resolves the slug to a `Topic` object (404 if not found).

**New routes:**
- `GET /` — topic list page (or redirect to default topic)
- `GET /{topic_slug}/` — home page for topic (scored news)
- `GET /{topic_slug}/news` — news list for topic
- `GET /{topic_slug}/news/{id}` — single news item
- `GET /{topic_slug}/search` — search within topic
- `GET /{topic_slug}/clusters` — clusters for topic
- `GET /{topic_slug}/umap` — UMAP for topic
- `GET /{topic_slug}/urls` — sources for topic
- `GET /{topic_slug}/urls/add` — add source to topic
- `POST /{topic_slug}/urls/add` — handle add source
- `GET /{topic_slug}/urls/{id}/delete` — confirm delete source
- `POST /{topic_slug}/urls/{id}/delete` — handle delete source
- `GET /{topic_slug}/preference-vectors` — preference vectors for topic
- `GET /{topic_slug}/preference-vectors/new` — add preference vector
- `POST /{topic_slug}/preference-vectors` — create preference vector
- `GET /{topic_slug}/preference-vectors/{id}/edit` — edit form
- `POST /{topic_slug}/preference-vectors/{id}` — update
- `POST /{topic_slug}/preference-vectors/{id}/delete` — delete
- `GET /topics` — topic management page (list/create/delete topics)

**Topic dependency:**
```python
async def get_topic(topic_slug: str, db: AsyncSession = Depends(get_db)) -> Topic:
    result = await db.execute(select(Topic).filter(Topic.slug == topic_slug))
    topic = result.scalars().first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic
```

Every route handler adds `topic` and `topic_slug` to the template context so templates can build correct links.

### 3.2 API routes (`app/routes/api.py`)

Add `/{topic_slug}` prefix to all topic-scoped API endpoints:
- `GET /api/{topic_slug}/news` — news for topic
- `GET /api/{topic_slug}/news/search` — search within topic
- `GET /api/{topic_slug}/news/clusters` — clusters for topic
- `GET /api/{topic_slug}/news/umap` — UMAP for topic
- `GET /api/{topic_slug}/news/trending` — trending for topic
- `GET /api/{topic_slug}/news/stats` — stats for topic
- `GET /api/{topic_slug}/news/{id}` — single news item
- `GET /api/{topic_slug}/news/{id}/similar` — similar items
- `GET /api/{topic_slug}/urls` — sources for topic
- `POST /api/{topic_slug}/urls` — add source
- `DELETE /api/{topic_slug}/urls/{id}` — delete source
- `GET /api/{topic_slug}/preference-vectors` — preference vectors for topic
- `POST /api/{topic_slug}/preference-vectors` — create
- `PUT /api/{topic_slug}/preference-vectors/{id}` — update
- `DELETE /api/{topic_slug}/preference-vectors/{id}` — delete

Global (non-topic-scoped) endpoints remain:
- `POST /api/auth/login`
- `GET /api/health`
- `GET /api/topics` (CRUD)

All topic-scoped queries add `.filter(Model.topic_id == topic.id)`.

**Files changed:** `app/routes/web.py`, `app/routes/api.py`

---

## Phase 4: Services — Topic Awareness

### 4.1 FAISS service (`app/services/faiss_service.py`)

Convert from a single global index to **per-topic indexes**:

```python
class FaissService:
    def __init__(self):
        self.indexes: Dict[int, faiss.IndexFlatL2] = {}      # topic_id → index
        self.news_ids: Dict[int, List[int]] = {}               # topic_id → [news_id, ...]
        self.vectors: Dict[int, List[np.ndarray]] = {}         # topic_id → [vector, ...]
        self.last_update: Dict[int, datetime] = {}             # topic_id → datetime
```

Update all methods (`update_index`, `get_clusters`, `get_hierarchical_clusters`, `search_similar`) to take `topic_id` as parameter and operate on the topic-specific index.

### 4.2 Crawler (`app/services/crawler.py`)

- `Crawler.__init__` — unchanged
- `start_crawler()` — for each topic, get its URLs, crawl them, and tag new `NewsItem`s with `topic_id`
- `_process_news_item(title, url, source_url, topic_id)` — add `topic_id` to new `NewsItem`
- `_cleanup_old_news(session)` — cleanup still operates globally (retention by age), no topic scoping needed
- `crawl_url(url_item)` — pass `topic_id` through from the URL's topic association

The crawler loops over all topics and their URLs each cycle.

### 4.3 Embedding service (`app/services/embedding.py`)

- `run_background_tasks()` — update FAISS index and regenerate visualizations **per topic**
- Loop: for each topic → `faiss_service.update_index(db, hours, topic_id)` → `update_visualizations(db, topic_id)`

### 4.4 Visualization service (`app/services/visualization.py`)

- `generate_clusters(db, hours, min_similarity, topic_id)` — filter by topic_id
- `generate_umap_visualization(db, hours, min_similarity, topic_id)` — filter by topic_id
- `update_visualizations(db, topic_id)` — scope to topic

**Files changed:** `app/services/faiss_service.py`, `app/services/crawler.py`, `app/services/embedding.py`, `app/services/visualization.py`, `app/services/embedding_worker.py`

---

## Phase 5: Templates

### 5.1 Update `base.html`

- All nav links get `topic_slug` prefix: `href="/{{ topic_slug }}/"`, `href="/{{ topic_slug }}/news"`, etc.
- Add topic name display in navbar (e.g., "EmBird / Tech News")
- Add topic switcher dropdown in navbar (list all topics, link to each `/{slug}/`)
- When on root `/` (topic list), show simplified nav without topic-specific links

### 5.2 Update all templates

Every template that generates internal links must use `{{ topic_slug }}` prefix:
- `index.html` — links to news items, preference vectors
- `news_list.html` — pagination links, news item links
- `news_detail.html` — back links, related items
- `news_clusters.html` — cluster article links
- `news_umap.html` — visualization article links
- `search.html` — search form action, result links
- `url_form.html` — form actions, back links
- `preference_vectors.html` — CRUD links
- `preference_vector_form.html` — form actions, back links

### 5.3 New template: `topics.html`

Topic list/management page at `/topics`:
- List all topics with name, slug, description, article count
- Create new topic form
- Delete topic button (with confirmation)

**Files changed:** All templates in `app/templates/`

---

## Phase 6: App Startup & Config

### 6.1 `app/main.py`

- On startup, ensure default topic exists (create if missing)
- FAISS initialization: initialize per-topic indexes for all existing topics

### 6.2 `app/config.py`

- Add `DEFAULT_TOPIC_NAME` and `DEFAULT_TOPIC_SLUG` settings (defaults: "Default", "default")
- Add `ENABLE_TOPIC_MANAGEMENT` setting (default: True)

### 6.3 `app/init-scripts/init.sql`

- Add `CREATE TABLE topics`
- Add migration blocks for existing tables (add `topic_id` columns)
- Insert default topic
- Update existing data

**Files changed:** `app/main.py`, `app/config.py`, `app/init-scripts/init.sql`

---

## Implementation Order

1. **Phase 1** — Database & Models (foundation, everything depends on this)
2. **Phase 2** — Topic CRUD & URL Database updates
3. **Phase 4** — Services (FAISS, Crawler, Embedding, Visualization) — topic awareness
4. **Phase 3** — Routes (web + API) — topic-scoped routing
5. **Phase 5** — Templates — update all links
6. **Phase 6** — Startup, config, init.sql

## Key Design Decisions

- **Slug-based routing** (not topic ID) — cleaner URLs, human-readable
- **Per-topic FAISS indexes** — complete isolation, no cross-topic contamination
- **Same URL in multiple topics** — a source like Reuters can appear in both "politics" and "tech" topics; the same article URL may exist in multiple topics
- **Default topic** — existing data migrated to a "default" topic seamlessly; single-topic setups continue to work
- **Topic dependency injection** — a shared FastAPI dependency resolves `topic_slug` to `Topic` object, reused across all routes
- **No cross-topic features** — each topic is fully independent (no global search, no cross-topic clusters)
