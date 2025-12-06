"""
Tests for rate limiting functionality
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

from app.core.rate_limit_middleware import RateLimitMiddleware, RATE_LIMITS


@pytest.fixture
def mock_cache():
    """Mock cache for rate limiting"""
    cache = MagicMock()
    cache.get_int.return_value = 0
    cache.set.return_value = None
    return cache


@pytest.fixture
def mock_request():
    """Create mock request"""
    request = MagicMock(spec=Request)
    request.url.path = "/api/v1/workflows"
    request.headers = {}
    request.state = MagicMock()
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    return request


@pytest.fixture
def mock_free_user():
    """Create mock free tier user"""
    user = MagicMock()
    user.id = "free_user_123"
    user.plan_tier = "free"
    user.is_tester = False
    return user


@pytest.fixture
def mock_pro_user():
    """Create mock pro tier user"""
    user = MagicMock()
    user.id = "pro_user_123"
    user.plan_tier = "pro"
    user.is_tester = False
    return user


class TestRateLimitingFreeUser:
    """Test rate limiting for free tier users"""

    @patch("app.core.rate_limit_middleware.get_cache")
    def test_free_user_within_limit(self, mock_get_cache, mock_cache, mock_request, mock_free_user):
        """Test free user within rate limit gets through"""
        mock_get_cache.return_value = mock_cache
        mock_cache.get_int.return_value = 30  # 30 requests in current minute
        
        middleware = RateLimitMiddleware(MagicMock())
        middleware.cache = mock_cache
        
        # Free tier allows 60 requests per minute
        result = middleware._check_user_rate_limit("free_user_123", "free", mock_request)
        
        assert result is True
        # Verify cache was updated
        mock_cache.set.assert_called()

    @patch("app.core.rate_limit_middleware.get_cache")
    def test_free_user_exceeds_per_minute_limit(self, mock_get_cache, mock_cache, mock_request, mock_free_user):
        """Test free user exceeding per-minute limit gets 429"""
        mock_get_cache.return_value = mock_cache
        # User has already made 60 requests this minute
        mock_cache.get_int.return_value = 60
        
        middleware = RateLimitMiddleware(MagicMock())
        middleware.cache = mock_cache
        
        # Free tier allows 60 requests per minute
        result = middleware._check_user_rate_limit("free_user_123", "free", mock_request)
        
        assert result is False

    @patch("app.core.rate_limit_middleware.get_cache")
    def test_free_user_exceeds_per_hour_limit(self, mock_get_cache, mock_cache, mock_request):
        """Test free user exceeding per-hour limit gets 429"""
        mock_get_cache.return_value = mock_cache
        
        def get_int_side_effect(key):
            if "minute" in key:
                return 30  # Within minute limit
            if "hour" in key:
                return 1000  # At hourly limit
            return 0
        
        mock_cache.get_int.side_effect = get_int_side_effect
        
        middleware = RateLimitMiddleware(MagicMock())
        middleware.cache = mock_cache
        
        # Free tier allows 1000 requests per hour
        result = middleware._check_user_rate_limit("free_user_123", "free", mock_request)
        
        assert result is False

    @patch("app.core.rate_limit_middleware.get_db")
    @patch("app.core.rate_limit_middleware.get_cache")
    async def test_free_user_429_response_format(self, mock_get_cache, mock_get_db, mock_cache, mock_request):
        """Test 429 response contains correct headers and body for free user"""
        mock_get_cache.return_value = mock_cache
        mock_cache.get_int.return_value = 60  # At limit
        
        # Mock get_db to avoid database connection
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        
        # Set up authenticated request with token
        mock_request.headers = {"Authorization": "Bearer test_token"}
        
        # Mock Firebase token verification
        with patch("app.core.rate_limit_middleware.verify_firebase_token") as mock_verify:
            mock_verify.return_value = {"uid": "free_user_123"}
            
            # Mock user from database
            mock_user = MagicMock()
            mock_user.plan_tier = "free"
            mock_user.is_tester = False
            mock_db.query.return_value.filter.return_value.first.return_value = mock_user
            
            middleware = RateLimitMiddleware(MagicMock())
            middleware.cache = mock_cache
            
            # Mock call_next
            async def mock_call_next(req):
                return JSONResponse({"status": "ok"})
            
            response = await middleware.dispatch(mock_request, mock_call_next)
            
            # Verify 429 response
            assert response.status_code == 429
            body = response.body.decode()
            assert "Rate limit exceeded" in body
            assert "free" in body.lower()
            
            # Verify headers
            assert "Retry-After" in response.headers
            assert response.headers["Retry-After"] == "60"


class TestRateLimitingProUser:
    """Test rate limiting for pro tier users"""

    @patch("app.core.rate_limit_middleware.get_cache")
    def test_pro_user_higher_limits(self, mock_get_cache, mock_cache, mock_request):
        """Test pro user has higher rate limits than free"""
        mock_get_cache.return_value = mock_cache
        mock_cache.get_int.return_value = 80  # Would exceed free limit
        
        middleware = RateLimitMiddleware(MagicMock())
        middleware.cache = mock_cache
        
        # Pro tier allows 120 requests per minute
        result = middleware._check_user_rate_limit("pro_user_123", "pro", mock_request)
        
        assert result is True

    @patch("app.core.rate_limit_middleware.get_cache")
    def test_pro_user_exceeds_limit(self, mock_get_cache, mock_cache, mock_request):
        """Test pro user exceeding their limit gets 429"""
        mock_get_cache.return_value = mock_cache
        mock_cache.get_int.return_value = 120  # At pro limit
        
        middleware = RateLimitMiddleware(MagicMock())
        middleware.cache = mock_cache
        
        # Pro tier allows 120 requests per minute
        result = middleware._check_user_rate_limit("pro_user_123", "pro", mock_request)
        
        assert result is False


class TestRateLimitingTester:
    """Test rate limiting for tester users"""

    @patch("app.core.rate_limit_middleware.get_db")
    @patch("app.core.rate_limit_middleware.get_cache")
    async def test_tester_bypasses_rate_limit(self, mock_get_cache, mock_get_db, mock_cache, mock_request):
        """Test tester users bypass rate limiting"""
        mock_get_cache.return_value = mock_cache
        mock_cache.get_int.return_value = 1000  # Way over limit
        
        # Mock get_db
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        
        # Set up authenticated request with token
        mock_request.headers = {"Authorization": "Bearer test_token"}
        
        # Mock Firebase token verification
        with patch("app.core.rate_limit_middleware.verify_firebase_token") as mock_verify:
            mock_verify.return_value = {"uid": "tester_123"}
            
            # Set up tester user in database
            tester_user = MagicMock()
            tester_user.id = "tester_123"
            tester_user.is_tester = True
            tester_user.plan_tier = "free"
            mock_db.query.return_value.filter.return_value.first.return_value = tester_user
            
            middleware = RateLimitMiddleware(MagicMock())
            middleware.cache = mock_cache
            
            # Mock call_next
            async def mock_call_next(req):
                return JSONResponse({"status": "ok"})
            
            response = await middleware.dispatch(mock_request, mock_call_next)
            
            # Verify request went through (not 429)
            assert response.status_code == 200


class TestRateLimitConfiguration:
    """Test rate limit configuration"""

    def test_rate_limit_config_values(self):
        """Test rate limit configuration has expected values"""
        assert RATE_LIMITS["free"]["per_minute"] == 60
        assert RATE_LIMITS["free"]["per_hour"] == 1000
        assert RATE_LIMITS["pro"]["per_minute"] == 120
        assert RATE_LIMITS["pro"]["per_hour"] == 5000

    def test_pro_plan_higher_than_free(self):
        """Test pro plan has higher limits than free"""
        assert RATE_LIMITS["pro"]["per_minute"] > RATE_LIMITS["free"]["per_minute"]
        assert RATE_LIMITS["pro"]["per_hour"] > RATE_LIMITS["free"]["per_hour"]


class TestRateLimitHeaders:
    """Test rate limit response headers"""

    @patch("app.core.rate_limit_middleware.get_db")
    @patch("app.core.rate_limit_middleware.get_cache")
    async def test_rate_limit_headers_added(self, mock_get_cache, mock_get_db, mock_cache, mock_request):
        """Test rate limit headers are added to response"""
        mock_get_cache.return_value = mock_cache
        mock_cache.get_int.return_value = 10
        
        # Mock get_db
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        
        # Set up authenticated request with token
        mock_request.headers = {"Authorization": "Bearer test_token"}
        
        # Mock Firebase token verification
        with patch("app.core.rate_limit_middleware.verify_firebase_token") as mock_verify:
            mock_verify.return_value = {"uid": "user_123"}
            
            # Mock user from database
            mock_user = MagicMock()
            mock_user.plan_tier = "free"
            mock_user.is_tester = False
            mock_db.query.return_value.filter.return_value.first.return_value = mock_user
            
            middleware = RateLimitMiddleware(MagicMock())
            middleware.cache = mock_cache
            
            async def mock_call_next(req):
                return JSONResponse({"status": "ok"})
            
            response = await middleware.dispatch(mock_request, mock_call_next)
            
            # Verify rate limit headers
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers
            assert "X-RateLimit-Reset" in response.headers
            assert response.headers["X-RateLimit-Limit"] == "60"  # Free tier limit

    @patch("app.core.rate_limit_middleware.get_cache")
    def test_remaining_requests_calculation(self, mock_get_cache, mock_cache):
        """Test remaining requests calculation is accurate"""
        mock_get_cache.return_value = mock_cache
        mock_cache.get_int.return_value = 45  # 45 requests made
        
        middleware = RateLimitMiddleware(MagicMock())
        middleware.cache = mock_cache
        
        remaining = middleware._get_remaining_requests("user_123", "free")
        
        # Free tier: 60 limit - 45 made - 1 current = 14 remaining
        assert remaining == 14
