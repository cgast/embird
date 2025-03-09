#!/bin/sh

# Set Python path to include app and shared directories
export PYTHONPATH=/app:/app/shared

if [ "$SERVICE_TYPE" = "crawler" ]; then
    echo "Starting crawler service..."
    python -m app.main
else
    echo "Starting web service..."
    uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
fi
