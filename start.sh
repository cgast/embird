#!/run/current-system/sw/bin/bash

# Load environment variables from .env.local
if [ -f .env.local ]; then
    export $(cat .env.local | grep -v '^#' | xargs)
else
    echo "Warning: .env.local file not found"
    exit 1
fi

# Function to kill processes on script exit
cleanup() {
    echo "Stopping services..."
    kill $CRAWLER_PID $WEBAPP_PID 2>/dev/null
    exit 0
}

# Set up trap for Ctrl+C
trap cleanup SIGINT SIGTERM

# Start crawler service
echo "Starting crawler..."
cd crawler
source venv/bin/activate
PYTHONPATH=. python app/main.py &
CRAWLER_PID=$!
deactivate
cd ..

# Start webapp service with uvicorn
echo "Starting webapp..."
cd webapp
source venv/bin/activate
PYTHONPATH=. uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
WEBAPP_PID=$!
deactivate
cd ..

echo "Services started! Press Ctrl+C to stop all services"
echo "Web interface available at http://localhost:8000"

# Wait for Ctrl+C
wait $CRAWLER_PID $WEBAPP_PID
