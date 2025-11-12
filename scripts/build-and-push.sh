#!/bin/bash

# Build and Push Docker Image with Version Bumping
# This script increments the patch version, builds the Docker image,
# and pushes it to GitHub Container Registry with both version and latest tags.

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VERSION_FILE="$PROJECT_ROOT/VERSION"

echo -e "${BLUE}🚀 FlowDash Backend - Build and Push Docker Image${NC}"
echo ""

# Check if VERSION file exists
if [ ! -f "$VERSION_FILE" ]; then
    echo -e "${RED}❌ Error: VERSION file not found at $VERSION_FILE${NC}"
    exit 1
fi

# Read current version
CURRENT_VERSION=$(cat "$VERSION_FILE" | tr -d '[:space:]')
echo -e "${YELLOW}📦 Current version: ${CURRENT_VERSION}${NC}"

# Parse version components
IFS='.' read -ra VERSION_PARTS <<< "$CURRENT_VERSION"
if [ ${#VERSION_PARTS[@]} -ne 3 ]; then
    echo -e "${RED}❌ Error: Invalid version format. Expected MAJOR.MINOR.PATCH (e.g., 0.0.1)${NC}"
    exit 1
fi

MAJOR=${VERSION_PARTS[0]}
MINOR=${VERSION_PARTS[1]}
PATCH=${VERSION_PARTS[2]}

# Increment patch version
NEW_PATCH=$((PATCH + 1))
NEW_VERSION="${MAJOR}.${MINOR}.${NEW_PATCH}"

echo -e "${GREEN}✨ New version: ${NEW_VERSION}${NC}"
echo ""

# Update VERSION file
echo "$NEW_VERSION" > "$VERSION_FILE"
echo -e "${GREEN}✅ Updated VERSION file${NC}"

# Get GitHub repository info
# Try to get from git remote, fallback to environment variable or prompt
if [ -d "$PROJECT_ROOT/.git" ]; then
    GIT_REMOTE=$(git -C "$PROJECT_ROOT" remote get-url origin 2>/dev/null || echo "")
    if [[ "$GIT_REMOTE" =~ github.com[:/]([^/]+)/([^/]+)(\.git)?$ ]]; then
        GITHUB_OWNER="${BASH_REMATCH[1]}"
        GITHUB_REPO="${BASH_REMATCH[2]%.git}"
        GITHUB_REPOSITORY="${GITHUB_OWNER}/${GITHUB_REPO}"
    fi
fi

# Use environment variable if available
if [ -z "$GITHUB_REPOSITORY" ] && [ -n "$GITHUB_REPO" ]; then
    GITHUB_REPOSITORY="$GITHUB_REPO"
fi

# Prompt if still not set
if [ -z "$GITHUB_REPOSITORY" ]; then
    echo -e "${YELLOW}⚠️  Could not detect GitHub repository automatically${NC}"
    read -p "Enter GitHub repository (owner/repo, e.g., kono/flowdash-backend): " GITHUB_REPOSITORY
fi

if [ -z "$GITHUB_REPOSITORY" ]; then
    echo -e "${RED}❌ Error: GitHub repository is required${NC}"
    exit 1
fi

IMAGE_NAME="ghcr.io/${GITHUB_REPOSITORY}"
VERSION_TAG="${IMAGE_NAME}:${NEW_VERSION}"
LATEST_TAG="${IMAGE_NAME}:latest"

echo ""
echo -e "${BLUE}🐳 Building Docker image...${NC}"
echo -e "   Image: ${IMAGE_NAME}"
echo -e "   Tags: ${VERSION_TAG}, ${LATEST_TAG}"
echo ""

# Build Docker image
cd "$PROJECT_ROOT"
docker build -t "$VERSION_TAG" -t "$LATEST_TAG" .

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Docker build failed${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ Docker image built successfully${NC}"
echo ""

# Check if user wants to push
read -p "Push image to GitHub Container Registry? (y/N): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}⏭️  Skipping push. Image built locally with tags:${NC}"
    echo -e "   ${VERSION_TAG}"
    echo -e "   ${LATEST_TAG}"
    exit 0
fi

# Check if logged in to ghcr.io
if ! docker info | grep -q "ghcr.io"; then
    echo -e "${YELLOW}⚠️  Not logged in to GitHub Container Registry${NC}"
    echo -e "${BLUE}💡 To login, run:${NC}"
    echo -e "   echo \$GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin"
    echo ""
    read -p "Do you want to login now? (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "Enter your GitHub username: " GITHUB_USERNAME
        echo -n "Enter your GitHub Personal Access Token (with write:packages permission): "
        read -s GITHUB_TOKEN
        echo ""
        echo "$GITHUB_TOKEN" | docker login ghcr.io -u "$GITHUB_USERNAME" --password-stdin
        if [ $? -ne 0 ]; then
            echo -e "${RED}❌ Login failed${NC}"
            exit 1
        fi
    else
        echo -e "${YELLOW}⏭️  Skipping push. Please login manually and push later.${NC}"
        exit 0
    fi
fi

echo ""
echo -e "${BLUE}📤 Pushing Docker image...${NC}"

# Push version tag
echo -e "${BLUE}   Pushing ${VERSION_TAG}...${NC}"
docker push "$VERSION_TAG"

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to push version tag${NC}"
    exit 1
fi

# Push latest tag
echo -e "${BLUE}   Pushing ${LATEST_TAG}...${NC}"
docker push "$LATEST_TAG"

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to push latest tag${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ Successfully pushed Docker image!${NC}"
echo ""
echo -e "${GREEN}📋 Summary:${NC}"
echo -e "   Version bumped: ${CURRENT_VERSION} → ${NEW_VERSION}"
echo -e "   Image: ${IMAGE_NAME}"
echo -e "   Tags pushed:"
echo -e "     - ${VERSION_TAG}"
echo -e "     - ${LATEST_TAG}"
echo ""

