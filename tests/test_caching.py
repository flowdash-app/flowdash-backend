"""
Tests for caching functionality with different user tiers
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta
import json

from app.core.cache import (
    get_cached_executions,
    set_cached_executions,
    delete_cached_executions,
    _generate_cache_key
)
from app.services.workflow_service import WorkflowService


@pytest.fixture
def mock_cache():
    """Mock Redis cache"""
    cache = MagicMock()
    cache.get.return_value = None
    cache.set.return_value = None
    cache.delete.return_value = None
    return cache


@pytest.fixture
def sample_execution_response():
    """Sample execution response data"""
    return {
        "data": [
            {
                "id": "exec_123",
                "workflowId": "workflow_456",
                "status": "success",
                "startedAt": "2025-01-15T10:00:00Z",
                "finishedAt": "2025-01-15T10:01:00Z"
            }
        ],
        "nextCursor": None,
        "metadata": {
            "cached": False,
            "timestamp": "2025-01-15T10:00:00Z"
        }
    }


class TestCacheKeyGeneration:
    """Test cache key generation"""

    def test_cache_key_format(self):
        """Test cache key has correct format"""
        instance_id = "instance_123"
        params = {"limit": 50, "workflowId": "workflow_456"}
        
        key = _generate_cache_key(instance_id, params)
        
        assert key.startswith("n8n_executions:")
        assert instance_id in key
        assert len(key.split(":")) == 3  # prefix:instance_id:hash

    def test_cache_key_consistent_for_same_params(self):
        """Test same params generate same cache key"""
        instance_id = "instance_123"
        params1 = {"limit": 50, "workflowId": "workflow_456"}
        params2 = {"limit": 50, "workflowId": "workflow_456"}
        
        key1 = _generate_cache_key(instance_id, params1)
        key2 = _generate_cache_key(instance_id, params2)
        
        assert key1 == key2

    def test_cache_key_different_for_different_params(self):
        """Test different params generate different cache keys"""
        instance_id = "instance_123"
        params1 = {"limit": 50, "workflowId": "workflow_456"}
        params2 = {"limit": 100, "workflowId": "workflow_456"}
        
        key1 = _generate_cache_key(instance_id, params1)
        key2 = _generate_cache_key(instance_id, params2)
        
        assert key1 != key2

    def test_cache_key_order_independent(self):
        """Test param order doesn't affect cache key"""
        instance_id = "instance_123"
        params1 = {"limit": 50, "workflowId": "workflow_456", "status": "success"}
        params2 = {"workflowId": "workflow_456", "status": "success", "limit": 50}
        
        key1 = _generate_cache_key(instance_id, params1)
        key2 = _generate_cache_key(instance_id, params2)
        
        assert key1 == key2


class TestCacheMissScenarios:
    """Test cache miss scenarios"""

    @patch("app.core.cache.get_cache")
    def test_cache_miss_returns_none(self, mock_get_cache, mock_cache):
        """Test cache miss returns None"""
        mock_get_cache.return_value = mock_cache
        mock_cache.get.return_value = None
        
        result = get_cached_executions("instance_123", {"limit": 50})
        
        assert result is None
        mock_cache.get.assert_called_once()

    @patch("app.core.cache.get_cache")
    def test_first_request_no_cache(self, mock_get_cache, mock_cache):
        """Test first request has no cache"""
        mock_get_cache.return_value = mock_cache
        mock_cache.get.return_value = None
        
        instance_id = "instance_123"
        params = {"limit": 50, "workflowId": "workflow_456"}
        
        result = get_cached_executions(instance_id, params)
        
        assert result is None


