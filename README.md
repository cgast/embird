# News Suck

An open-source project for crawling RSS feeds and websites, extracting news content, and storing it with vector embeddings for semantic search.

## Features

- Docker Compose setup for easy local deployment
- Web frontend for managing URLs (RSS feeds and homepages)
- Automated crawler that runs hourly
- Content extraction with title, summary, and timestamps
- Vector embeddings for semantic search using Cohere API
- Duplicate detection with hit-counter tracking
- PostgreSQL vector database for efficient similarity queries

## Architecture

The system consists of three main components:

1. **Web App**: FastAPI backend with Jinja2 templates for the frontend
2. **Crawler Service**: Python service that runs periodically to fetch and process content
3. **Databases**:
   - SQLite for URL management
   - PostgreSQL with pgvector extension for news items and vector embeddings

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Cohere API key (for generating embeddings)

### Installation

#### Clone the repository

```bash
git clone https://github.com/cgast/news-suck.git
cd news-suckr
```

#### Create a `.env` file with your Cohere API key

```bash
cp .env.example .env
# Edit .env and add your COHERE_API_KEY
```

#### Start the application

```bash
docker-compose up -d
```

#### Access the web interface at [http://localhost:8000](http://localhost:8000)

### Usage

1. Add URLs to crawl using the web interface
2. The crawler will automatically fetch content from these URLs hourly
3. View and search the collected news items

## Development

### Project Structure

- **webapp**: FastAPI application for the web interface
- **crawler**: Python service for crawling and processing content
- **init-scripts**: Database initialization scripts

### Local Development

To run the services individually for development:

#### Set up a virtual environment and install dependencies

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r webapp/requirements.txt
pip install -r crawler/requirements.txt
```

#### Start the web app

```bash
cd webapp
uvicorn app.main:app --reload
```

#### Run the crawler manually

```bash
cd crawler
python -m app.main
```

## Configuration

Configuration options can be set via environment variables:

- `DATABASE_URL`: PostgreSQL connection string
- `SQLITE_PATH`: Path to the SQLite database file
- `COHERE_API_KEY`: API key for Cohere embeddings
- `CRAWLER_INTERVAL`: Interval between crawls in seconds (default: 3600)

## License

This project is open source and available under the MIT License.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
