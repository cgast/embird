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

# Copy application code
COPY app /app/app
COPY shared /app/shared

USER appuser

# Set environment variable for service type (default to webapp)
ENV SERVICE_TYPE=webapp
ENV PORT=8000

# Use entrypoint script to determine which service to run
COPY entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
