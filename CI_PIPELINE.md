# CI/CD Pipeline Documentation

This document describes the CI/CD pipeline setup for the FlowDash Backend project.

## Overview

The CI pipeline is configured to run on every push to the `main` branch and on all pull requests. It consists of three main jobs:

1. **Lint** - Code quality checks
2. **Test** - Unit and integration tests
3. **Build** - Docker image build verification

## Pipeline Jobs

### 1. Lint Job

Runs code quality checks using:
- **Ruff**: Fast Python linter for catching errors and code smells
- **Black**: Code formatter to ensure consistent code style

**Configuration**: See `pyproject.toml` for linting rules

**Running locally**:
```bash
# Run ruff
ruff check app/ tests/ --select E,F,W,I

# Run black
black --check app/ tests/

# Auto-fix issues
ruff check app/ tests/ --fix
black app/ tests/
```

### 2. Test Job

Runs comprehensive test suite with:
- PostgreSQL database service for integration tests
- Redis cache service for caching tests
- Unit tests with mocked dependencies
- Integration tests with real database and Redis
- Code coverage reporting

**Test Types**:
- **Unit Tests**: Fast tests with mocked dependencies (marked as default)
- **Integration Tests**: Tests with real PostgreSQL and Redis (marked with `@pytest.mark.integration`)

**Running locally**:

```bash
# Install dependencies
pip install -r requirements.txt

# Run unit tests only (no database required)
pytest tests/ -v -m "not integration"

# Run all tests (requires PostgreSQL and Redis)
docker compose -f docker-compose.dev.yml up -d
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=app --cov-report=term-missing
```

**Test Database Setup**:
- Uses PostgreSQL 16
- Database: `test_db`
- User: `test`
- Password: `test`
- Automatically creates and tears down tables for each test session

**Test Redis Setup**:
- Uses Redis 7
- Database: 1 (separate from production DB 0)
- No password for test environment
- Automatically flushes data after each test

### 3. Build Job

Verifies that the Docker image can be built successfully:
- Uses Docker Buildx for efficient builds
- Caches layers using GitHub Actions cache
- Only runs if lint and test jobs pass

**Running locally**:
```bash
# Build Docker image
docker build -t flowdash-backend:test .

# Or using docker-compose
docker compose -f docker-compose.prod.yml build
```

## Environment Variables for Testing

The following environment variables are used in tests (configured in `tests/conftest.py`):

```bash
DATABASE_URL=postgresql://test:test@localhost:5432/test_db
REDIS_URL=redis://localhost:6379/1
REDIS_PASSWORD=""
FIREBASE_PROJECT_ID=test-project
FIREBASE_CREDENTIALS_PATH=/tmp/test-creds.json
SECRET_KEY=test-secret-key-for-testing-only
ENCRYPTION_KEY=test-encryption-key-32-bytes!!
N8N_API_CACHE_ENABLED=false
RATE_LIMIT_ENABLED=false
```

## Adding New Tests

### Unit Tests

Create test files in `tests/` directory with the prefix `test_`:

```python
import pytest
from unittest.mock import MagicMock, patch

def test_example():
    """Test description"""
    # Test implementation
    assert True
```

### Integration Tests

Mark integration tests with `@pytest.mark.integration`:

```python
import pytest

@pytest.mark.integration
class TestDatabaseIntegration:
    def test_create_user(self, db_session):
        """Test with real database"""
        # Test implementation
        pass
```

## Test Fixtures

Available fixtures (defined in `tests/conftest.py`):

- `db_engine`: Database engine (session-scoped)
- `db_session`: Database session (function-scoped, auto-rollback)
- `redis_client`: Redis client (function-scoped, auto-flush)
- `mock_firebase_admin`: Mocked Firebase Admin SDK (auto-used)

## CI Pipeline Configuration

The pipeline is defined in `.github/workflows/ci.yml`.

**Key Features**:
- Parallel execution of lint and test jobs
- Service containers for PostgreSQL and Redis
- Coverage reporting with Codecov
- Build verification after successful tests
- Caching of pip dependencies and Docker layers

## Troubleshooting

### Tests fail locally but pass in CI

- Ensure you have PostgreSQL and Redis running:
  ```bash
  docker compose -f docker-compose.dev.yml up -d
  ```

### Linting fails

- Run auto-fix commands:
  ```bash
  ruff check app/ tests/ --fix
  black app/ tests/
  ```

### Integration tests fail

- Check that database and Redis services are running
- Verify connection parameters in environment variables
- Look at service logs:
  ```bash
  docker compose -f docker-compose.dev.yml logs postgres redis
  ```

## Contributing

Before submitting a PR:

1. Run linting: `ruff check app/ tests/ --fix && black app/ tests/`
2. Run tests: `pytest tests/ -v`
3. Ensure all tests pass
4. Check coverage if adding new features

The CI pipeline will automatically run on your PR and provide feedback.
