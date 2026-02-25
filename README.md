<center>
  <img src="app/static/img/embird-logo-bird-v2.png" alt="EmBird logo" width="252" height="252" style="display: block; margin: 20px 0;">
</center>

# EmBird

An open-source project for crawling RSS feeds and websites, extracting news content and storing it with vector embeddings for semantic search - to give you a bird's eye view on your news.

## Features

- Docker Compose setup for easy local deployment
- Web frontend for managing URLs (RSS feeds and homepages)
- Automated crawler that runs hourly
- Content extraction with title, summary, and timestamps
- Vector embeddings for semantic search using Cohere API
- Duplicate detection with hit-counter tracking
- FAISS-powered vector similarity search for efficient news clustering
- Interactive visualizations:
  - UMAP dimensionality reduction for exploring news relationships
  - Clustered news articles with similarity scores
  - Time-based filtering for both clusters and visualizations

## Architecture

The system consists of five main components:

1. **Frontend**: Modern Vue.js + Vite application with responsive design and dark/light theme
2. **Web App**: FastAPI backend providing REST API endpoints
3. **Crawler Service**: Python service that runs periodically to fetch and process content
4. **Embedding Worker**: Dedicated service for managing vector embeddings and similarity computations
5. **Databases**:
   - PostgreSQL with pgvector extension for news items and metadata
   - FAISS for high-performance vector similarity search and clustering

### Vector Search Architecture

The system uses FAISS (Facebook AI Similarity Search) for efficient vector operations:
- In-memory index for fast similarity searches
- L2 distance-based clustering with cosine similarity
- Automatic index updates for recent news items
- Transitive clustering for finding related news groups

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Cohere API key (for generating embeddings)

### Quick Start with Docker Compose

#### 1. Clone the repository

```bash
git clone https://github.com/cgast/embird.git
cd embird
```

#### 2. Create a `.env` file with your Cohere API key

```bash
cp .env.example .env
# Edit .env and add your COHERE_API_KEY
```

#### 3. Choose your deployment mode

**For Local Development (with hot-reload):**

```bash
docker compose up -d
```

This uses `docker-compose.override.yml` automatically, providing:
- Frontend dev server with hot-reload on port 5173
- Backend API on port 8000
- Source code mounted for live updates

Access the application at:
- Frontend: [http://localhost:5173](http://localhost:5173)
- Backend API: [http://localhost:8000/api](http://localhost:8000/api)

**For Production:**

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

This provides:
- Optimized Vue build served by nginx on port 80
- Backend API proxied through nginx
- No source code mounting, secure setup

Access the application at:
- Application: [http://localhost](http://localhost)

### Usage

1. Add URLs to crawl using the web interface
2. The crawler will automatically fetch content from these URLs hourly
3. View and search the collected news items
4. Explore news clusters to find related articles
5. Use the UMAP visualization to discover content relationships

## Development

### Project Structure

```
embird/
├── frontend/               # Vue.js frontend application
│   ├── src/
│   │   ├── components/    # Reusable Vue components
│   │   ├── views/         # Page components
│   │   ├── App.vue        # Root component
│   │   ├── main.js        # Entry point
│   │   └── style.css      # Global styles
│   ├── Dockerfile         # Multi-stage build
│   └── nginx.conf         # Production nginx config
├── app/                   # Backend application
│   ├── models/            # Database models
│   ├── routes/            # API and web routes
│   ├── services/          # Core services
│   │   ├── crawler.py     # URL crawling and content extraction
│   │   ├── embedding_worker.py  # Vector embedding service
│   │   ├── faiss_service.py    # Vector similarity operations
│   │   └── visualization.py    # UMAP and clustering visualizations
│   └── static/            # Legacy static files (for old templates)
├── docker-compose.yml           # Base compose file (production)
├── docker-compose.override.yml  # Development overrides (auto-applied)
└── docker-compose.prod.yml      # Production-specific config
```

### Docker Compose Development Workflow

The recommended way to develop is using Docker Compose with hot-reload:

```bash
# Start all services in development mode
docker compose up -d

# View logs
docker compose logs -f frontend
docker compose logs -f webapp

# Rebuild after dependency changes
docker compose build frontend
docker compose up -d frontend

# Stop all services
docker compose down
```

**What you get:**

- Frontend hot-reload: Edit Vue files and see changes instantly
- Backend auto-reload: Changes to Python files restart the server
- Full database and services running
- No need to install Node.js or Python locally

### Manual Development (without Docker)

If you prefer to run services individually:

**Backend:**

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

**Note:** You'll still need PostgreSQL and other services running (can use Docker for just the database).

## Configuration

Configuration options can be set via environment variables:

- `DATABASE_URL`: PostgreSQL connection string
- `COHERE_API_KEY`: API key for Cohere embeddings
- `CRAWLER_INTERVAL`: Interval between crawls in seconds (default: 3600)
- `MAX_CONCURRENT_REQUESTS`: Maximum number of concurrent requests (default: 5)
- `REQUEST_TIMEOUT`: Request timeout in seconds (default: 30)
- `USER_AGENT`: Custom user agent string for the crawler
- `NEWS_RETENTION_DAYS`: Number of days to keep news items (default: 30)
- `NEWS_MAX_ITEMS`: Maximum number of news items to keep (default: 10000)
- `VECTOR_DIMENSIONS`: Dimension of embedding vectors (default: 1024)
- `VISUALIZATION_TIME_RANGE`: Hours of news to include in visualizations (default: 48)
- `VISUALIZATION_SIMILARITY`: Similarity threshold for clustering (default: 0.55)
- `FAISS_UPDATE_INTERVAL`: Interval between FAISS index updates in seconds (default: 3600)
- `FAISS_MAX_VECTORS`: Maximum number of vectors to keep in FAISS index (default: 10000)
- `DEBUG`: Enable debug mode (default: False)
- `ENABLE_URL_MANAGEMENT`: Enable Sources (URL) management mode, helps to prevent destruction of the demo site (default: True)
- `ENABLE_PREFERENCE_MANAGEMENT`: Enable Section (Preference-Vector) management mode, helps to prevent destruction of the demo site (default: True)
- `EMBED_TITLE_ONLY`: Use only the title for generating embeddings instead of title + summary (default: True)

## License

This project is open source and available under the MIT License.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
