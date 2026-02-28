#!/bin/bash

# Start DeepChat (Development Mode)

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting DeepChat (DEV MODE)...${NC}"
echo ""

# Load environment variables from .env file if it exists
if [ -f ".env" ]; then
    echo -e "${YELLOW}Loading configuration from .env file...${NC}"
    export $(grep -v '^#' .env | xargs)
    echo ""
fi

# Store PIDs for cleanup
PIDS=()

cleanup() {
    echo ""
    echo -e "${YELLOW}Stopping all servers...${NC}"
    for pid in "${PIDS[@]}"; do
        kill $pid 2>/dev/null
    done
    # Kill any remaining python/node processes from this session
    pkill -P $$ 2>/dev/null
    echo -e "${GREEN}All servers stopped.${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start Python backend
echo -e "${YELLOW}Starting API server on port 8000...${NC}"
source venv/bin/activate
python app.py &
PIDS+=($!)

# Wait a moment for the backend to start
sleep 2

# Start Vite dev server
echo -e "${YELLOW}Starting Vite dev server on port 5173...${NC}"
cd frontend && pnpm run dev &
PIDS+=($!)
cd ..

echo ""
echo -e "${GREEN}All servers are running...${NC}"
echo -e "${CYAN}- API: http://localhost:8000${NC}"
echo -e "${CYAN}- Frontend: http://localhost:5173${NC}"
echo ""
echo -e "${RED}Press Ctrl+C to stop all servers...${NC}"

# Wait for all background processes
wait
