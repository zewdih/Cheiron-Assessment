#!/bin/bash
# Start both backend and frontend for Cheiron

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Check .env exists
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "Error: .env file not found. Copy .env.example to .env and add your OPENAI_API_KEY"
    exit 1
fi

# Check Python dependencies
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "Installing Python dependencies..."
    pip install -r "$PROJECT_DIR/requirements.txt"
fi

# Check Node dependencies
if [ ! -d "$PROJECT_DIR/frontend/node_modules" ]; then
    echo "Installing frontend dependencies..."
    cd "$PROJECT_DIR/frontend" && npm install && cd "$PROJECT_DIR"
fi

# Kill any existing processes on ports 8000 and 5173
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
lsof -ti:5173 2>/dev/null | xargs kill -9 2>/dev/null || true

echo ""
echo "Starting Cheiron..."
echo "  Backend:  http://localhost:8000  (API docs: http://localhost:8000/docs)"
echo "  Frontend: http://localhost:5173"
echo ""

# Start backend
cd "$PROJECT_DIR"
uvicorn cheiron.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Start frontend
cd "$PROJECT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

# Trap to kill both on exit
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM

echo "Press Ctrl+C to stop both servers."
wait