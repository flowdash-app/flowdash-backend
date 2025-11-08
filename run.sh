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

echo -e "${GREEN}Starting FlowDash Backend...${NC}"
echo -e "${BLUE}API will be available at: http://localhost:8000${NC}"
echo -e "${BLUE}API Docs: http://localhost:8000/docs${NC}"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

