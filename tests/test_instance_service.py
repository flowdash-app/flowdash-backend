"""
Tests for InstanceService
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.services.instance_service import InstanceService
from app.models.n8n_instance import N8NInstance
from app.models.user import User


@pytest.fixture
def mock_db():
    """Create a mock database session"""
    return MagicMock(spec=Session)


@pytest.fixture
def mock_user():
    """Create a mock user"""
    user = MagicMock(spec=User)
    user.id = "test_user_123"
    user.email = "test@example.com"
    user.plan_tier = "free"
    user.is_tester = False
    return user


@pytest.fixture
def mock_instance():
    """Create a mock n8n instance"""
    instance = MagicMock(spec=N8NInstance)
    instance.id = "instance_123"
    instance.user_id = "test_user_123"
    instance.name = "Test Instance"
    instance.url = "https://test.n8n.cloud"
    instance.api_key_encrypted = "encrypted_key"
    instance.enabled = True
    return instance


class TestInstanceService:
    """Test cases for InstanceService"""

    @patch("app.services.instance_service.AnalyticsService")
    def test_get_instance_success(self, mock_analytics, mock_db, mock_instance):
        """Test successfully getting an instance"""
        # Setup
        service = InstanceService()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_instance

        # Execute
        result = service.get_instance(mock_db, "instance_123", "test_user_123")

        # Verify
        assert result == mock_instance
        mock_db.query.assert_called_once()

    @patch("app.services.instance_service.AnalyticsService")
    def test_get_instance_not_found(self, mock_analytics, mock_db):
        """Test getting an instance that doesn't exist"""
        # Setup
        service = InstanceService()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Execute and expect exception
        with pytest.raises(HTTPException) as exc_info:
            service.get_instance(mock_db, "invalid_id", "test_user_123")

        # Verify
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()

    @patch("app.services.instance_service.AnalyticsService")
    def test_get_instance_by_id_success(self, mock_analytics, mock_db, mock_instance):
        """Test get_instance_by_id without user ownership check"""
        # Setup
        service = InstanceService()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_instance

        # Execute
        result = service.get_instance_by_id(mock_db, "instance_123")

        # Verify
        assert result == mock_instance
        mock_db.query.assert_called_once()

    @patch("app.services.instance_service.AnalyticsService")
    def test_get_instance_by_id_not_found(self, mock_analytics, mock_db):
        """Test get_instance_by_id when instance doesn't exist"""
        # Setup
        service = InstanceService()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Execute and expect exception
        with pytest.raises(HTTPException) as exc_info:
            service.get_instance_by_id(mock_db, "invalid_id")

        # Verify
        assert exc_info.value.status_code == 404
