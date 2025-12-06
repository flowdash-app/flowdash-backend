#!/bin/bash

# FlowDash Backend Setup Script
# This script sets up the Python virtual environment and installs dependencies

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}FlowDash Backend Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check Python version
echo -e "${YELLOW}Checking Python version...${NC}"
if command -v python3.12 &> /dev/null; then
    PYTHON_CMD="python3.12"
    PYTHON_VERSION=$(python3.12 --version)
    echo -e "${GREEN}✓ Found: $PYTHON_VERSION${NC}"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    PYTHON_VERSION=$(python3 --version)
    echo -e "${YELLOW}⚠ Using $PYTHON_VERSION (Python 3.12 recommended)${NC}"
else
    echo -e "${RED}✗ Python 3 not found. Please install Python 3.12 or later.${NC}"
    exit 1
fi

# Check if venv already exists
if [ -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment already exists.${NC}"
    read -p "Do you want to recreate it? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Removing existing virtual environment...${NC}"
        rm -rf venv
    else
        echo -e "${GREEN}Using existing virtual environment.${NC}"
    fi
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    
    # Try to create venv normally first
    if $PYTHON_CMD -m venv venv 2>/dev/null; then
        echo -e "${GREEN}✓ Virtual environment created successfully${NC}"
    else
        # If that fails (e.g., missing distutils), create without pip and bootstrap it
        echo -e "${YELLOW}Creating venv without pip (will bootstrap pip manually)...${NC}"
        $PYTHON_CMD -m venv --without-pip venv
        
        echo -e "${YELLOW}Bootstrapping pip...${NC}"
        if command -v curl &> /dev/null; then
            curl -sS https://bootstrap.pypa.io/get-pip.py | venv/bin/$PYTHON_CMD
        else
            echo -e "${RED}✗ curl not found. Please install curl or pip manually.${NC}"
            exit 1
        fi
        echo -e "${GREEN}✓ Pip installed successfully${NC}"
    fi
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# Upgrade pip
echo -e "${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip --quiet
echo -e "${GREEN}✓ Pip upgraded${NC}"

# Install requirements
echo -e "${YELLOW}Installing dependencies from requirements.txt...${NC}"
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo -e "${GREEN}✓ Dependencies installed successfully${NC}"
else
    echo -e "${RED}✗ requirements.txt not found!${NC}"
    exit 1
fi

# Check for .env file
echo ""
echo -e "${YELLOW}Checking environment configuration...${NC}"
if [ ! -f ".env" ]; then
    echo -e "${RED}⚠ .env file not found!${NC}"
    echo -e "${YELLOW}You need to create a .env file with the following variables:${NC}"
    echo ""
    echo "Required variables:"
    echo "  - DATABASE_URL"
    echo "  - FIREBASE_PROJECT_ID"
    echo "  - FIREBASE_CREDENTIALS_PATH"
    echo "  - SECRET_KEY"
    echo "  - ENCRYPTION_KEY"
    echo ""
    echo -e "${YELLOW}Generate keys with:${NC}"
    echo "  SECRET_KEY: python3 -c \"import secrets; print(secrets.token_urlsafe(32))\""
    echo "  ENCRYPTION_KEY: python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    echo ""
else
    echo -e "${GREEN}✓ .env file found${NC}"
fi

# Check for database
echo ""
echo -e "${YELLOW}Database setup:${NC}"
echo "  To start PostgreSQL with Docker, run:"
echo -e "  ${BLUE}docker compose -f docker-compose.dev.yml up -d${NC}"
echo ""
echo "  Or use your own PostgreSQL instance and update DATABASE_URL in .env"
echo ""

# Success message
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Setup completed successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}To run the development server:${NC}"
echo ""
echo -e "  ${GREEN}1. Activate the virtual environment:${NC}"
echo -e "     ${YELLOW}source venv/bin/activate${NC}"
echo ""
echo -e "  ${GREEN}2. Run database migrations (if needed):${NC}"
echo -e "     ${YELLOW}alembic upgrade heads${NC}"
echo ""
echo -e "  ${GREEN}3. Start the development server:${NC}"
echo -e "     ${YELLOW}uvicorn app.main:app --reload --host 0.0.0.0 --port 8000${NC}"
echo ""
echo -e "${BLUE}The API will be available at:${NC}"
echo "  - API: http://localhost:8000"
echo "  - API Docs: http://localhost:8000/docs"
echo "  - Health Check: http://localhost:8000/health"
echo ""

