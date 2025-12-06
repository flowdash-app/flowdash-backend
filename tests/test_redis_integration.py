"""
Integration tests for Redis cache operations
"""

import pytest
import json
from app.core.redis_cache import RedisCache


@pytest.mark.integration
class TestRedisIntegration:
    """Integration tests for Redis cache"""

    def test_redis_connection(self, redis_client):
        """Test basic Redis connection"""
        if redis_client is None:
            pytest.skip("Redis not available")
        
        # Test ping
        assert redis_client.ping() is True

    def test_redis_set_get_string(self, redis_client):
        """Test setting and getting a string value"""
        if redis_client is None:
            pytest.skip("Redis not available")

        # Set value
        redis_client.set("test_key", "test_value")
        
        # Get value
        value = redis_client.get("test_key")
        assert value.decode('utf-8') == "test_value"

    def test_redis_set_get_with_ttl(self, redis_client):
        """Test setting a value with TTL"""
        if redis_client is None:
            pytest.skip("Redis not available")

        # Set value with 60 second TTL
        redis_client.setex("test_ttl_key", 60, "test_value")
        
        # Get value
        value = redis_client.get("test_ttl_key")
        assert value.decode('utf-8') == "test_value"
        
        # Check TTL exists
        ttl = redis_client.ttl("test_ttl_key")
        assert ttl > 0 and ttl <= 60

    def test_redis_delete(self, redis_client):
        """Test deleting a key"""
        if redis_client is None:
            pytest.skip("Redis not available")

        # Set and verify
        redis_client.set("test_delete_key", "test_value")
        assert redis_client.get("test_delete_key") is not None
        
        # Delete
        redis_client.delete("test_delete_key")
        
        # Verify deleted
        assert redis_client.get("test_delete_key") is None

    def test_redis_increment(self, redis_client):
        """Test incrementing a counter"""
        if redis_client is None:
            pytest.skip("Redis not available")

        # Increment new key
        value = redis_client.incr("test_counter")
        assert value == 1
        
        # Increment again
        value = redis_client.incr("test_counter")
        assert value == 2
        
        # Increment by amount
        value = redis_client.incrby("test_counter", 5)
        assert value == 7


@pytest.mark.integration
class TestRedisCacheClass:
    """Integration tests for RedisCache class"""

    def test_cache_set_and_get_dict(self):
        """Test setting and getting a dictionary"""
        cache = RedisCache()
        
        if not cache.ping():
            pytest.skip("Redis not available")

        # Set cache
        test_data = {"key": "value", "number": 123}
        cache.set("test_cache_dict", test_data, ttl_minutes=5)
        
        # Get cache
        retrieved = cache.get("test_cache_dict")
        assert retrieved is not None
        assert retrieved["key"] == "value"
        assert retrieved["number"] == 123

    def test_cache_set_and_get_int(self):
        """Test setting and getting an integer"""
        cache = RedisCache()
        
        if not cache.ping():
            pytest.skip("Redis not available")

        # Set cache
        cache.set("test_cache_int", 42, ttl_minutes=5)
        
        # Get cache
        retrieved = cache.get_int("test_cache_int")
        assert retrieved == 42

    def test_cache_delete(self):
        """Test deleting a cached value"""
        cache = RedisCache()
        
        if not cache.ping():
            pytest.skip("Redis not available")

        # Set and verify
        cache.set("test_cache_delete", {"data": "test"}, ttl_minutes=5)
        assert cache.get("test_cache_delete") is not None
        
        # Delete
        cache.delete("test_cache_delete")
        
        # Verify deleted
        assert cache.get("test_cache_delete") is None

    def test_cache_miss(self):
        """Test cache miss returns None"""
        cache = RedisCache()
        
        if not cache.ping():
            pytest.skip("Redis not available")

        # Get non-existent key
        result = cache.get("non_existent_key_12345")
        assert result is None

    def test_acquire_release_lock(self):
        """Test acquiring and releasing a distributed lock"""
        cache = RedisCache()
        
        if not cache.ping():
            pytest.skip("Redis not available")

        lock_key = "test_lock"
        
        # Acquire lock
        acquired = cache.acquire_lock(lock_key, timeout_seconds=10)
        assert acquired is True
        
        # Try to acquire same lock (should fail)
        acquired_again = cache.acquire_lock(lock_key, timeout_seconds=1, block_seconds=0)
        assert acquired_again is False
        
        # Release lock
        cache.release_lock(lock_key)
        
        # Should be able to acquire now
        acquired_after = cache.acquire_lock(lock_key, timeout_seconds=10)
        assert acquired_after is True
        
        # Clean up
        cache.release_lock(lock_key)
