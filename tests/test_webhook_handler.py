"""
Tests for webhook handler - specifically testing tester access to push notifications
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.notifier.webhook_handler import handle_n8n_error, N8NErrorRequest, Severity
from app.models.user import User
from app.models.n8n_instance import N8NInstance


@pytest.fixture
def mock_db():
    """Create a mock database session"""
    return MagicMock(spec=Session)


@pytest.fixture
def mock_free_user():
    """Create a mock free tier user (not a tester)"""
    user = MagicMock(spec=User)
    user.id = "test_user_123"
    user.email = "test@example.com"
    user.plan_tier = "free"
    user.is_tester = False
    return user


@pytest.fixture
def mock_tester_user():
    """Create a mock tester user on free plan"""
    user = MagicMock(spec=User)
    user.id = "tester_user_123"
    user.email = "tester@example.com"
    user.plan_tier = "free"
    user.is_tester = True
    return user


@pytest.fixture
def mock_pro_user():
    """Create a mock pro tier user"""
    user = MagicMock(spec=User)
    user.id = "pro_user_123"
    user.email = "pro@example.com"
    user.plan_tier = "pro"
    user.is_tester = False
    return user


@pytest.fixture
def mock_instance():
    """Create a mock n8n instance"""
    instance = MagicMock(spec=N8NInstance)
    instance.id = "instance_123"
    instance.user_id = "test_user_123"
    instance.enabled = True
    instance.name = "Test Instance"
    return instance


@pytest.fixture
def sample_error_request():
    """Create a sample N8N error request"""
    return N8NErrorRequest(
        executionId="exec_123",
        workflowId="workflow_456",
        instanceId="instance_123",
        workflowName="Test Workflow",
        severity=Severity.ERROR,
        error={"message": "Test error message"},
    )


class TestWebhookHandlerTesterAccess:
    """Test cases for tester access to push notifications"""

    @pytest.mark.asyncio
    @patch("app.notifier.webhook_handler.InstanceService")
    @patch("app.notifier.webhook_handler.FCMService")
    @patch("app.notifier.webhook_handler.PlanConfiguration")
    @patch("app.notifier.webhook_handler.AnalyticsService")
    async def test_free_user_without_tester_rejected(
        self,
        mock_analytics,
        mock_plan_config,
        mock_fcm_service,
        mock_instance_service,
        mock_db,
        mock_free_user,
        mock_instance,
        sample_error_request,
    ):
        """Test that free tier user without tester status is rejected"""
        # Setup mocks
        mock_instance_service_instance = mock_instance_service.return_value
        mock_instance_service_instance.get_instance_by_id.return_value = mock_instance

        mock_db.query.return_value.filter.return_value.first.return_value = (
            mock_free_user
        )

        # Free plan does not have push notifications
        mock_plan_config.get_plan.return_value = {
            "push_notifications": False,
            "name": "Free",
        }

        # Execute and expect 403 error
        with pytest.raises(HTTPException) as exc_info:
            await handle_n8n_error(sample_error_request, mock_db)

        # Verify exception
        assert exc_info.value.status_code == 403
        assert (
            "Push notifications are not available on the Free plan"
            in exc_info.value.detail
        )

        # Verify FCM was not called
        mock_fcm_service.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.notifier.webhook_handler.InstanceService")
    @patch("app.notifier.webhook_handler.FCMService")
    @patch("app.notifier.webhook_handler.PlanConfiguration")
    @patch("app.notifier.webhook_handler.AnalyticsService")
    async def test_tester_on_free_plan_allowed(
        self,
        mock_analytics,
        mock_plan_config,
        mock_fcm_service,
        mock_instance_service,
        mock_db,
        mock_tester_user,
        mock_instance,
        sample_error_request,
    ):
        """Test that tester on free plan IS allowed to receive push notifications"""
        # Setup mocks
        mock_instance = MagicMock(spec=N8NInstance)
        mock_instance.id = "instance_123"
        mock_instance.user_id = "tester_user_123"
        mock_instance.enabled = True

        mock_instance_service_instance = mock_instance_service.return_value
        mock_instance_service_instance.get_instance_by_id.return_value = mock_instance

        mock_db.query.return_value.filter.return_value.first.return_value = (
            mock_tester_user
        )

        # Free plan does not have push notifications
        mock_plan_config.get_plan.return_value = {
            "push_notifications": False,
            "name": "Free",
        }

        # Setup FCM service mock
        mock_fcm_instance = mock_fcm_service.return_value
        mock_fcm_instance.send_error_notification = AsyncMock()

        # Setup analytics mock
        mock_analytics_instance = mock_analytics.return_value
        mock_analytics_instance.log_success = MagicMock()
        mock_analytics_instance.log_failure = MagicMock()

        # Execute - should NOT raise exception for tester
        result = await handle_n8n_error(sample_error_request, mock_db)

        # Verify success response
        assert result["status"] == "success"
        assert result["message"] == "Notification sent"
        assert result["user_id"] == "tester_user_123"

        # Verify FCM notification was sent
        mock_fcm_instance.send_error_notification.assert_called_once()

        # Verify analytics logged success
        mock_analytics_instance.log_success.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.notifier.webhook_handler.InstanceService")
    @patch("app.notifier.webhook_handler.FCMService")
    @patch("app.notifier.webhook_handler.PlanConfiguration")
    @patch("app.notifier.webhook_handler.AnalyticsService")
    async def test_pro_user_allowed(
        self,
        mock_analytics,
        mock_plan_config,
        mock_fcm_service,
        mock_instance_service,
        mock_db,
        mock_pro_user,
        sample_error_request,
    ):
        """Test that pro tier user IS allowed to receive push notifications"""
        # Setup mocks
        mock_instance = MagicMock(spec=N8NInstance)
        mock_instance.id = "instance_123"
        mock_instance.user_id = "pro_user_123"
        mock_instance.enabled = True

        mock_instance_service_instance = mock_instance_service.return_value
        mock_instance_service_instance.get_instance_by_id.return_value = mock_instance

        mock_db.query.return_value.filter.return_value.first.return_value = (
            mock_pro_user
        )

        # Pro plan has push notifications
        mock_plan_config.get_plan.return_value = {
            "push_notifications": True,
            "name": "Pro",
        }

        # Setup FCM service mock
        mock_fcm_instance = mock_fcm_service.return_value
        mock_fcm_instance.send_error_notification = AsyncMock()

        # Setup analytics mock
        mock_analytics_instance = mock_analytics.return_value
        mock_analytics_instance.log_success = MagicMock()
        mock_analytics_instance.log_failure = MagicMock()

        # Execute - should NOT raise exception
        result = await handle_n8n_error(sample_error_request, mock_db)

        # Verify success response
        assert result["status"] == "success"
        assert result["message"] == "Notification sent"
        assert result["user_id"] == "pro_user_123"

        # Verify FCM notification was sent
        mock_fcm_instance.send_error_notification.assert_called_once()

        # Verify analytics logged success
        mock_analytics_instance.log_success.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.notifier.webhook_handler.InstanceService")
    @patch("app.notifier.webhook_handler.PlanConfiguration")
    @patch("app.notifier.webhook_handler.AnalyticsService")
    async def test_disabled_instance_rejected(
        self,
        mock_analytics,
        mock_plan_config,
        mock_instance_service,
        mock_db,
        mock_tester_user,
        sample_error_request,
    ):
        """Test that disabled instance is rejected even for testers"""
        # Setup mocks
        mock_instance = MagicMock(spec=N8NInstance)
        mock_instance.id = "instance_123"
        mock_instance.user_id = "tester_user_123"
        mock_instance.enabled = False  # Disabled

        mock_instance_service_instance = mock_instance_service.return_value
        mock_instance_service_instance.get_instance_by_id.return_value = mock_instance

        mock_db.query.return_value.filter.return_value.first.return_value = (
            mock_tester_user
        )

        # Execute and expect 403 error
        with pytest.raises(HTTPException) as exc_info:
            await handle_n8n_error(sample_error_request, mock_db)

        # Verify exception
        assert exc_info.value.status_code == 403
        assert "Instance is disabled" in exc_info.value.detail
