"""
Pytest configuration for testing
"""

import os
import pytest

# Set up environment variables for testing before any imports
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test_db"
os.environ["FIREBASE_PROJECT_ID"] = "test-project"
os.environ["FIREBASE_CREDENTIALS_PATH"] = "/tmp/test-creds.json"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["ENCRYPTION_KEY"] = "test-encryption-key-32-bytes!!"
os.environ["N8N_API_CACHE_ENABLED"] = "false"
os.environ["RATE_LIMIT_ENABLED"] = "false"


@pytest.fixture(autouse=True)
def mock_firebase_admin(monkeypatch):
    """Mock Firebase Admin SDK to avoid initialization issues in tests"""
    from unittest.mock import MagicMock

    mock_auth = MagicMock()
    monkeypatch.setattr("firebase_admin.auth", mock_auth)

    yield mock_auth
