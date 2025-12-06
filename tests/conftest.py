"""
Pytest configuration for testing
"""

import json
import os
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Create mock Firebase credentials before any imports
credentials_path = "/tmp/test-creds.json"
if not os.path.exists(credentials_path):
    os.makedirs(os.path.dirname(credentials_path), exist_ok=True)
    with open(credentials_path, "w") as f:
        json.dump({
            "type": "service_account",
            "project_id": "test-project",
            "private_key_id": "test-key-id",
            "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7W8jYbN3qCyYO\nwHjN8C7uxHvK7KqDfVJ5kLpY8xAqDgZ0mB6E1Z8vxOV7W4QGqN8YQG5e0VJ0nQYP\nEuWxN7iT0K7LMcJJ1fN7YH2KjQ1rE5wN8nLzOXF0xQKBgHm3R5Y8yHjF3wN7fP5Y\nxKBgQDNiL0Y8N7F5xB3wF8yHjN7L5F8N3Y8wB7H5F8xN7K8wH5N7F8xY3wB8N7F5\nxH3K8wN7F5xB3wH8N7F5xH3K8wN7F5xB3wF8N7F5xH3K8wN7F5xB3AgMBAAECggEA\nAWJgFVPjJPh9P8BxBqN7vLNe0Fp8YH8DGz1sKBW0JrH5F8xN7K8wH5N7F8xY3wB8\nN7F5xH3K8wN7F5xB3wH8N7F5xH3K8wN7F5xB3wF8N7F5xH3K8wN7F5xB3QKBgQDN\niL0Y8N7F5xB3wF8yHjN7L5F8N3Y8wB7H5F8xN7K8wH5N7F8xY3wB8N7F5xH3K8wN\n7F5xB3wH8N7F5xH3K8wN7F5xB3wF8N7F5xH3K8wN7F5xB3QKBgQC7W8jYbN3qCyYO\nwHjN8C7uxHvK7KqDfVJ5kLpY8xAqDgZ0mB6E1Z8vxOV7W4QGqN8YQG5e0VJ0nQYP\nEuWxN7iT0K7LMcJJ1fN7YH2KjQ1rE5wN8nLzOXF0xQKBgHm3R5Y8yHjF3wN7fP5Y\nxKBgQDNiL0Y8N7F5xB3wF8yHjN7L5F8N3Y8wB7H5F8xN7K8wH5N7F8xY3wB8N7F5\nxH3K8wN7F5xB3wH8N7F5xH3K8wN7F5xB3wF8N7F5xH3K8wN7F5xB3\n-----END PRIVATE KEY-----\n",
            "client_email": "test@test-project.iam.gserviceaccount.com",
            "client_id": "123456789",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/test%40test-project.iam.gserviceaccount.com"
        }, f)

# Set up environment variables for testing before any imports
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test_db"
os.environ["FIREBASE_PROJECT_ID"] = "test-project"
os.environ["FIREBASE_CREDENTIALS_PATH"] = credentials_path
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["ENCRYPTION_KEY"] = "test-encryption-key-32-bytes!!"
os.environ["N8N_API_CACHE_ENABLED"] = "false"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"
os.environ["REDIS_PASSWORD"] = ""


# Mock Firebase Admin before it's imported
@pytest.fixture(autouse=True)
def mock_firebase_admin(monkeypatch):
    """Mock Firebase Admin SDK to avoid initialization issues in tests"""
    # Mock firebase_admin.credentials
    mock_credentials = MagicMock()
    mock_cred = MagicMock()
    mock_credentials.Certificate.return_value = mock_cred
    monkeypatch.setattr("firebase_admin.credentials.Certificate", mock_credentials.Certificate)

    # Mock firebase_admin.initialize_app
    mock_init = MagicMock()
    monkeypatch.setattr("firebase_admin.initialize_app", mock_init)

    # Mock firebase_admin.auth
    mock_auth = MagicMock()
    monkeypatch.setattr("firebase_admin.auth", mock_auth)

    # Mock firestore client
    mock_firestore = MagicMock()
    monkeypatch.setattr("firebase_admin.firestore.client", mock_firestore)

    yield mock_auth


@pytest.fixture(scope="session")
def db_engine():
    """Create database engine for testing"""
    # Import after env vars are set
    from app.core.database import Base

    database_url = os.environ.get("DATABASE_URL")
    engine = create_engine(database_url)

    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)

        yield engine

        # Drop all tables after tests
        Base.metadata.drop_all(bind=engine)
    except Exception:
        # If database not available, yield None
        yield None


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create a new database session for a test"""
    if db_engine is None:
        pytest.skip("Database not available")

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestingSessionLocal()

    yield session

    # Rollback any changes and close session
    session.rollback()
    session.close()


@pytest.fixture(scope="function")
def redis_client():
    """Create Redis client for testing"""
    import redis

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
    redis_password = os.environ.get("REDIS_PASSWORD", "")

    try:
        client = redis.from_url(
            redis_url,
            password=redis_password if redis_password else None,
            decode_responses=False,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        # Test connection
        client.ping()

        yield client

        # Clean up test data
        client.flushdb()
        client.close()
    except Exception:
        # Return None if Redis is not available
        yield None
