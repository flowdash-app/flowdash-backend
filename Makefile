.PHONY: build-push docker-build docker-push help

help: ## Show this help message
	@echo "FlowDash Backend - Available Commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

build-push: ## Build and push Docker image with version bumping
	@bash scripts/build-and-push.sh

docker-build: ## Build Docker image only (no version bump, no push)
	@docker build -t flowdash-backend:local .

docker-push: ## Push existing Docker image (requires manual tagging first)
	@echo "Usage: docker push <image:tag>"
	@echo "Example: docker push ghcr.io/owner/flowdash-backend:0.0.1"

