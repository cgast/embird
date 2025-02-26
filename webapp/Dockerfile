FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create appuser before setting up directories
RUN adduser --disabled-password --gecos '' appuser

# Create SQLite data directory and set permissions
RUN mkdir -p /app/data && \
    chown -R appuser:appuser /app/data

# Copy application
COPY app /app/app

USER appuser

# Run the application
EXPOSE 8000
CMD ["sh", "-c", "PYTHONPATH=/app uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
