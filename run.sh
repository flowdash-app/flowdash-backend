#!/bin/bash

# FlowDash Backend Run Script
# Quick script to run the development server

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check if venv exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Running setup...${NC}"
    ./setup.sh
fi

# Activate virtual environment
source venv/bin/activate

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠ Warning: .env file not found!${NC}"
    echo "The application may not work without proper environment variables."
    echo ""
fi

# Check if Docker is available
if command -v docker &> /dev/null && docker compose version &> /dev/null; then
    echo -e "${BLUE}Starting Docker Compose dev services...${NC}"
    docker compose -f docker-compose.dev.yml up -d
    
    # Wait for PostgreSQL to be ready
    echo -e "${BLUE}Waiting for PostgreSQL to be ready...${NC}"
    timeout=30
    counter=0
    while ! docker compose -f docker-compose.dev.yml exec -T postgres pg_isready -U flowdash &> /dev/null; do
        if [ $counter -ge $timeout ]; then
            echo -e "${YELLOW}⚠ Warning: PostgreSQL did not become ready in time${NC}"
            break
        fi
        sleep 1
        counter=$((counter + 1))
    done
    
    if [ $counter -lt $timeout ]; then
        echo -e "${GREEN}✓ PostgreSQL is ready${NC}"
        
        # Run database migrations
        echo -e "${BLUE}Running database migrations...${NC}"
        alembic upgrade head
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ Migrations completed${NC}"
        else
            echo -e "${YELLOW}⚠ Warning: Migration failed${NC}"
            echo "You may need to check your database connection or migration files."
        fi
    fi
    echo ""
    
    # Set up cleanup function to stop docker compose on exit
    cleanup() {
        echo ""
        echo -e "${YELLOW}Stopping Docker Compose dev services...${NC}"
        docker compose -f docker-compose.dev.yml down
    }
    trap cleanup EXIT
else
    echo -e "${YELLOW}⚠ Warning: Docker/Docker Compose not found. Skipping dev services startup.${NC}"
    echo "Make sure PostgreSQL is running if you need database access."
    echo ""
fi

echo -e "${GREEN}Starting FlowDash Backend...${NC}"
echo -e "${BLUE}API will be available at: http://localhost:8000${NC}"
echo -e "${BLUE}API Docs: http://localhost:8000/docs${NC}"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