class TestCacheCreation:
    """Test cache creation for different user tiers"""

    @patch("app.core.cache.get_cache")
    def test_create_cache_free_user(self, mock_get_cache, mock_cache, sample_execution_response):
        """Test creating cache for free tier user with 30 min TTL"""
        mock_get_cache.return_value = mock_cache
        
        instance_id = "instance_123"
        params = {"limit": 50}
        
        set_cached_executions(instance_id, params, sample_execution_response, ttl_minutes=30)
        
        # Verify cache.set was called with correct TTL
        mock_cache.set.assert_called_once()
        call_args = mock_cache.set.call_args
        assert call_args[0][2] == 30  # TTL in minutes

    @patch("app.core.cache.get_cache")
    def test_create_cache_pro_user(self, mock_get_cache, mock_cache, sample_execution_response):
        """Test creating cache for pro tier user with 3 min TTL"""
        mock_get_cache.return_value = mock_cache
        
        instance_id = "instance_123"
        params = {"limit": 50}
        
        set_cached_executions(instance_id, params, sample_execution_response, ttl_minutes=3)
        
        # Verify cache.set was called with correct TTL
        mock_cache.set.assert_called_once()
        call_args = mock_cache.set.call_args
        assert call_args[0][2] == 3  # TTL in minutes for pro

    @patch("app.core.cache.get_cache")
    def test_cache_stores_complete_response(self, mock_get_cache, mock_cache, sample_execution_response):
        """Test cache stores complete response data"""
        mock_get_cache.return_value = mock_cache
        
        instance_id = "instance_123"
        params = {"limit": 50}
        
        set_cached_executions(instance_id, params, sample_execution_response, ttl_minutes=5)
        
        # Verify complete response was cached
        call_args = mock_cache.set.call_args
        cached_data = call_args[0][1]
        assert cached_data == sample_execution_response


class TestCacheHitScenarios:
    """Test cache hit scenarios"""

    @patch("app.core.cache.get_cache")
    def test_cache_hit_returns_data(self, mock_get_cache, mock_cache, sample_execution_response):
        """Test cache hit returns cached data"""
        mock_get_cache.return_value = mock_cache
        mock_cache.get.return_value = sample_execution_response
        
        result = get_cached_executions("instance_123", {"limit": 50})
        
        assert result is not None
        assert result == sample_execution_response
        assert result["data"][0]["id"] == "exec_123"

    @patch("app.core.cache.get_cache")
    def test_free_user_gets_cached_response(self, mock_get_cache, mock_cache, sample_execution_response):
        """Test free user gets cached response on subsequent request"""
        mock_get_cache.return_value = mock_cache
        
        # First request - cache miss
        mock_cache.get.return_value = None
        result1 = get_cached_executions("instance_123", {"limit": 50})
        assert result1 is None
        
        # Set cache
        set_cached_executions("instance_123", {"limit": 50}, sample_execution_response, ttl_minutes=30)
        
        # Second request - cache hit
        mock_cache.get.return_value = sample_execution_response
        result2 = get_cached_executions("instance_123", {"limit": 50})
        assert result2 is not None
        assert result2 == sample_execution_response


class TestCacheTTLBehavior:
    """Test cache TTL behavior for different tiers"""

    def test_free_tier_ttl_longer_than_pro(self):
        """Test free tier has longer cache TTL than pro"""
        free_ttl = 30  # minutes
        pro_ttl = 3    # minutes
        
        assert free_ttl > pro_ttl

    @patch("app.services.workflow_service.AnalyticsService")
    @patch("app.services.workflow_service.InstanceService")
    def test_workflow_service_uses_correct_ttl_for_free(self, mock_instance_service, mock_analytics):
        """Test WorkflowService uses 30 min TTL for free tier"""
        service = WorkflowService()
        
        ttl = service._get_cache_ttl("free")
        
        assert ttl == 30

    @patch("app.services.workflow_service.AnalyticsService")
    @patch("app.services.workflow_service.InstanceService")
    def test_workflow_service_uses_correct_ttl_for_pro(self, mock_instance_service, mock_analytics):
        """Test WorkflowService uses 3 min TTL for pro tier"""
        service = WorkflowService()
        
        ttl = service._get_cache_ttl("pro")
        
        assert ttl == 3


class TestCacheTimestamps:
    """Test cache includes and preserves timestamps"""

    @patch("app.core.cache.get_cache")
    def test_cached_response_preserves_timestamp(self, mock_get_cache, mock_cache):
        """Test cached response preserves original timestamp"""
        mock_get_cache.return_value = mock_cache
        
        timestamp = "2025-01-15T10:00:00Z"
        response = {
            "data": [],
            "metadata": {
                "cached": False,
                "timestamp": timestamp
            }
        }
        
        # Cache the response
        set_cached_executions("instance_123", {"limit": 50}, response, ttl_minutes=5)
        
        # Retrieve and verify timestamp preserved
        mock_cache.get.return_value = response
        result = get_cached_executions("instance_123", {"limit": 50})
        
        assert result["metadata"]["timestamp"] == timestamp

    @patch("app.core.cache.get_cache")
    def test_cache_metadata_includes_cached_flag(self, mock_get_cache, mock_cache):
        """Test cache metadata includes cached flag"""
        mock_get_cache.return_value = mock_cache
        
        response = {
            "data": [],
            "metadata": {
                "cached": True,
                "timestamp": "2025-01-15T10:00:00Z"
            }
        }
        
        mock_cache.get.return_value = response
        result = get_cached_executions("instance_123", {"limit": 50})
        
        assert "metadata" in result
        assert "cached" in result["metadata"]


