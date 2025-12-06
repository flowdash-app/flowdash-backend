"""
Tests for API endpoints
"""

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def client():
    """Create test client with mocked Firebase"""
    with patch('firebase_admin.credentials.Certificate') as mock_cert, \
         patch('firebase_admin.initialize_app') as mock_init, \
         patch('firebase_admin.auth') as mock_auth:
        
        # Now safe to import after mocking
        from fastapi.testclient import TestClient
        from app.main import app
        
        return TestClient(app)


@pytest.fixture
def mock_current_user():
    """Mock current user for authenticated requests"""
    return {
        "uid": "test_user_123",
        "email": "test@example.com",
        "token": {"uid": "test_user_123"}
    }


class TestHealthEndpoint:
    """Test health check endpoint"""

    def test_health_check(self, client):
        """Test health check returns 200"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestWorkflowEndpoints:
    """Test workflow-related endpoints"""

    @patch("app.api.v1.routes.workflows.get_current_user")
    def test_get_workflows_requires_auth(self, mock_get_user, client):
        """Test that workflows endpoint requires authentication"""
        # Mock authentication to raise exception
        from fastapi import HTTPException
        mock_get_user.side_effect = HTTPException(status_code=401, detail="Unauthorized")

        response = client.get("/api/v1/workflows?instance_id=test_instance")
        
        # Should fail without proper auth
        assert response.status_code == 401


class TestInstanceEndpoints:
    """Test instance-related endpoints"""

    @patch("app.api.v1.routes.instances.get_current_user")
    def test_list_instances_requires_auth(self, mock_get_user, client):
        """Test that listing instances requires authentication"""
        # Mock authentication failure
        from fastapi import HTTPException
        mock_get_user.side_effect = HTTPException(status_code=401, detail="Unauthorized")

        response = client.get("/api/v1/instances")
        
        # Should fail without proper auth
        assert response.status_code == 401