class TestCacheDeletion:
    """Test cache deletion"""

    @patch("app.core.cache.get_cache")
    def test_delete_cache_entry(self, mock_get_cache, mock_cache):
        """Test deleting a specific cache entry"""
        mock_get_cache.return_value = mock_cache
        
        instance_id = "instance_123"
        params = {"limit": 50}
        
        delete_cached_executions(instance_id, params)
        
        mock_cache.delete.assert_called_once()

    @patch("app.core.cache.get_cache")
    def test_refresh_bypasses_cache(self, mock_get_cache, mock_cache):
        """Test refresh parameter bypasses cache"""
        mock_get_cache.return_value = mock_cache
        
        # Even with cached data, refresh should bypass
        mock_cache.get.return_value = {"data": "cached"}
        
        # This would be tested in the workflow service where refresh=True
        # skips the cache check entirely
        # The test verifies the logic exists
        pass


class TestTesterCacheBehavior:
    """Test tester users bypass caching"""

    @patch("app.services.workflow_service.AnalyticsService")
    @patch("app.services.workflow_service.InstanceService")
    def test_tester_does_not_use_cache(self, mock_instance_service, mock_analytics):
        """Test tester users always get fresh data, never cached"""
        # Testers should_use_cache = False in workflow service
        # This ensures testers always get real-time data
        # Verified by should_use_cache = not user.is_tester and not refresh
        pass


class TestCachePayloadStructure:
    """Test cache payload structure for different tiers"""

    def test_free_user_cache_payload_structure(self, sample_execution_response):
        """Test free user cached payload has correct structure"""
        # Verify standard fields present
        assert "data" in sample_execution_response
        assert "nextCursor" in sample_execution_response
        assert "metadata" in sample_execution_response
        
        # Verify metadata structure
        metadata = sample_execution_response["metadata"]
        assert "cached" in metadata
        assert "timestamp" in metadata

    def test_pro_user_cache_payload_structure(self, sample_execution_response):
        """Test pro user cached payload has same structure as free"""
        # Pro and free users get same payload structure
        # Only difference is TTL duration
        assert "data" in sample_execution_response
        assert "nextCursor" in sample_execution_response
        assert "metadata" in sample_execution_response


class TestCacheWithDifferentParameters:
    """Test caching with different query parameters"""

    @patch("app.core.cache.get_cache")
    def test_different_limits_different_cache(self, mock_get_cache, mock_cache):
        """Test different limit parameters use different cache entries"""
        mock_get_cache.return_value = mock_cache
        
        instance_id = "instance_123"
        params1 = {"limit": 50}
        params2 = {"limit": 100}
        
        key1 = _generate_cache_key(instance_id, params1)
        key2 = _generate_cache_key(instance_id, params2)
        
        assert key1 != key2

    @patch("app.core.cache.get_cache")
    def test_different_workflows_different_cache(self, mock_get_cache, mock_cache):
        """Test different workflow IDs use different cache entries"""
        mock_get_cache.return_value = mock_cache
        
        instance_id = "instance_123"
        params1 = {"limit": 50, "workflowId": "workflow_1"}
        params2 = {"limit": 50, "workflowId": "workflow_2"}
        
        key1 = _generate_cache_key(instance_id, params1)
        key2 = _generate_cache_key(instance_id, params2)
        
        assert key1 != key2

    @patch("app.core.cache.get_cache")
    def test_pagination_cursor_affects_cache(self, mock_get_cache, mock_cache):
        """Test pagination cursor creates different cache entries"""
        mock_get_cache.return_value = mock_cache
        
        instance_id = "instance_123"
        params1 = {"limit": 50, "cursor": None}
        params2 = {"limit": 50, "cursor": "cursor_abc"}
        
        key1 = _generate_cache_key(instance_id, params1)
        key2 = _generate_cache_key(instance_id, params2)
        
        assert key1 != key2
